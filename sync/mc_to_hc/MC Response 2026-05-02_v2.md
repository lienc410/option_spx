# MC Response 2026-05-02 (v2 OCR Cleanup)

> 说明：
> - 本文件是对扫描件 `sync/mc_to_hc/MC Response 2026-05-02.md` 的**第一轮 OCR / 排版校正稿**
> - **不代表 HC 已吸收或接受其中内容**
> - 目标仅为：尽量消除扫描造成的字符损坏、编号损坏、路径损坏与明显断句问题，便于回发 MC 做内容确认
> - 若个别数字在扫描件中无法 100% 还原，保留为 `[OCR unclear]` 或按上下文做最小、可解释的修复
> - OCR 规则补充：扫描件中大量 `Δ / delta` 被误识别为大写字母 `A`；本稿凡遇到 `A ann_roe`、`A total_pnl`、`A_n`、`A trades` 等模式，默认按 `Δ / delta` 语义恢复，除非上下文明确不是该含义
> - 2026-05-03 更新：已根据 `sync/mc_to_hc/MC Response 2026-05-02 corrections_v2.md` 吸收 5 项 MC 明确给出的数字级 errata（`iron_condor_hv` 两项、`n_days`、6 笔 `IC` `entry_credit`、3 笔 `roll_21dte` 的 `dte_at_exit`）

# MC Response 2026-05-02

类型：response handoff  
对应 HC 包：`sync/hc_to_mc/HC_return_2026-05-02.md`

回应针对四件事：
1. HC 状态 ingest 确认
2. `SPEC-077` AC3 attribution data
3. `IC regular` 6-trade ledger
4. `SPEC-075 / SPEC-076` adoption 输入包

---

## 背景说明

HC 在 `2026-05-02` 完成：

- batch 1 + batch 2 共 5 个 SPEC 复现
- `SPEC-074 / SPEC-077 / SPEC-078 / SPEC-079 / SPEC-080` 全部 `DONE`
- tieout #2 / tieout #3 `PASS`
- `Q021` closed
- `Q036` 方向已对齐
- `Q038` 已 flip 到 `shadow`（old Air）

HC 提出：

- 2 项 MC 数据请求
- 1 项 adoption 输入包请求

本 response 一次性给齐，不再要求 HC 等下一周期。

---

## 一、HC 状态 ingest 确认

MC 确认接收 HC 的以下状态变更；对应内容已在 MC 索引层更新。

### A. SPEC 复现完成度

#### SPEC-074

- 校验：`SPEC-074`
- HC 状态：`DONE`
- MC 状态：`DONE`
- 分歧：永久 `SPEC-056c` / `DIAG Gate 1`
- MC 接受 HC 移除作为 canonical
- 此分歧不会再讨论

#### SPEC-077

- 校验：`SPEC-077`
- HC 状态：`DONE`（含 `AC3 documented FAIL`）
- MC 状态：`DONE`
- AC3 量级 gap 详见本 response §2

#### SPEC-078

- 校验：`SPEC-078`
- HC 状态：`DONE`
- MC 状态：`DONE`
- 全对齐

#### SPEC-079

- 校验：`SPEC-079`
- HC 状态：`DONE`
- MC 状态：`DONE`
- 全对齐

#### SPEC-080

- 校验：`SPEC-080`
- HC 状态：`DONE`
- MC 状态：`DONE`
- 全对齐

---

### B. Q 编号状态

#### Q021

- 在 HC 端关闭
- MC 侧：`Q021` 自 `2026-04-26` sync 起已 `resolved`
- 双方一致

#### Q036

- 方向已对齐
- HC 接受 MC `ESCALATE` 方向
- `SPEC-075 / SPEC-076` 进入下一批 adoption，而非继续作为分歧讨论

#### Q038

- HC live runtime 已 flip 到 `shadow`
- old Air commit：`3da1f5f`
- `bcd_comfort_filter_mode = shadow`
- `bcd_stop_tightening_mode = shadow`

