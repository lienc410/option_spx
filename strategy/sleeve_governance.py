from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
STATE_LOG_PATH = DATA_DIR / "sleeve_governance_state.jsonl"
DECISION_LOG_PATH = DATA_DIR / "sleeve_governance_decisions.jsonl"
OVERRIDE_LOG_PATH = DATA_DIR / "sleeve_governance_overrides.jsonl"
RUNTIME_STATE_PATH = DATA_DIR / "sleeve_governance_runtime.json"
BOOSTER_SHADOW_LOG_PATH = DATA_DIR / "q074_booster_shadow.jsonl"
Q072_DIR = REPO_ROOT / "research" / "q072"
Q072_DAILY_FLAGS = Q072_DIR / "q072_p1_daily_flags.csv"
Q072_PORTFOLIO_STATE = Q072_DIR / "q072_p4c0_portfolio_state.csv"
Q072_ALLOCATOR_RESULTS = Q072_DIR / "q072_p4c4_allocator_results.csv"

SPX_NLV = 100_000.0
ES_NLV = 100_000.0
COMBINED_NLV = SPX_NLV + ES_NLV

CAP_SPX_PM = 80.0
CAP_ES_SPAN = 80.0
CAP_COMBINED = 60.0
CAP_SHORT_VOL = 50.0
CAP_STRESS_EPISODE = 50.0
CAP_SECOND_LEG_EPISODE = 40.0
CAP_SPX_BENIGN_BOOSTER = 90.0
_REPLAY_CACHE: dict | None = None

SHORT_VOL_STRATEGIES = {
    "bull_put_spread",
    "bull_put_spread_hv",
    "iron_condor",
    "iron_condor_hv",
    "bear_call_spread",
    "bear_call_spread_hv",
    "es_short_put",
    "hv_ladder",
}
SHORT_VOL_TEXT = (
    "bull put",
    "iron condor",
    "bear call",
    "short put",
    "hv ladder",
)
LONG_GAMMA_TEXT = (
    "drawdown overlay",
    "long call",
    "call spread",
    "long gamma",
)


