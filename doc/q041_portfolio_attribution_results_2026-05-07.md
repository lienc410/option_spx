# Q041 Portfolio Attribution — Tier 3 Results Memo

Date: 2026-05-07
Owner: Quant Researcher
Window: 2023-01-02 → 2026-04-29 (868 trading days, ~3.3 yr)
Prototype: `backtest/prototype/q041_portfolio_attribution.py`
Artifact: `data/q041_portfolio_attribution_latest.json` (consumed by SPEC-085 F3 carrier)

---

## One-Line Conclusion

Q041 sleeve overlay on the post-`SPEC-084` J3 baseline lifts average BP utilization by **+22.2 pp** (from `15.8%` to `38.0%`) and captures **86.8%** of J3 fully-idle days, with **near-zero tail-clustering signal** (excess overlap vs. occupancy +4.5 pp). On a 3.3-yr in-sample window the mechanism behaves as the `Q046` benchmark + mechanism map predicted, and the artifact has been **accepted by PM as the formal SPEC-085 F3 input**. Per the 2026-05-07 PM decision, this artifact replaces both the original 12-month paper-trading requirement and any default 4–6-week live signal forward-tracking observation window.

---

## Headline Metrics

| Metric | Value | Unit | Interpretation |
|---|---|---|---|
| `idle_day_capture` | **132** | days | Q041 fills 86.8% of J3's 152 fully-idle days |
| `delta_avg_bp` | **+22.21** | pct points | Joint mean BP rises from 15.83% → 38.04% |
| `bp_fill_contribution` | **+22.21** | pct points | Equal to `delta_avg_bp` under additive overlay |
| `worst_day_overlap` | **87.8%** | of bottom-5% SPX-return days | high in absolute terms |
| `excess_overlap_vs_occupancy` | **+4.5** | pct points | Q041 occupancy is 83.3% baseline; tail clustering signal is mild |

---

## Per-Sleeve Cycle Diagnostics

| Sleeve | Symbol | DTE | Δ | BP cap | Cycles | WR | Worst cycle return on BP | Worst cycle date |
|---|---|---|---|---|---|---|---|---|
| Tier 1 | SPX | 30 | 0.20 | 20.0% | 25 | 100% | +0.37% | 2023-12-15 |
| Tier 2 | GOOGL | 21 | 0.20 | 7.5% | 40 | 90% | -2.05% | 2024-08-16 |
| Tier 2 | AMZN | 21 | 0.25 | 7.5% | 40 | 88% | -5.08% | 2026-01-16 |

Cycles are non-overlapping monthly third-Friday rolls. Tier 1 SPX CSP DTE30 produces fewer cycles per year than Tier 2 DTE21 because successive expiries cross more monthly roll candidates under the non-overlap rule. Tier 1 had **zero negative cycles** in the 3.3-yr window — consistent with the `Q041` execution-prep packet's `WR 97% / MaxDD -2.84%` headline (the prior packet was on a 4-yr window including 2022 H2 stress; the present 3.3-yr window starts 2023-01 and so doesn't include the 2022 bear quarter).

---

## Joint BP Behavior

| Stat | Value |
|---|---|
| J3 mean BP% | 15.83 |
| Q041 mean BP% | 22.21 |
| **Joint mean BP%** | **38.04** |
| Joint max BP% | 92.00 |
| Days w/ joint BP > 35% | 399 / 868 (46.0%) |
| Days w/ joint BP > 50% | 99 / 868 (11.4%) |

The joint mean of `38.04%` lands inside the external practitioner band (`Q046`: `25%–30%` typical, `30%+` in elevated vol). The `92%` joint peak indicates concurrency stress days where most allocable capital is in use — these days tolerable because Q041 sleeves are **defined-risk-equivalent** (CSP cash-secured) and allocated separately from the J3 NORMAL/HIGH_VOL ceilings, but operationally they should still be monitored on the SPEC-085 read-only summary surface.

---

## Tail-Clustering Read

The headline `worst_day_overlap = 87.8%` is **not** a strong tail-correlation alarm because Q041 sleeve baseline occupancy is `83.3%`. The discriminating metric is the **excess overlap = +4.5 pp**.

Reading:
- A near-zero excess (≤5 pp) means the worst-5% SPX days had Q041 exposure **roughly proportional to** Q041's overall open share — not disproportionately concentrated in tails.
- A large positive excess (≥15 pp) would mean Q041 systematically held short positions during SPX drawdowns, amplifying tail loss.
- Observed +4.5 pp is in the "mild" zone. Q041 does not appear to systematically time-load short premium into SPX tails on the in-sample window.

