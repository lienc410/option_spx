"""SPEC-116 — Q085 S2-BPS daily paper job (16:50 ET, after 16:30 chain snapshot).

Order per handoff:
  A. skew measurement (unconditional)         → data/q085_skew_monitor.jsonl
  C. manage open paper positions (daily)      → close events in ledger
  B. signal check + paper open (signal days)  → open event + Telegram
  D. degradation note (after any close)       → WARNING Telegram (informational)
  E. overlap tracking is recorded on open events (main BPS sleeve presence)

Missing chain snapshot → Telegram `missing_chain` and skip (never silently).
Non-signal days are Telegram-silent (skew row still written).
Strict-JSON discipline: every numeric field asserted finite before dumps
(per feedback_nan_json_browser_vs_python).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from strategy.q085_s2bps_signal import signal_day  # noqa: E402
from notify.event_push import _send as _telegram_send  # noqa: E402

log = logging.getLogger("q085_s2bps")
ET = ZoneInfo("America/New_York")

CHAIN_DIR = ROOT / "data" / "q041_chains"
SKEW_OUT = ROOT / "data" / "q085_skew_monitor.jsonl"
LEDGER = ROOT / "data" / "q085_paper_log.jsonl"

STOP_X = 3.0        # paper stop: cost_mid >= 3 x credit_mid
EXIT_DTE = 21       # paper expiry rule
DEGRADE_TRAIL_N = 10
DEGRADE_CUM_USD = -5000.0

_MAIN_BPS_KEYS = {"bull_put_spread", "bull_put_spread_hv"}


# ── strict-JSON helpers ────────────────────────────────────────────────────────

def _assert_finite(row: dict, ctx: str) -> None:
    for k, v in row.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"q085 {ctx}: non-finite field {k}={v}")


def _append_jsonl(path: Path, row: dict, ctx: str) -> None:
    _assert_finite(row, ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ── chain access ───────────────────────────────────────────────────────────────

def load_today_chain(date_str: str):
    """SPX puts with usable IV from the day's 16:30 snapshot; None if missing."""
    import pandas as pd
    p = CHAIN_DIR / date_str / "SPX.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    puts = df[(df.option_type.str.upper() == "PUT") & df.iv.notna() & (df.iv > 1)]
    return puts if len(puts) else None


# ── A. skew measurement ────────────────────────────────────────────────────────

def measure_skew(puts, vix: float, date_str: str) -> dict:
    """25-35 DTE |delta| 0.50/0.30/0.15 IV legs (mean of 3 nearest rows) + offsets vs VIX."""
    p = puts[(puts.dte >= 25) & (puts.dte <= 35)].assign(ad=lambda x: x.delta.abs())
    if len(p) < 3:
        raise ValueError(f"q085 skew: only {len(p)} puts in 25-35 DTE window")

    def leg(target: float) -> float:
        return float(p.iloc[(p.ad - target).abs().argsort()[:3]].iv.mean())

    row = {
        "date": date_str,
        "vix": round(float(vix), 2),
        "atm_iv": round(leg(0.50), 2),
        "d30_iv": round(leg(0.30), 2),
        "d15_iv": round(leg(0.15), 2),
    }
    row["atm_off"] = round(row["atm_iv"] - row["vix"], 2)
    row["d30_off"] = round(row["d30_iv"] - row["vix"], 2)
    row["d15_off"] = round(row["d15_iv"] - row["vix"], 2)
    _append_jsonl(SKEW_OUT, row, "skew")
    return row


# ── leg picking (shared by open + manage) ─────────────────────────────────────

def _pick_expiry(puts):
    """Expiry whose dte is nearest 30."""
    dtes = puts.dte.unique()
    best = min(dtes, key=lambda d: abs(int(d) - 30))
    return puts[puts.dte == best]

def _nearest_delta_row(chain, target: float):
    c = chain.assign(ad=lambda x: x.delta.abs())
    return c.iloc[(c.ad - target).abs().argsort()].iloc[0]

def _quote_for_strikes(puts, expiry: str, ks: float, kl: float):
    """Rows for exact expiry+strikes; (short_row, long_row) or None."""
    e = puts[puts.expiry == expiry]
    s = e[e.strike == ks]
    l = e[e.strike == kl]
    if s.empty or l.empty:
        return None
    return s.iloc[0], l.iloc[0]


# ── B. paper open ──────────────────────────────────────────────────────────────

