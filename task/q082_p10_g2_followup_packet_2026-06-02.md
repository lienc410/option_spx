# Q082 P10 G2 Follow-up Packet — Three Computations + Revised Verdict

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer
**Re**: G2 challenges addressed; verdict flipped X → Z; ready for re-ratify
**Date**: 2026-06-02
**Window**: 24h re-read per your G2 closing offer

---

## Short version

All three challenges addressed with data. **Verdict flipped from X to Z**
exactly as you predicted. Your CV1 directional argument turned out to be
the **opposite** direction (skew steepening HURTS BCD's vega cushion,
doesn't help) — that's a finding from the skew bracket test you forced.

Plus: I logged the pattern you flagged (systematic status-quo bias in my
verdicts) to memory as `feedback_status_quo_bias_in_verdicts`. Cross-
study learning, applies to future research.

---

## The three computations

### (1) Y MA-cross counterfactual — Y is REFUTED

For each of 137 trades, computed SPX 30d MA vs 200d MA at entry. Y gate
blocks trades where 30d < 200d.

| spx_dir | total | gated | gate rate |
|---|---:|---:|---:|
| UP | 60 | 3 | 5.0% |
| FLAT | 45 | 3 | 6.7% |
| **DOWN** | **32** | **2** | **6.2%** |

Y filters 2/32 = 6.2% of DOWN windows. **Aggregate edge essentially
unchanged post-gate** (+9.71% vs +9.70% baseline). Y is useless as a
directional filter — DOWN windows that crater BCD are not predictable
from MA-cross signal at entry.

**Important learning**: this confirms a deeper truth — "point-in-time
entry signal cannot predict forward 24-day window direction" is
structural to short-DTE strategies. Trend-filter gating doesn't help. The
only useful intervention is sizing/cap (Z), not directional filtering (Y).

### (2) Block bootstrap CI (block_size=4)

| Stratum | n | point | 95% CI |
|---|---:|---:|---|
| UP | 60 | +28.49% | [+26.07%, +31.10%] |
| FLAT | 45 | +5.04% | [+2.52%, +7.02%] |
| **DOWN** | **32** | **-18.99%** | **[-22.26%, -16.47%]** |
| AGG | 137 | +9.70% | [+6.33%, +13.41%] |

You predicted "if [-15, -23] structurally clear; if [-8, -30] you know
little". Actual = **[-16.5, -22.3]** — well within "structurally clear".

DOWN drag is a tight, reliable estimate. Not noise, not estimation error.
1-in-4 BCD trades will RELIABLY underperform QQQ by 16-22pp.

### (3) Skew bracket — CV1 direction was WRONG

I added short-leg σ +5vp at exit in DOWN windows (simulates real-chain
skew steepening in stress).

| Stratum | baseline (BS-flat) | LO bracket (with skew) | shift |
|---|---:|---:|---:|
| DOWN | -18.99% | **-21.40%** | **-2.41pp DEEPER** |
| AGG | +9.70% | +9.13% | -0.57pp |

**CV1 directional claim was wrong**. You argued skew steepening helps
BCD ("short-leg hedge bigger"). Actually:
- BCD net vega = long_vega − short_vega ≈ +4/vp (positive, "cushion")
- In real skew: long σ rises +3vp, short σ rises +7vp (uneven)
- Long-leg vega gain: 6×3 = +$18
- Short-leg vega loss: 2×7 = +$14
- Net vega gain: +$4 (vs +$20 with σ flat across strikes)

Skew steepening **erodes** the vega cushion. Real DOWN drag is ≥ -19pp
(the -21pp bracket), not ≤ -15pp.

This means my P8 caveat-asymmetry defense was a **specifically wrong
argument** for the verdict. Forcing the skew test caught it. Logged
the lesson to memory.

---

## Verdict flip — X is no longer defensible, Z replaces it

### Z specification (changes from X)

| Element | X (deprecated) | Z (revised) |
|---|---|---|
| SPEC-111 cap | 60% liquid | **50% liquid** |
| Single BCD sizing | $24k debit (Q081 baseline) | **~$20k debit** (~17% smaller) |
| Concurrent alert | 75% (unchanged) | 75% (unchanged) |
| Cash floor | $30k (unchanged) | $30k (unchanged) |
| Matrix routing | unchanged | unchanged |
| Y MA-cross gate | "defensible but not preferred" | **REFUTED by data** |

### Why Z, not X

1. **DOWN drag is REAL and TIGHT**: CI [-22.3, -16.5], skew makes it -21.
   Not soft estimate; can't be wished away.
2. **Y can't gate it**: confirmed by data. Cap is the only operational
   lever.
3. **Cap @ 60% doesn't go far enough** given confirmed DOWN depth. 50%
   tightens per-trade $ exposure.
4. **Trade-off accepted**: BCD sizing reduces ~17%; per-trade PnL
   proportionally smaller; aggregate edge persists (+9.13 to +9.70
   skew-bracket); structural alpha (UP-window +28pp) intact.

### Why NOT cap = 40% or lower

- 50% allows 1 BCD at sized ~$18.5k debit (50% × $37k baseline)
- 40% would force BCD to $14.8k debit → 2x sizing reduction → losing
  meaningful exposure to the upside structural alpha
- 50% balances DOWN-protection vs UP-edge preservation

---

## Cross-references

- SPEC-111 §1.2 calibration table needs update (60% → 50%)
- SPEC-111 §AC7 backtest sizing adjustment now ~17% not ~7%
- Memory `feedback_status_quo_bias_in_verdicts` records the pattern you
  flagged (1st quant defaults to status quo on ambiguous evidence)
- Q081 P5 verdict can mark B-1 as "ratified at aggregate, refined by
  Q082 to cap = 50% via Z path"

---

## Q1-Q5 final state

| Q | G2 read | P10 response |
|---|---|---|
| Q1 methodology | RATIFY (conditional) | Accept conditional — aggregate stable, DOWN absolute not stable; skew bracket explicit in P10 |
| Q2 per-stratum stability | RATIFY (strong) | Used n=137 own stratification; not ported from 3y |
| Q3 verdict X vs Y vs Z | CHALLENGE | Computed Y → REFUTED. Computed skew → DOWN deeper, not shallower. → Verdict **Z** |
| Q4 skew sensitivity | ADD (not skip) | Done. Direction of caveat-bias was opposite of CV1 hypothesis |
| Q5 bootstrap CI | CHALLENGE (block, not skip) | Done. CI [-16.5, -22.3] on DOWN diff (tight) |

---

## Re-ratify ask

You said "补三个数后我可在 24h 内 ratify verdict 结构并 close". The three
are now done. Specifically:

1. Y refuted by data — agree to drop Y from verdict options?
2. Z (cap 50%) with the trade-offs in §D §E of P10 — ratify?
3. SPEC-111 parameter update from 60% → 50% — ratify the cross-doc impact?

On full ratify → Q082 close, SPEC-111 update, Q081 final B-1 update.
