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
from datetime import date, datetime, timedelta
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
_signals_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # 5 minutes
_SIGNALS_CACHE_TTL = 3600  # 1 hour
_STATS_SCHEMA_VERSION = "v2"

# ── Disk cache for backtest stats (survives restarts) ────────────────────────
_STATS_DISK_CACHE = Path(__file__).parent.parent / "data" / "backtest_stats_cache.json"
_RESULTS_DISK_CACHE = Path(__file__).parent.parent / "data" / "backtest_results_cache.json"


def _params_hash() -> str:
    """Short hash of current default StrategyParams — changes when defaults change."""
    from strategy.selector import StrategyParams
    return _hash_payload(asdict(StrategyParams()))


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
    return StrategyParams(**params_payload), _hash_payload(params_payload), params_payload


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


@app.route("/performance")
def performance_page():
    return render_template("performance.html")


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
    from schwab.client import live_position_snapshot
    state = read_state()
    if state is None:
        return jsonify({"open": False, "schwab_live": live_position_snapshot(None)})
    if state.get("strategy_key"):
        try:
            state["strategy_meta"] = asdict(strategy_descriptor(state["strategy_key"]))
        except Exception:
            pass
    return jsonify({"open": True, **state, "schwab_live": live_position_snapshot(state)})


def _now_et_iso() -> str:
    return datetime.now(_ET).isoformat(timespec="seconds")


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
    write_state(desc.name, body.get("underlying", desc.underlying), strategy_key=strategy_key, **state_payload)
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
    return jsonify({"ok": True, "trade_id": trade_id})


@app.route("/api/position/open-draft")
def api_position_open_draft():
    from backtest.pricer import call_price, put_price, find_strike_for_delta
    from strategy.selector import get_recommendation

    try:
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

        short_leg = next((l for l in priced_legs if l["action"] == "SELL"), None)
        long_leg = next((l for l in priced_legs if l["action"] == "BUY"), None)
        model_premium = round(sum((l["price"] if l["action"] == "SELL" else -l["price"]) for l in priced_legs), 2)
        expiry_dte = min(l["dte"] for l in priced_legs)
        expiry = (datetime.now(_ET).date() + timedelta(days=expiry_dte)).isoformat()
        return jsonify({
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
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/position/close", methods=["POST"])
def api_position_close():
    from logs.trade_log_io import append_event
    from strategy.state import close_position, read_state

    body = flask_req.get_json(force=True) or {}
    state = read_state()
    if not state:
        return jsonify({"error": "No open position"}), 400
    entry_premium = state.get("actual_premium")
    exit_premium = body.get("exit_premium")
    actual_pnl = None
    model_pnl = None
    try:
        if entry_premium is not None and exit_premium not in (None, ""):
            actual_pnl = round((float(entry_premium) - float(exit_premium)) * float(state.get("contracts", 1)) * 100, 2)
        model_prem = state.get("model_premium")
        if model_prem is not None and exit_premium not in (None, ""):
            model_pnl = round((float(model_prem) - float(exit_premium)) * float(state.get("contracts", 1)) * 100, 2)
    except (TypeError, ValueError):
        actual_pnl = None
        model_pnl = None

    close_position(
        note=body.get("note"),
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


@app.route("/api/schwab/positions")
def api_schwab_positions():
    from schwab.client import get_account_positions
    return jsonify(get_account_positions())


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
        trades, metrics, _signals = run_backtest(start_date=start, verbose=False, params=params)
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
    latest = None
    for entry in disk_cache.values():
        if not isinstance(entry, dict):
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
            trades, _, signals = run_backtest(start_date=start, verbose=False)
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