#### overlay_f_mode

- 在 HC 侧当前不存在
- sync 后会随 `SPEC-075` 加入

#### Q039

- 双方均保持 `research only`
- 即 `IVP gate sensitivity` question
- 本 response §3 提供 MC 的 6 笔 ledger

---

### C. PARAM_MASTER 对齐

HC 反馈：6 个参数多数已对齐，1 项缺失：

- `overlay_f_mode`

该字段未在 HC 存在。  
理由：`SPEC-075` 未在 HC 复现，此为预期，不视为分歧。

---

## 二、SPEC-077 AC3 attribution data

HC 请求内容：

- MC 全样本 ledger total PnL delta
- MC ROE formula
- baseline denominator
- trade count by strategy
- exit reason split

MC 提供完整数据如下。

### 2.1 ROE formula

MC 使用：

- `simple average annual ROE`
- 不是 CAGR
- 不是 compound

公式：

```text
ann_roe_pct = total_pnl / start_eq / n_years * 100
```

其中：

- `start_eq = 100,000 USD`
- canonical：`Q029 1-SPX uniform scale`
- `total_pnl = end_eq - start_eq`
- `n_years = (end_date - start_date).days / 365.25`

### 2.2 Sample window

MC 全样本：

- 起点：`1999-01-01`
- 终点：`2026-05-02`
- `n_years = 26.3217`
- `n_days = 6621`

HC 全样本：

- 起点：`2007-01-01`
- 终点：`today`
- `n_years = 19.32`

差异：

- MC 多覆盖 `1999 → 2007`
- 该窗口包含：
  - `2000–2002` dot-com bust
  - `2008–2009` financial crisis
  - 高 vol regime 下 `profit_target` shift 影响最大

这被 MC 视为 HC / MC 量级 gap 的部分解释来源。

### 2.3 Baseline denominator

`denominator = start_eq = 100,000`

- 不随 equity 增长变化
- 即：不 compound

举例：

- 若 `end_eq = 387,248.42`
- 则 `total_pnl = 287,248.42`
- `ann_roe = 287,248.42 / 100,000 / 26.3217 * 100 = 10.9130%`

### 2.4 PT = 0.50 完整数字

- `start_eq = 100,000`
- `end_eq = 387,248.42`
- `total_pnl_dollar = +287,248.42`
- `n_years = 26.3217`
- `n_days = 6621`
- `ann_roe_pct = 10.9130`
- `daily_sharpe = 1.0177`
- `max_dd_pct = -15.38`
- `mdd_dollar = 60,608`
- `trades_total = 447`

### 2.5 PT = 0.60 完整数字

按扫描件算术关系最小修复为：

- `start_eq = 100,000`
- `end_eq = 411,168.66`
- `total_pnl_dollar = +311,168.66`
- `n_years = 26.3217`
- `n_days = 6621`
- `ann_roe_pct = 11.8218`
- `daily_sharpe = 1.1077`
- `max_dd_pct = -14.32`
- `mdd_dollar = 59,512`
- `trades_total = 433`

> 注：`end_eq` / `total_pnl_dollar` / `ann_roe_pct` 为按扫描件上下文及 delta 算术关系恢复；建议 MC 最终确认。

### 2.6 DELTA（PT 0.60 - PT 0.50）

- `Δ ann_roe = +0.9088pp`
- `Δ total_pnl = +23,920.24 USD`
- `Δ daily_sharpe = +0.09`
- `Δ max_dd` 改善 `1.06pp`
- `Δ trades = -14`

### 2.7 By strategy

格式：

```text
strategy
PT 0.50: trades / pnl
PT 0.60: trades / pnl
delta
```

#### bear_call_spread_hv

- PT 0.50：23 笔 / +611
- PT 0.60：20 笔 / +698
- delta：+87

#### bull_call_diagonal

