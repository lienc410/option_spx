# Q079 P1 Memo — VIX=15 Boundary Trigger Frequency

**Date**: 2026-05-29
**Phase**: P1 (Tier 2 quick quantification before full Tier 2)
**Script**: `research/q079/q079_p1_boundary_frequency.py`
**Data**: `research/q078/_signal_history_cache.csv` (6,639 trading days, 2000-01-03 → 2026-05-27)
**Decision threshold** (per PM 2026-05-29): < 5 days/yr → drop; ≥ 10 days/yr → continue full Tier 2

---

## Verdict

**DROP** — primary edge cell triggers only **1.4 days/year on average**, well below PM's 5-days/yr threshold. Boundary hardness is structurally real but the trigger frequency is too low to justify SPEC revision.

---

## A. Edge-cell trigger frequency (primary scope)

**Definition**: VIX ∈ [15, 16) + IVP ∈ [20, 40) + trend ∈ {BULLISH, NEUTRAL} + selector output = "Reduce / Wait"

| Stat | Value |
|---|---|
| Total triggered days | **38** |
| Span | 26.4 years |
| **Avg per year** | **1.4** |
| Annual min / median / max / p95 | 0 / 0 / 11 / 7 |
| Years with zero triggers | 19 / 27 (70%) |

**Distribution is extremely sparse**. 19 of 27 years have zero edge-cell days. Only 8 non-zero years:

```
Year   Trigger days
2004        8
2012        3
2013        3
2016        3
2019        4
2023        2
2025       11   ← recent concentration
2026 (ytd)  4   ← in-progress
```

**Verdict per PM threshold**: 1.4 < 5 → DROP.

## E. Sensitivity — extended buffer (VIX 14-17)

Even if PM widens the buffer band to VIX ∈ [14, 17):

| Stat | Value |
|---|---|
| Total triggered days | 104 |
| **Avg per year** | **3.9** |

**Still below 5 days/yr threshold.** Extending buffer doesn't unlock enough volume.

## B. SPX forward returns on edge-cell days (counterfactual proxy)

If those 38 edge-cell days had been routed to a long-debit LOW_VOL strategy (BCD / IC), what would SPX have done? Pure SPX forward returns (not actual BCD PnL):

| Horizon | Mean | Median | Std | p05 | n |
|---|---|---|---|---|---|
| SPX +30d | **+2.68%** | +2.75% | 3.05% | -2.10% | 38 |
| SPX +60d | **+5.40%** | +5.61% | 3.62% | +0.10% | 38 |
| SPX +90d | **+8.07%** | +7.60% | 4.00% | +3.35% | 36 |

**Strong positive selection** — every horizon has positive p05 at 60d/90d. This is **not surprising**: the cell selects BULLISH-trend days, and SPX trends mean-revert toward up in low-vol regimes.

**But this doesn't change the verdict**: even at the theoretical max (38 hypothetical BCD trades over 26 years), the marginal portfolio impact is < 2 trades/year × theoretical BCD ROI per trade. Annual ROE contribution ≈ noise-level (< 0.5pp per Q078 noise framework). Engineering cost > expected gain.

## C. VIX 14-16 chatter

| Stat | Value |
|---|---|
| Days with VIX ∈ [14, 16) | 900 (13.6% of all trading days) |
| VIX=15 crossings within those days | 261 |
| VIX=15 crossings total | 322 |
| Crossings / day within band | 0.290 |
| Estimated annual crossings within band | **9.9** |

**~10 boundary crossings per year inside the 14-16 buffer band.** Any boundary-softening rule (e.g., hysteresis, buffer band, regime sticky) would have to handle ~10 flips/year — non-trivial state machine. Compared to 1.4 edge-cell triggers/year, the **chatter ratio is 7:1 (10 crossings : 1.4 actionable triggers)** — would-be softening rule would be triggered by chatter far more often than by actual decisions.

## Cross-checks

1. **2025-2026 concentration**: 11 + 4 = 15 days = 39% of all 38 historical triggers. Reflects the recent low-vol VIX regime sitting around 14-16. Not new (2004 also had 8 days), but worth noting as a regime feature.
2. **All edge-cell days are NORMAL+IV LOW+BULLISH/NEUTRAL** — **consistent with**, not evidence for, SPEC-058/060 "thin premium reject" logic operating as designed. The boundary IS hard, but whether the rejection is calibrated correctly cannot be inferred from this dataset (single sample of selector-rejected days; no positive control of accepted-and-loss days for comparison).
3. **Why no 2008/2020 crisis triggers**: edge cell requires VIX [15, 16) — crisis years (2008, 2020, 2022) had VIX in 22+ regime, missing the cell entirely.
4. **2025-26 spike concentration analysis**: even projecting forward, if 2026 maintains current pace, full-year ≈ 10 days. Still < 10/yr threshold. The boundary issue may matter slightly more in low-vol regimes but doesn't change Q079 verdict.
5. **2026 cluster note (per ChatGPT 2nd Quant review 2026-05-29)**: 2026 ytd 4 triggers all in 9-day window, with SPX +30d mean −1.49% (only negative-counterfactual year). Earlier draft read this as "boundary worked correctly" — that overstates evidence from n=4 single-cluster. Correct read: **consistent with the drop verdict, not independent evidence for selector calibration**. The frequency reason (1.4 days/yr) is sufficient on its own; the 2026 negative counterfactual is corroborating, not confirming.

