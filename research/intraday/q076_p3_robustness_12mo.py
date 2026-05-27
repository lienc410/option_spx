"""Q076 Phase 3 — Robustness on 12-month sample.

PM verdict (2026-05-26): A2a + B is the Q076 governance choice. P3 task:
verify A2a + B doesn't misbehave outside the 21-day jitter window. Per
2nd Quant review, focus on 4 risks:

  R1. HIGH_VOL (VIX ≥ 22) — does governance fire when IVP locks high (≥80)?
  R2. Deep LOW_VOL (VIX < 14) — does A2a's IVP<35 close trigger fire?
  R3. Shock periods (2024-08 / 2025-04 / 2026-03) — does hysteresis react too slowly?
  R4. Hard exits (stop / stress / second-leg / R6) — must remain immediate.

Variants tested (drops A2b — out-of-scope per PM verdict):
  baseline   — current selector per 1h bar
  A2a        — two-sided hysteresis [42-53 entry / 35-57 hold]
  B          — scheduled eval (10:30 + 15:30 ET)
  A2a + B    — chosen verdict combo

Output:
  q076_p3_variants_12mo.csv  — per-bar decisions across all variants
  q076_p3_metrics_overall.csv     — overall metrics
  q076_p3_metrics_by_regime.csv   — split by VIX regime + by quarter
"""

from __future__ import annotations

import sys
import pickle
import pandas as pd
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from signals.vix_regime import get_current_snapshot
from signals.iv_rank import get_current_iv_snapshot
from signals.trend import get_current_trend
from strategy.selector import select_strategy

OUT = REPO / "research" / "intraday"

DAILY_VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
DAILY_SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
ALIGNED_12MO = REPO / "data" / "market_cache" / "spx_vix_1h_aligned_12mo.pkl"

ENTRY_LOW = 42.0
ENTRY_HIGH = 53.0
HOLD_LOW = 35.0
HOLD_HIGH = 57.0
SCHED_BARS = {"10:30", "15:30"}

PM_CONTRACTS_LOW = 5
PM_CONTRACTS_HIGH = 10
FRICTION_PER_CONTRACT_LOW = 5.0
FRICTION_PER_CONTRACT_HIGH = 15.0


def _load_daily(pkl_path, col):
    df = pickle.load(open(pkl_path, "rb"))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[["Close"]].rename(columns={"Close": col})


def baseline_replay():
    vix_daily = _load_daily(DAILY_VIX_PKL, "vix").tail(500)
    spx_daily = _load_daily(DAILY_SPX_PKL, "close").tail(500)
    aligned = pickle.load(open(ALIGNED_12MO, "rb"))
    print(f"Replaying {len(aligned)} bars across {aligned.index.normalize().nunique()} days...")

    rows = []
    with patch("signals.vix_regime.fetch_vix3m", return_value=None):
        for i, (ts, bar) in enumerate(aligned.iterrows()):
            if i % 200 == 0:
                print(f"  bar {i}/{len(aligned)} — {ts.date()}")
            bar_date = ts.date()
            vix_baseline = vix_daily.loc[vix_daily.index < pd.Timestamp(bar_date).normalize()]
            spx_baseline = spx_daily.loc[spx_daily.index < pd.Timestamp(bar_date).normalize()]
            if len(vix_baseline) < 10 or len(spx_baseline) < 220:
                continue
            try:
                vix_snap = get_current_snapshot(vix_baseline, current_vix=float(bar["vix_close"]))
                iv_snap = get_current_iv_snapshot(vix_baseline, current_vix=float(bar["vix_close"]))
                trend_snap = get_current_trend(spx_baseline, current_spx=float(bar["spx_close"]))
                rec = select_strategy(vix_snap, iv_snap, trend_snap)
                strat = rec.strategy.value if hasattr(rec.strategy, "value") else str(rec.strategy)
                pa = getattr(rec, "position_action", "")
                regime = vix_snap.regime.value if hasattr(vix_snap.regime, "value") else str(vix_snap.regime)
            except Exception as exc:
                strat, pa, regime = "ERROR", "", ""
                iv_snap = None

            rows.append({
                "timestamp": ts,
                "date": bar_date,
                "bar_hm": ts.strftime("%H:%M"),
                "vix": float(bar["vix_close"]),
                "spx": float(bar["spx_close"]),
                "ivp252": float(iv_snap.ivp252) if iv_snap else None,
                "regime": regime,
                "baseline_strategy": strat,
                "baseline_position_action": pa,
            })
    return pd.DataFrame(rows)


def _baseline_says_bps(row):
    return (row["baseline_strategy"] == "Bull Put Spread"
            and row["baseline_position_action"] in ("OPEN", "HOLD"))


