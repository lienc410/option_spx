"""Q076 AC7 — 12mo Replay Using Developer's evaluate_recommendation (SPEC-107).

Wraps `strategy.intraday_governance.evaluate_recommendation` and replays the
same 12mo aligned 1h dataset that P3 used. Compares the 4 AC7 metrics against
the P3 envelope:

  flips: 93 ± 5
  episodes_le_3h: ≤ 4
  round_trips: 18 ± 2
  eod_agreement_pct: ≥ 92%

Critical implementation note: must track position state across bars (open/closed
based on governed decision). If position is always None, hysteresis prev would
always be WAIT (state never built), producing artificially high flip count.
"""

from __future__ import annotations

import os
import sys
import pickle
import tempfile
from pathlib import Path
from datetime import datetime
import pandas as pd
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Pin governance state/log paths to temp before import side-effects
_TMP = tempfile.TemporaryDirectory()
os.environ["SPEC_107_STATE_DIR_TMP"] = _TMP.name

from signals.vix_regime import get_current_snapshot
from signals.iv_rank import get_current_iv_snapshot
from signals.trend import get_current_trend
from strategy.selector import select_strategy
import strategy.intraday_governance as gov

# Redirect governance state/log paths into the temp dir for clean replay
gov.STATE_PATH = Path(_TMP.name) / "intraday_governance_state.json"
gov.DECISION_LOG_PATH = Path(_TMP.name) / "intraday_governance_log.jsonl"

OUT = REPO / "research" / "intraday"

DAILY_VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
DAILY_SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
ALIGNED_12MO = REPO / "data" / "market_cache" / "spx_vix_1h_aligned_12mo.pkl"


def _load_daily(pkl_path, col):
    df = pickle.load(open(pkl_path, "rb"))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[["Close"]].rename(columns={"Close": col})


def replay():
    vix_daily = _load_daily(DAILY_VIX_PKL, "vix").tail(500)
    spx_daily = _load_daily(DAILY_SPX_PKL, "close").tail(500)
    aligned = pickle.load(open(ALIGNED_12MO, "rb"))
    print(f"AC7 replay: {len(aligned)} bars across {aligned.index.normalize().nunique()} days")

    # Position state tracking across bars
    position = None  # None = no active position; dict with status='open' = active BPS

    rows = []
    last_governed = "Reduce / Wait"
    with patch("signals.vix_regime.fetch_vix3m", return_value=None):
        # also silence Telegram during replay
        with patch("strategy.intraday_governance._telegram_alert", return_value=False):
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
                except Exception as exc:
                    rows.append({"timestamp": ts, "error": str(exc)})
                    continue

                # Reset state file each iteration would defeat hysteresis; let
                # evaluate_recommendation read/write the JSON file naturally.
                # But "now" must be the bar timestamp to drive scheduled-bar logic.
                ts_naive = ts.to_pydatetime()  # tz-aware ET timestamp from aligned data

                decision = gov.evaluate_recommendation(
                    rec,
                    now=ts_naive,
                    position=position,
                    context=None,
                    write_log=False,
                )

                final_strategy = decision.governed_strategy
                # Update position state based on governed decision
                if final_strategy == "Bull Put Spread":
                    if position is None or position.get("status") == "closed":
                        position = {
                            "status": "open",
                            "strategy_key": "bull_put_spread",
                            "opened_at": ts.isoformat(),
                            "trade_id": f"replay-{ts.isoformat()}",
                        }
                    # else: still open, no action
                elif final_strategy == "Reduce / Wait":
                    if position and position.get("status") == "open":
                        position = None  # close
                else:
                    # non-BPS, non-Wait strategy (e.g., Iron Condor) — for AC7 replay,
                    # treat as governance defer; if previously holding BPS, close it.
                    if position and position.get("status") == "open":
                        position = None

                rows.append({
                    "timestamp": ts,
                    "date": bar_date,
                    "bar_hm": ts.strftime("%H:%M"),
                    "vix": float(bar["vix_close"]),
                    "ivp252": float(iv_snap.ivp252),
                    "regime": str(getattr(vix_snap.regime, "value", vix_snap.regime)),
                    "baseline_strategy": rec.strategy.value if hasattr(rec.strategy, "value") else str(rec.strategy),
                    "baseline_action": getattr(rec, "position_action", ""),
                    "governed_strategy": final_strategy,
                    "governed_action": decision.governed_position_action,
                    "actionable": decision.actionable,
                    "is_scheduled_bar": decision.is_scheduled_bar,
                    "hysteresis_prev": decision.hysteresis_state_prev,
                    "hysteresis_new": decision.hysteresis_state_new,
                    "final_priority_layer": decision.final_priority_layer,
                })
                last_governed = final_strategy

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q076_ac7_replay.csv", index=False)
    print(f"Saved {len(df)} bars to q076_ac7_replay.csv")
    return df


