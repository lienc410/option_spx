"""Q090 E1 — fact layer for PM's technical model (pre-registered q090_framing.md).

Point-in-time discipline: a swing pivot (k=5) at bar i is only USABLE from bar
i+5 (confirmation lag) — no lookahead. Cutpoints: discrete pre-registered menu,
selection on 2000-2012 (fwd5 |t|), confirmation on 2013+ (4 endpoints, BH within
batch, sign-consistency from battery machinery).

SPEC-132 (2026-07-07): the flag CONSTRUCTORS are now importable pure functions —
strategy/structure_map.py (production Structure Map + shadow logger) imports
THESE definitions; no re-derivation anywhere (生产函数单一化). The research
runner below uses the same functions; its CSV outputs are byte-comparable to
the pre-refactor run (verified 2026-07-07). Loop bodies are verbatim from the
original inline version — only parameterized (globals → arguments).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

K = 5          # pivot half-window (house convention)
LOOK = 120     # cluster/trendline lookback (td)
SPLIT = pd.Timestamp("2013-01-01")


# ── importable constructors (SPEC-132 production shares these) ────────────────

def find_swing_pivots(hi: np.ndarray, lo: np.ndarray, k: int = K) -> tuple[np.ndarray, np.ndarray]:
    """Confirmed swing pivots (usable from i+k). Verbatim original loop."""
    n = len(hi)
    swing_hi = np.zeros(n, bool)
    swing_lo = np.zeros(n, bool)
    for i in range(k, n - k):
        w_hi = hi[i - k:i + k + 1]
        w_lo = lo[i - k:i + k + 1]
        if hi[i] == w_hi.max() and (w_hi == hi[i]).sum() == 1:
            swing_hi[i] = True
        if lo[i] == w_lo.min() and (w_lo == lo[i]).sum() == 1:
            swing_lo[i] = True
    return swing_hi, swing_lo


def cluster_flag_at(t: int, pivot_idx: np.ndarray, pivot_vals: np.ndarray,
                    cl: np.ndarray, band: float, touches: int, prox: float,
                    side: str, k: int = K, look: int = LOOK) -> bool:
    """Single-day cluster predicate — the EXACT body of the original per-t
    loop iteration. cluster_flag() and production's today-flag both call this
    (bit-identity by construction, asserted in tests/test_spec_132.py)."""
    usable = pivot_idx[(pivot_idx + k <= t) & (pivot_idx >= t - look)]
    if len(usable) < touches:
        return False
    vals = pivot_vals[usable]
    c = cl[t]
    for v in vals:
        members = vals[np.abs(vals / v - 1) <= band]
        if len(members) < touches:
            continue
        lvl = members.mean()
        if side == "r" and lvl >= c >= lvl * (1 - prox):
            return True
        if side == "s" and lvl <= c <= lvl * (1 + prox):
            return True
    return False


def cluster_flag(pivot_idx: np.ndarray, pivot_vals: np.ndarray, cl: np.ndarray,
                 index: pd.Index, band: float, touches: int, prox: float,
                 side: str, k: int = K, look: int = LOOK) -> pd.Series:
    """side='r': close below-but-within prox of a >=touches cluster level.
       side='s': close above-but-within prox."""
    n = len(cl)
    out = np.zeros(n, bool)
    for t in range(2 * k + look, n):
        out[t] = cluster_flag_at(t, pivot_idx, pivot_vals, cl, band, touches,
                                 prox, side, k=k, look=look)
    return pd.Series(out, index=index)


def clusters_at(t: int, pivot_idx: np.ndarray, pivot_vals: np.ndarray,
                band: float, touches: int, k: int = K, look: int = LOOK) -> list[dict]:
    """Descriptive companion (SPEC-132 display): the cluster levels usable at
    t under the SAME membership rule as cluster_flag_at (per-pivot window,
    mean of members, >=touches). Deduped on rounded level. Does NOT feed the
    flag — the flag stays on cluster_flag_at."""
    usable = pivot_idx[(pivot_idx + k <= t) & (pivot_idx >= t - look)]
    if len(usable) < touches:
        return []
    vals = pivot_vals[usable]
    seen: dict[float, int] = {}
    for v in vals:
        members = vals[np.abs(vals / v - 1) <= band]
        if len(members) < touches:
            continue
        lvl = float(members.mean())
        key = round(lvl, 2)
        seen[key] = max(seen.get(key, 0), int(len(members)))
    return [{"level": lvl, "touches": n_t} for lvl, n_t in sorted(seen.items())]


def trendline_state_at(t: int, hi_idx: np.ndarray, hi_vals: np.ndarray,
                       cl: np.ndarray, n_highs: int, prox: float,
                       k: int = K, look: int = LOOK) -> tuple[bool, float | None]:
    """Single-day trendline predicate + line value — exact body of the
    original per-t loop iteration (line value exposed for SPEC-132 display)."""
    usable = hi_idx[(hi_idx + k <= t) & (hi_idx >= t - look)]
    if len(usable) < n_highs:
        return False, None
    last = usable[-n_highs:]
    v = hi_vals[last]
    if not all(v[j] > v[j + 1] for j in range(len(v) - 1)):
        return False, None
    i1, i2 = last[-2], last[-1]
    slope = (hi_vals[i2] - hi_vals[i1]) / (i2 - i1)
    line = hi_vals[i2] + slope * (t - i2)
    flag = bool(line > cl[t] >= line * (1 - prox))
    return flag, float(line)


def trendline_flag(hi_idx: np.ndarray, hi_vals: np.ndarray, cl: np.ndarray,
                   index: pd.Index, n_highs: int, prox: float,
                   k: int = K, look: int = LOOK) -> pd.Series:
    """Last n_highs confirmed swing highs strictly decreasing; line through the
    most recent two, extrapolated to today; close within prox below the line."""
    n = len(cl)
    out = np.zeros(n, bool)
    for t in range(2 * k + look, n):
        flag, _line = trendline_state_at(t, hi_idx, hi_vals, cl, n_highs, prox,
                                         k=k, look=look)
        out[t] = flag
    return pd.Series(out, index=index)


def volume_ratio(volume: pd.Series) -> pd.Series:
    """V / 20d mean V (house convention across Q085/Q090)."""
    return volume / volume.rolling(20).mean()


def build_signal_menu(df: pd.DataFrame, k: int = K, look: int = LOOK) -> dict[str, pd.Series]:
    """The full pre-registered E1 cutpoint menu over an OHLCV frame."""
    hi = df["high"].to_numpy()
    lo = df["low"].to_numpy()
    cl = df["close"].to_numpy()
    swing_hi, swing_lo = find_swing_pivots(hi, lo, k=k)
    hi_idx = np.where(swing_hi)[0]
    lo_idx = np.where(swing_lo)[0]
    vol_ratio = volume_ratio(df["volume"])
    up1 = df["close"] > df["close"].shift(1)
    up2 = up1 & up1.shift(1).fillna(False)

    sigs: dict[str, pd.Series] = {}
    for band in (0.003, 0.005):
        for touches in (2, 3):
            for prox in (0.005, 0.01):
                tag = f"b{int(band*1e3)}_t{touches}_p{int(prox*1e3)}"
                sigs[f"S1r_{tag}"] = cluster_flag(hi_idx, hi, cl, df.index, band, touches, prox, "r", k=k, look=look)
                sigs[f"S1s_{tag}"] = cluster_flag(lo_idx, lo, cl, df.index, band, touches, prox, "s", k=k, look=look)
    for d_tag, upm in (("d1", up1), ("d2", up2)):
        for th in (0.85, 0.95):
            sigs[f"S2_{d_tag}_v{int(th*100)}"] = (upm & (vol_ratio < th)).fillna(False)
    for nh in (2, 3):
        for prox in (0.005, 0.01):
            sigs[f"S4_n{nh}_p{int(prox*1e3)}"] = trendline_flag(hi_idx, hi, cl, df.index, nh, prox, k=k, look=look)
    return sigs


# ── research runner (selection/confirmation analysis — unchanged outputs) ─────

def main() -> None:
    sys.path.insert(0, str(ROOT / "research" / "q085"))
    import q085_battery_lib as B

    df, C, V = B.df, B.C, B.V
    SIGS = build_signal_menu(df)

    ENDPOINTS = {f"fwd{h}": np.log(C.shift(-h) / C) for h in (1, 3, 5, 10)}
    valid = B.default_valid & V.rolling(20).mean().notna()
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


if __name__ == "__main__":
    main()
