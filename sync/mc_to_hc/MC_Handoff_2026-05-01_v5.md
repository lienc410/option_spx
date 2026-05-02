# MC Handoff 2026-05-01 v4

> 修订说明：
> - 本文件基于 `sync/mc_to_hc/MC_Handoff_2026-05-01.md` 整理
> - 在 `v2` 基础上吸收 `sync/mc_to_hc/MC_Handoff_2026-05-01_v3.md` 的 MC 反馈
> - 处理范围：OCR 错字、参数名/Spec 编号修复、排版清理、与 HC 当前 canonical 术语/状态的对照注记
> - 不主动改写 MC 原始研究结论；如与 HC 当前状态冲突，保留 MC 原意并加注 `HC 当前状态注记`

## 基本信息

- 上次同步日期：2026-04-26
- 本次 MC 工作期：2026-04-27 到 2026-05-01
- 本期周期：5 天
- 周期特征：集中度高
- MC 摘要自述：完成 `7` 个 `SPEC` 和 `3` 个研究弧

## 本期摘要

1. `SPEC-074` 完成
   - MC 的 `backtest_select` 现在 delegate 到 `live select_strategy`
   - 目标是实现 full-fidelity 对齐
   - MC 认为这可关闭 `Q020`

2. `Q036` capital-allocation 主线推进
   - MC canonical 写法：`PM 选择 Option 2 = ESCALATE`
   - MC 自述：`Overlay-F_sglt2` 的 productization 前提栈已推进到 `SPEC-075`（核心逻辑）+ `SPEC-076`（监控/复盘）

3. `Q037` broad rule audit
   - 新发现：`profit_target 0.50 -> 0.60`
   - MC 认为其对 ROE 的改善强于 `Overlay-F`
   - 对应 `SPEC-077`

4. `Q038` 研究弧完整推进
   - `BCD comfortable top` 模式经两轮 ChatGPT review 后落地
   - 对应 `SPEC-079`（入场过滤）+ `SPEC-080`（止损收紧）
   - 组合口径被称为 `V5b`

5. Dashboard metrics 统一
   - `SPEC-078`
   - 将 portfolio metrics 设为唯一权威来源，解决 `5y` 回测中 PM 看到的数字不一致问题

6. 三个治理性收获
   - `trade-list` 反事实会系统性低估 filter 价值
   - ChatGPT review 在 `SPEC-079` 上阻挡了次优配置
   - `Phase 2C` 发现 `V5` 的 stop 参数并非最优

## 当前状态快照

### 当前推荐生产配置（按 MC 文本整理）

- `profit_target = 0.60`
- `overlay_f_mode = disabled`
- `shock_mode = shadow`
- `bcd_comfort_filter_mode = disabled`
- `bcd_stop_tightening_mode = disabled`
- `use_atr_trend = True`
- `AFTERMATH_OFF_PEAK_PCT = 0.10`
- `IC_HV_MAX_CONCURRENT = 2`
- `long_call_delta = 0.04`
- `DTE = 45`（保持不变）

### 当前最高优先阻塞

- `/ES runtime safeguards`
  - 尚未有 Spec
  - 对应 `Q013`

### 当前 `PARAM_MASTER` 版本

- `v4`

> HC 当前状态注记：
> - HC 索引层里当前仍将 `Q036` 记为：**Quant recommendation = hold as research candidate, do not productize now；PM 最终产品化决策待定**
> - 因此，MC 文本中任何接近“`Q036` 已 resolved / escalate / productization stack closed-loop”的写法，都不能直接当作 HC canonical 当前事实

## 参数变更

### 1. `profit_target`

- 新值：`0.60`
- 来源 SPEC：`SPEC-077`
- 原因：`Q037 Phase 2A`
  - 全样本约 `+0.91` 到 `+1.03pp`
  - recent 约 `+0.23` 到 `+0.31pp`

### 2. `overlay_f_mode`

- 旧值：不存在
- 新值：`disabled`
- 来源 SPEC：`SPEC-075`
- 原因：
  - `Overlay-F_sglt2` capital-allocation overlay
  - 默认禁用，等待 PM 手动 shadow

### 3. `bcd_comfort_filter_mode`