def compute_metrics(df: pd.DataFrame):
    s = df["governed_strategy"]
    d = df.copy()
    d["prev"] = s.shift(1)
    d["flipped"] = (s != d["prev"]) & d["prev"].notna()

    n_bars = len(d)
    n_days = d["date"].nunique()
    n_flips = int(d["flipped"].sum())

    by_day = d.groupby("date").agg(
        first=("governed_strategy", "first"),
        last=("governed_strategy", "last"),
        n_unique=("governed_strategy", "nunique"),
    )
    open_close_mismatch = int((by_day["first"] != by_day["last"]).sum())
    switching_days = int((by_day["n_unique"] > 1).sum())

    # BPS episodes
    bps_on = (d["governed_strategy"] == "Bull Put Spread").values
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
    n_episodes = len(episodes)
    median_hold = float(pd.Series(episodes).median()) if episodes else None
    short_ep = sum(1 for e in episodes if e <= 3)

    # P3 baseline EOD comparison
    p3_df = pd.read_csv(OUT / "q076_p3_variants_12mo.csv", parse_dates=["timestamp"])
    p3_df["date"] = pd.to_datetime(p3_df["date"]).dt.date
    p3_eod = p3_df.groupby("date")["baseline"].last()
    ac7_eod = by_day["last"]
    common = ac7_eod.index.intersection(p3_eod.index)
    agreement = (ac7_eod.loc[common] == p3_eod.loc[common]).mean() * 100

    # Round trips
    flip_ev = d[d["flipped"]]
    opens = ((flip_ev["governed_strategy"] == "Bull Put Spread") & (flip_ev["prev"] == "Reduce / Wait")).sum()
    closes = ((flip_ev["governed_strategy"] == "Reduce / Wait") & (flip_ev["prev"] == "Bull Put Spread")).sum()
    rt = int(min(opens, closes))

    return {
        "n_bars": n_bars,
        "n_days": n_days,
        "intraday_flips": n_flips,
        "switching_days": switching_days,
        "open_close_mismatch_days": open_close_mismatch,
        "n_bps_episodes": n_episodes,
        "median_hold_hours": median_hold,
        "episodes_le_3h": short_ep,
        "round_trips": rt,
        "eod_agreement_pct": round(agreement, 1),
    }


def main():
    df = replay()
    m = compute_metrics(df)

    print("\n" + "=" * 70)
    print("AC7 Metrics — Developer SPEC-107 vs Q076 P3 envelope")
    print("=" * 70)
    print(f"  intraday_flips      = {m['intraday_flips']}    target 93 ± 5  (88-98)")
    print(f"  episodes_le_3h      = {m['episodes_le_3h']}     target ≤ 4")
    print(f"  round_trips         = {m['round_trips']}        target 18 ± 2  (16-20)")
    print(f"  eod_agreement_pct   = {m['eod_agreement_pct']}%   target ≥ 92%")
    print(f"  n_bps_episodes      = {m['n_bps_episodes']}")
    print(f"  median_hold_hours   = {m['median_hold_hours']}")

    flips_pass = 88 <= m["intraday_flips"] <= 98
    short_pass = m["episodes_le_3h"] <= 4
    rt_pass = 16 <= m["round_trips"] <= 20
    eod_pass = m["eod_agreement_pct"] >= 92

    print("\nAC7 status:")
    print(f"  flips:           {'PASS' if flips_pass else 'FAIL'}")
    print(f"  ≤3h episodes:    {'PASS' if short_pass else 'FAIL'}")
    print(f"  round_trips:     {'PASS' if rt_pass else 'FAIL'}")
    print(f"  EOD agreement:   {'PASS' if eod_pass else 'FAIL'}")
    print(f"\nOverall AC7: {'PASS' if all([flips_pass, short_pass, rt_pass, eod_pass]) else 'FAIL'}")


if __name__ == "__main__":
    main()
