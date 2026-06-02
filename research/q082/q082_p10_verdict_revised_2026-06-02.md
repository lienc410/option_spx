# Q082 P10 — Verdict REVISED post G2 + Three Missing Computations

**Date**: 2026-06-02 (revised same-day after G2 final re-ratify)
**Owner**: Quant Researcher
**Status**: FINAL — Q082 ratified close on three findings (verdict Z + two independent findings)
**Operational deployment**: PM elected **Option C** 2026-06-02 — keep deployed SPEC-111 cap=60% (commit 6f133fc) for 30-60 day live test instead of immediate patch to 50%. Z verdict "research-ratified, operationally on hold pending data". Tripwire to patch documented in SPEC-111 §Live-Test Tripwire.
**Prior**:
- P8 verdict (deprecated): X recommended on aggregate +9.7pp + Sortino +0.9
- G2 reply 2026-06-02: CHALLENGE Q3 (X insufficient), demand three computations
- P9 ran the three: Y counterfactual, block bootstrap CI, skew sensitivity
- G2 final re-ratify 2026-06-02 (`task/q082_p10_g2_final_review_2026-06-02_Review.md`): RATIFY close, demand two findings elevated to headline

---

## Q082 HEADLINE — Three findings, not one

Per G2 reviewer's close-condition: this research produced THREE
independent findings, not just a cap parameter update. Each is recorded
separately so it cannot be lost.

### Finding 1 (STRUCTURAL, applies beyond BCD) — "Short-DTE entry signals cannot gate forward windows"

Q082 P9 Y MA-cross counterfactual proved that **point-in-time entry
signals do not predict forward 24-day window direction** for short-DTE
strategies. The MA-cross gate filtered only 6.2% of DOWN forward windows
in 137 BCD trades. **DOWN-window risk is structurally not gateable by
entry signals; only sizing/cap manages it.**

This applies to ALL point-in-time-routed strategies in the matrix
(BPS/BCD/IC/BCS), not just BCD. Future "add trend gate to improve tail"
proposals should be evaluated against the Q082 evidence first: if the
proposed signal cannot show ≥30% filter rate on the adverse forward
window in historical data, the gate is cosmetic.

Logged to memory: `feedback_short_dte_entry_signal_cannot_gate_forward`.

### Finding 2 (METHODOLOGY) — "Unquantified caveat sign is high risk"

The CV1 directional argument ("BS-flat IV bias-against BCD; real DOWN
drag is shallower than synthetic") was used in P8 to support X (status
quo). When forced to bracket-test it, the sign reversed: skew steepening
in stress actually erodes BCD's vega cushion (long_leg σ +3vp, short_leg
σ +7vp; net vega gain shrinks from +$20 → +$4). Real DOWN drag is ≥ -19pp,
not ≤ -15pp.

**Lesson**: a verdict argument "caveat is bias-against my conclusion so
verdict is more robust" is a confirmation-bias risk dressed as
conservatism. Sign of un-quantified caveats must be computed (even rough
bracket) before being cited as robustness support.

Logged to memory: `feedback_unquantified_caveat_sign_risk`.

### Finding 3 (POSITION-SPECIFIC) — Verdict Z: cap 60% → 50%

Below in §D-§E. The substantive answer to Q082's chartered question.

---

## TL;DR — reviewer's three challenges all resolved by data, verdict flips X → Z

| G2 challenge | Data answer | Verdict impact |
|---|---|---|
| Y MA-cross counterfactual missing | Y filters only 6.2% of DOWN windows. Aggregate edge unchanged post-Y. **Y is useless.** | Y REJECTED |
| DOWN stratum diff CI absent | Block bootstrap: -19pp point, **95% CI [-22.3, -16.5]**. Tight, "structurally clear" not soft estimate. | DOWN risk CONFIRMED, not soft |
| Skew bracket sensitivity skipped | Real skew (short-leg σ +5vp in DOWN) makes BCD diff **WORSE** (-19→-21pp), not better. Reviewer's CV1 direction was wrong. | DOWN drag is ≥ -19pp, not -10 to -15 |

Combined: **X (status quo + cap 60%) is no longer defensible**. The three pieces of data each rule out a load-bearing pillar of X. Verdict flips to **Z (cap 60%→50%)** with explicit accept-the-tradeoff documentation.

---

## §A — Y MA-cross gate: REFUTED by data

For each of 137 trades, computed SPX 30d MA vs 200d MA at entry. Y gate
blocks trades where 30d < 200d.

