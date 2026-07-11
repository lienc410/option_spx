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


def _send_gateway(category: str, about: str, title: str, body: str,
                  dedupe_key: str, log: logging.Logger) -> bool:
    # SPEC-126: trigger alerts are event-driven pushes through the gateway
    # (dedupe: one per key per ET day); routine evaluations never push — the
    # 15:55 digest carries overlay state.
    try:
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
        from notify.gateway import escape, push as gw_push
        # plain-text body → whole-body escape at the boundary (H-4)
        return gw_push(category, about, title, escape(body), dedupe_key=dedupe_key)
    except Exception:
        log.exception("telegram send failed")
        return False


def _cash_context_line() -> str:
    """SPEC-094.2 F5b (Q093 P1 R-a): current cash context appended to every
    trigger alert so the PM sees pool余量 at execution time. Fully isolated —
    any failure degrades the single line to n/a, never blocks the alert (AC16)."""
    try:
        from strategy.cash_budget_governance import (
            get_current_liquid_cash, get_open_debit_total_usd,
        )
        liquid = get_current_liquid_cash().get("total")
        debit = get_open_debit_total_usd().get("total")
        liquid_s = f"${liquid:,.0f}" if liquid is not None else "n/a"
        debit_s = f"${debit:,.0f}" if debit is not None else "n/a"
        return f"Liquid cash {liquid_s} · 在场 debit 合计 {debit_s}"
    except Exception:
        return "Liquid cash n/a · 在场 debit 合计 n/a"


