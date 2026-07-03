# Q084 External Read Report — PASS

**Date**: 2026-07-03  
**Reviewer**: Claude Agent (lightweight audit)  
**Verdict**: **PASS — Kill verdict CONFIRMED, no false-negative risk**  
**Confidence**: HIGH

---

## 4 Key Facts Verification

| Fact | Status | Finding |
|------|--------|---------|
| **P1 Sample (33 trades, 67% WR, $764/yr)** | ✓ CONFIRMED | Arithmetic correct; win rate and net consistent |
| **Vol Expansion Calendar Mismatch (8/33 = 24% vs 45% prior)** | ✓ SUPPORTED | Definition gap (broad "any vol expansion" vs narrow "expansion during hold") is economically sound |
| **Gate B Threshold ($1.5k/yr)** | ✓ JUSTIFIED | FAV case $1,378 < K2; even most-optimistic scenario fails. Logic clear. |
| **P2 Robustness (PESS -$768/yr, 52% WR)** | ✓ CREDIBLE | Parameters (3% contango, 5% inversion) reasonable, not contrived. |

---

## Red Flag Checklist

- ✓ **BS-Flat assumption**: COVERED (P2 bracket quantifies term-structure risk)
- ⚠ **Leg-length selection bias**: NOT COVERED, but pre-registered constraint accepts it; even 2-3% leg optimization doesn't close 50% gap
- ✓ **2008 exclusion**: JUSTIFIED (2008 trades profitable, not tail risk; true tail in 2021-03-24)
- ✓ **Hidden adverse scenario**: COVERED (contango + inversion in PESS envelope)

---

## Kill Verdict Assessment

**Root cause (vol-calendar mismatch) is economically sound**. VIX expansion signal fires, but position has often expired before money is made. Only 8/33 trades capture the expansion event — structural timing problem, not a parameter-tweak fixable.

**P2 bracket (FAV $1.4k, PESS -$0.8k) covers both directions** of mispricing risk. Median outcome $764/yr is sufficiently below $1.5k gate to be unambiguous kill.

**No false-negative risk detected.**

---

## Recommendation

Q084 **KILL stands**. Archive as "NORMAL×LOW×NEUTRAL awaits future data" (annual observation slot open if vol-calendar conditions change materially).

---

**External read completed by**: Claude Agent audit (3 hours)  
**Next step**: Index update + archive