def _main_bps_overlap() -> bool:
    """External-review C7: is the main BPS sleeve holding a position today?"""
    try:
        from strategy.state import read_all_positions
        for pos in (read_all_positions() or {}).get("positions", []):
            if str(pos.get("status") or "open").lower() not in {"", "open"}:
                continue
            if str(pos.get("strategy_key") or "") in _MAIN_BPS_KEYS:
                return True
    except Exception:
        log.warning("q085: main-sleeve overlap check failed", exc_info=True)
    return False


def build_paper_bps(puts, date_str: str, *, vix: float, sig: dict) -> dict:
    """Construct the paper BPS open event from today's chain (signal days only)."""
    e = _pick_expiry(puts)
    short = _nearest_delta_row(e, 0.30)
    long_ = _nearest_delta_row(e, 0.15)
    credit_mid = float(short.mid) - float(long_.mid)
    credit_natural = float(short.bid) - float(long_.ask)
    row = {
        "event": "open",
        "date": date_str,
        "expiry": str(short.expiry),
        "dte": int(short.dte),
        "k_short": float(short.strike),
        "k_long": float(long_.strike),
        "short_bid": float(short.bid), "short_ask": float(short.ask), "short_mid": float(short.mid),
        "long_bid": float(long_.bid), "long_ask": float(long_.ask), "long_mid": float(long_.mid),
        "short_iv": round(float(short.iv), 2), "long_iv": round(float(long_.iv), 2),
        "credit_mid": round(credit_mid, 2),
        "credit_natural": round(credit_natural, 2),
        "entry_spx": float(short.close),
        "entry_vix": round(float(vix), 2),
        "rsi2": sig.get("rsi2"), "down3": sig.get("down3"),
        "overlap_main_bps": _main_bps_overlap(),
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
    }
    _append_jsonl(LEDGER, row, "open")
    return row


# ── C. paper management ────────────────────────────────────────────────────────

def _open_positions(ledger: list[dict]) -> list[dict]:
    closed = {(r.get("open_date"), r.get("expiry"), r.get("k_short"), r.get("k_long"))
              for r in ledger if r.get("event") == "close"}
    out = []
    for r in ledger:
        if r.get("event") != "open":
            continue
        if (r.get("date"), r.get("expiry"), r.get("k_short"), r.get("k_long")) in closed:
            continue
        out.append(r)
    return out


def _vix_max_between(start_date: str, end_date: str) -> float | None:
    """Peak VIX over the holding window, from the daily skew monitor file."""
    vals = [r["vix"] for r in _read_jsonl(SKEW_OUT)
            if start_date <= r.get("date", "") <= end_date and isinstance(r.get("vix"), (int, float))]
    return round(max(vals), 2) if vals else None


def manage_open_positions(puts, today: str) -> list[dict]:
    """Re-mark all open paper positions off today's chain; close on stop/expiry rule."""
    ledger = _read_jsonl(LEDGER)
    closes: list[dict] = []
    for pos in _open_positions(ledger):
        q = _quote_for_strikes(puts, pos["expiry"], pos["k_short"], pos["k_long"])
        if q is None:
            log.warning("q085 manage: no quotes today for %s %s/%s — skip",
                        pos["expiry"], pos["k_short"], pos["k_long"])
            continue
        s, l = q
        cost_mid = float(s.mid) - float(l.mid)          # buy back short, sell long
        cost_natural = float(s.ask) - float(l.bid)
        dte_now = int(s.dte)
        spx_close = float(s.close)

        reason = None
        if cost_mid >= STOP_X * pos["credit_mid"] and pos["credit_mid"] > 0:
            reason = "stop"
        elif dte_now <= EXIT_DTE:
            reason = "expiry_rule"
        if reason is None:
            continue

        hold_days = (date.fromisoformat(today) - date.fromisoformat(pos["date"])).days
        row = {
            "event": "close",
            "date": today,
            "open_date": pos["date"],
            "expiry": pos["expiry"],
            "k_short": pos["k_short"], "k_long": pos["k_long"],
            "cost_mid": round(cost_mid, 2),
            "cost_natural": round(cost_natural, 2),
            "pnl_mid": round((pos["credit_mid"] - cost_mid) * 100.0, 2),
            "pnl_natural": round((pos["credit_natural"] - cost_natural) * 100.0, 2),
            "hold_days": hold_days,
            "dte_at_close": dte_now,
            "vix_max_during": _vix_max_between(pos["date"], today),
            "breach": bool(spx_close < pos["k_short"]),
            "reason": reason,
            "ts": datetime.now(ET).isoformat(timespec="seconds"),
        }
        _append_jsonl(LEDGER, row, "close")
        closes.append(row)
    return closes


