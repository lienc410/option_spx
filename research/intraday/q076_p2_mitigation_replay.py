"""Q076 Phase 2 — Intraday Churn Mitigation Replay (v2: two-sided hysteresis).

2nd Quant review + PM verdict (2026-05-26): A v1 only had upper-bound
hysteresis (IVP > 57 → close). Production selector ALSO closes at low IVP
(< 40, "premium too thin") — implemented via get_position_action returning
CLOSE_AND_WAIT when position held. A v1 ignored this, contaminating EOD
agreement metric. This v2 implements two-sided hysteresis as a proper state
machine, plus a sensitivity (A2b) treating low-IV as entry-only filter.

Variants (6):
  baseline         : current selector once per 1h bar
  A2a              : two-sided hysteresis [entry 42-53, hold 35-57] —
                     matches production close-trigger semantics
  A2b              : upper hysteresis only [entry <53, close >57]; low IVP is
                     entry-only block (does NOT force close existing BPS) —
                     deviation from production semantics, semantic-test only
  B                : evaluate only at 10:30 + 15:30 ET; carry forward otherwise
  A2a+B            : A2a hysteresis applied at scheduled bars only
  A2b+B            : A2b entry-only applied at scheduled bars only

PM success criteria (vs baseline):
  - intraday flips ↓ ≥ 50%
  - ≤3h BPS episodes ↓ ≥ 75%
  - EOD recommendation agreement ≥ 90%

Output:
  q076_p2_variants_v2.csv   — per-bar decisions
  q076_p2_metrics_v2.csv    — 6-row variant metrics
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
ALIGNED_1H = REPO / "data" / "market_cache" / "spx_vix_1h_aligned_1mo.pkl"

# Hysteresis bands (PM-confirmed values)
# Entry zone: WAIT → BPS only when IVP inside [42, 53]
# Hold zone:  BPS → BPS while IVP inside [35, 57]
# Outside hold zone forces close (A2a) or only IVP>57 closes (A2b)
ENTRY_LOW = 42.0
ENTRY_HIGH = 53.0
HOLD_LOW = 35.0
HOLD_HIGH = 57.0

SCHED_BARS = {"10:30", "15:30"}

PM_CONTRACTS_LOW = 5
PM_CONTRACTS_HIGH = 10
FRICTION_PER_CONTRACT_LOW = 5.0
FRICTION_PER_CONTRACT_HIGH = 15.0


def _load_daily(pkl_path: Path, col: str) -> pd.DataFrame:
    df = pickle.load(open(pkl_path, "rb"))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[["Close"]].rename(columns={"Close": col})


def baseline_replay():
    vix_daily = _load_daily(DAILY_VIX_PKL, "vix").tail(500)
    spx_daily = _load_daily(DAILY_SPX_PKL, "close").tail(500)
    aligned = pickle.load(open(ALIGNED_1H, "rb"))

    rows = []
    with patch("signals.vix_regime.fetch_vix3m", return_value=None):
        for ts, bar in aligned.iterrows():
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
            except Exception:
                strat = "ERROR"
                pa = ""
                iv_snap = None

            rows.append({
                "timestamp": ts,
                "date": bar_date,
                "bar_hm": ts.strftime("%H:%M"),
                "vix": float(bar["vix_close"]),
                "spx": float(bar["spx_close"]),
                "ivp252": float(iv_snap.ivp252) if iv_snap else None,
                "baseline_strategy": strat,
                "baseline_position_action": pa,
            })
    return pd.DataFrame(rows)


def _baseline_says_bps(row):
    return (row["baseline_strategy"] == "Bull Put Spread"
            and row["baseline_position_action"] in ("OPEN", "HOLD"))


def _baseline_says_other(row):
    """True when baseline picks a non-BPS, non-Wait strategy (e.g., IC HV).
    Defer to baseline in that case."""
    return row["baseline_strategy"] not in ("Bull Put Spread", "Reduce / Wait")


def apply_a2a(df: pd.DataFrame) -> pd.Series:
    """A2a: two-sided hysteresis. Matches production close-trigger semantics.

    WAIT  → BPS: only if ENTRY_LOW ≤ IVP ≤ ENTRY_HIGH AND baseline approves
    BPS   → WAIT: if IVP > HOLD_HIGH OR IVP < HOLD_LOW (forced close)
    Other strategies (e.g., HV IC): defer to baseline
    """
    state = []
    prev = None
    for _, row in df.iterrows():
        if _baseline_says_other(row):
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
            else:  # prev = Wait
                if ivp is not None and ENTRY_LOW <= ivp <= ENTRY_HIGH and bps_ok:
                    new_state = "Bull Put Spread"
                else:
                    new_state = "Reduce / Wait"
        state.append(new_state)
        prev = new_state
    return pd.Series(state, index=df.index)


def apply_a2b(df: pd.DataFrame) -> pd.Series:
    """A2b: upper-band hysteresis only. Low IVP is entry-only filter
    (does NOT force close existing BPS). Deviation from production semantics —
    semantic-test only.

    WAIT  → BPS: only if ENTRY_LOW ≤ IVP ≤ ENTRY_HIGH AND baseline approves
    BPS   → WAIT: only if IVP > HOLD_HIGH (no low-IV forced close)
    """
    state = []
    prev = None
    for _, row in df.iterrows():
        if _baseline_says_other(row):
            new_state = row["baseline_strategy"]
        else:
            ivp = row["ivp252"]
            bps_ok = _baseline_says_bps(row)
            if prev is None:
                new_state = row["baseline_strategy"]
            elif prev == "Bull Put Spread":
                if ivp is not None and ivp > HOLD_HIGH:
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


def apply_b(df: pd.DataFrame) -> pd.Series:
    """B: evaluate only at scheduled bars; carry forward."""
    state = []
    last_decided = None
    for _, row in df.iterrows():
        if row["bar_hm"] in SCHED_BARS or last_decided is None:
            last_decided = row["baseline_strategy"]
        state.append(last_decided)
    return pd.Series(state, index=df.index)


def apply_hysteresis_scheduled(df: pd.DataFrame, hysteresis_fn) -> pd.Series:
    """A+B: apply hysteresis logic, but only at scheduled bars."""
    # Run hysteresis bar-by-bar but only "decide" on sched bars.
    state = []
    prev = None
    for _, row in df.iterrows():
        if row["bar_hm"] in SCHED_BARS or prev is None:
            if _baseline_says_other(row):
                new_state = row["baseline_strategy"]
            else:
                ivp = row["ivp252"]
                bps_ok = _baseline_says_bps(row)
                if prev is None:
                    new_state = row["baseline_strategy"]
                elif prev == "Bull Put Spread":
                    # decide whether to close using same rule as standalone
                    if hysteresis_fn == "a2a":
                        close_now = ivp is None or ivp > HOLD_HIGH or ivp < HOLD_LOW
                    else:  # a2b: only upper triggers close
                        close_now = ivp is not None and ivp > HOLD_HIGH
                    new_state = "Reduce / Wait" if close_now else "Bull Put Spread"
                else:
                    if ivp is not None and ENTRY_LOW <= ivp <= ENTRY_HIGH and bps_ok:
                        new_state = "Bull Put Spread"
                    else:
                        new_state = "Reduce / Wait"
            prev = new_state
        state.append(prev)
    return pd.Series(state, index=df.index)


def compute_metrics(df, variant_col, baseline_eod):
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
    n_bps_episodes = len(episodes)
    median_hold = float(pd.Series(episodes).median()) if episodes else None
    short_episodes = sum(1 for e in episodes if e <= 3)

    eod = by_day["last"]
    agreement = (eod == baseline_eod).mean() * 100 if len(eod) else None

    flip_events = d[d["flipped"]]
    bps_opens = ((flip_events["state"] == "Bull Put Spread") &
                 (flip_events["prev"] == "Reduce / Wait")).sum()
    bps_closes = ((flip_events["state"] == "Reduce / Wait") &
                  (flip_events["prev"] == "Bull Put Spread")).sum()
    completed_rt = int(min(bps_opens, bps_closes))
    friction_low_5 = completed_rt * PM_CONTRACTS_LOW * FRICTION_PER_CONTRACT_LOW
    friction_high_10 = completed_rt * PM_CONTRACTS_HIGH * FRICTION_PER_CONTRACT_HIGH

    return {
        "variant": variant_col,
        "n_bars": n_bars,
        "n_days": n_days,
        "intraday_flips": n_flips,
        "flips_per_day": round(n_flips / n_days, 3),
        "switching_days": switching_days,
        "open_close_mismatch_days": open_close_mismatch,
        "n_bps_episodes": n_bps_episodes,
        "median_hold_hours": median_hold,
        "episodes_le_3h": short_episodes,
        "bps_opens": int(bps_opens),
        "bps_closes": int(bps_closes),
        "round_trips": completed_rt,
        "friction_5contracts_usd": round(friction_low_5, 0),
        "friction_10contracts_usd": round(friction_high_10, 0),
        "eod_agreement_pct": round(agreement, 1) if agreement is not None else None,
    }


def main():
    print("Running baseline replay...")
    df = baseline_replay()
    print(f"  {len(df)} bars, IVP range {df['ivp252'].min():.1f} → {df['ivp252'].max():.1f}")

    print("\nApplying 6 variants...")
    df["baseline"] = df["baseline_strategy"]
    df["A2a"] = apply_a2a(df)
    df["A2b"] = apply_a2b(df)
    df["B"] = apply_b(df)
    df["A2a_B"] = apply_hysteresis_scheduled(df, "a2a")
    df["A2b_B"] = apply_hysteresis_scheduled(df, "a2b")

    df.to_csv(OUT / "q076_p2_variants_v2.csv", index=False)
    print(f"  Saved → {OUT/'q076_p2_variants_v2.csv'}")

    baseline_eod = df.groupby("date")["baseline"].last()

    variants = ["baseline", "A2a", "A2b", "B", "A2a_B", "A2b_B"]
    metrics = pd.DataFrame([compute_metrics(df, v, baseline_eod) for v in variants])
    metrics.to_csv(OUT / "q076_p2_metrics_v2.csv", index=False)

    print("\n" + "=" * 110)
    print("Q076 P2 — 6-Variant Comparison (v2: two-sided hysteresis)")
    print("=" * 110)
    cols = ["variant", "intraday_flips", "flips_per_day", "switching_days",
            "open_close_mismatch_days", "n_bps_episodes", "median_hold_hours",
            "episodes_le_3h", "round_trips", "friction_5contracts_usd",
            "friction_10contracts_usd", "eod_agreement_pct"]
    print(metrics[cols].to_string(index=False))

    base = metrics.iloc[0]
    print("\nImprovement vs baseline:")
    for i in range(1, len(metrics)):
        v = metrics.iloc[i]
        dflip = (base["intraday_flips"] - v["intraday_flips"]) / max(base["intraday_flips"], 1) * 100
        dshort = (base["episodes_le_3h"] - v["episodes_le_3h"]) / max(base["episodes_le_3h"], 1) * 100
        print(f"  {v['variant']:<8}: flips ↓{dflip:>4.0f}%  "
              f"≤3h ↓{dshort:>4.0f}%  EOD {v['eod_agreement_pct']:>5.1f}%  "
              f"round-trips {int(v['round_trips'])}/{int(base['round_trips'])}")

    print("\nPM success criteria check (all 3 must pass):")
    print("  flips ↓≥50%, ≤3h ↓≥75%, EOD ≥90%")
    print()
    for i in range(1, len(metrics)):
        v = metrics.iloc[i]
        dflip = (base["intraday_flips"] - v["intraday_flips"]) / max(base["intraday_flips"], 1) * 100
        dshort = (base["episodes_le_3h"] - v["episodes_le_3h"]) / max(base["episodes_le_3h"], 1) * 100
        eod_ok = v["eod_agreement_pct"] >= 90
        flip_ok = dflip >= 50
        short_ok = dshort >= 75
        verdict = "PASS" if (flip_ok and short_ok and eod_ok) else "FAIL"
        print(f"  {v['variant']:<8}: flips [{'✓' if flip_ok else '✗'}] "
              f"≤3h [{'✓' if short_ok else '✗'}] "
              f"EOD [{'✓' if eod_ok else '✗'}] → {verdict}")

    print(f"\nOutputs in {OUT}/")


if __name__ == "__main__":
    main()
