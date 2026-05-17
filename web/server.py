"""
web/server.py — Local Flask dashboard for the SPX Strategy Bot

Start:
  python main.py --web              → http://localhost:5050
  python main.py --web --port=8080
"""
from __future__ import annotations

import hashlib
import csv
import json
import os
import threading
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from enum import Enum
from itertools import product
from pathlib import Path

from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, redirect, render_template
from flask import request as flask_req

_ET = ZoneInfo("America/New_York")

def _is_market_hours() -> bool:
    """True if current ET time is within regular trading hours 09:30–16:00, Mon–Fri."""
    from datetime import datetime, time as dtime
    now = datetime.now(_ET)
    if now.weekday() >= 5:
        return False
    return dtime(9, 30) <= now.time() <= dtime(16, 0)

app = Flask(__name__, template_folder="templates")

_backtest_cache: dict[str, tuple[float, dict]] = {}
_signals_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # 5 minutes
_SIGNALS_CACHE_TTL = 3600  # 1 hour
_STATS_SCHEMA_VERSION = "v3"  # bump: account_size 150k → 500k
_ES_BP_PER_CONTRACT = 20_529.0
from strategy.es_params import DEFAULT_ES_PARAMS as _ES_PARAMS
_ES_BP_LIMIT_FRACTION = _ES_PARAMS.bp_limit_fraction  # 0.20 — sourced from EsShortPutParams

# ── Disk cache for backtest stats (survives restarts) ────────────────────────
_STATS_DISK_CACHE = Path(__file__).parent.parent / "data" / "backtest_stats_cache.json"
_RESULTS_DISK_CACHE = Path(__file__).parent.parent / "data" / "backtest_results_cache.json"
_RESEARCH_VIEWS_FILE = Path(__file__).parent.parent / "data" / "research_views.json"
_Q019_SETTLING_LOG_FILE = Path(__file__).parent.parent / "data" / "q019_settling_log.jsonl"


def _short_strategy_label(value: str | None) -> str:
    raw = (value or "").strip().lower()
    mapping = {
        "bull_put_spread": "BPS",
        "iron_condor": "IC",
        "bull_call_spread": "BCS",
        "bear_call_spread": "Bear Call",
        "bear_put_spread": "Bear Put",
        "reduce_wait": "WAIT",
        "reduce / wait": "WAIT",
    }
    return mapping.get(raw, value or "—")


def _load_q019_flip_days() -> list[dict[str, object]]:
    try:
        if not _Q019_SETTLING_LOG_FILE.exists():
            return []
        rows: list[dict[str, object]] = []
        for raw_line in _Q019_SETTLING_LOG_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not payload.get("changed"):
                continue
            rows.append({
                "date": payload.get("date"),
                "vix_signal1": payload.get("vix_signal1"),
                "rec_signal1": _short_strategy_label(payload.get("rec_signal1")),
                "vix_signal2": payload.get("vix_signal2"),
                "rec_signal2": _short_strategy_label(payload.get("rec_signal2")),
                "elapsed_min": payload.get("elapsed_min"),
            })
        rows.sort(key=lambda item: str(item.get("date") or ""))
        return rows
    except Exception:
        return []


_BACKTEST_ACCOUNT_SIZE = 500_000   # canonical account size for all frontend backtests

def _params_hash() -> str:
    """Short hash of StrategyParams + account size — changes when either changes."""
    from strategy.selector import StrategyParams
    payload = {**asdict(StrategyParams()), "_acct": _BACKTEST_ACCOUNT_SIZE}
    return _hash_payload(payload)


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _load_results_disk() -> dict:
    try:
        if _RESULTS_DISK_CACHE.exists():
            return json.loads(_RESULTS_DISK_CACHE.read_text())
    except Exception:
        pass
    return {}


def _save_results_disk(cache: dict) -> None:
    try:
        _RESULTS_DISK_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _RESULTS_DISK_CACHE.write_text(json.dumps(cache, default=str))
    except Exception:
        pass


def _backtest_query_params() -> tuple["StrategyParams", str, dict]:
    from strategy.selector import StrategyParams

    defaults = asdict(StrategyParams())
    editable = {
        "extreme_vix": float,
        "high_vol_delta": float,
        "high_vol_dte": int,
        "high_vol_size": float,
        "normal_delta": float,
        "normal_dte": int,
        "profit_target": float,
        "stop_mult": float,
        "min_hold_days": int,
    }
    params_payload = defaults.copy()
    for key, caster in editable.items():
        raw = flask_req.args.get(key)
        if raw in (None, ""):
            continue
        params_payload[key] = caster(raw)
    return StrategyParams(**params_payload), _hash_payload({**params_payload, "_acct": _BACKTEST_ACCOUNT_SIZE}), params_payload


def _load_stats_disk() -> dict:
    try:
        if _STATS_DISK_CACHE.exists():
            return json.loads(_STATS_DISK_CACHE.read_text())
    except Exception:
        pass
    return {}


def _stats_payload_has_avg(payload: dict) -> bool:
    for key, value in payload.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and "avg_pnl" in value:
            return True
    for value in payload.get("_cell", {}).values():
        if isinstance(value, dict) and "avg_pnl" in value:
            return True
    return False


def _save_stats_disk(cache: dict) -> None:
    try:
        _STATS_DISK_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _STATS_DISK_CACHE.write_text(json.dumps(cache, default=str))
    except Exception:
        pass


# ── Auto-search state (single global job, one at a time) ─────────────────────
_auto_search: dict = {
    "running":   False,
    "total":     0,
    "completed": 0,
    "best":      None,   # experiment dict with highest Sharpe so far
    "error":     None,
}


class _EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def _json_dc(dc) -> Response:
    """Serialize a dataclass (with nested enums) to JSON response."""
    return app.response_class(
        json.dumps(asdict(dc), cls=_EnumEncoder, default=str),
        mimetype="application/json",
    )


@app.route("/")
def index():
    return render_template("portfolio_home.html")


@app.route("/spx")
def spx_page():
    return render_template("spx.html")


@app.route("/es")
def es_page():
    return render_template("es.html")


@app.route("/q041")
def q041_page():
    return render_template("q041.html")


@app.route("/backtest")
def backtest_page():
    return render_template("backtest.html")


@app.route("/portfolio-backtest")
def portfolio_backtest_page():
    return render_template("portfolio_backtest.html")


@app.route("/es-backtest")
def es_backtest_page():
    return render_template("es_backtest.html")


@app.route("/hvladder")
def hvladder_page():
    return render_template("hvladder.html")


@app.route("/hvladder_backtest")
def hvladder_backtest_page():
    return render_template("hvladder_backtest.html")


@app.route("/q041-backtest")
@app.route("/q041/backtest")
def q041_backtest_page():
    return render_template("q041_backtest.html")


@app.route("/q042")
def q042_page():
    return render_template("q042.html")


@app.route("/q042/backtest")
def q042_backtest_page():
    return render_template("q042_backtest.html")


@app.route("/aftermath")
def aftermath_page():
    return render_template("aftermath.html")


@app.route("/aftermath/backtest")
def aftermath_backtest_page():
    return render_template("aftermath_backtest.html")


@app.route("/q041/archive")
def q041_archive_page():
    return render_template("q041_archive.html")


@app.route("/matrix")
def matrix_page():
    return render_template("matrix.html")


@app.route("/margin")
def margin_page():
    return render_template("margin.html")


@app.route("/performance")
def performance_page():
    return render_template("performance.html")


@app.route("/journal")
def journal_page():
    return render_template("journal.html")


@app.route("/api/recommendation")
def api_recommendation():
    from strategy.selector import get_recommendation
    try:
        rec = get_recommendation(use_intraday=_is_market_hours())
        return _json_dc(rec)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/recommendation/settling")
def api_recommendation_settling():
    try:
        from production.vix_settling import read_settling_state

        return jsonify(read_settling_state())
    except Exception as exc:
        return jsonify({
            "date": datetime.now(_ET).date().isoformat(),
            "status": "unavailable",
            "note": str(exc),
            "signal1": None,
            "signal2": None,
        }), 200


_AFTERMATH_HISTORY_CACHE: dict = {}
_AFTERMATH_V3A_CACHE: dict = {}


@app.route("/api/market/vix-history")
def api_market_vix_history():
    """VIX daily closes from 2007-01-01 for chart overlays."""
    vix = _get_vix_by_date()
    history = [{"date": d, "vix": v} for d, v in sorted(vix.items()) if d >= "2007-01-01"]
    return jsonify({"history": history})


@app.route("/api/aftermath/history")
def api_aftermath_history():
    """Historical scan of all aftermath windows.

    Aftermath active day: rolling-10d VIX peak >= 28 AND current VIX <= peak * 0.90
    AND current VIX < 40. Consecutive active days are grouped into windows.
    """
    import time as _time
    # Memory cache (24h TTL — VIX history only adds one bar per day)
    cached = _AFTERMATH_HISTORY_CACHE.get("data")
    if cached and (_time.time() - _AFTERMATH_HISTORY_CACHE.get("ts", 0)) < 86400:
        return jsonify(cached)
    try:
        import pandas as pd
        from strategy.selector import AFTERMATH_PEAK_VIX_10D_MIN, AFTERMATH_OFF_PEAK_PCT
        vix_path = os.path.join(os.path.dirname(__file__), "..", "data", "market_cache", "yahoo__VIX__max__1d.pkl")
        df = pd.read_pickle(vix_path)
        vix = df["Close"].copy()
        vix.index = pd.to_datetime([d.date() for d in vix.index])
        vix = vix.sort_index()

        peak10 = vix.rolling(10, min_periods=10).max()
        off_peak = (peak10 - vix) / peak10
        active = (peak10 >= AFTERMATH_PEAK_VIX_10D_MIN) & (off_peak >= AFTERMATH_OFF_PEAK_PCT) & (vix < 40.0)

        # Group consecutive True spans into windows
        windows = []
        in_win = False
        cur_start = None
        cur_peak_at_start = None
        for d, is_active in active.items():
            if is_active and not in_win:
                in_win = True
                cur_start = d
                cur_peak_at_start = float(peak10.loc[d])
            elif not is_active and in_win:
                in_win = False
                end_d = d - pd.Timedelta(days=1)
                # find last actual active date <= end_d
                prior_active = active.loc[cur_start:end_d]
                last_active = prior_active[prior_active].index[-1] if (prior_active.any()) else cur_start
                windows.append({
                    "start": cur_start.strftime("%Y-%m-%d"),
                    "end":   last_active.strftime("%Y-%m-%d"),
                    "days":  int((last_active - cur_start).days) + 1,
                    "peak_at_start": round(cur_peak_at_start, 2),
                    "max_off_peak_pct": round(float(off_peak.loc[cur_start:last_active].max()) * 100, 2),
                })
        if in_win:  # still active at end of series
            last_d = active.index[-1]
            windows.append({
                "start": cur_start.strftime("%Y-%m-%d"),
                "end":   last_d.strftime("%Y-%m-%d"),
                "days":  int((last_d - cur_start).days) + 1,
                "peak_at_start": round(cur_peak_at_start, 2),
                "max_off_peak_pct": round(float(off_peak.loc[cur_start:last_d].max()) * 100, 2),
                "ongoing": True,
            })

        total_days = int(active.sum())
        total_obs  = int(active.notna().sum())
        scan_start = vix.index[0].strftime("%Y-%m-%d") if len(vix) else None
        scan_end   = vix.index[-1].strftime("%Y-%m-%d") if len(vix) else None

        payload = {
            "scan_start": scan_start,
            "scan_end":   scan_end,
            "total_windows": len(windows),
            "total_active_days": total_days,
            "active_days_pct": round((total_days / total_obs * 100) if total_obs else 0, 2),
            "avg_window_days": round(sum(w["days"] for w in windows) / len(windows), 1) if windows else None,
            "max_window_days": max((w["days"] for w in windows), default=None),
            "last_window": windows[-1] if windows else None,
            "windows": windows,
            "thresholds": {
                "peak_min": AFTERMATH_PEAK_VIX_10D_MIN,
                "off_peak_pct": AFTERMATH_OFF_PEAK_PCT * 100,
                "vix_max": 40.0,
            },
        }
        _AFTERMATH_HISTORY_CACHE["data"] = payload
        _AFTERMATH_HISTORY_CACHE["ts"] = _time.time()
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc), "windows": [], "total_windows": 0}), 200


@app.route("/api/aftermath/state")
def api_aftermath_state():
    """Aftermath addon state — surfaces is_aftermath() trigger from SPX selector.

    Aftermath = VIX peak回落 window. Currently active if:
      trailing 10d VIX peak >= 28 AND current VIX <= peak * (1 - 10%) AND vix < 40.
    """
    try:
        from signals.vix_regime import get_current_snapshot
        from strategy.selector import (
            is_aftermath,
            AFTERMATH_PEAK_VIX_10D_MIN,
            AFTERMATH_OFF_PEAK_PCT,
        )
        vix = get_current_snapshot()
        peak = vix.vix_peak_10d
        active = is_aftermath(vix)
        off_peak_pct = ((peak - vix.vix) / peak * 100.0) if peak and peak > 0 else None
        reason = None
        if not active:
            if peak is None:
                reason = "no_peak_data"
            elif peak < AFTERMATH_PEAK_VIX_10D_MIN:
                reason = f"peak_below_threshold ({peak:.1f} < {AFTERMATH_PEAK_VIX_10D_MIN})"
            elif vix.vix >= 40.0:
                reason = f"vix_above_extreme ({vix.vix:.1f} >= 40)"
            elif off_peak_pct is not None and off_peak_pct < AFTERMATH_OFF_PEAK_PCT * 100:
                reason = f"insufficient_off_peak ({off_peak_pct:.1f}% < {AFTERMATH_OFF_PEAK_PCT*100:.0f}%)"
            else:
                reason = "not_active"
        return jsonify({
            "active": active,
            "vix": round(vix.vix, 2),
            "vix_peak_10d": round(peak, 2) if peak else None,
            "off_peak_pct": round(off_peak_pct, 2) if off_peak_pct is not None else None,
            "threshold_off_peak_pct": AFTERMATH_OFF_PEAK_PCT * 100,
            "threshold_peak_min": AFTERMATH_PEAK_VIX_10D_MIN,
            "threshold_vix_max": 40.0,
            "regime": vix.regime.value if vix.regime else None,
            "trend": vix.trend.value if vix.trend else None,
            "reason": reason,
            "date": datetime.now(_ET).date().isoformat(),
        })
    except Exception as exc:
        return jsonify({
            "active": False,
            "error": str(exc),
            "date": datetime.now(_ET).date().isoformat(),
        }), 200


@app.route("/api/aftermath/v3a_trades")
def api_aftermath_v3a_trades():
    """V3-A IC_HV strategy P&L from Q064 research (R-20260512-03).

    Data source: research/q064/q064_p6_results.csv (authoritative Q064 output).
    Aggregates from research/q064/q064_p6_summary.csv (V3-A actual row).
    Cache: 24h TTL.
    """
    import time as _time
    cached = _AFTERMATH_V3A_CACHE.get("data")
    if cached and (_time.time() - _AFTERMATH_V3A_CACHE.get("ts", 0)) < 86400:
        return jsonify(cached)
    try:
        import csv as _csv
        base = os.path.join(os.path.dirname(__file__), "..", "research", "q064")
        trades_path  = os.path.normpath(os.path.join(base, "q064_p6_results.csv"))
        summary_path = os.path.normpath(os.path.join(base, "q064_p6_summary.csv"))

        # Summary row: "V3-A actual (production)"
        summary = {}
        with open(summary_path, newline="") as f:
            for row in _csv.DictReader(f):
                if "V3-A actual" in (row.get("version") or ""):
                    summary = row
                    break

        # Per-trade list
        trades = []
        with open(trades_path, newline="") as f:
            for row in _csv.DictReader(f):
                trades.append({
                    "entry_date":  row["entry_date"],
                    "exit_date":   row["exit_date"],
                    "exit_reason": row["exit_reason"],
                    "hold_days":   int(row["hold_days"]),
                    "vix_at_entry": round(float(row["vix_at_entry"]), 2),
                    "pnl":         round(float(row["v3a_pnl_actual"]), 2),
                    "bp":          round(float(row["v3a_bp_actual"]), 2),
                })

        def _f(key, digits=2):
            try:
                return round(float(summary[key]), digits)
            except (KeyError, ValueError, TypeError):
                return None

        payload = {
            "trade_count":        _f("n_trades", 0),
            "win_count":          int(round((_f("win_rate_pct") or 0) / 100 * (_f("n_trades", 0) or 0))),
            "win_rate_pct":       _f("win_rate_pct", 1),
            "avg_pnl":            _f("avg_pnl", 2),
            "median_pnl":         _f("median_pnl", 2),
            "total_pnl":          _f("total_pnl", 2),
            "worst_trade":        _f("worst_trade", 2),
            "best_trade":         _f("best_trade", 2),
            "avg_bp":             _f("avg_bp", 2),
            "dollar_per_bp_day":  _f("dollar_per_bp_day", 2),
            "scan_start": "2009-01-01",
            "scan_end":   "2025-06-30",
            "trades": trades,
        }
        _AFTERMATH_V3A_CACHE["data"] = payload
        _AFTERMATH_V3A_CACHE["ts"]   = _time.time()
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc), "trade_count": 0, "trades": []}), 200


@app.route("/api/aftermath/window-gates")
def api_aftermath_window_gates():
    """Gate reason for each aftermath window with no V3-A trade.

    Primary source: research/q064/q064_p7_skip_log.csv (exact select_strategy rationale
    from backtest replay + engine-level concurrent/spell check for blocked aftermath signals).
    """
    try:
        import csv as _csv
        from datetime import date as _date

        base        = os.path.join(os.path.dirname(__file__), "..", "research", "q064")
        skip_path   = os.path.normpath(os.path.join(base, "q064_p7_skip_log.csv"))
        trades_path = os.path.normpath(os.path.join(base, "q064_p6_results.csv"))

        # Load V3-A trades for concurrent-position check on "signal fired but blocked" windows
        trades = []
        with open(trades_path, newline="") as f:
            for row in _csv.DictReader(f):
                try:
                    trades.append({
                        "entry": _date.fromisoformat(row["entry_date"]),
                        "exit":  _date.fromisoformat(row["exit_date"]),
                    })
                except (KeyError, ValueError):
                    pass

        IC_HV_MAX = 2

        def _active_count(d: _date) -> int:
            return sum(1 for t in trades if t["entry"] < d <= t["exit"])

        def _short_label(row: dict) -> str:
            """Map P7 skip log row to a concise UI label."""
            rationale = row.get("rationale", "")
            strategy  = row.get("strategy",  "")
            window    = row.get("window_start", "")
            vix_str   = row.get("vix", "")

            if "(date not reached in backtest)" in rationale:
                return "模拟起始前" if window < "2009" else "回测数据截止后"

            if "EXTREME_VOL" in rationale:
                vix_label = f"{float(vix_str):.1f}" if vix_str else "?"
                return f"EXTREME_VOL (VIX {vix_label} ≥ 35)"

            if "VIX RISING" in rationale:
                return "VIX 上升期 — 等待企稳"

            if "BACKWARDATION" in rationale.upper():
                return "期限结构倒挂"

            # Selector fired V3-A / IC_HV aftermath signal — engine blocked it
            if "aftermath" in rationale and "bypass" in rationale:
                try:
                    d = _date.fromisoformat(window)
                    n = _active_count(d)
                    if n >= IC_HV_MAX:
                        return f"V3-A信号触发 · 满仓 {n}/{IC_HV_MAX}"
                    elif n == 1:
                        return f"V3-A信号触发 · Spell 配额/并发阻断 ({n}/2 open)"
                except ValueError:
                    pass
                return "V3-A信号触发 · Spell/并发上限"

            # Selector recommended a different HIGH_VOL strategy (not IC_HV aftermath path)
            if "Bull Put Spread" in strategy:
                return "BULLISH + IV LOW → BPS_HV 路径 (非V3-A)"
            if "Bear Call Spread" in strategy:
                return "BEARISH + IV NEUTRAL → BCS_HV 路径 (非V3-A)"
            if "Iron Condor" in strategy and "BULLISH" in rationale:
                return "BULLISH → IC_HV 对称 (非Aftermath路径)"
            if "Iron Condor" in strategy and "NEUTRAL" in rationale and "aftermath" not in rationale:
                return "NEUTRAL + IV LOW → IC_HV 对称 (非Aftermath路径)"

            # Fallback: trim rationale to reasonable display length
            return rationale[:60].rstrip() + ("…" if len(rationale) > 60 else "")

        gates = {}
        with open(skip_path, newline="") as f:
            for row in _csv.DictReader(f):
                wstart = row.get("window_start", "").strip()
                if not wstart:
                    continue
                label  = _short_label(row)
                detail = row.get("rationale", "").strip()
                gates[wstart] = {"label": label, "detail": detail}

        return jsonify({"gates": gates})
    except Exception as exc:
        return jsonify({"error": str(exc), "gates": {}}), 200


@app.route("/api/q019/flip-days")
def api_q019_flip_days():
    return jsonify(_load_q019_flip_days())


@app.route("/api/es/recommendation")
def api_es_recommendation():
    from strategy.selector import get_es_recommendation

    try:
        rec = get_es_recommendation(use_intraday=_is_market_hours())
        return _json_dc(rec)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/es/position")
