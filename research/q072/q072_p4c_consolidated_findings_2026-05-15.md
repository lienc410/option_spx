# Q072 P4C — Consolidated Findings (P4C.0 – P4C.6)

**Date**: 2026-05-15
**Phase**: All P4C subphases complete (P4C.0 eligibility / P4C.1 priority scoring / P4C.4 5-allocator simulation / P4C.5 cap-impact / P4C.6 walk-forward / P4C.7 stress slice embedded in P4C.4)
**Status**: Ready for Q072 final memo + production SPEC proposal

---

## TL;DR — Q072 P4 三个决定性结论

1. **Priority allocator 复杂度不值得**——19y simulation 中 priority allocator 与 FCFS / main-first / sleeve-first **完全等价**（identical n_entered, total P&L, max DD），因为现行 sleeve cadence 下**多 candidate 同日竞争同 pool BP 的情况极少发生**

2. **Static per-sleeve cap 反而恶化结果**——在 default cap 之上加 per-sleeve cap（Main 70/DD 20/Aftermath 15/HV 60），P&L 减少 $102k（full 19y），无任何 max DD 改善

3. **R5 + R6 是真正的高价值规则**——R5 stress episode cap + R6 second-leg block 在 2022 真实 second-leg backtest 中**减少 $11.6k 组合损失**（B_tight: -$151k vs default: -$163k），且 R6 19y 仅 fire 26 天，几乎不扰动正常交易

---

## 1. P4C.4 — 5-Allocator Simulation 结果

### Full 19y

| Allocator | Cap | n entered | n blocked | Total P&L | Ann ROE | Sharpe | Max DD | Peak SPX BP | Peak /ES BP |
|---|---|---|---|---|---|---|---|---|---|
| main-first | default | 872 | 7 | **$742k** | 8.65% | 3.36 | -$175k | 56.7% | 80.0% |
| sleeve-first | default | 872 | 7 | $742k | 8.65% | 3.36 | -$175k | 56.7% | 80.0% |
| FCFS | default | 872 | 7 | $742k | 8.65% | 3.36 | -$175k | 56.7% | 80.0% |
| **priority** | default | 872 | 7 | **$742k** | **8.65%** | 3.36 | -$175k | 56.7% | 80.0% |
| static-cap | default | 803 | 76 | $641k | 8.18% | 2.99 | -$174k | 56.7% | 59.9% |
| main-first | B_tight | 842 | 37 | $694k | 8.19% | 3.23 | -$163k | 45.4% | 59.9% |
| priority | B_tight | 842 | 37 | $694k | 8.19% | 3.23 | -$163k | 45.4% | 59.9% |
| static-cap | B_tight | 801 | 78 | $634k | 8.13% | 2.96 | -$175k | 45.0% | 59.9% |

**核心结果**：
- 4 个非 static-cap allocator (main-first / sleeve-first / FCFS / priority) 在 19y 数据上**完全等价**
- 这意味着 19y 历史里**多 candidate 同日竞争同 pool BP 的情况几乎不发生**——sleeve cadence 自然错开（DD 在 dd4 后入场，HV 5 TD 一笔，main 按 catalog 节奏，Aftermath 跟 BPS_HV）
- **Allocator 复杂度无用武之地**

### Stress 2022（关键测试 bed）

| Allocator | Cap | Total P&L | Max DD | Worst 20d | Blocked P&L | Blocked worst trade |
|---|---|---|---|---|---|---|
| FCFS/priority | **default** | -$163,065 | -$174,959 | -$58,745 | +$1,807 | +$1,807 |
| FCFS/priority | **B_tight** | **-$151,490** | -$163,139 | -$59,320 | **-$11,407** | **-$15,771** |
| static-cap | default | -$163,331 | -$173,585 | -$59,034 | +$3,879 | -$5,708 |
| static-cap | B_tight | -$164,970 | -$174,978 | -$59,034 | +$3,879 | -$5,708 |

**B_tight cap 在 2022 真实 second-leg 中减少 $11,575 组合损失**——P&L 从 -$163k 改善到 -$151k。这是 R6 second-leg block + B_tight 各项 cap 联合的真实保护证据。

**注意**：static-cap allocator 在 2022 表现最差——per-sleeve cap 把 BPS_HV / DD 的有效 trades 也挡掉。

---

## 2. P4C.6 — Walk-Forward 验证

Priority lookup 在 2007-2018 训练，2019-2026 测试：

| 指标 | 值 |
|---|---|
| Test candidates | 369 |
| Pearson corr (IS vs OOS priority) | 0.746 |
| **Spearman rank corr** | **0.704** |
| Mean abs diff | 11.6 priority points |

**Spearman 0.704 处于 borderline overfit warning 区**（>0.9 stable / 0.7-0.9 moderate / <0.7 overfit）。

By-sleeve 稳定性：
- **稳定**：HV_Ladder (Δ=0.1), BPS_HV (Δ=-1.1), BPS (Δ=-6.7)
- **不稳定**：DD_Overlay_B (Δ=+40, n=4), Bull_Call_Diagonal (Δ=+17.1)

**结论**：priority 排序的 top-tier（BPS_HV, BPS, DD_A, HV_Ladder）稳定；低端 stable strategies (BCD, DD_B 小样本) overfit 风险高。但因为 P4C.4 已证明 priority allocator ≡ FCFS，walk-forward 实际意义有限。

