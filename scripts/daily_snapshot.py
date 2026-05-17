"""Daily portfolio snapshot — captures comprehensive daily state for future analysis.

Runs at 16:30 ET each trading day. Persists one JSONL record per day to
data/daily_snapshot.jsonl. Idempotent: skips if today already recorded.

Captures:
- Per-account NLV / maint margin (Schwab, E-Trade)
- Market context (VIX, SPX, IV rank, trend, drawdowns)
- Regime state (normal/stress/second-leg, aftermath flag)
- Per-strategy BP usage + active flags
- Open SPX position details (strikes, qty, DTE, unrealized P&L)

Data is fetched from the local web server's APIs to reuse all existing
aggregation/auth logic. A schema_version field is stamped on each record
so future migrations can detect old shapes.
"""
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import pytz

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "daily_snapshot.jsonl"
ET = pytz.timezone("America/New_York")
BASE = "http://127.0.0.1:5050"
SCHEMA_VERSION = 2


def _today_et() -> str:
    return datetime.now(ET).date().isoformat()


def _fetch(path: str, timeout: int = 30):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as exc:
        print(f"[daily_snapshot] {path} failed: {exc}", file=sys.stderr)
        return None


def _already_recorded(date_str: str) -> bool:
    if not HISTORY.exists():
        return False
    with HISTORY.open() as f:
        for line in f:
            try:
                if json.loads(line).get("date") == date_str:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _r(v, dec=2):
    n = _num(v)
    return round(n, dec) if n is not None else None


