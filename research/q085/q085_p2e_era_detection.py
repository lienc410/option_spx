"""Q085 P2e — can the "dead era" (2014-2021) be identified and avoided?

PM question 2026-07-04: shouldn't we detect long unlucky eras and switch
behavior by regime?

Two routes examined:
  A) PREDICTIVE era detection: statistically impossible on this sample —
     the dead era is ONE contiguous stretch (2012-2021); any detector is
     fitted to n=1 and unfalsifiable (same trap as the VIX 15-20 band carve).
  B) REACTIVE performance stop (generic form, not fitted to era features):
     halt after trailing-K event sum < 0, paper-track while halted, resume
     when trailing-reentry sum > 0. Pre-registered grid {(K=10,re=5),
     (K=20,re=10)}, select/confirm halves.

Result (2026-07-04 run): route B FAILS —
  worst-7y era mean: baseline -$31/event -> -$23 (K10) / -$37 (K20)
  full-sample net/yr: $547 -> ~$480-500 (whipsaw cost exceeds salvage)
Mechanism: the dead era is ZERO-MEAN CHOP, not a persistent bleed. Trailing
stops only rescue persistent-bleed failures; on coin-flip eras they whipsaw.

Conclusion recorded: era-robustness must come from VEHICLE choice (BPS carry
cushion keeps the dead era positive natively, +$31/trade) — not from era
detection. House distinction: we condition on observable WEATHER (VIX regime
matrix); multi-year edge CLIMATE is not ex-ante observable at n=1 eras.
"""
# executable form: see git history; rerun reproduces with the P2c event stream