- PT 0.50：102 笔 / +73,499
- PT 0.60：102 笔 / +73,597
- delta：+98 `[OCR minimal fix]`

#### bull_put_spread

- PT 0.50：131 笔 / +21,003
- PT 0.60：128 笔 / +24,459
- delta：+3,456

> 最大贡献者

#### bull_put_spread_hv

- PT 0.50：55 笔 / +7,616
- PT 0.60：53 笔 / +7,591
- delta：-26 `[likely -25 / -26; OCR uncertain]`
- 基本不受影响

#### iron_condor

- PT 0.50：61 笔 / +4,277
- PT 0.60：57 笔 / +3,563
- delta：-714

#### iron_condor_hv

- PT 0.50：75 笔 / +13,679
- PT 0.60：73 笔 / +13,539
- delta：-140

### 2.8 By exit_reason

这是 attribution 主线。

格式：

```text
reason
PT 0.50: trades / pnl
PT 0.60: trades / pnl
delta_n
```

#### 50pct_profit

- PT 0.50：110 笔 / +37,678
- PT 0.60：69 笔 / +24,733
- `Δ_n = -41`

#### 50pct_profit_early

- PT 0.50：44 笔 / +24,592
- PT 0.60：15 笔 / +9,097
- `Δ_n = -29`

#### roll_21dte

- PT 0.50：263 笔 / +162,332
- PT 0.60：315 笔 / +191,338
- `Δ_n = +52`
- 最大数量增长来源

#### roll_up

- PT 0.50：2 笔 / +362
- PT 0.60：6 笔 / +2,292
- `Δ_n = +4`

#### stop_loss

- PT 0.50：12 笔 / -56,236
- PT 0.60：11 笔 / -52,503
- `Δ_n = -1`

#### trend_flip

- PT 0.50：16 笔 / -48,041
- PT 0.60：17 笔 / -51,509
- `Δ_n = +1`

### 2.9 Attribution 解读

机制：

- `profit_target` 从 `0.50` 升到 `0.60`
- 导致约 70 笔 trade 原本会在：
  - `50pct_profit`
  - `50pct_profit_early`
 退出
- 现在改为 `roll_21dte` 退出
- `roll_21dte` 比早退贡献更多，约 `+29,000 USD`
- 这被 MC 视为 `ann_roe +0.91pp` 的主因

非主因：

- 策略选择基本不变
- `Overlay-F` 等其他 SPEC 不变，仅 exit timing 变化

### 2.10 与 HC 对比

- HC AC3：`+0.0856pp`
- MC AC3：`+0.9088pp`
- 约 10× 差距

MC 可能解释：

1. **sample window**
   - HC：19.32 年
   - MC：26.32 年
   - MC 多 7 年，包含 `2000` 与 `2008` 高 vol regime
   - `roll vs early exit` 在高 vol 环境影响最大

2. **永久分歧 SPEC-056c**
   - HC 移除 `DIAG Gate 1`
   - 导致 `BCD` entry 数量与 trade 选择路径不同
   - attribution 在 `BPS` 上 MC 有 `+3,456`
   - HC 可能在不同 strategy 上分布

3. **trade path 累积**
   - `SPEC-074` alignment 已在 MC / HC 都实施
   - 但 HC 保留了 `SPEC-056c` 移除
   - 意味着 HC 的 selector tree 与 MC 末端仍有结构差异

MC 建议：

- HC 用 MC 的 `by exit_reason` 数据独立验证 HC 端：
  - `roll_21dte` vs `50pct_profit_early`
  - trade 数变化是否同方向
- 若同方向但量级低：
  - 说明 sample window + 结构差异可共同解释约 10× gap
- 若反方向：
  - 说明仍有其他未识别因素
  - 需要 MC 补 trade-level diff

---

## 三、Q039 / IC regular 6 笔 ledger

HC 请求 MC 提供 6 笔 `IC regular` 日期级 ledger，以对比 HC 的 13 笔，并分析 HC 多入的 7 笔是否合理。

