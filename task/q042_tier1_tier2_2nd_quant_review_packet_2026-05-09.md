# Q042 Directional Drawdown Overlay — 2nd Quant Review Packet (Tier 1 + Tier 2)

- **Date**: 2026-05-09
- **Prepared by**: Quant Researcher (Claude)
- **Audience**: 2nd Quant (ChatGPT)
- **Topic**: New directional research branch — long-premium overlay on SPX drawdowns
- **Span**: Tier 1 feasibility scan → Tier 2 design study → recommended Tier 3 / DRAFT Spec parameter pack
- **Stage**: Pre-Spec drafting; Quant requests stage review before authoring DRAFT Spec

---

## 1. Review Request

PM promoted Q042 from "future research seed" to active research on 2026-05-09. Tier 1 (3 feasibility questions) and Tier 2 (3-phase design study) both PASSED. PM has approved Tier 3 promotion. Quant requests **stage review before DRAFT Spec drafting** to confirm:

> Is the Tier 1 → Tier 2 chain methodologically sound, are the recommended winner parameters well-grounded, and is anything missing before we hand a DRAFT Spec to PM and Developer?

We are **not** asking:
- to reopen the Tier 1 verdict (PM accepted, Tier 2 was authorised on it)
- to redesign the trigger universe from scratch (Tier 2 P1 already grid-scanned 6 dd × 5 confirmation)
- to challenge the use of BS-flat-VIX + skew haircut (PM authorised this in scope decision D1; live IV-surface is deferred to Tier 3)

We **are** asking:
- Is the **rank order of structures** in P2 (call spread DTE 30 > LEAP > ratio) defensible given pricing simplifications?
- Is the **BP-stacking-gate-is-redundant** conclusion in P3 robust, or are we missing a regime where it fires?
- Is the recommended **winner config (dd12 + MA50 reclaim + ATM/+5% spread DTE 30, 1% account / entry, 20% account cap)** reasonable, or should the 6 Tier 3 unknowns block this?
- Is anything **structurally absent** from the analysis (a known failure mode we didn't test, a hidden regime we didn't break out)?

Specific questions Q1–Q6 in §6 below.

---

## 2. Top-Level PM Objective (Unchanged)

PM standing objective remains:

> reasonably maximize account-level ROE

with explicit attention to drawdown control, margin stress, hidden concentration, and opportunity cost. Q042 is being evaluated as an additional **long-premium directional overlay** on top of the existing **non-directional short-premium income** stack. The two are vega-opposite by construction (overlay long vega, main strategy short vega).

---

## 3. Strategy Restatement

### Core idea

After SPX prints a drawdown of meaningful depth from a recent high and shows a technical reclaim, buy a call spread to capture forward upside. The thesis is that drawdowns of ≥10-15% historically have positive-skewed forward returns (mean-reversion + post-stress recovery), and a defined-risk call spread captures the upside efficiently per unit of capital.

### Trigger (winner config)

```
condition_1: SPX close ≤ 60-day rolling high × 0.88   (dd60 ≥ 12%)
condition_2: within 30 trading days post-condition_1, first day where
             SPX close > 50-day moving average        (MA50 reclaim)
re-arm:      after SPX revisits the 60-day high (resets)
```

Sample: **n=41 trades over 2007-01 → 2026-05** (19y, ≈ 2.2 trades / year).

### Position structure (winner config)

```
Long  call: ATM (K = entry SPX close)
Short call: K = entry SPX close × 1.05            (5% OTM)
DTE:        30 calendar days
Hold:       to expiry (MVP — Tier 4 to test 50% TP / 50% stop)
```

### Sizing

- **1% account per entry** (start small; conservative Tier 3 baseline)
- **20% account absolute cap** for Q042 sleeve
- **Joint gate** (governance backstop, currently inert):
  `q042_cap = min(20%, max(0%, 60% − main_strategy_bp%))`

### Expected edge source (per PnL decomposition framework)