def api_es_position():
    from datetime import date
    from strategy.state import read_state

    try:
        state = read_state()

        # Determine if an /ES short put position is open
        strategy_key = str(state.get("strategy_key") or "").strip().lower() if state else ""
        underlying   = str(state.get("underlying")   or "").upper()         if state else ""
        strategy_str = str(state.get("strategy")     or "").lower()         if state else ""
        is_es = state and (
            strategy_key == "es_short_put"
            or (underlying == "/ES" and "short put" in strategy_str)
        )

        if not is_es:
            return jsonify({"open": False, "entry_premium": None, "mark": None,
                            "ratio": None, "stop_level": "NONE",
                            "entry_date": None, "expiry": None, "dte": None})

        def _num(v):
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        entry_premium = _num(state.get("actual_premium")) or _num(state.get("model_premium"))
        expiry_str    = state.get("expiry")
        entry_date    = state.get("opened_at")
        short_strike  = _num(state.get("short_strike"))
        contracts     = _num(state.get("contracts")) or 1

        # DTE from expiry
        dte = None
        if expiry_str:
            try:
                dte = max((date.fromisoformat(str(expiry_str)) - date.today()).days, 0)
            except ValueError:
                pass

        # Mark from Schwab live positions
        mark = None
        ratio = None
        stop_level = "NONE"
        try:
            from schwab.client import get_account_positions

            pos_payload = get_account_positions()
            if (pos_payload.get("configured") and pos_payload.get("authenticated")
                    and not pos_payload.get("stale")):
                for pos in pos_payload.get("positions", []):
                    text = f"{pos.get('symbol', '')} {pos.get('description', '')}".upper()
                    qty  = _num(pos.get("quantity")) or 0.0
                    if abs(qty) > 0 and "/ES" in text and "PUT" in text:
                        mark = _num(pos.get("mark"))
                        break
        except Exception:
            pass

        if mark is not None and entry_premium and entry_premium > 0:
            ratio = round(mark / entry_premium, 3)
            if ratio >= 3.0:
                stop_level = "TRIGGER"
            elif ratio >= 2.0:
                stop_level = "WARNING"

        # Expiry DTE warning
        expiry_warning = dte is not None and dte <= 7

        return jsonify({
            "open":            True,
            "entry_premium":   entry_premium,
            "mark":            mark,
            "ratio":           ratio,
            "stop_level":      stop_level,
            "entry_date":      entry_date,
            "expiry":          expiry_str,
            "dte":             dte,
            "short_strike":    short_strike,
            "contracts":       int(contracts),
            "expiry_warning":  expiry_warning,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/es/stressed-span")
def api_es_stressed_span():
    from web.portfolio_surface import es_stressed_span_payload

    try:
        return jsonify(es_stressed_span_payload())
    except Exception as exc:
        return jsonify({
            "surface": "es_stressed_span",
            "status": "unavailable",
            "stress_band": "unavailable",
            "has_es_live_position": False,
            "error": str(exc),
        })


@app.route("/api/strategy-catalog")
def api_strategy_catalog():
    from strategy.catalog import strategy_catalog_payload
    return jsonify(strategy_catalog_payload())


@app.route("/api/sleeve-candidates")
def api_sleeve_candidates():
    from web.portfolio_surface import sleeve_candidates_payload

    return jsonify(sleeve_candidates_payload())


@app.route("/api/portfolio/summary")
def api_portfolio_summary():
    from web.portfolio_surface import portfolio_summary_payload

    return jsonify(portfolio_summary_payload())


@app.route("/api/sleeve-governance/state")
def api_sleeve_governance_state():
    from strategy.sleeve_governance import governance_dashboard_payload

    try:
        return jsonify(governance_dashboard_payload())
    except Exception as exc:
        return jsonify({
            "surface": "sleeve_governance",
            "status": "unavailable",
            "error": str(exc),
        }), 200


@app.route("/api/governance/backtest")
def api_governance_backtest():
    """SPEC-103 historical stress episode analysis from Q072 daily flags."""
    try:
        import pandas as pd
        from strategy.sleeve_governance import (
            Q072_DAILY_FLAGS,
            DECISION_LOG_PATH,
            _read_jsonl,
            stress_episode_from_flags,
            detect_second_leg_state,
            governance_caps,
        )

        daily = pd.read_csv(Q072_DAILY_FLAGS, parse_dates=["date"]).set_index("date")
        stress = stress_episode_from_flags(daily)
        second_leg = detect_second_leg_state(daily)

        total_days = len(daily)
        stress_days = int(stress.sum())
        second_leg_days = int(second_leg.sum())

        # Build episode list: contiguous runs of stress=True
        episodes = []
        in_ep = False
        ep_start = None
        for d, s in stress.items():
            if s and not in_ep:
                in_ep = True
                ep_start = d
            elif not s and in_ep:
                ep_end = d - pd.Timedelta(days=1)
                dur = int((stress[ep_start:ep_end]).sum())
                vix_col = "vix" if "vix" in daily.columns else None
                max_vix = float(daily.loc[ep_start:ep_end, vix_col].max()) if vix_col else None
                sl = bool(second_leg.loc[ep_start:ep_end].any())
                episodes.append({
                    "start": ep_start.strftime("%Y-%m-%d"),
                    "end":   ep_end.strftime("%Y-%m-%d"),
                    "trading_days": dur,
                    "max_vix": round(max_vix, 1) if max_vix else None,
                    "second_leg_triggered": sl,
                })
                in_ep = False
        if in_ep and ep_start is not None:
            ep_end = daily.index[-1]
            dur = int((stress[ep_start:ep_end]).sum())
            vix_col = "vix" if "vix" in daily.columns else None
            max_vix = float(daily.loc[ep_start:ep_end, vix_col].max()) if vix_col else None
            sl = bool(second_leg.loc[ep_start:ep_end].any())
            episodes.append({
                "start": ep_start.strftime("%Y-%m-%d"),
                "end":   ep_end.strftime("%Y-%m-%d"),
                "trading_days": dur,
                "max_vix": round(max_vix, 1) if max_vix else None,
                "second_leg_triggered": sl,
                "ongoing": True,
            })

        # Blocked entry rate from decision log
        decisions = _read_jsonl(DECISION_LOG_PATH, limit=5000)
        total_decided = len(decisions)
        total_blocked = sum(1 for r in decisions if r.get("accepted") is False)

        # Caps snapshot — call with stress=True so R5 shows the actual tighter cap
        caps = governance_caps(stress_episode_active=True)

        normal_days = total_days - stress_days
        n_second_leg_episodes = sum(1 for e in episodes if e.get("second_leg_triggered"))
        n_stress_only_episodes = len(episodes) - n_second_leg_episodes
        stress_only_days = stress_days - second_leg_days

        return jsonify({
            "status": "available",
            "data_range": {
                "start": daily.index[0].strftime("%Y-%m-%d"),
                "end":   daily.index[-1].strftime("%Y-%m-%d"),
                "total_trading_days": total_days,
            },
            "metrics": {
                "normal_days": normal_days,
                "normal_pct": round(normal_days / total_days * 100, 1) if total_days else 0,
                "stress_days": stress_days,
                "stress_pct": round(stress_days / total_days * 100, 1) if total_days else 0,
                "stress_only_days": stress_only_days,
                "stress_only_pct": round(stress_only_days / total_days * 100, 1) if total_days else 0,
                "second_leg_days": second_leg_days,
                "second_leg_pct": round(second_leg_days / total_days * 100, 1) if total_days else 0,
                "n_episodes": len(episodes),
                "n_stress_only_episodes": n_stress_only_episodes,
                "n_second_leg_episodes": n_second_leg_episodes,
                "avg_episode_days": round(stress_days / max(len(episodes), 1), 1),
                "total_decided": total_decided,
                "total_blocked": total_blocked,
                "blocked_rate_pct": round(total_blocked / total_decided * 100, 1) if total_decided else 0,
            },
            "episodes": episodes,
            "caps": caps,
        })
    except Exception as exc:
        return jsonify({"status": "unavailable", "error": str(exc)}), 200


@app.route("/api/governance/timeline")
def api_governance_timeline():
    """Daily VIX + SPX + regime flags for the governance regime chart."""
    try:
        import pandas as pd
        from strategy.sleeve_governance import (
            Q072_DAILY_FLAGS, DECISION_LOG_PATH, _read_jsonl,
            stress_episode_from_flags, detect_second_leg_state,
        )

        daily = pd.read_csv(Q072_DAILY_FLAGS, parse_dates=["date"]).set_index("date")
        stress = stress_episode_from_flags(daily)
        second_leg = detect_second_leg_state(daily)

        # Per-date regime string
        def _regime(s, sl):
            if sl: return "second"
            if s:  return "stress"
            return "normal"

        dates = [d.strftime("%Y-%m-%d") for d in daily.index]
        vix_vals = [round(float(v), 2) if not pd.isna(v) else None
                    for v in daily["vix"]] if "vix" in daily.columns else [None] * len(dates)
        regimes = [_regime(bool(s), bool(sl))
                   for s, sl in zip(stress.values, second_leg.values)]

        # Aftermath signal (SPEC-064 / Q070 BPS_HV permission gate) — separate
        # annotation layer, NOT a SPEC-103 governance regime. Can coexist with
        # stress/second-leg regimes. Sourced from q072_p1_daily_flags column.
        if "aftermath_active" in daily.columns:
            aftermath_flags = [bool(v) for v in daily["aftermath_active"].astype(bool).values]
            aftermath_dates = [d for d, f in zip(dates, aftermath_flags) if f]
        else:
            aftermath_flags = [False] * len(dates)
            aftermath_dates = []

        # DD Overlay active flag (Q042 — ddATH ≤ -4% Sleeve A / deeper Sleeve B)
        if "dd_overlay_active" in daily.columns:
            dd_overlay_flags = [bool(v) for v in daily["dd_overlay_active"].astype(bool).values]
            dd_overlay_dates = [d for d, f in zip(dates, dd_overlay_flags) if f]
        else:
            dd_overlay_flags = [False] * len(dates)
            dd_overlay_dates = []

        # HV blocked dates: VIX ≥ 22 AND second_leg active
        hv_blocked = [d for d, r, v in zip(dates, regimes, vix_vals)
                      if r == "second" and v is not None and v >= 22.0]

        # HV Ladder entries from backtest cache
        today = datetime.now(_ET).date().isoformat()
        bt_cache = None
        try:
            with open(_ES_DISK_CACHE_PATH, "r") as _f:
                _store = json.load(_f)
            mtime = _es_script_mtime()
            _keys = sorted(
                (k for k in _store if k.startswith("hvlad:2000-01-01:") and k.endswith(f"__{mtime}")),
                reverse=True,
            )
            if _keys:
                bt_cache = _store[_keys[0]]
        except Exception:
            pass

        hv_entries   = bt_cache.get("backtest_signal_dates", []) if bt_cache else []
        daily_curve  = bt_cache.get("daily_curve", []) if bt_cache else []

        # SPX from market cache (reuse existing helper)
        spx_by_date = _get_spx_by_date()
        spx_vals = [spx_by_date.get(d) for d in dates]

        # SPX MA10
        spx_ma10: list[float | None] = []
        for i, v in enumerate(spx_vals):
            if i < 9 or any(spx_vals[i-9:i+1][j] is None for j in range(10)):
                spx_ma10.append(None)
            else:
                spx_ma10.append(round(sum(spx_vals[i-9:i+1]) / 10, 2))  # type: ignore

        return jsonify({
            "status": "available",
            "dates":            dates,
            "vix":              vix_vals,
            "regimes":          regimes,
            "spx":              spx_vals,
            "spx_ma10":         spx_ma10,
            "hv_entries":       hv_entries,
            "hv_blocked":       hv_blocked,
            "daily_curve":      daily_curve,
            "aftermath_flags":   aftermath_flags,    # bool per date, parallel to dates
            "aftermath_dates":   aftermath_dates,    # date list of days where aftermath fired
            "dd_overlay_flags":  dd_overlay_flags,   # bool per date, parallel to dates
            "dd_overlay_dates":  dd_overlay_dates,   # date list of DD Overlay active days
        })
    except Exception as exc:
        return jsonify({"status": "unavailable", "error": str(exc)}), 200


@app.route("/api/etrade/balances")
def api_etrade_balances():
    from etrade.client import get_account_balances

    payload = get_account_balances()
    if not payload.get("configured") or not payload.get("authenticated") or payload.get("stale"):
        return jsonify({"error": "unavailable", **payload})
    return jsonify(payload)


@app.route("/api/etrade/positions")
def api_etrade_positions():
    from etrade.client import get_account_positions

    payload = get_account_positions()
    if not payload.get("configured") or not payload.get("authenticated") or payload.get("stale"):
        return jsonify({"error": "unavailable", **payload})
    return jsonify(payload)


@app.route("/etrade/reauth")
def etrade_reauth_page():
    return render_template("etrade_reauth.html")


@app.route("/api/etrade/status")
def api_etrade_status():
    from etrade.auth import token_status
    return jsonify(token_status())


@app.route("/api/etrade/request-token", methods=["POST"])
def api_etrade_request_token():
    """Get a fresh E-Trade request token + authorize URL. Saves request token
    to ~/.spxstrat/etrade_token.json so subsequent verifier exchange can find it."""
    from etrade.auth import request_token, is_configured
    if not is_configured():
        return jsonify({"ok": False, "error": "not_configured"}), 400
    try:
        payload = request_token()
        url = payload.get("authorize_url")
        if not url:
            return jsonify({"ok": False, "error": "no_authorize_url"}), 500
        return jsonify({"ok": True, "authorize_url": url, "expires_in_min": 5})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/etrade/exchange-verifier", methods=["POST"])
def api_etrade_exchange_verifier():
    """Exchange a verifier code for an access token. Verifier must be from the
    request_token issued via /api/etrade/request-token within the last ~5 min."""
    from etrade.auth import get_access_token, is_configured, token_status
    if not is_configured():
        return jsonify({"ok": False, "error": "not_configured"}), 400
    verifier = (flask_req.get_json(silent=True) or {}).get("verifier", "").strip()
    if not verifier:
        verifier = flask_req.form.get("verifier", "").strip()
    if not verifier:
        return jsonify({"ok": False, "error": "missing_verifier"}), 400
    try:
        get_access_token(verifier)
        return jsonify({"ok": True, "status": token_status()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/etrade/auth")
def api_etrade_auth():
    from etrade.auth import get_access_token, request_token

    verifier = flask_req.args.get("oauth_verifier")
    try:
        if verifier:
            get_access_token(verifier)
            return redirect("/")
        token_payload = request_token()
        authorize_url = token_payload.get("authorize_url")
        if not authorize_url:
            return redirect("/")
        return redirect(authorize_url)
    except Exception:
        return redirect("/")


@app.route("/api/q042/state")
def api_q042_state():
    try:
        from signals.q042_trigger import get_current_q042_snapshot
        from production.q042_positions import get_active_positions, get_lifetime_stats
        snap = get_current_q042_snapshot()
        positions = get_active_positions(paper=True)
        stats = get_lifetime_stats(paper=True)

        def _pos_dict(p):
            if p is None:
                return None
            return {
                "trade_id": p.trade_id,
                "entry_date": p.entry_date,
                "long_strike": p.long_strike,
                "short_strike": p.short_strike,
                "contracts": p.contracts,
                "expiry_date": p.expiry_date,
                "days_to_expiry": p.days_to_expiry,
                "is_active": p.is_active,
                "current_pnl": p.current_pnl,
            }

        return jsonify({
            "date": snap.date,
            "spx_close": snap.spx_close,
            "ath_running_max": snap.ath_running_max,
            "ddath_pct": round(snap.ddath * 100, 2),
            "sleeve_a": {
                "armed": snap.sleeve_a.armed,
                "active_position": _pos_dict(positions.get("A")),
                "stats": stats.get("A", {}),
            },
            "sleeve_b": {
                "armed": snap.sleeve_b.armed,
                "in_watching": snap.sleeve_b.in_watching,
                "watch_start_date": snap.sleeve_b.watch_start_date,
                "active_position": _pos_dict(positions.get("B")),
                "stats": stats.get("B", {}),
            },
            "combined_bp_pct": snap.combined_bp_pct,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_Q042_SPX_CACHE: dict = {}   # {"ts": float, "data": dict}
_Q042_BT_CACHE_MEM: dict = {}

_Q042_SPX_DISK_CACHE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "q042_spx_history_cache.json")
)


def _q042_spx_load_disk_cache(cache_key: str) -> dict | None:
    try:
        with open(_Q042_SPX_DISK_CACHE, "r") as f:
            blob = json.load(f)
        entry = blob.get(cache_key)
        if not entry:
            return None
        # Disk cache valid for 24h (much longer than memory cache); SPX history
        # only adds one new bar per trading day.
        if (time.time() - entry.get("ts", 0)) > 86400:
            return None
        return entry.get("payload")
    except Exception:
        return None


def _q042_spx_save_disk_cache(cache_key: str, payload: dict) -> None:
    try:
        blob: dict = {}
        try:
            with open(_Q042_SPX_DISK_CACHE, "r") as f:
                blob = json.load(f)
        except Exception:
            blob = {}
        blob[cache_key] = {"ts": time.time(), "payload": payload}
        tmp = _Q042_SPX_DISK_CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(blob, f)
        os.replace(tmp, _Q042_SPX_DISK_CACHE)
    except Exception:
        pass


@app.route("/api/q042/spx-history")
def api_q042_spx_history():
    import time as _time
    full = flask_req.args.get("full", "0") == "1"
    cache_key = "full" if full else "recent"
    cached = _Q042_SPX_CACHE.get(cache_key)
    if cached and (_time.time() - _Q042_SPX_CACHE.get(f"{cache_key}_ts", 0)) < 3600:
        return jsonify(cached)
    # Disk cache fallback — survives server restarts
    disk = _q042_spx_load_disk_cache(cache_key)
    if disk is not None:
        _Q042_SPX_CACHE[cache_key] = disk
        _Q042_SPX_CACHE[f"{cache_key}_ts"] = _time.time()
        return jsonify(disk)
    try:
        import yfinance as yf, pandas as pd
        df = yf.Ticker("^GSPC").history(start="2007-01-01", interval="1d")
        df.index = pd.to_datetime([d.date() for d in df.index])
        closes = df["Close"].sort_index()
        ath = closes.cummax()
        ddath = (closes / ath - 1) * 100
        ma10 = closes.rolling(10).mean()
        cutoff = closes.index[0] if full else (closes.index[-252] if len(closes) >= 252 else closes.index[0])
        history = []
        for d in closes.index[closes.index >= cutoff]:
            history.append({
                "date": d.strftime("%Y-%m-%d"),
                "close": round(float(closes[d]), 2),
                "ath": round(float(ath[d]), 2),
                "ddath_pct": round(float(ddath[d]), 2),
            })
        cur_close = float(closes.iloc[-1])
        cur_ma10  = float(ma10.iloc[-1]) if not pd.isna(ma10.iloc[-1]) else None
        payload = {
            "history": history,
            "current": {
                "close": round(cur_close, 2),
                "ma10":  round(cur_ma10, 2) if cur_ma10 else None,
                "above_ma10": cur_close > cur_ma10 if cur_ma10 else None,
            },
        }
        _Q042_SPX_CACHE[cache_key] = payload
        _Q042_SPX_CACHE[f"{cache_key}_ts"] = _time.time()
        _q042_spx_save_disk_cache(cache_key, payload)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/q042/backtest")
def api_q042_bt():
    import csv as _csv
    from datetime import datetime as _dt
    if _Q042_BT_CACHE_MEM:
        return jsonify(_Q042_BT_CACHE_MEM)
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "q042_backtest_trades.csv"))
    try:
        trades = []
        with open(path, newline="") as f:
            for row in _csv.DictReader(f):
                trades.append({
                    "sleeve_id":       row["sleeve_id"],
                    "signal_date":     row["signal_date"],
                    "entry_date":      row["entry_date"],
                    "exit_date":       row["exit_date"],
                    "ath_at_signal":   round(float(row["ath_at_signal"]), 2),
                    "ddath_at_signal": round(float(row["ddath_at_signal"]) * 100, 2),  # to %
                    "long_strike":     float(row["long_strike"]),
                    "short_strike":    float(row["short_strike"]),
                    "contracts":       float(row["contracts"]),
                    "debit_per_share": round(float(row["debit_per_share"]), 4),
                    "exit_pnl":        round(float(row["exit_pnl"]), 2),
                    "account_pct":     round(float(row["account_pct"]) * 100, 2),  # to %
                    "status":          row.get("status", "CLOSED"),
                })
        summary = {}
        for sleeve in ["A", "B"]:
            # Summary stats use CLOSED trades only — OPEN rows are MTM snapshots,
            # not realized outcomes (see RESEARCH_LOG R-20260510-11).
            st = [t for t in trades if t["sleeve_id"] == sleeve and t["status"] == "CLOSED"]
            if not st:
                continue
            wins = [t for t in st if t["exit_pnl"] > 0]
            held_days = [
                (_dt.strptime(t["exit_date"], "%Y-%m-%d") - _dt.strptime(t["entry_date"], "%Y-%m-%d")).days
                for t in st
            ]
            summary[sleeve] = {
                "n":           len(st),
                "wr":          round(len(wins) / len(st) * 100, 1),
                "avg_pnl":     round(sum(t["exit_pnl"] for t in st) / len(st), 0),
                "total_pnl":   round(sum(t["exit_pnl"] for t in st), 0),
                "worst_pnl":   round(min(t["exit_pnl"] for t in st), 0),
                "avg_dte_held": round(sum(held_days) / len(held_days), 0),
            }
        payload = {"trades": trades, "summary": summary}
        _Q042_BT_CACHE_MEM.update(payload)
        return jsonify(payload)
    except FileNotFoundError:
        return jsonify({"trades": [], "summary": {}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _q042_ledger_path() -> Path:
    return Path(__file__).parent.parent / "data" / "q042_paper_trades.jsonl"


def _q042_append(rec: dict) -> None:
    path = _q042_ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _q042_load_rows() -> list[dict]:
    path = _q042_ledger_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _q042_next_trade_id(sleeve: str, signal_date: str) -> str:
    """Trade ID: {SLEEVE}-{SIGNAL_DATE}-{NNN}.

    Existing daemon writes use 'A-YYYY-MM-DD' (no suffix). Append suffix when
    a same-sleeve+date entry already exists, so manual entries don't collide
    with auto entries.
    """
    rows = _q042_load_rows()
    same = [r for r in rows
            if r.get("sleeve_id") == sleeve
            and str(r.get("signal_date") or r.get("entry_target_date") or "")[:10] == signal_date
            and (r.get("event") or "open") == "open"]
    nth = len(same) + 1
    return f"{sleeve}-{signal_date}-{nth:03d}"


@app.route("/api/q042/draft")
def api_q042_draft():
    """Open draft for DD Overlay sleeve A or B.

    Returns suggested long/short call strikes (ATM and OTM) and expiry per
    SPEC-094.1: Sleeve A = +2.5% OTM at 30 DTE; Sleeve B = +5% OTM at 90 DTE.
    Strikes rounded to nearest $5 SPX grid. Est debit computed via BSM at
    current SPX/VIX.
    """
    sleeve = (flask_req.args.get("sleeve") or "A").upper()
    if sleeve not in ("A", "B"):
        return jsonify({"status": "error", "error": "sleeve must be A or B"}), 400

    try:
        from backtest.pricer import call_price
        from signals.trend import fetch_spx_history, get_current_trend
        from schwab.client import get_spx_quote, get_vix_quote
    except Exception as exc:
        return jsonify({"status": "error", "error": f"pricer/data import failed: {exc}"})

    # Live SPX
    spx = None
    try:
        q = get_spx_quote()
        if q.get("last") not in (None, ""):
            spx = float(q["last"])
    except Exception:
        pass
    if spx is None:
        try:
            df = fetch_spx_history(period="6mo")
            trend = get_current_trend(df, current_spx=None)
            spx = float(trend.spx)
        except Exception as exc:
            return jsonify({"status": "unavailable", "reason": f"spx not available: {exc}"})

    # Live VIX → sigma
    sigma = None
    try:
        q = get_vix_quote()
        v = q.get("last")
        if v not in (None, ""):
            sigma = max(float(v) / 100.0, 0.05)
    except Exception:
        pass
    if sigma is None:
        sigma = 0.18  # conservative default

    # Strikes per sleeve
    long_strike = int(round(float(spx) / 5.0) * 5)
    if sleeve == "A":
        short_pct = 1.025
        dte = 30
    else:
        short_pct = 1.05
        dte = 90
    short_strike = int(round(float(spx) * short_pct / 5.0) * 5)

    # BSM debit estimate: long call - short call
    try:
        long_p = call_price(float(spx), float(long_strike), int(dte), float(sigma))
        short_p = call_price(float(spx), float(short_strike), int(dte), float(sigma))
        est_debit = max(round(float(long_p) - float(short_p), 2), 0.0)
    except Exception as exc:
        return jsonify({"status": "error", "error": f"bsm failed: {exc}"})

    today = date.today()
    signal_date = today.isoformat()
    entry_target_date = (today + timedelta(days=1)).isoformat()
    expiry = (today + timedelta(days=int(dte))).isoformat()
    width = short_strike - long_strike
    max_loss_per_contract = round(est_debit * 100.0, 2)
    max_gain_per_contract = round((float(width) - est_debit) * 100.0, 2)

    return jsonify({
        "status":            "ok",
        "sleeve":            sleeve,
        "spx":               round(float(spx), 2),
        "vix":               round(float(sigma) * 100.0, 2),
        "sigma":             round(float(sigma), 4),
        "dte":               dte,
        "long_strike":       long_strike,
        "short_strike":      short_strike,
        "width":             width,
        "est_debit":         est_debit,
        "max_loss_per_contract":  max_loss_per_contract,
        "max_gain_per_contract":  max_gain_per_contract,
        "signal_date":       signal_date,
        "entry_target_date": entry_target_date,
        "expiry":            expiry,
    })


@app.route("/api/q042/position/open", methods=["POST"])
def api_q042_position_open():
    """Record a manual DD Overlay open. PM-decides paper vs real."""
    data = flask_req.get_json(silent=True) or {}
    now = datetime.now(_ET)
    sleeve = (data.get("sleeve_id") or "").upper()
    if sleeve not in ("A", "B"):
        return jsonify({"status": "error", "error": "sleeve_id must be A or B"}), 400

    required = ["long_strike", "short_strike", "contracts", "expiry"]
    missing = [k for k in required if data.get(k) in (None, "")]
    if missing:
        return jsonify({"status": "error", "error": f"missing fields: {', '.join(missing)}"}), 400

    signal_date = data.get("signal_date") or now.date().isoformat()
    rec = {
        "trade_id":          _q042_next_trade_id(sleeve, signal_date),
        "event":             "open",
        "timestamp":         now.isoformat(timespec="seconds"),
        "sleeve_id":         sleeve,
        "source":            "manual",
        "signal_date":       signal_date,
        "entry_target_date": data.get("entry_target_date") or (datetime.fromisoformat(signal_date).date() + timedelta(days=1)).isoformat(),
        "expiry":            data.get("expiry"),
        "option_type":       "CALL",
        "long_strike":       int(data.get("long_strike")),
        "short_strike":      int(data.get("short_strike")),
        "contracts":         int(data.get("contracts")),
        "est_debit":         float(data.get("est_debit") or 0.0),
        "fill_debit":        float(data["fill_debit"]) if data.get("fill_debit") not in (None, "") else None,
        "entry_spx":         float(data["entry_spx"]) if data.get("entry_spx") not in (None, "") else None,
        "entry_vix":         float(data["entry_vix"]) if data.get("entry_vix") not in (None, "") else None,
        "paper_trade":       bool(data.get("paper_trade", False)),
        "settled":           False,
        "exit_pnl":          None,
        "note":              data.get("note", "") or "",
    }
    _q042_append(rec)
    return jsonify({"status": "ok", "trade_id": rec["trade_id"], "record": rec})


@app.route("/api/q042/position/note", methods=["POST"])
def api_q042_position_note():
    """Append a free-form note, optionally linked to a sleeve and/or trade_id."""
    data = flask_req.get_json(silent=True) or {}
    now = datetime.now(_ET)
    note = (data.get("note") or "").strip()
    if not note:
        return jsonify({"status": "error", "error": "note text required"}), 400
    rec = {
        "event":     "note",
        "timestamp": now.isoformat(timespec="seconds"),
        "sleeve_id": (data.get("sleeve_id") or None) and str(data["sleeve_id"]).upper(),
        "trade_id":  data.get("trade_id"),
        "source":    "manual",
        "note":      note,
    }
    _q042_append(rec)
    return jsonify({"status": "ok", "record": rec})


@app.route("/api/q042/paper")
def api_q042_paper():
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "q042_paper_trades.jsonl"))
    try:
        trades = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))
        return jsonify(trades)
    except FileNotFoundError:
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/attribution")
def api_portfolio_attribution():
    from web.portfolio_surface import attribution_payload

    return jsonify(attribution_payload())


