# Q074 P2 — Booster Sweep Results

> **Status: P2 RESULTS — All 4 candidates Soft Pass.**
> **No Strong Pass yet.** P3 transition-risk forensic is the decision gate.
> B1-B4 remain FROZEN per 2nd Quant Revision 4 / P0.

**Date**: 2026-05-18
**Parent**: `q074_p1_attribution_memo.md` + G2 PASS

---

## TL;DR

| Cand | Booster cap | Active % | Net ROE | ΔROE vs B0 | Worst 20d | Floor 8% | All V1-V3 | Classification |
|---|---|---|---|---|---|---|---|---|
| B0 baseline (Arch-3) | — | 0% | 7.95% | — | -7.04% | ✗ | ✓ | reference |
| B1 strict 85 | 85% | 17.3% | 8.06% | +0.11pp | -7.04% | ✓ | ✓ | **Soft pass** |
| B2 moderate 85 | 85% | 20.1% | 8.08% | +0.13pp | -7.04% | ✓ | ✓ | **Soft pass** |
| B3 strict 90 | 90% | 17.3% | 8.17% | +0.22pp | -7.04% | ✓ | ✓ | **Soft pass** |
| **B4 moderate 90** | **90%** | **20.1%** | **8.20%** | **+0.25pp** | **-7.04%** | **✓** | **✓** | **Soft pass (leading)** |

**Key finding**: Worst 20d is **UNCHANGED** across all 4 candidates. Booster signal is self-protective by design (IVP/VIX/trend filters turn booster OFF before stress).

> **P2 validates economic feasibility; P3 must validate transition safety.**

---

## 1. P2 verdict per success criteria

All 4 candidates fall in **Soft pass** territory (ROE +0.10 to +0.30pp). None reach **Strong pass** (ROE ≥ +0.30pp).

- B4 closest to Strong (+0.25pp, 0.05pp gap)
- All pass V1/V2/V3 vetoes
- All push Net ROE through floor 8%
- Worst 20d completely unchanged (-7.04%)

**Per P0 Soft pass policy**: paper/shadow only; **cannot amend SPEC-104 production caps** without Strong pass + P3/P4 validation.

---

## 2. Why worst 20d UNCHANGED — self-protective signal

P1 attribution already foreshadowed this: B1 ON has P(stress 10d) = 8.8% vs OFF 27.2%. The benign confirmation features (IVP < 55, VIX_5d_change ≤ +1.0/+1.5, ddATH > -3%/-4%) **systematically turn booster OFF before stress fires**:

```
IVP rising → booster OFF
VIX_5d_change > threshold → booster OFF
ddATH worsens > -3% / -4% → booster OFF
SPX falls below MA50 → booster OFF
```

So when stress triggers (R5 / R6 conditions met), booster has already deactivated 5-10 days earlier in most cases. **Worst-20d windows occur during stress days where SPX cap is 50% — booster never in play there**.

This is the intended P0 design: state machine priority + multi-condition benign confirmation = booster cannot be ON during stress. Self-protection is structural, not optional.

---

## 3. Incremental booster PnL (candidate - B0)

| Cand | Cumul Δ (26y) | Ann incr % NLV |
|---|---|---|
| B1 | +$185,417 | +0.79% |
| B2 | +$211,550 | +0.90% |
| B3 | +$370,833 | +1.58% |
| B4 | +$423,099 | +1.80% |

These are the dollar contributions in days when booster is active. On 26y basis they translate to:
- B1: +0.11pp ann ROE on combined NLV
- B4: +0.25pp ann ROE on combined NLV

Booster active 17-20% of trading days → booster contribution is structurally bounded.

---

## 4. Candidate ranking (Quant prior, P3 will verify)

| Rank | Cand | Why |
|---|---|---|
| 1 | **B4 moderate 90%** | Highest ROE upside; but biggest transition-risk exposure (includes VIX 20-22 + cap 90%) |
| 2 | B3 strict 90% | Same ROE potential as B4 but tighter benign filter — better safety, slightly less ROE |
| 3 | B2 moderate 85% | Moderate cap; VIX 20-22 inclusion may be partial liability |
| 4 | B1 strict 85% | Most conservative; smallest ROE gain |

P3 must:
1. Validate B4 transition risk — is the +0.25pp ROE clean or transition-tainted?
2. Compare B3 vs B4 on transition windows (both 90% cap, differ on VIX 20-22 inclusion)
3. Compute false-benign incremental losses per candidate

---

## 5. B1-B4 Frozen — P3 Inputs Locked

Per 2nd Quant Revision 4: no new B5/B6 derived from P2 results. P3 runs on B1-B4 as-is. If P3 shows ALL FOUR fail transition test → reject Q074. If P3 shows some pass / some fail → P4 validates the surviving 1-2 candidates.

---

## 6. P3 Focus (per PM brief)

### Required outputs

| Output | Definition |
|---|---|
| Primary transition window | Booster active in prior 10 TD before stress trigger |
| Secondary diagnostic window | Booster active in prior 20 TD before stress trigger |
| Severity classification | mild (no 2nd-leg next 20d) / acute (2nd-leg next 20d) / failed-benign (incremental loss < 0) |
| Top-10 booster losses | Worst 10 incremental booster days per candidate |
| Crisis-specific examination | 2000-03 / 2007-07 / 2018-02 / 2020-02 / 2022-01 |
| VIX 20-22 attribution (B2/B4) | What % of B2/B4 transition losses come from VIX 20-22 days? |

### P3 success → P4 validation

If B4 (or B3) shows clean transitions (false-benign rare, mild dominant, incremental losses < 2% NLV per window):
- Candidate advances to P4: V6 bootstrap, V7 walk-forward, friction sensitivity, synthetic stress
- Strong pass possible if walk-forward both halves pass + bootstrap robust

If B4 shows concentrated transition losses (acute or failed-benign dominant):
- Candidate fails transition test → fall back to B3 or reject
- P4 then runs on B3 or next surviving candidate

---

## 7. Caveats

1. **Worst 20d unchanged is BEFORE transition forensic**. P2 used 26y composite — if transition windows individually had losses, they're averaged into the overall PnL series but didn't dominate the worst rolling 20d. P3 will examine these windows specifically.

2. **P2 model treats cash as signed**: when booster active 85% + Q42 17.5% + HV 0%, cash residual = -2.5% (margin loan). Same for 90% booster (cash -7.5%). Model assumes cash earns/costs BOXX 4.3% — likely understates real margin cost (margin loan typically > BOXX yield). Friction sensitivity in P4 will test ±50%.

3. **Q42 stays at 17.5% target constant**. P3 / P4 should check if Q42 active periods coincide with booster active periods. If high coincidence → BP utilization stress; if anti-correlated → diversification working.

4. **No floor 8% pass with friction confidence yet**. Friction estimate is conservative; could be lower → ROE slightly higher. Could be higher (margin cost > BOXX) → ROE slightly lower. P4 ±50% sensitivity will calibrate.

---

## 8. Decision

**Continue to P3 transition-risk forensic. Do not finalize candidate ranking until P3 complete.**

> P2 validates economic feasibility; P3 must validate transition safety.

---

## 9. References

- `q074_p0_anchored_memo_2026-05-17.md` — P0 + 2nd Quant R1-R5 applied
- `q074_p1_attribution_memo.md` — P1 diagnostic + B1/B2 composite signals
- `q074_p2_booster_sweep.py` — P2 simulator
- `q074_p2_candidate_results.csv` — 5-candidate metrics
- `q074_p2_incremental_summary.csv` — incremental PnL per booster