- **Primary**: directional alpha — conditional positive skew in forward 30-day return after dd12+reclaim trigger
- **Secondary**: vol crush — entry typically during VIX-elevated period (dd12 trigger ↔ HIGH_VOL); IV mean reversion benefits the long ATM call relative to deep-OTM expiry
- **NOT** the source: time decay (we are long premium; theta is a cost, not a profit driver)

### What this is NOT

- NOT a short-premium strategy. **§6.1 short-premium standard checks in REVIEW_TEMPLATE do not apply** except where noted (HIGH_VOL aggregate scale annotation).
- NOT a hedge for the main strategy. Vega-opposite by happenstance, not designed as risk offset.
- NOT a market-timing system. The trigger is rare (~2/year) and reactive, not predictive.

---

## 4. Tier 1 Summary

**Method**: SPX/VIX daily 2007-2026 (n=4,868). Three feasibility questions answered with one-line conclusion + supporting numbers.

### Q1 — Drawdown depth vs forward return

dd60 ≥ 10% from 60-day high produces clear positive skew in 12-month forward returns:

| Trigger | n | 3m median | 6m median | 12m median | 12m positive% |
|---|---:|---:|---:|---:|---:|
| dd60 ≥ 10% (naive) | 480 | +5.2% | +11.7% | +21.2% | 81.7% |
| dd60 ≥ 15% (naive) | 192 | +8.2% | +15.9% | **+29.8%** | **97.9%** |
| **unconditional baseline** | 4,616 | +3.6% | +6.3% | +12.7% | 78.8% |

dd5 marginal (close to baseline); dd20 has 3-mo "falling-knife" risk (median −7.2%) that resolves by 12m (100% positive).

### Q2 — Option structure economics

ATM/+5% **call spread DTE 90** is the only structure clearing main-strategy baseline ($4.85 / $1000 BP-day, *(research)* scale):

| Structure (10% dd60 trigger, n=480) | median $/$100BP/day | vs V_A baseline |
|---|---:|---|
| LEAP ATM | +$0.088 | 18% of baseline |
| LEAP Δ0.35 | -$0.274 | structurally negative |
| **Call spread (ATM/+5%, DTE 90)** | **+$1.486** | **3.1× baseline** |

LEAP Δ0.35 fails because OTM strike + skew haircut + IV mean-reversion → typically expires worthless (19% win rate, median −100% premium).

### Q3 — Regime overlap

dd60 ≥ 10% triggers occur 98.5% inside HIGH_VOL (VIX>22) vs 27.9% baseline. **Tier 1 framing**: BP-stacking risk is severe.

(See §5.3 for the **revision** of this conclusion in Tier 2.)

### Tier 1 verdict

PASS (2/3 questions clear edge). Promoted to Tier 2.

---

## 5. Tier 2 Summary

**Method**: 3-phase design study. PM scope decisions (D1: BS-flat-VIX + skew haircut for P2; D2: 3y trade log + 19y baseline backtest for P3; D3: Tier 2 memo only as deliverable).

### 5.1 Tier 2 P1 — Trigger grid

6 dd thresholds × 5 confirmations × 3 forward windows × OOS split (2007-18 / 2019-26).

**Top configs by 12-mo positive rate × log(n)**:

| Trigger | n | 3m median | 6m positive% | 12m median | 12m positive% |
|---|---:|---:|---:|---:|---:|
| dd15 + naive | 192 | +8.2% | 83.3% | +29.8% | **97.9%** |
| dd15 + vix_decline | 132 | +7.9% | 84.8% | +30.8% | 98.5% |
| **dd12 + MA50 reclaim** | **41** | +11.0% | 90.2% | **+42.7%** | 92.7% |
| dd10 + MA50 reclaim | 56 | +8.3% | 89.3% | +25.2% | 92.9% |

OOS robust: dd12+MA50_reclaim 88.2% (2007-2018, n=17) / 95.8% (2019-2026, n=24).

**Dropped**: MA200 reclaim (n collapses); term_normalize (unreliable in OOS); dd5/dd8 (marginal vs unconditional); dd20 (3-mo falling-knife risk).

### 5.2 Tier 2 P2 — Structure grid (BS + skew haircut)

