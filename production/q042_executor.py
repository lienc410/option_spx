"""Q042 EOD Executor — Trigger evaluation + Telegram alert (F5, revised)

架構決策 (PM 2026-05-10): Telegram alert + 人手下单。
- 整個 repo 目前無 Schwab order automation endpoint
- ~1.5 trades/yr 頻率完全適合人工執行
- No Schwab API call in MVP; future order automation is a separate SPEC

Flow (post-close, ~16:15 ET):
  1. Fetch latest SPX close and VIX.
  2. Advance sleeve state machines (F1).
  3. For each sleeve that fires: check BP gate (F3), size the order (F2).
  4. Send Telegram alert with order details + manual execution instruction.
  5. Log pending entry to data/q042_paper_trades.jsonl.
     fill_debit and entry_time are back-filled by PM after manual execution.

Acceptance criteria:
  AC14: Telegram alert content matches the spec format (sleeve_id, strikes,
        DTE, est_debit, contracts, NLV, ddATH).
  AC16: Failed alert does NOT block daily main-strategy alerts.
  AC17: Pending trade record contains: sleeve_id (A/B), signal_date,
        ATH_at_signal, ddATH_at_signal, strikes, DTE, est_debit, contracts,
        NLV_at_entry; fill_debit / entry_time are null until PM back-fills.

Run with: python -m production.q042_executor [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

ET = ZoneInfo("America/New_York")
PAPER_LOG = REPO_ROOT / "data" / "q042_paper_trades.jsonl"
RUN_LOG   = REPO_ROOT / "logs" / "q042_executor.log"
TELEGRAM_TIMEOUT = 20


@dataclass
class PendingOrderSpec:
    sleeve_id: str
    signal_date: str
    entry_target_date: str
    long_strike: int
    short_strike: int
    contracts: int
    est_debit_per_contract: float
    nlv_at_signal: float
    ddath_at_signal: float
    ath_at_signal: float
    vix_at_signal: float
    spx_close: float


# ── Logging ───────────────────────────────────────────────────────────────────

def _logger(verbose: bool) -> logging.Logger:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("q042_executor")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(RUN_LOG)
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


# ── Telegram ──────────────────────────────────────────────────────────────────

def _telegram_creds() -> tuple[str, str]:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _send_telegram(text: str, log: logging.Logger, *, sleeve: str = "?") -> bool:
    # SPEC-126: trigger alerts are event-driven ACTION pushes through the
    # gateway (dedupe: one per sleeve per day); routine evaluations never
    # push — the 15:55 digest carries overlay state.
    try:
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
        from notify.gateway import escape, push as gw_push
        from datetime import date as _date
        # plain-text body → whole-body escape at the boundary (H-4)
        return gw_push("ACTION", "新开仓", "Q042 Drawdown Overlay 触发", escape(text),
                       dedupe_key=f"q042_trigger_{sleeve}_{_date.today().isoformat()}")
    except Exception:
        log.exception("telegram send failed")
        return False


def _format_alert(spec: PendingOrderSpec) -> str:
    """Build the F5 Telegram alert (AC14)."""
    return (
        f"\U0001f7e2 Q042 [Sleeve {spec.sleeve_id}] | SPX\n"
        f"Entry: T+1 open (manual) — {spec.entry_target_date}\n"
        f"Strikes: long K={spec.long_strike} / short K={spec.short_strike}\n"
        f"DTE: {30 if spec.sleeve_id == 'A' else 90}\n"
        f"Est debit: ${spec.est_debit_per_contract:,.0f} per contract\n"
        f"Contracts: {spec.contracts}\n"
        f"NLV at signal: ${spec.nlv_at_signal:,.0f}\n"
        f"ddATH at signal: {spec.ddath_at_signal*100:+.2f}%\n"
        f"→ Place SPX call spread at T+1 open"
    )


# ── Market data helpers ───────────────────────────────────────────────────────

def _fetch_spx_close() -> tuple[float, str]:
    df = yf.Ticker("^GSPC").history(period="5d", interval="1d")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return float(df["Close"].iloc[-1]), df.index[-1].strftime("%Y-%m-%d")


def _fetch_vix() -> float:
    df = yf.Ticker("^VIX").history(period="5d", interval="1d")
    return float(df["Close"].iloc[-1])


def _fetch_nlv() -> float:
    try:
        from schwab.client import get_account_balances
        bal = get_account_balances()
        # key is "net_liquidation" (Schwab API), not "net_liquidation_value"
        nlv = bal.get("net_liquidation") or bal.get("net_liquidation_value")
        return float(nlv) if nlv is not None else 0.0
    except Exception:
        return 0.0


# ── Pending record (AC17) ─────────────────────────────────────────────────────

def _write_pending_record(spec: PendingOrderSpec) -> None:
    """
    Write a pending trade record with null fill_debit / entry_time (AC17).
    PM back-fills these fields after manual order execution.
    """
    record = {
        "sleeve_id":        spec.sleeve_id,
        "signal_date":      spec.signal_date,
        "entry_target_date":spec.entry_target_date,
        "entry_time":       None,           # back-filled by PM
        "ath_at_signal":    round(spec.ath_at_signal, 2),
        "ddath_at_signal":  round(spec.ddath_at_signal, 4),
        "long_strike":      spec.long_strike,
        "short_strike":     spec.short_strike,
        "dte":              30 if spec.sleeve_id == "A" else 90,  # SPEC-094.1
        "est_debit":        round(spec.est_debit_per_contract, 2),
        "fill_debit":       None,           # back-filled by PM
        "contracts":        spec.contracts,
        "nlv_at_entry":     round(spec.nlv_at_signal, 2),
        "paper":            True,
        "settled":          False,
    }
    PAPER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PAPER_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


# ── EOD evaluation ────────────────────────────────────────────────────────────

def run_eod_evaluation(
    dry_run: bool = False,
    verbose: bool = False,
) -> list[PendingOrderSpec]:
    """
    Full EOD evaluation cycle. Returns list of PendingOrderSpec that fired.
    AC16: exceptions here must not propagate to main-strategy flows.
    """
    log = _logger(verbose)
    fired: list[PendingOrderSpec] = []

    try:
        from signals.q042_trigger import (
            load_state, save_state, update_sleeve_a, update_sleeve_b,
        )
        from strategy.q042_gate import compute_gate, log_gate, read_main_bp_pct
        from strategy.q042_sizing import compute_sizing

        spx_close, today_str = _fetch_spx_close()
        vix = _fetch_vix()
        nlv = _fetch_nlv()
        log.info(f"EOD eval {today_str} SPX={spx_close:.0f} VIX={vix:.2f} NLV=${nlv:,.0f}")

        state = load_state()

        ath = max(state.get("ath_running_max", 0.0), spx_close)
        state["ath_running_max"] = ath
        state["ath_last_update"] = today_str
        ddath = spx_close / ath - 1.0

        spx_hist = yf.Ticker("^GSPC").history(period="1mo", interval="1d")
        ma10 = float(spx_hist["Close"].iloc[-10:].mean())
        cal = pd.DatetimeIndex(pd.to_datetime(spx_hist.index).tz_localize(None))

        main_bp = read_main_bp_pct()
        gate = compute_gate(main_bp, today_str)
        log_gate(gate)
        log.info(f"gate: main_bp={main_bp:.1f}% cap={gate.q042_combined_cap:.1f}%")

        entry_date  = (datetime.strptime(today_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        # Expiry is DTE from entry (T+1), not signal (T). Aligns with backtest engine fix (R-20260510-15).
        expiry_a    = (datetime.strptime(entry_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")  # SPEC-094.1
        expiry_b    = (datetime.strptime(entry_date, "%Y-%m-%d") + timedelta(days=90)).strftime("%Y-%m-%d")  # Sleeve B unchanged

        act_a = update_sleeve_a(state["sleeve_a"], ddath, today_str)
        if act_a["action"] == "fire_A" and gate.sleeve_a_allowance > 0:
            long_k, short_k, contracts, est = compute_sizing(nlv, spx_close, vix, "A")
            if contracts > 0:
                spec = PendingOrderSpec(
                    sleeve_id="A", signal_date=today_str, entry_target_date=entry_date,
                    long_strike=long_k, short_strike=short_k, contracts=contracts,
                    est_debit_per_contract=est, nlv_at_signal=nlv,
                    ddath_at_signal=ddath, ath_at_signal=ath, vix_at_signal=vix,
                    spx_close=spx_close,
                )
                sent = _send_telegram(_format_alert(spec), log, sleeve=spec.sleeve_id)
                if sent or not dry_run:
                    _write_pending_record(spec)
                fired.append(spec)
                state["sleeve_a"]["active_position_id"] = f"A-{today_str}"
                state["sleeve_a"]["active_position_expiry"] = expiry_a

        act_b = update_sleeve_b(state["sleeve_b"], ddath, spx_close, ma10, today_str, cal)
        if act_b["action"] == "fire_B" and gate.sleeve_b_allowance > 0:
            long_k, short_k, contracts, est = compute_sizing(nlv, spx_close, vix, "B")
            if contracts > 0:
                spec = PendingOrderSpec(
                    sleeve_id="B", signal_date=today_str, entry_target_date=entry_date,
                    long_strike=long_k, short_strike=short_k, contracts=contracts,
                    est_debit_per_contract=est, nlv_at_signal=nlv,
                    ddath_at_signal=ddath, ath_at_signal=ath, vix_at_signal=vix,
                    spx_close=spx_close,
                )
                sent = _send_telegram(_format_alert(spec), log, sleeve=spec.sleeve_id)
                if sent or not dry_run:
                    _write_pending_record(spec)
                fired.append(spec)
                state["sleeve_b"]["active_position_id"] = f"B-{today_str}"
                state["sleeve_b"]["active_position_expiry"] = expiry_b

        save_state(state)

    except Exception:
        log.exception("EOD evaluation failed — main-strategy flows unaffected (AC16)")

    return fired


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Q042 EOD executor (Telegram-only)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    specs = run_eod_evaluation(dry_run=args.dry_run, verbose=args.verbose)
    print(f"fired {len(specs)} sleeve(s)")
    for s in specs:
        print(f"  Sleeve {s.sleeve_id}: {s.long_strike}/{s.short_strike} ×{s.contracts} ct")
