# SPEC-074 简短版（供 HC 复现）

> 整理说明：
> - 本文件基于 `sync/mc_to_hc/MC_Spec-074_short_summary.md` 做第一轮扫描勘误
> - 目标：保留 MC 原意，修正常见 OCR / 排版错误，便于 HC Quant 读取
> - 不主动扩写成正式 SPEC；如某些文件名或函数名看起来是 **MC 侧预期路径** 而非 HC 当前已存在文件，保留其语义并加注

---

## 基本信息

- 原始文档：`task/SPEC-074.md`
- SPEC 编号：`SPEC-074`
- 校验：`SPEC-074`
- 状态：`DONE`
- PM 决策日期：`2026-04-27`
- MC 口径：关闭 `Q020`

---

## 一句话目标

让 MC 的 `_backtest_select` 不再使用简化决策矩阵，而是直接 delegate 到 live `select_strategy`，从而保证 backtest 选择与 live recommendation 逻辑完全一致。

---

## 为什么需要

MC 认为当前 `_backtest_select` 缺失了若干 live `select_strategy` 中已经存在的 gate，因此 backtest 与 live 的 selector fidelity 不足。

按 MC 文本整理，缺失项包括：

1. `BACKWARDATION` filter  
   - 影响：`BPS_HV` / `IC_HV aftermath`
   - 原因：MC 侧此前没有 term structure

2. `VIX_RISING` gate  
   - 影响：`BCS_HV bearish` 路径

3. `IVP63 >= 70` gate  
   - 影响：`BCS_HV`

4. `IC` 的 `IVP` range filter  
   - 范围：`20 < IVP < 50`

5. `DIAGONAL IV-high` gate  
   - 来源：`SPEC-051`

6. `DIAGONAL both-high` gate  
   - 来源：`SPEC-054`

7. `aftermath bypass`  
   - 含 backwardation retention

---

## 已 documented 的差距证据

### 证据 1：`SPEC-064 AC10` 低于目标

- target aftermath `IC_HV` count = `22 ± 3`
- MC full-history backtest 的实测值曾只有 `5`
- MC 认为差距过大，说明 selector fidelity 不足

### 证据 2：`Q036` reconstruction gap

MC 文本声称 `Overlay-F` 上存在 HC / MC 数字差异，例如：

- MC recent baseline：`194,856`
- HC：`164,958`
- gap 约：`$30,000`

MC 将此视为 backtest / selector fidelity 不一致的延伸证据。

---

## HC 实施所需的五个组件

### 组件 1：`VIX3M` 历史数据（blocking dependency）

HC 需要在 Bloomberg Windows 机器上运行：

- `data/fetch_bbg_vix3m.py`  （MC 侧预期文件名）

回传：

- `data/vix3m_history.csv`

覆盖范围：

- `2003-12-04` 到 `today`

说明：

- `VIX3M` inception = `2003-12-04`
- `2003-12-04` 之前可按 `None` 处理

### 组件 2：`IVP63` helper function

MC 侧预期新增：

- `compute_iv_percentile_63d`

用途：

- 计算当前 `VIX` 在 trailing `63` trading day 历史分布中的 percentile

MC 文本建议位置：

- `signals/vix_regime.py`

### 组件 3：full snapshot construction

MC 预期在 backtest engine 主循环中，每个 daily tick 构建完整 snapshot：

#### `VixSnapshot`

至少应包含：

- `vix`
- `vix3m`
- `term_structure`

#### `IVSnapshot`

至少应包含：

- `iv_percentile_252`
- `iv_percentile_63`
- `iv_signal`

#### `TrendSnapshot`

至少应包含：

- `spx`
- `ma200`
- `trend_signal`

### 组件 4：`select_strategy` delegation

MC 口径是：

- `_backtest_select(...)` 继续保留 backward compatibility
- 但其 body 改为 delegate 到：
  - `select_strategy(vix_snap, iv_snap, trend_snap, params)`

目标：

- `strategy`
- `underlying` 
- `rationale`
- `legs`

都应与 live `select_strategy` 一致。

### 组件 5：测试 parity 验证

MC 侧预期测试文件：

- `tests/test_backtest_select_parity.py`  （MC 侧预期文件名）

覆盖：

- 至少 `20` 个手挑日期
- 分布在：
  - `2008`
  - `2018`
  - `2020`
  - `2022`

验证目标：

- backtest selection 与 live selection `99%+` 一致

---

## 关键代码改动文件（按 MC 文本整理）

### `backtest/engine.py`

主要改动：

- snapshot construction
- delegation call
- 由旧 `_backtest_select(regime, iv, trend, ...)`
- 改为调用 `select_strategy(vix_snap, iv_snap, trend_snap, spx_history=None,params=None)`

### `strategy/selector.py`

- MC 口径：**不需要改**
- live `select_strategy` 仍是 canonical

### `backtest/metrics_portfolio.py`

- `SPEC-074` 本身不要求改
- 但 `SPEC-078` 会改 dashboard metrics source-of-truth

### `signals/vix_regime.py`

MC 侧预期新增或补充：

- `compute_iv_percentile_63d`
- `term_structure` classification helper

### 新数据 / 脚本文件（MC 侧预期）

- `data/vix3m_history.csv`
- `data/fetch_bbg_vix3m.py`
- `bin/run_fetch_bbg_vix3m.cmd`