- 旧值：不存在
- 新值：`disabled`
- 来源 SPEC：`SPEC-079`
- 原因：
  - 新增 `BCD comfortable top` 入场过滤
  - 默认禁用，等待 PM 手动 shadow

### 4. `bcd_stop_tightening_mode`

- 旧值：不存在
- 新值：`disabled`
- 来源 SPEC：`SPEC-080`
- 原因：
  - 新增 `BCD` 止损收紧
  - `debit stop loss` 从 `0.50` 到 `0.35`
  - 仅作用于 `BCD`
  - 默认禁用，等待 PM 手动 shadow

### 5. `stop_mult`

- 旧值：隐式硬编码 `2.0`
- 新值：显式参数 `2.0`
- 来源 SPEC：`SPEC-077` 附带
- 原因：
  - governance fix
  - `StrategyParams` 字段已存在，但 engine 之前未读取；现已 wire through

## SPEC 决策

### `SPEC-074`

- 新状态：`DONE`
- PM 决策日期：2026-04-27
- review 过程：经过 `3` 次 review attempt 后 `PASS`
- MC 结论：
  - `Q020` 关闭
  - 在 aligned measurement 下，`Q036` 出现 ranking flip，`Overlay-F` dominate `IC non-HV`

### `SPEC-075`

- 新状态：`DONE`
- PM 决策日期：2026-04-28
- review 过程：
  - Round 1：`AC6 schema` 缺失
  - Round 2：修复后通过
- MC 记录：
  - annualized ROE（full sample）从 `11.789` 到 `13.159`，`+1.371pp`
  - Sharpe `1.106 -> 1.200`
  - `fires = 38`
- 非阻塞注记：
  - `live_scaled_est pnl` 不应用 `tier scale`
  - 仍属于 reporting-layer 职责

### `SPEC-076`

- 新状态：`DONE`
- PM 决策日期：2026-04-29
- review 过程：
  - v1：`3` 个 blocking bug
  - v2：全修复，含同日 dedup、`N4 parity`
- MC 记录功能：
  - shadow `JSONL` log
  - alert 文件
  - dashboard `F×2` badge
  - recommendation card overlay 面板
  - quarterly review protocol 文档

### `SPEC-077`

- 新状态：`DONE`
- PM 决策日期：2026-04-28
- review：`1x Review PASS`
- 内容：
  - `profit_target` 常数升级
  - `StrategyParams` wiring
  - `stop_mult` companion fix

### `SPEC-078`

- 新状态：`DONE`
- PM 决策日期：2026-04-29
- review：`1x Review PASS`
- 内容：
  - dashboard metrics 唯一权威化
  - API 作为单一 source of truth
  - dashboard JS 退化为纯展示
  - `P12 Fast Path` 后续修复

### `SPEC-079`

- 新状态：`DONE`
- PM 决策日期：2026-04-29
- review 过程：
  - v1：两个 blocking bug
    - `numpy bool` JSON 序列化静默失败
    - `log call` 架构错位
  - v2：全修复
- 内容：
  - `BCD comfortable top` 入场过滤
  - 当 `risk_state_score = 3` 时触发 `skip`
  - 单 toggle / split toggle
  - 详见 `V5b`

### `SPEC-080`

- 新状态：`DONE`
- PM 决策日期：2026-04-29
- review：`1x PASS + non-blocking architecture flag`
- 内容：
  - `BCD debit stop loss` 从 `0.50` 到 `0.35`
  - toggle：`bcd_stop_tightening_mode`
  - 与 `SPEC-079` 独立可切换
  - log 文件区分 `engine` 和 `live source`

## 研究发现

### `F-26-04-29-1`

- 内容：`BCD comfortable top` 入场模式
- MC 摘要：
  - 跨 `13` 年 top + worst-losses `10/10` 命中
  - fingerprint 约为：
    - `VIX 13–15`
    - `SPX dist_30d_high <= -1%`
    - `MA50 > 1.5pp`
- 依据：`Q038` walk-forward 验证
- 解读：从 `1999–2018` 学到的 filter，在 `2024–2025` 的 `3` 个 OOS 大亏上“完美捕获”
- 相关 SPEC：`SPEC-079`

