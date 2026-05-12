# Q064 Aftermath Routing Review — 2nd Quant Review Packet

- **Date**: 2026-05-12
- **Prepared by**: Quant Researcher
- **Audience**: 2nd Quant Reviewer
- **Topic**: Main strategy `is_aftermath()` routing — should aftermath window trades use V3-A IC (current) or BPS HV (counterfactual)?
- **Stage**: Pre-SPEC; PM requests independent review before reverting aftermath routing from V3-A → BPS HV

---

## 1. Review Request

Q064 (P1–P4) produced a consistent result: aftermath routing to V3-A IC broken-wing underperforms BPS HV by 57–63% on $/BP-day across all three comparison frames (P3 raw, P4 equal-BP, P3 per-contract). The first Quant recommends reverting the aftermath routing from V3-A to BPS HV.

Before opening a SPEC, we request independent review on:

> Is the methodology sound, are the comparison frames fair, and does the evidence support reverting aftermath routing to BPS HV?

We are **not** asking:
- Whether to remove the `is_aftermath()` detection itself (P2 confirms aftermath timing has value; timing is not under review)
- Whether to redesign trigger parameters (peak ≥ 28, off-peak ≥ 10%, VIX < 40 — these are unchanged)
- Whether BS pricing is a valid approximation (both structures use identical BS framework; relative comparison is insulated from absolute-level bias)

We **are** asking:
- Is the **P3 counterfactual methodology** valid (same entry dates, same DTE / delta parameters for BPS HV)?
- Is the **P4 equal-BP standardization** a fair comparison (fractional contract scaling)?
- Does **n=15 aftermath trades** provide sufficient evidence to act on?
- Is **any structural failure mode** missing from the analysis — a scenario where V3-A IC materially outperforms BPS HV that we haven't tested?
- Is **BPS HV revert** the right recommendation, or is there a narrower IC variant or hybrid worth testing first?

Specific review questions in §7.

---

## 2. Background: Current Routing Logic

`strategy/selector.py:295` defines:

```python
AFTERMATH_PEAK_VIX_10D_MIN = 28.0   # trailing 10-TD peak VIX threshold
AFTERMATH_OFF_PEAK_PCT     = 0.10   # VIX must have fallen ≥10% from peak
EXTREME_VIX                = 40.0   # hard upper exclusion

def is_aftermath(vix: VixSnapshot) -> bool:
    peak = vix.vix_peak_10d
    if peak is None or peak < AFTERMATH_PEAK_VIX_10D_MIN:
        return False
    if vix.vix >= EXTREME_VIX:
        return False
    return vix.vix <= peak * (1.0 - AFTERMATH_OFF_PEAK_PCT)
```

When `is_aftermath()` returns True **and** `iv_signal == HIGH` **and** regime is `HIGH_VOL + BEARISH/NEUTRAL`, the selector routes to **V3-A IC HV broken-wing** instead of the standard **BPS HV**.

### V3-A IC HV vs BPS HV Structure Parameters

| Parameter | BPS HV (standard) | V3-A IC HV (aftermath current) |
|---|---|---|
| Structure | Bull Put Spread | Iron Condor (broken-wing) |
| DTE | 35 | 45 |
| Short put | δ0.20 | δ0.12 (more OTM) |
| Long put | δ0.10 | δ0.08 (broken-wing wider) |
| Short call | — | δ0.12 |
| Long call | — | δ0.04 (broken-wing much wider) |
| Avg put wing width | 102 pts | 58 pts |
| Avg call wing width | — | 195 pts (3.4× put wing) |
| Avg BP | $23,258 | $44,700 (1.92×) |
| Avg entry credit | $3,914 (put only) | $4,263 (put $1,576 + call $2,687) |

**Key structural asymmetry**: V3-A's call wing (avg 195 pts) is far wider than the put wing (avg 58 pts), driving BP to 1.9× BPS HV. IC is PM-margin-governed at `max(call_width, put_width) × 100 × contracts`.

---

## 3. P1: Aftermath Window Statistics (19yr, 2007–2026)

| Metric | Value |
|---|---|
| Total trading days | 4,869 |
| Aftermath days | 518 (10.6%) |
| Independent aftermath windows | **90** |
| Avg window duration | 5.8 calendar days |
| VIX median (aftermath) | 26.03 |
| VIX P25–P75 (aftermath) | 24.04 – 29.96 |

Aftermath windows cluster in: 2008–2009 GFC aftermath, 2011 EU debt, 2020 post-COVID Q2–Q3, 2022 rate hike cycle, 2025 tariff shock.

**Observation**: 90 windows in 19yr = ~4.7 windows/yr, but most are short (1–5 days). The 11 windows ≥15 days are concentrated in 2011 Q4 and 2020 Q2–Q3.

---

## 4. P2: Aftermath Timing Attribution

19yr baseline trades: 282 total. Focused on `Bull Put Spread (High Vol)` — n=28.

Of those 28, **15 (53.6%) had entry_date inside an aftermath window**. These are the sample for P3/P4.