MC 提供 6 笔完整 ledger：

- 窗口：`2023-06-01 → 2026-04-29`
- `profit_target = 0.50`

### 3.1 6 笔 ledger 详细

#### 第 1 笔

- `entry_date = 2023-08-15`
- `exit_date = 2023-09-13`
- `entry_spx = 4438`
- `entry_vix = 16.46`
- `exit_spx = 4467`
- `pnl = +399`
- `exit_reason = 50pct_profit`
- `dte_at_entry = 45`
- `dte_at_exit = 25`
- `entry_credit = -2962`

#### 第 2 笔

- `entry_date = 2023-09-20`
- `exit_date = 2023-10-24`
- `entry_spx = 4402`
- `entry_vix = 15.14`
- `exit_spx = 4248`
- `pnl = +63`
- `exit_reason = roll_21dte`
- `dte_at_entry = 45`
- `dte_at_exit = 21`
- `entry_credit = -2702`

#### 第 3 笔

- `entry_date = 2023-10-31`
- `exit_date = 2023-12-05`
- `entry_spx = 4194`
- `entry_vix = 18.14`
- `exit_spx = 4567`
- `pnl = -661` `[OCR-reconstructed from summary]`
- `exit_reason = roll_21dte`
- `dte_at_entry = 45`
- `dte_at_exit = 21`
- `entry_credit = -3087`

#### 第 4 笔

- `entry_date = 2024-05-03`
- `exit_date = 2024-06-07`
- `entry_spx = 5128`
- `entry_vix = 13.49`
- `exit_spx = 5347`
- `pnl = +45`
- `exit_reason = roll_21dte`
- `dte_at_entry = 45`
- `dte_at_exit = 21`
- `entry_credit = -2792`

#### 第 5 笔

- `entry_date = 2025-12-18`
- `exit_date = 2026-01-20`
- `entry_spx = 6775`
- `entry_vix = 16.87`
- `exit_spx = 6797`
- `pnl = +624` `[from summary]`
- `exit_reason = 50pct_profit`
- `dte_at_entry = 45`
- `dte_at_exit = 25`
- `entry_credit = -4630`

#### 第 6 笔

- `entry_date = 2026-01-21`
- `exit_date = 2026-02-19`
- `entry_spx = 6876` `[OCR likely]`
- `entry_vix = 16.9`
- `exit_spx = 6862`
- `pnl = +621`
- `exit_reason = 50pct_profit`
- `dte_at_entry = 45`
- `dte_at_exit = 25`
- `entry_credit = -4711`

### 3.2 总计

- 总 `PnL = +1,090.58 USD`
- `win rate = 5/6 = 83.3%`

### 3.3 与 HC 13 笔对比

- HC：13 笔
- MC：6 笔

#### MC-only 4 笔 `entry_date`

- `2023-08-15`
- `2023-09-20`
- `2023-10-31`
- `2026-01-21`

即第 1 / 2 / 3 / 6 笔。

#### 双方共有 2 笔 `entry_date`

- `2024-05-03`
- `2025-12-18`

即第 4 / 5 笔。

#### HC-only 11 笔 `entry_date`

- `2023-10-04`
- `2023-11-03`
- `2024-04-12`
- `2024-08-01`
- `2024-09-03`
- `2024-12-30`
- `2025-02-21`
- `2025-03-27`
- `2025-11-13`
- `2026-02-12`
- `2026-04-08`

HC 报告这 11 笔 IC 的大致合计约 `+$13,952`；具体每笔 HC 已有数据。

### 3.4 攻击面建议

HC 提议：

- 先看 MC 这 6 笔 ledger
- 然后做窄的 `IC regular trade-level divergence pack`

MC 同意此 attack 顺序。

#### 观察建议 1

HC 这 6 笔均为 `NORMAL_VOL` regime。

