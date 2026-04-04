"""
web/server.py — Local Flask dashboard for the SPX Strategy Bot

Start:
  python main.py --web              → http://localhost:5050
  python main.py --web --port=8080
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict
from datetime import date, timedelta
from enum import Enum
from itertools import product
from pathlib import Path

from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, render_template
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
_CACHE_TTL = 300  # 5 minutes

# ── Disk cache for backtest stats (survives restarts) ────────────────────────
_STATS_DISK_CACHE = Path(__file__).parent.parent / "data" / "backtest_stats_cache.json"


def _params_hash() -> str:
    """Short hash of current default StrategyParams — changes when defaults change."""
    from strategy.selector import StrategyParams
    return hashlib.md5(str(StrategyParams()).encode()).hexdigest()[:10]


def _load_stats_disk() -> dict:
    try:
        if _STATS_DISK_CACHE.exists():
            return json.loads(_STATS_DISK_CACHE.read_text())
    except Exception:
        pass
    return {}


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
    return render_template("index.html")


@app.route("/backtest")
def backtest_page():
    return render_template("backtest.html")


@app.route("/matrix")
def matrix_page():
    return render_template("matrix.html")


@app.route("/margin")
def margin_page():
    return render_template("margin.html")


@app.route("/api/recommendation")
def api_recommendation():
    from strategy.selector import get_recommendation
    try:
        rec = get_recommendation(use_intraday=_is_market_hours())
        return _json_dc(rec)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/strategy-catalog")
def api_strategy_catalog():
    from strategy.catalog import strategy_catalog_payload
    return jsonify(strategy_catalog_payload())


@app.route("/api/position")
def api_position():
    from strategy.state import read_state
    from strategy.catalog import strategy_descriptor
    state = read_state()
    if state is None:
        return jsonify({"open": False})
    if state.get("strategy_key"):
        try:
            state["strategy_meta"] = asdict(strategy_descriptor(state["strategy_key"]))
        except Exception:
            pass
    return jsonify({"open": True, **state})


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
    cached = _backtest_cache.get(start)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return jsonify(cached[1])
    try:
        trades, metrics, signals = run_backtest(start_date=start, verbose=False)
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
        result = {"metrics": metrics, "trades": trades_data, "signals": signals}
        _backtest_cache[start] = (time.time(), result)
        return jsonify(result)
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
        if entry.get("date") == today and entry.get("params_hash") == phash:
            payload = entry["payload"]
            _backtest_cache[cache_key] = (time.time(), payload)  # warm memory cache
            result[period]           = {k: v for k, v in payload.items() if not k.startswith("_")}
            result[f"{period}_cell"] = payload.get("_cell", {})
            continue

        # 3. Run backtest and populate both caches
        try:
            trades, _, signals = run_backtest(start_date=start, verbose=False)
            sig_by_date = {s["date"]: s for s in signals}

            by_strat: dict[str, dict] = {}
            by_cell:  dict[str, dict] = {}

            for t in trades:
                key  = catalog_strategy_key(t.strategy.value)
                win  = t.exit_pnl > 0

                rec = by_strat.setdefault(key, {"n": 0, "wins": 0})
                rec["n"] += 1
                if win: rec["wins"] += 1

                sig      = sig_by_date.get(t.entry_date, {})
                regime   = sig.get("regime", "")
                iv_lv    = _iv_level(float(sig.get("ivp", 50)))
                trend    = sig.get("trend", "NEUTRAL")
                cell_key = f"{regime}|{iv_lv}|{trend}"
                crec = by_cell.setdefault(cell_key, {"n": 0, "wins": 0})
                crec["n"] += 1
                if win: crec["wins"] += 1

            strat_stats = {
                s: {"n": v["n"], "win_rate": round(v["wins"] / v["n"] * 100)}
                for s, v in by_strat.items()
            }
            cell_stats = {
                k: {"n": v["n"], "win_rate": round(v["wins"] / v["n"] * 100)}
                for k, v in by_cell.items()
            }
            payload = {**strat_stats, "_cell": cell_stats}

            _backtest_cache[cache_key] = (time.time(), payload)
            disk_cache[cache_key] = {"date": today, "params_hash": phash, "payload": payload}
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
        params = StrategyParams(
            extreme_vix     = float(p.get("extreme_vix",     35.0)),
            high_vol_delta  = float(p.get("high_vol_delta",  0.20)),
            high_vol_dte    = int(  p.get("high_vol_dte",    21)),
            high_vol_size   = float(p.get("high_vol_size",   0.50)),
            normal_delta    = float(p.get("normal_delta",    0.30)),
            normal_dte      = int(  p.get("normal_dte",      30)),
            profit_target   = float(p.get("profit_target",   0.50)),
            stop_mult       = float(p.get("stop_mult",       2.0)),
            min_hold_days   = int(  p.get("min_hold_days",   10)),
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
        for combo in combos:
            p = {**fixed, **dict(zip(keys, combo))}
            params = StrategyParams(
                extreme_vix    = float(p.get("extreme_vix",    35.0)),
                high_vol_delta = float(p.get("high_vol_delta", 0.20)),
                high_vol_dte   = int(  p.get("high_vol_dte",   21)),
                high_vol_size  = float(p.get("high_vol_size",  0.50)),
                normal_delta   = float(p.get("normal_delta",   0.30)),
                normal_dte     = int(  p.get("normal_dte",     30)),
                profit_target  = float(p.get("profit_target",  0.50)),
                stop_mult      = float(p.get("stop_mult",      2.0)),
                min_hold_days  = int(  p.get("min_hold_days",  14)),
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