| Metric | Aftermath (n=15) | Non-aftermath HV (n=13) |
|---|---|---|
| Win rate | 86.7% | 84.6% |
| Avg P&L | **+$2,140** | +$1,609 (+33%) |
| Median P&L | +$2,767 | +$2,690 |
| $/BP-day | 44.32 | 44.18 |
| Worst trade | **-$3,163** | -$5,392 |
| Total P&L | **+$32,097** | +$20,914 |
| VIX at entry (median) | 27.62 | 22.51 |

**P2 interpretation**: Aftermath timing adds ~+33% avg P&L and meaningfully better downside protection (worst trade -$3,163 vs -$5,392). The VIX context is genuinely different (median 27.6 vs 22.5). However, median P&L is nearly identical ($2,767 vs $2,690), and $/BP-day is the same — the avg P&L gap is driven by aggregate rather than per-trade quality.

**P2 conclusion**: aftermath timing has directional value (better tail, modest avg improvement). This part of the routing is not under challenge.

---

## 5. P3: V3-A vs BPS HV Counterfactual (Same 15 Entry Dates)

### Methodology

For each of the 15 aftermath entry dates, simulate both structures using:
- **Pricing**: BS with σ = max(VIX/100, 0.10) × term_mult(DTE), r=0.04
- **Entry**: signal-date close as S; strikes per delta targets above
- **Exit**: BS mid-price at actual exit_date using remaining DTE and exit-date VIX (replicates 60% TP / 21DTE exit rule)
- **BP**: BPS HV = put_width × 100 × contracts; V3-A = max(call_width, put_width) × 100 × contracts

Note: Both structures priced with identical BS framework on identical dates — relative comparison is insulated from absolute-level pricing bias.

### Results

| Metric | BPS HV (counterfactual) | V3-A IC HV (current routing) |
|---|---|---|
| Win rate | 93.3% | **100%** |
| Avg P&L | **+$2,426** | +$1,984 (−18%) |
| Median P&L | **+$3,056** | +$2,078 (−32%) |
| $/BP-day | **87.04** | 33.42 (−62%) |
| Worst trade | −$2,330 | **+$10** |
| Total P&L | **+$36,386** | +$29,755 |
| Avg BP | $23,258 | **$44,700** (1.92×) |
| V3-A > BPS (笔数) | — | **4/15** (26.7%) |

**P3 interpretation**: V3-A wins on 4 of 15 trades — the 4 cases where BPS would have lost or barely broken even (market reversal during hold). V3-A's 100% win rate vs BPS's 93.3% reflects IC's double-sided premium absorbing directional risk. However, V3-A consumes 1.9× BP while delivering −18% lower avg P&L.

---

## 6. P4: Equal-BP Normalization (V3-A Contracts Scaled to BPS BP)

### Methodology

Per-trade scaling: `v3a_contracts_adj = bps_bp_per_contract / v3a_bp_per_contract` (avg ≈ 0.52). V3-A P&L scaled by same factor. BPS HV baseline unchanged.

This answers: "If we gave V3-A the same BP budget as BPS HV, who wins?"

### Results

| Metric | BPS HV | V3-A (equal-BP adjusted) |
|---|---|---|
| Avg contracts | 1.000 | 0.521 |
| Win rate | 93.3% | **100%** |
| Avg P&L | **+$2,426** | +$1,031 (−57%) |
| Median P&L | **+$3,056** | +$1,130 (−63%) |
| $/BP-day | **80.37** | 29.73 (−63%) |
| Worst trade | −$2,330 | **+$5** |
| Total P&L | **+$36,386** | +$15,471 |
| V3-A > BPS | — | **2/15** (13.3%) |

**P4 interpretation**: BP-normalization widens the gap to −57% avg P&L and −63% $/BP-day. This rules out the hypothesis that "V3-A underperforms only because it deploys more capital." On an equal-BP basis, V3-A earns 42.5 cents for every dollar BPS earns. V3-A wins only in the 2 trades where BPS would have lost or been near zero.

### Evidence Summary Across Frames

| Frame | Avg P&L delta | $/BP-day delta | V3-A win rate | BPS win rate |
|---|---|---|---|---|
| P3 (per contract) | −18% | −62% | 26.7% | 73.3% |
| P4 (equal BP) | −57% | −63% | 13.3% | 86.7% |

The gap is consistent and widens under equal-BP — confirming the inefficiency is structural, not a capital-scale artifact.

---

## 7. First Quant Recommendation

**Revert aftermath routing from V3-A IC HV → BPS HV.**

Rationale:
1. P4 eliminates the capital-scale explanation. V3-A generates 42.5¢ per $1 of BPS at equal BP.
2. Aftermath VIX environment (median 26, falling) makes BPS HV the structurally better fit: put risk is already reduced (vol retreating), call wing in IC is unnecessary insurance consuming BP without commensurate return.
3. V3-A's sole advantage (100% win rate / near-zero worst trade) can be replicated by a VIX re-escalation stop on BPS HV ("close BPS if VIX crosses back above 28 during hold") at near-zero cost.
4. The one historical scenario where V3-A IC genuinely helped (2020-06-05 VIX reversal) would be caught by a VIX stop rule applied to BPS HV — without forgoing the 57% P&L advantage on all other trades.