入场 VIX 范围约 `13.5 → 18.1`；  
入场 SPX 在 30d 高点附近，但不是新高。  
看似与 HC IC 入场条件类似。

#### 观察建议 2

MC 的 IC 入场必须满足 `select_strategy` 的 `NORMAL_VOL` 路径，且：

- `ivp_signal` 不是低位（即 `ivp > 30`）
- `ivp_252 < BPS_NNB_IVP_UPPER = 55`

即 `ivp_252` 需在大致 `30 → 55` 区间。

HC 的 13 笔 IC 中，HC 已报告 `9/13` 在 `ivp_252 >= 55`。

这意味着：

- HC 在 `NORMAL_VOL` 路径上，当 `ivp_252 >= 55` 时，fallback 直接到 IC
- 而 MC 在 `ivp_252 >= 55` 时，`NORMAL_VOL + BULLISH` 路径返回 `REDUCE_WAIT`

#### 观察建议 3

若双端 `BPS_NNB_IVP_UPPER` 都设为 `55`，但 HC 在 `NORMAL_VOL + BULLISH` 路径、`ivp_252 >= 55` 时 fallback 行为不同，则差异就在 fallback 上。

HC return §6.5 已提到：

- HC 的 `9/13` 在 `ivp_252 >= 55`

这印证 fallback 差异是主因。

MC 建议下一步：

HC 在自己 11 笔 HC-only IC 上按以下三个条件分桶：

1. `ivp_252 < 30`
   - 即 IV 太低
   - 此桶 MC 路径也会 `REDUCE_WAIT`
   - 理论上 HC / MC 都不应入
   - 若 HC 入了，是 HC 端 bug

2. `ivp_252 ∈ [30, 55)`
   - 此桶 MC 路径返回 IC
   - 理论上 HC / MC 都应入
   - 若 HC 此桶有 IC 入而 MC 没入，需要查为何 MC 没入

3. `ivp_252 >= 55`
   - 此桶 MC 返回 `REDUCE_WAIT`
   - HC 若仍 IC fallback，则这是主要差异桶

若分桶后：

- `9` 笔以上落在第三桶：则 fallback 差异主因成立
- `2` 笔以下落在其他桶：则多是边缘 effect
- 若分桶结果不符合预期：需要 MC 补 trade-level diff

---

## 四、SPEC-075 / SPEC-076 adoption 输入包

HC 请求内容：

- SPEC 全文
- MC commit / patch / file list
- `overlay_f_mode` posture
- old runtime 影响面
- 最小 regression / tieout 验证口径

MC 提供完整 adoption 输入包如下。

### 4.1 SPEC 全文

#### SPEC-075

- 全文位置：`task/SPEC-075.md`
- HC 需 PM OCR 扫描
- 该文件包含：
  - problem statement
  - 2 attempts review history
  - attempt 1：AC6 schema set FAIL
  - attempt 2：PASS

#### SPEC-076

- 全文位置：`task/SPEC-076.md`
- HC 需 PM OCR 扫描
- 该文件包含：
  - 2 attempts review history
  - attempt 1：3 blocking bug（B1 / B2 / B3）
  - attempt 2：全 PASS + N4 parity decision

### 4.2 SPEC-075 file list

#### 新文件 1

`strategy/overlay.py`

新增：

- `evaluate_overlay_f`
- `PortfolioState` dataclass
- `OverlayDecision` dataclass
- `build_portfolio_state`
- `build_live_portfolio_state`

#### 修改文件 1

`strategy/selector.py`

新增：

- `StrategyParams.overlay_f_mode`，默认 `disabled`
- `Recommendation.overlay_f_would_fire`
- `Recommendation.overlay_f_factor`
- `Recommendation.overlay_f_rationale`
- `_eval_overlay_f_live` helper
- `get_recommendation_live` 集成 overlay 评估
- `get_recommendation` 集成 overlay 评估

#### 修改文件 2

`backtest/engine.py`