## Unaudited boundaries (per ChatGPT Q17)

This Q079 work audits **only** the VIX=15 boundary in IV LOW + BULLISH/NEUTRAL trend cells. The following boundaries are intentionally **NOT audited** here and are open questions for future research lines (each independently, with dual-threshold frequency AND per-trigger ROE per `feedback_boundary_research_dual_threshold.md`):

| Boundary | Where | Open question |
|---|---|---|
| VIX = 22 | NORMAL → HIGH_VOL | Same cliff-effect concern, but HIGH_VOL gives BPS_HV / IC_HV variants not Reduce/Wait → counterfactual differs |
| IVP = 40 | IV LOW → IV NEUTRAL | Affects gate routing in both LOW_VOL and NORMAL; per-VIX-bucket impact may differ |
| IVP = 70 | IV NEUTRAL → IV HIGH | Affects SPEC-060 "NORMAL + IV HIGH + BULLISH → R/W"; this is the SPEC-058/060 directly-relevant threshold |
| VIX = 35 | HIGH_VOL → EXTREME_VOL | Layer-1 frozen by design (per SPEC-103); revisiting requires separate framing |

These are **not** Q079 deferments — they are independent research lines. Q079 closes on the VIX=15 boundary alone.

---

## Findings & Recommendation

### Findings

1. **PM 直觉结构上对**：boundary 在 IV LOW + BULLISH/NEUTRAL trend 区确实硬（VIX 0.4pt 变动改变 selector 输出，物理上不合理）— 这点 framing memo 已确认
2. **触发频率远低于改 SPEC 门槛**：1.4 天/年 ≪ 5 天/年
3. **Buffer 扩大也不足**：3.9 天/年 < 5 门槛
4. **Counterfactual 方向证实**：被拒绝的 BCD/IC 候选若按 LOW_VOL 路由，SPX 90d 后均上涨 — 但样本太小，年化 ROE 贡献 sub-noise
5. **Chatter 风险**：boundary softening 会被 7× 频率的 chatter 触发，工程复杂度 ROI 差

### Recommendation: `drop`

Per QUANT_RESEARCHER.md research output format:

> **Topic**: VIX=15 boundary hardness in NORMAL + IV LOW + BULLISH/NEUTRAL edge cell
>
> **Findings**: Boundary hardness is structurally real but trigger frequency is 1.4 days/yr — below PM's 5-days/yr threshold. Counterfactual SPX returns suggest theoretical BCD path-routing would have positive expectation, but absolute volume is too small to move portfolio ROE meaningfully. Boundary chatter (10/yr) significantly exceeds actionable trigger rate (1.4/yr).
>
> **Risks / Counterarguments**:
> - Recent regime (2025-2026) shows mild concentration — worth watching but not changing 26y decision
> - Counterfactual uses pure SPX return as proxy, not actual BCD PnL — overestimates upside (BCD also has IV-expansion tail risk and stop logic)
> - SPEC-058/060 are intentionally vetted — Q079 finds no evidence to overturn
>
> **Confidence**: High — 26y / 6,639 days / hard-thresholded query, simple count statistic
>
> **Next Tests**: None recommended. If 2026 trigger count substantially exceeds 2025 (e.g., > 15 by EOY), revisit with new data.
>
> **Recommendation**: **`drop`** — close Q079, do not enter Tier 3 or SPEC.

### What to keep / document

- **Memory worthy**: "Edge-cell trigger frequency < 5/yr threshold is the right kill criterion for boundary-softening research." General principle for future regime / threshold studies (Q079 closes confirming this gatekeeper works).
- **Watch item**: 2025-2026 edge-cell concentration. If 2027+ continues > 10/yr, Q079 can be reopened with newer data.

### What NOT to do

- Do NOT modify `LOW_VOL_THRESHOLD = 15.0` or `HIGH_VOL_THRESHOLD = 22.0`
- Do NOT modify `IVP_LOW_THRESHOLD = 40.0` or `IVP_HIGH_THRESHOLD = 70.0`
- Do NOT add buffer band / hysteresis to selector
- Do NOT relax SPEC-058 / SPEC-060 IVP gates
- Do NOT open Q079 P2 / P3 / P4 — they are predicated on > 5 days/yr threshold

---

## Files

```
research/q079/q079_framing_memo_2026-05-29.md   ← framing
research/q079/q079_p1_boundary_frequency.py      ← script
research/q079/q079_p1_cells.csv                  ← per-day cell tags (38 primary triggers)
research/q079/q079_p1_annual.csv                 ← per-year aggregation
research/q079/q079_p1_memo.md                    ← this file
```

---

Status: **CLOSED — DROP**