@app.route("/api/portfolio/daily-history")
def api_portfolio_daily_history():
    """Daily portfolio snapshot history for /journal page.

    Query params:
      days: limit to last N calendar days (default 90, 'all' for all records)
    Returns full JSONL records (schema v2) for the requested window.
    """
    history_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "daily_snapshot.jsonl")
    )
    if not os.path.exists(history_path):
        return jsonify({"status": "no_history", "records": [], "count": 0})

    records: list[dict] = []
    try:
        with open(history_path) as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc), "records": [], "count": 0})

    if not records:
        return jsonify({"status": "no_history", "records": [], "count": 0})

    # Sort by date ascending (defensive — file is append-only but resilient)
    records.sort(key=lambda r: r.get("date") or "")

    days_arg = flask_req.args.get("days", "90")
    if days_arg != "all":
        try:
            n_days = int(days_arg)
            from datetime import date as _date, timedelta as _td
            cutoff = (_date.today() - _td(days=n_days)).isoformat()
            records = [r for r in records if (r.get("date") or "") >= cutoff]
        except ValueError:
            pass

    status = "available" if len(records) >= 5 else "warming_up"
    return jsonify({
        "status": status,
        "records": records,
        "count": len(records),
        "earliest": records[0].get("date") if records else None,
        "latest": records[-1].get("date") if records else None,
    })


@app.route("/api/portfolio/nlv-change")
def api_portfolio_nlv_change():
    """Today's combined NLV vs prior snapshot. Fed by scripts/daily_snapshot.py."""
    history_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "daily_snapshot.jsonl")
    )
    if not os.path.exists(history_path):
        return jsonify({"status": "no_history"})

    records: list[dict] = []
    try:
        with open(history_path) as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)})

    if not records:
        return jsonify({"status": "no_history"})

    today_iso = datetime.now(_ET).date().isoformat()

    # Live current NLV: reuse portfolio summary aggregation
    try:
        from schwab.client import live_position_snapshot
        from strategy.state import read_state
        from web.portfolio_surface import portfolio_summary_payload

        summary = portfolio_summary_payload()
        accounts = summary.get("account_breakdown") or {}
        schwab_nlv = float(accounts.get("schwab_nlv") or 0.0)
        etrade_nlv = float(accounts.get("etrade_nlv") or 0.0) if accounts.get("etrade_nlv") else 0.0
        today_combined = schwab_nlv + etrade_nlv
    except Exception:
        # Fall back to most recent recorded value
        today_combined = float(records[-1].get("combined_nlv") or 0.0)

    prior = [r for r in records if r.get("date") and r["date"] < today_iso]
    if not prior:
        return jsonify({
            "status": "first_day",
            "today_nlv": round(today_combined, 2),
            "history_days": len(records),
        })
    prev = prior[-1]
    prev_nlv = float(prev.get("combined_nlv") or 0.0)
    change_dollars = today_combined - prev_nlv
    change_pct = (change_dollars / prev_nlv * 100.0) if prev_nlv > 0 else 0.0

    # MTD / YTD
    from datetime import date as _date
    today_date = _date.fromisoformat(today_iso)
    mtd_start = today_date.replace(day=1).isoformat()
    ytd_start = today_date.replace(month=1, day=1).isoformat()
    mtd_rows = [r for r in records if r.get("date") and r["date"] >= mtd_start and r["date"] < today_iso]
    ytd_rows = [r for r in records if r.get("date") and r["date"] >= ytd_start and r["date"] < today_iso]

    def _pct_from(rows):
        if not rows:
            return None
        anchor = float(rows[0].get("combined_nlv") or 0.0)
        if anchor <= 0:
            return None
        return round((today_combined - anchor) / anchor * 100.0, 2)

    return jsonify({
        "status": "available",
        "today_nlv": round(today_combined, 2),
        "prev_nlv": round(prev_nlv, 2),
        "prev_date": prev.get("date"),
        "change_dollars": round(change_dollars, 2),
        "change_pct": round(change_pct, 3),
        "mtd_pct": _pct_from(mtd_rows),
        "ytd_pct": _pct_from(ytd_rows),
        "history_days": len(records),
    })


@app.route("/api/q041/overview")
def api_q041_overview():
    try:
        return jsonify(_build_q041_overview_payload())
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
            "tier_status": {},
            "backtest_summary": {"by_symbol": {}, "tier2_combined": None},
            "paper_progress": {"status": "unavailable", "by_tier": {}, "by_symbol": {}, "curves": {}, "iv_entry": {}, "bp_timeline": []},
            "attribution": {"status": "pending_quant_input"},
            "risk_visibility": {"joint_bp": None, "idle_day_capture": None, "bp_fill_contribution": None, "worst_day_overlap": None, "shock": _q041_shock_metrics()},
        })


@app.route("/api/portfolio/bp-timeline")
def api_portfolio_bp_timeline():
    import csv, os

    path = os.path.join(os.path.dirname(__file__), "..", "data", "q045_phase2d_idle_bp_timeline.csv")
    try:
        rows = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_val = row.get("") or row.get("date") or ""
                if not date_val:
                    continue
                rows.append({
                    "date":      date_val,
                    "j0_bp_pct": float(row["j0_bp_pct"]) if row.get("j0_bp_pct") not in (None, "") else 0.0,
                    "j3_bp_pct": float(row["j3_bp_pct"]) if row.get("j3_bp_pct") not in (None, "") else 0.0,
                    "j0_n_open": int(float(row["j0_n_open"])) if row.get("j0_n_open") not in (None, "") else 0,
                    "j3_n_open": int(float(row["j3_n_open"])) if row.get("j3_n_open") not in (None, "") else 0,
                })
        return jsonify({"status": "ok", "rows": rows, "count": len(rows)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


_ES_BT_CACHE: dict = {}
_Q041_BT_CACHE: dict = {}

# ROE denominator constants (SPEC-096)
# Research layer uses $50k per-sleeve equity; display layer scales to $500k account level.
_Q041_ACCOUNT_EQUITY = 500_000.0   # account-level denominator (same as /ES)
_Q041_SLEEVE_EQUITY  =  50_000.0   # per-sleeve BP deployed (research layer starting equity)

_ES_DISK_CACHE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "es_backtest_cache.json")
)
_ES_SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "research", "strategies", "ES_puts", "backtest.py")
)


def _es_script_mtime() -> str:
    try:
        return str(int(os.path.getmtime(_ES_SCRIPT_PATH)))
    except OSError:
        return "0"


def _load_es_disk_cache(cache_key: str) -> dict | None:
    try:
        with open(_ES_DISK_CACHE_PATH, "r") as f:
            store = json.load(f)
        return store.get(f"{cache_key}__{_es_script_mtime()}")
    except Exception:
        return None


def _save_es_disk_cache(cache_key: str, payload: dict) -> None:
    try:
        try:
            with open(_ES_DISK_CACHE_PATH, "r") as f:
                store = json.load(f)
        except Exception:
            store = {}
        store[f"{cache_key}__{_es_script_mtime()}"] = payload
        tmp = _ES_DISK_CACHE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(store, f)
        os.replace(tmp, _ES_DISK_CACHE_PATH)
    except Exception:
        pass


def _es_trade_summary_metrics(result) -> dict:
    trades = result.trades
    portfolio = result.portfolio_metrics or {}
    bootstrap = result.bootstrap or {}
    stress = result.stress_metrics or {}
    wins = sum(1 for trade in trades if trade.pnl > 0)
    worst_trade = min((trade.pnl for trade in trades), default=0.0)
    initial_equity = 500_000.0
    return {
        "n_trades": len(trades),
        "ann_roe_geometric": portfolio.get("ann_return"),
        "sharpe": portfolio.get("daily_sharpe"),
        "max_dd": portfolio.get("max_drawdown"),
        "worst_trade_pct_nlv": (worst_trade / initial_equity) if trades else 0.0,
        "win_rate": (wins / len(trades)) if trades else 0.0,
        "active_days_pct": portfolio.get("active_days_pct"),
        "bootstrap_sig_rate": bootstrap.get("sig_rate"),
        "bootstrap_ci_lo": bootstrap.get("ci_lo"),
        "stress_worst_single_pct_nlv": stress.get("stress_worst_single_pct_nlv"),
        "stress_cluster_pct": stress.get("stress_cluster_pct"),
    }


def _default_v2f_caveats() -> list[str]:
    return [
        "BS-flat synthetic data; OTM put premium may be understated ~2-3% (skew).",
        "STOP_MULT=15 triggered rarely in 26y research; live trigger frequency remains unvalidated.",
        "Bootstrap significance is alive-but-borderline edge, not production-grade alpha proof.",
        "BSH / dynamic leverage interaction with V2f remains untested; Phase 3/4 results still belong to V0.",
        "M1 1987 stress worst single remains slightly beyond the original -15% veto threshold.",
    ]


def _default_hvlad_caveats() -> list[str]:
    return [
        "BS-flat pricing; OTM put premium underestimated ~17-25% (Q057).",
        "G6 deploys only ~21% of trading days; accept low capital deployment.",
        "Bootstrap sig supports paper promotion, not production certainty.",
        "STOP=15 unused in historical sample; retained as fail-safe.",
    ]


def _result_window_pnl_pct(result, start: str, end: str) -> float | None:
    rows = [
        row for row in (result.daily_rows or [])
        if start <= getattr(row, "date", "") <= end
    ]
    if not rows:
        return None
    pnl = sum(float(getattr(row, "total_pnl", 0.0) or 0.0) for row in rows)
    return pnl / 500_000.0


def _purge_v2f_cache_entries() -> None:
    for key in list(_ES_BT_CACHE.keys()):
        if str(key).startswith("v2f:"):
            _ES_BT_CACHE.pop(key, None)
    try:
        with open(_ES_DISK_CACHE_PATH, "r") as f:
            store = json.load(f)
    except Exception:
        return
    next_store = {k: v for k, v in store.items() if not str(k).startswith("v2f:")}
    if next_store == store:
        return
    tmp = _ES_DISK_CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(next_store, f)
    os.replace(tmp, _ES_DISK_CACHE_PATH)


def _is_v2f_m1_payload(payload: dict | None) -> bool:
    return isinstance(payload, dict) and "v2f_baseline" in payload and "v2f_m1" in payload and "m1_delta" in payload


def _is_hvlad_payload(payload: dict | None) -> bool:
    return (isinstance(payload, dict)
            and "hvlad_metrics" in payload
            and "hv_delta" in payload
            and "backtest_signal_dates" in payload
            and "daily_curve" in payload)


def _purge_hvlad_cache_entries() -> None:
    for key in list(_ES_BT_CACHE.keys()):
        if str(key).startswith("hvlad:"):
            _ES_BT_CACHE.pop(key, None)
    try:
        with open(_ES_DISK_CACHE_PATH, "r") as f:
            store = json.load(f)
    except Exception:
        return
    next_store = {k: v for k, v in store.items() if not str(k).startswith("hvlad:")}
    if next_store == store:
        return
    tmp = _ES_DISK_CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(next_store, f)
    os.replace(tmp, _ES_DISK_CACHE_PATH)


def _hvlad_paper_state() -> dict:
    path = Path(__file__).parent.parent / "data" / "q071_hv_paper_trades.jsonl"
    rows = _load_hvlad_paper_trades()
    rows.sort(key=lambda row: str(row.get("signal_date") or row.get("timestamp") or ""))
    return {
        "path": "data/q071_hv_paper_trades.jsonl",
        "total_entries": len(rows),
        "last_signal": rows[-1] if rows else None,
        "status": "paper_observation",
    }


def _load_hvlad_paper_trades() -> list[dict]:
    path = Path(__file__).parent.parent / "data" / "q071_hv_paper_trades.jsonl"
    rows: list[dict] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda row: str(row.get("timestamp") or row.get("signal_date") or ""), reverse=True)
    return rows


def _hvlad_business_days_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    # Local lightweight copy; exact holiday handling is not critical for read-only display.
    holidays = {
        "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
        "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
        "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    }
    days = 0
    cur = start
    while cur < end:
        cur += timedelta(days=1)
        if cur.weekday() < 5 and cur.isoformat() not in holidays:
            days += 1
    return days


def _hvlad_active_slots(rows: list[dict], today: date) -> int:
    """Count open slots that are: open event present, not yet closed, within 49d signal window.

    Legacy rows without `event` field are treated as event="open" for back-compat.
    Trade lifecycle keyed by trade_id; rows without trade_id fall back to legacy
    signal_date-only counting (one row = one slot).
    """
    # Build trade lifecycle state
    by_tid: dict[str, dict] = {}
    legacy_rows: list[dict] = []
    for row in rows:
        event = row.get("event") or "open"
        if event == "note":
            continue
        tid = row.get("trade_id")
        if not tid:
            legacy_rows.append(row)
            continue
        st = by_tid.setdefault(tid, {"open_date": None, "closed": False})
        if event == "open":
            raw = row.get("signal_date")
            if raw:
                try:
                    st["open_date"] = date.fromisoformat(str(raw)[:10])
                except ValueError:
                    pass
        elif event == "close":
            st["closed"] = True

    active = 0
    for st in by_tid.values():
        if st["closed"] or not st["open_date"]:
            continue
        if 0 <= (today - st["open_date"]).days <= 49:
            active += 1

    # Legacy rows (no trade_id): each row counted as one slot if within window
    for row in legacy_rows:
        raw = row.get("signal_date")
        if not raw:
            continue
        try:
            signal_date = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if 0 <= (today - signal_date).days <= 49:
            active += 1
    return min(active, 5)


def _hvlad_cadence_status(rows: list[dict], today: date, active_slots: int) -> tuple[bool, int | None]:
    signal_dates: list[date] = []
    for row in rows:
        raw = row.get("signal_date")
        if not raw:
            continue
        try:
            signal_dates.append(date.fromisoformat(str(raw)[:10]))
        except ValueError:
            continue
    if not signal_dates:
        return True, None
    min_gap = 10 if active_slots >= 4 else 5
    elapsed = _hvlad_business_days_between(max(signal_dates), today)
    return elapsed >= min_gap, elapsed


def _hvlad_vix_context() -> dict:
    try:
        from signals.vix_regime import fetch_vix_history
        from schwab.client import get_vix_quote

        df = fetch_vix_history(period="1mo")
        latest_date = df.index[-1].strftime("%Y-%m-%d")
        eod_vix = float(df["vix"].iloc[-1])
        vix_5td_avg = float(df["vix"].iloc[-5:].mean())
        quote = None
        current_vix = eod_vix
        quote_time = None
        stale = False
        source = "yfinance_eod"
        try:
            quote = get_vix_quote()
            last = quote.get("last")
            if last not in (None, ""):
                current_vix = float(last)
                source = "schwab_quote"
            quote_time = quote.get("quote_time")
            if quote_time:
                ts = datetime.fromisoformat(str(quote_time).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=_ET)
                stale = ts.astimezone(_ET).date() < (datetime.now(_ET).date() - timedelta(days=1))
        except Exception:
            quote = None
        hist = [{"date": idx.strftime("%Y-%m-%d"), "vix": float(row["vix"])} for idx, row in df.tail(10).iterrows()]
        return {
            "ok": True,
            "vix_current": current_vix,
            "vix_eod": eod_vix,
            "vix_5td_avg": vix_5td_avg,
            "latest_close_date": latest_date,
            "quote_time": quote_time,
            "source": source,
            "stale": stale,
            "history_tail": hist,
            "raw_quote": quote,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stale": True}


def _hvlad_trend_status() -> dict:
    try:
        from signals.trend import TrendSignal, fetch_spx_history, get_current_trend
        from schwab.client import get_spx_quote

        spx_quote = None
        current_spx = None
        try:
            spx_quote = get_spx_quote()
            if spx_quote.get("last") not in (None, ""):
                current_spx = float(spx_quote["last"])
        except Exception:
            pass
        df = fetch_spx_history(period="2y")
        trend = get_current_trend(df, current_spx=current_spx)
        warmed = len(df) >= 64
        return {
            "ok": True,
            "warmed": warmed,
            "trend_ok": trend.signal == TrendSignal.BULLISH,
            "trend": trend.signal.value,
            "spx": trend.spx,
            "ma50": trend.ma50,
            "ma_gap_pct": trend.ma_gap_pct,
            "spx_quote_time": (spx_quote or {}).get("quote_time"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "warmed": False,
            "trend_ok": False,
            "trend": "unavailable",
            "error": str(exc),
        }


def _hvlad_vix_days_counts() -> dict:
    vix = _get_vix_by_date()
    if not vix:
        return {"days_30": None, "days_90": None, "days_365": None, "max_vix": None}
    items = sorted(vix.items())
    latest = datetime.fromisoformat(items[-1][0]).date()
    result = {"max_vix": max(v for _, v in items)}
    for window in (30, 90, 365):
        cutoff = latest - timedelta(days=window)
        result[f"days_{window}"] = sum(1 for d, value in items if datetime.fromisoformat(d).date() >= cutoff and value >= 22.0)
    return result


def _load_hvlad_crisis_windows() -> list[dict]:
    path = Path(__file__).parent.parent / "research" / "q071" / "q071_p5_crisis.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in ("n_active", "window_pnl", "window_pnl_pct_nlv", "worst_cluster_pct_nlv", "worst_trade_nlv_pct", "ann_ret_in_window"):
            try:
                row[key] = float(row[key])
            except Exception:
                pass
    return rows


def _pct_point_delta(new_value, old_value) -> float | None:
    if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
        return (new_value - old_value) * 100.0
    return None


def _numeric_delta(new_value, old_value) -> float | None:
    if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
        return new_value - old_value
    return None


_VIX_BY_DATE: dict | None = None
_SPX_BY_DATE: dict | None = None

_Q041_DISK_CACHE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "q041_backtest_cache.json")
)
_Q041_PAPER_LEDGER_FILE = Path(__file__).parent.parent / "data" / "q041_paper_trades.jsonl"
_Q041_SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "research", "strategies", "q041_csp_backtest.py")
)


