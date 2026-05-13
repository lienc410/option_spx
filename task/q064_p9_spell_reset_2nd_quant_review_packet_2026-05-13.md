# Q064 Phase 9 — Spell Reset Mechanism Sensitivity — 2nd Quant Review Packet

- **Date**: 2026-05-13
- **Prepared by**: Quant Researcher (Claude)
- **Audience**: 2nd Quant (ChatGPT)
- **Topic**: Spell reset mechanism (VIX_low_reset hysteresis / VIX_high_reset / spell_age_cap) sensitivity
- **Stage**: Pre-SPEC drafting; PM requested broader spell-gate study after P8 (`max_trades_per_spell` 2→3) approved with watchlist
- **Prior reviews**:
  - 2026-05-12 P5+Routing review: APPROVE α (retain V3-A as aftermath bypass)
  - 2026-05-13 P8 review: APPROVE WITH WATCHLIST (`max_trades_per_spell` 2→3)

---

## 1. Review Request

After P8 raised `max_trades_per_spell: 2→3`, PM asked: "the rest of the spell reset mechanism (VIX<22 reset, VIX≥35 reset, age_cap=30d) — are these all reasonable?". P9 tests 12 variants (3 dimensions × multiple values + 2 combos).

**Findings**:
- 9a hysteresis (1-day → 3/5 days): **all REJECT** (counter-intuitive — alpha drops 22-30%)
- 9b no high reset: **REJECT** (alpha drops $16k)
- 9c age_cap (30 → 60/90/180/∞): **only age_cap≥90d marginal PASS** (+1 trade, +$1.3k)
- 9d combos: **all REJECT**

**We are asking**:
- Is the P9 methodology sound (engine replay + capture-via-selector-wrapper)?
- Is the "broader-population" framing (n=40 in P9 vs n=33 in P6/P8) valid for spell-gate analysis?
- Are the 3 counter-intuitive findings (hysteresis tightens, high-reset valuable, age_cap nearly optimal) credible?
- Given P8 already approved max=3 and P9 finds spell_age_cap=90 as the only other Pareto improvement: should SPEC bundle both (β) or just keep P8 (α)?

**We are not asking**:
- to reopen P8 verdict (already approved)
- to test new spell gate mechanisms not in P9 scope

Specific questions Q1–Q6 in §6.

---

## 2. Method Recap

### 2.1 Engine instrumentation

Monkey-patched 2 functions in `backtest/engine.py`:
- `_update_hv_spell_state` — controls when spell starts/ends/resets
- `_block_hv_spell_entry` — controls age_cap check (max_trades_per_spell kept at baseline)

Parameters varied:
- **`low_reset_hysteresis_days`**: 1 (baseline, single-day reset) / 3 / 5
- **`high_reset_enabled`**: True (baseline) / False
- **`age_cap`**: 30 (baseline) / 15 / 60 / 90 / 180 / 9999

`max_trades_per_spell` held constant at 2 across all P9 variants (P8 already approved 2→3 separately).

### 2.2 Trade identification

Captured trades via wrapper filter:
```python
regime == HIGH_VOL AND iv_signal == HIGH AND trend in (BEARISH, NEUTRAL)
AND strategy == "Iron Condor (High Vol)"
```

**Note**: filter does NOT include `is_aftermath()` check. This is intentional — spell gate applies to ALL HV strategies, not just V3-A aftermath subset. P9 baseline thus has **40 IC_HV trades** vs P6's 33 V3-A trades. The 7-trade difference is SPEC-060 normal IC_HV (BEARISH/NEUTRAL+IV_HIGH cells outside aftermath windows).

For spell-gate sensitivity, broader population is correct denominator. We confirm with 2nd Quant in Q2.

### 2.3 Sample

- 2009-01-01 → 2025-06-30 (16.5y)
- Engine replay (not BS sim), same as P6/P7/P8
- Account size: $150,000

---

## 3. Full Results Table