新增：

- 在 `select_strategy` 之后进行 `overlay-F` evaluation
- `overlay_factor` 应用于 legs
- `record_entry` 接收 `overlay_factor` 参数
- 新增 reason 标记：`new_entry_overlay_f_x2`

#### 修改文件 3

`backtest/portfolio.py`

新增：

- `TradeEventRow.research_1spx_pnl`
- `TradeEventRow.live_scaled_est_pnl`
- `PortfolioTracker._overlay_factors` dict
- `record_entry` 接收 `overlay_factor` 参数
- `record_exit` 支持 dual-column PnL

#### 新增测试文件

`tests/test_overlay_f_gate.py`

- 覆盖 18 个 gate 测试

### 4.3 SPEC-076 file list

#### 修改文件 1

`strategy/overlay.py`

新增：

- `_append_overlay_f_log`

函数包含：

- same-day dedup
- alert text file 输出

#### 修改文件 2

`strategy/selector.py`

- `get_recommendation_live` 加 telemetry log call
- 但 `get_recommendation` 不写（与 backtest 隔离）

#### 修改文件 3

`web/html/spx_strat.html`

新增：

- trade history 的 `F×2` badge
- rec card 的 overlay-F panel

#### 新文件 1

`scripts/overlay_f_review_reports.py`

生成五节 Markdown 报告：

- fire summary
- entries on fire days
- counterfactual uplift estimate
- gate condition distribution
- disaster window check

#### 新文件 2

`doc/OVERLAY_F_REVIEW_PROTOCOL.md`

- quarterly review 决策协议
- shadow → active flip 的 4 条准则
- active → disabled rollback 的 2 条准则

#### 新增测试文件

`tests/test_overlay_f_monitoring.py`

- 覆盖 15 测试

### 4.4 `overlay_f_mode` posture 说明

参数名：

- `overlay_f_mode`

可取值：

- `disabled`
- `shadow`
- `active`

默认值：

- `disabled`

PARAM_MASTER 中位置：

- v4 起新增

#### posture = disabled

含义：

- `overlay-F` 评估完全跳过
- 不写 log
- 不影响 trade selection
- 不影响 trade sizing
- system 行为等同 `SPEC-075` 之前

#### posture = shadow

含义：

- 做 `overlay-F gate` 评估
- log 记录 `would-fire` 事件
- 但 `effective_factor` 仍为 `1.0`
- 即不实际加倍 `IC_HV` 入场 size
- 用于观察期，让 PM 看 fires 发生频率和 disaster-window 影响

#### posture = active

含义：

当 `IC_HV` 入场且：

- `idle_bp_pct >= 0.70`
- `vix < 30`
- `sg_count < 2`

则：

- `effective_factor = 2.0`
- 即 `IC_HV` 入场 size 翻倍

### 4.5 old runtime 影响面

#### bot 影响

`get_recommendation_live` 路径中，当 `overlay_f_mode != disabled` 且 `IC_HV` 推荐时：

- 评估 `overlay-F gate`
- `shadow` 模式写 `jsonl + alert`
- `active` 模式推荐数量翻倍

#### web 影响

`SPEC-076` 新增 dashboard 元素：

- trade log `F×2` badge
- rec card 的 overlay-F panel

MC 注：

- 不需要 web 重启
- HTML 自包含 JS 逻辑

#### dashboard 影响

- `F×2 badge` 仅当 `trade.reason == new_entry_overlay_f_x2` 时显示
- recommendation 的 overlay-F panel 仅当 recommendation 含 overlay 字段时显示
- 若 `SPEC-075` 落地但 mode = `disabled`，panel 不显示，badge 不出现

#### logs 影响

新文件：

- `data/overlay_f_shadow.jsonl`
  - `shadow + active` 模式追加
- `data/overlay_f_alert_latest.txt`
  - `shadow` 模式覆写
  - 供 PM 监控

### 4.6 最小 regression / tieout 验证口径