### `F-26-04-29-2`

- 内容：`trade-list` 反事实系统性低估
- MC 摘要：
  - 原始 `rejected-set EV` 接近零
  - full engine 的 `rejected set` 实际为正贡献
  - `21` 笔 `BCD reject` 合计 `+$13,695`
  - 原因包括：
    - fallback strategy slot
    - BP cascade
    - concurrency caps
  - 这些都未在 `trade-list` 计算里建模
- review 提及：`ChatGPT 2nd Quant Review §5`
- 相关 SPEC：`SPEC-079` + `SPEC-080`

### `F-26-04-29-3`

- 内容：`V5` 的 stop 参数 `0.30` 不是最优，真正 plateau 中心是 `0.35`
- MC 摘要：
  - annualized ROE `13.59 vs 13.23`
  - Sharpe `1.407 vs 1.355`
- 依据：
  - `Q038 Phase 2C`
  - `11 configs` sensitivity sweep
  - `ChatGPT 3rd Quant Review §4` 要求的 sweep
- 相关 SPEC：`SPEC-080`

### `F-26-04-29-4`

- 内容：`profit_target = 0.60` 是优势点
- MC 摘要：
  - `0.50 -> 0.60` 是 inflection
  - `0.55 -> 0.60` 增量约 `+0.53pp`
  - `0.60 -> 0.65` 再增量约 `+0.26pp`
  - `0.65` 之后递减明显
  - `MaxDD` 和 stop-loss count 基本不变
  - `0.65` 候选 deferred
- 依据：`Q037 BC1` 扫描
- 相关 SPEC：`SPEC-077`

## 策略逻辑变更

### 1. `backtest_select`

- 旧逻辑：
  - `_backtest_select` 用简化矩阵 fallback
  - 不读 `VIX3M term structure`
  - 不读 `IVP63 / IVR-IVP divergence checks`
- 新逻辑：
  - `_backtest_select` delegate 到 `live select_strategy`
  - 完整保真度对齐
  - 包含 `VIX3M`、`IVP63`、divergence
- 相关 SPEC：`SPEC-074`

### 2. `BCD entry filter`

- 旧逻辑：
  - `LOW_VOL + BULLISH` 直接返回 `BULL_CALL_DIAGONAL`
- 新逻辑：
  - 加可选 `comfortable top` 过滤
  - 当 `bcd_comfort_filter_mode = active`
  - 且 `risk_score = 3`
  - 返回 `REDUCE_WAIT` 而非 `BCD`
- 相关 SPEC：`SPEC-079`

### 3. `BCD stop tightening`

- 旧逻辑：
  - 所有 debit 策略统一 `DEBIT_STOP_LOSS_RATIO = -0.50`
- 新逻辑：
  - 仅 `BCD`
  - 当 `bcd_stop_tightening_mode = active`
  - `debit stop loss = -0.35`
  - 其他 debit 策略不变
- 相关 SPEC：`SPEC-080`

### 4. `Overlay-F capital allocation`

- 新逻辑：
  - `IC_HV` 入场时，若三条件成立：
    - `idle BP >= 70%`
    - `VIX < 30`
    - `pre-existing SG count < 2`
  - 则 position size 翻倍
  - 默认禁用，等待 PM 手动 shadow
- 相关 SPEC：`SPEC-075`

### 5. `dashboard metrics rendering`

- 旧逻辑：
  - dashboard JS 本地重算
  - annual ROE 用 `total_pnl / 100000 / years`
- 新逻辑：
  - API 返回 `portfolio_metrics`
  - dashboard JS 只读：
    - `pm_ann_roe`
    - `pm_daily_sharpe`
    - `pm_max_dd_dollar`
- 相关 SPEC：`SPEC-078`

## 开放问题更新

### `Q020`

- MC 新状态：`resolved`
- MC 结论：`SPEC-074 DONE`，MC `backtest_select` 完全对齐 `live select_strategy`

> HC 当前状态注记：
> - HC 索引层中的 `Q020` 当前仍是 **MC-side housekeeping**
> - 核心意思接近，但 HC 尚未把它重写成“完全 resolved”

### `Q036`

