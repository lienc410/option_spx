"""Q084 P2 — term-structure bracket for the P1 BS-flat calendar result.

P1's BS-flat sigma has a BOTH-SIGNED caveat (per
feedback_unquantified_caveat_sign_risk, quantify instead of hand-waving):

  FAV  (favorable): real calendars sell richer front vol
       -> entry short-leg IV = VIX x 1.02, rest flat  (debit lower)
  PESS (pessimistic): calm-regime contango at entry + spike backwardation
       at exit -> entry long-leg IV = VIX x 1.03 (debit higher); on exit,
       if vix rose, short-leg IV = VIX_exit x 1.05 (dearer to close).

K2 kill gate ($1,500/yr today-scale net) is evaluated against the bracket:
  - if even FAV < K2 -> kill robust across sign uncertainty
  - if PESS > K2     -> strategy robust (proceed)
  - else             -> ambiguous, escalate with quantified brackets
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path
from statistics import mean, median
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q082"))
from q082_p6_bcd_synth_reconstruction import (  # noqa: E402
    call_price, load_spx_history, load_vix_history,
)

SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
SHORT_DTE, LONG_DTE, ROLL_AT_DTE = 45, 90, 21
QQQ_OPP_RATE = 0.10

SCENARIOS = {
    #        entry_front entry_back exit_front_vixup exit_back_vixup
    "BASE": (1.00, 1.00, 1.00, 1.00),
    "FAV":  (1.02, 1.00, 1.00, 1.00),
    "PESS": (1.00, 1.03, 1.05, 1.00),
}


def simulate(entry_iso, spx, vix, ef, eb, xf_up, xb_up):
    if entry_iso not in spx or entry_iso not in vix:
        return None
    S0, v0 = spx[entry_iso], vix[entry_iso] / 100.0
    if v0 <= 0:
        return None
    K = round(S0 / 5) * 5
    debit = call_price(S0, K, LONG_DTE, v0 * eb) - call_price(S0, K, SHORT_DTE, v0 * ef)
    if debit <= 0:
        return None
    entry_dt = date.fromisoformat(entry_iso)
    cur_S, cur_v = S0, v0
    for dd in range(1, 50):
        cur_iso = (entry_dt + timedelta(days=dd)).isoformat()
        srem, lrem = max(0, SHORT_DTE - dd), max(0, LONG_DTE - dd)
        if cur_iso in spx:
            cur_S = spx[cur_iso]
        if cur_iso in vix:
            cur_v = vix[cur_iso] / 100.0
        if srem <= ROLL_AT_DTE and cur_iso in spx:
            vix_up = cur_v > v0
            xf = xf_up if vix_up else 1.00
            xb = xb_up if vix_up else 1.00
            pnl = (call_price(cur_S, K, lrem, cur_v * xb)
                   - call_price(cur_S, K, srem, cur_v * xf)) - debit
            return {"entry_date": entry_iso, "exit_date": cur_iso, "hold_days": dd,
                    "entry_spx": S0, "entry_debit_usd": debit * 100, "pnl_usd": pnl * 100}
    return None


def main():
    days = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            if (r["regime"] == "NORMAL" and r["iv_signal"] == "LOW"
                    and r["trend"] == "NEUTRAL" and not r["strategy_key"]):
                days.append(r["date"])
    days.sort()
    spx, vix = load_spx_history(), load_vix_history()
    priceable = [d for d in days if d >= min(spx)]
    spx_ref = spx[max(spx)]
    years = (date.fromisoformat(max(priceable)) - date.fromisoformat(min(priceable))).days / 365.25

    print(f"{'scenario':<8} {'n':>3} {'win%':>5} {'PnL(hist)':>10} {'net $/yr today':>15}  K2($1,500)")
    results = {}
    for name, (ef, eb, xf, xb) in SCENARIOS.items():
        trades, busy = [], ""
        for d in priceable:
            if d <= busy:
                continue
            t = simulate(d, spx, vix, ef, eb, xf, xb)
            if t:
                trades.append(t)
                busy = t["exit_date"]
        core = [t for t in trades if not t["entry_date"].startswith("2008")]
        scaled = sum(t["pnl_usd"] * spx_ref / t["entry_spx"] for t in core)
        opp = sum(t["entry_debit_usd"] * spx_ref / t["entry_spx"] * t["hold_days"] / 365 * QQQ_OPP_RATE
                  for t in core)
        net_yr = (scaled - opp) / years
        wins = sum(1 for t in core if t["pnl_usd"] > 0)
        verdict = "PASS" if net_yr >= 1500 else "below"
        print(f"{name:<8} {len(core):>3} {100*wins/len(core):>4.0f}% "
              f"${sum(t['pnl_usd'] for t in core):>9,.0f} ${net_yr:>13,.0f}/yr  {verdict}")
        results[name] = net_yr

    print()
    if results["FAV"] < 1500:
        print("VERDICT INPUT: even FAV bracket < $1,500/yr -> K2 kill robust across sign uncertainty")
    elif results["PESS"] >= 1500:
        print("VERDICT INPUT: even PESS bracket >= $1,500/yr -> strategy robust, proceed")
    else:
        print("VERDICT INPUT: brackets straddle K2 -> ambiguous, escalate with quantified numbers")


if __name__ == "__main__":
    main()