**Pricing assumptions**:
- BS with σ = max(VIX/100, 10% floor)
- **Term-structure multiplier** on σ: DTE ≤ 45 → 1.10; DTE 46-120 → 1.00; DTE > 120 → 0.95
- **Skew multiplier** on σ (linear in moneyness K/S): ATM 1.00; +5% K 0.93; +10% K 0.85; -5% K 1.07; -10% K 1.15
- r = 4%, hold to expiry

**Top-5 by `$ / $100 BP / day` (median, full 2007-2026 sample)**:

| Trigger | Structure | n | median $/$100BP/day | win% | worst |
|---|---|---:|---:|---:|---:|
| **dd12 + MA50 reclaim** | **spread ATM/+5% DTE 30** | 41 | **+$3.525** | **73.2%** | -$100 |
| dd12 + MA50 reclaim | spread ATM/+3% DTE 30 | 41 | +$3.262 | 75.6% | -$100 |
| dd10 + MA50 reclaim | spread ATM/+3% DTE 30 | 56 | +$3.281 | 71.4% | -$100 |
| dd15 naive | spread ATM/+5% DTE 30 | 192 | +$2.772 | 59.4% | -$100 |
| dd10 + MA50 reclaim | spread ATM/+5% DTE 30 | 56 | +$2.599 | 69.6% | -$100 |

vs V_A baseline `$0.485 / $100 BP-day` *(research scale)* — winner is **~7.3× baseline raw** (before tx-cost haircut).

**Non-spread structures (FYI — all weaker)**:

| Structure | Best $/$100BP/day | Note |
|---|---:|---|
| LEAP ATM (DTE 365) | +$0.42 (dd12+MA50) | 90% win rate but BP-day denom too large |
| LEAP Δ0.30 | +$0.12 (dd12+MA50) | OTM + skew + IV mean-reversion = barely positive |
| Long ATM call DTE 120 | +$0.79 (dd12+MA50) | 49% win rate path-dependent |
| Ratio 1×2 (long ATM / short 2× +5%) | +$0.18 best | Worst-case truncated to ~−$30; **BP proxy fragile** (20% notional × 2 — not live PM margin) |

### 5.3 Tier 2 P3 — BP-stacking gate (Tier 1 Q3 revision)

**Tier 1 Q3 framing was directionally wrong**:

> Tier 1: "98.5% HIGH_VOL overlap → BP collision risk severe."
> **Tier 2 actual**: Main strategy by design **de-grosses in HIGH_VOL** (BPS_HV / IC_HV are reduced-BP variants). 98% regime overlap is real, but BP usage in those regimes is *low*, not high.

**Method**: Ran 19y main-strategy baseline backtest (`research/q042/q042_run_19y_baseline.py`, 282 trades, 4,868 daily portfolio rows). Aligned Q042 trigger dates with daily BP envelope.

**19y main-strategy BP envelope** *(research scale)*:

| Metric | All days | HIGH_VOL only | LOW_VOL only |
|---|---:|---:|---:|
| Mean bp_pct | 6.3% | 9.3% | 5.7% |
| Median bp_pct | 4.3% | 4.7% | 4.8% |
| p95 bp_pct | 23.6% | — | — |
| Max bp_pct | 53.2% (2007-08) | 53.2% | 22.8% |

By era: 2007-2008 elevated (mean 15-20%); 2009-2016 moderate (5-13%); 2017-2026 very low (1-4% mean). Strategy parameter evolution explains the regime shift.

**Main strategy BP at Q042 trigger dates**:

| Trigger | n | main_bp_pct median | p75 | max |
|---|---:|---:|---:|---:|
| dd10 + MA50 reclaim | 56 | 2.8% | 3.5% | 34.3% |
| dd12 + MA50 reclaim | 41 | 2.8% | 2.8% | 31.1% |
| dd15 naive | 192 | 0.0% | 3.6% | 36.5% |

**Gate firing rate (default `min(20%, max(0, 60% − main_bp%))`)**:

| Trigger | Gate variant | blocked / n | combined peak BP |
|---|---|---:|---:|
| dd12 + MA50 reclaim | default | 0/41 | 51.1% |
| dd12 + MA50 reclaim | conservative (15%/50%) | 0/41 | 46.1% |
| dd12 + MA50 reclaim | aggressive (25%/70%) | 0/41 | 56.1% |
| dd15 naive | default | 0/192 | 56.5% |

**Gate fire rate = 0% across all 19 years on all gate variants.**

**Hold-period collision (winner config 30-day hold)**:
- combined peak BP during hold: median 22.8%, p75 35.6%, max 67.2%
- 0/41 days where combined > 80% account
- 0/41 days where combined > 100% account

**Gate recommendation**: Keep default gate as governance backstop (regime-conditional on main-strategy parameters; if Q021 V_D/V_J ever promote, gate becomes load-bearing). Current era: gate is functionally inert.

---

## 6. Specific Review Questions

### Q1 — P1 trigger grid: dd12 vs dd15 finalist choice

I picked **dd12 + MA50 reclaim** as the winner for P2/P3 because of:
- Highest 12m median (+42.7%) and highest **conditional** edge (vs unconditional baseline +12.7%, that's +30pp)
- Smaller sample (n=41) than dd15 naive (n=192) but cleaner because of the reclaim filter
- OOS robust (88% / 96%)

**Question to 2nd Quant**: Is this the right trade-off? An alternative argument:
- dd15 naive has 4.7× the sample (192 vs 41) → tighter confidence interval on win rate
- dd15 naive 12m positive 97.9% > dd12+reclaim 92.7%
- dd15 naive doesn't require the 30-day reclaim wait (zero "missed entry" risk)

Should the winner be **dd15 naive** rather than dd12+MA50_reclaim, or is dd12+reclaim genuinely superior?

### Q2 — P2 structure: short-DTE bias

The P2 results are dominated by short-DTE structures because the BP-day denominator scales with DTE. spread DTE 30 wins on $/BP-day even though spread DTE 90 had better full-period absolute PnL in Tier 1.

**Question to 2nd Quant**:
1. Is `$/BP-day` the right metric to optimize for an overlay sleeve, or should I be looking at `$/trade` or `risk-adjusted ROE on full-period`?
2. The DTE 30 structure has a tighter "expiration window" — does this introduce hidden timing risk that the BP-day denominator masks? (E.g., if entry was 1-day early relative to the bottom, the 30-day window may not catch the recovery; a DTE 90/120 window would.)
3. Should the winner default to **DTE 60** instead of DTE 30, accepting a lower $/BP-day for more path tolerance?

### Q3 — P2 ratio 1×2: BP proxy fragility

I assigned ratio 1×2 a BP proxy of `0.20 × S × 2` (20% notional per naked short × 2 contracts). This is a guess at PM naked-call margin during average vol. The real PM margin during VIX>30 is likely 30-40% notional per short (and rises with realized loss-on-position).

**Question to 2nd Quant**: Is the ratio 1×2 — with truncated downside (worst -$30 vs spread's -$100) — a structurally better candidate that I'm under-weighting due to BP proxy? Or is the undefined-upside risk (short 2× OTM calls in a runaway rally) a categorical disqualifier that should keep ratio out of the finalist set regardless of BP?

### Q4 — P3 BP gate: regime-conditional fragility

The gate fires 0% in 19 years, but the conclusion depends on main strategy operating in the current low-BP-during-HIGH_VOL pattern. If Q021 V_D / V_J / V_G (sizing-up variants) ever promote, the BP envelope shifts up and the gate becomes load-bearing.

**Question to 2nd Quant**: Should the gate be more **structurally conservative** (e.g., max 10% account for Q042 instead of 20%), since:
- The "gate is inert" finding rests on a parameter set that is itself in active research (Q021 not yet finally resolved)?
- 20% account in a long-premium overlay is a lot of capital exposed to -100% loss tail?
- The expected annual contribution at 1% per entry × ~2 trades / yr = ~2% account base sizing — we don't actually need a 20% cap to capture this; 5-10% would be sufficient.

Or is the 20% cap right because it allows scaling up if Tier 4 finds a bigger edge?

### Q5 — Tier 3 unknowns: are 6 enough?

I listed 6 unknowns to resolve in Tier 3 / Spec drafting:

1. Live SPX chain pricing
2. Ratio 1×2 PM margin reality check
3. Re-trigger spacing rule
4. Exit rule MVP test (held-to-expiry vs 50% TP / stop)
5. SPX vs XSP symbol selection
6. Account-scale activation threshold

**Question to 2nd Quant**: Is anything **structurally absent** that should be a 7th unknown? Specifically:
- Tax / wash-sale considerations? (Repeated triggers in same calendar window could create tax artifacts.)
- Entry-time-of-day specification? (Daily close trigger but execution at next open / next close is a non-trivial choice.)
- Earnings / FOMC blackout? (Not in current trigger logic.)
- Correlation with main-strategy concurrent trades? (Q042 entry day might also be a main-strategy entry day; combined directional bias?)
- "What if the trigger fires on day T and SPX gaps down 10% on day T+1 before we execute" — slippage risk?

### Q6 — Hidden failure mode

The strategy's failure mode set:
- Trigger fires, then SPX continues down (long ATM call eaten by realised vol, short OTM expires worthless): **-$100 / $100 BP**, accounted in raw numbers
- Trigger fires, then sideways grinding: long ATM theta decay, short expires worthless: **-$30 to -$100**, accounted
- Trigger fires, then SPX rallies past +5% short strike before expiry: capped at **max gain ≈ +$130-150 / $100 BP**, accounted
- Trigger fires during a structurally-different regime (e.g., 1929-style depression, secular bear): **0/41 historical samples**, untested
- Trigger fires when broker margin is constrained for unrelated reasons (e.g., main strategy BP usage is at era-2007 levels): **gate fires**, Q042 entry blocked → "missed alpha" risk, opportunity cost only
- Trigger fires near earnings season for major SPX components: **not screened**, possible vol-event interaction not modeled

**Question to 2nd Quant**: Is there a **failure mode I missed entirely**? Particularly: any path where this strategy produces a loss substantially worse than -100% premium (e.g., margin call cascade, gap risk against the long leg, dividend assignment on short leg in the unlikely case of deep ITM at expiry, etc.)?

---

## 7. REVIEW_TEMPLATE.md §6.1 Applicability

Per REVIEW_TEMPLATE.md §6.1 short-premium standard checks: **this strategy is long premium** (long call spread = net debit paid; max loss = full debit). The 5 short-premium checks (stress-capital basis, IV expansion test, stop methodology, scale dependence, execution-drift sensitivity) are designed for short-vega exposures and do not directly apply.

**However**, the following sub-items still apply as analogues:

| Check | Applicability | Status |
|---|---|---|
| Stress-capital basis (Principle 3) | **Adapted**: instead of stress BP under vol expansion, "what's the worst-case account drawdown if 5 consecutive trades all hit -100%?" | **Open** for 2nd Quant — back-of-envelope: 5 × 1% account × -100% = -5% account. Acceptable. Tier 3 should make this explicit. |
| IV expansion stress test (Principle 1) | **Inverted**: this strategy benefits from IV expansion (long premium). Worth confirming "no hidden short-vega leg" | **Confirmed** — pure long debit spread; vega ≥ 0 always |
| Stop methodology (Principle 2) | **Applies**: held-to-expiry vs 50% loss stop — this is Tier 3 unknown #4 | **Open**, deferred to Tier 3 |
| Scale dependence (Principle 5) | **Applies**: needs account-size threshold for sleeve to make sense | **Open** as Tier 3 unknown #6 |
| Execution-drift sensitivity (Principle 4) | **Applies if the entry is human-alert-triggered**, but Q042 trigger is daily-close-mechanical → arguably auto-close exemption applies | **Need PM/2nd Quant to confirm exemption rationale** |
| **HIGH_VOL aggregate scale annotation** (Q029 / SPEC-072.1) | **Applies** — this packet's 19y BP envelope and V_A baseline references all use research scale | **Annotated** in §5.2 / §5.3 with `(research)` callouts; live execution would apply SPEC-072 0.1× HV factor |

---

## 8. Caveats Explicitly Disclosed

1. **No transaction costs** in P2 numbers. Estimated 1.6-4% per-trade haircut for SPX/SPXW; doesn't reverse winner ranking but compresses headroom.
2. **No live IV surface**. P2 uses BS + linear-skew haircut + term-structure multiplier — direction of bias is mixed (skew haircut likely under-states real call skew haircut in HIGH_VOL).
3. **Sample sizes**: dd12+MA50_reclaim n=41 / 19y; 95% CI on 73% win rate roughly ±10pp. Validate post-spec OOS.
4. **19y baseline backtest uses current main-strategy parameter set**. P3 BP gate conclusion is regime-conditional on this set.
5. **dd20 falling-knife pattern** dropped from finalist. Tier 4 could revisit with delay.
6. **Tier 1 Q3 framing was directionally wrong**, corrected in Tier 2 P3.
7. **Ratio 1×2 BP proxy uncertain** (Tier 3 must use live PM margin numbers).
8. **No earnings / FOMC / dividend blackout** screen in trigger logic.
9. **No tax / wash-sale** consideration at sleeve level.
10. **All numbers reference 2007-2026 single backtest history** — sample contains 3 distinct vol regimes (GFC, post-2010 grind, COVID-era) but no pre-2007 regime (e.g., 1987, 1998 LTCM, 2000-2002 dot-com).

---

## 9. Constraints on Reviewer Output

Per REVIEW_TEMPLATE.md "Reviewer → SPEC 写回规则":

- Do **NOT** propose code-level or implementation-specific changes
- Focus on **strategy logic, risk exposure, and failure modes**
- Output as `q042_tier1_tier2_2nd_quant_review_packet_2026-05-09_Review.md` in `task/`

---

## 10. Inputs / Outputs Index

```
research/q042/
├── q042_tier1_feasibility.py            # Tier 1 script
├── q042_tier1_memo_2026-05-09.md        # Tier 1 memo (full)
├── q042_tier2_p1_trigger_grid.py        # Tier 2 P1
├── p1_grid_full.csv                     # P1 output (full sample)
├── p1_grid_2007_2018.csv                # P1 OOS H1
├── p1_grid_2019_2026.csv                # P1 OOS H2
├── q042_tier2_p2_structure_grid.py      # Tier 2 P2
├── p2_structure_grid.csv                # P2 output
├── q042_run_19y_baseline.py             # 19y main-strategy baseline runner
├── baseline_19y_bp_daily.csv            # 19y daily BP envelope (4,868 rows)
├── baseline_19y_trades.csv              # 19y trade log (282 trades)
├── q042_tier2_p3_bp_gate.py             # Tier 2 P3
├── p3_bp_gate.csv                       # P3 gate firing-rate output
├── p3_hold_collision.csv                # P3 hold-period collision output
└── q042_tier2_memo_2026-05-09.md        # Tier 2 memo (full)

doc/
└── q042_directional_overlay_seed_memo_2026-05-04.md   # Seed memo
```

**RESEARCH_LOG entries**: R-20260509-11 (Tier 1), R-20260509-12 (Tier 2)
**Open Question entry**: Q042 (current state: Tier 2 DONE, awaiting Tier 3 / DRAFT Spec)

---

## 11. Decision-Of-Record on Reviewer Concerns

Whatever 2nd Quant returns will be incorporated into the DRAFT Spec at Tier 3. If 2nd Quant flags REVISE on any specific question, Quant Researcher will:

1. Revise the relevant Tier 2 conclusion in `research/q042/q042_tier2_memo_2026-05-09.md` with a `## 2nd-Quant-revised` section
2. Re-run any analysis required (Tier 3 has not started — no rework lost)
3. Reflect updated parameters in the eventual DRAFT Spec

If 2nd Quant returns APPROVE / minor REVISE, Tier 3 / DRAFT Spec drafting proceeds.