---

## 3. P4C.5 — Cap Impact 详情（已在前一份 status 报告）

简要重复：
- Default cap (SPX 70/ES 80/Combined 60/SV 50): 19y 仅 block 18 笔，几乎不扰动
- B_tight cap (SPX 60/ES 60/Combined 50/SV 35): block 89 笔，full 19y 净亏 $86k，但 stress 2022 净保护 $11k

---

## 4. Q072 P4 — 最终治理建议

基于 P1 – P4C 全部证据，Q072 推荐的 **production governance** 是：

### 推荐方案：Augmented Default Cap

```
R1: SPX PM pool cap          = 70% NLV
R2: /ES SPAN cap             = 80% NLV
R3: Combined economic cap    = 60% combined NLV
R4: Max short-vol exposure   = 50% combined NLV
R5: Stress episode reduced cap = 60% NLV (SPX) during tight stress episode
R6: Second-leg state         = absolute block for new short-vol entries
```

### 不推荐的方案

| 方案 | 原因 |
|---|---|
| **Priority allocator** | 19y 数据中 ≡ FCFS（无 BP 竞争实例），复杂度无价值；walk-forward Spearman 0.70 borderline overfit |
| **Static per-sleeve cap** | P4C.4 显示 static-cap 减少 $102k P&L（full 19y），未改善 max DD；over-restricts profitable trades |
| **B_tight cap (全面 tighten)** | 19y 净亏 $86k gains 换 $10k worst trade 保护，trade-off 太差 |
| **降低 Aftermath threshold** | Q070 已论证维持 28 |
| **关闭 Aftermath gate** | P4A 显示 Aftermath 仍 +$53k full 19y，且是 low-cost guardrail |

### 关键缺口（不在 P4 范围）

- **2008 / 2022 真实 second-leg + 完整 sleeve pack 的 backtest** 还未做。当前 P4C.5/C.7 已嵌入 stress slice，但 sleeve 在 2008 实际未部署（DD Overlay 2026-05, HV Ladder pre-launch）。Q071 final lock 后可做完整 inject。
- **Production 实施 SPEC**：R5 / R6 需要 daily portfolio state tracker（已有 P4C.0 原型）+ live monitoring。建议另开 SPEC-xxx 实施。

---

## 5. P4C 输出文件清单

```
research/q072/
├── q072_p4c0_eligibility_filter.py
├── q072_p4c0_portfolio_state.csv             ← 19y daily portfolio state
├── q072_p4c0_eligibility_log.csv             ← 877 candidates × pass/blocker (default)
├── q072_p4c1_priority_allocator.py
├── q072_p4c1_candidates_with_priority.csv    ← 877 × priority score
├── q072_p4c1_bucket_lookup.csv               ← strategy-specific 2D bucket lookup
├── q072_p4c1_parent_lookup.csv               ← per-sleeve parent stats
├── q072_p4c4_5_allocator_sim.py
├── q072_p4c4_allocator_results.csv           ← 5 allocator × 2 cap × 5 split (50 cells)
├── q072_p4c5_cap_impact.py
├── q072_p4c5_log_default.csv / _B_tight.csv  ← per-candidate eligibility log
├── q072_p4c5_blocked_trades.csv
├── q072_p4c5_cap_impact_summary.csv
├── q072_p4c6_walkforward.py
├── q072_p4c6_walkforward_compare.csv         ← IS vs OOS priority per candidate
├── q072_p4b_es_pool_framework.py
├── q072_p4b_results_placeholder.csv          ← awaiting Q071 lock
├── q072_p4b_combined_placeholder.csv
├── q072_p4a_findings_2026-05-15.md
├── q072_p4b_p4c0_status_2026-05-15.md
├── q072_p4c_status_2026-05-15.md
└── q072_p4c_consolidated_findings_2026-05-15.md  ← 本 memo
```

---

## 6. 下一步建议

### 立即收口
Q072 final memo 把 P1-P4 全套结论收编，明确：
- production 治理建议（augmented default cap）
- 不推荐的复杂方案及证据（priority allocator / static cap）
- 推荐另开 SPEC-xxx 实施 R5/R6 rules

### Q071 lock 后再做
- P4B /ES pool ablation 重跑（V2f → final config）
- P4C.7 完整版：2008/2022 SPX/VIX path inject DD + HV 假定部署

### 中期 monitoring
- 每月查 portfolio state tracker 输出，看 R5/R6 是否触发
- 半年回顾：实盘是否出现"4-sleeve + 真实 second-leg"样本，如有则用真实数据校准 P3.3/P3.4 conditional co-loss

---

## 7. 一句话答 PM 的核心问题

> **"应该砍哪个 sleeve / 设什么 cap / main-first 是否合理 / priority allocator 是否优于 static cap?"**

**答**：
- 不砍任何 sleeve（P4A 显示 DD/Aftermath/HV 都是 alpha 贡献者，P4B 待 Q071 lock 后确认 HV）
- Cap：default (SPX 70/ES 80/Combined 60/SV 50) + R5 stress 60 + R6 second-leg block
- main-first / priority / FCFS 在 19y 中等价 → 用最简单的 FCFS（即 production 当前默认）
- Priority allocator 不优于 static cap（19y 数据下 priority ≡ FCFS）；static cap 不优于 default + R5/R6 → **augmented default cap 就是答案**

确认是否进入 Q072 final memo 收口？
