# Quant Validation — Post HC v3 Reproduction (2026-04-25)

Scope: validate Developer-implemented SPEC-070 v2 / 068 / 069 / 071 against the SPEC contracts and produce cascade attribution for PM handoff.

Branch: `hc-reproduction-2026-04`
Anchor: tag `pre-spec070-baseline-2026-04-24` (commit `a7f938e`, baseline at `doc/baseline_2026-04-24/`)

## Commit chain

| SPEC | Commit | Status |
|---|---|---|
| SPEC-073 (BCD dead-code cleanup) | `4cbaeae` | DONE (Quant byte-identical baseline diff) |
| SPEC-070 v2 (IC long → δ0.08) | `f69b840` | DONE |
| SPEC-068 (per-strategy HV spell budget) | `127e741` | DONE |
| SPEC-069 (open_at_end reporting) | `6b68e68` | DONE |
| SPEC-071 (aftermath broken-wing V3-A) | `8b79a47` | DONE |
| SPEC-072 (frontend dual-scale) | — | BLOCKED_BY_HANDOFF |

## Headline cascade — anchored on `doc/baseline_2026-04-24/`

| Stage | Closed trades | Open at end | Total PnL | Sharpe | MaxDD |
|---|---|---|---|---|---|
| baseline_2026-04-24 (pre-070) | 59 | n/a (implicit) | 93,890.04 | 2.36 | -9,807.63 |
| baseline_post_spec070 | 59 | n/a | 79,736.85 | 2.09 | -9,391.92 |
| baseline_post_spec068 | 60 | n/a | 81,464.82 | 2.13 | -9,391.92 |
| baseline_post_spec069 | 58 | 2 | 80,765.71 | 2.14 | -9,391.92 |
| baseline_post_spec071 | 58 | 2 | 73,748.04 | 1.97 | -9,391.92 |

Notes
- 070 → 068 closed-count delta: `+1` (BPS_HV released, see SPEC-068 below)
- 068 → 069 closed-count delta: `-2` is bookkeeping only — two end-of-backtest rows are now reclassified as `open_at_end` virtual trades and excluded from metrics. PnL difference 81,464.82 vs 80,765.71 = 699.10 = $150.38 + $548.73, the two open_at_end mark-to-market values.
- 069 → 071 closed counts unchanged at 58/2; the entire -7,017.67 PnL delta is concentrated in IC_HV avg_pnl `1620.42 → 918.65` (`-701.77` × 10 trades).

## SPEC-by-SPEC validation

### SPEC-070 v2 — IC long legs to δ0.08

AC compliance:
- AC1 wing variable removed from IC branch ✓
- AC2 (spec-adjusted) — original directional prediction was wrong; real δ0.08 wings are wider, not tighter. Audit doc §3.3 also corrected (see below).
- AC3 / AC4 IC_HV n=10, IC n=13, entry-date sets identical ✓
- AC5 system trade count 59 → 59 ✓
- AC6 non-IC strategies leg-by-leg unchanged ✓
- AC7 README produced at `doc/baseline_post_spec070/README.md` ✓
- AC8 / AC9 sanity asserts + py_compile pass ✓

Cascade attribution:
- All -14,153.19 PnL hit attributable to wider IC long legs (call long 7772 → 8017, put long 6092 → 5920 at SPX≈6796). Both IC and IC_HV book values fell because wider wings increase wing cost and reduce credit collected per spread.
- MaxDD slightly improved (+415.71) because wider tails reduce the worst-case loss tail.

### SPEC-068 — Per-strategy HV spell budget

AC compliance:
- AC1 / AC2 / AC3 / AC4 type & call-site changes verified ✓
- AC5 py_compile ✓
- AC6 met under "or HV cascade" branch — released exactly 1 trade ✓
- AC7 / AC8 unit tests pass ✓

Cascade attribution:
- One trade released: `Bull Put Spread (High Vol)` 2025-05-02 → 2025-05-13, +$1,727.97
- Previously blocked because aggregate spell counter saturated at IC_HV cap=2; per-strategy dict allows BPS_HV its own budget.
- All other strategies' counts and entry dates unchanged.

### SPEC-069 — open_at_end reporting

AC compliance:
- AC1 `Trade.open_at_end: bool = False` added ✓
- AC2 two virtual rows: `Iron Condor` 2026-04-08→2026-04-24 (+$150.38) and `Bull Put Spread` 2026-04-17→2026-04-24 (+$548.73) ✓
- AC3 metrics excludes open_at_end; `n_open_at_end=2` ✓
- AC4 trade_log.csv header includes `open_at_end` column ✓
- AC5 (scope-adjusted by Developer) — backtest research view shows OPEN badge; margin page has no trade table so badge does not apply. Acceptable scope adjustment.
- AC6 research_views.json regenerated and transports `open_at_end` ✓
- AC7 closed-trade metric drift = 0 vs `baseline_post_spec068` after filtering its `end_of_backtest` rows ✓
- AC8 py_compile + unit tests pass ✓

