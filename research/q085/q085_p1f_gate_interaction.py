"""Q085 P1f — oversold signal x gate/matrix interaction (PM question 2026-07-03).

PM: "超卖的时候通常 VIX 明显上升，现有矩阵会 gate 住或漂移到更高 VIX 格子" —
does the F3 edge survive inside the states where we can actually act?

Findings (2026-07-03 run, descriptive; formal inference in P2):
  A. Oversold days: median IVP 72 (gate upper=70!), median VIX 21.4;
     72% BLOCKED; 47% drift into HIGH_VOL regime. PM mechanism confirmed.
  B. S3 dynamic feasibility: allowed day -> oversold within 5td AND still
     allowed AND same cell = 17.4%. S3-as-designed mostly idles.
  C. fwd-21td edge by state:
       allowed & NORMAL   -0.24pp (n=48)   <- S3's habitat: NO edge
       allowed & HIGH_VOL +0.99pp (n=100)  <- HV cells: sizing/conviction
       blocked & NORMAL   +0.59pp (n=267)  <- IVP-blocked stratum: edge lives HERE
  => P2 reprioritized: S2 (conditional reopen of blocked windows) primary,
     S5-HV (oversold-day HV sizing) secondary, S3 demoted (formally tested
     but expected dead).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import q085_battery_lib as B
import pandas as pd

df = B.df
sig = pd.read_csv(B.ROOT/"research/q078/_signal_history_cache.csv", parse_dates=["date"]).set_index("date")
for col in ["strategy_key","regime","iv_signal","trend","ivp"]:
    df[col] = sig[col].reindex(df.index)
df = df[(df.index >= "2000-01-01") & df["regime"].notna()].copy()
oversold = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]).reindex(df.index).fillna(False)
allowed = df["strategy_key"].notna() & (df["strategy_key"] != "")
fwd21 = (B.C.shift(-21)/B.C - 1).reindex(df.index)

st = df[oversold].assign(allowed=allowed[oversold])
print(f"oversold: {oversold.sum()} days; blocked {100*(~st.allowed).mean():.0f}%; "
      f"median IVP {st.ivp.median():.0f} vs all {df.ivp.median():.0f}; "
      f"median VIX {st.vix.median():.1f} vs all {df.vix.median():.1f}")
print("regimes:", dict(st.regime.value_counts()))

ov, al = oversold.to_numpy(), allowed.to_numpy()
keys = df["strategy_key"].fillna("").to_numpy()
n_alw = feas = same = 0
for i in range(len(df)-5):
    if not al[i]: continue
    n_alw += 1
    for j in range(i+1, i+6):
        if ov[j]:
            if al[j]:
                feas += 1
                if keys[j] == keys[i]: same += 1
            break
print(f"S3 feasibility: {100*feas/n_alw:.1f}% still-allowed, {100*same/n_alw:.1f}% same-cell")

for mask, label in [(allowed, "allowed all"), (allowed & (df.regime=="NORMAL"), "allowed NORMAL"),
                    (allowed & (df.regime=="HIGH_VOL"), "allowed HV"),
                    (~allowed, "blocked all"), (~allowed & (df.regime=="NORMAL"), "blocked NORMAL")]:
    n = (mask & oversold).sum()
    e = fwd21[mask & oversold].mean() - fwd21[mask].mean()
    print(f"{label:<16} n_os={n:>4} fwd21 edge {100*e:+.2f}pp")
