"""Q091 P0 — Crash BP reserve floor (deterministic scenario grid).

Question (BP-utilization reaudit ②, PM approved 2026-07-07): how much of
today's BP headroom is actually deployable, once the crash-day joint claim
on it is priced in? Idle BP is the crash absorber for a beta-heavy book —
in a 2008-replay equity MV falls, house PM haircuts RISE, and short-premium
margin expands. The reserve the book needs at the worst point puts a floor
under "deployable BP". This is risk arithmetic, not statistics: no fitting,
no p-values; the scenario/haircut grid is an assumption set for PM
ratification.

Model (per broker, then combined):
    E(dd)      = equity_mv × (1 − dd × beta_eff)          # equity book value
    NLV(dd)    = E(dd) + cash − L_opt                     # options sleeve at max loss
    Maint(dd)  = E(dd) × h0 × k                           # haircut escalation k
    Excess(dd) = NLV(dd) − Maint(dd)                      # < 0 ⇒ forced liquidation

    h0 = today's measured blended haircut = maint_today / equity_mv_today
         (uses the broker's own number, incl. current options margin — see
         LIMITATIONS in the memo)

Deployable new BP today = min over ratified scenarios of Excess(dd) − buffer,
divided by the new position type's own crash expansion multiple
(defined-risk spread: 1.0×; naked put: computed below for T2 GOOGL/AMZN).

Usage (on Old Air, where broker tokens live):
    ./venv/bin/python research/q091/q091_p0_crash_bp_reserve.py [--offline SNAP.json]
Writes research/q091/q091_p0_grid.csv + q091_p0_snapshot.json and prints a summary.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "research" / "q091"
ET = ZoneInfo("America/New_York")

# ── Scenario grid (assumption set — PM to ratify) ─────────────────────────────
# dd: index peak-to-trough draw on the beta book's benchmark
# k:  house PM haircut escalation multiple on today's blended haircut.
#     History anchor: brokers raised PM house requirements toward 30%+ on
#     concentrated books in 2008-Q4 / 2020-03; base haircut today ≈ 15-20%,
#     so k=1.5–2.0 spans "haircut doubles".
SCENARIOS = [
    # (name, dd, beta_eff, k)
    ("2022_grind",  0.25, 1.0, 1.0),
    ("2022_grind_haircut1.5", 0.25, 1.0, 1.5),
    ("2020_crash",  0.34, 1.0, 1.5),
    ("2020_crash_beta1.2", 0.34, 1.2, 1.5),
    ("2008_replay", 0.45, 1.0, 1.5),
    ("2008_replay_haircut2x", 0.45, 1.0, 2.0),
    ("2008_replay_beta1.2_h2x", 0.45, 1.2, 2.0),
]

# Single-name overnight gap for the T2 naked-put expansion multiple
NAKED_GAP = 0.30
PM_STRESS_PCT = 0.15   # max(15%×spot − OTM, 10%×K) per-share entry margin
PM_MIN_PCT = 0.10


def live_snapshot() -> dict:
    """Pull both brokers: cash, maint margin, NLV, equity MV, options sleeve
    max loss. Options sleeve: open cash-occupying positions (BCD debit =
    max loss) + defined-risk SPX spreads (width − credit ≈ max loss) read
    from position state."""
    snap: dict = {"ts": datetime.now(ET).isoformat(timespec="seconds"), "brokers": {}}

    from schwab.client import get_account_balances as sb, get_account_positions as sp
    from etrade.client import get_account_balances as eb, get_account_positions as ep

    for name, bal_fn, pos_fn in (("schwab", sb, sp), ("etrade", eb, ep)):
        bal = bal_fn()
        positions = (pos_fn() or {}).get("positions") or []
        equity_mv = 0.0
        for p in positions:
            at = str(p.get("asset_type") or "").upper()
            mv = p.get("market_value")
            if at in ("EQUITY", "ETF", "COLLECTIVE_INVESTMENT", "MUTUAL_FUND", "EQ") and mv:
                equity_mv += float(mv)
        snap["brokers"][name] = {
            "nlv": float(bal.get("net_liquidation") or 0.0),
            "cash": float(bal.get("cash_balance") or 0.0),
            "maint": float(bal.get("maintenance_margin") or 0.0),
            "option_bp": float(bal.get("option_buying_power")
                               or bal.get("buying_power") or 0.0),
            "equity_mv": round(equity_mv, 2),
            "n_positions": len(positions),
        }

    # options sleeve max loss — cash-occupying book (BCD debits) is the
    # dominant defined-risk exposure today; SPX spreads read from state
    from strategy.cash_budget_governance import get_open_cash_collateral_total_usd
    snap["options_sleeve_max_loss"] = float(
        (get_open_cash_collateral_total_usd() or {}).get("total") or 0.0)

    # spots for naked-put expansion examples (T2 candidates)
    spots = {}
    try:
        import yfinance as yf
        for sym in ("GOOGL", "AMZN"):
            h = yf.Ticker(sym).history(period="1d")
            if len(h):
                spots[sym] = round(float(h["Close"].iloc[-1]), 2)
    except Exception:
        pass
    snap["spots"] = spots
    return snap


def run_grid(snap: dict) -> list[dict]:
    rows = []
    L_opt = snap["options_sleeve_max_loss"]
    for name, dd, beta, k in SCENARIOS:
        combined = {"scenario": name, "dd": dd, "beta_eff": beta, "haircut_x": k}
        tot_excess = tot_nlv = tot_maint = 0.0
        for broker, b in snap["brokers"].items():
            h0 = (b["maint"] / b["equity_mv"]) if b["equity_mv"] else 0.0
            e_dd = b["equity_mv"] * max(0.0, 1.0 - dd * beta)
            # options max loss charged once, to the broker holding most of it
            # (both BCDs split schwab/etrade — split L_opt by half each for P0)
            l_opt_b = L_opt / 2.0
            nlv = e_dd + b["cash"] - l_opt_b
            maint = e_dd * min(h0 * k, 1.0)
            combined[f"{broker}_excess"] = round(nlv - maint, 0)
            combined[f"{broker}_h0"] = round(h0, 3)
            tot_excess += nlv - maint
            tot_nlv += nlv
            tot_maint += maint
        combined["combined_nlv"] = round(tot_nlv, 0)
        combined["combined_maint"] = round(tot_maint, 0)
        combined["combined_excess"] = round(tot_excess, 0)
        rows.append(combined)
    return rows


def naked_put_expansion(snap: dict, k_strike_frac: float = 0.92) -> list[dict]:
    """T2 naked-put crash multiple: entry PM margin vs claim after a
    NAKED_GAP single-name gap (margin + realized intrinsic loss both draw
    on the same excess pool). k_strike_frac ≈ Δ0.20-0.25 strike ≈ 8% OTM."""
    out = []
    for sym, s0 in (snap.get("spots") or {}).items():
        strike = round(s0 * k_strike_frac)
        otm = s0 - strike
        m_entry = max(PM_STRESS_PCT * s0 - otm, PM_MIN_PCT * strike) * 100
        s_gap = s0 * (1.0 - NAKED_GAP)
        intrinsic = max(strike - s_gap, 0.0) * 100
        m_gap = (PM_STRESS_PCT * s_gap) * 100 + intrinsic  # ITM: stress + intrinsic
        total_claim = m_gap  # margin claim; intrinsic loss additionally hits NLV
        out.append({
            "symbol": sym, "spot": s0, "strike": strike,
            "entry_margin_per_contract": round(m_entry, 0),
            "gap30_margin_per_contract": round(m_gap, 0),
            "gap30_nlv_loss_per_contract": round(intrinsic, 0),
            "expansion_multiple": round(total_claim / m_entry, 1) if m_entry else None,
            "cash_secured_per_contract": strike * 100,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", help="reuse a saved snapshot json instead of live pull")
    args = ap.parse_args()

    if args.offline:
        snap = json.loads(Path(args.offline).read_text())
    else:
        snap = live_snapshot()
        (OUT_DIR / "q091_p0_snapshot.json").write_text(
            json.dumps(snap, indent=1, sort_keys=True))

    rows = run_grid(snap)
    naked = naked_put_expansion(snap)

    with (OUT_DIR / "q091_p0_grid.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("=== Q091 P0 — snapshot ===")
    for broker, b in snap["brokers"].items():
        print(f"{broker}: nlv=${b['nlv']:,.0f} cash=${b['cash']:,.0f} "
              f"equity_mv=${b['equity_mv']:,.0f} maint=${b['maint']:,.0f} "
              f"(h0={b['maint']/b['equity_mv']:.1%})" if b["equity_mv"] else broker)
    print(f"options sleeve max loss: ${snap['options_sleeve_max_loss']:,.0f}")
    print()
    print("=== scenario grid (combined excess = crash-day BP cushion) ===")
    for r in rows:
        print(f"{r['scenario']:28s} dd={r['dd']:.0%} β={r['beta_eff']} k={r['haircut_x']}"
              f"  → excess ${r['combined_excess']:>12,.0f}"
              f"  (schwab ${r['schwab_excess']:,.0f} / etrade ${r['etrade_excess']:,.0f})")
    print()
    print("=== T2 naked-put crash expansion (per contract) ===")
    for n in naked:
        print(f"{n['symbol']}: entry ${n['entry_margin_per_contract']:,.0f} → "
              f"gap-30% claim ${n['gap30_margin_per_contract']:,.0f} "
              f"({n['expansion_multiple']}x) + NLV loss ${n['gap30_nlv_loss_per_contract']:,.0f}"
              f"  [cash-secured: ${n['cash_secured_per_contract']:,.0f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