def _baseline_other(row):
    return row["baseline_strategy"] not in ("Bull Put Spread", "Reduce / Wait")


def apply_a2a(df):
    state = []
    prev = None
    for _, row in df.iterrows():
        if _baseline_other(row):
            new_state = row["baseline_strategy"]
        else:
            ivp = row["ivp252"]
            bps_ok = _baseline_says_bps(row)
            if prev is None:
                new_state = row["baseline_strategy"]
            elif prev == "Bull Put Spread":
                if ivp is None or ivp > HOLD_HIGH or ivp < HOLD_LOW:
                    new_state = "Reduce / Wait"
                else:
                    new_state = "Bull Put Spread"
            else:
                if ivp is not None and ENTRY_LOW <= ivp <= ENTRY_HIGH and bps_ok:
                    new_state = "Bull Put Spread"
                else:
                    new_state = "Reduce / Wait"
        state.append(new_state)
        prev = new_state
    return pd.Series(state, index=df.index)


def apply_b(df):
    state = []
    last_decided = None
    for _, row in df.iterrows():
        if row["bar_hm"] in SCHED_BARS or last_decided is None:
            last_decided = row["baseline_strategy"]
        state.append(last_decided)
    return pd.Series(state, index=df.index)


def apply_a2a_plus_b(df):
    state = []
    prev = None
    for _, row in df.iterrows():
        if row["bar_hm"] in SCHED_BARS or prev is None:
            if _baseline_other(row):
                new_state = row["baseline_strategy"]
            else:
                ivp = row["ivp252"]
                bps_ok = _baseline_says_bps(row)
                if prev is None:
                    new_state = row["baseline_strategy"]
                elif prev == "Bull Put Spread":
                    close_now = ivp is None or ivp > HOLD_HIGH or ivp < HOLD_LOW
                    new_state = "Reduce / Wait" if close_now else "Bull Put Spread"
                else:
                    if ivp is not None and ENTRY_LOW <= ivp <= ENTRY_HIGH and bps_ok:
                        new_state = "Bull Put Spread"
                    else:
                        new_state = "Reduce / Wait"
            prev = new_state
        state.append(prev)
    return pd.Series(state, index=df.index)


def compute_metrics(df, variant_col, baseline_eod, sample_name=""):
    s = df[variant_col]
    d = df.copy()
    d["state"] = s
    d["prev"] = s.shift(1)
    d["flipped"] = (d["state"] != d["prev"]) & d["prev"].notna()

    n_bars = len(d)
    n_days = d["date"].nunique()
    n_flips = int(d["flipped"].sum())

    by_day = d.groupby("date").agg(
        n_unique=("state", "nunique"),
        first=("state", "first"),
        last=("state", "last"),
    )
    switching_days = int((by_day["n_unique"] > 1).sum())
    open_close_mismatch = int((by_day["first"] != by_day["last"]).sum())

    bps_on = (d["state"] == "Bull Put Spread").values
    episodes = []
    i = 0
    while i < len(bps_on):
        if bps_on[i]:
            j = i
            while j < len(bps_on) and bps_on[j]:
                j += 1
            episodes.append(j - i)
            i = j
        else:
            i += 1
    n_bps_ep = len(episodes)
    median_hold = float(pd.Series(episodes).median()) if episodes else None
    short_ep = sum(1 for e in episodes if e <= 3)

    eod = by_day["last"]
    if isinstance(baseline_eod, pd.Series):
        base_aligned = baseline_eod.reindex(eod.index)
        agreement = (eod == base_aligned).mean() * 100 if len(eod) else None
    else:
        agreement = None

    flip_ev = d[d["flipped"]]
    opens = ((flip_ev["state"] == "Bull Put Spread") & (flip_ev["prev"] == "Reduce / Wait")).sum()
    closes = ((flip_ev["state"] == "Reduce / Wait") & (flip_ev["prev"] == "Bull Put Spread")).sum()
    rt = int(min(opens, closes))

    return {
        "sample": sample_name,
        "variant": variant_col,
        "n_bars": n_bars,
        "n_days": n_days,
        "intraday_flips": n_flips,
        "flips_per_day": round(n_flips / max(n_days, 1), 3),
        "switching_days": switching_days,
        "open_close_mismatch_days": open_close_mismatch,
        "n_bps_episodes": n_bps_ep,
        "median_hold_hours": median_hold,
        "episodes_le_3h": short_ep,
        "bps_opens": int(opens),
        "bps_closes": int(closes),
        "round_trips": rt,
        "friction_5contracts_usd": round(rt * PM_CONTRACTS_LOW * FRICTION_PER_CONTRACT_LOW, 0),
        "friction_10contracts_usd": round(rt * PM_CONTRACTS_HIGH * FRICTION_PER_CONTRACT_HIGH, 0),
        "eod_agreement_pct": round(agreement, 1) if agreement is not None else None,
    }