def _et_now() -> datetime:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("America/New_York"))
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _et_now().isoformat(timespec="seconds")


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        number = float(value)
        if math.isnan(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def booster_mode() -> str:
    """SPEC-105 rollout mode. Default is mandatory Stage 1 shadow."""
    mode = str(os.getenv("SPX_BENIGN_BOOSTER_MODE", "shadow")).strip().lower()
    return mode if mode in {"shadow", "active", "disabled"} else "shadow"


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:] if limit else rows


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _parse_duration(value: str) -> timedelta:
    raw = str(value).strip().lower()
    if not raw:
        raise ValueError("duration is required")
    unit = raw[-1]
    amount = float(raw[:-1])
    if unit == "d":
        return timedelta(days=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    raise ValueError("duration must end with d, h, or m")


def active_overrides(now: datetime | None = None) -> list[dict]:
    now = now or _et_now()
    active: list[dict] = []
    for row in _read_jsonl(OVERRIDE_LOG_PATH):
        try:
            expires_at = datetime.fromisoformat(str(row.get("expires_at")))
        except ValueError:
            continue
        if expires_at.tzinfo is None and now.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        if expires_at > now and row.get("action") == "pause":
            active.append(row)
    return active


def is_rule_paused(rule: str, now: datetime | None = None) -> bool:
    rule = str(rule).upper()
    return any(str(row.get("rule", "")).upper() == rule for row in active_overrides(now))


def pause_rule(rule: str, duration: str, reason: str = "manual override") -> dict:
    now = _et_now()
    payload = {
        "timestamp": now.isoformat(timespec="seconds"),
        "action": "pause",
        "rule": str(rule).upper(),
        "duration": duration,
        "expires_at": (now + _parse_duration(duration)).isoformat(timespec="seconds"),
        "reason": reason,
    }
    _append_jsonl(OVERRIDE_LOG_PATH, payload)
    return payload


def stress_episode_from_flags(daily: Any) -> Any:
    """Q072 tight stress episode: stress flag true within last 3 trading days."""
    flag = (
        (daily["vix"] >= 22.0)
        | (daily["dd_20d"] <= -0.04)
        | (daily["dd_60d"] <= -0.04)
        | daily.get("dd_overlay_active", False).astype(bool)
        | daily.get("aftermath_active", False).astype(bool)
    )
    return flag.rolling(3, min_periods=1).max().astype(bool)


def detect_second_leg_state(daily: Any) -> Any:
    """Detect Q072 R6 second-leg selloff state."""
    import pandas as pd

    close = daily["spx_close"]
    high_60d = close.rolling(60, min_periods=10).max()
    dd_60d = close / high_60d - 1.0

    bounce_flag = pd.Series(False, index=daily.index)
    for i in range(30, len(daily)):
        window = close.iloc[i - 30:i + 1]
        low_in_window = window.min()
        idx_low = window.idxmin()
        post_low = window[window.index > idx_low]
        if len(post_low) > 0 and (post_low.max() / low_in_window - 1.0) > 0.02:
            if close.iloc[i] <= low_in_window * 1.01:
                bounce_flag.iloc[i] = True

    eid = daily["episode_id_tight"].values
    days_in_ep: list[int] = []
    cur_ep = -1
    counter = 0
    for e in eid:
        if e != cur_ep:
            cur_ep = e
            counter = 0 if e >= 0 else -1
        else:
            if counter >= 0:
                counter += 1
        days_in_ep.append(counter)

    return (
        (dd_60d <= -0.08)
        & bounce_flag
        & (daily["vix"] >= 25.0)
        & (pd.Series(days_in_ep, index=daily.index) > 14)
    ).astype(bool)


def q072_replay_validation() -> dict:
    global _REPLAY_CACHE
    if _REPLAY_CACHE is not None:
        return dict(_REPLAY_CACHE)
    import pandas as pd

    daily = pd.read_csv(Q072_DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    stress = stress_episode_from_flags(daily)
    stress_target = daily["episode_id_tight"] >= 0
    stress_mismatch = int((stress != stress_target).sum())

    second_leg = detect_second_leg_state(daily)
    target_state = pd.read_csv(Q072_PORTFOLIO_STATE, parse_dates=["date"]).set_index("date")
    common = second_leg.index.intersection(target_state.index)
    second_mismatch = int((second_leg.loc[common] != target_state.loc[common, "second_leg"].astype(bool)).sum())

    allocator = pd.read_csv(Q072_ALLOCATOR_RESULTS)
    row = allocator[
        (allocator["allocator"].astype(str) == "FCFS")
        & (allocator["cap"].astype(str) == "default")
        & (allocator["split"].astype(str) == "full")
    ].iloc[0]
    ac8 = {
        "n_entered": int(row["n_entered"]),
        "total_pnl": float(row["total_pnl"]),
        "max_dd": float(row["max_dd"]),
        "pass": int(row["n_entered"]) == 872 and round(float(row["total_pnl"])) == 742193 and round(float(row["max_dd"])) == -174959,
    }
    result = {
        "stress_days": int(stress.sum()),
        "stress_mismatch_days": stress_mismatch,
        "stress_pass": stress_mismatch == 0,
        "second_leg_days": int(second_leg.sum()),
        "second_leg_mismatch_days": second_mismatch,
        "second_leg_pass": second_mismatch <= 2,
        "allocator_smoke": ac8,
    }
    _REPLAY_CACHE = dict(result)
    return result


def booster_signal_conditions(market_state: dict) -> dict:
    """Return Q074 B4 condition flags.

    `warmed` is a data-readiness flag. The B4 gate itself then requires:
    no stress, no second-leg, SPX above MA50, ddATH > -4%, VIX < 22,
    VIX 5d point-change <= +1.5, and IVP252 < 55.
    """
    status_ok = market_state.get("status") == "available"
    spx_close = _num(market_state.get("spx_close"))
    ma50 = _num(market_state.get("ma50"))
    ddath = _num(market_state.get("ddath"))
    vix = _num(market_state.get("vix"))
    vix_5d_change = _num(market_state.get("vix_5d_change"))
    ivp252 = _num(market_state.get("ivp252"))
    return {
        "warmed": bool(status_ok and spx_close is not None and ma50 is not None and ddath is not None and vix is not None and vix_5d_change is not None and ivp252 is not None),
        "no_stress": not bool(market_state.get("stress_episode_active")),
        "no_second_leg": not bool(market_state.get("second_leg_active")),
        "trend_ok": bool(spx_close is not None and ma50 is not None and spx_close > ma50),
        "ddath_ok": bool(ddath is not None and ddath > -0.04),
        "vix_ok": bool(vix is not None and vix < 22.0),
        "vix5d_ok": bool(vix_5d_change is not None and vix_5d_change <= 1.5),
        "ivp_ok": bool(ivp252 is not None and ivp252 < 55.0),
        "low_vix_escape_ok": bool(vix is not None and vix < 15.0),
        "ivp_gate_pass": bool((ivp252 is not None and ivp252 < 55.0) or (vix is not None and vix < 15.0)),
    }


def b4_benign_active(market_state: dict) -> bool:
    """Q074 B4 moderate 90% booster activation criteria."""
    cond = booster_signal_conditions(market_state)
    required = (
        "warmed",
        "no_stress",
        "no_second_leg",
        "trend_ok",
        "ddath_ok",
        "vix_ok",
        "vix5d_ok",
        "ivp_gate_pass",
    )
    return all(bool(cond.get(key)) for key in required)


def gate_f_only_active(market_state: dict) -> bool:
    """SPEC-105 v2 diagnostic: active only because low absolute VIX bypassed IVP."""
    cond = booster_signal_conditions(market_state)
    return bool(
        b4_benign_active(market_state)
        and not cond.get("ivp_ok")
        and cond.get("low_vix_escape_ok")
    )


def active_spx_cap(market_state: dict, mode: str | None = None) -> tuple[float, str]:
    """Return effective SPX cap and regime.

    Priority is second-leg > stress > booster > normal. In mandatory Stage 1
    shadow mode, booster is surfaced as `booster_shadow` but does not change the
    production cap above the SPEC-104 normal cap.
    """
    if bool(market_state.get("second_leg_active")):
        return CAP_SECOND_LEG_EPISODE, "second_leg"
    if bool(market_state.get("stress_episode_active")):
        return CAP_STRESS_EPISODE, "stress"
    if b4_benign_active(market_state):
        rollout = mode or booster_mode()
        if rollout == "active":
            return CAP_SPX_BENIGN_BOOSTER, "booster"
        if rollout == "disabled":
            return CAP_SPX_PM, "normal"
        return CAP_SPX_PM, "booster_shadow"
    return CAP_SPX_PM, "normal"


def _latest_market_stress() -> dict:
    """Best-effort live stress flags. Fails closed to unavailable, not optimistic."""
    try:
        import pandas as pd
        from schwab.client import get_vix_quote
        from signals.iv_rank import get_current_iv_snapshot
        from signals.vix_regime import fetch_vix_history

        spx_path = DATA_DIR / "market_cache" / "yahoo__GSPC__max__1d.pkl"
        if not spx_path.exists():
            return {"status": "unavailable", "reason": "missing SPX cache"}
        spx = pd.read_pickle(spx_path)
        close_full = spx["Close"].dropna()
        close = close_full.tail(90)
        if len(close_full) < 60:
            return {"status": "unavailable", "reason": "insufficient SPX history"}
        vix_quote = get_vix_quote()
        vix = _num(vix_quote.get("last")) or _num(vix_quote.get("close"))
        if vix is None:
            return {"status": "unavailable", "reason": "missing VIX quote"}
        last = float(close.iloc[-1])
        ma50 = float(close_full.rolling(50).mean().iloc[-1])
        ddath = last / float(close_full.max()) - 1.0
        dd_20d = last / float(close.tail(20).max()) - 1.0
        dd_60d = last / float(close.tail(60).max()) - 1.0
        stress_flag = vix >= 22.0 or dd_20d <= -0.04 or dd_60d <= -0.04
        vix_5d_change = None
        ivp252 = None
        try:
            vix_hist = fetch_vix_history(period="1y")
            if len(vix_hist) >= 6:
                vix_5d_change = float(vix) - float(vix_hist["vix"].iloc[-6])
            ivp252 = float(get_current_iv_snapshot(vix_hist, current_vix=float(vix)).ivp252)
        except Exception:
            pass
        return {
            "status": "available",
            "vix": round(vix, 2),
            "spx_close": round(last, 2),
            "ma50": round(ma50, 2),
            "ddath": round(ddath, 4),
            "dd_20d": round(dd_20d, 4),
            "dd_60d": round(dd_60d, 4),
            "vix_5d_change": round(vix_5d_change, 2) if vix_5d_change is not None else None,
            "ivp252": round(ivp252, 1) if ivp252 is not None else None,
            "stress_episode_active": bool(stress_flag),
            "second_leg_active": bool(dd_60d <= -0.08 and vix >= 25.0),
            "source": "live_cache_quote_best_effort",
        }
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}


def _pools_for_view(*, view: str, schwab_maint: float, etrade_maint: float,
                    schwab_nlv: float, etrade_nlv: float,
                    es_dollars: float, spx_is_short_vol: bool,
                    etrade_is_short_vol: bool) -> dict | None:
    """Compute pool BP % under a given account-view (all / schwab / etrade).

    R1 uses the account's full maintenance margin (not just SPX spread max-loss)
    per SPEC-103 §R1 "SPX 账户内所有持仓总和". Each view denominates against the
    NLV(s) selected by that view. /ES is an independent SPAN pool (separate
    broker) — it appears only in the 'all' view; in 'schwab'/'etrade' views the
    /ES row is N/A.
    """
    if view == "schwab":
        nlv = schwab_nlv
        spx_maint = schwab_maint
        es = 0.0
        short_vol = schwab_maint if spx_is_short_vol else 0.0
    elif view == "etrade":
        nlv = etrade_nlv
        spx_maint = etrade_maint
        es = 0.0
        short_vol = etrade_maint if etrade_is_short_vol else 0.0
    else:  # all
        nlv = schwab_nlv + etrade_nlv
        spx_maint = schwab_maint + etrade_maint
        es = es_dollars
        sv_schwab = schwab_maint if spx_is_short_vol else 0.0
        sv_etrade = etrade_maint if etrade_is_short_vol else 0.0
        short_vol = sv_schwab + sv_etrade + es  # /ES HV Ladder is short-vol

    if nlv <= 0:
        return None

    return {
        "view": view,
        "nlv_basis": round(nlv, 2),
        "spx_pm_bp_pct": round(spx_maint / nlv * 100.0, 2),
        "spx_pm_bp_dollars": round(spx_maint, 2),
        "es_span_bp_pct": round(es / nlv * 100.0, 2) if view == "all" else None,
        "es_span_bp_dollars": round(es, 2) if view == "all" else None,
        "combined_bp_pct": round((spx_maint + es) / nlv * 100.0, 2),
        "short_vol_bp_pct": round(short_vol / nlv * 100.0, 2),
    }


def current_governance_state() -> dict:
    """Build current read-only governance snapshot from existing portfolio surfaces.

    SPEC-103 口径 (refined 2026-05-16 per PM):
      R1 SPX PM pool BP uses account-level maintenance margin (Schwab maint or
      ETrade maint or sum, depending on view), not just SPX option spread
      max-loss. View filter (all / schwab / etrade) parallels Portfolio Snapshot
      view toggle.
    """
    errors: list[str] = []
    schwab_nlv = etrade_nlv = 0.0
    schwab_maint = etrade_maint = 0.0
    es_dollars = 0.0
    live_position = None
    etrade_position = None

    try:
        from web.portfolio_surface import es_stressed_span_payload, portfolio_summary_payload

        summary = portfolio_summary_payload()
        accounts = summary.get("account_breakdown") or {}
        schwab_nlv = _num(accounts.get("schwab_nlv")) or 0.0
        etrade_nlv = _num(accounts.get("etrade_nlv")) or 0.0
        schwab_maint = _num(accounts.get("schwab_maintenance_margin")) or 0.0
        etrade_maint = _num(accounts.get("etrade_maintenance_margin")) or 0.0

        rails = summary.get("rails") or {}
        live_position = (rails.get("spx_live") or {}).get("current_position")
        etrade_position = (rails.get("etrade_pm") or {}).get("current_position")
        # Use Schwab NLV as denominator (matches Margin Allocation display, not combined NLV)
        _spx_live_bp_dollars = _num((rails.get("spx_live") or {}).get("bp_usage", {}).get("bp_usage_dollars"))
        _spx_live_bp_pct = None  # computed after schwab_nlv is set

        es_payload = es_stressed_span_payload()
        if es_payload.get("has_es_live_position"):
            es_dollars = _num(es_payload.get("current_estimated_stressed_span")) or _num(es_payload.get("entry_static_span")) or 0.0
    except Exception as exc:
        errors.append(str(exc))
        _spx_live_bp_dollars = None

    # Denominate SPX live BP against Schwab NLV (same basis as Margin Allocation display)
    _spx_live_bp_pct = (
        round(_spx_live_bp_dollars / schwab_nlv * 100.0, 2)
        if _spx_live_bp_dollars is not None and schwab_nlv > 0
        else None
    )

    spx_is_sv = is_short_vol_candidate({
        "strategy_key": (live_position or {}).get("strategy_key"),
        "strategy": (live_position or {}).get("strategy"),
    })
    etrade_is_sv = is_short_vol_candidate({
        "strategy_key": (etrade_position or {}).get("strategy_key"),
        "strategy": (etrade_position or {}).get("strategy"),
    }) if etrade_position else False

    pools_by_view: dict[str, dict | None] = {}
    for v in ("all", "schwab", "etrade"):
        pools_by_view[v] = _pools_for_view(
            view=v,
            schwab_maint=schwab_maint,
            etrade_maint=etrade_maint,
            schwab_nlv=schwab_nlv,
            etrade_nlv=etrade_nlv,
            es_dollars=es_dollars,
            spx_is_short_vol=spx_is_sv,
            etrade_is_short_vol=etrade_is_sv,
        )

    market = _latest_market_stress()
    stress_active = bool(market.get("stress_episode_active")) if market.get("status") == "available" else False
    second_leg = bool(market.get("second_leg_active")) if market.get("status") == "available" else False
    booster_conditions = booster_signal_conditions(market)
    booster_active = b4_benign_active(market)
    cap_pct, cap_regime = active_spx_cap(market)

    # Back-compat: 'pools' = 'all' view (existing consumers don't break).
    pools_default = pools_by_view.get("all") or {
        "spx_pm_bp_pct": 0.0,
        "spx_pm_bp_dollars": 0.0,
        "es_span_bp_pct": 0.0,
        "es_span_bp_dollars": 0.0,
        "combined_bp_pct": 0.0,
        "short_vol_bp_pct": 0.0,
    }
    basis = (pools_default.get("nlv_basis") or 0.0) or COMBINED_NLV

    return {
        "timestamp": _iso_now(),
        "status": "available" if not errors else "partial",
        "errors": errors,
        "basis_dollars": round(basis, 2),
        "pools": pools_default,
        "pools_by_view": pools_by_view,
        "caps": governance_caps(stress_active, second_leg, booster_active, cap_pct, cap_regime),
        "stress_episode_active": stress_active,
        "second_leg_active": second_leg,
        "booster_active": booster_active,
        "booster_mode": booster_mode(),
        "booster_signal_conditions": booster_conditions,
        "active_spx_pm_cap_pct": cap_pct,
        "active_spx_pm_cap_regime": cap_regime,
        "market": market,
        "active_overrides": active_overrides(),
        "spx_live_bp_pct": round(_spx_live_bp_pct, 2) if _spx_live_bp_pct is not None else None,
    }


def governance_caps(
    stress_episode_active: bool = False,
    second_leg_active: bool = False,
    booster_active: bool = False,
    active_cap_pct: float | None = None,
    active_regime: str | None = None,
) -> dict:
    if active_cap_pct is None or active_regime is None:
        proxy = {
            "status": "available",
            "stress_episode_active": stress_episode_active,
            "second_leg_active": second_leg_active,
            "spx_close": 1.0 if booster_active else None,
            "ma50": 0.5 if booster_active else None,
            "ddath": 0.0 if booster_active else None,
            "vix": 10.0 if booster_active else None,
            "vix_5d_change": 0.0 if booster_active else None,
            "ivp252": 10.0 if booster_active else None,
        }
        active_cap_pct, active_regime = active_spx_cap(proxy)
    return {
        "R1_spx_pm_pool_cap_pct": CAP_SPX_PM,
        "R2_es_span_cap_pct": CAP_ES_SPAN,
        "R3_combined_cap_pct": CAP_COMBINED,
        "R4_short_vol_cap_pct": CAP_SHORT_VOL,
        # Effective cap for current regime (used for live BP display)
        "active_spx_pm_cap_pct": active_cap_pct,
        "active_spx_pm_cap_regime": active_regime,
        "booster_mode": booster_mode(),
        "booster_active": booster_active,
        "booster_shadow_cap_pct": CAP_SPX_BENIGN_BOOSTER if booster_active else None,
        "booster_production_enabled": booster_mode() == "active",
        "CAP_SPX_BENIGN_BOOSTER": CAP_SPX_BENIGN_BOOSTER,
        "R5_spx_pm_stress_cap_pct": CAP_STRESS_EPISODE if stress_episode_active else CAP_SPX_PM,
        # Fixed stress threshold — always CAP_STRESS_EPISODE regardless of current regime
        "R5_stress_threshold_pct": CAP_STRESS_EPISODE,
        "R6_second_leg_spx_cap_pct": CAP_SECOND_LEG_EPISODE,
        "R6_second_leg_short_vol_block": True,
    }


def is_short_vol_candidate(candidate: dict) -> bool:
    text = " ".join(str(candidate.get(k, "")) for k in ("strategy_key", "strategy", "sleeve", "underlying")).lower()
    if any(token in text for token in LONG_GAMMA_TEXT):
        return False
    key = str(candidate.get("strategy_key") or "").lower()
    if key in SHORT_VOL_STRATEGIES:
        return True
    return any(token in text for token in SHORT_VOL_TEXT)


def is_risk_reducing(candidate: dict) -> bool:
    text = " ".join(str(candidate.get(k, "")) for k in ("action", "operation", "entry_type", "note")).lower()
    return any(token in text for token in ("close", "exit", "roll", "risk-reducing", "reduce"))


def _candidate_pool(candidate: dict) -> str:
    text = " ".join(str(candidate.get(k, "")) for k in ("strategy_key", "strategy", "sleeve", "underlying", "pool")).upper()
    if "/ES" in text or "ES_SPAN" in text or "HV_LADDER" in text:
        return "ES_SPAN"
    return "SPX_PM"


def _candidate_requested_bp(candidate: dict) -> float:
    for key in ("requested_bp", "requested_bp_dollars", "bp_dollars", "bp_usage_dollars"):
        value = _num(candidate.get(key))
        if value is not None:
            return max(0.0, value)
    preview = candidate.get("bp_preview") if isinstance(candidate.get("bp_preview"), dict) else {}
    value = _num(preview.get("bp_usage_dollars"))
    if value is not None:
        return max(0.0, value)
    short = _num(candidate.get("short_strike"))
    long = _num(candidate.get("long_strike"))
    contracts = _num(candidate.get("contracts")) or 1.0
    if short is not None and long is not None:
        return abs(short - long) * 100.0 * contracts
    return 0.0


@dataclass
class GovernanceDecision:
    accepted: bool
    rule: str | None
    reason: str
    candidate: dict
    state: dict
    requested_bp_dollars: float
    requested_bp_pct: float
    timestamp: str

    def as_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "accepted": self.accepted,
            "rule": self.rule,
            "reason": self.reason,
            "candidate": self.candidate,
            "state": self.state,
            "requested_bp_dollars": round(self.requested_bp_dollars, 2),
            "requested_bp_pct": round(self.requested_bp_pct, 2),
            "counterfactual": {
                "forward_spx_return_5d": None,
                "forward_spx_return_10d": None,
                "forward_spx_return_20d": None,
                "estimated_pnl_if_entered": None,
                "status": "pending_future_observation",
            },
            "estimated_bp_saved": round(self.requested_bp_dollars, 2) if not self.accepted else 0.0,
            "similar_entry_later": None,
        }