def _q041_script_mtime() -> str:
    try:
        return str(int(os.path.getmtime(_Q041_SCRIPT_PATH)))
    except OSError:
        return "0"


def _q041_disk_cache_key(start_date: str) -> str:
    return f"{start_date}__{_q041_script_mtime()}"


def _load_q041_disk_cache(start_date: str) -> dict | None:
    try:
        with open(_Q041_DISK_CACHE_PATH, "r") as f:
            store = json.load(f)
        entry = store.get(_q041_disk_cache_key(start_date))
        return entry if isinstance(entry, dict) else None
    except Exception:
        return None


def _save_q041_disk_cache(start_date: str, payload: dict) -> None:
    try:
        try:
            with open(_Q041_DISK_CACHE_PATH, "r") as f:
                store = json.load(f)
        except Exception:
            store = {}
        store[_q041_disk_cache_key(start_date)] = payload
        tmp = _Q041_DISK_CACHE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(store, f)
        os.replace(tmp, _Q041_DISK_CACHE_PATH)
    except Exception:
        pass


def _q041_paper_ledger_path() -> Path:
    return Path(os.environ.get("Q041_PAPER_LEDGER_FILE", _Q041_PAPER_LEDGER_FILE))


def _read_q041_paper_rows() -> list[dict]:
    path = _q041_paper_ledger_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    except Exception:
        return []
    return rows


def _get_q041_backtest_payload(start_date: str = "2022-05-06") -> dict:
    cached = _Q041_BT_CACHE.get(start_date)
    if cached:
        return cached
    disk = _load_q041_disk_cache(start_date)
    if disk:
        _Q041_BT_CACHE[start_date] = disk
        return disk
    payload = _build_q041_payload(start_date)
    _Q041_BT_CACHE[start_date] = payload
    _save_q041_disk_cache(start_date, payload)
    return payload


def _q041_shock_metrics() -> dict:
    return {
        "tier1_spx": {"mark_loss": 61585.0, "pct_nlv": 12.3, "stress_bp_pct": 27.2},
        "tier2_googl": {"mark_loss": 4726.0, "pct_nlv": 0.9, "stress_bp_pct": 2.0},
        "tier2_amzn": {"mark_loss": 3669.0, "pct_nlv": 0.7, "stress_bp_pct": 1.5},
    }


def _q041_sleeve_bp_cap_pct(symbol: str, attribution_data: dict | None = None) -> float | None:
    attribution_data = attribution_data or {}
    for sleeve in attribution_data.get("sleeves_simulated", []):
        if str(sleeve.get("symbol")) == symbol:
            return _num(sleeve.get("bp_cap_pct"))
    return {"SPX": 20.0, "GOOGL": 7.5, "AMZN": 7.5}.get(symbol)


def _q041_backtest_summaries(backtest_payload: dict, attribution_data: dict | None = None) -> dict:
    attribution_data = attribution_data or {}
    account_size = _num(attribution_data.get("account_size_usd")) or 500000.0
    rows: dict[str, dict] = {}
    sleeves = backtest_payload.get("sleeves", []) if isinstance(backtest_payload, dict) else []
    for sleeve in sleeves:
        symbol = str(sleeve.get("symbol") or "")
        trades = sleeve.get("trades") or []
        equity_curve = sleeve.get("equity_curve") or []
        total_pnl = _num(sleeve.get("total_pnl")) or 0.0
        bp_cap_pct = _q041_sleeve_bp_cap_pct(symbol, attribution_data) or 0.0
        win_rate_pct = _num(sleeve.get("win_rate_pct")) or 0.0
        worst_trade = min((_num(t.get("pnl")) or 0.0 for t in trades), default=0.0)
        avg_pnl = total_pnl / len(trades) if trades else None
        ann_roe = None
        sharpe = None
        avg_bp_day = None
        if equity_curve and len(equity_curve) > 1:
            init_equity = _num(equity_curve[0].get("equity")) or account_size
            end_equity = _num(equity_curve[-1].get("equity")) or init_equity
            first_date = equity_curve[0].get("date")
            last_date = equity_curve[-1].get("date")
            try:
                years = max((datetime.fromisoformat(str(last_date)) - datetime.fromisoformat(str(first_date))).days / 365.25, 0.01)
            except Exception:
                years = None
            if years and init_equity > 0:
                sleeve_ann_roe = ((end_equity / init_equity) ** (1.0 / years) - 1.0) * 100.0
                # Scale sleeve-level ROE to account level (SPEC-096 F1):
                # sleeve basis = $50k; account basis = $500k → ÷ 10
                ann_roe = sleeve_ann_roe * (_Q041_SLEEVE_EQUITY / _Q041_ACCOUNT_EQUITY)
            returns: list[float] = []
            for prev, cur in zip(equity_curve[:-1], equity_curve[1:]):
                prev_eq = _num(prev.get("equity"))
                cur_eq = _num(cur.get("equity"))
                if prev_eq and cur_eq and prev_eq > 0 and cur_eq != prev_eq:
                    returns.append((cur_eq - prev_eq) / prev_eq)
            if len(returns) > 1:
                mean_ret = sum(returns) / len(returns)
                variance = sum((ret - mean_ret) ** 2 for ret in returns) / len(returns)
                if variance > 0:
                    sharpe = mean_ret / (variance ** 0.5) * (52 ** 0.5)
        if trades and bp_cap_pct > 0:
            bp_per_trade = account_size * bp_cap_pct / 100.0
            bp_days = 0.0
            for trade in trades:
                entry_date = trade.get("entry_date")
                exit_date = trade.get("exit_date")
                try:
                    held_days = max((datetime.fromisoformat(str(exit_date)[:10]) - datetime.fromisoformat(str(entry_date)[:10])).days, 1)
                except Exception:
                    held_days = 1
                bp_days += bp_per_trade * held_days
            if bp_days > 0:
                avg_bp_day = total_pnl / bp_days
        rows[symbol] = {
            "symbol": symbol,
            "label": sleeve.get("label"),
            "n_trades": int(sleeve.get("n_trades") or len(trades)),
            "win_rate_pct": round(win_rate_pct, 1),
            "avg_pnl_per_trade": round(avg_pnl, 2) if avg_pnl is not None else None,
            "ann_roe_pct": round(ann_roe, 2) if ann_roe is not None else None,
            "sharpe": round(sharpe, 2) if sharpe is not None else None,
            "avg_pnl_per_bp_day": round(avg_bp_day, 6) if avg_bp_day is not None else None,
            "worst_trade": round(worst_trade, 2),
            "bp_cap_pct": bp_cap_pct,
        }
    tier2_symbols = [rows[sym] for sym in ("GOOGL", "AMZN") if sym in rows]
    tier2_combined = None
    if tier2_symbols:
        total_trades = sum(item["n_trades"] for item in tier2_symbols)
        total_bp = sum((item["bp_cap_pct"] or 0.0) for item in tier2_symbols)
        weighted = lambda key: (
            sum((item[key] or 0.0) * item["n_trades"] for item in tier2_symbols) / total_trades
            if total_trades else None
        )
        tier2_combined = {
            "symbol": "TIER2",
            "n_trades": total_trades,
            "win_rate_pct": round(weighted("win_rate_pct"), 1) if weighted("win_rate_pct") is not None else None,
            "avg_pnl_per_trade": round(weighted("avg_pnl_per_trade"), 2) if weighted("avg_pnl_per_trade") is not None else None,
            "ann_roe_pct": round(sum((item["ann_roe_pct"] or 0.0) for item in tier2_symbols), 2) if any(item["ann_roe_pct"] is not None for item in tier2_symbols) else None,
            "sharpe": round(weighted("sharpe"), 2) if weighted("sharpe") is not None else None,
            "avg_pnl_per_bp_day": round(weighted("avg_pnl_per_bp_day"), 6) if weighted("avg_pnl_per_bp_day") is not None else None,
            "worst_trade": round(min(item["worst_trade"] for item in tier2_symbols), 2),
            "bp_cap_pct": round(total_bp, 2),
        }
    return {"by_symbol": rows, "tier2_combined": tier2_combined}


def _q041_paper_progress() -> dict:
    rows = _read_q041_paper_rows()
    if not rows:
        return {
            "status": "unavailable",
            "reason": "paper ledger unavailable",
            "tier2_goal": 20,
            "by_tier": {"tier1": {"count": 0}, "tier2": {"count": 0}, "tier3": {"count": 0}},
            "by_symbol": {},
            "curves": {},
            "iv_entry": {},
            "bp_timeline": [],
        }

    by_tier = {"tier1": {"count": 0}, "tier2": {"count": 0}, "tier3": {"count": 0}}
    by_symbol: dict[str, dict] = {}
    curves: dict[str, dict[str, float]] = {}
    iv_entry: dict[str, list[float]] = {}
    timeline: dict[str, dict[str, float]] = {}
    for row in rows:
        tier = str(row.get("tier") or "")
        symbol = str(row.get("symbol") or "")
        if tier in by_tier:
            by_tier[tier]["count"] += 1
        by_symbol.setdefault(symbol, {"count": 0, "closed": 0, "open": 0})
        by_symbol[symbol]["count"] += 1
        status = str(row.get("status") or "")
        if status == "open":
            by_symbol[symbol]["open"] += 1
        else:
            by_symbol[symbol]["closed"] += 1
        iv_val = _num(row.get("iv_entry"))
        if iv_val is not None:
            iv_entry.setdefault(symbol, []).append(iv_val)
        pnl = _num(row.get("pnl"))
        close_date = str(row.get("close_date") or row.get("expiry") or "")[:10]
        if pnl is not None and close_date:
            curves.setdefault(symbol, {})
            curves[symbol][close_date] = curves[symbol].get(close_date, 0.0) + pnl
        entry_date = str(row.get("entry_date") or "")[:10]
        close_bound = str(row.get("close_date") or row.get("expiry") or "")[:10]
        bp_reserved = _num(row.get("bp_reserved")) or 0.0
        if entry_date and close_bound and bp_reserved > 0:
            try:
                start_dt = datetime.fromisoformat(entry_date)
                end_dt = datetime.fromisoformat(close_bound)
            except ValueError:
                start_dt = end_dt = None
            if start_dt and end_dt:
                current = start_dt
                while current <= end_dt:
                    key = current.date().isoformat()
                    slot = timeline.setdefault(key, {"q041_bp_dollars": 0.0})
                    slot["q041_bp_dollars"] += bp_reserved
                    current += timedelta(days=1)

    curve_rows = {}
    for symbol, daily in curves.items():
        cumulative = 0.0
        curve_rows[symbol] = []
        for date_key in sorted(daily):
            cumulative += daily[date_key]
            curve_rows[symbol].append({"date": date_key, "pnl": round(cumulative, 2)})
    bp_timeline = [
        {"date": date_key, "q041_bp_dollars": round(values["q041_bp_dollars"], 2)}
        for date_key, values in sorted(timeline.items())
    ]
    return {
        "status": "available",
        "tier2_goal": 20,
        "by_tier": by_tier,
        "by_symbol": by_symbol,
        "curves": curve_rows,
        "iv_entry": iv_entry,
        "bp_timeline": bp_timeline,
    }


def _build_q041_overview_payload() -> dict:
    from web.portfolio_surface import attribution_payload, sleeve_candidates_payload

    attr = attribution_payload()
    attr_data = attr if attr.get("status") == "available" else {}
    try:
        backtest_payload = _get_q041_backtest_payload("2022-05-06")
    except Exception as exc:
        backtest_payload = {"status": "error", "error": str(exc), "sleeves": []}
    paper = _q041_paper_progress()
    summaries = _q041_backtest_summaries(backtest_payload, attr_data)
    candidates = sleeve_candidates_payload()
    return {
        "status": "ok",
        "as_of": _now_et_iso(),
        "routing_note": "Tier 1 SPX CSP is eliminated by Q055; Tier 2 remains paper-trading active; Tier 3 remains observe-only.",
        "tier_status": {
            "tier1": {
                "state": "eliminated",
                "badge": "ELIMINATED",
                "symbol": "SPX",
                "reason": "Q055 naked put slot competition eliminated Tier 1 SPX CSP on 2026-05-10.",
            },
            "tier2": {
                "state": "paper_trading_active",
                "badge": "ACTIVE",
                "symbols": ["GOOGL", "AMZN"],
                "tail_caveat": "COVID / single-name mega-cap tail remains a mandatory visible caveat.",
            },
            "tier3": {
                "state": "observe_only",
                "badge": "OBSERVE-ONLY",
                "symbols": ["COST", "JPM"],
                "gate": "VIX >= 15 required before any paper event record.",
            },
        },
        "candidate_surface": candidates,
        "backtest_summary": summaries,
        "paper_progress": paper,
        "attribution": attr,
        "risk_visibility": {
            "joint_bp": attr_data.get("joint_bp_diagnostics"),
            "idle_day_capture": attr_data.get("idle_day_capture"),
            "bp_fill_contribution": attr_data.get("bp_fill_contribution"),
            "worst_day_overlap": attr_data.get("worst_day_overlap"),
            "shock": _q041_shock_metrics(),
        },
    }


def _get_spx_by_date() -> dict:
    global _SPX_BY_DATE
    if _SPX_BY_DATE is not None:
        return _SPX_BY_DATE
    import pickle as _pkl
    path = os.path.join(os.path.dirname(__file__), "..", "data", "market_cache", "yahoo__GSPC__max__1d.pkl")
    try:
        with open(os.path.normpath(path), "rb") as _f:
            _df = _pkl.load(_f)
        result: dict = {}
        for _idx, _row in _df.iterrows():
            _d = str(_idx)[:10]
            _v = _row.get("Close", _row.get("close", _row.iloc[0] if len(_row) > 0 else None))
            if _v is not None:
                result[_d] = round(float(_v), 2)
        _SPX_BY_DATE = result
    except Exception:
        _SPX_BY_DATE = {}
    return _SPX_BY_DATE


def _get_vix_by_date() -> dict:
    global _VIX_BY_DATE
    if _VIX_BY_DATE is not None:
        return _VIX_BY_DATE
    import pickle as _pkl
    path = os.path.join(os.path.dirname(__file__), "..", "data", "market_cache", "yahoo__VIX__max__1d.pkl")
    try:
        with open(os.path.normpath(path), "rb") as _f:
            _df = _pkl.load(_f)
        result: dict = {}
        for _idx, _row in _df.iterrows():
            _d = str(_idx)[:10]
            _v = _row.get("Close", _row.get("close", _row.iloc[0] if len(_row) > 0 else None))
            if _v is not None:
                result[_d] = round(float(_v), 2)
        _VIX_BY_DATE = result
    except Exception:
        _VIX_BY_DATE = {}
    return _VIX_BY_DATE


def _fetch_price_series(symbol: str, start_date: str) -> list[dict]:
    """Fetch daily closes for a symbol from yfinance, starting from start_date."""
    try:
        import yfinance as yf
        import pandas as pd
        yt = "^GSPC" if symbol == "SPX" else symbol
        df = yf.Ticker(yt).history(period="max", interval="1d")
        idx = df.index
        df.index = pd.to_datetime(idx.date if hasattr(idx, "date") else idx).normalize()
        closes = df["Close"].sort_index()
        closes = closes[closes.index >= pd.Timestamp(start_date)]
        return [{"date": str(d.date()), "close": round(float(v), 2)} for d, v in closes.items()]
    except Exception:
        return []


def _enrich_payload(payload: dict, start_date: str) -> None:
    """Add vix_at_entry per trade and price_series per sleeve."""
    vix = _get_vix_by_date()
    for sleeve in payload.get("sleeves", []):
        sym = sleeve.get("symbol", "")
        # VIX enrichment
        for trade in sleeve.get("trades", []):
            d = (trade.get("entry_date") or "")[:10]
            trade["vix_at_entry"] = vix.get(d)
        # Price series
        sleeve["price_series"] = _fetch_price_series(sym, start_date)

    # Cache metadata
    payload["_cached_at"] = datetime.now().isoformat(timespec="seconds")
    payload["_cache_key"] = _q041_disk_cache_key(start_date)


def _enrich_trades_with_vix(payload: dict) -> None:
    """Backward-compat shim used by warmup; full enrichment now via _enrich_payload."""
    vix = _get_vix_by_date()
    for sleeve in payload.get("sleeves", []):
        for trade in sleeve.get("trades", []):
            d = (trade.get("entry_date") or "")[:10]
            trade["vix_at_entry"] = vix.get(d)


def _build_q041_payload(start_date: str) -> dict:
    from research.strategies.q041_csp_backtest import run_q041_backtest
    payload = run_q041_backtest(start_date=start_date)
    _enrich_payload(payload, start_date)
    return payload