- MC 新状态：`resolved`
- MC 结论：
  - PM 选 `Option 2 = ESCALATE`
  - `SPEC-075` 核心逻辑 + `SPEC-076` 监控复盘均 `DONE`
  - productization 前提 `1–5` 全闭环
  - `overlay_f_mode = disabled`，等 PM 手动 shadow

> HC 当前状态注记：
> - 这部分与 HC 当前 canonical 状态**不一致**
> - HC 当前索引层是：
>   - `Q036 = open`
>   - `PASS WITH CAVEAT`
>   - `PM 选 governance Option B`
>   - **Quant 最新 recommendation = hold as research candidate, do not productize now**
>   - **PM 最终产品化决策待定**
> - 因此这里更适合理解为：**MC 侧推进到 governance/productization planning 完成，但 HC 当前并未把 Q036 视为 resolved**

### `Q037`

- MC 新状态：`部分 resolved`
- MC 结论：
  - `Phase 2A` `profit_target` 主发现已进 `SPEC-077` 且 `DONE`
  - `Phase 2B NORMAL BPS audit` deferred
  - `0.65` 候选 deferred
  - 等 `0.60` live 效果观察

### `Q038`

- MC 新状态：`部分 resolved`
- MC 结论：
  - `BCD comfortable top` 进入 `SPEC-079`
  - 止损收紧进入 `SPEC-080`
  - 但研究 umbrella 仍保持 open
  - 未来候选包括：
    - state-conditional stop
    - `score >= 2` 的更激进 filter

### `Q009`

- MC 新状态：仍 `blocked`
- 内容：Schwab Developer Portal
  - HC 已通过
  - MC 仍等待
  - 不影响 backtest，仅影响 live execution

## 新增问题

### `Q039`（candidate research）

- 扫描原文缺失正式编号，按上下文整理为 `Q039`
- 内容：
  - `ivp252 >= 55` 触发 `REDUCE_WAIT`
  - `3y` backtest 发现 HC 的 `11` 笔 `IC`，MC 因 gate 全部跳过
  - 合计约 `+$13,952`
  - 问题：是否过度 restrictive，有待研究
- 依据：`HC vs MC 3y tieout 2026-05-01`

## Master Doc 影响清单（按 MC 文本整理）

- `PARAM_MASTER`：需要更新
  - 新增三个 toggle 参数
  - `profit_target 0.50 -> 0.60`
  - `stop_mult` 显式化
- `open_questions`：需要更新
  - `Q020`
  - `Q036`
  - `Q037`
  - `Q038`
  - `Q039` candidate
- `strategy status`：需要更新
  - `SPEC-074`
  - `Overlay-F`
  - `BCD filter`
  - `BCD stop`
- `research_notes`：需要更新
  - `Q038` 研究弧
  - `trade-list` 方法论修正
- `SPEC` 状态：需要更新
  - `SPEC-074` 到 `SPEC-080` 均为 `DONE`

## 给 HC 的指令（按 MC 文本整理）

### 指令 1：同步 SPEC 实施

HC 需要将以下 `7` 个 SPEC 的代码改动全部同步到 HC 端 codebase：

- `SPEC-074`
- `SPEC-075`
- `SPEC-076`
- `SPEC-077`
- `SPEC-078`
- `SPEC-079`
- `SPEC-080`

MC 说明：PM 会单独传输每个 SPEC 的源代码 diff。

### 指令 2：重跑 `3y backtest tieout`

HC 在同步代码后，重跑 `2023–2026` 的 `3y backtest`，导出与之前相同格式的 CSV，回传供 MC 比对。

MC 目标：
- `>= 99% trade match`
- 总 PnL 差 `< $1,000`

### 指令 3：backfill `VIX3M`

- `SPEC-074` 涉及 `VIX3M term structure`
- HC 需在 Bloomberg Windows 机器上跑：
  - `data/fetch_bbg_vix3m.py`
- 回传 `vix3m_history.csv`

### 指令 4：dashboard 同步

- `SPEC-078 / P12 Fast Path`
- 需同步 dashboard 文件，否则 dashboard 仍显示 trade-based metrics

### 指令 5：产品化部署姿态