def evaluate_candidate(candidate: dict, state: dict | None = None) -> GovernanceDecision:
    state = state or current_governance_state()
    pool = _candidate_pool(candidate)
    requested_bp = _candidate_requested_bp(candidate)
    basis = _num(state.get("basis_dollars")) or COMBINED_NLV
    requested_pct = requested_bp / basis * 100.0 if basis else 0.0
    pools = state.get("pools") or {}
    is_short = is_short_vol_candidate(candidate)
    caps = state.get("caps") if isinstance(state.get("caps"), dict) else governance_caps(
        bool(state.get("stress_episode_active")),
        bool(state.get("second_leg_active")),
        bool(state.get("booster_active")),
        _num(state.get("active_spx_pm_cap_pct")),
        state.get("active_spx_pm_cap_regime"),
    )
    normal_spx_cap = _num(caps.get("active_spx_pm_cap_pct")) or CAP_SPX_PM
    accepted = True
    rule = None
    reason = "accepted"

    if is_risk_reducing(candidate):
        return GovernanceDecision(True, None, "risk-reducing exit/roll allowed", candidate, state, requested_bp, requested_pct, _iso_now())

    spx_after = (_num(pools.get("spx_pm_bp_pct")) or 0.0) + (requested_pct if pool == "SPX_PM" else 0.0)
    es_after = (_num(pools.get("es_span_bp_pct")) or 0.0) + (requested_pct if pool == "ES_SPAN" else 0.0)
    combined_after = (_num(pools.get("combined_bp_pct")) or 0.0) + requested_pct
    short_vol_after = (_num(pools.get("short_vol_bp_pct")) or 0.0) + (requested_pct if is_short else 0.0)

    checks = [
        ("R2", pool == "ES_SPAN" and es_after > CAP_ES_SPAN, f"Projected /ES SPAN BP {es_after:.1f}% exceeds {CAP_ES_SPAN:.1f}% cap"),
        ("R3", combined_after > CAP_COMBINED, f"Projected combined BP {combined_after:.1f}% exceeds {CAP_COMBINED:.1f}% cap"),
        ("R4", is_short and short_vol_after > CAP_SHORT_VOL, f"Projected short-vol BP {short_vol_after:.1f}% exceeds {CAP_SHORT_VOL:.1f}% cap"),
        ("R6", bool(state.get("second_leg_active")) and pool == "SPX_PM" and spx_after > CAP_SECOND_LEG_EPISODE, f"Second-leg SPX cap {CAP_SECOND_LEG_EPISODE:.1f}% would be exceeded"),
        ("R6", bool(state.get("second_leg_active")) and is_short, "Second-leg state blocks new short-vol entries"),
        ("R5", bool(state.get("stress_episode_active")) and pool == "SPX_PM" and spx_after > CAP_STRESS_EPISODE, f"Stress episode SPX cap {CAP_STRESS_EPISODE:.1f}% would be exceeded"),
        ("R1", pool == "SPX_PM" and spx_after > normal_spx_cap, f"Projected SPX PM BP {spx_after:.1f}% exceeds {normal_spx_cap:.1f}% active cap"),
    ]
    for candidate_rule, triggered, candidate_reason in checks:
        if triggered and not is_rule_paused(candidate_rule):
            accepted = False
            rule = candidate_rule
            reason = candidate_reason
            break
    return GovernanceDecision(accepted, rule, reason, candidate, state, requested_bp, requested_pct, _iso_now())


