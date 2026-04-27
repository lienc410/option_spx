# Q036 Phase 3 — Guardrail Refinement (`Overlay-B` / `Overlay-C` follow-up)

- 日期：2026-04-26
- Author: Quant Researcher
- 上游：`doc/q036_framing_and_feasibility_2026-04-26.md`
- 上游：`backtest/prototype/q036_phase2_overlay_pilots.py`
- Prototype: `backtest/prototype/q036_phase3_guardrail_refinement.py`

---

## TL;DR

Phase 2 之后最自然的问题是：能否把 `Overlay-B` 的 disaster guardrail 与 `Overlay-C` 的 no-overlap guardrail 合并，在不牺牲太多回报的情况下清掉 stacking 风险。

本轮结果是：

1. **可以清掉 stacking，但会明显压缩 uplift。**
2. `Overlay-D hybrid`（`B + C`）把 realized `SG>=2` 从 `Overlay-B` 的 `20%` 压到 `0%`，同时保住 disaster-window net 与 `Overlay-B` 相同。
3. 代价是 account-level annualized ROE uplift 从 `+0.088pp` 降到 `+0.046pp`，大约砍掉一半。
4. `Overlay-E`（在 `D` 基础上把 idle gate 提到 `80%`）与 `D` 完全同值，说明 **hybrid 实际触发的日子本来就全部满足 `idle BP >= 80%`**，更高 idle gate 在这个局部上是 inert。

因此：

- `Overlay-B` 仍是 **最高回报** 候选
- `Overlay-D` 是 **治理最干净且 disaster 结果最稳** 的候选
- 但两者都还没有强到足以进入 DRAFT overlay spec discussion
- `Q036` 当前最合理状态仍是 **continue research**

---

## 1. 为什么要做 Phase 3

Phase 2 的核心 tension 已经很清楚：

- `Overlay-B`：回报最好，disaster net 最干净，但仍有 `20%` 的 overlay fires 发生在 pre-existing `>=2` short-gamma 环境
- `Overlay-C`：stacking 治理最好（`0%`），但回报略低，且 disaster-window net 不如 `B`

所以本轮不是再开新 semantic tree，而是只回答一个 guardrail refinement 问题：

> 如果把 `B` 和 `C` 合并，能否保住大部分 account-level ROE uplift，同时把 stacking 风险压到接近零？

---

## 2. 变体定义

基线：

- `V_baseline` = `V_A / SPEC-066`

对照：

- `Overlay-B_ctrl` = `2x` first-entry iff `idle BP >= 70%` and `VIX < 30`
- `Overlay-C_ctrl` = `2x` first-entry iff `idle BP >= 70%` and **no IC_HV already open**

本轮新增：

- `Overlay-D_hybrid` = `2x` first-entry iff
  - `idle BP >= 70%`
  - `VIX < 30`
  - `no IC_HV already open`

- `Overlay-E_hyb80` = `Overlay-D` plus stricter idle gate:
  - `idle BP >= 80%`
  - `VIX < 30`
  - `no IC_HV already open`

共同规则：

- 一旦某个 cluster 的 first entry 已经 boosted，则同 cluster 第 2 笔不再开
- 如果 first entry 没有 boost，则保留 baseline `V_A` 行为

---

## 3. Account-Level 结果

| Variant | Total PnL | Annualized ROE | Δ Ann ROE vs baseline |
|---|---:|---:|---:|
| `V_baseline` | `+$403,850` | `8.67%` | — |
| `Overlay-B_ctrl` | `+$414,556` | `8.76%` | `+0.088pp` |
| `Overlay-C_ctrl` | `+$413,214` | `8.75%` | `+0.077pp` |
| `Overlay-D_hybrid` | `+$409,492` | `8.72%` | `+0.046pp` |
| `Overlay-E_hyb80` | `+$409,492` | `8.72%` | `+0.046pp` |

### 直接解读

- `D` 仍然是正增量 overlay，但 uplift 已缩到非常小
- `D` 相比 `B` 少了 `+$5,064` 总 PnL，annualized ROE uplift 约减半
- `E` 与 `D` 完全同值，说明 `80% idle gate` 没有进一步筛掉任何 `D` 的实际触发

---

## 4. Incremental Return vs Incremental Tail Cost

| Variant | MaxDD | Δ CVaR 5% | Disaster Net | Peak BP% |
|---|---:|---:|---:|---:|
| `V_baseline` | `-10,323` | — | `+301` | `30.0%` |
| `Overlay-B_ctrl` | `-9,749` | `-74` | `+301` | `38.0%` |
| `Overlay-C_ctrl` | `-9,749` | `-74` | `-99` | `34.0%` |
| `Overlay-D_hybrid` | `-9,749` | `-74` | `+301` | `34.0%` |
| `Overlay-E_hyb80` | `-9,749` | `-74` | `+301` | `34.0%` |

### 关键比较

`Overlay-D` 相对 `Overlay-B`：

- account-level uplift 更低：`+0.046pp` vs `+0.088pp`
- disaster-window net 不变：都为 `+301`
- `Peak BP%` 从 `38%` 降到 `34%`
- stacking 从 `20%` 降到 `0%`

因此 `D` 的实际语义是：

> 用一半左右的 incremental return，换掉 `B` 剩余的 stacking 风险，并把 peak BP 再压低 `4pp`

