"""Daily portfolio snapshot — captures comprehensive daily state for future analysis.

Runs at 17:00 ET each trading day. Persists one JSONL record per day to
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
SCHEMA_VERSION = 4   # v4: spx_spread.{options,equity}_bp_{pct,dollars} split
_HOLIDAYS = {
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}


def _today_et() -> str:
    return datetime.now(ET).date().isoformat()


def _is_trading_day(date_str: str) -> bool:
    d = datetime.fromisoformat(date_str).date()
    return d.weekday() < 5 and date_str not in _HOLIDAYS


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


def _authoritative_index_close(symbol: str, fallback, label: str):
    try:
        from schwab.client import get_index_quote

        q = get_index_quote(symbol)
        value = q.get("last") if q.get("last") not in (None, 0) else q.get("close")
        if value not in (None, 0):
            return value
        print(f"[daily_snapshot] WARNING {label} Schwab quote missing/zero: {q}", file=sys.stderr)
    except Exception as exc:
        print(f"[daily_snapshot] WARNING {label} Schwab quote failed: {exc}", file=sys.stderr)
    print(f"[daily_snapshot] WARNING {label} falling back to stale local source", file=sys.stderr)
    return fallback


# strategy_key → option_type for the broker greeks lookup. Mirrors the same
# map in scripts/compute_greek_attribution.py — keep them in sync.
_STRATEGY_OPTION_TYPE = {
    "bull_put_spread":     "PUT",
    "bull_put_spread_hv":  "PUT",
    "bear_call_spread_hv": "CALL",
    "bull_call_diagonal":  "CALL",
    "iron_condor":         "PUT",
    "iron_condor_hv":      "PUT",
}


def _option_type_for(strategy_key) -> str:
    return _STRATEGY_OPTION_TYPE.get(str(strategy_key or "").lower(), "PUT")


def _attach_broker_greeks(positions: list[dict]) -> None:
    """Mutates positions in place: adds greeks_short / greeks_long via Schwab
    chain. SPX index options have no greeks in Polygon historical chain, so
    capturing them at snapshot time is the only way to feed path B
    attribution.

    Per-leg lookup: each leg uses its own (option_type, strike, expiry) so
    BCD-style diagonals where short and long sit on different expiry chains
    are quoted correctly. option_type is derived from each position's
    strategy_key (BCD → CALL; BPS → PUT). Calls into Schwab are batched by
    (option_type, expiry) to minimise API hits.
    """
    if not positions:
        return
    try:
        from schwab.client import get_option_chain
    except Exception as exc:
        print(f"[daily_snapshot] schwab.client import failed: {exc}", file=sys.stderr)
        return
    today_d = datetime.now(ET).date()

    # Build a per-leg request list. Each entry knows its option_type, the
    # chain expiry to query, the strike, and which position dict + key to
    # write the result into.
    requests: list[tuple[str, str, float, dict, str]] = []
    for p in positions:
        opt = _option_type_for(p.get("strategy_key"))
        ss = p.get("short_strike")
        short_exp = p.get("expiry")
        if ss is not None and short_exp:
            requests.append((opt, short_exp, float(ss), p, "greeks_short"))
        ls = p.get("long_strike")
        long_exp = p.get("long_expiry") or p.get("expiry")
        if ls is not None and long_exp:
            requests.append((opt, long_exp, float(ls), p, "greeks_long"))

    # Group by (option_type, expiry) so each unique chain is fetched once.
    by_chain: dict[tuple[str, str], list[tuple[float, dict, str]]] = {}
    for opt, exp, strike, pos, leg_key in requests:
        by_chain.setdefault((opt, exp), []).append((strike, pos, leg_key))

    for (opt, expiry), legs in by_chain.items():
        try:
            exp_d = datetime.fromisoformat(expiry).date()
            dte = (exp_d - today_d).days
            if dte <= 0:
                continue
            strikes = [s for s, _, _ in legs]
            center = (min(strikes) + max(strikes)) / 2.0
            # Schwab strike_window=20 only returns ~$100 around center. Use a
            # fixed wide window so any spread up to ~$1000 wide is covered
            # in one chain call.
            window = 200
            chain = get_option_chain("SPX", opt, target_dte=int(dte),
                                     dte_range=0, center_strike=center,
                                     strike_window=window)
            if not chain:
                print(f"[daily_snapshot] greek chain empty for {opt} {expiry}",
                      file=sys.stderr)
                continue
            by_strike = {float(r["strike"]): r for r in chain
                         if r.get("strike") is not None and r.get("expiry") == expiry}
            for strike, pos, leg_key in legs:
                row = by_strike.get(strike)
                if row is None:
                    continue
                pos[leg_key] = {
                    "delta": _r(row.get("delta"), 4),
                    "gamma": _r(row.get("gamma"), 6),
                    "theta": _r(row.get("theta"), 4),
                    "vega":  _r(row.get("vega"),  4),
                    "iv":    _r(row.get("iv"),    4),
                    "mark":  _r(row.get("mid"),   2),
                }
        except Exception as exc:
            print(f"[daily_snapshot] greek fetch for {opt} {expiry} failed: {exc}",
                  file=sys.stderr)
            continue


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
    # Asset-class breakdown of SPX-account maintenance (for journal BP chart):
    # options = (schwab_maint - schwab_equity) + (etrade_maint - etrade_equity)
    # equity  = schwab_equity + etrade_equity
    _schwab_m = _num(accounts.get("schwab_maintenance_margin")) or 0.0
    _etrade_m = _num(accounts.get("etrade_maintenance_margin")) or 0.0
    _schwab_eq_d = _num(buckets.get("equity_margin_dollars")) or 0.0
    _etrade_eq_d = _num(buckets.get("etrade_equity_dollars")) or 0.0
    _options_bp_dollars = max(0.0, (_schwab_m - _schwab_eq_d) + (_etrade_m - _etrade_eq_d))
    _equity_bp_dollars  = _schwab_eq_d + _etrade_eq_d
    if not schwab_nlv:
        print("[daily_snapshot] schwab_nlv missing — aborting", file=sys.stderr)
        return None
    # When ETrade is unauthenticated (refresh-token expired, etc), do NOT silently
    # treat etrade_nlv as 0 — that produces an artificial $X drop in combined_nlv
    # on the journal NLV curve when in reality ETrade just wasn't visible. Mark
    # the row as partial so downstream consumers (journal chart, nlv-change
    # endpoint) can skip / annotate rather than draw a misleading line.
    partial_accounts: list[str] = []
    if etrade_nlv is None and accounts.get("etrade_nlv") is None:
        partial_accounts.append("etrade")
    combined_nlv = (
        None if partial_accounts
        else schwab_nlv + (etrade_nlv or 0.0)
    )

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
    spx_close = _authoritative_index_close(
        "$SPX",
        trend_snap.get("spx") if trend_snap.get("spx") is not None else q042.get("spx_close"),
        "SPX",
    )
    vix_close = _authoritative_index_close("$VIX", vix_snap.get("vix"), "VIX")

    stress_active = bool(state.get("stress_episode_active"))
    second_active = bool(state.get("second_leg_active"))
    regime_name = "second" if second_active else "stress" if stress_active else "normal"

    # SPEC-094.2 F7 (AC-94.2-9): when the Q042 snapshot flags ath_degraded, its
    # ddath is a neutral-0 filler (state ATH missing/0), NOT a real drawdown
    # read — warn and record null instead of a fake number.
    q042_ath_degraded = bool(q042.get("ath_degraded"))
    if q042_ath_degraded:
        print("[daily_snapshot] WARNING q042 ath_degraded — state ATH missing/0; "
              "recording regime.ddath_pct as null (not the 0-filler)", file=sys.stderr)
    q042_ddath_pct = None if q042_ath_degraded else q042.get("ddath_pct")

    # SPX positions snapshot — including per-leg broker chain greeks (path B).
    # SPX greeks are NOT available from Polygon historical chain, so daily
    # snapshot captures them from Schwab marketdata/v1/chains for both legs.
    # ETrade has greeks too but SPX is fungible across brokers — one Schwab
    # chain call covers all positions sharing the same expiry+strike.
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
            # Unrealized P&L lives in pos.position_lives[trade_id].
            # ETrade legs often carry mark but no unrealized_pnl (live-quote
            # path only fills it for the primary broker) — derive it so the
            # snapshot is broker-symmetric: (entry − mark) × 100 × contracts
            # works for credit (+entry) and debit (−entry) alike.
            pl = position_lives.get(p.get("trade_id")) or {}
            if pl.get("unrealized_pnl") is None and pl.get("mark") is not None:
                try:
                    ep_raw = p.get("actual_premium") or p.get("model_premium")
                    ct_raw = p.get("contracts") or 1
                    pl = dict(pl)
                    pl["unrealized_pnl"] = (float(ep_raw) - float(pl["mark"])) * 100.0 * float(ct_raw)
                except (TypeError, ValueError):
                    pass
            spx_positions.append({
                "account":        p.get("account"),
                "trade_id":       p.get("trade_id"),
                "strategy_key":   p.get("strategy_key") or pos.get("strategy_key"),
                "short_strike":   _num(p.get("short_strike")),
                "long_strike":    _num(p.get("long_strike")),
                "contracts":      _num(p.get("contracts")),
                "expiry":         expiry_str,
                # Per-leg long-expiry survives the snapshot so compute_greek_
                # attribution can re-quote diagonal long legs at the right
                # chain after the position has been closed (current_position
                # .json is gone by then).
                "long_expiry":    p.get("long_expiry"),
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

    # Path B — broker chain greeks per leg. Best-effort: any failure leaves
    # position dict unchanged and falls back to BS reverse-solve (path A) in
    # the attribution compute job.
    _attach_broker_greeks(spx_positions)

    sleeve_a = q042.get("sleeve_a") or {}
    sleeve_b = q042.get("sleeve_b") or {}

    return {
        "date": today,
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "combined_nlv": round(combined_nlv, 2) if combined_nlv is not None else None,
        # Accounts present in this snapshot but with no data this run (e.g.,
        # ETrade refresh-token expired). When non-empty, combined_nlv is None
        # and downstream chart/aggregations must skip or gap this row.
        "partial_accounts": partial_accounts,

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
            "vix":           _r(vix_close, 2),
            "vix_peak_10d":  _r(aftermath.get("vix_peak_10d"), 2),
            "vix3m":         _r(vix_snap.get("vix3m"), 2),
            "spx":           _r(spx_close, 2),
            "iv_rank":       _r(iv_snap.get("iv_rank"), 1),
            "iv_percentile": _r(iv_snap.get("iv_percentile"), 1),
            "trend":         trend_snap.get("signal"),
        },

        "regime": {
            "name":              regime_name,
            "stress_active":     stress_active,
            "second_leg_active": second_active,
            "aftermath_active":  bool(aftermath.get("active")),
            "ddath_pct":         _r(q042_ddath_pct, 4),   # SPEC-094.2 F7: null when ath_degraded
        },

        "strategies": {
            "spx_spread": {
                "active":     bool(pos.get("open")),
                # bp_dollars / bp_pct = account-level maintenance (SPEC-103 §R1):
                # options spread max-loss + equity collateral. Used by governance.
                "bp_dollars": _r(pools.get("spx_pm_bp_dollars"), 2),
                "bp_pct":     _r(pools.get("spx_pm_bp_pct"), 2),
                # v4 split: asset-class breakdown for journal BP chart, matches
                # what /api/portfolio/summary surfaces on home Portfolio Snapshot.
                "options_bp_pct":     _r(
                    (_num(buckets.get("spx_live_bp_pct")) or 0.0)
                    + (_num(buckets.get("etrade_options_bp_pct")) or 0.0), 2),
                "equity_bp_pct":      _r(
                    (_num(buckets.get("equity_margin_bp_pct")) or 0.0)
                    + (_num(buckets.get("etrade_equity_bp_pct")) or 0.0), 2),
                "options_bp_dollars": _r(_options_bp_dollars, 2),
                "equity_bp_dollars":  _r(_equity_bp_dollars, 2),
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


def _state_surface_hook(today: str) -> None:
    """SPEC-141 F2 — 状态面日志挂载（幂等一天一行 data/state_surface.jsonl，
    首跑自动回填 90 TD 简版）。完全隔离：任何失败只打日志，绝不影响 snapshot。"""
    try:
        from strategy.state_surface import append_daily_log

        res = append_daily_log(date=today)
        print(f"[daily_snapshot] state_surface {res.get('status')} "
              f"(backfilled={res.get('backfilled', 0)})")
    except Exception as exc:
        print(f"[daily_snapshot] state_surface log failed: {exc}", file=sys.stderr)


def main() -> int:
    today = _today_et()
    if not _is_trading_day(today):
        print(f"[daily_snapshot] non-trading day {today} — skipping")
        return 0
    # SPEC-141: 状态面日志有独立幂等，与 snapshot 的 already_recorded 互不耦合
    _state_surface_hook(today)
    if _already_recorded(today):
        print(f"[daily_snapshot] already recorded for {today}")
        return 0
    rec = build_record()
    if not rec:
        return 1
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    if rec.get("combined_nlv") is None:
        partial = ",".join(rec.get("partial_accounts") or [])
        print(f"[daily_snapshot] saved date={today} combined_nlv=PARTIAL ({partial} missing)")
    else:
        print(f"[daily_snapshot] saved date={today} combined_nlv=${rec['combined_nlv']:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
