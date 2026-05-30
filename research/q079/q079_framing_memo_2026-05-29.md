# Q079 Framing — VIX=15 Boundary Hardness

**Date**: 2026-05-29
**Owner**: Quant Researcher
**Status**: FRAMING + P1 START
**Trigger**: PM observed hard split at VIX=15 in selector; questioned whether VIX=15.3 + IVP=20 should route to LOW_VOL strategies
**Approval**: PM said "A" (option A) — start P1 quantification, kill if < 5 days/yr, continue if ≥ 10 days/yr

---

## Question

NORMAL bucket 在 **VIX ∈ [15, 16] + IVP ∈ [20, 40] + BULLISH/NEUTRAL trend** 的边缘 cell（当前被 SPEC-058/060 强制 Reduce/Wait），是否应该 reuse LOW_VOL 策略集（BCD / IC）而不放大 tail？

---

## Boundary hardness (already verified in framing chat)

固定 IVP=20（IV LOW），分 3 trend 看 VIX 14.9 vs 15.3：

| Trend | VIX 14.9 (LOW_VOL) | VIX 15.3 (NORMAL) | Δ |
|---|---|---|---|
| BULLISH | Bull Call Diagonal (BCD) | Reduce / Wait | 开仓 → 不开 |
| NEUTRAL | Iron Condor (IVP=20 是 IC 入场下沿) | Reduce / Wait | 开仓 → 不开 |
| BEARISH | Reduce / Wait | Bear Put Spread | wait → 反向防御 |

来源：`signals/vix_regime.py:34-35`, `strategy/selector.py:177-178, 986-1024, 1197-1200, 1245-1250`.

---

## Plan

按 PM option A：先 P1 量化触发频率，再决定继续。

### P1 量化（本轮）

数据源：`research/q078/_signal_history_cache.csv` — 26 年 daily signal history（已含 VIX / IVP / trend / strategy / IV signal 全部字段，6639 trading days，2000-01-03 → 2026-05-28）。

**统计目标**：
1. **A. 边缘 cell 触发天数**：VIX ∈ [15, 16] + IVP ∈ [20, 40] + trend ∈ {BULLISH, NEUTRAL} + strategy = "Reduce / Wait"（被 boundary 拒绝）
2. **B. 触发分布**：年度触发频率（min/median/max/p95）
3. **C. 反事实强度**：触发日 SPX 30d/60d/90d 实际表现 — 如果当时开仓 BCD/IC 会怎样（粗 proxy，不算实际 PnL）
4. **D. flip 频率**：VIX 在 [14, 16] 区间徘徊时穿越 15 的次数 → 估计 chatter
5. **E. 控制对照**：扩展 buffer 到 VIX ∈ [14, 17] 看体量变化（敏感性）

**决策门槛**（per PM）：
- **触发频率 < 5 天/年**：研究停止，结论 "boundary 硬但触发低不值得改"，drop
- **触发频率 ≥ 10 天/年**：进 Tier 2 完整 — P2 反事实 PnL + P3 tail check + P4 方案设计
- **5 ≤ 频率 < 10**：PM-discretionary，给 PM 看数据 + 推荐

### Out of scope (Q079 不做)

- 改 VIX=22 boundary (HIGH_VOL 入口) — 独立课题
- 改 IVP=40/70 boundary — 与 VIX boundary 解耦
- 改 EXTREME_VOL=35 — Layer-1 frozen
- 改 SPEC-058/060 IVP gate 数值本身（即使 Q079 结论触发，也是 follow-up SPEC）
- 改 BCD comfort filter / BCS_HV / IC_HV 单独 SPEC
- BEARISH trend 边缘 cell（与 BULLISH/NEUTRAL 反向防御策略不同；Q079 主线先做 BULLISH/NEUTRAL，BEARISH 看 PM 后续是否单独要）

### Files

```
research/q079/q079_framing_memo_2026-05-29.md      ← this file
research/q079/q079_p1_boundary_frequency.py        ← P1 script
research/q079/q079_p1_cells.csv                    ← per-day cell tag
research/q079/q079_p1_annual.csv                   ← per-year aggregation
research/q079/q079_p1_memo.md                      ← P1 conclusion
```

---

## Expected output

- P1 memo with: edge-cell trigger count / annual distribution / SPX-forward summary / flip count
- Verdict: drop / hold / continue-to-Tier-2
- 不进 SPEC，不修改生产代码