这不是“更优”，而是“更保守、更干净”。

---

## 5. Capital-Allocation / Governance 结果

| Variant | +BPdays | Idle Utilization | Overlay Fires | SG mean | SG>=2 |
|---|---:|---:|---:|---:|---:|
| `Overlay-B_ctrl` | `+2,569` | `0.43%` | `25` | `0.84` | `20%` |
| `Overlay-C_ctrl` | `+2,793` | `0.46%` | `29` | `0.41` | `0%` |
| `Overlay-D_hybrid` | `+1,428` | `0.24%` | `18` | `0.50` | `0%` |
| `Overlay-E_hyb80` | `+1,428` | `0.24%` | `18` | `0.50` | `0%` |

### 解释

- `D` / `E` 只动用了 baseline idle budget 的 `0.24%`
- 这意味着 hybrid guardrail 把 overlay 缩得非常窄
- 它仍是正的 idle-capital deployment，但已经非常接近“治理优先、收益次之”的姿态

---

## 6. Disaster Window Detail

| Variant | 2008 GFC | 2020 COVID | 2025 Tariff | Total |
|---|---:|---:|---:|---:|
| `V_baseline` | `0` | `-1,656` | `+1,958` | `+301` |
| `Overlay-B_ctrl` | `0` | `-1,656` | `+1,958` | `+301` |
| `Overlay-C_ctrl` | `0` | `-2,665` | `+2,565` | `-99` |
| `Overlay-D_hybrid` | `0` | `-1,656` | `+1,958` | `+301` |
| `Overlay-E_hyb80` | `0` | `-1,656` | `+1,958` | `+301` |

### 结论

- `D/E` 的 disaster 行为与 `B` 严格一致
- 这说明 hybrid 的关键新增约束主要作用在 **overlap governance**，而不是再额外改变 disaster-screen 的经济结果

---

## 7. Recent Slice (2018+)

| Variant | Total PnL | PnL/BP-day | Marginal $/BP-day | MaxDD |
|---|---:|---:|---:|---:|
| `V_baseline` | `+$164,958` | `5.9178` | — | `-9,405` |
| `Overlay-B_ctrl` | `+$171,103` | `5.9298` | `+6.2704` | `-9,392` |
| `Overlay-C_ctrl` | `+$168,759` | `5.8599` | `+4.1136` | `-9,392` |
| `Overlay-D_hybrid` | `+$168,465` | `5.9377` | `+7.0563` | `-9,392` |
| `Overlay-E_hyb80` | `+$168,465` | `5.9377` | `+7.0563` | `-9,392` |

这部分说明：

- hybrid 在 recent slice 的 **unit economics** 其实不差
- 但它触发得更少，所以总 dollars 仍然落后于 `B`

即：

> `D` 不是“坏 overlay”，而是“触发过窄，导致总量 uplift 太小”

---

## 8. Quant Judgment

### 8.1 本轮最重要的发现

`Overlay-D hybrid` 证明了：

- `B` 的剩余 stacking 风险是可以工程化压掉的
- 而且压掉之后不需要再付 disaster-window 额外代价

但与此同时也证明：

- **当前 overlay 经济性本来就很薄**
- 再加一层 guardrail 后，annualized ROE uplift 只剩 `+0.046pp`

所以本轮没有产生一个足够强的新候选，能推动到 DRAFT overlay spec discussion。

### 8.2 对各候选的现阶段定位

- `Overlay-B`
  - 优点：最高回报，disaster net 最稳
  - 问题：stacking 仍未完全治理，peak BP 最高

- `Overlay-C`
  - 优点：stacking 彻底清零
  - 问题：disaster-window net 不如 `B`

- `Overlay-D`
  - 优点：把 `B` 的 disaster profile 与 `C` 的 stacking cleanliness 合在一起
  - 问题：回报被压得太薄

- `Overlay-E`
  - 没有独立意义；在当前样本中等同于 `D`

---

## 9. Recommendation

- **Topic**: `Q036` Phase 3 — guardrail refinement
- **Findings**:
  - `B+C hybrid` 可以把 stacking 压到 `0%`
  - hybrid 保住了 `B` 的 disaster-window net
  - 但 account-level annualized ROE uplift 约被压缩到 Phase 2 `B` 的一半
  - `80% idle gate` 在该 hybrid 上是 inert
- **Risks / Counterarguments**:
  - 如果项目对 hidden leverage drift 极其敏感，`D` 的治理形态更可接受
  - 但如果 uplift 只有 `+0.046pp annualized ROE`，治理复杂度可能不值得
- **Confidence**: medium-high
- **Next Tests**:
  - 若继续研究，重点不应再是 `A/B/C/D/E` 横向扩枝
  - 应改为回答一个更窄问题：
    - 是否存在一个 **比 `D` 更不保守、但仍把 stacking 压在低位** 的 conditional rule
    - 例如限制的不是 “no IC_HV open at all”，而是 “pre-existing short-gamma count < 2”
- **Recommendation**: **continue research**

当前不建议：

- 不建议 `drop Q036`
- 也不建议 `ready for DRAFT overlay spec discussion`

更准确的状态是：

> `Q036` 已证明 idle-BP overlay 在经济上可为正，但在当前 guardrail 组合下，增量回报仍偏薄，尚不足以支持制度化推进。