三个新增 toggle 参数默认值必须保持 `disabled`，而 `shock_mode` 维持原有 `shadow` 姿态：

- `overlay_f_mode`
- `bcd_comfort_filter_mode`
- `bcd_stop_tightening_mode`
- `shock_mode = shadow`

HC 不允许自行翻到 `active`；PM 会在下次 handoff 中单独决定 shadow flip 时机。

### 指令 6：backtest tieout 特别关注

MC 文本记录：
- HC 独有 entry 日期：`29`
- MC 独有 entry 日期：`24`
- 目标是重跑后显著收敛到 `0` 或个位数
- 若仍有大量 divergence，说明 `SPEC-074` 同步不完全，需要进一步 reconcile

## 不要推断的项目

1. 不要擅自调整 `SPEC-079 / SPEC-080` 的 thresholds / post-hoc 参数：
   - `VIX 13 / 15`
   - `dist_30d_high <= -1%`
   - `MA50 > 1.5pp`
   - `debit stop = -0.35`

2. 不要把 `V5b` 的 combined 部署自动翻到 `active`
  - 两个 toggle 独立可控
  - PM 会先 flip 到 `shadow`
  - 观察期至少 `4–8` 周

3. `SPEC-079 v2` fix history
   - AMP 在 `SPEC-080` 同期 session 里顺手修了 `SPEC-079 Attempt 1` 的两个 bug
   - 但未 filed 正式 `v2 handoff`
   - HC 同步时应使用 `SPEC-079` 最新代码

4. `Q038` 的研究路径
   - PM 选的是 `Path C`
   - `SPEC-079` 先独立立项，`SPEC-080` 并行验证后再开
   - HC 不应把它们理解成两个无依赖的独立 SPEC

## 下周 MC 计划

1. 等待 HC return 包，确认同步完成度
   - `3y tieout #2`
   - 目标收敛到 trade 差 `0` 或个位数

2. 准备双 toggle shadow 部署
   - `bcd_comfort_filter_mode = shadow`
   - `bcd_stop_tightening_mode = shadow`
   - `overlay_f_mode = shadow`
   - 观察期 `1–2` 个月

3. `SPEC-076 review protocol`
   - `3` 周后，约 `2026-05-20`
   - 检查 shadow log 累积
   - 若 `fires >= 10` 或满 `90` 天，启动 quarterly review

4. `Q039` candidate research
   - 若 PM 拍板研究
   - 跑 `IVP gate sensitivity sweep`
   - 看 `ivp252` 阈值放宽到 `60 / 65` 是否能回收这期发现的 `11` 笔 `IC`

5. 备选研究方向
   - `profit_target = 0.65` follow-up
   - 等当前 `0.60` live 效果观察
   - 约 `2026-06` 到 `2026-08` 再考虑

## `3y backtest tieout` 数据

### HC 文件

- `data/backtest_trades_3y_2026-04-29.csv`

### HC 侧（MC 引用）

- `57` trades
- `exit_pnl = +$73,952`

### MC 当前默认配置

- `profit_target = 0.60`
- 所有 toggle `disabled`

### MC 公平对照模式

- 手动将 `profit_target` 调回 `0.50`
- 得到：
  - `52` trades
  - `exit_pnl = +$45,922`

### 差异分解

#### 第一类：入场日期分歧

- HC 独有：`29`
- MC 独有：`24`
- 双方共有：`28`

MC 解释：
- 当双方同日都入场时，`100%` 选择同一策略
- 分歧不在策略选择，而在“是否入场”的 gate 行为

#### 第二类：策略组合分化

- `BCD`
  - HC `21` 笔 / `+$37,714`
  - MC `15` 笔 / `+$32,813`
- `BPS`
  - HC `14` 笔 / `+$11,619`
  - MC `21` 笔 / `+$7,205`
- `IC regular`
  - HC `13` 笔 / `+$16,705`
  - MC `6` 笔 / `+$1,090`
  - 这是最大单一拖累
- `IC_HV`
  - HC `8` 笔
  - MC `6` 笔
- `BPS_HV`
  - HC `1` 笔
  - MC `4` 笔

#### 第三类：同入场但不同退出原因 / PnL