def log_decision(decision: GovernanceDecision, path: Path | None = None) -> dict:
    payload = decision.as_dict()
    _append_jsonl(path or DECISION_LOG_PATH, payload)
    return payload


def _send_alert(text: str) -> bool:
    try:
        from notify.event_push import _send

        return _send(text)
    except Exception:
        return False


def maybe_alert_decision(decision: GovernanceDecision) -> bool:
    if decision.accepted or decision.rule != "R6":
        return False
    c = decision.candidate
    return _send_alert(
        "⚠️ <b>Sleeve governance block</b>\n"
        f"Rule: <code>{decision.rule}</code>\n"
        f"Sleeve: <code>{c.get('sleeve') or c.get('strategy_key') or c.get('strategy') or 'unknown'}</code>\n"
        f"Reason: {decision.reason}"
    )


def _cap_regime_for_alert(state: dict | None) -> str:
    if not state:
        return "unknown"
    return str(state.get("active_spx_pm_cap_regime") or (state.get("caps") or {}).get("active_spx_pm_cap_regime") or "normal")


def _maybe_alert_booster_transition(previous: dict | None, current: dict) -> bool:
    if previous is None:
        return False
    prev = _cap_regime_for_alert(previous)
    now = _cap_regime_for_alert(current)
    if prev == now:
        return False
    booster_related = prev.startswith("booster") or now.startswith("booster")
    if not booster_related:
        return False
    cap = current.get("active_spx_pm_cap_pct") or (current.get("caps") or {}).get("active_spx_pm_cap_pct")
    shadow_cap = (current.get("caps") or {}).get("booster_shadow_cap_pct")
    return _send_alert(
        "🧪 <b>Q074 Booster shadow transition</b>\n"
        f"State: <code>{prev}</code> → <code>{now}</code>\n"
        f"Effective SPX cap now: <code>{cap}%</code>\n"
        f"Would-be booster cap: <code>{shadow_cap or CAP_SPX_BENIGN_BOOSTER}%</code>\n"
        "Stage 1 shadow only — production cap remains governed by SPEC-104 unless PM flips booster active."
    )


