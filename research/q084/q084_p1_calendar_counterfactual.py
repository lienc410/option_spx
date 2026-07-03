"""Q084 P1 — ATM calendar counterfactual on NORMAL x IV_LOW x NEUTRAL days.

Universe: the 182 blocked days (26y) that route to reduce_wait with zero
strategy coverage. Structure: ATM call calendar — long 90 DTE / short 45 DTE
at the SAME spot-nearest strike (net +vega, delta-neutral at entry).
Exit convention identical to Q082/Q083 BCD sims: short leg reaches 21 DTE.

Reuses Q082 P6 BS-flat pricing machinery (sys.path import, like Q083 P11).

Methodology caveats (inherit Q082 P6 §1-5, plus one calendar-specific):
  C1. BS-flat sigma applies the SAME vol to both legs. Real vol expansion
      lifts front-month IV MORE than back-month (term structure inverts),
      which hurts the short 45d leg more than the model shows. BS-flat
      therefore OVERSTATES calendar gains from vol expansion.
      -> P2 must bracket with a term-structure stress before any ratify ask.

Layer-1 screen (framing memo par.2): 2008 days simulated but reported
separately; headline metrics exclude them.

Pre-registered kill gates (framing memo par.4):
  K1: Layer-1-screened tradeable days < 120 -> DOCUMENT and stop
  K2: pessimistic-bracket net at today scale < $1,500/yr -> DOCUMENT
      (P1 reports base bracket; K2 formally evaluated at P2)
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q082"))
from q082_p6_bcd_synth_reconstruction import (  # noqa: E402
    call_price, load_spx_history, load_vix_history, find_next_trading_day,
)
from datetime import date, timedelta  # noqa: E402

SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
TRADES_OUT = ROOT / "research" / "q084" / "q084_p1_calendar_trades.csv"

SHORT_DTE, LONG_DTE, ROLL_AT_DTE = 45, 90, 21
QQQ_OPP_RATE = 0.10  # opportunity cost on occupied cash (house convention)


def simulate_calendar(entry_iso: str, spx: dict, vix: dict) -> dict | None:
    """ATM call calendar: long 90 DTE + short 45 DTE at same spot-nearest strike."""
    if entry_iso not in spx or entry_iso not in vix:
        return None
    S0, sigma0 = spx[entry_iso], vix[entry_iso] / 100.0
    if sigma0 <= 0:
        return None
    K = round(S0 / 5) * 5
    long_entry = call_price(S0, K, LONG_DTE, sigma0)
    short_entry = call_price(S0, K, SHORT_DTE, sigma0)
    debit = long_entry - short_entry
    if debit <= 0:
        return None

    entry_dt = date.fromisoformat(entry_iso)
    cur_S, cur_sigma = S0, sigma0
    for delta_days in range(1, 50):
        cur_dt = entry_dt + timedelta(days=delta_days)
        cur_iso = cur_dt.isoformat()
        short_rem = max(0, SHORT_DTE - delta_days)
        long_rem = max(0, LONG_DTE - delta_days)
        if cur_iso in spx:
            cur_S = spx[cur_iso]
        if cur_iso in vix:
            cur_sigma = vix[cur_iso] / 100.0
        if short_rem <= ROLL_AT_DTE and cur_iso in spx:
            long_exit = call_price(cur_S, K, long_rem, cur_sigma)
            short_exit = call_price(cur_S, K, short_rem, cur_sigma)
            pnl = (long_exit - short_exit) - debit
            return {
                "entry_date": entry_iso, "exit_date": cur_iso,
                "hold_days": delta_days, "strike": K,
                "entry_spx": round(S0, 2), "exit_spx": round(cur_S, 2),
                "entry_vix": round(sigma0 * 100, 2),
                "exit_vix": round(cur_sigma * 100, 2),
                "entry_debit_usd": round(debit * 100, 2),
                "pnl_usd": round(pnl * 100, 2),
                "period_roe": round(pnl / debit, 4),
            }
    return None


def main():
    days = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            if (r["regime"] == "NORMAL" and r["iv_signal"] == "LOW"
                    and r["trend"] == "NEUTRAL" and not r["strategy_key"]):
                days.append(r["date"])
    days.sort()
    print(f"Universe: {len(days)} NORMAL x IV_LOW x NEUTRAL blocked days")

    spx, vix = load_spx_history(), load_vix_history()
    priceable = [d for d in days if d >= min(spx)]
    print(f"Priceable (>= {min(spx)}): {len(priceable)} "
          f"(dropped {len(days)-len(priceable)} pre-2003 days, no SPX cache)")

    # Sequential ladder: max 1 concurrent
    trades, busy_until = [], ""
    for d in priceable:
        if d <= busy_until:
            continue
        t = simulate_calendar(d, spx, vix)
        if t:
            trades.append(t)
            busy_until = t["exit_date"]

    with open(TRADES_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
        w.writeheader()
        w.writerows(trades)
    print(f"wrote {TRADES_OUT} ({len(trades)} trades)")

    # Layer-1 screen: 2008 separated
    t2008 = [t for t in trades if t["entry_date"].startswith("2008")]
    core = [t for t in trades if not t["entry_date"].startswith("2008")]
    core_days = [d for d in priceable if not d.startswith("2008")]
    print(f"\nK1 gate: Layer-1-screened days = {len(core_days)} (>=120 required)")

    def report(label, tt):
        if not tt:
            print(f"\n--- {label}: no trades ---")
            return
        pnls = [t["pnl_usd"] for t in tt]
        roes = [t["period_roe"] for t in tt]
        wins = sum(1 for p in pnls if p > 0)
        debits = sorted(t["entry_debit_usd"] for t in tt)
        neg = [r for r in roes if r < 0]
        dd = (sum(r * r for r in neg) / len(roes)) ** 0.5 if neg else 0.0
        sortino = (mean(roes) / dd) if dd > 0 else float("inf")
        worst = min(tt, key=lambda t: t["pnl_usd"])
        k = max(1, round(0.10 * len(pnls)))
        cvar10 = mean(sorted(pnls)[:k])
        print(f"\n--- {label} (n={len(tt)}) ---")
        print(f"  win {wins}/{len(tt)} = {100*wins/len(tt):.0f}%   "
              f"total PnL ${sum(pnls):,.0f}   mean ${mean(pnls):,.0f}/trade")
        print(f"  debit median ${debits[len(debits)//2]:,.0f}   "
              f"ROE mean {mean(roes):+.1%} / median {median(roes):+.1%}")
        print(f"  Sortino(per-trade, exit-day) {sortino:.2f}   "
              f"worst {worst['entry_date']} ${worst['pnl_usd']:,.0f} ({worst['period_roe']:+.1%})")
        print(f"  CVaR10% ${cvar10:,.0f}/trade")
        return pnls

    report("CORE (ex-2008)", core)
    report("2008 (Layer-1, reported separately)", t2008)

    # Today-scale annual net (linear scaling like Q083 P15)
    spx_ref = spx[max(spx)]
    years = (date.fromisoformat(max(priceable)) - date.fromisoformat(min(priceable))).days / 365.25
    scaled_pnl = sum(t["pnl_usd"] * spx_ref / t["entry_spx"] for t in core)
    opp = sum(t["entry_debit_usd"] * spx_ref / t["entry_spx"] * t["hold_days"] / 365 * QQQ_OPP_RATE
              for t in core)
    net_yr = (scaled_pnl - opp) / years
    med_debit_scaled = median(t["entry_debit_usd"] * spx_ref / t["entry_spx"] for t in core)
    print(f"\n--- Today-scale (SPX_ref={spx_ref:.0f}, span {years:.1f}y) ---")
    print(f"  scaled PnL ${scaled_pnl:,.0f}  opp cost ${opp:,.0f}  "
          f"NET ${scaled_pnl-opp:,.0f} = ${net_yr:,.0f}/yr")
    print(f"  median debit at today scale: ${med_debit_scaled:,.0f} "
          f"(vs SPEC-111 cap at $61.4k cash: ${0.6*61415:,.0f})")
    print(f"  K2 reference (formal at P2 pessimistic bracket): ${net_yr:,.0f}/yr vs $1,500/yr")

    # Vol-expansion attribution: PnL when exit_vix > entry_vix vs not
    up = [t for t in core if t["exit_vix"] > t["entry_vix"]]
    dn = [t for t in core if t["exit_vix"] <= t["entry_vix"]]
    print(f"\n--- +vega attribution (core) ---")
    print(f"  vix UP at exit:   n={len(up)}  mean ${mean(t['pnl_usd'] for t in up):,.0f}")
    print(f"  vix DOWN at exit: n={len(dn)}  mean ${mean(t['pnl_usd'] for t in dn):,.0f}")


if __name__ == "__main__":
    main()
