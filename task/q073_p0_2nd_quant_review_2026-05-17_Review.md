# Q073 P0 Anchored Objectives — 2nd Quant Review

**Reviewer**: 2nd Quant
**Date**: 2026-05-17
**Source**: `research/q073/q073_p0_anchored_memo_2026-05-17.md`
**Verdict**: **PASS WITH MINOR REVISIONS — 可以签 P0，进入 P1**

---

## Final verdict statement

> Q073 P0 is now sufficiently anchored for research launch. The project is correctly framed as risk-constrained portfolio ROE optimization under a multi-strategy, multi-account architecture. The ROE denominator, floor/stretch targets, risk constraints, tear-down boundaries, lever priority, and review gates are now mostly clear. Before P1 starts, revise the cash-adjusted terminology, clarify V6/V7 as promotion-level evidence gates, and ensure P1 outputs include a ROE bridge and idle-BP reason decomposition. After those edits, P0 can be signed and Q073 can proceed to P1.

---

## 5 项 Minor Revisions Required Before P1

1. **Terminology fix**: "Cash-adjusted Total Account Return" → "Excess ROE over cash baseline"; separately report Total Account Return = strategy PnL + cash yield on idle
2. **Stretch/Floor clarity**: 20% is **aspirational stretch, NOT failure threshold**; 8% is Q073 success floor
3. **V6/V7 demoted from hard veto → promotion-level evidence gate**:
   - V6 bootstrap < 80% → still paper/shadow promotable, not auto-淘汰
   - V7 walk-forward Spearman 仅在 architecture 使用 learned/optimized allocator 时为 production-ready gate
4. **Aftermath retire wording**: 按 permission/bypass role 评价, 不按 standalone alpha
5. **P1 增加 2 个输出**: ROE bridge + Idle BP decomposition by reason

## Other minor adjustments

- **P2A stop condition**: 不要因单 lever < 0.5pp 就 "dead"。需 AND 低风险 lever 组合也无 ≥ 1.0pp upside
- **Lever G (retire)**: 在 **P1 role map** 里 identify, 在 **P2C** actioned. 不要拖到 P2C 才识别

---

## 2nd Quant Sign-off Status (CONDITIONAL PASS)

- [x] P0 锚定项 acceptable
- [revise → applied] V6/V7 promotion-level evidence gate (not universal hard veto)
- [x] P1-P5 plan acceptable
- [minor revise → applied] cash-adjusted terminology
- [x] stopping conditions acceptable after P2A wording tweak
- [x] G3 / G4 mid+final review scope acceptable

→ 5 项修订全部应用至 P0 memo 2026-05-17, status: **PASS** for P1 launch.
