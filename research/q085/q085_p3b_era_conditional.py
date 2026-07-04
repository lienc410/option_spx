"""Q085 P3b — era-conditional revival check (PM challenge 2026-07-04).

PM: "every signal has some historical failure era; the job is to use what
works NOW with monitoring, not to demand all-weather survival."

Both vehicles re-measured by recent windows (results 2026-07-04 run):

S6 MES (per contract):          S2-BPS @ CALIB skew + $130 cost:
  full 26y  mean  +$38            full 26y  n=131 mean  -$53
  2024+     n=38  +$210  win 79%  2024+     n=16  mean +$591
  2025+     n=23  +$288  win 78%  2025+     n=10  mean +$1,014  win 80%
  rolling 24m windows monotone     (entire full-sample negative comes
  $91->$111->$113->$135->$219      from older eras)

=> Under real-chain skew + costs, the CURRENT era clears friction
   comfortably for both vehicles. The all-weather verdict ("not adoptable
   without watching") stands as fact; the adaptive-posture adoption
   (pre-committed degradation rules, paper-first) is the PM-ratified path.
PM posture ratification recorded 2026-07-04:
  "不存在一劳永逸的全天候门…市场不再支持了就要及时改变"
Scope boundary: applies to Layer-2 income edges only; Layer-1 survival
vetoes (2008-type, VIX>=35) remain static per PM 2026-07-03 confirmation.
"""
# reproducible forms: see q085_p2c/p2e (S6 event stream) and
# q085_p3_s2bps_robustness.py run() with scen="CALIB"; era slicing by entry date.