**Optional enhancement**: Rather than V3-A, add a "VIX re-cross stop" to BPS HV in aftermath windows (close position if VIX > 28 during hold period). This preserves BPS efficiency while addressing the 1 tail scenario V3-A handled better.

---

## 8. Caveats and Limitations

1. **n=15 aftermath trades** — all conclusions are directional; no result achieves 5% statistical significance. Both P2 and P3/P4 point the same direction across all metrics, which is the main confidence basis.
2. **BS pricing** — both structures use identical σ formula; relative comparison is consistent, but absolute P&L numbers carry the standard BS-flat caveat (skew regime-dependency, especially at HIGH_VOL entry).
3. **Historical BPS HV trades were executed pre-SPEC-064** — the actual 15 trades in P2 used BPS HV (before V3-A routing was introduced). This means P3/P4 are full counterfactuals; neither structure has live aftermath execution history post-SPEC-064.
4. **P4 uses fractional contracts** — real execution requires integer contracts. At account NLV ~$500k, rounding from 0.52 to 1 V3-A contract doubles the BP vs a 1 BPS HV contract, making the real-world equal-BP comparison even less favorable for V3-A.
5. **No intraday stop simulation** — all simulations use hold-to-exit-date or 60% TP exit without explicit intraday stop. The VIX re-cross stop recommendation is not yet quantified.

---

## 9. Review Questions

**Q1 — Counterfactual validity**: P3 uses BPS HV parameters (δ0.20/δ0.10, DTE 35) on the same 15 aftermath entry dates. Is this a valid counterfactual? The entry dates were selected by the aftermath trigger; would BPS HV have been recommended on those same dates if V3-A routing didn't exist?

**Q2 — Equal-BP scaling**: P4 scales V3-A by `bps_bp / v3a_bp ≈ 0.52`. Is per-trade multiplicative scaling the right BP normalization? An alternative is portfolio-level scaling (fix total BP budget, count how many contracts of each). Would that change the conclusion?

**Q3 — Sample size adequacy**: n=15 aftermath trades, 2/15 (13%) V3-A wins in P4. Is this sufficient to recommend a routing change in production, given the system has been live with V3-A routing since SPEC-064? What additional evidence (paper trading, larger window scan) would you require before acting?

**Q4 — Missing failure mode**: Is there a scenario not covered by the 15 historical trades where V3-A IC would materially outperform BPS HV? Candidates: (a) prolonged VIX re-escalation during hold (>2 weeks VIX above 28 again), (b) very deep aftermath with VIX >35 at entry, (c) post-2022 rate regime where put-heavy IC is structurally better. Do any of these invalidate the P3/P4 conclusion?

**Q5 — VIX stop alternative**: The recommendation proposes "close BPS if VIX re-crosses 28 during hold" as an alternative to V3-A's tail protection. Is this stop rule worth quantifying before the SPEC is written, or is the P3/P4 evidence sufficient to proceed without it?

**Q6 — Structural diagnosis**: V3-A's call wing (avg 195 pts) is 3.4× its put wing (avg 58 pts). Is the asymmetric call wing the core design problem, and would a symmetric IC (equal wing widths) perform better? Is this worth testing before committing to BPS HV revert?

---

## 10. Artifacts

| File | Description |
|---|---|
| `research/q064/q064_p1_aftermath_windows.py` | P1 window extraction script |
| `research/q064/q064_p1_windows.csv` | 90 aftermath windows (start/end/peak VIX/duration) |
| `research/q064/q064_p1_daily_flags.csv` | 4,869 trading days with daily aftermath flag |
| `research/q064/q064_p2_pnl_attribution.py` | P2 attribution script |
| `research/q064/q064_p2_tagged_trades.csv` | 28 BPS HV trades + aftermath flag + VIX at entry |
| `research/q064/q064_p2_summary.csv` | Two-group comparison (aftermath vs non-aftermath) |
| `research/q064/q064_p3_structure_counterfactual.py` | P3 counterfactual simulation |
| `research/q064/q064_p3_results.csv` | 15 trades × 3 structures (actual / BPS BS / V3-A) |
| `research/q064/q064_p3_summary.csv` | P3 aggregate comparison |
| `research/q064/q064_p4_equal_bp.py` | P4 equal-BP normalization |
| `research/q064/q064_p4_results.csv` | 15 trades × BPS vs V3-A adjusted (with win/loss flag) |
| `research/q064/q064_p1p2_memo_2026-05-11.md` | Full research memo (P1–P4) |
| `strategy/selector.py:295` | `is_aftermath()` implementation |

---

*Reviewer response to go in: `task/q064_aftermath_2nd_quant_review_packet_2026-05-12_Review.md`*