def _format_alert(spec: PendingOrderSpec) -> str:
    """Build the F5 Telegram alert (AC14)."""
    return (
        f"\U0001f7e2 Drawdown Overlay [Sleeve {spec.sleeve_id}] · SPX\n"
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

def _process_sleeve_fire(
    *, sleeve_id: str, state: dict, gate, gate_available: bool,
    nlv: float, spx_close: float, vix: float, ddath: float, ath: float,
    today_str: str, entry_date: str, expiry: str, dry_run: bool,
    log: logging.Logger, gate_unavail_dedupe: str,
) -> Optional[PendingOrderSpec]:
    """Handle one sleeve's fire: gate check → sizing → fire or F5 blocked path.

    Returns the PendingOrderSpec on a real (or would-be, in dry-run) fire, else
    None when held. The armed flag is ALREADY consumed by update_sleeve_* — that
    trigger semantic is invariant (漏单 is solved by F3 data + F5 auditability,
    not by re-arming). A held fire NEVER sets active_position_id.
    """
    from strategy.q042_gate import log_blocked_fire
    from strategy.q042_sizing import compute_sizing

    allowance = 0.0
    if gate_available and gate is not None:
        allowance = gate.sleeve_a_allowance if sleeve_id == "A" else gate.sleeve_b_allowance

    # Would-be sizing (computed regardless, for the counterfactual record).
    long_k, short_k, contracts, est = compute_sizing(nlv, spx_close, vix, sleeve_id)
    contracts = int(contracts or 0)

    blocked_reason: Optional[str] = None
    if not gate_available:
        blocked_reason = "gate_unavailable"                       # F3 fail-closed
    elif allowance <= 0:
        blocked_reason = ("sleeve_b_production_cap_0_by_design"   # N2
                          if sleeve_id == "B" else "gate_binding_allowance_0")
    elif contracts <= 0:
        blocked_reason = "contracts_0"                            # NLV<$200k / debit过贵

    if blocked_reason is not None:
        if not dry_run:                                          # B6: no disk in dry-run
            log_blocked_fire(sleeve_id, blocked_reason, contracts, ddath, date=today_str)
        is_by_design = blocked_reason == "sleeve_b_production_cap_0_by_design"
        category = "FYI" if is_by_design else "ACTION"          # N2 degrade
        if blocked_reason == "gate_unavailable":
            dedupe = gate_unavail_dedupe                         # N6 merge into one
        else:
            dedupe = f"q042_blocked_{sleeve_id}_{today_str}"
        est_s = f" @ ${est:,.0f}/ct" if est else ""
        body = (
            f"⛔ Drawdown Overlay [Sleeve {sleeve_id}] 触发但被拦截\n"
            f"原因: {blocked_reason}\n"
            f"ddATH: {ddath*100:+.2f}%\n"
            f"Would-be sizing: {contracts} ct{est_s}\n"
            + ("此为设计内拦截（Sleeve B 生产 cap=0），仅 FYI。\n" if is_by_design
               else "请人工核查。\n")
            + "PM 若手动入场须经 /api/q042/position/open 记录并同步 trigger state。\n"
            + _cash_context_line()
        )
        if not dry_run:
            _send_gateway(category, "新开仓", "Drawdown Overlay（回撤加仓）被拦截",
                          body, dedupe, log)
        else:
            log.info("[dry-run] WOULD BLOCK Sleeve %s: %s (would-be %d ct)",
                     sleeve_id, blocked_reason, contracts)
        return None

    # ── Real fire ─────────────────────────────────────────────────────────────
    spec = PendingOrderSpec(
        sleeve_id=sleeve_id, signal_date=today_str, entry_target_date=entry_date,
        long_strike=long_k, short_strike=short_k, contracts=contracts,
        est_debit_per_contract=est, nlv_at_signal=nlv,
        ddath_at_signal=ddath, ath_at_signal=ath, vix_at_signal=vix,
        spx_close=spx_close,
    )
    if dry_run:
        log.info("[dry-run] WOULD FIRE Sleeve %s: %s/%s x%d ct est $%.0f/ct",
                 sleeve_id, long_k, short_k, contracts, est or 0.0)
        return spec

    body = _format_alert(spec) + "\n" + _cash_context_line()
    _send_gateway("ACTION", "新开仓", "Drawdown Overlay（回撤加仓）触发",
                  body, f"q042_trigger_{sleeve_id}_{today_str}", log)
    _write_pending_record(spec)
    key = "sleeve_a" if sleeve_id == "A" else "sleeve_b"
    state[key]["active_position_id"] = f"{sleeve_id}-{today_str}"
    state[key]["active_position_expiry"] = expiry
    return spec


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
        import copy

        from signals.q042_trigger import (
            load_state, save_state, update_sleeve_a, update_sleeve_b,
        )
        from strategy.q042_gate import compute_gate, log_gate, read_main_bp_source
        from production.q042_positions import (
            settle_expired_positions, get_active_committed_debit_usd,
        )

        spx_close, today_str = _fetch_spx_close()
        vix = _fetch_vix()
        nlv = _fetch_nlv()
        log.info(f"EOD eval {today_str} SPX={spx_close:.0f} VIX={vix:.2f} NLV=${nlv:,.0f}")

        # ── F1: settle expired positions BEFORE advancing state machines ──────
        # N3: settle first, THEN load_state — never hold a pre-settle copy that
        # the末尾 save_state would use to overwrite settle's on-disk cleanup.
        # N9: pass today_str (data-date) into settle. B6: dry-run = no disk.
        settled_sleeves: list[str] = []
        for paper_flag in (True, False):
            try:
                settled = settle_expired_positions(
                    spx_close, today=today_str, paper=paper_flag, dry_run=dry_run,
                )
                settled_sleeves.extend(settled)
                if settled:
                    tag = "would-settle" if dry_run else "settled"
                    log.info("F1 %s (%s ledger): %s",
                             tag, "paper" if paper_flag else "live", settled)
            except Exception:
                log.exception("F1 settlement failed (paper=%s)", paper_flag)

        state = load_state()
        if dry_run:
            state = copy.deepcopy(state)   #推演 only; never persisted (F4)

        # F1 step 2: state-level expiry cleanup (walk-forward parity) + idempotent
        # double-clear of settle-returned sleeves. Must precede update_sleeve_* or
        # the expiry-day trigger stays blocked by has_pos.
        for sid in ("A", "B"):
            key = "sleeve_a" if sid == "A" else "sleeve_b"
            exp = state.get(key, {}).get("active_position_expiry")
            if exp and str(exp) <= today_str:
                state[key]["active_position_id"] = None
                state[key]["active_position_expiry"] = None
        for sid in settled_sleeves:
            key = "sleeve_a" if str(sid).upper() == "A" else "sleeve_b"
            if key in state:
                state[key]["active_position_id"] = None
                state[key]["active_position_expiry"] = None

        ath = max(state.get("ath_running_max", 0.0), spx_close)
        state["ath_running_max"] = ath
        state["ath_last_update"] = today_str
        ddath = spx_close / ath - 1.0

        spx_hist = yf.Ticker("^GSPC").history(period="1mo", interval="1d")
        ma10 = float(spx_hist["Close"].iloc[-10:].mean())
        cal = pd.DatetimeIndex(pd.to_datetime(spx_hist.index).tz_localize(None))

        # ── F3: fail-closed account-level BP gate read ────────────────────────
        bp_detail = read_main_bp_source()
        main_bp = bp_detail.get("value")
        gate_available = main_bp is not None
        gate = compute_gate(main_bp, today_str) if gate_available else None
        if gate_available:
            log.info("gate: main_bp=%.1f%% cap=%.1f%% src=%s",
                     main_bp, gate.q042_combined_cap, bp_detail.get("source"))
        else:
            log.warning("F3 gate data unavailable (%s) — fail-closed, allowance=0",
                        bp_detail.get("reason"))

        if not dry_run:                                   # B6: no gate log in dry-run
            log_gate(gate, bp_source=bp_detail, date=today_str)

        gate_unavail_dedupe = f"q042_gate_unavailable_{today_str}"
        if not gate_available and not dry_run:
            _send_gateway(
                "ACTION", "系统状态", "Q042 gate 数据不可用",
                (f"Q042 gate 数据不可用（{bp_detail.get('reason')}），"
                 f"trigger 被保守拦截，请人工核查。\n"
                 f"数据源: {bp_detail.get('source')} · snapshot: {bp_detail.get('timestamp')}\n"
                 + _cash_context_line()),
                gate_unavail_dedupe, log,
            )

        entry_date  = (datetime.strptime(today_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        # Expiry is DTE from entry (T+1), not signal (T). Aligns with backtest engine fix (R-20260510-15).
        expiry_a    = (datetime.strptime(entry_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")  # SPEC-094.1
        expiry_b    = (datetime.strptime(entry_date, "%Y-%m-%d") + timedelta(days=90)).strftime("%Y-%m-%d")  # Sleeve B unchanged

        act_a = update_sleeve_a(state["sleeve_a"], ddath, today_str)
        if act_a["action"] == "fire_A":
            spec = _process_sleeve_fire(
                sleeve_id="A", state=state, gate=gate, gate_available=gate_available,
                nlv=nlv, spx_close=spx_close, vix=vix, ddath=ddath, ath=ath,
                today_str=today_str, entry_date=entry_date, expiry=expiry_a,
                dry_run=dry_run, log=log, gate_unavail_dedupe=gate_unavail_dedupe,
            )
            if spec is not None:
                fired.append(spec)

        act_b = update_sleeve_b(state["sleeve_b"], ddath, spx_close, ma10, today_str, cal)
        if act_b["action"] == "fire_B":
            spec = _process_sleeve_fire(
                sleeve_id="B", state=state, gate=gate, gate_available=gate_available,
                nlv=nlv, spx_close=spx_close, vix=vix, ddath=ddath, ath=ath,
                today_str=today_str, entry_date=entry_date, expiry=expiry_b,
                dry_run=dry_run, log=log, gate_unavail_dedupe=gate_unavail_dedupe,
            )
            if spec is not None:
                fired.append(spec)

        # ── F6: combined_bp_pct writer (debit/NLV, NOT maint/NLV — N10) ───────
        # B2: est_debit/fill_debit already PER-CONTRACT USD → do NOT ×100 again.
        # NLV unavailable (0) → skip write, preserve prior value (never write 0).
        if nlv > 0:
            committed = get_active_committed_debit_usd(today=today_str)
            state["combined_bp_pct"] = round(committed / nlv * 100.0, 2)
            log.info("F6 combined_bp_pct=%.2f%% (committed $%.0f / NLV $%.0f)",
                     state["combined_bp_pct"], committed, nlv)
        else:
            log.warning("F6 NLV unavailable — combined_bp_pct write skipped (kept %.2f)",
                        state.get("combined_bp_pct", 0.0))

        if not dry_run:
            save_state(state)
        else:
            log.info("[dry-run] state NOT saved (would-be combined_bp_pct=%.2f)",
                     state.get("combined_bp_pct", 0.0))

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