最显著案例：
- `2024-12-13` `BCD`
- HC / MC 同日入场
- `SPX ≈ 6051`
- HC 在 `2024-12-18` 退出，PnL `+$662`
- MC 在 `2025-01-14` 退出，PnL `-$9,577`
- 差异原因：`persistence filter` 触发时机不同
  - HC：单日 bearish 即翻
  - MC：等多日确认
  - 被解释为 `SPEC-020` 设计 trade-off

### MC 要 HC 核对项

1. HC 的 `_backtest_select` 是否仍是简化矩阵 fallback，而非 delegate 到 `live select_strategy`
2. HC 的 `trend signal` 逻辑 / `ATR persistence filter` 版本
3. HC 的 `Q015 IVP gate`
   - `ivp252 >= 55` 是否在 `NORMAL_VOL fallback` 路径上
   - 若 HC fallback 直接返回 `IC`，而 MC 通过 `live tree`，这可能就是 `11` 笔 `IC reject` 的根因

## SPEC 技术细节供 HC 参考

### 主要代码改动文件（按 MC 文本整理）

- `SPEC-074`
  - `backtest/engine.py`
  - `strategy/selector.py`
  - `backtest/metrics_portfolio.py`

- `SPEC-075`
  - `strategy/overlay.py` `NEW`
  - `strategy/selector.py`
  - `backtest/engine.py`
  - `backtest/portfolio.py`

- `SPEC-076`
  - `strategy/overlay.py`
  - `strategy/selector.py`
  - `scripts/overlay_f_review_report.py` `NEW`
  - `doc/OVERLAY_F_REVIEW_PROTOCOL.md` `NEW`

- `SPEC-077`
  - `strategy/selector.py`
  - `backtest/engine.py`

- `SPEC-078`
  - `web/api_server.py`
  - `web/html/spx_strat.html`
  - `backtest/engine.py`（docstring only）

- `SPEC-079`
  - `strategy/bcd_filter.py` `NEW`
  - `strategy/selector.py`
  - `backtest/engine.py`
  - `doc/BCD_FILTER_SHADOW_LOG.md` `NEW`

- `SPEC-080`
  - `strategy/bcd_stop.py` `NEW`
  - `backtest/engine.py`
  - `strategy/selector.py`（for live log call）

### 测试文件清单（按 MC 文本整理）

- `tests/test_overlay_f_gate.py`
- `tests/test_overlay_f_monitoring.py`
- `tests/test_bcd_filter.py`
- `tests/test_bcd_stop.py`
- `tests/test_dashboard_metrics_consistency.py`

## 完整 SPEC / 文档传输需求

### SPEC 文档 7 份

- `task/SPEC-074.md`
- `task/SPEC-075.md`
- `task/SPEC-076.md`
- `task/SPEC-077.md`
- `task/SPEC-078.md`
- `task/SPEC-079.md`
- `task/SPEC-080.md`

### 研究文档 3 份

- `task/Q038_2024_2025_drawdown_analysis.md`
- `task/Q038_phase2b_findings.md`
- `task/Q038_phase2c_findings.md`

### ChatGPT review 3 份

- `task/Q038_2nd_quant_review.md`
- `task/Q038_3rd_quant_review.md`
- `task/SPEC-070_v2_Q027_Review.md`（仅参考）

### 新增数据文件

- `data/bcd_filter_shadow.jsonl`
- `data/bcd_filter_alert_latest.txt`
- `data/bcd_stop_shadow_engine.jsonl`
- `data/bcd_stop_shadow_live.jsonl`
- `data/overlay_f_shadow.jsonl`
- `data/overlay_f_alert_latest.txt`

## HC 收到后回包要求

HC 在执行完同步后，请按标准 HC return 包格式返回，重点回报：

1. `SPEC-074` 到 `SPEC-080` 全部七个 SPEC 的实施完成度，逐个 `PASS / FAIL`
2. `3y backtest tieout #2` 结果
   - HC trade count vs MC `52`
   - PnL 差异
   - 若差异大于 `$5,000`，提供具体 divergence trade 列表
3. 所有四个 toggle 参数保持 `disabled` 状态确认
4. `Q039` 候选上，HC 对 `IVP gate sensitivity research` 是否有补充看法
