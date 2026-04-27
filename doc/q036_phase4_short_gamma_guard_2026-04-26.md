# Q036 Phase 4 — Short-Gamma-Count Guard Refinement

- 日期：2026-04-26
- Author: Quant Researcher
- 上游：`doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- Prototype: `backtest/prototype/q036_phase4_short_gamma_guard.py`

---

## TL;DR

Phase 3 的核心结论是：

- `Overlay-B` 回报最好，但 residual stacking 还在
- `Overlay-D`（`B + no IC_HV open`）把 stacking 压到 `0%`，但回报被压薄过头

于是本轮只问一个更窄的问题：

> 是否可以用 account-level 的 short-gamma guard，替代过于保守的 “no IC_HV open at all”？

答案是：**可以，而且效果明显优于 `Overlay-D`。**

最有价值的新候选是：

- **`Overlay-F_sglt2`** = `2x` iff `idle BP >= 70%`, `VIX < 30`, and **pre-existing short-gamma count < 2**

它的结果是：

- annualized ROE uplift `+0.074pp`
- 明显高于 `Overlay-D` 的 `+0.046pp`
- 接近 `Overlay-B` 的 `+0.088pp`
- 同时把 realized `SG>=2` 压到 **`0%`**
- disaster-window net 与 `Overlay-B` 完全一致
- peak BP 也从 `38%` 压回 `34%`

这意味着：

> Phase 4 首次找到了一个比 `Overlay-D` 更不保守、但仍然把 stacking 治理到 0 的折中点。

---

## 1. 研究问题

Phase 3 的 hybrid (`Overlay-D`) 使用的是：

- `no IC_HV open at all`

这个 guardrail 的问题不是错，而是太粗：

- 它把“已有一个可接受的 short-gamma posture”与“已经进入危险 stacking posture”混成同一类
- 结果是 governance 很干净，但总量 uplift 太小

所以本轮改成直接按 account-level 风险语义来卡：

- 允许已有一些 short-gamma
- 但当 **pre-existing short-gamma count >= 2** 时，不再允许 overlay 加倍

---

## 2. 变体定义

基线与对照：

- `V_baseline` = `V_A / SPEC-066`
- `Overlay-B_ctrl` = `2x` iff `idle BP >= 70%` and `VIX < 30`
- `Overlay-D_hybrid` = `2x` iff `idle BP >= 70%`, `VIX < 30`, and `no IC_HV open`

本轮新增：

- **`Overlay-F_sglt2`**
  - `2x` iff `idle BP >= 70%`
  - `VIX < 30`
  - `pre-existing short-gamma count < 2`

- `Overlay-G_sg0`
  - `2x` iff `idle BP >= 70%`
  - `VIX < 30`
  - `pre-existing short-gamma count == 0`

共同规则保持不变：

- boosted first-entry 一旦触发，同 cluster 第 2 笔不再开

---

## 3. Account-Level 结果

| Variant | Total PnL | Annualized ROE | Δ Ann ROE vs baseline |
|---|---:|---:|---:|
| `V_baseline` | `+$403,850` | `8.67%` | — |
| `Overlay-B_ctrl` | `+$414,556` | `8.76%` | `+0.088pp` |
| `Overlay-D_hybrid` | `+$409,492` | `8.72%` | `+0.046pp` |
| **`Overlay-F_sglt2`** | **`+$412,855`** | **`8.75%`** | **`+0.074pp`** |
| `Overlay-G_sg0` | `+$405,876` | `8.69%` | `+0.016pp` |

### 解读

- `F` 明显优于 `D`
- `F` 只比 `B` 少 `+$1,701` 总 PnL
- 但它不再承受 `B` 的 residual stacking 问题
- `G` 过于严格，经济性明显太弱

---

## 4. Incremental Return vs Incremental Tail Cost

| Variant | MaxDD | Δ CVaR 5% | Disaster Net | Peak BP% |
|---|---:|---:|---:|---:|
| `V_baseline` | `-10,323` | — | `+301` | `30.0%` |
| `Overlay-B_ctrl` | `-9,749` | `-74` | `+301` | `38.0%` |
| `Overlay-D_hybrid` | `-9,749` | `-74` | `+301` | `34.0%` |
| **`Overlay-F_sglt2`** | **`-9,749`** | **`-74`** | **`+301`** | **`34.0%`** |
| `Overlay-G_sg0` | `-9,749` | `-74` | `+301` | `31.0%` |

### 关键结论

`F` 相对 `B`：

- disaster-window net 完全不变
- MaxDD / CVaR 没有额外恶化
- Peak BP 从 `38%` 降到 `34%`
- 回报只少一点点

这比 `D` 的 tradeoff 明显更好。

---

## 5. Governance / Stacking 结果

| Variant | +BPdays | Idle Utilization | Overlay Fires | SG mean | SG>=2 | Marginal $/BP-day |
|---|---:|---:|---:|---:|---:|---:|
| `Overlay-B_ctrl` | `+2,569` | `0.43%` | `25` | `0.84` | `20%` | `+4.1674` |
| `Overlay-D_hybrid` | `+1,428` | `0.24%` | `18` | `0.50` | `0%` | `+3.9510` |
| **`Overlay-F_sglt2`** | **`+2,100`** | **`0.35%`** | **`23`** | **`0.61`** | **`0%`** | **`+4.2881`** |
| `Overlay-G_sg0` | `+616` | `0.10%` | `9` | `0.00` | `0%` | `+3.2890` |

### 解释

`F` 是本轮最重要的结果：

- 保持 `SG>=2 = 0%`
- overlay fires `23`，几乎追上 `B` 的 `25`
- +BPdays `2,100`，明显高于 `D` 的 `1,428`
- marginal `$ / BP-day = +4.2881`

也就是说：

> `F` 没有像 `D` 那样把 overlay 缩得过窄，但已经把最关心的 stacking 问题压掉了。

---

## 6. Disaster Detail

所有候选在本轮 disaster detail 上都一致：

| Variant | 2008 GFC | 2020 COVID | 2025 Tariff | Total |
|---|---:|---:|---:|---:|
| `V_baseline` | `0` | `-1,656` | `+1,958` | `+301` |
| `Overlay-B_ctrl` | `0` | `-1,656` | `+1,958` | `+301` |
| `Overlay-D_hybrid` | `0` | `-1,656` | `+1,958` | `+301` |
| **`Overlay-F_sglt2`** | **`0`** | **`-1,656`** | **`+1,958`** | **`+301`** |
| `Overlay-G_sg0` | `0` | `-1,656` | `+1,958` | `+301` |

这说明：

- `F` 的新增放松并没有把 overlay 带回 disaster downgrade 问题
- 这一步是真正的 governance refinement，而不是重新打开 tail blow-up

---

## 7. Recent Slice (2018+)

| Variant | Total PnL | PnL/BP-day | Marginal $/BP-day | MaxDD |
|---|---:|---:|---:|---:|
| `V_baseline` | `+$164,958` | `5.9178` | — | `-9,405` |
| `Overlay-B_ctrl` | `+$171,103` | `5.9298` | `+6.2704` | `-9,392` |
| `Overlay-D_hybrid` | `+$168,465` | `5.9377` | `+7.0563` | `-9,392` |
| **`Overlay-F_sglt2`** | **`+$169,353`** | **`5.9470`** | **`+7.3007`** | **`-9,392`** |
| `Overlay-G_sg0` | `+$166,232` | `5.9590` | `+60.6667` | `-9,392` |

`G` 的 marginal 数字虽然看起来很高，但那只是因为触发极少、分母很小，不具备单独经济意义。

真正应看的是：

- `F` 在 recent slice 上也优于 `D`
- 且仍保持与 `B` 相当接近的总量结果

---

## 8. Quant Judgment

### 8.1 新发现

`Overlay-F_sglt2` 是 `Q036` 到目前为止最像“candidate frontier point”的结果：

- 比 `B` 更干净
- 比 `D` 更不保守
- 比 `G` 更有经济意义

这是第一次出现一个候选同时满足：

1. account-level annualized ROE uplift 仍有可见正值
2. realized `SG>=2` 被压到 `0%`
3. disaster-window net 不退化
4. peak BP 比最激进候选更低

### 8.2 还没到哪一步

即便如此，仍然要保持克制：

- uplift 依然小，只有 `+0.074pp annualized ROE`
- 这比此前明显更可 defend，但仍谈不上“强到可直接制度化”
- 所以它更像 **Phase 4 的 best-so-far research candidate**，而不是已经 ready-for-spec 的结论

---

## 9. Recommendation

- **Topic**: `Q036` Phase 4 — short-gamma-count guard
- **Findings**:
  - `short_gamma_count < 2` 明显优于 `no IC_HV open`
  - `Overlay-F_sglt2` 保住了大部分 `Overlay-B` 的回报
  - 同时把 realized stacking 风险压到 `0%`
  - disaster-window net 与 `Overlay-B` 相同
- **Risks / Counterarguments**:
  - uplift 仍然偏小，治理复杂度是否值得，仍需 PM 层面判断
  - 当前结论仍只覆盖这条 IC_HV aftermath overlay，不代表 broader capital-allocation layer 已经答完
- **Confidence**: medium-high
- **Next Tests**:
  - 如果继续，下一步不应再广泛扩枝
  - 应只围绕 `Overlay-F` 做 very narrow confirmation，例如：
    - recent-era robustness
    - yearly attribution
    - overlay fire distribution by regime / VIX bucket / pre-existing SG count
- **Recommendation**: **continue research**, but now with a **lead candidate**

当前状态可表述为：

> `Q036` 还不建议直接进入 DRAFT overlay spec discussion，但 `Overlay-F_sglt2` 已成为目前最值得继续验证的 lead candidate。
