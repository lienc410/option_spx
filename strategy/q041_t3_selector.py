"""SPEC-115 Phase B — Q041 T3 earnings Iron Condor selector + close logic.

T-3 entry IC: ATM short straddle wings + 1.0× implied-move long protection (4 legs).
cash_need_usd = max_loss_usd (IC credit-spread BP requirement proxy, per 5/5 packet §4.3).
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
CHAINS_ROOT = REPO_ROOT / "data" / "q041_chains"

VIX_GATE = 15.0

T3_PARAMS: dict[str, dict] = {
    "q041_t3_cost_earnings_ic": {"underlying": "COST"},
    "q041_t3_jpm_earnings_ic":  {"underlying": "JPM"},
}


def _safe_filename(symbol: str) -> str:
    return symbol.lstrip("/").replace("/", "_")


def select_t3_earnings_ic(
    strategy_key: str,
    asof_date: str,
    earn_date: date,
    vix_now: float | None,
) -> dict | None:
    """Build T-3 IC candidate. Returns candidate dict or None on any failure.

    VIX gate is enforced by the caller; a defensive check here returns None too.
    """
    params = T3_PARAMS.get(strategy_key)
    if params is None:
        return None
    if vix_now is None or vix_now < VIX_GATE:
        return None

    sym = params["underlying"]
    chain_path = CHAINS_ROOT / asof_date / f"{_safe_filename(sym)}.parquet"
    und_path = CHAINS_ROOT / asof_date / "_underlying.parquet"
    if not chain_path.exists() or not und_path.exists():
        log.info("q041_t3: chain or underlying missing for %s %s", sym, asof_date)
        return None

    import pandas as pd
    df = pd.read_parquet(chain_path)
    und = pd.read_parquet(und_path)

    spot_row = und[und["symbol"] == sym]
    if spot_row.empty:
        return None
    spot = float(spot_row.iloc[0].get("close") or spot_row.iloc[0].get("last") or 0.0)
    if spot <= 0:
        return None

    # Step 3: earliest post-earnings expiry within DTE [1,14]
    df = df[(df["dte"] >= 1) & (df["dte"] <= 14)].copy()
    if df.empty:
        return None
    df["expiry_date"] = pd.to_datetime(df["expiry"]).dt.date
    df = df[df["expiry_date"] >= earn_date]
    if df.empty:
        return None
    target_expiry = df["expiry_date"].min()
    df = df[df["expiry_date"] == target_expiry]
    dte = int(df["dte"].iloc[0])

    # price column: prefer mid then close-equivalent
    price_col = "mid" if "mid" in df.columns else ("ask" if "ask" in df.columns else None)
    if price_col is None:
        return None

    # Step 4: ATM strike
    df["_strike_dist"] = (df["strike"] - spot).abs()
    atm_strike = float(df.sort_values("_strike_dist").iloc[0]["strike"])

    otype_col = "option_type"
    calls = df[df[otype_col].str.upper() == "CALL"]
    puts = df[df[otype_col].str.upper() == "PUT"]

    atm_call = calls[calls["strike"] == atm_strike]
    atm_put = puts[puts["strike"] == atm_strike]
    if atm_call.empty or atm_put.empty:
        return None
    atm_call_close = float(atm_call.iloc[0][price_col])
    atm_put_close = float(atm_put.iloc[0][price_col])

    # Step 5-7: straddle → implied move → 1.0× width
    straddle = atm_call_close + atm_put_close
    if straddle <= 0:
        return None
    implied_move_usd = straddle
    implied_move_pct = straddle / spot
    spread_width = implied_move_usd * 1.0

    # Step 8: long wings at ATM ± width (closest available strikes)
    k_long_put_target = atm_strike - spread_width
    k_long_call_target = atm_strike + spread_width
    puts = puts.copy()
    calls = calls.copy()
    puts["_dist"] = (puts["strike"] - k_long_put_target).abs()
    calls["_dist"] = (calls["strike"] - k_long_call_target).abs()
    if puts.empty or calls.empty:
        return None
    k_long_put = float(puts.sort_values("_dist").iloc[0]["strike"])
    k_long_call = float(calls.sort_values("_dist").iloc[0]["strike"])

    # Step 9: 4-leg prices
    def _price(side_df, strike):
        r = side_df[side_df["strike"] == strike]
        return float(r.iloc[0][price_col]) if not r.empty else None

    p_short_put = atm_put_close
    p_long_put = _price(puts, k_long_put)
    p_short_call = atm_call_close
    p_long_call = _price(calls, k_long_call)
    if p_long_put is None or p_long_call is None:
        return None

    # Step 10-11: net credit + max loss
    net_credit_ps = (p_short_put + p_short_call) - (p_long_put + p_long_call)
    if net_credit_ps <= 0:
        log.info("q041_t3: %s net credit <= 0 (%.2f) — skip", sym, net_credit_ps)
        return None
    net_credit_usd = round(net_credit_ps * 100.0, 2)
    width_pts = max(atm_strike - k_long_put, k_long_call - atm_strike)
    max_loss_ps = width_pts - net_credit_ps
    max_loss_usd = round(max_loss_ps * 100.0, 2)

    return {
        "strategy_key": strategy_key,
        "underlying": sym,
        "asof_date": asof_date,
        "earn_date": earn_date.isoformat(),
        "vix_entry": vix_now,
        "spot": round(spot, 2),
        "atm_strike": atm_strike,
        "implied_move_pct": round(implied_move_pct, 4),
        "implied_move_usd": round(implied_move_usd, 2),
        "spread_width_usd": round(spread_width, 2),
        "K_short_put": atm_strike,
        "K_long_put": k_long_put,
        "K_short_call": atm_strike,
        "K_long_call": k_long_call,
        "expiry": target_expiry.isoformat(),
        "dte": dte,
        "net_credit_usd": net_credit_usd,
        "max_loss_usd": max_loss_usd,
        "cash_need_usd": max_loss_usd,
        "imr_rank_pct": None,           # v1 skip (JPM optional IMR)
        "imr_check": "skipped",         # AC-10
        "contracts": 1,
        "paper_trade": True,
        "requested_bp_dollars": max_loss_usd,
        "sleeve": "q041_paper",
    }


def compute_ic_close_pnl(entry: dict, s_exit: float) -> dict:
    """SPEC-115 §2.7 — T+1 paper close PnL for an IC entry.

    neither strike breached → PnL = net_credit
    short put breached      → net_credit - min(max_loss, (K_short_put - s_exit) × 100)
    short call breached     → net_credit - min(max_loss, (s_exit - K_short_call) × 100)
    """
    k_put = float(entry["K_short_put"])
    k_call = float(entry["K_short_call"])
    net_credit = float(entry["net_credit_usd"])
    max_loss = float(entry["max_loss_usd"])

    breached = None
    if s_exit < k_put:
        breached = "put"
        loss = min(max_loss, (k_put - s_exit) * 100.0)
        pnl = net_credit - loss
    elif s_exit > k_call:
        breached = "call"
        loss = min(max_loss, (s_exit - k_call) * 100.0)
        pnl = net_credit - loss
    else:
        pnl = net_credit

    return {
        "s_exit": round(s_exit, 2),
        "breached": breached,           # None | "put" | "call"
        "strikes_held": breached is None,
        "paper_pnl_usd": round(pnl, 2),
        "net_credit_usd": net_credit,
        "max_loss_usd": max_loss,
    }
