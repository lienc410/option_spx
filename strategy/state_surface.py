"""SPEC-141 F1 — 统一状态面（S1，shadow 语义，纯只读聚合）.

把散落在 5 个模块的市场状态收拢为一个状态面：两轴（vol / structure）+
事件灯（DIP·AFTERMATH·BACKWARDATION·SECOND-LEG）+ 生存 veto + 弹药 + 今日路由。

铁律（SPEC-141 策略/信号逻辑节）：
  * 零路由/参数/风险语义变更——selector、executor、governance 一行不改、
    不 import 本模块（AC-141-4 shadow invariant，方向为本模块 import 它们）。
  * 不重新实现任何算法：RANGE 判定复用 SPEC-094.4 因果贪婪分段
    （production.q042_executor._find_chop_episodes / _classify_trigger_type，
    尾窗语义同 094.4）；分型/弹药路由复用 ex._ammo_advisory；sizing 复用
    strategy.q042_sizing.compute_sizing；阈值全部 import 源常量。
  * 失败语义：任一子源失败 → 该字段 {"status": "n/a"}，不抛不假造
    （fail-soft，逐字段）。

F2：`append_daily_log()` 一天一行落 data/state_surface.jsonl（幂等）；
首跑用日线缓存回填过去 90 TD 的 (vol_state, structure_state) 简版
（回填行打 backfill:true）。挂载点：scripts/daily_snapshot.py 日度 job。

CLI:  python -m strategy.state_surface [--print] [--log]
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = None

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_SURFACE_LOG = REPO_ROOT / "data" / "state_surface.jsonl"
BACKFILL_TRADING_DAYS = 90

# 引擎徽章词汇（SPEC-141 边界约束 1，PM 2026-07-13）：只有 ON / STANDBY 两词。
# Q042 armed/disarmed 是行内字段，不是徽章；veto 灯用点色不用词。
BADGE_ON = "ON"
BADGE_STANDBY = "STANDBY"

# 引擎-结构归属（doc/unified_state_redesign_2026-07-13.md §4 矩阵列的 code 化，
# 仅供 live 徽章显示。单一归属（Quant 裁决 2026-07-13，P1 依据：BPS delta
# 份额 59% / 截面 R²=0.94 = 方向决定胜负 → Trend 引擎）：Premium = IC 家族
# （+V3-A aftermath 变体走 iron_condor_hv key）；Trend = BCD/BPS/BCS 家族。
# doc §4 矩阵同步修正。display-only。
ENGINE_STRUCTURES: dict[str, frozenset[str]] = {
    "premium": frozenset({
        "iron_condor", "iron_condor_hv",
    }),
    "trend": frozenset({
        "bull_call_diagonal",
        "bull_put_spread", "bull_put_spread_hv",
        "bear_call_spread", "bear_call_spread_hv",
    }),
}


def _now_et() -> datetime:
    return datetime.now(_ET) if _ET is not None else datetime.now()


def _today_str() -> str:
    return _now_et().date().isoformat()


def _num(v: Any) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _guard(builder: Callable[[], dict]) -> dict:
    """逐字段 fail-soft：子源异常 → {"status": "n/a", "error": ...}（不抛不假造）。"""
    try:
        d = builder()
        if isinstance(d, dict) and "status" not in d:
            d["status"] = "ok"
        return d
    except Exception as exc:  # noqa: BLE001 — fail-soft by spec
        return {"status": "n/a", "error": f"{type(exc).__name__}: {exc}"[:200]}


# ── 量表几何（AC-141-6 单源计算函数，模板 JS 只消费不重算） ────────────────────

def bar_geometry(value: Any, scale_max: float, cap: Optional[float] = None) -> dict:
    """绝对刻度条几何：width_pct = value / scale_max × 100（同值必同长）。

    所有 BP 条共用绝对 0-100% 刻度（scale_max=100）；cash 条 scale_max=liquid。
    cap 以刻度线标注在各自绝对位置（cap_pos_pct）。禁止"利用率相对 cap"的
    变长条（SPEC-141 边界约束 2）。
    """
    m = float(scale_max)
    if m <= 0:
        raise ValueError("scale_max must be > 0")
    v = _num(value)
    if v is None:
        raise ValueError("value is not a number")
    geom = {
        "value": round(v, 2),
        "scale_max": round(m, 2),
        "width_pct": round(max(0.0, min(100.0, v / m * 100.0)), 2),
    }
    if cap is not None:
        c = float(cap)
        geom["cap"] = round(c, 2)
        geom["cap_pos_pct"] = round(max(0.0, min(100.0, c / m * 100.0)), 2)
    return geom


# ── Vol 轴 ─────────────────────────────────────────────────────────────────────

def _vol_state(vix: float) -> str:
    """CALM(<15) / NORMAL(15-22) / HIGH(22-35) / EXTREME(≥35)。

    阈值 import 源常量：15/22 = signals.vix_regime（LOW_VOL/HIGH_VOL），
    35 = strategy.selector.DEFAULT_PARAMS.extreme_vix（SPEC-118.1 单源）。
    """
    from signals.vix_regime import HIGH_VOL_THRESHOLD, LOW_VOL_THRESHOLD
    from strategy.selector import DEFAULT_PARAMS

    if vix < LOW_VOL_THRESHOLD:
        return "CALM"
    if vix < HIGH_VOL_THRESHOLD:
        return "NORMAL"
    if vix < DEFAULT_PARAMS.extreme_vix:
        return "HIGH"
    return "EXTREME"


def _vol_axis(vix_snap) -> dict:
    from signals.vix_regime import HIGH_VOL_THRESHOLD, LOW_VOL_THRESHOLD
    from strategy.selector import DEFAULT_PARAMS

    vix = float(vix_snap.vix)
    state = _vol_state(vix)
    nxt = {
        "CALM": LOW_VOL_THRESHOLD,
        "NORMAL": HIGH_VOL_THRESHOLD,
        "HIGH": DEFAULT_PARAMS.extreme_vix,
        "EXTREME": None,
    }[state]
    return {
        "state": state,
        "vix": round(vix, 2),
        "dist_next": round(nxt - vix, 2) if nxt is not None else None,
        "next_threshold": nxt,
        "thresholds": [LOW_VOL_THRESHOLD, HIGH_VOL_THRESHOLD, DEFAULT_PARAMS.extreme_vix],
    }


# ── Structure 轴（RANGE = SPEC-094.4 因果分段；尾窗同 094.4） ───────────────────

def _range_segment(closes, asof: str) -> Optional[dict]:
    """截断到 asof 的 Close 序列上跑 094.4 同款贪婪分段，判 in-episode-now。

    分段器与尾窗常量直接 import production.q042_executor（_find_chop_episodes /
    _EPISODE_* LOCKED by SPEC-094.4）——不内联不复制；membership 语义与
    ex._classify_trigger_type 完全一致（段末端距 asof ≤7 日历日）。若 094.4
    分类器修订，此处自动跟随（同步义务：本函数只允许调用 ex 的 helper）。
    """
    import pandas as pd

    import production.q042_executor as ex

    sig = pd.Timestamp(asof)
    trail = closes.loc[ex._EPISODE_SCAN_START:sig]
    if len(trail) < ex._EPISODE_MIN_LEN:
        raise ValueError("insufficient trailing closes for structure axis")
    if (sig - trail.index.max()).days > ex._EPISODE_GAP_CAL_DAYS:
        raise ValueError("trailing closes too stale for structure axis")
    dates = trail.index
    episodes = ex._find_chop_episodes(trail.values)
    live = [(s, e) for s, e in episodes
            if (sig - dates[e]).days <= ex._EPISODE_GAP_CAL_DAYS]
    if not live:
        return None
    s, e = live[-1]
    seg = trail.values[s:e + 1]
    return {
        # 段起点到最新收盘的交易日数（in-episode-now 口径，含当日）
        "episode_day": int(len(trail) - s),
        "band_lo": round(float(min(seg)), 2),
        "band_hi": round(float(max(seg)), 2),
        "episode_start": dates[s].strftime("%Y-%m-%d"),
    }


def _trend_to_structure(signal: str) -> str:
    """非 RANGE 时按 trend 信号方向；NEUTRAL 非 episode → MIXED（spec F1 表）。"""
    return {"BULLISH": "TREND_UP", "BEARISH": "TREND_DOWN"}.get(str(signal), "MIXED")


def _structure_axis_from_closes(closes, asof: str,
                                trend_signal: Optional[str] = None) -> dict:
    """结构轴：RANGE（094.4 因果分段）优先；否则 trend 方向 / MIXED。

    trend_signal 缺省时用截断序列的 MA50 gap 现算（阈值 import
    signals.trend.TREND_THRESHOLD，回填简版路径；live 路径传入
    signals.trend 快照的 signal，两者同公式同阈值）。
    """
    seg = _range_segment(closes, asof)
    if seg is not None:
        return {"state": "RANGE", **seg}
    if trend_signal is None:
        import pandas as pd

        from signals.trend import MA_LONG, TREND_THRESHOLD
        trail = closes.loc[:pd.Timestamp(asof)]
        if len(trail) < MA_LONG:
            raise ValueError("insufficient closes for MA50 trend fallback")
        ma50 = float(trail.iloc[-MA_LONG:].mean())
        gap = float(trail.iloc[-1]) / ma50 - 1.0
        if gap > TREND_THRESHOLD:
            trend_signal = "BULLISH"
        elif gap < -TREND_THRESHOLD:
            trend_signal = "BEARISH"
        else:
            trend_signal = "NEUTRAL"
    return {"state": _trend_to_structure(trend_signal),
            "episode_day": None, "band_lo": None, "band_hi": None}


# ── 状态面本体 ──────────────────────────────────────────────────────────────────

def _read_governance_runtime() -> dict:
    """sleeve governance runtime 快照（record_state_snapshot 日度落盘）只读。"""
    from strategy.sleeve_governance import RUNTIME_STATE_PATH

    d = json.loads(Path(RUNTIME_STATE_PATH).read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("governance runtime malformed")
    return d


def _engine_badges(strategy_key: Optional[str], position_action: Optional[str],
                   dip_active: Any, armed_a: Any) -> dict:
    """ON = 今日被路由/可入场；STANDBY = 今日未被路由（词汇仅此两词，约束 1）。

    Convexity 是事件驱动引擎：DIP 触发条件当日成立且 sleeve A armed → ON。
    """
    routed_open = bool(strategy_key) and strategy_key != "reduce_wait" \
        and str(position_action or "").upper() == "OPEN"
    return {
        "premium": BADGE_ON if routed_open and strategy_key in ENGINE_STRUCTURES["premium"] else BADGE_STANDBY,
        "trend": BADGE_ON if routed_open and strategy_key in ENGINE_STRUCTURES["trend"] else BADGE_STANDBY,
        "convexity": BADGE_ON if (dip_active is True and bool(armed_a)) else BADGE_STANDBY,
    }


def compute_state_surface(today: Optional[str] = None) -> dict:
    """统一状态面（纯只读聚合，全部复用现役信号）。绝不 raise：逐字段 fail-soft。"""
    today = today or _today_str()

    # ── 共享子源（各自独立 guard，互不拖垮） ──────────────────────────────────
    vix_snap = vix_err = None
    spx_df = None
    try:
        from signals.vix_regime import fetch_vix_history, get_current_snapshot
        vix_snap = get_current_snapshot(fetch_vix_history(period="2y"))
    except Exception as exc:  # noqa: BLE001
        vix_err = exc

    trend_snap = trend_err = None
    try:
        from signals.trend import fetch_spx_history, get_current_trend
        spx_df = fetch_spx_history(period="2y")
        trend_snap = get_current_trend(spx_df)
    except Exception as exc:  # noqa: BLE001
        trend_err = exc

    closes = closes_err = None
    try:
        import production.q042_executor as ex
        closes = ex._fetch_spx_close_series(today)
    except Exception as exc:  # noqa: BLE001
        closes_err = exc

    q042_snap = q042_err = None
    try:
        from signals.q042_trigger import get_current_q042_snapshot
        q042_snap = get_current_q042_snapshot(spx_df)
    except Exception as exc:  # noqa: BLE001
        q042_err = exc

    gov = gov_err = None
    try:
        gov = _read_governance_runtime()
    except Exception as exc:  # noqa: BLE001
        gov_err = exc

    liquid = cash_err = None
    try:
        from strategy.cash_budget_governance import get_current_liquid_cash
        cash_data = get_current_liquid_cash()
        if cash_data.get("source") == "unavailable":
            raise ValueError(f"liquid cash unavailable: {cash_data.get('error')}")
        liquid = _num(cash_data.get("total"))
    except Exception as exc:  # noqa: BLE001
        cash_err = exc

    debit = debit_err = None
    try:
        from strategy.cash_budget_governance import get_open_debit_total_usd
        debit_data = get_open_debit_total_usd()
        if debit_data.get("error"):
            # committed 侧读失败返回 total=0 —— 不得当 0 假造（SPEC-138 F6 同姿态）
            raise ValueError(f"open debit read failed: {debit_data.get('error')}")
        debit = _num(debit_data.get("total"))
    except Exception as exc:  # noqa: BLE001
        debit_err = exc

    rec = rec_err = None
    try:
        from signals.vix_regime import fetch_vix_history as _fvh
        from strategy.selector import get_recommendation
        rec = get_recommendation(vix_df=_fvh(period="2y"), spx_df=spx_df)
    except Exception as exc:  # noqa: BLE001
        rec_err = exc

    def _need(obj, err, name):
        if obj is None:
            raise RuntimeError(f"{name} unavailable: {err}")
        return obj

    # ── vol_axis ──────────────────────────────────────────────────────────────
    vol_axis = _guard(lambda: _vol_axis(_need(vix_snap, vix_err, "vix snapshot")))

    # ── structure_axis（RANGE=094.4 因果分段；非 RANGE=trend 方向） ───────────
    def _structure() -> dict:
        c = _need(closes, closes_err, "spx close series")
        sig = None
        if trend_snap is not None:
            sig = getattr(trend_snap.signal, "value", str(trend_snap.signal))
        return _structure_axis_from_closes(c, today, trend_signal=sig)
    structure_axis = _guard(_structure)

    # ── trend_signal（hero 单列，与 structure 轴并存） ────────────────────────
    def _trend() -> dict:
        t = _need(trend_snap, trend_err, "trend snapshot")
        return {
            "signal": getattr(t.signal, "value", str(t.signal)),
            "spx": round(float(t.spx), 2),
            "ma50": round(float(t.ma50), 2),
            "ma_gap_pct": round(float(t.ma_gap_pct) * 100.0, 2),
            "above_200": bool(t.above_200),
        }
    trend_signal = _guard(_trend)

    # ── events（DIP / AFTERMATH / BACKWARDATION / SECOND-LEG，各自 fail-soft）─
    def _dip() -> dict:
        from signals.q042_trigger import _DD4_THRESHOLD
        q = _need(q042_snap, q042_err, "q042 snapshot")
        armed_a = bool(q.sleeve_a.armed)
        armed_b = bool(q.sleeve_b.armed)
        base = {
            "trigger_pp": round(_DD4_THRESHOLD * 100.0, 2),
            "sleeve_a": {"armed": armed_a,
                         "active_position": q.sleeve_a.active_position_id is not None},
            "sleeve_b": {"armed": armed_b,
                         "in_watching": bool(q.sleeve_b.in_watching),
                         "active_position": q.sleeve_b.active_position_id is not None},
        }
        if bool(getattr(q, "ath_degraded", False)):
            # SPEC-094.2 F7 惯例：state ATH 缺失时 ddath 是 0 填充，不得当真值。
            return {"status": "n/a", "error": "ath_degraded — state ATH missing/0",
                    **base}
        ddath = float(q.ddath)
        type_now = None
        if closes is not None:
            try:
                import production.q042_executor as ex
                type_now = ex._classify_trigger_type(closes, today)
            except Exception:  # noqa: BLE001
                type_now = None
        return {
            **base,
            "active": bool(ddath <= _DD4_THRESHOLD),
            "ddath_pct": round(ddath * 100.0, 2),
            "ath": round(float(q.ath_running_max), 2),
            "spx_close": round(float(q.spx_close), 2),
            # 距触发还差多少个百分点（已触发为 0）
            "dist_pp": round(max(0.0, (ddath - _DD4_THRESHOLD) * 100.0), 2),
            "type_if_now": type_now,
            # DIP 灯带距离条几何（0 → |trigger|，绝对刻度，AC-6 同源函数）
            "gauge": bar_geometry(min(abs(min(ddath, 0.0)) * 100.0,
                                      abs(_DD4_THRESHOLD) * 100.0),
                                  abs(_DD4_THRESHOLD) * 100.0),
        }

    def _aftermath() -> dict:
        from strategy.selector import is_aftermath
        v = _need(vix_snap, vix_err, "vix snapshot")
        return {
            "active": bool(is_aftermath(v)),
            "peak10d": round(float(v.vix_peak_10d), 2) if v.vix_peak_10d is not None else None,
        }

    def _backwardation() -> dict:
        v = _need(vix_snap, vix_err, "vix snapshot")
        return {
            "active": bool(v.backwardation),
            "vix3m": round(float(v.vix3m), 2) if v.vix3m is not None else None,
        }

    def _second_leg() -> dict:
        g = _need(gov, gov_err, "governance runtime")
        return {"active": bool(g.get("second_leg_active")),
                "stress_episode_active": bool(g.get("stress_episode_active")),
                "runtime_ts": g.get("timestamp")}

    events = {
        "dip": _guard(_dip),
        "aftermath": _guard(_aftermath),
        "backwardation": _guard(_backwardation),
        "second_leg": _guard(_second_leg),
    }

    # ── veto（Layer 0 生存否决——governance runtime + cash_budget） ────────────
    def _veto() -> dict:
        from strategy.cash_budget_governance import CASH_FLOOR_USD
        from strategy.selector import DEFAULT_PARAMS

        out: dict = {"detail": {}}
        d = out["detail"]

        if vix_snap is not None:
            d["vix"] = round(float(vix_snap.vix), 2)
            d["extreme_vix"] = DEFAULT_PARAMS.extreme_vix
            out["extreme_ok"] = bool(float(vix_snap.vix) < DEFAULT_PARAMS.extreme_vix)
        else:
            out["extreme_ok"] = "n/a"

        if gov is not None:
            pools = gov.get("pools") or {}
            caps = gov.get("caps") or {}
            out["second_leg_ok"] = not bool(gov.get("second_leg_active"))
            d["second_leg_active"] = bool(gov.get("second_leg_active"))
            d["stress_episode_active"] = bool(gov.get("stress_episode_active"))
            d["cap_regime"] = gov.get("active_spx_pm_cap_regime")
            d["runtime_ts"] = gov.get("timestamp")
            d["pools"] = {k: _num(pools.get(k)) for k in
                          ("spx_pm_bp_pct", "short_vol_bp_pct",
                           "combined_bp_pct", "es_span_bp_pct")}
            d["caps"] = {
                "active_spx_pm_cap_pct": _num(caps.get("active_spx_pm_cap_pct")),
                "R2_es_span_cap_pct": _num(caps.get("R2_es_span_cap_pct")),
                "R3_combined_cap_pct": _num(caps.get("R3_combined_cap_pct")),
                "R4_short_vol_cap_pct": _num(caps.get("R4_short_vol_cap_pct")),
            }
            checks = [
                (d["pools"]["spx_pm_bp_pct"], d["caps"]["active_spx_pm_cap_pct"]),
                (d["pools"]["short_vol_bp_pct"], d["caps"]["R4_short_vol_cap_pct"]),
                (d["pools"]["combined_bp_pct"], d["caps"]["R3_combined_cap_pct"]),
                (d["pools"]["es_span_bp_pct"], d["caps"]["R2_es_span_cap_pct"]),
            ]
            if any(v is None or c is None for v, c in checks):
                out["caps_ok"] = "n/a"
            else:
                out["caps_ok"] = bool(all(v <= c for v, c in checks))
        else:
            out["second_leg_ok"] = "n/a"
            out["caps_ok"] = "n/a"

        # plausibility gate（094.2 B1 同类）：本账户 liquid 结构性 > 0，
        # 读到 0 只可能是上游静默失败 → n/a，绝不染红报 $0 假警。
        if liquid is not None and liquid > 0:
            d["liquid"] = round(liquid, 2)
            d["cash_floor_usd"] = CASH_FLOOR_USD
            out["cash_floor_ok"] = bool(liquid >= CASH_FLOOR_USD)
        else:
            out["cash_floor_ok"] = "n/a"
        return out
    veto = _guard(_veto)

    # ── ammo（liquid − 在场 debit ≥ reserve_need 为绿；reserve = 12.5%×NLV 现算）─
    def _ammo() -> dict:
        from strategy.q042_sizing import q042_sleeve_cap_pct
        if liquid is None:
            raise RuntimeError(f"liquid cash unavailable: {cash_err}")
        if debit is None:
            raise RuntimeError(f"open debit unavailable: {debit_err}")
        g = _need(gov, gov_err, "governance runtime")
        nlv = _num(g.get("basis_dollars")) or _num((g.get("pools") or {}).get("nlv_basis"))
        if not nlv:
            raise RuntimeError("NLV basis unavailable in governance runtime")
        pct = float(q042_sleeve_cap_pct("A"))          # 12.5（SPEC-104 staged）
        reserve = nlv * pct / 100.0
        inflight = debit
        return {
            "liquid": round(liquid, 2),
            "in_flight_debit": round(inflight, 2),
            "reserve_need": round(reserve, 2),
            "reserve_pct_nlv": pct,
            "nlv_basis": round(nlv, 2),
            "ready": bool(liquid - inflight >= reserve),
        }
    ammo = _guard(_ammo)

    # ── today（selector 推荐摘要 + 资源类型 + 引擎徽章；/api/recommendation 同源）─
    def _today() -> dict:
        from strategy.cash_budget_governance import CASH_OCCUPYING_STRATEGIES
        r = _need(rec, rec_err, "selector recommendation")
        key = getattr(r, "strategy_key", None)
        strategy_name = getattr(r.strategy, "value", str(r.strategy))
        action = getattr(r, "position_action", None)
        if not key or key == "reduce_wait":
            resource = None
        elif key in CASH_OCCUPYING_STRATEGIES:
            resource = "cash"
        else:
            resource = "bp"
        dip = events.get("dip") or {}
        engines = _engine_badges(
            key, action,
            dip.get("active"), (dip.get("sleeve_a") or {}).get("armed"),
        )
        return {
            "strategy": strategy_name,
            "strategy_key": key,
            "position_action": action,
            "resource": resource,          # 吃 BP / 吃 cash（None = 观望）
            "engines": engines,            # ON / STANDBY only（约束 1）
            "size_rule": getattr(r, "size_rule", None),
        }
    today_field = _guard(_today)

    # ── positions（Layer 2 live 行支持字段：开仓一览，只读） ──────────────────
    def _positions() -> dict:
        from strategy.state import read_all_positions
        rows = (read_all_positions() or {}).get("positions", []) or []
        open_rows = [r for r in rows
                     if str(r.get("status") or "open").lower() in {"", "open"}]
        out = []
        for r in open_rows:
            out.append({
                "trade_id": r.get("trade_id"),
                "strategy_key": r.get("strategy_key"),
                "contracts": _num(r.get("contracts")),
                "expiry": r.get("expiry"),
                "underlying": r.get("underlying") or "SPX",
            })
        by_engine = {"premium": 0, "trend": 0}
        for r in out:
            for eng, keys in ENGINE_STRUCTURES.items():
                if str(r.get("strategy_key")) in keys:
                    by_engine[eng] += 1
        return {"open_count": len(out), "open": out, "by_engine": by_engine}
    positions = _guard(_positions)

    # ── pools（Layer 3 双池几何；bar_geometry 单源，AC-141-6） ────────────────
    def _pools() -> dict:
        g = _need(gov, gov_err, "governance runtime")
        p = g.get("pools") or {}
        caps = g.get("caps") or {}
        bp = {
            "spx_pm": bar_geometry(_num(p.get("spx_pm_bp_pct")), 100.0,
                                   cap=_num(caps.get("active_spx_pm_cap_pct"))),
            "short_vol": bar_geometry(_num(p.get("short_vol_bp_pct")), 100.0,
                                      cap=_num(caps.get("R4_short_vol_cap_pct"))),
            "es_span": bar_geometry(_num(p.get("es_span_bp_pct")) or 0.0, 100.0,
                                    cap=_num(caps.get("R2_es_span_cap_pct"))),
            "combined": {"value": _num(p.get("combined_bp_pct")),
                         "cap": _num(caps.get("R3_combined_cap_pct"))},
            "cap_regime": g.get("active_spx_pm_cap_regime"),
            "nlv_basis": _num(p.get("nlv_basis")) or _num(g.get("basis_dollars")),
        }
        cash: dict = {"status": "n/a",
                      "error": f"{cash_err or debit_err or 'liquid/debit unavailable'}"[:200]}
        if liquid is not None and liquid > 0 and debit is not None:
            from strategy.cash_budget_governance import (
                CAP_PCT, CASH_FLOOR_USD,
                CASH_WATERLINE_SELF_CONSISTENT_USD,
                CASH_WATERLINE_SELL_OR_SKIP_USD,
            )
            inflight = debit
            a = ammo if ammo.get("status") == "ok" else {}
            reserve = _num(a.get("reserve_need"))
            # Quant 裁决 2026-07-13：并发余量按 live 口径「1 张 SPX BCD ≈ $40k」
            # 计（Q096：$22k 是 engine-canonical 非 live 指令；2026-06 实测一张
            # $38-41k。display 估值；单张 ~$45k 时按 Q096 §3 复议并更新此常量）。
            bcd_std = 40_000.0
            cash = {
                "status": "ok",
                "liquid": round(liquid, 2),
                "committed": bar_geometry(inflight, liquid),
                "cap_pct": CAP_PCT * 100.0,
                "floor_usd": CASH_FLOOR_USD,
                "floor_pos_pct": round(min(100.0, CASH_FLOOR_USD / liquid * 100.0), 2),
                "utilization_pct": round(inflight / liquid * 100.0, 1),
                # 现金水位门线（Q093 P1 R-b，只读不拦单）——与 home Resource
                # Waterline 卡同一常数源；state 供 Layer 3 行文与金色刻度线。
                "waterline_self_usd": CASH_WATERLINE_SELF_CONSISTENT_USD,
                "waterline_sell_usd": CASH_WATERLINE_SELL_OR_SKIP_USD,
                "waterline_self_pos_pct": round(
                    min(100.0, CASH_WATERLINE_SELF_CONSISTENT_USD / liquid * 100.0), 2),
                "waterline_state": (
                    "ok" if liquid >= CASH_WATERLINE_SELF_CONSISTENT_USD
                    else "below_self" if liquid >= CASH_WATERLINE_SELL_OR_SKIP_USD
                    else "sell_or_skip"),
            }
            # 池水位计（PM 2026-07-13 重画）：fill = liquid 本身；floor/水位线
            # 约束的是池总量而非 committed debit——与 debit 条分离，两根条各自
            # 量纲自洽。scale 锚定 max(liquid, 水位线) 保证门线始终在图内。
            _scale = max(liquid * 1.05, CASH_WATERLINE_SELF_CONSISTENT_USD * 1.25)
            cash["level_gauge"] = {
                "scale_max": round(_scale, 2),
                "fill_pct": round(min(100.0, liquid / _scale * 100.0), 2),
                "floor_pos_pct": round(CASH_FLOOR_USD / _scale * 100.0, 2),
                "waterline_pos_pct": round(
                    CASH_WATERLINE_SELF_CONSISTENT_USD / _scale * 100.0, 2),
            }
            if reserve is not None:
                # 金色弹药刻度线：liquid − reserve_need 的绝对位置；
                # committed 越过此线 = 抄底子弹被吃掉
                cash["ammo_line_usd"] = round(max(liquid - reserve, 0.0), 2)
                cash["ammo_line_pos_pct"] = round(
                    max(0.0, min(100.0, (liquid - reserve) / liquid * 100.0)), 2)
                cash["reserve_need"] = round(reserve, 2)
                cash["ready"] = bool(a.get("ready"))
                headroom = liquid - inflight - reserve
                cash["bcd_standard_usd"] = bcd_std
                cash["bcd_headroom_count"] = int(max(0.0, headroom) // bcd_std)
                cash["headroom_after_reserve_usd"] = round(headroom, 2)
        return {"bp": bp, "cash": cash}
    pools = _guard(_pools)

    # ── rehearsal（触发预演：分型 → 弹药分支 → 建议结构；复用 094.4 helper）───
    def _rehearsal() -> dict:
        import production.q042_executor as ex
        from strategy.q042_sizing import compute_sizing
        c = _need(closes, closes_err, "spx close series")
        g = _need(gov, gov_err, "governance runtime")
        v = _need(vix_snap, vix_err, "vix snapshot")
        nlv = _num(g.get("basis_dollars")) or _num((g.get("pools") or {}).get("nlv_basis"))
        if not nlv:
            raise RuntimeError("NLV basis unavailable")
        spx_close = float(c.iloc[-1])
        long_k, short_k, contracts, est = compute_sizing(nlv, spx_close, float(v.vix), "A")
        advisory_line, ammo_payload = ex._ammo_advisory(
            sleeve_id="A", signal_date=today, nlv=nlv, spx_close=spx_close,
            vix=float(v.vix), contracts=int(contracts or 0), est_debit=est,
            closes=c,
        )
        return {
            "sleeve": "A",
            "long_strike": long_k,
            "short_strike": short_k,
            "contracts": int(contracts or 0),
            "est_debit_per_contract": est,
            "nlv_basis": round(nlv, 2),
            "advisory": advisory_line,
            "episode_type": (ammo_payload or {}).get("episode_type"),
            "branch": (ammo_payload or {}).get("branch"),
            "ammo": ammo_payload,
        }
    rehearsal = _guard(_rehearsal)

    return {
        "spec": "SPEC-141",
        "semantics": "shadow read-only state surface — describes, never routes",
        "ts": _now_et().isoformat(timespec="seconds"),
        "date": today,
        "vol_axis": vol_axis,
        "structure_axis": structure_axis,
        "trend_signal": trend_signal,
        "events": events,
        "veto": veto,
        "ammo": ammo,
        "today": today_field,
        # F3 页面支持字段（additive to the F1 field contract）
        "positions": positions,
        "pools": pools,
        "rehearsal": rehearsal,
    }


# ── F2 — 日志（一天一行，幂等；首跑回填 90 TD 简版） ───────────────────────────

def _log_dates(path: Path) -> set[str]:
    dates: set[str] = set()
    if not path.exists():
        return dates
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line).get("date")
        except json.JSONDecodeError:
            continue
        if d:
            dates.add(str(d))
    return dates


def _simple_backfill_rows(closes, vix_by_date: dict, end_date: str,
                          n: int = BACKFILL_TRADING_DAYS) -> list[dict]:
    """过去 n 个交易日（不含 end_date 当日）的 (vol_state, structure_state) 简版。"""
    import pandas as pd

    end_ts = pd.Timestamp(end_date)
    days = [d for d in closes.index if d < end_ts][-n:]
    rows: list[dict] = []
    for d in days:
        ds = d.strftime("%Y-%m-%d")
        vix = _num(vix_by_date.get(ds))
        try:
            vol = _vol_state(vix) if vix is not None else None
        except Exception:  # noqa: BLE001
            vol = None
        try:
            structure = _structure_axis_from_closes(closes, ds).get("state")
        except Exception:  # noqa: BLE001
            structure = None
        rows.append({"date": ds, "backfill": True,
                     "vol_state": vol, "structure_state": structure})
    return rows


def append_daily_log(date: Optional[str] = None,
                     log_path: Optional[Path] = None,
                     surface: Optional[dict] = None,
                     closes=None, vix_by_date: Optional[dict] = None) -> dict:
    """一天一行落盘（幂等：当日已有则跳过）；首跑回填 90 TD 简版（backfill:true）。

    closes / vix_by_date 仅测试注入用；生产默认走日线缓存
    （ex._fetch_spx_close_series + signals.vix_regime.fetch_vix_history）。
    """
    date = date or _today_str()
    path = Path(log_path) if log_path is not None else STATE_SURFACE_LOG
    existing = _log_dates(path)
    if date in existing:
        return {"status": "skipped", "reason": "already_recorded", "date": date}

    lines: list[str] = []
    backfilled = 0
    if not existing:                    # 首跑（含空文件）→ 回填
        try:
            if closes is None:
                import production.q042_executor as ex
                closes = ex._fetch_spx_close_series(date)
            if vix_by_date is None:
                from signals.vix_regime import fetch_vix_history
                vdf = fetch_vix_history(period="1y")
                vix_by_date = {ts.strftime("%Y-%m-%d"): float(v)
                               for ts, v in vdf["vix"].items()}
            for row in _simple_backfill_rows(closes, vix_by_date, date):
                lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
                backfilled += 1
        except Exception as exc:  # noqa: BLE001 — 回填失败不阻塞当日行
            lines.append(json.dumps({
                "date": date, "backfill": True, "status": "n/a",
                "error": f"backfill failed: {type(exc).__name__}: {exc}"[:200],
            }, ensure_ascii=False, sort_keys=True))

    if surface is None:
        surface = compute_state_surface(today=date)
    row = {
        "date": date,
        "ts": surface.get("ts"),
        "backfill": False,
        "vol_state": (surface.get("vol_axis") or {}).get("state"),
        "structure_state": (surface.get("structure_axis") or {}).get("state"),
        "dip_active": ((surface.get("events") or {}).get("dip") or {}).get("active"),
        "surface": surface,
    }
    lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")
    return {"status": "written", "date": date, "backfilled": backfilled}


def read_history(limit: int = 90, log_path: Optional[Path] = None) -> list[dict]:
    """时间轴读取：最近 limit 行的 (date, vol_state, structure_state, backfill)。

    每日期只保留最后一行（防手工重放产生重复日）；剥掉重字段 surface。
    """
    path = Path(log_path) if log_path is not None else STATE_SURFACE_LOG
    if not path.exists():
        return []
    by_date: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        d = str(r.get("date") or "")
        if not d:
            continue
        by_date[d] = {
            "date": d,
            "vol_state": r.get("vol_state"),
            "structure_state": r.get("structure_state"),
            "dip_active": r.get("dip_active"),
            "backfill": bool(r.get("backfill")),
        }
    return [by_date[d] for d in sorted(by_date)][-limit:]


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="SPEC-141 unified state surface (shadow)")
    ap.add_argument("--print", action="store_true", help="compute and dump the surface JSON")
    ap.add_argument("--log", action="store_true", help="append today's row to data/state_surface.jsonl")
    args = ap.parse_args()
    if args.log:
        print(json.dumps(append_daily_log(), ensure_ascii=False))
    if args.print or not args.log:
        print(json.dumps(compute_state_surface(), ensure_ascii=False, indent=2, default=str))
