# SPEC-147 — 盘中推送 hysteresis（VIX spike / SPX stop / ES credit stop）

**来源**: 生产事故 2026-07-23。PM 报"今天这一串推送有点乱"——VIX 全天在 8% WARNING 阈值线附近来回蹭，`intraday_monitor` 全天推了 4 组 WARNING/cleared（实际用真实 VIX 5 分钟数据核对，理论上按硬切线逻辑能推 8+ 组）。

## 根因

`signals/intraday.py` 的 `_classify_spike`/`_classify_stop` 与 `notify/telegram_bot.py` 的 `_check_es_credit_stop`，三条阈值线全部是**硬切点、零缓冲带**：超过线一次就 WARNING，跌破线（哪怕只低 0.01）就整个状态清零回 NONE。`intraday_monitor()` 的状态机（`_intraday_state`）严格跟着这条线走：任何一次跌破都被当成"真的解除"，下次哪怕只涨回超一点点，也被当成"全新一次告警"重新推送。2026-07-23 当天 VIX 在 18.9~19.4（对应 baseline 17.67 的 7~10% 区间）晃了一整个上午，正好横跨 8% 这条线，于是产生了反复的 WARNING→cleared→WARNING→cleared。

同类排查确认三处状态机全部同一缺陷：
1. VIX spike（`SpikeLevel`）— 已实锤（今天真实触发）
2. SPX stop（`StopLevel`）— 代码结构完全相同，与 VIX 共用同一条 `was_elevated`/`now_clear` 组合判定；SPX 今天没抖是因为 SPX 本身没在阈值附近晃，不代表没有这个洞
3. ES credit stop（`EsStopLevel`）— 独立第三套状态机，同样硬切+立即清零

前端 `/api/intraday`（`web/server.py`）直接调用同一批 `get_vix_spike`/`get_spx_stop` 函数，60 秒轮询一次，同样会在阈值线附近闪烁徽章颜色——修好共享的分类函数，前端徽章自动一起好，不需要单独改。

## 评估过并放弃的方案：gateway dedupe_key

最初设想是给这几条推送接上 gateway 的 `dedupe_key`/`clears`（同日只报一次，只有升级才重发）。但推演后发现这个工具用错了地方：`dedupe_key` 是按自然日粒度的"同key不重发"，如果 VIX 真的先冲高、真的完全回落、下午又真的再冲一次——那是两次独立的真实事件，理应都推送；但 dedupe_key 会把第二次真实的 WARNING 当"重复"静默吞掉，属于比"偶尔多推几条"更严重的错误（真实信号被吞比噪音更危险）。改用 hysteresis（缓冲带）从源头消灭噪音，不动 dedupe_key。

## 修复

**`signals/intraday.py`**：新增 `VIX_SPIKE_CLEAR=0.05`（vs WARN 0.08）、`SPX_STOP_CLEAR=0.005`（vs CAUTION 0.01），新增纯函数 `hysteresis_spike_level(pct, prev_level)` / `hysteresis_stop_level(pct, prev_level)`——一旦进入 WARNING/CAUTION，只有跌破更低的 CLEAR 线才真正解除，卡在缓冲区内维持原状态。`_classify_spike`/`_classify_stop` 保持纯函数不变（批量回测/分析调用点零影响）。

**`notify/telegram_bot.py`**：新增 `ES_STOP_CLEAR_MULT=1.5`（vs WARN 2.0）与 `_hysteresis_es_stop_level`；`intraday_monitor()` 三处（VIX 升级判定、SPX 升级判定、cleared 组合判定、ES 升级/清除判定、状态持久化）全部改用 hysteresis 后的 `eff_spike`/`eff_stop`/`eff_es_stop`，推送正文仍用原始 dataclass 显示真实瞬时读数（不撒谎，只是"要不要推"的判断变了）。

## AC

- **AC-1**：`hysteresis_spike_level`/`hysteresis_stop_level`/`_hysteresis_es_stop_level` 纯函数覆盖：进场触发、缓冲区内维持原状态、真正跌穿 CLEAR 线才解除
- **AC-2**：用 2026-07-23 当天真实 VIX 5 分钟收盘价重放的 spike_pct 序列跑一遍 `intraday_monitor`，验证 8 次原始阈值穿越被折叠成 1 次 WARNING + 1 次 cleared + 1 次真实二次 WARNING（而非旧逻辑的 5 次 WARNING）
- **AC-3**：既有边界测试（`test_spec_046_quotes`/`test_spec_121` 对 `_check_es_credit_stop`/pure classify 的精确边界断言）不受影响——hysteresis 只包在 `intraday_monitor` 的状态判定层，单次调用的纯分类语义不变
- 回归：`tests/test_spec_086.py` 两处依赖旧"跌破 WARN 即清除"假设的断言按新行为更新（先证明改动前失败/新行为不成立，再证明改动后通过）；全套 1271 passed 无新增失败

## 边界

前端 `/api/intraday` 徽章不单独加 hysteresis（如需状态化会引入第二套跟 bot 不同步的 prev-level bookkeeping，且被动看板场景没有推送轰炸问题，展示瞬时真实读数更诚实）——共享的分类函数一改，两边自动同步获益；如需要前端也做视觉防闪烁，另行提出。
