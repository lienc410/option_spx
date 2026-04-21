# SPX Strategy System — Strategy Status 2026-04-20
**Date: 2026-04-20 | 承接 `strategy_status_2026-04-16.md`**

*本版新增内容：*
- *`SPEC-064` 已 DONE：HIGH_VOL aftermath `IC_HV` bypass 成为当前生产逻辑*
- *`SPEC-066` 已 DONE：`IC_HV` 最多 2 槽并发，`AFTERMATH_OFF_PEAK_PCT 0.05 -> 0.10`*
- *`Q018` 已通过 `SPEC-066` 收口，但 PM 又识别出新的语义问题 `Q020`*
- *`Q019` 新开：close-based vs open-based VIX 时间基准差异*

*以下章节无变更，请参阅 `strategy_status_2026-04-16.md`：*
- *§1–3：系统定位 / 历史回测基准 / 信号体系*
- *§4：SPX Credit 基础决策矩阵*
- *§5：StrategyParams 总体结构*
- *§6：DIAGONAL / BPS 既有 sizing 与 Q015 后的 BPS gate 口径*
- *`/ES` Short Put 生产组件（`SPEC-061`）*

---

## 生产路由变更（2026-04-19~20）

### 1. `SPEC-064` — HIGH_VOL aftermath `IC_HV` bypass 已生效

当前生产在以下条件下，允许 `IC_HV` 绕过原有 `HIGH_VOL` 内部两个 gate：

- regime = `HIGH_VOL`
- trend ∈ `{BEARISH, NEUTRAL}`
- IV signal = `HIGH`
- 满足 aftermath 条件：
  - 近 10 日 VIX 峰值 `>= 28`
  - 当前 VIX 相比该峰值至少回落 `5%`
  - 当前 VIX `< 40`（即不触发 `EXTREME_VOL` 硬门槛）

**绕过的 gate：**
- `VIX_RISING`
- `ivp63 >= 70`（仅在 `HIGH_VOL + BEARISH` 子路径）

**仍保留的保护：**
- `EXTREME_VOL (VIX >= 40)` 继续优先命中 `REDUCE_WAIT`
- `backwardation` 在 `HIGH_VOL + NEUTRAL` 继续保留
- `BPS_HV / BCS_HV` 不因 `SPEC-064` 获得同类 bypass

**当前理解**：
- `Q017` 已不再是开放研究项
- `HIGH_VOL aftermath IC_HV bypass` 已是生产事实
- 当前 `IC_HV` aftermath 语义的后续讨论，转入 `Q018 / Q020`

### 2. `SPEC-066` — `IC_HV` aftermath 允许最多 2 槽并发，且 aftermath 条件收紧到 10%

在 `SPEC-064` 基础上，当前生产进一步增加两点：

1. `IC_HV_MAX_CONCURRENT = 2`
   - 仅 `IRON_CONDOR_HV` 允许最多 `2` 笔并发
   - 非 `IC_HV` 策略仍保持原单槽位 `_already_open` 行为

2. `AFTERMATH_OFF_PEAK_PCT = 0.10`
   - 先前 `SPEC-064` 使用 `0.05`
   - `SPEC-066` 将其收紧为 `0.10`

**设计初衷（Q018）**：
- 解决 `2026-03` double-spike 场景里，第二次 aftermath 机会被单槽位挡住的问题
- 同时避免 `0.05` 口径在 `2008-09` 这类深危机中开出过多危险的 `IC_HV`

**最终 review 结论**：
- `SPEC-066` 已 `PASS with spec adjustment -> DONE`
- 实现本身成立；收口时修正的是 Spec 表述，不是代码

---

## 当前 HIGH_VOL 路由语义（截至 2026-04-20）

### HIGH_VOL + BEARISH

大致顺序：

1. 若 `VIX >= 40`：
   - `EXTREME_VOL -> REDUCE_WAIT`
2. 否则，若满足 aftermath 且 `IV = HIGH`：
   - 直通 `IC_HV`
3. 否则按原逻辑：
   - `VIX_RISING -> REDUCE_WAIT`
   - `ivp63 >= 70 -> REDUCE_WAIT`
   - `IV_HIGH -> IC_HV`
   - 其余 -> `BCS_HV`

### HIGH_VOL + NEUTRAL

大致顺序：