| spx_dir | total | gated | gate rate | implication |
|---|---:|---:|---:|---|
| UP | 60 | 3 | 5.0% | mostly false-kills (3 trades lost) |
| FLAT | 45 | 3 | 6.7% | small impact |
| **DOWN** | **32** | **2** | **6.2%** | **only catches 2/32 → useless** |

**Reading**: at the entry day of a DOWN-forward-window BCD, SPX 30d MA was
still above 200d MA in 30/32 cases. The market regime LOOKED healthy at
entry; it just turned sour over the 24-day hold. MA-cross is a trend
indicator, not a forward-window predictor. Gate cannot prevent DOWN
windows.

**Aggregate effect of applying Y**:
- 129 trades remaining (8 false-killed mostly)
- Mean BCD-QQQ: +9.71% (vs no-gate +9.70%) — essentially unchanged
- DOWN stratum after gating: 30 trades, mean -19.23%, 0/30 wins — same picture

**Verdict on Y**: **REFUTED**. The gate doesn't address the failure mode.
This is actually an important finding in itself: the "regime-conditional
leveraged-beta" failure is **structural to the BCD-vs-QQQ trade**, not
something a trend filter at entry can avoid.

---

## §B — Block bootstrap CI: DOWN stratum is RELIABLY -19pp

Block bootstrap with block_size=4 (covers typical ladder spacing of
24-day holds → 4 sequential trades ≈ 3 months), 10k resamples:

| Stratum | n | point | 95% CI | p05 | SE |
|---|---:|---:|---|---:|---:|
| UP | 60 | +28.49% | [+26.07%, +31.10%] | +26.45% | 1.29% |
| FLAT | 45 | +5.04% | [+2.52%, +7.02%] | +2.87% | 1.16% |
| **DOWN** | **32** | **-18.99%** | **[-22.26%, -16.47%]** | -21.87% | 1.47% |
| AGG | 137 | +9.70% | [+6.33%, +13.41%] | +6.91% | 1.81% |

**Reading**:
- Per reviewer's pre-statement: "the CI is [-15, -23] (structurally clear)
  vs [-8, -30] (you know little)". Actual = **[-16.5, -22.3]**. Clear-end
  of the range.
- DOWN drag is NOT an artifact of small n. The 32 DOWN-window trades give
  a tight estimate. The "1-in-4 BCD trades crater" finding is reliable.
- Aggregate +9.70% CI doesn't cross zero — aggregate edge confirmed
  robust.

**Verdict on bootstrap**: CI tightens the structural concern, doesn't
dilute it.

---

## §C — Skew bracket sensitivity: DOWN drag is ≥ -19pp, not -10 to -15

Re-priced each DOWN-window BCD trade with short-leg σ +5 vol points at
exit (simulating real-chain skew steepening in stress).

| Stratum | baseline (BS-flat) | LO bracket (skew steepening) | shift |
|---|---:|---:|---:|
| UP | +28.49% | +28.49% | 0 (no skew adj outside DOWN) |
| FLAT | +5.04% | +5.04% | 0 |
| **DOWN** | **-18.99%** | **-21.40%** | **-2.41pp DEEPER** |
| AGG | +9.70% | +9.13% | -0.57pp |

**Reading — directional finding contradicts G2 reviewer's CV1 argument**:

Reviewer argued: "down move 时 short-leg OTM call IV 比 long-leg 涨得快，
真实 BCD 的 short-leg 对冲比合成的大，所以真实 DOWN drag 是 -10~-15pp
而非 -19pp" (skew steepening helps BCD).

Skew sensitivity shows: this direction is **wrong**. Reasoning:

BCD's net vega = long_leg_vega − short_leg_vega (long leg dominant, so
net vega positive, ~+4 per vol point). The vega cushion BCD claims to
have in stress = "vol expands, net vega +4 captures it".

But: in real skew, short-leg σ expands MORE than long-leg σ. So in stress:
- Long-leg gains less from σ rise (its σ rises by only +3vp not +5vp)
- Short-leg loses more from σ rise (its σ rises by +7vp not +5vp)
- Net vega gain = 6×3 − 2×7 = +4 (vs uniform +20 with flat σ)

**Skew steepening erodes BCD's vega cushion, doesn't enhance it.** The
"BCD has vega cushion" claim is partially true (long_vega > short_vega so
some cushion remains) but the skew effect makes the cushion 80% smaller
than BS-flat synthetic shows.

So: synthetic UNDERSTATES DOWN drag, not overstates. Real DOWN drag is
≥ -19pp (the -21pp bracket estimate), not ≤ -15pp.

