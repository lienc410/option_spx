"""SPEC-115 Phase A — Q041 T2 CSP daily chain selector.

Reads the Schwab chain parquet for a given underlying and date,
finds the best-fit short-put leg (by delta + DTE targets), and returns
a governance candidate dict with cash_need_usd = K × 100.

Chain data: data/q041_chains/<YYYY-MM-DD>/<SYMBOL>.parquet
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
CHAIN_ROOT = REPO_ROOT / "data" / "q041_chains"

# T2 strategy config: delta target, DTE target, tolerance
_T2_CONFIG: dict[str, dict[str, Any]] = {
    "q041_t2_googl_csp": {
        "underlying": "GOOGL",
        "delta_target": 0.20,
        "delta_tol": 0.05,
        "dte_target": 21,
        "dte_tol": 3,
        "min_close": 0.10,
        "contracts": 1,
    },
    "q041_t2_amzn_csp": {
        "underlying": "AMZN",
        "delta_target": 0.25,
        "delta_tol": 0.05,
        "dte_target": 21,
        "dte_tol": 3,
        "min_close": 0.10,
        "contracts": 1,
    },
}


def _safe_filename(symbol: str) -> str:
    return symbol.lstrip("/").replace("/", "_")


def select_t2_csp(strategy_key: str, asof_date: str | date) -> dict | None:
    """Select the best short-put leg from the chain for a T2 CSP strategy.

    Args:
        strategy_key: "q041_t2_googl_csp" or "q041_t2_amzn_csp"
        asof_date: YYYY-MM-DD string or date object

    Returns:
        Candidate dict suitable for sleeve_governance.evaluate_candidate(), or None.

    Candidate fields:
        strategy_key, underlying, short_strike, delta, dte, close,
        cash_need_usd (= K × 100 × contracts), paper_trade=True,
        expiry, contracts
    """
    cfg = _T2_CONFIG.get(strategy_key)
    if cfg is None:
        log.warning("q041_selector: unknown strategy_key %r", strategy_key)
        return None

    if isinstance(asof_date, date):
        date_str = asof_date.isoformat()
    else:
        date_str = str(asof_date)[:10]

    chain_path = CHAIN_ROOT / date_str / f"{_safe_filename(cfg['underlying'])}.parquet"
    if not chain_path.exists():
        log.info("q041_selector: chain missing for %s on %s", cfg["underlying"], date_str)
        return None

    try:
        import pandas as pd
        df = pd.read_parquet(chain_path)
    except Exception as exc:
        log.warning("q041_selector: failed to read chain %s: %s", chain_path, exc)
        return None

    # Filter to PUT legs
    if "option_type" in df.columns:
        df = df[df["option_type"].str.upper() == "PUT"]
    elif "putCall" in df.columns:
        df = df[df["putCall"].str.upper() == "PUT"]

    if df.empty:
        log.info("q041_selector: no PUT rows in chain for %s %s", cfg["underlying"], date_str)
        return None

    # Use absolute delta for filtering (chain may store negative delta for puts)
    delta_col = "delta" if "delta" in df.columns else None
    if delta_col is None:
        log.warning("q041_selector: no delta column in chain %s", chain_path)
        return None

    df = df.copy()
    df["_abs_delta"] = df[delta_col].abs()

    # Price column
    price_col = "mid" if "mid" in df.columns else ("ask" if "ask" in df.columns else None)
    if price_col is None:
        log.warning("q041_selector: no price column in chain %s", chain_path)
        return None

    # Filter by delta band, DTE band, min close
    dt = cfg["delta_target"]
    dtol = cfg["delta_tol"]
    dte_t = cfg["dte_target"]
    dte_tol = cfg["dte_tol"]

    mask = (
        df["_abs_delta"].between(dt - dtol, dt + dtol)
        & df["dte"].between(dte_t - dte_tol, dte_t + dte_tol)
        & (df[price_col] >= cfg["min_close"])
    )
    candidates = df[mask]

    if candidates.empty:
        log.info(
            "q041_selector: no candidates in band δ%.2f±%.2f DTE%d±%d for %s %s",
            dt, dtol, dte_t, dte_tol, cfg["underlying"], date_str,
        )
        return None

    # Best fit: minimize |delta - target| then |dte - target|
    candidates = candidates.copy()
    candidates["_delta_err"] = (candidates["_abs_delta"] - dt).abs()
    candidates["_dte_err"] = (candidates["dte"] - dte_t).abs()
    best = candidates.sort_values(["_delta_err", "_dte_err"]).iloc[0]

    strike = float(best["strike"])
    n = cfg["contracts"]
    cash_need = strike * 100.0 * n

    expiry = str(best.get("expiry", ""))
    dte_val = int(best.get("dte", dte_t))
    delta_val = float(best["_abs_delta"])
    close_val = float(best[price_col])

    return {
        "strategy_key": strategy_key,
        "underlying": cfg["underlying"],
        "short_strike": strike,
        "delta": delta_val,
        "dte": dte_val,
        "expiry": expiry,
        "close": close_val,
        "contracts": n,
        "cash_need_usd": round(cash_need, 2),
        "paper_trade": True,
        "asof_date": date_str,
        # Fields expected by sleeve_governance BP checks (CSP uses strike-based BP)
        "requested_bp_dollars": cash_need,
        "sleeve": "q041_paper",
    }