def record_state_snapshot(send_alerts: bool = False) -> dict:
    state = current_governance_state()
    previous = None
    if RUNTIME_STATE_PATH.exists():
        try:
            previous = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            previous = None
    _append_jsonl(STATE_LOG_PATH, state)
    _append_jsonl(BOOSTER_SHADOW_LOG_PATH, {
        "timestamp": state.get("timestamp"),
        "mode": state.get("booster_mode"),
        "booster_active": state.get("booster_active"),
        "active_spx_pm_cap_regime": state.get("active_spx_pm_cap_regime"),
        "active_spx_pm_cap_pct": state.get("active_spx_pm_cap_pct"),
        "booster_shadow_cap_pct": (state.get("caps") or {}).get("booster_shadow_cap_pct"),
        "gate_f_only": gate_f_only_active(state.get("market") or {}),
        "conditions": state.get("booster_signal_conditions"),
        "market": state.get("market"),
    })
    _write_json(RUNTIME_STATE_PATH, state)
    if send_alerts and previous is not None:
        _maybe_alert_booster_transition(previous, state)
        prev_second = bool(previous.get("second_leg_active"))
        now_second = bool(state.get("second_leg_active"))
        if not prev_second and now_second:
            _send_alert("⚠️ <b>Sleeve governance</b> second-leg state ACTIVE — new short-vol entries blocked.")
        elif prev_second and not now_second:
            _send_alert("✅ <b>Sleeve governance</b> second-leg state cleared — R6 block inactive.")
    return state


