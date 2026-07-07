"""Q090 E1 — fact layer for PM's technical model (pre-registered q090_framing.md).

Point-in-time discipline: a swing pivot (k=5) at bar i is only USABLE from bar
i+5 (confirmation lag) — no lookahead. Cutpoints: discrete pre-registered menu,
selection on 2000-2012 (fwd5 |t|), confirmation on 2013+ (4 endpoints, BH within
batch, sign-consistency from battery machinery).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q085"))
import q085_battery_lib as B

df, C, H, L, V = B.df, B.C, B.H, B.L, B.V
n = len(df)
K = 5          # pivot half-window (house convention)
LOOK = 120     # cluster/trendline lookback (td)
SPLIT = pd.Timestamp("2013-01-01")

# --- confirmed swing pivots (usable from i+K) ---
hi = H.to_numpy(); lo = L.to_numpy(); cl = C.to_numpy()
swing_hi = np.zeros(n, bool); swing_lo = np.zeros(n, bool)
for i in range(K, n - K):
    w_hi = hi[i - K:i + K + 1]; w_lo = lo[i - K:i + K + 1]
    if hi[i] == w_hi.max() and (w_hi == hi[i]).sum() == 1:
        swing_hi[i] = True
    if lo[i] == w_lo.min() and (w_lo == lo[i]).sum() == 1:
        swing_lo[i] = True
hi_idx = np.where(swing_hi)[0]; lo_idx = np.where(swing_lo)[0]

def cluster_flag(pivot_idx, pivot_vals, band, touches, prox, side):
    """side='r': close below-but-within prox of a >=touches cluster level.
       side='s': close above-but-within prox."""
    out = np.zeros(n, bool)
    for t in range(2 * K + LOOK, n):
        usable = pivot_idx[(pivot_idx + K <= t) & (pivot_idx >= t - LOOK)]
        if len(usable) < touches:
            continue
        vals = pivot_vals[usable]
        c = cl[t]
        for v in vals:
            members = vals[np.abs(vals / v - 1) <= band]
            if len(members) < touches:
                continue
            lvl = members.mean()
            if side == "r" and lvl >= c >= lvl * (1 - prox):
                out[t] = True; break
            if side == "s" and lvl <= c <= lvl * (1 + prox):
                out[t] = True; break
    return pd.Series(out, index=df.index)

def trendline_flag(n_highs, prox):
    """Last n_highs confirmed swing highs strictly decreasing; line through the
    most recent two, extrapolated to today; close within prox below the line."""
    out = np.zeros(n, bool)
    for t in range(2 * K + LOOK, n):
        usable = hi_idx[(hi_idx + K <= t) & (hi_idx >= t - LOOK)]
        if len(usable) < n_highs:
            continue
        last = usable[-n_highs:]
        v = hi[last]
        if not all(v[j] > v[j + 1] for j in range(len(v) - 1)):
            continue
        i1, i2 = last[-2], last[-1]
        slope = (hi[i2] - hi[i1]) / (i2 - i1)
        line = hi[i2] + slope * (t - i2)
        if line > cl[t] >= line * (1 - prox):
            out[t] = True
    return pd.Series(out, index=df.index)

vol_ratio = V / V.rolling(20).mean()
up1 = C > C.shift(1)
up2 = up1 & up1.shift(1).fillna(False)

SIGS: dict[str, pd.Series] = {}
for band in (0.003, 0.005):
    for touches in (2, 3):
        for prox in (0.005, 0.01):
            tag = f"b{int(band*1e3)}_t{touches}_p{int(prox*1e3)}"
            SIGS[f"S1r_{tag}"] = cluster_flag(hi_idx, hi, band, touches, prox, "r")
            SIGS[f"S1s_{tag}"] = cluster_flag(lo_idx, lo, band, touches, prox, "s")
for d_tag, upm in (("d1", up1), ("d2", up2)):
    for th in (0.85, 0.95):
        SIGS[f"S2_{d_tag}_v{int(th*100)}"] = (upm & (vol_ratio < th)).fillna(False)
for nh in (2, 3):
    for prox in (0.005, 0.01):
        SIGS[f"S4_n{nh}_p{int(prox*1e3)}"] = trendline_flag(nh, prox)

ENDPOINTS = {f"fwd{h}": np.log(C.shift(-h) / C) for h in (1, 3, 5, 10)}
valid = B.default_valid & V.rolling(20).mean().notna()
all_days = pd.Series(True, index=df.index)
RNG = np.random.default_rng(90)

first_half = pd.Series(df.index < SPLIT, index=df.index)
second_half = pd.Series(df.index >= SPLIT, index=df.index)

print("== selection (2000-2012, fwd5) ==")
sel_rows, winners = [], {}
for name, cond in SIGS.items():
    r = B.perm_test_studentized(cond, valid, first_half, ENDPOINTS["fwd5"], RNG, df.index)
    if r is None:
        sel_rows.append({"signal": name, "n_on": int((cond & first_half & valid).sum()), "t": np.nan}); continue
    sel_rows.append({"signal": name, **{k: r[k] for k in ("n_on", "mean_diff_bp", "t", "p")}})
    fam = name.split("_")[0]
    if fam not in winners or abs(r["t"]) > abs(winners[fam][1]["t"]):
        winners[fam] = (name, r)
sel = pd.DataFrame(sel_rows)
sel.to_csv(ROOT / "research/q090/q090_e1_selection.csv", index=False)
print(sel.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

print("\n== confirmation (2013+, 4 endpoints, winners only) ==")
conf_rows = []
for fam, (name, _) in sorted(winners.items()):
    cond = SIGS[name]
    for ep, out in ENDPOINTS.items():
        r = B.perm_test_studentized(cond, valid, second_half, out, RNG, df.index)
        row = {"family": fam, "signal": name, "endpoint": ep}
        row.update({k: r[k] for k in ("n_on", "mean_diff_bp", "t", "p", "sign_consistent")} if r else {"n_on": 0})
        conf_rows.append(row)
conf = pd.DataFrame(conf_rows)
# BH within the confirmation batch
m = conf.p.notna(); pv = conf.loc[m, "p"].to_numpy()
order = np.argsort(pv); passed = np.zeros(len(pv), bool)
for rank, oi in enumerate(order, 1):
    if pv[oi] <= 0.10 * rank / len(pv):
        passed[order[:rank]] = True
conf.loc[m, "bh_pass_q10"] = passed
conf.to_csv(ROOT / "research/q090/q090_e1_confirmation.csv", index=False)
print(conf.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

print("\n== era slices for winners (mean fwd5 on-days, bp; n) ==")
ERAS = [("2000s", "2000", "2010"), ("2010s", "2010", "2020"), ("2020-23", "2020", "2024"),
        ("2024+", "2024", "2100"), ("last24m", "2024-07-07", "2100")]
f5 = ENDPOINTS["fwd5"]
for fam, (name, _) in sorted(winners.items()):
    cond = SIGS[name] & valid
    parts = []
    for era, a, b_ in ERAS:
        w = cond & (df.index >= a) & (df.index < b_)
        parts.append(f"{era}: {f5[w].mean()*1e4:+.0f}bp(n={int(w.sum())})")
    print(f"{name}: " + " | ".join(parts))