# ── D. degradation note ────────────────────────────────────────────────────────

def degradation_note() -> dict | None:
    """Trailing-10 and cumulative pnl_mid; WARNING (no halt) if either trips."""
    pnls = [r["pnl_mid"] for r in _read_jsonl(LEDGER)
            if r.get("event") == "close" and isinstance(r.get("pnl_mid"), (int, float))]
    if not pnls:
        return None
    trail = sum(pnls[-DEGRADE_TRAIL_N:])
    cum = sum(pnls)
    trip_trail = trail < 0
    trip_cum = cum <= DEGRADE_CUM_USD
    if not (trip_trail or trip_cum):
        return None
    return {"trailing10_pnl_mid": round(trail, 2), "cum_pnl_mid": round(cum, 2),
            "trip_trailing": trip_trail, "trip_cum": trip_cum}


# ── main ───────────────────────────────────────────────────────────────────────

def run(today: str | None = None, *, dry_run: bool = False) -> dict:
    today = today or datetime.now(ET).date().isoformat()
    summary: dict = {"date": today, "skew": None, "closes": [], "open": None, "signal": None}

    puts = load_today_chain(today)
    if puts is None:
        msg = f"[S2-BPS PAPER] {today} missing_chain — skew/管理跳过（SPEC-114 sanity 会另行报警）"
        log.warning(msg)
        if not dry_run:
            _telegram_send(msg)
        summary["missing_chain"] = True
        return summary

    # regime / strategy_key / VIX from the SAME pipeline as the bot's daily push
    from strategy.selector import get_recommendation
    rec = get_recommendation(use_intraday=False)
    vix = float(rec.vix_snapshot.vix)
    regime = getattr(rec.vix_snapshot.regime, "value", str(rec.vix_snapshot.regime))
    strategy_key = getattr(rec, "strategy_key", None)

    # A. skew (unconditional)
    try:
        summary["skew"] = measure_skew(puts, vix, today)
    except Exception as exc:
        log.exception("q085 skew measurement failed")
        summary["skew_error"] = str(exc)
        if not dry_run:
            _telegram_send(f"[S2-BPS PAPER] {today} skew 测量失败: {exc}")

    # C. manage open positions
    closes = manage_open_positions(puts, today)
    summary["closes"] = closes
    for c in closes:
        stop_tag = " STOP" if c["reason"] == "stop" else ""
        if not dry_run:
            _telegram_send(
                f"[S2-BPS PAPER] 平仓 · {c['open_date']} 仓位 · "
                f"PnL mid ${c['pnl_mid']:,.0f} / natural ${c['pnl_natural']:,.0f} · "
                f"hold {c['hold_days']}d{stop_tag}"
            )

    # B. signal check + paper open
    from signals.trend import fetch_spx_history
    closes_series = fetch_spx_history(period="2y")["close"].dropna().tolist()
    sig = signal_day(closes_series, vix, regime, strategy_key)
    summary["signal"] = sig
    if sig["signal"]:
        opened = build_paper_bps(puts, today, vix=vix, sig=sig)
        summary["open"] = opened
        if not dry_run:
            _telegram_send(
                f"[S2-BPS PAPER] 信号日 · SPX {opened['entry_spx']:,.0f} · VIX {vix:.1f} · "
                f"{opened['dte']}DTE {opened['k_short']:,.0f}/{opened['k_long']:,.0f} "
                f"credit mid ${opened['credit_mid']:.2f} / natural ${opened['credit_natural']:.2f}"
            )

    # D. degradation note (after closes)
    if closes:
        note = degradation_note()
        if note:
            summary["degradation"] = note
            if not dry_run:
                _telegram_send(
                    f"[S2-BPS PAPER] ⚠ WARNING 降级注记 · trailing10 ${note['trailing10_pnl_mid']:,.0f} · "
                    f"cum ${note['cum_pnl_mid']:,.0f}（paper 阶段仅记录，不停机）"
                )
    return summary


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="SPEC-116 Q085 S2-BPS daily paper job")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default today ET)")
    p.add_argument("--dry-run", action="store_true", help="no Telegram, still writes files")
    args = p.parse_args(argv)
    summary = run(args.date, dry_run=args.dry_run)
    print(json.dumps(summary, default=str, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