#### 口径 1：disabled byte parity

当 `overlay_f_mode = disabled` 时：

- 27y full backtest
- trade list / PnL / DD / `SPEC-064 AC10`
- 全部与 `SPEC-075` 之前 byte-identical
- 即 zero behavioral change

#### 口径 2：active 复现 SPEC-075 numbers

当 `overlay_f_mode = active` 时：

27y full backtest：

- `ann_roe = 13.159pp`
- `sharpe = 1.200`
- `fires = 38`
- `mdd` 改善

误差容忍：

- `ann_roe ± 0.05pp`
- `sharpe ± 0.02`
- `fires ± 2`
- `mdd ± 500 USD`

#### 口径 3：shadow 模式只 log 不变

当 `overlay_f_mode = shadow` 时：

- trade list 与 PnL 应与 `disabled` 一样
- 但 `data/overlay_f_shadow.jsonl` 应有记录，约 38 个 fires
- 若 fires 数与 active mode 一致，则 shadow 工作正常

#### 口径 4：SPEC-076 telemetry 测试

要求 shadow log JSONL 字段完整，至少包括：

- `date`
- `strategy`
- `vix`
- `idle_bp_pct`
- `sg_count`
- `rationale`
- `mode`
- `effective_factor`

#### 口径 5：dashboard parity

- `F×2 badge` 仅在 `trade.reason == new_entry_overlay_f_x2` 时显示
- overlay-F panel 仅在 recommendation 含 overlay 字段时显示

### 4.7 Staged rollout 建议

HC 已正确指出应按：

`disabled -> shadow -> active`

进行 staged rollout。

具体建议：

1. **阶段 1**
   - `SPEC-075` 落地于 `disabled` mode
   - verify 口径 1：byte parity
   - 确认 zero regression

2. **阶段 2**
   - `SPEC-076 telemetry` 落地
   - verify 口径 4：telemetry
   - 确认 log + alert 文件结构 OK

3. **阶段 3**
   - PM 手动 flip 到 `shadow`
   - 观察期建议 1–2 个月
   - verify 口径 3：shadow log 积累
   - fires 数与 MC 的 38 接近，则 shadow 健康

4. **阶段 4**
   - PM 评估 shadow 数据
   - 按 `doc/OVERLAY_F_REVIEW_PROTOCOL.md` 的 4 条准则
   - 若全部满足，再 flip 到 `active`

5. **阶段 5**
   - active 后 1 周内
   - verify 口径 2：active 复现 `ann_roe / sharpe / fires`
   - 若数字异常，flip back 到 `shadow` 调查

### 4.8 顺序建议

强烈建议 `SPEC-075 + SPEC-076` 作为同一批 adoption work。

理由：

- `SPEC-076 monitoring` 依赖 `SPEC-075 hook`
- 单独 ship `SPEC-076` 没有 fires 可 log
- `SPEC-075` 不带 `SPEC-076 monitoring`，PM 无法观察 shadow 状态
- 两者必须一起进入

---

## 五、MC 端待 HC 决策项

### 项 1：SPEC-056c / DIAG Gate 1 永久分歧

MC 在本 response 中 acknowledge：

- HC 移除作为 canonical
- MC 保留 `Gate 1`

此分歧不再讨论，不需要 HC 回复。

### 项 2：PARAM_MASTER 中 `overlay_f_mode`

HC 端在 `SPEC-075` 未实施时，PARAM_MASTER 中暂无 `overlay_f_mode`，此为预期。  
`SPEC-075` 实施后 HC 再加入，不需现在补。

### 项 3：Q040 候选 post-SPEC-080 attribution

HC 提到 `SPEC-077` 量级 gap 的三候选：

- a. compounding-baseline 口径
- b. debit-side 硬编（已闭合）
- c. `SPEC-054 + SPEC-056c` 永久分歧

