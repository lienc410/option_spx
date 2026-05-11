# Q063 Closure Memo — IVP<55 Gate Robustness Confirmed

**Date**：2026-05-11
**Researcher**：Quant
**Verdict**：**REJECT relaxation. Keep IVP < 55 gate unchanged.**
**Status**：CLOSED

---

## 0. TL;DR

PM 提出 hypothesis：「IVP<55 gate 在低 VIX 环境下产生 false alarm」。Q063 三 Tier + decay-weighted + recent-window 四层检验后，**hypothesis 被数据精确反向 reject**。Gate 在最近 2024-2026 期间挡住的 5 笔 entries 累计 counterfactual P&L = **-$13.7k**。Gate 不是 false alarm，是高价值真信号。

---

## 1. Hypothesis vs Data

| 假设 | 数据 |
|---|---|
| Gate 在低 VIX 过度保守 | Phase 1：低 VIX BLOCKED entries WR 63% (vs ALLOWED 83%)，avg P&L $389 (vs $2,323)。即使在低 VIX，blocked entries 显著差于 allowed |
| Relax gate 应提升 ann ROE | Phase 2：候选 A unweighted +$6,069 over 19y。但 Phase 3 OOS test 期 A LOSES -$907/yr |
| Recent regime 更应 favor relax | **Phase 4 完全反转**：3y HL decay → BL wins +$19,237；last 5y → A loses -$13,730 |

---

## 2. Mechanism — 为什么 gate 在低 VIX 仍然 valuable

**Counter-intuitive 但 empirically robust**：

- VIX=15-17 + IVP=60-65 不是矛盾，是「vol 已 compress 到 1y 高分位（相对）」即使「absolute level 低」
- 这种 setup 在 2024-2026 实证为「**complacency before mean reversion**」
- IV pricing 在此区间 underprice tail——BPS sells put at high IVP but absolute premium reasonable; max-loss event probability is mispriced
- Gate 正确识别此 setup 并 reduce_wait

PM 的 perception「block 后市场没崩 → gate 错」忽略了 counterfactual 的真实形态：
- 不是「市场 crash」，而是「市场 chop / sharp 1-2 周 pullback + theta decay → trade hit debit-double stop」
- PM 看不到「不入场则不亏」，只看到「不入场也没赚」

---

## 3. Quant Forensic — Recent 5 trades counterfactual

A 在 2024-2026 期间放进的 5 笔 added trades 实证 P&L：

```
year  added_trades  added_pnl
2024     +3         -$4,825
2025     +1         -$3,723
2026     +1         -$5,181
────────────────────────────
total    +5         -$13,729
```

**5 笔被 gate 挡住的 trades 平均亏 $2,746/笔**。在 PM 1h/day day-job 约束下，这是非常 material 的损失保护。

---

## 4. 推广性 insight

Q063 是一个 **「PM intuition tested and reversed by data」** 的典型案例。Quant lane 的价值正是提供这种 counterfactual 测试，避免 perception bias 驱动的 SPEC 修订。

类似的 perception biases 应警惕：
1. **Survivor bias on blocked entries**：看到的是「block 后没崩」，看不到「if 入场 will lose」
2. **Recency bias on absolute VIX**：2023-2025 异常低 vol regime 让 absolute VIX 看似过低；IVP 相对分位仍 valid
3. **Counterfactual blindness**：缺少「同时跑 baseline 与候选 + 比较 forward returns」的 mental model

---

## 5. Q063 关闭 — 不修订 SPEC

| 项 | 状态 |
|---|---|
| SPEC change | **None** — IVP < 55 gate 保留 |
| Code change | None |
| Deploy | Not required |
| Live recommendation today | 保持 reduce_wait (IVP=64 ≥ 55)，gate 正在 protect |

---

## 6. Watchlist（可选 follow-up，PM 决定）

| 选 | 含义 | 优先级 |
|---|---|---|
| Strengthen gate | IVP > 50 in low-VIX block (gate even tighter)——既然 gate 在 low VIX 真正起作用，也许阈值可更紧 | Low（先验更复杂的 gate 容易 overfit） |
| Q063.1 IVP-IVR-VIX3M 联合 gate | 探索三因子复合 gate 是否优于纯 IVP | Low（边际收益可能更小） |
| Q063.2 BPS gate 重写为 prob-based | 用 ML / regression 直接预测 tail prob 而非 threshold | Medium-Low（工程量大） |

---

## 7. Artifacts

- `research/q063/q063_phase1_vix_stratified_blocked_trades.py`
- `research/q063/q063_phase2_candidate_gates.py`
- `research/q063/q063_phase3_robustness.py`
- `research/q063/q063_phase4_decay_weighted.py`
- `research/q063/q063_phase1_blocked_trades.csv`
- `research/q063/q063_phase2_gate_comparison.csv`
- `task/q063_phase4_closure_memo_2026-05-11.md`（本文档）

---

## 8. Quant standing recommendation

**Live recommendation for 2026-05-11 unchanged**：
- Main SPX strategy currently in `reduce_wait` (IVP=64 ≥ 55)
- This is the **gate working as designed**——历经 Q063 验证，**no override warranted**
- Wait for IVP to drop below 55 (1y rolling will gradually shift as old high-IV bars roll out of window)
- 若 PM 想 manually override（个案判断），按 SPEC-094 主策略 manual SOP 流程；但 Q063 数据建议**默认尊重 gate**

Q063 closed.