def _warmup_backtest_caches() -> None:
    """Pre-compute backtest caches in background thread on server start.
    Loads from disk if available; otherwise computes and saves."""
    try:
        start = "2022-05-06"
        cached = _load_q041_disk_cache(start)
        if cached:
            _Q041_BT_CACHE[start] = cached
        else:
            payload = _build_q041_payload(start)
            _Q041_BT_CACHE[start] = payload
            _save_q041_disk_cache(start, payload)
    except Exception:
        pass
    # ── ES backtest warmup ────────────────────────────────────────────────────
    try:
        es_key = "both:2022-05-01:1"
        es_disk = _load_es_disk_cache(es_key)
        if es_disk:
            _ES_BT_CACHE[es_key] = es_disk
        else:
            from research.strategies.ES_puts.backtest import run_phase1_hybrid
            rf = run_phase1_hybrid(mode="filtered", start_date="2022-05-01")
            rb = run_phase1_hybrid(mode="baseline", start_date="2022-05-01")

            def _ser(r, label):
                wins  = [t for t in r.trades if t.pnl > 0]
                stops = [t for t in r.trades if t.exit_reason == "stop_loss"]
                profs = [t for t in r.trades if t.exit_reason == "profit_target"]
                m = r.portfolio_metrics
                return {
                    "label": label, "phase": r.phase,
                    "trades": [{"entry_date": t.entry_date, "exit_date": t.exit_date, "entry_spx": round(t.entry_spx,1), "exit_spx": round(t.exit_spx,1), "entry_vix": round(t.entry_vix,1), "entry_premium": round(t.entry_premium,2), "exit_premium": round(t.exit_premium,2), "dte_at_entry": t.dte_at_entry, "dte_at_exit": t.dte_at_exit, "exit_reason": t.exit_reason, "contracts": round(t.contracts,4), "pnl": round(t.pnl,2)} for t in r.trades],
                    "equity_curve": [{"date": dr.date, "equity": round(dr.end_equity,2)} for i, dr in enumerate(r.daily_rows) if i % 5 == 0],
                    "summary": {"n_trades": len(r.trades), "win_rate_pct": round(len(wins)/len(r.trades)*100,1) if r.trades else 0, "stop_rate_pct": round(len(stops)/len(r.trades)*100,1) if r.trades else 0, "profit_target_pct": round(len(profs)/len(r.trades)*100,1) if r.trades else 0, "total_pnl": round(sum(t.pnl for t in r.trades),0), "ann_return_pct": m.get("ann_return"), "sharpe": m.get("daily_sharpe"), "max_drawdown_pct": round(abs(m.get("max_drawdown",0) or 0)*100,2), "actual_market_entries": m.get("actual_market_entries"), "bs_fallback_entries": m.get("bs_fallback_entries")},
                }

            es_payload = {"status": "ok", "filtered": _ser(rf, "Trend Filter ON"), "baseline": _ser(rb, "No Filter"), "start_date": "2022-05-01", "pricing": "hybrid_actual+bs"}
            _ES_BT_CACHE[es_key] = es_payload
            _save_es_disk_cache(es_key, es_payload)
    except Exception:
        pass

    # ── SPX backtest results warmup — pre-populate memory cache from disk ────────
    try:
        disk_cache = _load_results_disk()
        today = date.today().isoformat()
        for ck, entry in disk_cache.items():
            if isinstance(entry, dict) and entry.get("date") == today:
                payload = {
                    **entry.get("payload", {}),
                    "computed_at": entry.get("computed_at"),
                    "start_date":  entry.get("start_date", ""),
                    "params_hash": entry.get("params_hash", ""),
                }
                _backtest_cache[ck] = (time.time(), payload)
    except Exception:
        pass

    # ── SPX backtest stats warmup — /api/backtest/stats (Matrix win-rate cells) ──
    # Cold computation: 3y≈4s, 10y≈13s, all≈35s.  Runs here so the first page
    # request hits memory cache instead of timing out through Cloudflare (~30s limit).
    try:
        from backtest.engine import run_backtest as _rb
        from strategy.catalog import strategy_key as _cat_key
        today        = date.today().isoformat()
        phash        = _params_hash()
        disk_stats   = _load_stats_disk()
        disk_dirty   = False
        periods      = [
            ("3y",  (date.today() - timedelta(days=365 * 3)).isoformat()),
            ("10y", (date.today() - timedelta(days=365 * 10)).isoformat()),
            ("all", "2000-01-01"),
        ]
        for _period, _start in periods:
            _ck = f"stats_{_start}"
            # Skip if memory cache already warm
            if _backtest_cache.get(_ck):
                continue
            # Try disk first
            _entry = disk_stats.get(_ck, {})
            if (
                _entry.get("date") == today
                and _entry.get("params_hash") == phash
                and _entry.get("schema") == _STATS_SCHEMA_VERSION
                and _stats_payload_has_avg(_entry.get("payload", {}))
            ):
                _backtest_cache[_ck] = (time.time(), _entry["payload"])
                continue
            # Must compute
            _bt = _rb(start_date=_start, verbose=False, account_size=_BACKTEST_ACCOUNT_SIZE)
            _sig_by_date = {s["date"]: s for s in _bt.signals}
            _by_strat: dict = {}
            _by_cell:  dict = {}
            for _t in _bt.trades:
                _key = _cat_key(_t.strategy.value)
                _win = _t.exit_pnl > 0
                _r = _by_strat.setdefault(_key, {"n": 0, "wins": 0, "total_pnl": 0.0})
                _r["n"] += 1
                if _win: _r["wins"] += 1
                _r["total_pnl"] += _t.exit_pnl
                _sig = _sig_by_date.get(_t.entry_date, {})
                _ckey = f"{_sig.get('regime','')}|{_iv_level(float(_sig.get('ivp', 50)))}|{_sig.get('trend', '')}"
                _cr = _by_cell.setdefault(_ckey, {"n": 0, "wins": 0, "total_pnl": 0.0})
                _cr["n"] += 1
                if _win: _cr["wins"] += 1
                _cr["total_pnl"] += _t.exit_pnl
            _ss = {s: {"n": v["n"], "win_rate": round(v["wins"]/v["n"]*100), "avg_pnl": round(v["total_pnl"]/v["n"])} for s, v in _by_strat.items()}
            _cs = {k: {"n": v["n"], "win_rate": round(v["wins"]/v["n"]*100), "avg_pnl": round(v["total_pnl"]/v["n"])} for k, v in _by_cell.items()}
            _payload = {**_ss, "_cell": _cs}
            _backtest_cache[_ck] = (time.time(), _payload)
            disk_stats[_ck] = {"date": today, "params_hash": phash, "schema": _STATS_SCHEMA_VERSION, "payload": _payload}
            disk_dirty = True
        if disk_dirty:
            _save_stats_disk(disk_stats)
    except Exception:
        pass


threading.Thread(target=_warmup_backtest_caches, daemon=True).start()

@app.route("/api/es/backtest")
def api_es_backtest():
    import json, hashlib, time
    from pathlib import Path

    mode       = flask_req.args.get("mode", "filtered")   # filtered | baseline | both
    start_date = flask_req.args.get("start", "2000-01-01")
    use_hybrid = flask_req.args.get("hybrid", "1") == "1"
    cache_key  = f"{mode}:{start_date}:{use_hybrid}"

    # Memory cache
    if cache_key in _ES_BT_CACHE:
        return jsonify(_ES_BT_CACHE[cache_key])
    # Disk cache
    disk_cached = _load_es_disk_cache(cache_key)
    if disk_cached:
        _ES_BT_CACHE[cache_key] = disk_cached
        return jsonify(disk_cached)

    def _serialize_result(r, label):
        trades_out = [
            {
                "entry_date":    t.entry_date,
                "exit_date":     t.exit_date,
                "entry_spx":     round(t.entry_spx, 1),
                "exit_spx":      round(t.exit_spx, 1),
                "entry_vix":     round(t.entry_vix, 1),
                "entry_premium": round(t.entry_premium, 2),
                "exit_premium":  round(t.exit_premium, 2),
                "dte_at_entry":  t.dte_at_entry,
                "dte_at_exit":   t.dte_at_exit,
                "exit_reason":   t.exit_reason,
                "contracts":     round(t.contracts, 4),
                "pnl":           round(t.pnl, 2),
            }
            for t in r.trades
        ]
        # Sample equity curve (every 5 days to reduce payload)
        equity_rows = [
            {"date": dr.date, "equity": round(dr.end_equity, 2)}
            for i, dr in enumerate(r.daily_rows)
            if i % 5 == 0
        ]
        wins   = [t for t in r.trades if t.pnl > 0]
        stops  = [t for t in r.trades if t.exit_reason == "stop_loss"]
        profits = [t for t in r.trades if t.exit_reason == "profit_target"]
        total_pnl = sum(t.pnl for t in r.trades)
        m = r.portfolio_metrics
        return {
            "label":          label,
            "phase":          r.phase,
            "trades":         trades_out,
            "equity_curve":   equity_rows,
            "summary": {
                "n_trades":          len(r.trades),
                "win_rate_pct":      round(len(wins) / len(r.trades) * 100, 1) if r.trades else 0,
                "stop_rate_pct":     round(len(stops) / len(r.trades) * 100, 1) if r.trades else 0,
                "profit_target_pct": round(len(profits) / len(r.trades) * 100, 1) if r.trades else 0,
                "total_pnl":         round(total_pnl, 0),
                "ann_return_pct":    m.get("ann_return"),
                "sharpe":            m.get("daily_sharpe"),
                "max_drawdown_pct":  round(abs(m.get("max_drawdown", 0) or 0) * 100, 2),
                "actual_market_entries": m.get("actual_market_entries"),
                "bs_fallback_entries":   m.get("bs_fallback_entries"),
            },
        }

    try:
        from research.strategies.ES_puts.backtest import run_phase1, run_phase1_hybrid
        run_fn = run_phase1_hybrid if use_hybrid else run_phase1

        if mode == "both":
            rf = run_fn(mode="filtered",  start_date=start_date)
            rb = run_fn(mode="baseline",  start_date=start_date)
            payload = {
                "status":   "ok",
                "filtered": _serialize_result(rf, "Trend Filter ON"),
                "baseline": _serialize_result(rb, "No Filter"),
                "start_date": start_date,
                "pricing":    "hybrid_actual+bs" if use_hybrid else "black_scholes",
            }
        else:
            r = run_fn(mode=mode, start_date=start_date)
            payload = {
                "status":   "ok",
                mode:       _serialize_result(r, "Trend Filter ON" if mode == "filtered" else "No Filter"),
                "start_date": start_date,
                "pricing":    "hybrid_actual+bs" if use_hybrid else "black_scholes",
            }

        _ES_BT_CACHE[cache_key] = payload
        _save_es_disk_cache(cache_key, payload)
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/es-backtest/hvlad")
def api_es_backtest_hvlad():
    start_date = flask_req.args.get("start", "2000-01-01")
    end_date = flask_req.args.get("end")
    cache_key = f"hvlad:{start_date}:{end_date or ''}"

    if cache_key in _ES_BT_CACHE:
        cached = _ES_BT_CACHE[cache_key]
        if _is_hvlad_payload(cached):
            return jsonify(cached)
        _purge_hvlad_cache_entries()

    disk_cached = _load_es_disk_cache(cache_key)
    if disk_cached and _is_hvlad_payload(disk_cached):
        _ES_BT_CACHE[cache_key] = disk_cached
        return jsonify(disk_cached)
    if disk_cached:
        _purge_hvlad_cache_entries()

    try:
        from research.strategies.ES_puts.backtest import V2F_VIX_MIN_ENTRY, run_phase2_hvlad

        baseline_result = run_phase2_hvlad(
            start_date=start_date,
            end_date=end_date,
            vix_min_entry=0.0,
        )
        hv_result = run_phase2_hvlad(
            start_date=start_date,
            end_date=end_date,
            vix_min_entry=V2F_VIX_MIN_ENTRY,
        )
        baseline_metrics = _es_trade_summary_metrics(baseline_result)
        hv_metrics = _es_trade_summary_metrics(hv_result)
        baseline_covid = _result_window_pnl_pct(baseline_result, "2020-02-15", "2020-05-31")
        hv_covid = _result_window_pnl_pct(hv_result, "2020-02-15", "2020-05-31")
        baseline_metrics["covid_2020_pct_nlv"] = baseline_covid
        hv_metrics["covid_2020_pct_nlv"] = hv_covid

        payload = {
            "phase": hv_result.phase,
            "mode": hv_result.mode,
            "vix_min_entry": V2F_VIX_MIN_ENTRY,
            "paper_mode": True,
            "hvlad_metrics": hv_metrics,
            "v2f_baseline": baseline_metrics,
            "hv_delta": {
                "ann_roe_pp": _pct_point_delta(
                    hv_metrics.get("ann_roe_geometric"),
                    baseline_metrics.get("ann_roe_geometric"),
                ),
                "sharpe_delta": _numeric_delta(
                    hv_metrics.get("sharpe"),
                    baseline_metrics.get("sharpe"),
                ),
                "max_dd_improvement_pp": _pct_point_delta(
                    hv_metrics.get("max_dd"),
                    baseline_metrics.get("max_dd"),
                ),
                "worst_trade_improvement_pp": _pct_point_delta(
                    hv_metrics.get("worst_trade_pct_nlv"),
                    baseline_metrics.get("worst_trade_pct_nlv"),
                ),
                "bootstrap_improvement_pp": _pct_point_delta(
                    hv_metrics.get("bootstrap_sig_rate"),
                    baseline_metrics.get("bootstrap_sig_rate"),
                ),
                "covid_2020_pp": _pct_point_delta(hv_covid, baseline_covid),
            },
            "paper_state": _hvlad_paper_state(),
            "caveats": _default_hvlad_caveats(),
            "start_date": start_date,
            "end_date": end_date,
            "backtest_signal_dates": sorted({t.entry_date for t in hv_result.trades}),
            "backtest_exit_data": [
                {"entry_date": t.entry_date, "exit_date": t.exit_date, "pnl": t.pnl}
                for t in sorted(hv_result.trades, key=lambda t: t.exit_date)
            ],
            "daily_curve": [
                {"date": r.date, "equity": round(r.cumulative_equity, 2), "drawdown": round(r.drawdown, 6)}
                for r in hv_result.daily_rows
            ],
        }
        _purge_hvlad_cache_entries()
        _ES_BT_CACHE[cache_key] = payload
        _save_es_disk_cache(cache_key, payload)
        return jsonify(payload)
    except Exception as exc:
        payload = {
            "phase": "es_hv_ladder",
            "mode": "baseline",
            "vix_min_entry": 22.0,
            "paper_mode": True,
            "hvlad_metrics": None,
            "v2f_baseline": None,
            "hv_delta": None,
            "paper_state": _hvlad_paper_state(),
            "caveats": _default_hvlad_caveats(),
            "error": str(exc),
            "start_date": start_date,
            "end_date": end_date,
        }
        return jsonify(payload)


@app.route("/api/hvladder/live")
def api_hvladder_live():
    rows = _load_hvlad_paper_trades()
    today = datetime.now(_ET).date()
    active_slots = _hvlad_active_slots(rows, today)
    cadence_ok, cadence_elapsed = _hvlad_cadence_status(rows, today, active_slots)
    vix = _hvlad_vix_context()
    trend = _hvlad_trend_status()
    vix_current = vix.get("vix_current")
    vix_ok = isinstance(vix_current, (int, float)) and vix_current >= 22.0 and not vix.get("stale")
    slots_ok = active_slots < 5
    gate_status = {
        "warmed": bool(trend.get("warmed")),
        "trend_ok": bool(trend.get("trend_ok")),
        "cadence_ok": bool(cadence_ok),
        "slots_ok": bool(slots_ok),
        "vix_ok": bool(vix_ok),
    }
    blockers = [key for key, ok in gate_status.items() if not ok]
    return jsonify({
        "date": today.isoformat(),
        "threshold": 22.0,
        "vix_current": vix_current,
        "vix_5td_avg": vix.get("vix_5td_avg"),
        "latest_close_date": vix.get("latest_close_date"),
        "quote_time": vix.get("quote_time"),
        "vix_source": vix.get("source"),
        "vix_stale": bool(vix.get("stale")),
        "vix_gate_distance": (vix_current - 22.0) if isinstance(vix_current, (int, float)) else None,
        "active_slots": active_slots,
        "max_slots": 5,
        "cadence_elapsed_trading_days": cadence_elapsed,
        "trend": trend,
        "gate_status": gate_status,
        "signal_live": all(gate_status.values()),
        "blockers": blockers,
        "last_signal": rows[0] if rows else None,
        "status": "ok" if vix.get("ok") and trend.get("ok") else "degraded",
        "errors": {
            "vix": vix.get("error"),
            "trend": trend.get("error"),
        },
    })


def _hvlad_open_trades(rows: list[dict]) -> list[dict]:
    """Return open trades (open event, no matching close), newest first.

    Each entry includes the merged state {trade_id, signal_date, expiry,
    short_strike, contracts, entry_premium, entry_spx, entry_vix, opened_at, note}.
    """
    closed_tids: set[str] = set()
    open_records: dict[str, dict] = {}
    # Iterate rows oldest first to capture open then potential close
    sorted_rows = sorted(rows, key=lambda r: str(r.get("timestamp") or r.get("signal_date") or ""))
    for row in sorted_rows:
        tid = row.get("trade_id")
        if not tid:
            continue
        event = row.get("event") or "open"
        if event == "open":
            open_records[tid] = row
        elif event == "close":
            closed_tids.add(tid)
    out = [r for tid, r in open_records.items() if tid not in closed_tids]
    out.sort(key=lambda r: str(r.get("signal_date") or r.get("timestamp") or ""), reverse=True)
    return out


def _hvlad_ledger_path() -> Path:
    return Path(__file__).parent.parent / "data" / "q071_hv_paper_trades.jsonl"


def _hvlad_next_trade_id() -> str:
    today_iso = datetime.now(_ET).date().isoformat()
    rows = _load_hvlad_paper_trades()
    same_day_opens = [
        r for r in rows
        if str(r.get("trade_id", "")).startswith(today_iso + "_hvl_")
        and (r.get("event") or "open") == "open"
    ]
    return f"{today_iso}_hvl_{len(same_day_opens) + 1:03d}"


def _hvlad_append(rec: dict) -> None:
    path = _hvlad_ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


@app.route("/api/hvladder/position/open", methods=["POST"])
def api_hvladder_position_open():
    """Record a manual Stress Put Ladder slot open. PM decides paper vs real."""
    data = flask_req.get_json(silent=True) or {}
    now = datetime.now(_ET)
    today_iso = now.date().isoformat()
    required = ["expiry", "short_strike", "contracts", "entry_premium"]
    missing = [k for k in required if data.get(k) in (None, "")]
    if missing:
        return jsonify({"status": "error", "error": f"missing fields: {', '.join(missing)}"}), 400

    rec = {
        "trade_id":      _hvlad_next_trade_id(),
        "event":         "open",
        "timestamp":     now.isoformat(timespec="seconds"),
        "signal_date":   data.get("signal_date") or today_iso,
        "source":        "manual",
        "underlying":    "/ES",
        "strategy_key":  "stress_put_ladder",
        "expiry":        data.get("expiry"),
        "dte_at_entry":  data.get("dte_at_entry"),
        "short_strike":  data.get("short_strike"),
        "contracts":     data.get("contracts", 1),
        "entry_premium": data.get("entry_premium"),
        "model_premium": data.get("model_premium"),
        "entry_spx":     data.get("entry_spx"),
        "entry_vix":     data.get("entry_vix"),
        "paper_trade":   bool(data.get("paper_trade", False)),
        "note":          data.get("note", "") or "",
    }
    _hvlad_append(rec)
    return jsonify({"status": "ok", "trade_id": rec["trade_id"], "record": rec})


@app.route("/api/hvladder/position/close", methods=["POST"])
def api_hvladder_position_close():
    """Record a close event referencing an existing open trade_id."""
    data = flask_req.get_json(silent=True) or {}
    now = datetime.now(_ET)
    tid = data.get("trade_id")
    if not tid:
        return jsonify({"status": "error", "error": "trade_id required"}), 400
    if data.get("close_premium") in (None, ""):
        return jsonify({"status": "error", "error": "close_premium required"}), 400

    # Verify trade exists and is open
    open_trades = _hvlad_open_trades(_load_hvlad_paper_trades())
    if not any(t.get("trade_id") == tid for t in open_trades):
        return jsonify({"status": "error", "error": f"trade_id {tid} not in open trades"}), 400

    rec = {
        "trade_id":      tid,
        "event":         "close",
        "timestamp":     now.isoformat(timespec="seconds"),
        "close_date":    data.get("close_date") or now.date().isoformat(),
        "source":        "manual",
        "close_premium": data.get("close_premium"),
        "close_spx":     data.get("close_spx"),
        "close_vix":     data.get("close_vix"),
        "exit_reason":   data.get("exit_reason", "discretionary"),
        "note":          data.get("note", "") or "",
    }
    _hvlad_append(rec)
    return jsonify({"status": "ok", "record": rec})


@app.route("/api/hvladder/position/note", methods=["POST"])
def api_hvladder_position_note():
    """Append a note entry, optionally linked to a trade_id."""
    data = flask_req.get_json(silent=True) or {}
    now = datetime.now(_ET)
    note = (data.get("note") or "").strip()
    if not note:
        return jsonify({"status": "error", "error": "note text required"}), 400
    rec = {
        "event":     "note",
        "timestamp": now.isoformat(timespec="seconds"),
        "trade_id":  data.get("trade_id"),
        "source":    "manual",
        "note":      note,
    }
    _hvlad_append(rec)
    return jsonify({"status": "ok", "record": rec})


@app.route("/api/hvladder/draft")
def api_hvladder_draft():
    """Open draft for Stress Put Ladder: live /ES chain scan ranked by spread + OI + delta gap.

    Falls back to BSM-only fit if Schwab futures chain is unavailable. Response
    mirrors /api/es/position/open-draft shape so the frontend can render the
    same scan table for row selection.
    """
    try:
        from backtest.pricer import find_strike_for_delta, put_price
        from schwab.scanner import build_strike_scan
    except Exception as exc:
        return jsonify({"status": "error", "error": f"pricer/scanner unavailable: {exc}"})

    vix_ctx = _hvlad_vix_context()
    trend = _hvlad_trend_status()
    vix = vix_ctx.get("vix_current")
    spx = trend.get("spx")
    if not isinstance(vix, (int, float)) or vix <= 0:
        return jsonify({"status": "unavailable", "reason": "vix not available"})
    if not isinstance(spx, (int, float)) or spx <= 0:
        return jsonify({"status": "unavailable", "reason": "spx not available"})

    sigma = max(float(vix) / 100.0, 0.01)
    dte = 49
    target_delta = 0.20

    # BSM fit as center for the chain scan (rounded to /ES 25-pt monthly grid)
    try:
        k_raw = find_strike_for_delta(float(spx), dte, sigma, target_delta, False)
    except Exception as exc:
        return jsonify({"status": "error", "error": f"strike fit failed: {exc}"})
    k_center = int(round(k_raw / 25.0) * 25)

    # Live chain scan (Schwab futures)
    scan_rows: list[dict] = []
    scan_fallback = True
    scan_error: str | None = None
    try:
        scan = build_strike_scan(
            symbol="/ES",
            option_type="PUT",
            target_delta=-target_delta,  # scanner convention: negative for puts
            target_dte=dte,
            center_strike=float(k_center),
            spot=float(spx),
            sigma=float(sigma),
        )
        scan_rows = scan.get("rows") or []
        scan_fallback = bool(scan.get("scan_fallback"))
    except Exception as exc:
        scan_error = str(exc)

    today = date.today()
    bsm_premium = round(float(put_price(float(spx), float(k_center), dte, sigma)), 2)
    base_payload = {
        "status":          "ok",
        "spx":             round(float(spx), 2),
        "vix":             round(float(vix), 2),
        "sigma":           round(float(sigma), 4),
        "dte":             dte,
        "target_delta":    target_delta,
        "strike_raw":      round(float(k_raw), 2),
        "signal_date":     today.isoformat(),
        "default_expiry": (today + timedelta(days=dte)).isoformat(),
    }

    recommended = next((r for r in scan_rows if r.get("recommended")), None)
    if scan_fallback or recommended is None:
        market_open = _is_market_hours()
        if scan_error:
            msg = f"Live /ES chain error — using BSM model fit: {scan_error}"
        elif not market_open:
            msg = "Markets closed (no two-sided /ES quotes) — using BSM model fit"
        else:
            msg = "No /ES quotes in target DTE window — using BSM model fit"
        return jsonify({
            **base_payload,
            "short_strike":   k_center,
            "expiry":         base_payload["default_expiry"],
            "model_premium":  bsm_premium,
            "model_bsm":      bsm_premium,
            "strike_scan":    {"rows": [], "scan_fallback": True, "error": scan_error},
            "scan_message":   msg,
            "market_open":    market_open,
        })

    # Enrich rows with target_delta + live_delta + delta_gap
    enriched = []
    for r in scan_rows:
        lv = abs(float(r["delta"])) if r.get("delta") not in (None, "") else None
        enriched.append({
            **r,
            "target_delta": target_delta,
            "live_delta":   round(lv, 3) if lv is not None else None,
            "delta_gap":    round(abs(lv - target_delta), 3) if lv is not None else None,
        })

    final_strike = int(round(float(recommended["strike"])))
    final_mid = float(recommended["mid"]) if recommended.get("mid") not in (None, "") else None
    final_premium = round(final_mid, 2) if final_mid is not None else bsm_premium
    expiry = str(recommended.get("expiry") or base_payload["default_expiry"])

    return jsonify({
        **base_payload,
        "short_strike":   final_strike,
        "expiry":         expiry,
        "model_premium":  final_premium,
        "model_bsm":      bsm_premium,
        "strike_scan":    {
            "rows":               enriched,
            "scan_fallback":      False,
            "center_strike":      k_center,
            "recommended_strike": final_strike,
        },
    })