def governance_dashboard_payload() -> dict:
    state = current_governance_state()
    decisions = _read_jsonl(DECISION_LOG_PATH, limit=200)
    blocked = [row for row in decisions if row.get("accepted") is False]
    recent_blocked = blocked[-20:]
    since30 = _et_now() - timedelta(days=30)
    since90 = _et_now() - timedelta(days=90)
    state_rows = _read_jsonl(STATE_LOG_PATH, limit=500)

    def _after(row: dict, cutoff: datetime) -> bool:
        try:
            ts = datetime.fromisoformat(str(row.get("timestamp")))
            if ts.tzinfo is None and cutoff.tzinfo is not None:
                ts = ts.replace(tzinfo=cutoff.tzinfo)
            return ts >= cutoff
        except ValueError:
            return False

    stress30 = sum(1 for row in state_rows if _after(row, since30) and row.get("stress_episode_active"))
    second90 = sum(1 for row in state_rows if _after(row, since90) and row.get("second_leg_active"))
    r5_blocks_90 = sum(1 for row in blocked if _after(row, since90) and row.get("rule") == "R5")
    r6_blocks_90 = sum(1 for row in blocked if _after(row, since90) and row.get("rule") == "R6")
    return {
        "surface": "sleeve_governance",
        "semantics": "read-only portfolio-level sleeve stress governance; production entry gate logs decisions",
        "state": state,
        "recent_blocked_candidates": recent_blocked,
        "recent_counts": {
            "blocked_30d": sum(1 for row in blocked if _after(row, since30)),
            "stress_episode_days_30d": stress30,
            "second_leg_days_90d": second90,
        },
        "monitors": {
            "spx_normal_to_stress_transition_loss": {
                "status": "pending_live_data",
                "description": "Track SPX sleeve loss during normal-to-stress transitions; no realized transition ledger yet.",
            },
            "r5_r6_frequency": {
                "status": "ok",
                "r5_blocks_90d": r5_blocks_90,
                "r6_blocks_90d": r6_blocks_90,
            },
            "blocked_hv_signals": {
                "status": "research_only",
                "description": "HV Ladder production allocation is 0% per SPEC-104; paper signals are not executable.",
            },
        },
        "replay_validation": q072_replay_validation(),
    }


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage SPEC-103 sleeve governance overrides")
    parser.add_argument("--pause", action="store_true", help="pause a governance rule")
    parser.add_argument("--rule", default="", help="rule to pause, e.g. R6")
    parser.add_argument("--duration", default="", help="duration, e.g. 1d, 6h, 30m")
    parser.add_argument("--reason", default="manual override")
    args = parser.parse_args(argv)
    if args.pause:
        if not args.rule or not args.duration:
            parser.error("--pause requires --rule and --duration")
        payload = pause_rule(args.rule, args.duration, args.reason)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