def main():
    df = baseline_replay()
    df.to_csv(OUT / "q076_p3_baseline_replay_12mo.csv", index=False)
    print(f"\nBaseline replay: {len(df)} bars saved")

    print("\nApplying variants...")
    df["baseline"] = df["baseline_strategy"]
    df["A2a"] = apply_a2a(df)
    df["B"] = apply_b(df)
    df["A2a_B"] = apply_a2a_plus_b(df)
    df.to_csv(OUT / "q076_p3_variants_12mo.csv", index=False)

    baseline_eod_full = df.groupby("date")["baseline"].last()
    variants = ["baseline", "A2a", "B", "A2a_B"]

    # Overall metrics
    print("\n=== Overall 12mo metrics ===")
    rows = [compute_metrics(df, v, baseline_eod_full, sample_name="all_12mo") for v in variants]
    overall = pd.DataFrame(rows)
    overall.to_csv(OUT / "q076_p3_metrics_overall.csv", index=False)
    cols = ["variant", "n_bars", "n_days", "intraday_flips", "flips_per_day",
            "switching_days", "open_close_mismatch_days", "n_bps_episodes",
            "median_hold_hours", "episodes_le_3h", "round_trips",
            "friction_5contracts_usd", "friction_10contracts_usd", "eod_agreement_pct"]
    print(overall[cols].to_string(index=False))

    # Improvement vs baseline
    base = overall.iloc[0]
    print("\n  Improvement vs baseline:")
    for i in range(1, len(overall)):
        v = overall.iloc[i]
        dflip = (base["intraday_flips"] - v["intraday_flips"]) / max(base["intraday_flips"], 1) * 100
        dshort = (base["episodes_le_3h"] - v["episodes_le_3h"]) / max(base["episodes_le_3h"], 1) * 100
        print(f"    {v['variant']:<8}: flips ↓{dflip:>4.0f}%  ≤3h ↓{dshort:>4.0f}%  "
              f"EOD {v['eod_agreement_pct']:>5.1f}%  RT {int(v['round_trips'])}/{int(base['round_trips'])}")

    # Regime split — by VIX regime of the bar
    print("\n=== By VIX regime ===")
    regime_rows = []
    for regime_name, mask in [
        ("LOW_VOL (<14)", df["vix"] < 14),
        ("NEUTRAL (14-22)", (df["vix"] >= 14) & (df["vix"] < 22)),
        ("HIGH_VOL (22-30)", (df["vix"] >= 22) & (df["vix"] < 30)),
        ("STRESS (≥30)", df["vix"] >= 30),
    ]:
        sub = df[mask]
        if len(sub) == 0:
            continue
        sub_base_eod = sub.groupby("date")["baseline"].last()
        for v in variants:
            m = compute_metrics(sub, v, sub_base_eod, sample_name=regime_name)
            regime_rows.append(m)

    regime_df = pd.DataFrame(regime_rows)
    regime_df.to_csv(OUT / "q076_p3_metrics_by_regime.csv", index=False)
    for regime_name in ["LOW_VOL (<14)", "NEUTRAL (14-22)", "HIGH_VOL (22-30)", "STRESS (≥30)"]:
        sub_r = regime_df[regime_df["sample"] == regime_name]
        if sub_r.empty:
            continue
        print(f"\n  --- {regime_name} ---")
        print(sub_r[["variant", "n_bars", "intraday_flips", "flips_per_day",
                     "n_bps_episodes", "median_hold_hours", "episodes_le_3h",
                     "round_trips"]].to_string(index=False))

    # Quarterly split
    print("\n=== By quarter ===")
    df["quarter"] = pd.to_datetime(df["date"]).dt.to_period("Q").astype(str)
    quarter_rows = []
    for q in sorted(df["quarter"].unique()):
        sub = df[df["quarter"] == q]
        sub_base_eod = sub.groupby("date")["baseline"].last()
        for v in variants:
            m = compute_metrics(sub, v, sub_base_eod, sample_name=q)
            quarter_rows.append(m)
    quarter_df = pd.DataFrame(quarter_rows)
    quarter_df.to_csv(OUT / "q076_p3_metrics_by_quarter.csv", index=False)
    for q in sorted(df["quarter"].unique()):
        sub_q = quarter_df[quarter_df["sample"] == q]
        print(f"\n  --- {q} ---")
        print(sub_q[["variant", "n_bars", "intraday_flips", "n_bps_episodes",
                     "median_hold_hours", "episodes_le_3h", "round_trips",
                     "eod_agreement_pct"]].to_string(index=False))

    print(f"\nOutputs in {OUT}/")


if __name__ == "__main__":
    main()