HC 建议记为 `Q040` 候选。  
MC 同意：若 HC 在 `SPEC-080` 落地后继续看到 AC3 量级 gap，可开 `Q040` 正式研究。  
本期保持 candidate 状态。

---

## 六、完整数字对账

为防止 OCR 误读关键数字，本节列出本 response 全部关键数字，供 HC 逐项核对。

### SPEC-077 AC3 MC numbers

#### PT = 0.50

- `start_eq = 100,000`
- `n_years = 26.3217`
- `end_eq = 387,248.42`
- `total_pnl = 287,248.42`
- `ann_roe = 10.9130pp`
- `sharpe = 1.0177`
- `mdd_pct = -15.38`
- `mdd_dollar = 60,608`
- `trades = 447`

#### PT = 0.60

- `end_eq = 411,168.66`
- `total_pnl = 311,168.66`
- `ann_roe = 11.8218pp`
- `sharpe = 1.1077`
- `mdd_pct = -14.32`
- `mdd_dollar = 59,512`
- `trades = 433`

#### DELTA

- `Δ ann_roe = +0.9088pp`
- `Δ total_pnl = +23,920.24 USD`
- `Δ sharpe = +0.09`
- `Δ trades = -14`

### by exit_reason attribution

#### 50pct_profit

- PT 0.50：110 笔
- PT 0.60：69 笔
- `Δ_n = -41`

#### 50pct_profit_early

- PT 0.50：44 笔
- PT 0.60：15 笔
- `Δ_n = -29`

#### roll_21dte

- PT 0.50：263 笔
- PT 0.60：315 笔
- `Δ_n = +52`
- 最大数量增长

### Q039 / IC regular MC ledger 6 笔总计

- 总 PnL：`+1,090.58 USD`
- `win rate = 5/6 = 83.3%`

具体 6 笔 `entry_date`：

- `2023-08-15`
- `2023-09-20`
- `2023-10-31`
- `2024-05-03`
- `2025-12-18`
- `2026-01-21`

其中 4 笔 MC-only：

- `2023-08-15` `+399`
- `2023-09-20` `+63`
- `2023-10-31` `-661`
- `2026-01-21` `+621`

其中 2 笔双方共有：

- `2024-05-03` `+45`
- `2025-12-18` `+624`

---

## 七、SPEC / Q 编号校验总表

### SPEC 编号

- `SPEC-074`
- `SPEC-075`
- `SPEC-076`
- `SPEC-077`
- `SPEC-078`
- `SPEC-079`
- `SPEC-080`
- `SPEC-056c`（HC 移除 `DIAG Gate 1`，此为永久分歧，MC acknowledge）

### Q 编号

- `Q020`：已通过 `SPEC-074` closed
- `Q021`：closed in HC `2026-05-02`
- `Q036`：方向已对齐
- `Q038`：HC live shadow flip
- `Q039`：research only
- `Q040`：candidate post-SPEC-080 attribution

---

## 八、HC 收到本 response 后建议动作

1. **确认 §1 状态 ingest 无误**
   - 若 MC 列表与 HC 实际不符，回包提出更正

2. **按 §2 attribution data**
   - HC 端独立验证：
     - `roll_21dte` vs `50pct_profit_early`
     - trade 数变化方向
   - 若同方向，gap 量级解释收敛
   - 若反方向，需要 trade-level diff

3. **按 §3 IC regular ledger**
   - HC 端按三个分桶分析 11 笔 HC-only IC：
     - `ivp252 < 30`
     - `30 <= ivp252 < 55`
     - `ivp252 >= 55`

4. **按 §4 SPEC-075 / SPEC-076 adoption**
   - HC 准备实施计划
   - 建议 staged rollout：
     - `disabled -> shadow -> active`
   - 不需立即实施，取决于 HC PM cycle

5. **若有 HC 不一致项**
   - 按 `D-编号` 格式提出
   - MC 在下一周期回应

文档结束。  
格式遵循 OCR-friendly。