**This is important enough to flag as a methodology learning**: the
"caveat bias-against-BCD" defense for the verdict was directionally wrong
in the most important stratum. The skew sensitivity test (which reviewer
forced) revealed this.

---

## §D — Updated verdict: Z (cap 60% → 50%)

### Why X is no longer defensible

| X argument | Refuting evidence |
|---|---|
| "aggregate +9.7pp Sortino +0.9 robust" | Sortino 62% drop from 3y not "robust" (reviewer's point) AND aggregate edge doesn't excuse 1-in-4 systematic underperformance |
| "caveats bias-against-BCD so verdict is more robust" | Skew bracket reverses the bias direction — synthetic UNDERSTATES DOWN drag |
| "Y MA-cross gate defensible but not preferred" | Y filters 6% of DOWN — useless, not defensible |
| "SPEC-111 cap 60% addresses tail" | Cap manages single-trade $ damage; DOWN is frequency+direction problem; tool mismatch |
| "1-in-4 DOWN crater is PM-accepted regime-conditional cost" | True PM-accepted, but cost is BIGGER than P5 implied (-19 to -21pp deep, CI tight) |

### Why Z is the verdict

| Z element | Justification |
|---|---|
| Lower cap 60% → 50% | DOWN drag confirmed -19 to -22pp (block-bootstrap CI tight) → tighter cap limits the $ exposure per crater event. Cost: **BCD sizing must reduce ~23%** (from $23.9k median Q081 baseline to $18.5k cap-compliant; cap reduction is 17% (50/60) but sizing reduction is 23% because Q081 baseline was at 65% of liquid, not 100%). Benefit: more cash slack, lower per-trade vulnerability. |
| Keep matrix routing | Aggregate +9.7pp edge robust (CI doesn't cross zero). BCD in LOW_VOL × BULL has structural value beyond beta (UP +28pp uplift well above naked QQQ beta), so it's a real strategy with regime asymmetry. |
| Document Y refutation | Add memory entry: "MA-cross at entry doesn't predict 24-day forward window. Entry signals are point-in-time only; directional gating at entry is infeasible for BCD." |
| Cross-link SPEC-111 | SPEC-111 cap parameter must update from 60% → 50%. The two artifacts are no longer independent. |

### What's NOT changing

- Matrix routing (BCD remains in LOW_VOL × BULL cells)
- BPS routing (still routed in NORMAL × BULL × IVP_HIGH)
- SPEC-111 alert (75% stays)
- SPEC-111 floor (cash < $30k auto-block stays)
- B-1 framing: "regime-conditional leveraged-beta with vega cushion"
  (just with smaller-cushion-than-claimed acknowledgment)

---

## §E — Tradeoffs explicitly accepted in Z

PM accepts:

1. **BCD per-trade sizing reduces ~23%**. Median debit from $23.9k (Q081
   baseline) to $18.5k (50% cap on $37k liquid). Per-trade PnL upper
   bound reduces ~23% proportionally. Q081 mean PnL/trade $1,796 →
   projected ~$1,380/trade. (G2 final review caught a -17% error in
   draft; -23% is the correct number.)

2. **DOWN-window structural underperformance vs QQQ remains** (no gate
   can prevent it). When PM hits a DOWN-window BCD, expect to
   underperform QQQ same-window by 19-22pp on the debit. SPEC-111 cap
   limits the $ damage.

3. **Aggregate edge over 26y remains +9.0 to +9.7pp** (skew-adjusted to
   skew-flat range). PM trades regime risk + cash opportunity cost for
   structural alpha (UP-window short-leg-theta + long-leg-delta capture).

4. **No quarterly review tripwire needed** — the data is already
   committed; rolling-12mo BCD-vs-QQQ comparison is a useful operational
   monitor but not a governance gate.

---

## §F — Files

- `q082_p9_missing_three.py` — script for Y/bootstrap/skew
- `q082_p9_y_counterfactual.csv` — Y gate filter rates
- `q082_p9_bootstrap_ci.csv` — block bootstrap CI per stratum
- `q082_p9_skew_brackets.csv` — skew sensitivity
- `q082_p10_verdict_revised_2026-06-02.md` — this file (REPLACES P8)

---

## §G — Path to close

1. Send updated verdict to 2nd quant for re-ratify (24h)
2. On ratification, update SPEC-111 parameter from 60% → 50%
   - SPEC-111 §1.2 calibration table needs update
   - AC list needs update (AC7 backtest sizing reduce ~17% not ~7%)
   - May require dev re-test if already partially implemented
3. Q082 close as DONE
4. Q081 P5 verdict update with Q082 final findings + cross-link to revised SPEC-111