说明：

- 这些是 MC handoff 中要求 HC 补齐或接收的产物 / 脚本名
- 不代表它们现在已经存在于 HC 仓库中

---

## 验收标准（简化版，供 HC 复现关注）

### 关注 1：Decision parity

测试通过标准：

- `99%+` 日期上，backtest 与 live 选择相同 strategy

### 关注 2：`SPEC-064 AC10` 对齐

aftermath `IC_HV` count 应回到：

- `22 ± 3`

MC 文本记录：

- `SPEC-074` 前：`5`
- `SPEC-074` 后：`+25 net`

并注明：

- PM 定义的 canonical 含义是：
  - `40 new - 15 lost = +25 net`

### 关注 3：Zero behavior regression

对其他已 closed specs：

- 方向性应继续一致

MC 提供的 PM amended bounds：

- `PnL` 变化：`<= 5pp`
- `Sharpe` 变化：`<= 0.10`
- `MaxDD` 变化：`<= 25pp`

说明：

- 这里的 `Sharpe / MaxDD` bounds 是 PM amended version
- 不是原始 SPEC 文本里的旧阈值

### 关注 4：`Q036 Phase 4` 重新跑

MC 预期：

- `Overlay-F` fire count 应接近 HC 的 `23`
- MC 当前是 `22`
- `SPEC-074` 后预期应进一步 converge

---

## 关键数字汇总

### `SPEC-064 AC10`

- target：`22 ± 3`
- pre `SPEC-074`：`5`
- post `SPEC-074`：`+25 net`

### AC5 amended bounds

- `PnL` 变化阈值：`5pp`
- `Sharpe` 变化阈值：`0.10`
- `MaxDD` 变化阈值：`25pp`

### `VIX3M` 数据范围

- `2003-12-04` 到 `today`
- inception = `2003-12-04`

### parity test 覆盖

- 至少 `20` 个手挑日期
- 分布在：
  - `2008`
  - `2018`
  - `2020`
  - `2022`

### downstream impact

MC 文本声称：

- post `SPEC-074` measurement 出现 `Q036 ranking flip`
- `Overlay-F` dominate `IC non-HV`

即：

- `IC_HV Overlay-F` 的表现优于 `IC non-HV`

---

## 范围外

以下内容不在 `SPEC-074` 范围内：

1. `position state evolution`
   - MC 文本声称已通过 `Q022` 对齐

2. `leg construction conventions`
   - 已通过 `SPEC-070 v2` 对齐

3. `BP + qty` 处理
   - 属于 `Q029 + Q033 dual-column reporting`

4. `PARAM_MASTER` 参数值
   - `SPEC-074` 不改任何参数

---

## 实施顺序建议（按 MC 文本整理）

1. PM 在 BBG Windows 跑 `fetch_bbg_vix3m`，拿到数据后回 MC / HC 同步 CSV
2. HC 实施 `IVP63 helper` + `term_structure helper`，并通过单元测试
3. HC 修改 backtest engine：
   - 增加 snapshot construction
   - 增加 delegation
4. HC 跑 parity test：
   - 覆盖 `20` 个日期
   - 确认 `99%+` 一致
5. HC 跑 full-history backtest：
   - 检查 `SPEC-064 AC10 == 22 ± 3`
6. HC 跑 closed specs regression：
   - 确认 directional 一致，且 amended bounds 内通过
7. HC 重跑 `Q036 Phase 4`：
   - 看 `Overlay-F` fire count 是否接近 `23`
8. HC 重跑 `3y backtest tieout`：
   - 回传 CSV 给 MC 对比

---

## 风险注意点

### 风险 1：`VIX3M` 早期数据稀疏

- `2003–2008` 段可能不完整
- graceful fallback 到 `None` 可接受

### 风险 2：`IVP63` 历史计算可能较慢

MC 建议：

- 预计算到 time-series cache
- 类似 `ivp252` 的 cached 模式

### 风险 3：closed specs 可能 regress

- 方向性变化是 expected
- 只要绝对值变化在 amended bounds 内即可
- 若超出，则 escalate to PM

### 风险 4：`Q036` 数字可能 shift

MC 文本强调：

- 这是 `SPEC-074` 的预期价值之一
- 不是异常本身
- 但 PM 需要重新看 ranking flip 是否影响决策

---

## 完整 `SPEC-074` 全文位置

完整详细版位于：

- `task/SPEC-074.md`

MC 文本说其中包含：

- problem statement 详细分析
- implementation plan
- 三轮 review 历史
- `v1 PASS-with-ADDENDUM`（后续不可用）
- `v2` 三个 substantive FAIL
- `v3 PASS - PM amendment`

review verdict 文件（按 MC 文本整理）：

- `task/RV-074-1.md` — `FAIL`
- `task/RV-074-2.md` — `FAIL`
- `task/RV-074-3.md` — `PASS`

数据 fetch handoff：

- `task/SPEC-074_data_fetch_handoff.md`

---

## 给 HC Quant 的一句话理解

如果只抓主轴，这份 `SPEC-074` short summary 的核心意思是：

> **先把 `_backtest_select` 收回到 live `select_strategy` fidelity，再看 `3y tieout`、`SPEC-064 AC10`、以及 `Q036` ranking 是否显著收敛。**