| Variant | n | WR% | Total | Worst | Δ Total | Pareto |
|---|---|---|---|---|---|---|
| **9a/V0 baseline** (1d / high / 30d) | 40 | 90.0% | **$53,776** | -$5,041 | (ref) | — |
| 9a/V1 hyst 3d | 31 | 87.1% | $33,078 | -$5,041 | **-$20,698** | ❌ |
| 9a/V2 hyst 5d | 28 | 85.7% | $28,560 | -$5,041 | **-$25,216** | ❌ |
| 9a/V4 no-op (control) | 40 | 90.0% | $53,776 | -$5,041 | $0 | tied |
| 9b/V1 no high reset | 31 | 87.1% | $37,433 | -$5,041 | -$16,344 | ❌ |
| 9c/V1 age 15d | 40 | 90.0% | $53,776 | -$5,041 | $0 | tied |
| 9c/V2 age 60d | 40 | 90.0% | $53,776 | -$5,041 | $0 | tied |
| **9c/V3 age 90d** | **41** | **90.2%** | **$55,107** | -$5,041 | **+$1,330** | **✅** |
| 9c/V4 age 180d | 41 | 90.2% | $55,107 | -$5,041 | +$1,330 | ✅ |
| 9c/V5 age ∞ | 41 | 90.2% | $55,107 | -$5,041 | +$1,330 | ✅ |
| 9d/combo hyst3 + age60 | 34 | 88.2% | $41,290 | -$5,041 | -$12,486 | ❌ |
| 9d/combo hyst3 + age90 + no_high | 27 | 85.2% | $27,582 | -$5,041 | -$26,195 | ❌ |

### 3.1 Pareto winners

Only `9c V3-V5` (age_cap ≥ 90d) Pareto improve baseline. All three give same +1 trade — they're equivalent because the binding age was ≥30d and ≤90d for that specific trade.

### 3.2 The +1 unblocked trade

```
entry: 2022-10-04
exit:  2022-10-27 (50% profit)
pnl:   +$1,330
```