Cascade attribution:
- No economic change. Pure reporting refactor — terminal mark-to-market rows are now explicitly tagged and excluded from headline metrics.

### SPEC-071 — Aftermath broken-wing V3-A

AC compliance:
- AC1 selector aftermath legs now `(SELL CALL 0.12, BUY CALL 0.04, SELL PUT 0.12, BUY PUT 0.08)` ✓
- AC2 non-aftermath IC_HV remains symmetric `0.16/0.08` ✓
- AC3 (spec-adjusted) — original "call wing < put wing" wording was directionally wrong; in strike space, lower call long delta `0.04` produces a *wider* call wing than put wing `0.08`. Asymmetry is real and matches the broken-wing intent at the delta level.
- AC4 non-IC and non-aftermath IC strikes leg-by-leg unchanged ✓
- AC5 attribution provided in baseline README ✓
- AC6 sanity asserts pass ✓
- AC7 py_compile + tests pass ✓
- AC8 README at `doc/baseline_post_spec071/README.md` ✓

Cascade attribution (vs `baseline_post_spec069`):
- Total PnL `-7,017.67`, fully concentrated in IC_HV: avg_pnl `1620.42 → 918.65`.
- All 10 IC_HV entry dates identical pre/post — the loss is per-trade structural, not cascade.
- IC_HV win-rate stays 100% but average win shrinks: broken-wing collects less premium per spread (short delta moved from 0.16 to 0.12, away from ATM), and the wider call wing raises hedging cost.
- **PnL drop concentration** (corrected 2026-04-25 after MC response v2): the -$7,017.67 hit is concentrated in the **2 aftermath trades only** (2026-03-09 + 2026-03-10), each losing ~$3,509. The other 8 IC_HV trades are non-aftermath and their selector legs remain `0.16/0.08`, identical to the SPEC-070 v2 baseline. Earlier wording "broad shift across 5 vol-spike windows" was wrong — the avg-PnL drop is an arithmetic artifact of dividing a 2-trade hit across n=10. Verification: `(2 × -3509) / 10 = -702 ≈ avg_pnl change 1620 → 919`.
- **HC vs MC short-delta divergence**: HC selector has had `IC_HV short=0.16 / long=0.08` hardcoded since file-creation commit `f119e99` (no `IRON_CONDOR_TARGETS` dict in HC). MC response v2 §3 asserts MC-side has `HIGH_VOL short=0.12 / long=0.06` as long-term convention. This is a real codebase divergence, not an HC anchor error. Aftermath path now agrees post-SPEC-071 (`0.12/0.04/0.12/0.08` on both sides); non-aftermath HIGH_VOL IC_HV remains divergent (HC `0.16/0.08`, MC `0.12/0.06`). PM directive 2026-04-25: do not open alignment SPEC until MC supplies historical evidence for the `0.12` convention claim.

## Errata corrected this round

1. **`doc/hc_vs_mc_v3_semantic_audit.md` §3.3** — claimed wing=100 baseline corresponded to long-call δ ≈ 0.04. Empirical SPEC-070 v2 result is the opposite: real δ0.08 sits at strikes farther OTM than wing=100, so the baseline implicit delta is roughly `0.10–0.12`. Corrected with an inline 2026-04-25 postscript; section conclusion (semantic mismatch is real, fix direction = `find_strike_for_delta(..., 0.08)`) stays valid.
2. **SPEC-070 v2 AC2 wording** — corrected by Developer at DONE time.
3. **SPEC-071 AC3 wording** — corrected by Developer at DONE time.
4. **SPEC-069 AC5 scope** — narrowed by Developer to backtest research view (margin page has no trade table). Quant: acceptable.

## Outstanding items

- **SPEC-072** unblocked 2026-04-25 by MC response v2 §2.1 (F1–F7 + 5 smoke scenarios + AC1–AC10 + live-scale rules). HC will draft `SPEC-072` from this content; target file mapping (`web/templates/backtest.html`) is HC self-decided.
- **HC ↔ MC IC_HV non-aftermath delta divergence** — open. PM has chosen NOT to open an alignment SPEC until MC provides historical evidence for the claimed `HIGH_VOL 0.12/0.06` long-term convention.
- **Q020 / Q021 numbering reconciliation** — adopt MC convention: `Q020` = MC backtest_select simplification; `Q021` = SPEC-066 second-trade semantics (formerly HC's `Q020`). HC indexes to be updated.
