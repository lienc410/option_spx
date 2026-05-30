# Q075 P2 G3 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-19
**Source**: `research/q075/q075_p2_memo.md`
**Verdict**: **PASS TO P3** — disciplined scope; IC primary, BCS secondary conditional on melt-up, C2 diagnostic only

---

## Final verdict statement

> Q075 P2 supports advancing C3 small IC as the primary candidate. IC w15/25/35 all beat cash under forced-exit-on-stress and slippage sensitivities, with positive worst trades even when 57% of trades are force-exited by stress. This is promising but suspiciously clean, so P3 must aggressively test IC intraperiod MAE, distance-to-strike, downside shocks, and gap-down scenarios. C4 BCS remains secondary and must pass historical plus mechanical melt-up analogs before any P4 inclusion. C2 short-DTE BPS remains diagnostic only.

---

## 3 decisions — 2nd Quant answers

| Decision | Answer |
|---|---|
| **D5 IC width** | Run **15 / 25 / 35** through P3/P4. Width 25 is **reporting base only**, NOT locked production choice. P4 portfolio-level utility decides final. |
| **D6 BCS analogs** | Use **2019-Q1 + 2023-Q4 + 2024-H1 + 1 mechanically-selected fastest 10d melt-up with VIX compression** (rule-based, not cherry-picked) |
| **D7 IC clean worst** | **Yes — probe aggressively**. P3 must include intraperiod MAE, distance-to-strike, downside shock, gap-down tests |

---

## P3 scope — disciplined

### Primary: C3 IC 15/25/35 — required tests
- **A. Stress-fire + SPX-down subset**: for IC trades where stress fired mid-trade, report entry/exit dates, SPX & VIX moves, distance to put short strike at exit, put/call leg MTM, net IC PnL
- **B. Intraperiod MAE**: worst mark-to-market loss during holding window, worst distance-to-short-strike, minimum SPX cushion. If exit PnL all positive but intraperiod MAE ugly → IC is less clean than it looks
- **C. Downside shock injection**: SPX -2% / -3% / -5% over 5-10d, combined with VIX +20% / +40% and skew widening. IC must survive downside path, not just historical stress exits
- **D. Gap-down at entry+1**: -2% and -3% overnight gap scenarios injected on day 1 of each IC trade
- Standard P3 forensic: transition forensic, crisis windows, top losses, distance-to-strike diagnostics

### Secondary: C4 BCS — 4 melt-up analogs (P4 inclusion conditional)
- 2019-Q1 broad rebound (~+13% Q1)
- 2023-Q4 rally (~+14%)
- 2024-H1 rally (~+14%)
- **Mechanical**: largest 10 trading-day SPX rally WHILE VIX compresses, selected over full 26y sample by rule (no cherry-pick)

BCS pass bar:
```
No analog cumulative loss worse than -$10k
No single trade worse than -0.5% NLV
No material W20d degradation
```

Given P2's -$98k under +5%/10d squeeze, prior is BCS likely fails this gate. Keep eligible because base-case economics strong; reject if even one analog breaks.

### Diagnostic: C2 short-DTE BPS
- One-pass appendix summary only
- No P4 integration unless IC fails AND PM explicitly reopens

---

## P4 scope (if P3 IC passes)

```
Required:
  IC w15 / w25 / w35
  BCS only if all 4 melt-up analogs pass

Compare per width:
  ΔROE
  ROE per BP-day
  MaxDD
  Worst 20d (V2)
  Worst 63d (V3)
  Capital competition with SPX / Q042
  Bootstrap (block=250, 20 seeds)
  Walk-forward H1 / H2
  Operational burden

Final width pick: by portfolio-level marginal utility, NOT standalone PnL
```

---

## Reframing — P3 goal

> P3 goal is NOT to confirm the IC.
> P3 goal is to actively try to BREAK IT.
> Find whether IC has hidden tail exposure P2's mark model missed.

Q075 is still worth continuing because IC w25 ~+0.18pp is right at Soft/Strong boundary and trade frequency is low (only meaningful if tail-neutral). The remaining question is exactly the one P3 tests:

> **Is IC clean because the opportunity is real, or because the simplified mark model missed the true stress path?**

---

## 2nd Quant Sign-off

- [x] G3 PASS to P3
- [x] D5/D6/D7 answered
- [x] P3 scope disciplined: IC primary with 4 stress probes; BCS secondary with 4 melt-up analogs; C2 diagnostic appendix
- [x] BCS mechanical melt-up rule defined (no cherry-pick)
- [x] P4 conditional on P3 IC clean result
- [x] Final IC width decided by portfolio-level utility in P4

→ Quant proceeds to draft P3 forensic with 4 IC probes + 4 BCS analogs + 1 C2 diagnostic appendix.