def build_record() -> dict | None:
    today = _today_et()

    summary = _fetch("/api/portfolio/summary")
    if not summary or summary.get("error"):
        print("[daily_snapshot] /api/portfolio/summary failed — aborting", file=sys.stderr)
        return None

    accounts = summary.get("account_breakdown") or {}
    buckets  = summary.get("bp_usage_by_bucket") or {}
    schwab_nlv = _num(accounts.get("schwab_nlv"))
    etrade_nlv = _num(accounts.get("etrade_nlv"))
    if not schwab_nlv:
        print("[daily_snapshot] schwab_nlv missing — aborting", file=sys.stderr)
        return None
    combined_nlv = schwab_nlv + (etrade_nlv or 0.0)

    # Best-effort fetches — None if unavailable
    gov       = _fetch("/api/sleeve-governance/state") or {}
    state     = gov.get("state") or {}
    pools     = state.get("pools") or {}
    q042      = _fetch("/api/q042/state") or {}
    hvlad     = _fetch("/api/hvladder/live") or {}
    aftermath = _fetch("/api/aftermath/state") or {}
    rec       = _fetch("/api/recommendation") or {}
    pos       = _fetch("/api/position") or {}

    vix_snap   = rec.get("vix_snapshot")   or {}
    iv_snap    = rec.get("iv_snapshot")    or {}
    trend_snap = rec.get("trend_snapshot") or {}

    stress_active = bool(state.get("stress_episode_active"))
    second_active = bool(state.get("second_leg_active"))
    regime_name = "second" if second_active else "stress" if stress_active else "normal"

    # SPX positions snapshot
    spx_positions = []
    if pos.get("open"):
        rows = pos.get("positions") if isinstance(pos.get("positions"), list) and pos["positions"] else [pos]
        position_lives = pos.get("position_lives") or {}
        today_date = datetime.now(ET).date()
        for p in rows:
            if not isinstance(p, dict):
                continue
            # Current DTE: derive from expiry (dte_at_entry is the original entry value)
            expiry_str = p.get("expiry")
            current_dte = None
            if expiry_str:
                try:
                    exp = datetime.fromisoformat(expiry_str).date()
                    current_dte = max(0, (exp - today_date).days)
                except Exception:
                    pass
            # Unrealized P&L lives in pos.position_lives[trade_id]
            pl = position_lives.get(p.get("trade_id")) or {}
            spx_positions.append({
                "account":        p.get("account"),
                "trade_id":       p.get("trade_id"),
                "short_strike":   _num(p.get("short_strike")),
                "long_strike":    _num(p.get("long_strike")),
                "contracts":      _num(p.get("contracts")),
                "expiry":         expiry_str,
                "dte_current":    current_dte,
                "dte_at_entry":   _num(p.get("dte_at_entry")),
                "opened_at":      p.get("opened_at"),
                "entry_premium":  _r(p.get("actual_premium") or p.get("model_premium"), 2),
                "entry_spx":      _r(p.get("entry_spx"), 2),
                "entry_vix":      _r(p.get("entry_vix"), 2),
                "premium_source": p.get("premium_source"),
                "mark":           _r(pl.get("mark"), 2),
                "unrealized_pnl": _r(pl.get("unrealized_pnl"), 2),
            })

    sleeve_a = q042.get("sleeve_a") or {}
    sleeve_b = q042.get("sleeve_b") or {}

    return {
        "date": today,
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "combined_nlv": round(combined_nlv, 2),

        "accounts": {
            "schwab": {
                "nlv":   _r(schwab_nlv),
                "maint": _r(accounts.get("schwab_maintenance_margin")),
            },
            "etrade": {
                "nlv":   _r(etrade_nlv),
                "maint": _r(accounts.get("etrade_maintenance_margin")),
            },
        },

        "market": {
            "vix":           _r(vix_snap.get("vix"), 2),
            "vix_peak_10d":  _r(aftermath.get("vix_peak_10d"), 2),
            "vix3m":         _r(vix_snap.get("vix3m"), 2),
            "spx":           _r(trend_snap.get("spx") if trend_snap.get("spx") is not None else q042.get("spx_close"), 2),
            "iv_rank":       _r(iv_snap.get("iv_rank"), 1),
            "iv_percentile": _r(iv_snap.get("iv_percentile"), 1),
            "trend":         trend_snap.get("signal"),
        },

        "regime": {
            "name":              regime_name,
            "stress_active":     stress_active,
            "second_leg_active": second_active,
            "aftermath_active":  bool(aftermath.get("active")),
            "ddath_pct":         _r(q042.get("ddath_pct"), 4),
        },

        "strategies": {
            "spx_spread": {
                "active":     bool(pos.get("open")),
                "bp_dollars": _r(pools.get("spx_pm_bp_dollars"), 2),
                "bp_pct":     _r(pools.get("spx_pm_bp_pct"), 2),
                "positions":  spx_positions,
            },
            "stress_put_ladder": {
                "active_slots":      _num(hvlad.get("active_slots")),
                "max_slots":         _num(hvlad.get("max_slots")),
                "signal_live":       bool(hvlad.get("signal_live")),
                "vix_current":       _r(hvlad.get("vix_current"), 2),
                "vix_gate_distance": _r(hvlad.get("vix_gate_distance"), 2),
                "blockers":          hvlad.get("blockers") or [],
                "bp_dollars":        _r(pools.get("es_span_bp_dollars"), 2),
            },
            "dd_overlay": {
                "sleeve_a_armed":    bool(sleeve_a.get("armed")),
                "sleeve_a_active":   bool(sleeve_a.get("active_position")),
                "sleeve_b_watching": bool(sleeve_b.get("in_watching")),
                "sleeve_b_active":   bool(sleeve_b.get("active_position")),
                "bp_pct":            _r(q042.get("combined_bp_pct"), 2),
            },
            "sleeves": {
                "tier2_bp_pct": _r(buckets.get("q041_tier2_bp_pct"), 2),
                "tier3_bp_pct": _r(buckets.get("q041_tier3_bp_pct"), 2),
            },
        },
    }


def main() -> int:
    today = _today_et()
    if _already_recorded(today):
        print(f"[daily_snapshot] already recorded for {today}")
        return 0
    rec = build_record()
    if not rec:
        return 1
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[daily_snapshot] saved date={today} combined_nlv=${rec['combined_nlv']:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