This does not exempt Q041 from tail-risk monitoring — it just says the tail-risk alarm is not lit by the in-sample joint exposure pattern.

---

## Caveats / Honest Limits

1. **Window is 3.3 yr, not 19 yr.** Option-level joint simulation requires `data/q041_historical/` which is `2022-05-06 → 2026-05-05`. SPX index has 19 yr but option-level joint behavior cannot be reconstructed pre-2022.
2. **No COVID 2020.** The mechanism is not stress-tested against a vol-crash regime within the joint frame.
3. **Only partial 2022 bear coverage.** J3 baseline timeline starts `2023-01-02`; the 2022 H2 SPX drawdown is not in the joint-window simulation.
4. **CSP BP proxy.** Naked CSP BP is approximated as `K * 100` (margin proxy). Under PM defined-risk this is mildly overstated — relative attribution between sleeves is consistent under the proxy, but absolute BP% has a small upward bias.
5. **No fill calibration.** Backtest assumes 3% slippage on premium and BS-priced strikes. Live forward-tracking should validate slippage/IV/fill behavior, especially for GOOGL/AMZN single-name where retail fill realism is harder than SPX.
6. **Tier 3 not simulated.** COST/JPM earnings IC remains review-only per `Q041` packet; not in this artifact.
7. **Static caveat / candidate list.** SPEC-085 carrier hard-codes the same candidate list; if the Q041 packet is updated, the carrier and this prototype must be re-aligned.

---

## Coverage of the Original Paper-Trading Knowledge Goals

The original 12-month paper-trading requirement was meant to accumulate evidence across five dimensions. This artifact resolves four of them ex-ante:

- **A (cycle quality)**: per-sleeve WR / worst-cycle behavior in line with `Q041` packet expectations — answered.
- **C (overlap with J3 / idle-day fill)**: idle-day capture `86.8%` — answered.
- **D (BP-fill contribution)**: `+22.21 pp` directly quantified — answered.
- **E (tail co-occurrence)**: excess-overlap `+4.5 pp` — mild, not a tail-correlation alarm — answered.
- **B (slippage / fill / single-name realism)**: not answered by backtest. Per the 2026-05-07 PM decision, B is **not** a default open requirement; it remains a **deferred narrow follow-up** that PM may open later if Tier 2 GOOGL/AMZN fill realism specifically becomes a question.

Net effect: the knowledge value the long paper-trading window was supposed to produce is now front-loaded by this artifact. No default observation window is held open against Q041.

---

## Status / Next-Step Posture

Per 2026-05-07 PM decision (reflected in `PROJECT_STATUS.md`, `RESEARCH_LOG.md`, `sync/open_questions.md`):

1. `data/q041_portfolio_attribution_latest.json` is **accepted** as the formal SPEC-085 F3 input. SPEC-085 `/api/portfolio/attribution` already reads it (status: `available`).
2. **No** 4–6-week live signal forward-tracking observation period is required as a default next step. The original 12-month paper-trading line is closed.
3. The main support narrative for Q041 is now: visualization / attribution surface (SPEC-085) + this in-sample artifact, plus the existing read-only `sleeve_candidates[]` overlap-validation view. It is no longer "wait through a long observation window."
4. Tier 2 fill / slippage realism (dimension B above) is **not** an open default item. PM may open a narrow follow-up later; until then no implicit observation window is being held.
5. This memo does not authorize any live trading entry. Promotion of any sleeve to a production trading sleeve remains a separate PM decision and is not implied by acceptance of the artifact.
6. If joint mean BP > 50% becomes a frequent operational concern when the SPEC-085 read-only summary surface is observed in practice, the Tier 2 single-name allocation (currently 7.5% per sleeve) may be revisited before any future live-deployment discussion.

---

## Audit Trail

- Prototype: `backtest/prototype/q041_portfolio_attribution.py`
- Run command: `arch -arm64 venv/bin/python -m backtest.prototype.q041_portfolio_attribution`
- Artifact: `data/q041_portfolio_attribution_latest.json` (schema_version 1.0)
- Consumer: SPEC-085 F3 `/api/portfolio/attribution` → `web/portfolio_surface.py:attribution_payload`
- J3 baseline source: `data/q045_phase2d_idle_bp_timeline.csv`
- Option data source: `data/q041_historical/{SPX,GOOGL,AMZN}.parquet`
- SPX spot source: `data/market_cache/yahoo__GSPC__max__1d.pkl`
- GOOGL/AMZN spot source: put-call parity from option chain (no separate underlying cache needed)