@app.route("/api/hvladder/open-trades")
def api_hvladder_open_trades():
    """List currently-open Stress Put Ladder slots (for close modal picker)."""
    rows = _load_hvlad_paper_trades()
    return jsonify({"trades": _hvlad_open_trades(rows)})


@app.route("/api/hvladder/paper_trades")
def api_hvladder_paper_trades():
    try:
        limit = int(flask_req.args.get("limit", 20))
    except ValueError:
        limit = 20
    rows = _load_hvlad_paper_trades()
    return jsonify({
        "path": "data/q071_hv_paper_trades.jsonl",
        "count": len(rows),
        "trades": rows[: max(0, min(limit, 200))],
    })


@app.route("/api/hvladder/stats")
def api_hvladder_stats():
    rows = _load_hvlad_paper_trades()
    vix_counts = _hvlad_vix_days_counts()
    vix_values = [row.get("vix_at_signal") for row in rows if isinstance(row.get("vix_at_signal"), (int, float))]
    return jsonify({
        "paper_signal_count": len(rows),
        "max_signal_vix": max(vix_values) if vix_values else None,
        "last_signal": rows[0] if rows else None,
        "vix_days": vix_counts,
        "crisis_windows": _load_hvlad_crisis_windows(),
    })


@app.route("/api/hvladder/chart")
def api_hvladder_chart():
    """Full SPX+VIX history with backtest overlay data. Frontend handles time-window slicing."""
    vix = _get_vix_by_date()
    spx = _get_spx_by_date()
    dates = sorted(d for d in vix if d in spx)
    date_set = set(dates)

    # SPX 10-day moving average
    spx_vals = [spx[d] for d in dates]
    spx_ma10: list[float | None] = []
    for i in range(len(spx_vals)):
        if i < 9:
            spx_ma10.append(None)
        else:
            spx_ma10.append(round(sum(spx_vals[i - 9: i + 1]) / 10, 2))

    # Load backtest cache — scan all hvlad keys, pick most recent date.
    bt_cache = None
    try:
        with open(_ES_DISK_CACHE_PATH, "r") as _f:
            _store = json.load(_f)
        mtime = _es_script_mtime()
        _hvlad_keys = sorted(
            (k for k in _store if k.startswith("hvlad:2000-01-01:") and k.endswith(f"__{mtime}")),
            reverse=True,
        )
        if _hvlad_keys:
            bt_cache = _store[_hvlad_keys[0]]
    except Exception:
        pass

    # Prefer paper trades if they have signal_date; fall back to backtest.
    paper = _load_hvlad_paper_trades()
    paper_signals = {str(r.get("signal_date") or "")[:10] for r in paper} - {""}
    if paper_signals:
        entry_dates = sorted(paper_signals & date_set)
        exit_data: list[dict] = []
    else:
        bt_signals = set(bt_cache.get("backtest_signal_dates", [])) if bt_cache else set()
        entry_dates = sorted(bt_signals & date_set)
        exit_data = bt_cache.get("backtest_exit_data", []) if bt_cache else []

    # Daily equity curve + drawdown from backtest.
    daily_curve = bt_cache.get("daily_curve", []) if bt_cache else []

    return jsonify({
        "dates":         dates,
        "spx":           spx_vals,
        "vix":           [vix[d] for d in dates],
        "spx_ma10":      spx_ma10,
        "entry_dates":   entry_dates,
        "exit_data":     exit_data,
        "daily_curve":   daily_curve,
        "vix_threshold": 22.0,
    })


@app.route("/api/es-backtest/v2f")
def api_es_backtest_v2f():
    start_date = flask_req.args.get("start", "2000-01-01")
    end_date = flask_req.args.get("end")
    mode = flask_req.args.get("mode", "baseline")
    cache_key = f"v2f:{mode}:{start_date}:{end_date or ''}"

    if cache_key in _ES_BT_CACHE:
        cached = _ES_BT_CACHE[cache_key]
        if _is_v2f_m1_payload(cached):
            return jsonify(cached)
        _purge_v2f_cache_entries()

    disk_cached = _load_es_disk_cache(cache_key)
    if disk_cached and _is_v2f_m1_payload(disk_cached):
        _ES_BT_CACHE[cache_key] = disk_cached
        return jsonify(disk_cached)
    if disk_cached:
        _purge_v2f_cache_entries()

    try:
        from research.strategies.ES_puts.backtest import run_phase2_v2f

        baseline_result = run_phase2_v2f(mode=mode, start_date=start_date, end_date=end_date, enable_m1=False)
        m1_result = run_phase2_v2f(mode=mode, start_date=start_date, end_date=end_date, enable_m1=True)
        baseline_metrics = _es_trade_summary_metrics(baseline_result)
        m1_metrics = _es_trade_summary_metrics(m1_result)
        baseline_ann = baseline_metrics.get("ann_roe_geometric")
        m1_ann = m1_metrics.get("ann_roe_geometric")
        baseline_sharpe = baseline_metrics.get("sharpe")
        m1_sharpe = m1_metrics.get("sharpe")
        baseline_cluster = baseline_metrics.get("stress_cluster_pct")
        m1_cluster = m1_metrics.get("stress_cluster_pct")
        payload = {
            "phase": m1_result.phase,
            "mode": m1_result.mode,
            "v2f_baseline": baseline_metrics,
            "v2f_m1": m1_metrics,
            "m1_delta": {
                "ann_roe_pp": ((m1_ann - baseline_ann) * 100.0) if isinstance(m1_ann, (int, float)) and isinstance(baseline_ann, (int, float)) else None,
                "sharpe_delta": (m1_sharpe - baseline_sharpe) if isinstance(m1_sharpe, (int, float)) and isinstance(baseline_sharpe, (int, float)) else None,
                "stress_improvement_pp": ((m1_cluster - baseline_cluster) * 100.0) if isinstance(m1_cluster, (int, float)) and isinstance(baseline_cluster, (int, float)) else None,
            },
            "caveats": _default_v2f_caveats(),
            "start_date": start_date,
            "end_date": end_date,
        }
        _purge_v2f_cache_entries()
        _ES_BT_CACHE[cache_key] = payload
        _save_es_disk_cache(cache_key, payload)
        return jsonify(payload)
    except Exception as exc:
        payload = {
            "phase": "phase2_v2f_m1",
            "mode": mode,
            "v2f_baseline": None,
            "v2f_m1": None,
            "m1_delta": None,
            "caveats": _default_v2f_caveats(),
            "error": str(exc),
            "start_date": start_date,
            "end_date": end_date,
        }
        return jsonify(payload)


@app.route("/api/es/backtest/refresh", methods=["POST"])
def api_es_backtest_refresh():
    """Force recompute ES backtest, bypassing memory and disk cache."""
    mode       = flask_req.args.get("mode", "both")
    start_date = flask_req.args.get("start", "2022-05-01")
    use_hybrid = flask_req.args.get("hybrid", "1") == "1"
    cache_key  = f"{mode}:{start_date}:{int(use_hybrid)}"
    _ES_BT_CACHE.pop(cache_key, None)
    try:
        from research.strategies.ES_puts.backtest import run_phase1, run_phase1_hybrid
        run_fn = run_phase1_hybrid if use_hybrid else run_phase1
        rf = run_fn(mode="filtered", start_date=start_date)
        rb = run_fn(mode="baseline", start_date=start_date)

        def _s(r, lbl):
            wins  = [t for t in r.trades if t.pnl > 0]
            stops = [t for t in r.trades if t.exit_reason == "stop_loss"]
            profs = [t for t in r.trades if t.exit_reason == "profit_target"]
            m = r.portfolio_metrics
            return {"label": lbl, "phase": r.phase,
                "trades": [{"entry_date": t.entry_date, "exit_date": t.exit_date, "entry_spx": round(t.entry_spx,1), "exit_spx": round(t.exit_spx,1), "entry_vix": round(t.entry_vix,1), "entry_premium": round(t.entry_premium,2), "exit_premium": round(t.exit_premium,2), "dte_at_entry": t.dte_at_entry, "dte_at_exit": t.dte_at_exit, "exit_reason": t.exit_reason, "contracts": round(t.contracts,4), "pnl": round(t.pnl,2)} for t in r.trades],
                "equity_curve": [{"date": dr.date, "equity": round(dr.end_equity,2)} for i, dr in enumerate(r.daily_rows) if i % 5 == 0],
                "summary": {"n_trades": len(r.trades), "win_rate_pct": round(len(wins)/len(r.trades)*100,1) if r.trades else 0, "stop_rate_pct": round(len(stops)/len(r.trades)*100,1) if r.trades else 0, "total_pnl": round(sum(t.pnl for t in r.trades),0), "ann_return_pct": m.get("ann_return"), "sharpe": m.get("daily_sharpe"), "max_drawdown_pct": round(abs(m.get("max_drawdown",0) or 0)*100,2)}}

        payload = {"status": "ok", "filtered": _s(rf, "Trend Filter ON"), "baseline": _s(rb, "No Filter"), "start_date": start_date, "pricing": "hybrid_actual+bs" if use_hybrid else "black_scholes"}
        _ES_BT_CACHE[cache_key] = payload
        _save_es_disk_cache(cache_key, payload)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/q041/backtest")
def api_q041_backtest():
    start_date = flask_req.args.get("start", "2022-05-06")
    if start_date in _Q041_BT_CACHE:
        return jsonify(_Q041_BT_CACHE[start_date])
    # Try disk cache first
    cached = _load_q041_disk_cache(start_date)
    if cached:
        _Q041_BT_CACHE[start_date] = cached
        return jsonify(cached)
    try:
        payload = _build_q041_payload(start_date)
        _Q041_BT_CACHE[start_date] = payload
        _save_q041_disk_cache(start_date, payload)
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/q041/backtest/refresh", methods=["POST"])
def api_q041_backtest_refresh():
    """Force recompute, bypass both memory and disk cache."""
    start_date = flask_req.args.get("start", "2022-05-06")
    try:
        payload = _build_q041_payload(start_date)
        _Q041_BT_CACHE[start_date] = payload
        _save_q041_disk_cache(start_date, payload)
        return jsonify({"ok": True, "cached_at": payload.get("_cached_at")})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/position")
def api_position():
    from strategy.state import read_state, read_all_positions
    from strategy.catalog import strategy_descriptor
    from schwab.client import live_position_snapshot
    state = read_state()
    if state is None:
        return jsonify({"open": False, "schwab_live": live_position_snapshot(None)})
    if state.get("strategy_key"):
        try:
            state["strategy_meta"] = asdict(strategy_descriptor(state["strategy_key"]))
        except Exception:
            pass
    all_pos = read_all_positions()
    positions = (all_pos or {}).get("positions", [])
    live = live_position_snapshot(state)
    # Combined trade-log P&L across all accounts using the same spread mark
    spread_mark = live.get("mark") if live.get("visible") else None
    if spread_mark is not None and positions:
        try:
            combined_pnl = sum(
                (float(p.get("actual_premium") or p.get("model_premium") or 0) - spread_mark)
                * float(p.get("contracts") or 0) * 100
                for p in positions
            )
            live["combined_trade_log_pnl"] = round(combined_pnl, 2)
        except Exception:
            pass
    # Per-tranche live quotes keyed by trade_id; also maintain etrade_live for compat
    position_lives: dict = {}
    etrade_live: dict = {"visible": False}
    _et_cache: dict = {}
    _sw_cache: dict = {}
    primary_sw = (str(state.get("short_strike")), str(state.get("long_strike")))
    expiry = state.get("expiry", "")
    underlying = state.get("underlying", "SPX")

    for p in positions:
        tid = p.get("trade_id")
        if not tid or not expiry:
            continue
        acct = (p.get("account") or "schwab").lower()
        ss, ls = str(p.get("short_strike") or ""), str(p.get("long_strike") or "")
        if not (ss and ls):
            continue
        ck = (ss, ls)

        if acct == "etrade":
            if ck not in _et_cache:
                try:
                    from etrade.client import get_option_spread_quote
                    _et_cache[ck] = get_option_spread_quote(
                        underlier=underlying, expiry=expiry,
                        short_strike=float(ss), long_strike=float(ls),
                    )
                except Exception:
                    _et_cache[ck] = {"visible": False}
            position_lives[tid] = _et_cache[ck]
            if not etrade_live.get("visible"):   # first E-Trade entry wins for compat
                etrade_live = _et_cache[ck]

        elif acct == "schwab":
            if ck not in _sw_cache:
                if ck == primary_sw:
                    _sw_cache[ck] = live   # reuse already-computed schwab_live (has Greeks)
                else:
                    try:
                        from schwab.client import spread_quote_for_strikes
                        _sw_cache[ck] = spread_quote_for_strikes(
                            underlying, expiry, float(ss), float(ls)
                        )
                    except Exception:
                        _sw_cache[ck] = {"visible": False}
            position_lives[tid] = _sw_cache[ck]

    return jsonify({
        "open": True,
        **state,
        "positions": positions,
        "schwab_live": live,
        "etrade_live": etrade_live,
        "position_lives": position_lives,
    })


def _now_et_iso() -> str:
    return datetime.now(_ET).isoformat(timespec="seconds")