This is in the 2022 long-spell context P8 packet flagged. Confirms 2022 spell did have age_cap-binding window, but only 1 trade actually releases (not P8 packet's predicted "5 of 6").

### 3.3 Worst trade unchanged across all 12 variants

`worst = -$5,041` for every variant. This is a non-V3-A IC_HV trade (V3-A subset's worst was -$2,016). The fact that no variant changes this number indicates none of the spell gate parameters affect tail trade selection — they only affect entry frequency.

---

## 4. Three Counter-Intuitive Findings (need 2nd Quant validation)

### 4.1 Hysteresis tightens, not loosens

Pre-test prediction: hysteresis would prevent "spurious resets" when VIX briefly dips below 22, **preserving** trade opportunity continuity.

**Empirical result**: 3-day hysteresis LOSES 9 trades / -$20.7k. 5-day hysteresis loses 12 trades / -$25.2k.

**Mechanism interpretation**: When VIX briefly dips below 22 and re-enters, current production behavior RESETS spell → `trade_count` clears → next entry allowed (subject to other gates). Hysteresis prevents this reset → spell persists → existing `trade_count=2` carries over → new entries blocked.

The "spurious resets" are actually high-value: they enable trades in same vol regime that would otherwise be capped by max_trades_per_spell.

**Quant calibration**: my pre-test prediction was wrong in direction. P9 forces revision: VIX boundary oscillation around 22 is NOT noise — it's valuable trade-opportunity multiplier.

### 4.2 High reset (VIX≥35 → spell reset) is non-redundant

Pre-test prediction: since selector already `reduce_wait` when VIX≥35 (EXTREME_VOL gate), high-side spell reset should be redundant.

**Empirical result**: removing high reset LOSES 9 trades / -$16.3k.

**Mechanism interpretation**: when VIX spikes through 35 and recovers, the post-spike recovery window often has high-quality V3-A opportunities. Pre-spike spell may have already used `trade_count=2`; high reset gives a fresh slate for recovery window. Without high reset, recovery entries are blocked by accumulated pre-spike count.

### 4.3 spell_age_cap is nearly optimal at 30d

Pre-test prediction (P8 packet hint): "5 of 6 blocked 2022 windows are due to spell_age_cap → relaxing to 60-90d would release 5+ trades, ~$5-10k".

**Empirical result**: only 1 trade released (2022-10-04, +$1,330). Going from 90 to 180 to ∞ releases NO additional trades.

**Mechanism interpretation**: 2022 long spell did get briefly reset internally (likely VIX dipped below 22 and recovered), creating multiple shorter spells rather than one 9-month spell. So age_cap=30d on each sub-spell wasn't binding for most 2022 windows. Other gates (concurrent IC_HV limit, selector path conditions) were the dominant blockers.

---

## 5. Implications for SPEC-100 (or any spell-gate-related SPEC)

### 5.1 What's confirmed safe to change

| Param | Current | Recommended | Source | Δ alpha |
|---|---|---|---|---|
| `max_trades_per_spell` | 2 | **3** | P8 | +$5,424 / 19y |
| `spell_age_cap` | 30 | **90** | P9 9c | +$1,330 / 19y |

Combined: +$6,754 / 19y = ~$355/yr on $150k account.

### 5.2 What's confirmed locked (do not change)

| Param | Current | Do not change | Source |
|---|---|---|---|
| `low_reset_hysteresis_days` | 1 (single-day) | Keep at 1 | P9 9a — Pareto fail |
| `high_reset_enabled` | True (VIX≥35 resets) | Keep True | P9 9b — Pareto fail |
| `IC_HV_MAX_CONCURRENT` | 2 | (not tested in P9) | Untested |
| spell-internal V3-A vs SPEC-060 mix | as-is | (out of P9 scope) | Q064 closed |

### 5.3 Decision options

| Option | Content | Quant lean |
|---|---|---|
| α | Implement P8 only: `max_trades_per_spell: 2→3` | Adopt; defer age_cap to live trigger |
| **β** | Implement P8 + P9 9c: `max_trades_per_spell: 2→3` AND `spell_age_cap: 30→90` | **Recommend** (both Pareto-verified; single SPEC) |
| γ | Conservative: keep all parameters as-is, don't even implement P8 | Reject (P8 evidence is clean) |

---

## 6. Specific Review Questions

**Q1** — **P9 methodology**: Is engine replay + selector-wrapper trade capture a valid method for measuring spell-gate parameter sensitivity? Specifically, the monkey-patching of `_update_hv_spell_state` and `_block_hv_spell_entry` — is there a risk that other engine state leaks across variant runs?

**Q2** — **Broader population framing**: P9 baseline n=40 includes 7 SPEC-060 normal IC_HV trades that P6/P8 framing excluded (33 V3-A only). For spell-gate analysis, is n=40 the correct denominator (because spell gate doesn't distinguish V3-A vs SPEC-060 in HV_STRATEGY_KEYS), or should we restrict to V3-A subset?

**Q3** — **Counter-intuitive findings credibility**: Three findings violate my pre-test intuition (hysteresis tightens / high reset valuable / age_cap nearly optimal). Is this an artifact of the test design, or genuine? Specifically, is the "spell resets are valuable" mechanism §4.1 a real phenomenon, or could it be a backtest-engine quirk that doesn't translate live?

**Q4** — **n=4 (P8) + n=1 (P9 9c) — small samples for SPEC changes**: P8's incremental was 4 trades, P9 9c's is 1 trade. Combined we're proposing a SPEC change based on 5 historical edge cases. Is this evidentially sufficient or should we require a live-monitoring period first?

**Q5** — **Worst trade unchanged across all variants**: every P9 variant has worst=-$5,041 (the same non-V3-A IC_HV trade). This is because spell gate parameters control ENTRY frequency, not which trade is entered or how it exits. Is this interpretation correct? Are there hidden ways worst trade could shift in a different sample period?

**Q6** — **SPEC-100 scope question**: P8 + P9 9c are two distinct parameter changes (different files / same engine module). Bundle into one SPEC-100, or separate SPEC-100a (P8) and SPEC-100b (P9)? Which is more PM-friendly / Developer-friendly?

---

## 7. Honesty / Calibration Note

My P9 design memo (filed before running) made 3 predictions; **all 3 were wrong** in direction or magnitude:

| Subtest | My pre-test prediction | Actual | Calibration |
|---|---|---|---|
| 9a hysteresis | "trade count -5%" | -22 to -30% | Wrong magnitude (5x off) |
| 9b high reset | "near-zero impact" | -22% trades / -$16k | Wrong direction (I thought redundant) |
| 9c age_cap | "+5-8 trades, ~$5-10k, low confidence" | +1 trade / $1.3k | Right direction, wrong magnitude (5x off) |

This calibration miss is itself research evidence: **spell gate behavior is not easily intuited from code structure**. Future spell-gate-adjacent research must rely on empirical engine replay, not first-principles reasoning.

---

## 8. Artifacts

| File | Purpose |
|---|---|
| `research/q064/q064_p9_spell_reset_sensitivity.py` | P9 sweep script |
| `research/q064/q064_p9_summary.csv` | 12 variant aggregate metrics |
| `research/q064/q064_p9_trade_detail.csv` | per-variant per-trade detail |
| `task/q064_p8_spell_gate_review.md` | P8 prior packet |
| `task/q064_p5_routing_2nd_quant_review_packet_2026-05-12.md` | Q064 main + Addenda A/B (closed) |

Awaiting 2nd Quant verdict before SPEC drafting.

---

## 9. 2nd Quant Final Verdict (2026-05-13)

**APPROVE α — Adopt P8 only (`max_trades_per_spell: 2 → 3`). Defer P9 `spell_age_cap: 30 → 90` as future optional note.**

### Decision basis

| Option | 2nd Quant verdict |
|---|---|
| **α** (P8 only) | **RECOMMENDED** — primary improvement, clean SPEC attribution |
| β (P8 + P9 9c) | Acceptable but bundles marginal tweak with primary fix; not preferred |
| γ (none) | Rejected — P8 evidence is clean Pareto positive |

### Reasons against β (bundling P9 9c)

1. **Evidence too thin**: P9 9c gain = 1 trade / +$1,330 / 19y. SPEC parameter change should not rest on n=1 historical edge case.
2. **Governance cost**: future reviewers will need to explain why 30→90 changed; the rationale is "1 trade in 2022-10". Low ROI on documentation.
3. **Attribution clarity**: bundling makes SPEC change "fix quota AND adjust lifetime" — less clean than "fix quota only".
4. **Reversal friendly**: keeping spell_age_cap=30 means if live evidence later shows it's binding, reopen is straightforward.
5. **Scope discipline**: project already has many SPECs/gates/exceptions; +$70/yr alpha is below the threshold for adding new parameter changes.

### Design principles confirmed by P9 (preserve these going forward)

| Principle | Source |
|---|---|
| `vix_low_reset` single-day behavior is **deliberate** | 9a — hysteresis 3d/5d both Pareto-fail |
| `vix_high_reset` (VIX≥35 → spell reset) is **deliberate, not redundant** | 9b — removing it loses 9 trades / -$16k |
| `spell_age_cap=30d` is **near-optimal**, not a binding constraint | 9c — only 1 trade in 19y benefits from relaxation |
| Worst trade is **invariant to spell gate params** | All 12 variants worst = -$5,041 |

### Documentation guidance

If/when P9 9c is implemented in the future, the wording must NOT inflate its importance:

> `spell_age_cap` is relaxed from 30d to 90d as a low-risk operational simplification. Historical benefit is minimal (+1 trade), so this should not be interpreted as a core alpha driver.

### Action sequence

1. **Now**: Quant writes RESEARCH_LOG entry recording P9 findings + α decision
2. **Now**: Draft SPEC for P8 only (`max_trades_per_spell: 2 → 3`)
3. **Future trigger**: If live evidence shows spell_age_cap is binding (e.g., long HV spell blocks ≥ 2 entries that selector recommends), reopen Q064 with P9 9c as candidate
4. **Methodology lesson logged**: Spell gate behavior is not easily intuited from code — future research must use engine replay, not first-principles reasoning

### Status

- Q064 P5 main verdict: UNCHANGED (V3-A retained as aftermath bypass)
- Q064 P8 (max_trades_per_spell 2→3): **APPROVED FOR SPEC**
- Q064 P9 (spell reset mechanism): **APPROVED α (reject hysteresis, reject no-high-reset, defer age_cap)**
- Q064 thread overall: research phase complete, awaiting SPEC drafting for P8