1. 若 `VIX >= 40`：
   - `EXTREME_VOL -> REDUCE_WAIT`
2. 否则，若满足 aftermath 且 `IV = HIGH` 且非 backwardation：
   - 直通 `IC_HV`
3. 否则按原逻辑：
   - `VIX_RISING -> REDUCE_WAIT`
   - `backwardation -> REDUCE_WAIT`
   - 默认 `IC_HV`

### HIGH_VOL + BULLISH

**无新变化**：
- `SPEC-060 Change 3` 仍然保持 `REDUCE_WAIT`
- `Q016` 已证明在 recovery context 下，`NORMAL + HIGH + BULLISH` 不是独立可修方向
- 当前不应把 `SPEC-064/066` 外推到 `HIGH_VOL + BULLISH`

---

## `Q018` 与 `Q020` 的最新关系

### `Q018` 已解决的是什么

`Q018` 解决的是：
- 在 HIGH_VOL aftermath 场景里，单槽位约束是否会错过后续机会
- 研究结果最终收成 `SPEC-066`

也就是说，`Q018` 解决的是 **slot-capacity** 问题。

### `Q020` 新提出的是什么

PM 进一步指出：
- 在 `2026-03` double-spike 真实案例里，
  - `2026-03-09` — `IC_HV`
  - `2026-03-10` — `IC_HV`
- 这两笔是 **back-to-back 连续开仓**
- 但真正想要捕捉的，可能不是“第一峰后连续再抓一次”，而是“第二个峰值形成后，再抓第二峰回落”

因此 `Q020` 问的是：

> `SPEC-066` 的增量 alpha 中，有多少来自语义正确的“distinct second peak”，又有多少来自语义可能错误的 back-to-back re-entry？

**当前结论**：
- `Q020` 目前是新的 `research only`
- 它不会自动推翻 `SPEC-066`
- 但它确实限制了我们对 `SPEC-066` alpha 含义的解释

---

## `Q019` — VIX 时间基准差异（新开）

当前大量研究与 backtest 使用按交易日**收盘**构建的 VIX 序列；
但 live recommendation 实际发生在**开盘 / 早盘**。

在 HIGH_VOL / aftermath 语义里，这可能影响：

- `HIGH_VOL` vs `NORMAL` regime 切换
- `VIX_RISING` 判断
- `ivp63` / 高 IV gate 的触发边界
- aftermath 条件在 live 中的提前或延后

**当前状态**：
- `Q019` 已登记
- 尚无研究输出
- 不能用它来回头解释任何既有结论成败

---

## 当前开放问题（截至 2026-04-20）

| 编号 | 状态 | 内容 |
|------|------|------|
| Q013 | open | `/ES` runtime stop 监控与 bot alert follow-up |
| Q012 | open | `/ES` shared-BP 管理与 MVP 边界 |
| Q019 | research | VIX close-based vs open-based 时间基准差异 |
| Q020 | research | `SPEC-066` 的多槽位 alpha 是否混入了语义错误的 back-to-back re-entry |
| Q011 | open | regime decay DIAGONAL 样本仍小 |
| Q002 | open | Shock active mode Phase B |
| Q003 | open | L3 Hedge v2 |
| Q004 | open | `vix_accel_1d` fast-path |
| Q005 | open | 多仓 trim 精细化 |
| Q001 | blocked | SPEC-020 ablation（等待 AMP） |

### 已收口但当前必须知道的事项

| 编号 / Spec | 当前事实 |
|-------------|----------|
| Q015 | 已通过 Fast Path 落地，BPS `IVP` upper gate 从 `50 -> 55` |
| Q017 | 已通过 `SPEC-064` 落地 |
| Q018 | 已通过 `SPEC-066` 落地 |
| SPEC-064 | DONE |
| SPEC-066 | DONE |
| SPEC-061 | DONE，但 `/ES` follow-up `Q013` 仍 open |

---

## 研究候选（当前）

### H1 — `Q020`
重新定义 HIGH_VOL aftermath 的“第二次机会”语义：
- 是允许同峰 back-to-back 重复抓
- 还是必须绑定 distinct second peak / re-arm 逻辑

### H2 — `Q019`
评估 VIX 时间基准（close vs open/early-session）对 HIGH_VOL / aftermath 格子的影响

### H3 — `/ES` follow-up
在 `Q013` 上收缩出最小运行时安全 Spec