def _num(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bp_target_fraction_for_strategy(strategy_key: str, regime_name: str | None = None) -> float:
    from strategy.selector import DEFAULT_PARAMS

    if regime_name == "HIGH_VOL" or strategy_key in {"bull_put_spread_hv", "bear_call_spread_hv", "iron_condor_hv"}:
        return float(DEFAULT_PARAMS.bp_target_high_vol)
    if regime_name == "LOW_VOL":
        return float(DEFAULT_PARAMS.bp_target_low_vol)
    return float(DEFAULT_PARAMS.bp_target_normal)


def _estimate_bp_per_contract(strategy_key: str, short_strike, long_strike, premium) -> float | None:
    short_k = _num(short_strike)
    long_k = _num(long_strike)
    premium_val = abs(_num(premium) or 0.0)
    width = abs(short_k - long_k) if short_k is not None and long_k is not None else None

    if strategy_key == "bull_call_diagonal":
        return round(max(premium_val * 100.0, 0.0), 2)

    if strategy_key in {
        "bull_put_spread",
        "bull_put_spread_hv",
        "bear_call_spread_hv",
        "iron_condor",
        "iron_condor_hv",
    }:
        if width is None:
            return None
        return round(max((width - premium_val) * 100.0, 0.0), 2)

    if width is not None:
        return round(max((width - premium_val) * 100.0, 0.0), 2)
    return round(max(premium_val * 100.0, 0.0), 2)


def _bp_basis_snapshot() -> dict:
    from schwab.client import get_account_balances
    from strategy.selector import DEFAULT_PARAMS

    basis = {
        "basis_dollars": float(DEFAULT_PARAMS.initial_equity),
        "basis_label": "Model Equity",
        "basis_is_live": False,
        "pct_basis_dollars": None,
        "pct_basis_label": None,
    }
    try:
        balances = get_account_balances()
    except Exception:
        return basis

    option_bp = _num(balances.get("option_buying_power"))
    buying_power = _num(balances.get("buying_power"))
    if option_bp and option_bp > 0:
        basis.update({
            "basis_dollars": option_bp,
            "basis_label": "Schwab Option BP",
            "basis_is_live": True,
            "pct_basis_dollars": option_bp,
            "pct_basis_label": "Schwab Option BP",
        })
        return basis
    if buying_power and buying_power > 0:
        basis.update({
            "basis_dollars": buying_power,
            "basis_label": "Schwab Buying Power",
            "basis_is_live": True,
            "pct_basis_dollars": buying_power,
            "pct_basis_label": "Schwab Buying Power",
        })
    return basis


def _bp_preview_payload(strategy_key: str, regime_name: str | None, short_strike, long_strike, premium, contracts: int | float | None) -> dict:
    target_fraction = _bp_target_fraction_for_strategy(strategy_key, regime_name)
    basis = _bp_basis_snapshot()
    bp_per_contract = _estimate_bp_per_contract(strategy_key, short_strike, long_strike, premium)
    target_dollars = round(float(basis["basis_dollars"]) * target_fraction, 2)

    if bp_per_contract and bp_per_contract > 0:
        recommended_contracts = max(1, int(target_dollars // bp_per_contract))
    else:
        recommended_contracts = 1

    contracts_value = max(1, int(_num(contracts) or recommended_contracts))
    usage_dollars = round((bp_per_contract or 0.0) * contracts_value, 2) if bp_per_contract is not None else None
    pct_basis = basis.get("pct_basis_dollars")
    usage_pct = round((usage_dollars / pct_basis) * 100.0, 2) if usage_dollars is not None and pct_basis else None

    return {
        "bp_per_contract": bp_per_contract,
        "bp_usage_dollars": usage_dollars,
        "bp_usage_pct": usage_pct,
        "bp_target_pct": round(target_fraction * 100.0, 2),
        "bp_target_dollars": target_dollars,
        "recommended_contracts": recommended_contracts,
        "basis_dollars": round(float(basis["basis_dollars"]), 2),
        "basis_label": basis["basis_label"],
        "basis_is_live": basis["basis_is_live"],
        "pct_basis_dollars": round(float(pct_basis), 2) if pct_basis else None,
        "pct_basis_label": basis.get("pct_basis_label"),
    }


def _is_es_option_position(position: dict) -> bool:
    text = f"{position.get('symbol', '')} {position.get('description', '')}".upper()
    quantity = _num(position.get("quantity")) or 0.0
    return abs(quantity) > 0 and "/ES" in text and "PUT" in text


def _live_es_bp_check() -> dict:
    from schwab.client import get_account_balances, get_account_positions

    balances = get_account_balances()
    positions = get_account_positions()

    if (
        not balances.get("configured")
        or not balances.get("authenticated")
        or balances.get("stale")
        or not positions.get("configured")
        or not positions.get("authenticated")
        or positions.get("stale")
    ):
        return {"ok": False, "reason": "Live Schwab balances/positions unavailable"}

    nlv = _num(balances.get("net_liquidation"))
    used_margin_candidates = [
        _num(balances.get("initial_margin")),
        _num(balances.get("maintenance_margin")),
    ]
    used_margin = max((value for value in used_margin_candidates if value is not None), default=None)
    if nlv is None or nlv <= 0 or used_margin is None:
        return {"ok": False, "reason": "Missing NLV or live margin usage"}

    if any(_is_es_option_position(position) for position in positions.get("positions", [])):
        return {"ok": False, "reason": "Existing /ES short-put slot detected"}

    limit_dollars = round(nlv * _ES_BP_LIMIT_FRACTION, 2)
    projected_bp = round(float(used_margin) + _ES_BP_PER_CONTRACT, 2)
    bp_ok = projected_bp <= limit_dollars
    return {
        "ok": bp_ok,
        "reason": None if bp_ok else "Projected /ES BP would exceed NLV 20% cap",
        "nlv": round(float(nlv), 2),
        "current_bp": round(float(used_margin), 2),
        "projected_bp": projected_bp,
        "bp_limit": limit_dollars,
        "bp_check_passed": bp_ok,
        "es_bp_per_contract": _ES_BP_PER_CONTRACT,
    }


@app.route("/api/position/open", methods=["POST"])
def api_position_open():
    from logs.trade_log_io import append_event, next_trade_id
    from strategy.catalog import strategy_descriptor
    from strategy.state import write_state

    body = flask_req.get_json(force=True) or {}
    strategy_key = str(body.get("strategy_key", "")).strip()
    paper_trade = bool(body.get("paper_trade", False))
    if not strategy_key:
        return jsonify({"error": "strategy_key is required"}), 400
    try:
        desc = strategy_descriptor(strategy_key)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    timestamp = _now_et_iso()
    trade_id = next_trade_id(strategy_key)
    actual_premium = body.get("actual_premium")
    model_premium = body.get("model_premium")
    premium_source = "actual"
    if actual_premium in (None, "") and model_premium not in (None, ""):
        actual_premium = model_premium
        premium_source = "model"

    state_payload = {
        "trade_id": trade_id,
        "short_strike": body.get("short_strike"),
        "long_strike": body.get("long_strike"),
        "expiry": body.get("expiry"),
        "dte_at_entry": body.get("dte_at_entry"),
        "contracts": body.get("contracts", 1),
        "actual_premium": actual_premium,
        "model_premium": model_premium,
        "premium_source": premium_source,
        "entry_spx": body.get("entry_spx"),
        "entry_vix": body.get("entry_vix"),
        "regime": body.get("regime"),
        "iv_signal": body.get("iv_signal"),
        "trend_signal": body.get("trend_signal"),
        "paper_trade": paper_trade,
    }
    account = str(body.get("account") or "schwab").strip().lower()
    add_tranche = bool(body.get("add_tranche", False))
    try:
        from strategy.sleeve_governance import evaluate_candidate, log_decision, maybe_alert_decision

        governance_candidate = {
            "sleeve": body.get("sleeve"),
            "strategy_key": strategy_key,
            "strategy": desc.name,
            "underlying": body.get("underlying", desc.underlying),
            "account": account,
            "action": "open",
            "short_strike": body.get("short_strike"),
            "long_strike": body.get("long_strike"),
            "contracts": body.get("contracts", 1),
            "requested_bp_dollars": body.get("requested_bp_dollars") or body.get("bp_usage_dollars"),
            "bp_preview": body.get("bp_preview"),
            "paper_trade": paper_trade,
        }
        governance_decision = evaluate_candidate(governance_candidate)
        log_decision(governance_decision)
        if not governance_decision.accepted and not paper_trade:
            maybe_alert_decision(governance_decision)
            return jsonify({
                "error": "Sleeve governance blocked entry",
                "governance": governance_decision.as_dict(),
            }), 400
    except Exception as exc:
        if not paper_trade:
            return jsonify({"error": f"Sleeve governance unavailable: {exc}"}), 503

    write_state(desc.name, body.get("underlying", desc.underlying), strategy_key=strategy_key, account=account, add_tranche=add_tranche, **state_payload)
    append_event({
        "id": trade_id,
        "event": "open",
        "timestamp": timestamp,
        "strategy_key": strategy_key,
        "strategy": desc.name,
        "underlying": body.get("underlying", desc.underlying),
        "short_strike": body.get("short_strike"),
        "long_strike": body.get("long_strike"),
        "expiry": body.get("expiry"),
        "dte_at_entry": body.get("dte_at_entry"),
        "contracts": body.get("contracts", 1),
        "actual_premium": actual_premium,
        "model_premium": model_premium,
        "premium_source": premium_source,
        "entry_spx": body.get("entry_spx"),
        "entry_vix": body.get("entry_vix"),
        "regime": body.get("regime"),
        "iv_signal": body.get("iv_signal"),
        "trend_signal": body.get("trend_signal"),
        "paper_trade": paper_trade,
        "note": body.get("note", ""),
    })

    # Async Telegram push — mirrors bot /entered flow
    try:
        from notify.event_push import notify_open
        from strategy.state import read_state as _read_state
        new_state = _read_state() or {}
        threading.Thread(target=notify_open, args=(new_state,), daemon=True).start()
    except Exception:
        pass

    return jsonify({"ok": True, "trade_id": trade_id})


@app.route("/api/position/open-draft")
def api_position_open_draft():
    from backtest.pricer import call_price, put_price, find_strike_for_delta
    from schwab.auth import is_configured as schwab_is_configured
    from schwab.scanner import build_strike_scan
    from strategy.selector import get_recommendation, StrategyParams

    try:
        force_key = flask_req.args.get("force_strategy", "").strip() or None
        if force_key:
            # User overrides wait: use forced strategy legs with current market snapshot
            forced_params = StrategyParams(force_strategy=force_key)
            rec = get_recommendation(use_intraday=_is_market_hours(), params=forced_params)
        else:
            rec = get_recommendation(use_intraday=_is_market_hours())

        if rec.strategy_key == "reduce_wait" or not rec.legs:
            return jsonify({"error": "No tradeable recommendation to prefill"}), 400

        spx = float(rec.trend_snapshot.spx)
        sigma = max(float(rec.vix_snapshot.vix) / 100.0, 0.01)

        priced_legs = []
        for leg in rec.legs:
            is_call = leg.option.upper() == "CALL"
            strike = find_strike_for_delta(spx, leg.dte, sigma, abs(float(leg.delta)), is_call)
            strike = int(round(strike / 5.0) * 5)
            price = call_price(spx, strike, leg.dte, sigma) if is_call else put_price(spx, strike, leg.dte, sigma)
            priced_legs.append({
                "action": leg.action,
                "option": leg.option,
                "dte": leg.dte,
                "delta": leg.delta,
                "strike": strike,
                "price": round(price, 2),
                "note": leg.note,
            })

        strike_scan = None
        scanner_error = None
        chosen_expiry = None
        if schwab_is_configured():
            try:
                scan_slots: dict[str, int] = {}
                if rec.strategy_key == "bull_call_diagonal":
                    short_idx = next((i for i, l in enumerate(priced_legs) if l["action"] == "SELL" and l["option"] == "CALL"), None)
                    if short_idx is not None:
                        scan_slots["short_leg"] = short_idx
                elif rec.strategy_key in {"iron_condor", "iron_condor_hv"}:
                    short_idx = next((i for i, l in enumerate(priced_legs) if l["action"] == "SELL" and l["option"] == "CALL"), None)
                    long_idx = next((i for i, l in enumerate(priced_legs) if l["action"] == "BUY" and l["option"] == "CALL"), None)
                    if short_idx is not None:
                        scan_slots["short_leg"] = short_idx
                    if long_idx is not None:
                        scan_slots["long_leg"] = long_idx
                else:
                    short_idx = next((i for i, l in enumerate(priced_legs) if l["action"] == "SELL"), None)
                    long_idx = next((i for i, l in enumerate(priced_legs) if l["action"] == "BUY"), None)
                    if short_idx is not None:
                        scan_slots["short_leg"] = short_idx
                    if long_idx is not None:
                        scan_slots["long_leg"] = long_idx

                strike_scan = {"scan_fallback": False}
                for slot, idx in scan_slots.items():
                    leg = priced_legs[idx]
                    target_delta = abs(float(leg["delta"])) if leg["option"] == "CALL" else -abs(float(leg["delta"]))
                    scan = build_strike_scan(
                        symbol=rec.underlying,
                        option_type=leg["option"],
                        target_delta=target_delta,
                        target_dte=int(leg["dte"]),
                        center_strike=float(leg["strike"]),
                    )
                    enriched_rows = []
                    target_abs = abs(float(target_delta))
                    for row in scan["rows"]:
                        live_delta = abs(float(row.get("delta"))) if row.get("delta") not in (None, "") else None
                        delta_gap = abs(live_delta - target_abs) if live_delta is not None else None
                        enriched_rows.append({
                            **row,
                            "target_delta": round(target_abs, 3),
                            "live_delta": round(live_delta, 3) if live_delta is not None else None,
                            "delta_gap": round(delta_gap, 3) if delta_gap is not None else None,
                        })
                    strike_scan[slot] = enriched_rows
                    strike_scan["scan_fallback"] = strike_scan["scan_fallback"] or scan["scan_fallback"]
                    recommended = next((row for row in enriched_rows if row.get("recommended")), None)
                    if recommended:
                        priced_legs[idx]["strike"] = int(round(float(recommended["strike"])))
                        if recommended.get("mid") not in (None, ""):
                            priced_legs[idx]["price"] = round(float(recommended["mid"]), 2)
                        if recommended.get("expiry"):
                            chosen_expiry = str(recommended["expiry"])

                if len(strike_scan) == 1 and "scan_fallback" in strike_scan:
                    strike_scan = None
            except Exception as exc:
                strike_scan = None
                scanner_error = str(exc)
        short_leg = None
        long_leg = None
        if rec.strategy_key in {"iron_condor", "iron_condor_hv"}:
            short_leg = next((l for l in priced_legs if l["action"] == "SELL" and l["option"] == "CALL"), None)
            long_leg = next((l for l in priced_legs if l["action"] == "BUY" and l["option"] == "CALL"), None)
        elif rec.strategy_key == "bull_call_diagonal":
            short_leg = next((l for l in priced_legs if l["action"] == "SELL" and l["option"] == "CALL"), None)
            long_leg = next((l for l in priced_legs if l["action"] == "BUY" and l["option"] == "CALL"), None)
        else:
            short_leg = next((l for l in priced_legs if l["action"] == "SELL"), None)
            long_leg = next((l for l in priced_legs if l["action"] == "BUY"), None)
        model_premium = round(sum((l["price"] if l["action"] == "SELL" else -l["price"]) for l in priced_legs), 2)
        expiry_dte = min(l["dte"] for l in priced_legs)
        expiry = (datetime.now(_ET).date() + timedelta(days=expiry_dte)).isoformat()
        if 'chosen_expiry' in locals() and chosen_expiry:
            expiry = chosen_expiry
        payload = {
            "strategy_key": rec.strategy_key,
            "strategy": rec.strategy.value,
            "underlying": rec.underlying,
            "expiry": expiry,
            "dte_at_entry": expiry_dte,
            "short_strike": short_leg["strike"] if short_leg else None,
            "long_strike": long_leg["strike"] if long_leg else None,
            "contracts": 1,
            "model_premium": model_premium,
            "entry_spx": round(rec.trend_snapshot.spx, 2),
            "entry_vix": round(rec.vix_snapshot.vix, 2),
            "regime": rec.vix_snapshot.regime.value,
            "iv_signal": rec.iv_snapshot.iv_signal.value,
            "trend_signal": rec.trend_snapshot.signal.value,
            "paper_trade": False,
            "legs": priced_legs,
            "legs_hint": " / ".join(f'{l["action"]} {l["option"]} {l["strike"]} ({l["dte"]}D)' for l in priced_legs),
        }
        if scanner_error:
            payload["scanner_error"] = scanner_error
            payload["legs_hint"] += " · Live strike scan unavailable — using model estimate."
        bp_preview = _bp_preview_payload(
            rec.strategy_key,
            rec.vix_snapshot.regime.value,
            payload["short_strike"],
            payload["long_strike"],
            model_premium,
            1,
        )
        payload["contracts"] = bp_preview["recommended_contracts"]
        payload["bp_preview"] = {
            **bp_preview,
            "bp_usage_dollars": round((bp_preview["bp_per_contract"] or 0.0) * payload["contracts"], 2)
            if bp_preview["bp_per_contract"] is not None else None,
            "bp_usage_pct": round((((bp_preview["bp_per_contract"] or 0.0) * payload["contracts"]) / bp_preview["pct_basis_dollars"]) * 100.0, 2)
            if bp_preview["bp_per_contract"] is not None and bp_preview.get("pct_basis_dollars") else None,
        }
        if strike_scan:
            payload["strike_scan"] = strike_scan
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/es/position/open-draft")
def api_es_position_open_draft():
    from backtest.pricer import put_price, find_strike_for_delta
    from schwab.scanner import build_strike_scan
    from strategy.selector import get_es_recommendation

    try:
        rec = get_es_recommendation(use_intraday=_is_market_hours())
        if rec.strategy_key == "reduce_wait" or not rec.legs:
            return jsonify({"error": "Trend filter blocked /ES short put"}), 400

        bp_gate = _live_es_bp_check()
        if not bp_gate.get("ok"):
            return jsonify({"error": bp_gate.get("reason"), "bp_gate": bp_gate}), 400

        spx = float(rec.trend_snapshot.spx)
        sigma = max(float(rec.vix_snapshot.vix) / 100.0, 0.01)
        strike = find_strike_for_delta(spx, 45, sigma, 0.20, is_call=False)
        strike = int(round(strike / 5.0) * 5)
        scan = build_strike_scan(
            symbol="/ES",
            option_type="PUT",
            target_delta=-0.20,
            target_dte=45,
            center_strike=float(strike),
        )
        rows = scan.get("rows") or []
        recommended = next((row for row in rows if row.get("recommended")), None)
        if scan.get("scan_fallback") or recommended is None:
            return jsonify({"error": "Insufficient /ES chain data for 45 DTE / 20 delta selection"}), 400

        live_delta = abs(float(recommended["delta"])) if recommended.get("delta") not in (None, "") else None
        model_price = put_price(spx, strike, 45, sigma)
        final_strike = int(round(float(recommended["strike"])))
        final_price = round(float(recommended["mid"]), 2) if recommended.get("mid") not in (None, "") else round(model_price, 2)
        expiry = str(recommended.get("expiry") or (datetime.now(_ET).date() + timedelta(days=45)).isoformat())
        payload = {
            "strategy_key": rec.strategy_key,
            "strategy": rec.strategy.value,
            "underlying": rec.underlying,
            "expiry": expiry,
            "dte_at_entry": 45,
            "short_strike": final_strike,
            "long_strike": None,
            "contracts": 1,
            "model_premium": final_price,
            "entry_spx": round(rec.trend_snapshot.spx, 2),
            "entry_vix": round(rec.vix_snapshot.vix, 2),
            "regime": rec.vix_snapshot.regime.value,
            "iv_signal": rec.iv_snapshot.iv_signal.value,
            "trend_signal": rec.trend_snapshot.signal.value,
            "roll_rule": rec.roll_rule,
            "max_risk": rec.max_risk,
            "target_return": rec.target_return,
            "rationale": rec.rationale,
            "paper_trade": False,
            "trend_filter_passed": True,
            "bp_check_passed": True,
            "bp_gate": bp_gate,
            "legs": [{
                "action": "SELL",
                "option": "PUT",
                "dte": 45,
                "delta": 0.20,
                "strike": final_strike,
                "price": final_price,
                "note": "Single-slot /ES short put candidate",
            }],
            "legs_hint": f"SELL PUT {final_strike} (45D)",
            "strike_scan": {
                "scan_fallback": False,
                "short_leg": [
                    {
                        **recommended,
                        "target_delta": 0.20,
                        "live_delta": round(live_delta, 3) if live_delta is not None else None,
                        "delta_gap": round(abs(live_delta - 0.20), 3) if live_delta is not None else None,
                    }
                ],
            },
            "bp_preview": {
                "bp_per_contract": bp_gate["es_bp_per_contract"],
                "bp_usage_dollars": bp_gate["es_bp_per_contract"],
                "bp_usage_pct": round((bp_gate["es_bp_per_contract"] / bp_gate["nlv"]) * 100.0, 2),
                "bp_target_pct": round(_ES_BP_LIMIT_FRACTION * 100.0, 2),
                "bp_target_dollars": bp_gate["bp_limit"],
                "recommended_contracts": 1,
                "basis_dollars": bp_gate["nlv"],
                "basis_label": "Schwab Net Liquidation",
                "basis_is_live": True,
                "pct_basis_dollars": bp_gate["nlv"],
                "pct_basis_label": "Schwab Net Liquidation",
                "current_bp_dollars": bp_gate["current_bp"],
                "projected_total_bp_dollars": bp_gate["projected_bp"],
            },
        }
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/position/close", methods=["POST"])
def api_position_close():
    from logs.trade_log_io import append_event
    from strategy.state import close_position, read_state, read_all_positions

    body = flask_req.get_json(force=True) or {}
    # account=None → close all; account="schwab"/"etrade" → close one leg
    account = body.get("account") or None
    if account:
        account = str(account).strip().lower()

    state = read_state()
    if not state:
        return jsonify({"error": "No open position"}), 400

    # Use the specific account's position data for PnL calc if account specified
    if account:
        all_pos = read_all_positions()
        leg = next(
            (p for p in (all_pos or {}).get("positions", []) if p.get("account") == account),
            state,
        )
    else:
        leg = state

    entry_premium = leg.get("actual_premium")
    exit_premium = body.get("exit_premium")
    actual_pnl = None
    model_pnl = None
    try:
        if entry_premium is not None and exit_premium not in (None, ""):
            actual_pnl = round((float(entry_premium) - float(exit_premium)) * float(leg.get("contracts", 1)) * 100, 2)
        model_prem = leg.get("model_premium")
        if model_prem is not None and exit_premium not in (None, ""):
            model_pnl = round((float(model_prem) - float(exit_premium)) * float(leg.get("contracts", 1)) * 100, 2)
    except (TypeError, ValueError):
        actual_pnl = None
        model_pnl = None

    close_position(
        note=body.get("note"),
        account=account,
        exit_premium=body.get("exit_premium"),
        exit_spx=body.get("exit_spx"),
        exit_reason=body.get("exit_reason"),
        actual_pnl=actual_pnl,
        model_pnl=model_pnl,
    )
    append_event({
        "id": state.get("trade_id"),
        "event": "close",
        "timestamp": _now_et_iso(),
        "exit_premium": body.get("exit_premium"),
        "exit_spx": body.get("exit_spx"),
        "exit_reason": body.get("exit_reason"),
        "actual_pnl": actual_pnl,
        "model_pnl": model_pnl,
        "note": body.get("note", ""),
    })

    # Async Telegram push — mirrors bot /closed flow with re-entry scan
    try:
        from notify.event_push import notify_close
        threading.Thread(target=notify_close, args=(state, body.get("note")), daemon=True).start()
    except Exception:
        pass

    return jsonify({"ok": True, "actual_pnl": actual_pnl, "model_pnl": model_pnl})


@app.route("/api/position/roll", methods=["POST"])
def api_position_roll():
    from logs.trade_log_io import append_event
    from strategy.state import read_state, roll_position

    body = flask_req.get_json(force=True) or {}
    state = read_state()
    if not state:
        return jsonify({"error": "No open position"}), 400
    roll_position(
        expiry=body.get("new_expiry"),
        short_strike=body.get("new_short_strike"),
        long_strike=body.get("new_long_strike"),
        roll_credit=body.get("roll_credit"),
    )
    append_event({
        "id": state.get("trade_id"),
        "event": "roll",
        "timestamp": _now_et_iso(),
        "new_expiry": body.get("new_expiry"),
        "new_short_strike": body.get("new_short_strike"),
        "new_long_strike": body.get("new_long_strike"),
        "roll_credit": body.get("roll_credit"),
        "note": body.get("note", ""),
    })
    return jsonify({"ok": True})


@app.route("/api/position/note", methods=["POST"])
def api_position_note():
    from logs.trade_log_io import append_event
    from strategy.state import add_note, read_state

    body = flask_req.get_json(force=True) or {}
    note = str(body.get("note", "")).strip()
    state = read_state()
    if not state:
        return jsonify({"error": "No open position"}), 400
    if not note:
        return jsonify({"error": "note is required"}), 400
    add_note(note)
    append_event({
        "id": state.get("trade_id"),
        "event": "note",
        "timestamp": _now_et_iso(),
        "note": note,
    })
    return jsonify({"ok": True})


@app.route("/api/trade-log")
def api_trade_log():
    from logs.trade_log_io import load_log, resolve_log
    if flask_req.args.get("raw") == "1":
        raw = load_log()
        return jsonify({"raw": raw})
    raw = load_log()
    return jsonify({"trades": resolve_log(), "raw_count": len(raw)})


_CORRECTABLE_FIELDS = {
        "open": {
            "actual_premium", "model_premium", "contracts", "short_strike", "long_strike",
            "expiry", "dte_at_entry", "entry_spx", "entry_vix", "note", "paper_trade",
        },
    "close": {
        "exit_premium", "exit_spx", "exit_reason", "actual_pnl", "note",
    },
    "roll": {
        "new_expiry", "new_short_strike", "new_long_strike", "roll_credit", "note",
    },
}


@app.route("/api/position/correction", methods=["POST"])
def api_position_correction():
    from logs.trade_log_io import append_event, load_log_by_id, resolve_log
    from strategy.state import read_state, update_open_position

    body = flask_req.get_json(force=True) or {}
    trade_id = str(body.get("trade_id", "")).strip()
    target_event = str(body.get("target_event", "")).strip()
    fields = body.get("fields") or {}
    reason = str(body.get("reason", "")).strip()

    if not trade_id:
        return jsonify({"error": "trade_id is required"}), 400
    if target_event not in {"open", "close", "roll"}:
        return jsonify({"error": "target_event must be open / close / roll"}), 400
    if not isinstance(fields, dict) or not fields:
        return jsonify({"error": "fields must be a non-empty object"}), 400
    if not reason:
        return jsonify({"error": "reason is required"}), 400

    rows = load_log_by_id(trade_id)
    if not rows:
        return jsonify({"error": "trade_id not found"}), 400
    if any(r.get("event") == "void" for r in rows):
        return jsonify({"error": "cannot correct a voided trade"}), 400

    allowed = _CORRECTABLE_FIELDS[target_event]
    for key in fields:
        if key not in allowed:
            return jsonify({"error": f"field not correctable: {key}"}), 400

    append_event({
        "id": trade_id,
        "event": "correction",
        "timestamp": _now_et_iso(),
        "target_event": target_event,
        "fields": fields,
        "reason": reason,
    })

    resolved = next((t for t in resolve_log() if t["id"] == trade_id), None)
    current = read_state()
    if target_event == "open" and current and current.get("trade_id") == trade_id and resolved and resolved.get("open"):
        ropen = resolved["open"]
        update_open_position(
            trade_id=trade_id,
            short_strike=ropen.get("short_strike"),
            long_strike=ropen.get("long_strike"),
            expiry=ropen.get("expiry"),
            dte_at_entry=ropen.get("dte_at_entry"),
            contracts=ropen.get("contracts"),
            actual_premium=ropen.get("actual_premium"),
            model_premium=ropen.get("model_premium"),
            entry_spx=ropen.get("entry_spx"),
            entry_vix=ropen.get("entry_vix"),
            paper_trade=ropen.get("paper_trade"),
        )

    auto_recalc = False
    if target_event == "open" and resolved and resolved.get("open") and resolved.get("close") and {"actual_premium", "contracts"} & set(fields):
        ropen = resolved["open"]
        rclose = resolved["close"]
        try:
            actual_pnl = round(
                (float(ropen.get("actual_premium")) - float(rclose.get("exit_premium"))) * float(ropen.get("contracts", 1)) * 100,
                2,
            )
            append_event({
                "id": trade_id,
                "event": "correction",
                "timestamp": _now_et_iso(),
                "target_event": "close",
                "fields": {"actual_pnl": actual_pnl},
                "reason": "auto-recalculated from open correction",
            })
            auto_recalc = True
        except (TypeError, ValueError):
            pass

    return jsonify({"ok": True, "auto_recalculated": auto_recalc})


@app.route("/api/position/void", methods=["POST"])
def api_position_void():
    from logs.trade_log_io import append_event, load_log_by_id
    from strategy.state import close_position, read_state

    body = flask_req.get_json(force=True) or {}
    trade_id = str(body.get("trade_id", "")).strip()
    reason = str(body.get("reason", "")).strip()
    if not trade_id:
        return jsonify({"error": "trade_id is required"}), 400
    if not reason:
        return jsonify({"error": "reason is required"}), 400
    rows = load_log_by_id(trade_id)
    if not rows:
        return jsonify({"error": "trade_id not found"}), 400
    if any(r.get("event") == "void" for r in rows):
        return jsonify({"error": "trade already voided"}), 400

    append_event({
        "id": trade_id,
        "event": "void",
        "timestamp": _now_et_iso(),
        "reason": reason,
    })
    current = read_state()
    state_cleared = bool(current and current.get("trade_id") == trade_id)
    if state_cleared:
        close_position(note=f"voided: {reason}")
    return jsonify({"ok": True, "state_cleared": state_cleared})


@app.route("/api/schwab/status")
def api_schwab_status():
    from schwab.auth import token_status
    return jsonify(token_status())


@app.route("/api/schwab/chain-debug")
def api_schwab_chain_debug():
    """Debug: show raw chain rows for current open position's strikes."""
    from schwab.client import _get_option_chain_exact_expiry, _spread_live_snapshot_from_chain, live_position_snapshot
    from strategy.state import read_state
    state = read_state()
    if not state:
        return jsonify({"error": "no open position"})
    expiry   = state.get("expiry", "")
    ss       = state.get("short_strike")
    ls       = state.get("long_strike")
    underly  = state.get("underlying", "SPX")
    try:
        rows = _get_option_chain_exact_expiry(underly, "PUT", expiry, center_strike=ss, strike_window=160)
    except Exception as e:
        rows = []
        chain_error = str(e)
    else:
        chain_error = None
    def _row(r):
        return {k: r.get(k) for k in ("strike","bid","ask","mark","mid","delta","gamma","theta","vega")}
    target_rows = [_row(r) for r in rows if r.get("strike") in (float(ss) if ss else None, float(ls) if ls else None)]
    snapshot = live_position_snapshot(state)
    return jsonify({
        "state_used": {"strategy_key": state.get("strategy_key"), "expiry": expiry,
                       "short_strike": ss, "long_strike": ls, "underlying": underly},
        "chain_rows_total": len(rows),
        "chain_error": chain_error,
        "target_rows": target_rows,
        "snapshot_visible": snapshot.get("visible"),
        "snapshot_pricing_source": snapshot.get("pricing_source"),
        "snapshot_mark": snapshot.get("mark"),
        "snapshot_trade_log_pnl": snapshot.get("trade_log_pnl"),
    })


@app.route("/api/schwab/positions")
def api_schwab_positions():
    from schwab.client import get_account_positions, get_account_balances

    pos_payload  = get_account_positions()
    bal_payload  = get_account_balances()
    positions    = pos_payload.get("positions", [])
    nlv          = bal_payload.get("net_liquidation") or 0.0
    maintenance  = bal_payload.get("maintenance_margin") or 0.0

    # Known ETF tickers for sub-category classification
    _EQUITY_ETF    = {"SPY", "QQQ", "IWM", "VTI", "VOO", "SCHB"}
    _BOND_ETF      = {"BND", "AGG", "SHY", "TLT"}
    _CASH_ETF      = {"BOXX", "SGOV", "TBLL", "USFR", "FLOT", "SHV", "BIL"}
    _MONEY_MARKET  = {"SPAXX", "SWVXX", "VMFXX", "VMMXX", "FDRXX", "FZFXX", "SPRXX"}

    enriched = []
    # Group SPXW legs by expiry to show as spread net
    spx_legs: dict = {}
    for pos in positions:
        sym      = str(pos.get("symbol") or "")
        at       = str(pos.get("asset_type") or "")
        mv       = float(pos.get("market_value") or 0.0)
        sym_up   = sym.upper()

        if at == "OPTION" and ("SPX" in sym_up or "SPXW" in sym_up):
            # Collect SPX option legs to group into spread
            key = "spx_options"
            if key not in spx_legs:
                spx_legs[key] = {"legs": [], "net_mv": 0.0}
            spx_legs[key]["legs"].append(pos)
            spx_legs[key]["net_mv"] += mv
        else:
            if at == "EQUITY":
                cat = "equity"
                sub = "stock"
            elif at == "COLLECTIVE_INVESTMENT":
                if sym_up in _EQUITY_ETF:
                    cat = "collective"
                    sub = "equity_etf"
                elif sym_up in _CASH_ETF:
                    cat = "collective"
                    sub = "cash_etf"
                elif sym_up in _BOND_ETF:
                    cat = "collective"
                    sub = "bond_etf"
                elif sym_up in _MONEY_MARKET:
                    cat = "cash"
                    sub = "money_market"
                else:
                    cat = "collective"
                    sub = "etf"
            else:
                cat = "other"
                sub = at.lower()
            enriched.append({
                "symbol":       sym,
                "description":  pos.get("description") or sym,
                "asset_type":   at,
                "category":     cat,
                "sub_category": sub,
                "market_value": round(mv, 2),
                "mv_pct_nlv":   round(mv / nlv * 100, 2) if nlv else None,
                "quantity":     pos.get("quantity"),
                "unrealized_pnl": pos.get("unrealized_pnl"),
            })

    # Add grouped SPX spread entry
    for key, grp in spx_legs.items():
        net_mv = grp["net_mv"]
        enriched.append({
            "symbol":       "SPX Options",
            "description":  f"SPX spread ({len(grp['legs'])} legs)",
            "asset_type":   "OPTION",
            "category":     "spx_options",
            "sub_category": "spread",
            "market_value": round(net_mv, 2),
            "mv_pct_nlv":   round(net_mv / nlv * 100, 2) if nlv else None,
            "legs":         grp["legs"],
        })

    # Inject cash balance as a synthetic position if > $1
    cash_balance = float(bal_payload.get("cash_balance") or 0.0)
    # Subtract money-market positions already counted as positions to avoid double-count
    mm_mv = sum(p.get("market_value") or 0.0 for p in enriched if p.get("sub_category") == "money_market")
    cash_only = cash_balance - mm_mv
    if cash_only > 1.0:
        enriched.append({
            "symbol":       "Cash",
            "description":  "Cash & sweep",
            "asset_type":   "CASH",
            "category":     "cash",
            "sub_category": "cash",
            "market_value": round(cash_only, 2),
            "mv_pct_nlv":   round(cash_only / nlv * 100, 2) if nlv else None,
            "quantity":     None,
            "unrealized_pnl": None,
        })

    # Compute total cash (cash + cash ETF + money market)
    _CASH_CATS = {"cash"}
    _CASH_SUBS = {"cash_etf", "money_market", "cash"}
    total_cash_mv = sum(
        p.get("market_value") or 0.0 for p in enriched
        if p.get("category") == "cash" or p.get("sub_category") in _CASH_SUBS
    )

    # Sort: spx_options first, cash last, then by abs market value desc
    enriched.sort(key=lambda p: (
        0 if p["category"] == "spx_options" else (2 if p["category"] == "cash" or p.get("sub_category") in ("cash_etf", "money_market", "cash") else 1),
        -abs(p.get("market_value") or 0)
    ))

    return jsonify({
        "configured":   pos_payload.get("configured"),
        "authenticated": pos_payload.get("authenticated"),
        "positions":    enriched,
        "summary": {
            "nlv":              round(nlv, 2),
            "maintenance_margin": round(maintenance, 2),
            "margin_pct_nlv":   round(maintenance / nlv * 100, 2) if nlv else None,
            "position_count":   len(enriched),
            "cash_balance":     round(cash_balance, 2),
            "total_cash_mv":    round(total_cash_mv, 2),
            "total_cash_pct":   round(total_cash_mv / nlv * 100, 2) if nlv else None,
        },
    })


@app.route("/api/schwab/balances")
def api_schwab_balances():
    from schwab.client import get_account_balances
    return jsonify(get_account_balances())


@app.route("/api/performance/live")
def api_performance_live():
    from logs.trade_log_io import resolve_log
    from performance.live import compute_live_performance
    from schwab.client import live_position_snapshot
    from strategy.state import read_state

    resolved = resolve_log()
    state = read_state()
    schwab_snapshot = live_position_snapshot(state)
    include_paper = flask_req.args.get("include_paper") == "1"
    return jsonify(compute_live_performance(resolved, schwab_snapshot=schwab_snapshot, include_paper=include_paper))


@app.route("/api/intraday")
def api_intraday():
    from signals.intraday import get_vix_spike, get_spx_stop
    try:
        spike = get_vix_spike(interval="5m")
        stop  = get_spx_stop(interval="5m")
        return jsonify({
            "vix_spike": {
                "timestamp":   spike.timestamp,
                "vix_open":    round(spike.vix_open, 2),
                "vix_current": round(spike.vix_current, 2),
                "spike_pct":   round(spike.spike_pct * 100, 2),
                "level":       spike.level.value,
            },
            "spx_stop": {
                "timestamp":   stop.timestamp,
                "spx_open":    round(stop.spx_open, 2),
                "spx_current": round(stop.spx_current, 2),
                "drop_pct":    round(stop.drop_pct * 100, 2),
                "level":       stop.level.value,
            },
            "market_open": _is_market_hours(),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/backtest")
def api_backtest():
    from backtest.engine import run_backtest
    from strategy.catalog import strategy_key as catalog_strategy_key

    start = flask_req.args.get(
        "start", (date.today() - timedelta(days=365)).isoformat()
    )
    params, phash, _params_payload = _backtest_query_params()
    cache_key = f"{start}__{phash}"
    today = date.today().isoformat()
    cached = _backtest_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return jsonify(cached[1])

    disk_cache = _load_results_disk()
    entry = disk_cache.get(cache_key, {})
    if entry.get("date") == today and entry.get("params_hash") == phash:
        result = {
            **entry.get("payload", {}),
            "computed_at": entry.get("computed_at"),
            "start_date": entry.get("start_date", start),
            "params_hash": phash,
        }
        _backtest_cache[cache_key] = (time.time(), result)
        return jsonify(result)

    try:
        trades, metrics, _signals = run_backtest(start_date=start, verbose=False, params=params, account_size=_BACKTEST_ACCOUNT_SIZE)
        trades_data = [
            {
                "strategy":        t.strategy.value,
                "strategy_key":    catalog_strategy_key(t.strategy.value),
                "underlying":      t.underlying,
                "entry_date":      t.entry_date,
                "exit_date":       t.exit_date,
                "entry_spx":       round(t.entry_spx, 2),
                "exit_spx":        round(t.exit_spx, 2),
                "entry_vix":       round(t.entry_vix, 2),
                "entry_credit":    round(t.entry_credit, 2),
                "exit_pnl":        round(t.exit_pnl, 2),
                "exit_reason":     t.exit_reason,
                "entry_reason":    getattr(t, "entry_reason", ""),
                "dte_at_entry":    t.dte_at_entry,
                "dte_at_exit":     t.dte_at_exit,
                "spread_width":    round(t.spread_width, 0),
                "option_premium":  round(t.option_premium, 2),
                "bp_per_contract": round(t.bp_per_contract, 2),
                "contracts":       round(t.contracts, 4),
                "total_bp":        round(t.total_bp, 2),
                "bp_pct_account":  round(t.bp_pct_account, 2),
            }
            for t in trades
        ]
        computed_at = datetime.now(_ET).isoformat(timespec="seconds")
        result = {
            "metrics": metrics,
            "trades": trades_data,
            "computed_at": computed_at,
            "start_date": start,
            "params_hash": phash,
        }
        _backtest_cache[cache_key] = (time.time(), result)
        disk_cache[cache_key] = {
            "date": today,
            "start_date": start,
            "params_hash": phash,
            "computed_at": computed_at,
            "payload": {
                "metrics": metrics,
                "trades": trades_data,
            },
        }
        _save_results_disk(disk_cache)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/signals/history")
def api_signals_history():
    from backtest.engine import run_signals_only

    start = flask_req.args.get("start", "2000-01-01")
    cache_key = f"signals__{start}"
    cached = _signals_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _SIGNALS_CACHE_TTL:
        return jsonify(cached[1])
    try:
        payload = {"signals": run_signals_only(start_date=start)}
        _signals_cache[cache_key] = (time.time(), payload)
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/backtest/latest-cached")
def api_backtest_latest_cached():
    disk_cache = _load_results_disk()
    if not disk_cache:
        return jsonify({"empty": True})
    current_phash = _params_hash()
    latest = None
    for entry in disk_cache.values():
        if not isinstance(entry, dict):
            continue
        # Only serve entries that match current params (account_size, strategy defaults)
        if entry.get("params_hash") != current_phash:
            continue
        if latest is None or entry.get("computed_at", "") > latest.get("computed_at", ""):
            latest = entry
    if latest is None:
        return jsonify({"empty": True})
    return jsonify({
        **latest.get("payload", {}),
        "computed_at": latest.get("computed_at"),
        "start_date": latest.get("start_date"),
        "params_hash": latest.get("params_hash"),
    })


@app.route("/api/research/views")
def api_research_views():
    if not _RESEARCH_VIEWS_FILE.exists():
        return jsonify({"empty": True, "message": "Run: python -m backtest.research_views generate"})
    try:
        return jsonify(json.loads(_RESEARCH_VIEWS_FILE.read_text()))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _iv_level(ivp: float) -> str:
    """Map IVP value to matrix IV row key using selector thresholds."""
    return "HIGH" if ivp > 70 else ("LOW" if ivp < 40 else "NEUTRAL")


@app.route("/api/backtest/stats")
def api_backtest_stats():
    """Per-strategy and per-cell trade count and win rate for 3Y, 10Y, and all-time periods.

    Returns:
        {
          "3y":       { strategy_name: {n, win_rate} },
          "10y":      { strategy_name: {n, win_rate} },
          "all":      { strategy_name: {n, win_rate} },
          "3y_cell":  { "REGIME|IV|TREND": {n, win_rate} },
          "10y_cell": { "REGIME|IV|TREND": {n, win_rate} },
          "all_cell": { "REGIME|IV|TREND": {n, win_rate} },
        }
    """
    from backtest.engine import run_backtest
    from strategy.catalog import strategy_key as catalog_strategy_key
    result = {}
    today       = date.today().isoformat()
    phash       = _params_hash()
    disk_cache  = _load_stats_disk()
    disk_dirty  = False

    periods = [
        ("3y",  (date.today() - timedelta(days=365 * 3)).isoformat()),
        ("10y", (date.today() - timedelta(days=365 * 10)).isoformat()),
        ("all", "2000-01-01"),
    ]
    for period, start in periods:
        cache_key = f"stats_{start}"

        # 1. Memory cache (hot path — same process, within TTL)
        mem = _backtest_cache.get(cache_key)
        if mem and (time.time() - mem[0]) < _CACHE_TTL:
            payload = mem[1]
            result[period]           = {k: v for k, v in payload.items() if not k.startswith("_")}
            result[f"{period}_cell"] = payload.get("_cell", {})
            continue

        # 2. Disk cache (survives restarts — valid for today + same params)
        entry = disk_cache.get(cache_key, {})
        if (
            entry.get("date") == today
            and entry.get("params_hash") == phash
            and entry.get("schema") == _STATS_SCHEMA_VERSION
            and _stats_payload_has_avg(entry.get("payload", {}))
        ):
            payload = entry["payload"]
            _backtest_cache[cache_key] = (time.time(), payload)  # warm memory cache
            result[period]           = {k: v for k, v in payload.items() if not k.startswith("_")}
            result[f"{period}_cell"] = payload.get("_cell", {})
            continue

        # 3. Run backtest and populate both caches
        try:
            trades, _, signals = run_backtest(start_date=start, verbose=False, account_size=_BACKTEST_ACCOUNT_SIZE)
            sig_by_date = {s["date"]: s for s in signals}

            by_strat: dict[str, dict] = {}
            by_cell:  dict[str, dict] = {}

            for t in trades:
                key  = catalog_strategy_key(t.strategy.value)
                win  = t.exit_pnl > 0

                rec = by_strat.setdefault(key, {"n": 0, "wins": 0, "total_pnl": 0.0})
                rec["n"] += 1
                if win:
                    rec["wins"] += 1
                rec["total_pnl"] += t.exit_pnl

                sig      = sig_by_date.get(t.entry_date, {})
                regime   = sig.get("regime", "")
                iv_lv    = _iv_level(float(sig.get("ivp", 50)))
                trend    = sig.get("trend", "NEUTRAL")
                cell_key = f"{regime}|{iv_lv}|{trend}"
                crec = by_cell.setdefault(cell_key, {"n": 0, "wins": 0, "total_pnl": 0.0})
                crec["n"] += 1
                if win:
                    crec["wins"] += 1
                crec["total_pnl"] += t.exit_pnl

            strat_stats = {
                s: {"n": v["n"], "win_rate": round(v["wins"] / v["n"] * 100), "avg_pnl": round(v["total_pnl"] / v["n"])}
                for s, v in by_strat.items()
            }
            cell_stats = {
                k: {"n": v["n"], "win_rate": round(v["wins"] / v["n"] * 100), "avg_pnl": round(v["total_pnl"] / v["n"])}
                for k, v in by_cell.items()
            }
            payload = {**strat_stats, "_cell": cell_stats}

            _backtest_cache[cache_key] = (time.time(), payload)
            disk_cache[cache_key] = {"date": today, "params_hash": phash, "schema": _STATS_SCHEMA_VERSION, "payload": payload}
            disk_dirty = True

            result[period]           = strat_stats
            result[f"{period}_cell"] = cell_stats
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    if disk_dirty:
        _save_stats_disk(disk_cache)

    return jsonify(result)


# ── Experiment APIs ─────────────────────────────────────────────────────────

@app.route("/api/experiments")
def api_experiments():
    from backtest.experiment import load_experiments, diff_params, diff_metrics
    exps = load_experiments()
    a_id = flask_req.args.get("compare_a", type=int)
    b_id = flask_req.args.get("compare_b", type=int)
    if a_id and b_id:
        by_id = {e["id"]: e for e in exps}
        ea, eb = by_id.get(a_id), by_id.get(b_id)
        if ea and eb:
            return jsonify({
                "experiments": exps,
                "comparison": {
                    "a": ea, "b": eb,
                    "param_diff":  diff_params(ea, eb),
                    "metric_diff": diff_metrics(ea, eb),
                },
            })
    return jsonify({"experiments": exps})


@app.route("/api/experiments/run", methods=["POST"])
def api_experiments_run():
    from backtest.experiment import run_experiment
    from strategy.selector import StrategyParams
    body = flask_req.get_json(force=True) or {}
    try:
        p = body.get("params", {})
        _d = StrategyParams()  # canonical defaults — never hardcode fallbacks here
        params = StrategyParams(
            extreme_vix     = float(p.get("extreme_vix",    _d.extreme_vix)),
            high_vol_delta  = float(p.get("high_vol_delta", _d.high_vol_delta)),
            high_vol_dte    = int(  p.get("high_vol_dte",   _d.high_vol_dte)),
            high_vol_size   = float(p.get("high_vol_size",  _d.high_vol_size)),
            normal_delta    = float(p.get("normal_delta",   _d.normal_delta)),
            normal_dte      = int(  p.get("normal_dte",     _d.normal_dte)),
            profit_target   = float(p.get("profit_target",  _d.profit_target)),
            stop_mult       = float(p.get("stop_mult",      _d.stop_mult)),
            min_hold_days   = int(  p.get("min_hold_days",  _d.min_hold_days)),
        )
        exp = run_experiment(
            params     = params,
            note       = str(body.get("note", "")),
            start_date = str(body.get("start_date", "2020-01-01")),
            end_date   = body.get("end_date") or None,
        )
        return jsonify(exp)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _run_auto_search(grid: dict, fixed: dict, start_date: str):
    """Background thread: sweep parameter grid, log each combination."""
    global _auto_search
    from backtest.experiment import run_experiment
    from strategy.selector import StrategyParams

    keys   = list(grid.keys())
    values = list(grid.values())
    combos = list(product(*values))

    _auto_search.update(running=True, total=len(combos), completed=0,
                        best=None, error=None)
    try:
        _d = StrategyParams()
        for combo in combos:
            p = {**fixed, **dict(zip(keys, combo))}
            params = StrategyParams(
                extreme_vix    = float(p.get("extreme_vix",    _d.extreme_vix)),
                high_vol_delta = float(p.get("high_vol_delta", _d.high_vol_delta)),
                high_vol_dte   = int(  p.get("high_vol_dte",   _d.high_vol_dte)),
                high_vol_size  = float(p.get("high_vol_size",  _d.high_vol_size)),
                normal_delta   = float(p.get("normal_delta",   _d.normal_delta)),
                normal_dte     = int(  p.get("normal_dte",     _d.normal_dte)),
                profit_target  = float(p.get("profit_target",  _d.profit_target)),
                stop_mult      = float(p.get("stop_mult",      _d.stop_mult)),
                min_hold_days  = int(  p.get("min_hold_days",  _d.min_hold_days)),
            )
            note = "auto: " + ", ".join(f"{k}={v}" for k, v in zip(keys, combo))
            exp  = run_experiment(params=params, note=note,
                                  start_date=start_date, is_auto=True)
            _auto_search["completed"] += 1
            sharpe = exp.get("metrics", {}).get("sharpe", -999)
            best_sharpe = (_auto_search["best"] or {}).get("metrics", {}).get("sharpe", -999)
            if sharpe > best_sharpe:
                _auto_search["best"] = exp
    except Exception as exc:
        _auto_search["error"] = str(exc)
    finally:
        _auto_search["running"] = False


@app.route("/api/experiments/auto", methods=["POST"])
def api_experiments_auto():
    if _auto_search["running"]:
        return jsonify({"error": "Auto-search already running"}), 409
    body  = flask_req.get_json(force=True) or {}
    grid  = body.get("grid", {})
    fixed = body.get("fixed", {})
    start = str(body.get("start_date", "2020-01-01"))
    if not grid:
        return jsonify({"error": "No grid params specified"}), 400
    if len(grid) > 3:
        return jsonify({"error": "Max 3 sweep params to limit overfitting"}), 400
    total = 1
    for v in grid.values():
        total *= len(v)
    threading.Thread(target=_run_auto_search, args=(grid, fixed, start),
                     daemon=True).start()
    return jsonify({"started": True, "total": total})


@app.route("/api/experiments/auto/status")
def api_experiments_auto_status():
    s = dict(_auto_search)
    if s.get("best"):
        b = s["best"]
        s["best"] = {
            "id":       b.get("id"),
            "note":     b.get("note"),
            "sharpe":   b.get("metrics", {}).get("sharpe"),
            "win_rate": b.get("metrics", {}).get("win_rate"),
        }
    return jsonify(s)
