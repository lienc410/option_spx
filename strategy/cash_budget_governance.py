"""SPEC-111 — Cash-budget cap + concurrent-utilization alert.

Governs any strategy that occupies liquid cash: debit strategies (BCD) and
cash-secured puts (CSP). Extended by SPEC-115 Phase A to cover Q041 T2 CSPs.

Rules:
  Hard cap:   Σ cash_occupied ≥ 60% × liquid_cash  → BLOCK
  Alert:      Σ cash_occupied ≥ 75% × liquid_cash  → NOTIFY (allow)
  Cash floor: liquid_cash < $30,000                 → BLOCK regardless

Fail-safe: on any broker API failure, BLOCK (fail closed, not open).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DECISIONS_LOG = DATA_DIR / "cash_budget_decisions.jsonl"
STANDING_STATE = DATA_DIR / "cash_budget_standing_state.json"
STANDING_LOG = DATA_DIR / "cash_budget_standing.jsonl"

# ── Constants ──────────────────────────────────────────────────────────────────

# SPEC-115 Phase A: extended to cover CSP cash collateral strategies
CASH_OCCUPYING_STRATEGIES: frozenset[str] = frozenset({
    "bull_call_diagonal",        # debit (SPEC-111/113)
    "q041_t2_googl_csp",         # CSP cash collateral (SPEC-115 phase A)
    "q041_t2_amzn_csp",          # CSP cash collateral (SPEC-115 phase A)
    "q041_t3_cost_earnings_ic",  # IC max-loss collateral (SPEC-115 phase B)
    "q041_t3_jpm_earnings_ic",   # IC max-loss collateral (SPEC-115 phase B)
})
# Backward-compat alias — do not remove (test_spec_111.py imports this)
DEBIT_STRATEGIES: frozenset[str] = CASH_OCCUPYING_STRATEGIES

CASH_LIKE_SYMBOLS: frozenset[str] = frozenset({"BOXX", "SGOV", "SHV", "USFR", "BIL"})

CAP_PCT: float = 0.60          # hard cap: Σ debit / liquid ≤ 60%
ALERT_PCT: float = 0.75        # concurrent alert: warn but allow
CASH_FLOOR_USD: float = 30_000.0   # hard floor regardless of cap math


# ── Helpers ────────────────────────────────────────────────────────────────────

def _num(v: Any) -> float | None:
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_decisions_log(payload: dict) -> None:
    DECISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


# ── Cash reading ───────────────────────────────────────────────────────────────

def get_current_liquid_cash() -> dict:
    """Read combined liquid cash across brokers.

    Returns:
        {
          "total": float,
          "breakdown": {
            "schwab": {"raw_cash": float, "cash_like": float, "cash_like_positions": list},
            "etrade": {"raw_cash": float, "cash_like": float, "cash_like_positions": list},
          },
          "source": str,  # "live" | "partial" | "unavailable"
          "error": str | None,
        }
    Fail-safe: on any error, returns total=0 + source="unavailable".
    """
    result: dict = {
        "total": 0.0,
        "breakdown": {},
        "source": "unavailable",
        "error": None,
    }
    total = 0.0
    errors: list[str] = []

    # ── Schwab ─────────────────────────────────────────────────────────────────
    try:
        from schwab.client import get_account_balances as schwab_balances
        from schwab.client import get_account_positions as schwab_positions

        bal = schwab_balances()
        schwab_cash = _num(bal.get("cash_balance")) or 0.0

        # Cash-like positions (BOXX etc.)
        pos_data = schwab_positions()
        schwab_cl_positions: list[dict] = []
        schwab_cl_value = 0.0
        for pos in (pos_data.get("positions") or []):
            sym = str(pos.get("symbol") or "").upper()
            if sym in CASH_LIKE_SYMBOLS:
                mv = _num(pos.get("market_value")) or 0.0
                schwab_cl_positions.append({"symbol": sym, "market_value": mv})
                schwab_cl_value += mv

        schwab_total = schwab_cash + schwab_cl_value
        result["breakdown"]["schwab"] = {
            "raw_cash": round(schwab_cash, 2),
            "cash_like": round(schwab_cl_value, 2),
            "cash_like_positions": schwab_cl_positions,
        }
        total += schwab_total
    except Exception as exc:
        errors.append(f"schwab: {exc}")
        log.warning("cash_budget_governance: schwab cash read failed: %s", exc)

    # ── E-Trade ────────────────────────────────────────────────────────────────
    try:
        from etrade.client import get_account_balances as et_balances
        from etrade.client import get_account_positions as et_positions
        from etrade.auth import is_configured as et_configured

        if et_configured():
            bal = et_balances()
            et_cash = _num(bal.get("cash_balance")) or 0.0

            pos_data = et_positions()
            et_cl_positions: list[dict] = []
            et_cl_value = 0.0
            for pos in (pos_data.get("positions") or []):
                sym = str(pos.get("symbol") or "").upper()
                if sym in CASH_LIKE_SYMBOLS:
                    mv = _num(pos.get("market_value")) or 0.0
                    et_cl_positions.append({"symbol": sym, "market_value": mv})
                    et_cl_value += mv

            et_total = et_cash + et_cl_value
            result["breakdown"]["etrade"] = {
                "raw_cash": round(et_cash, 2),
                "cash_like": round(et_cl_value, 2),
                "cash_like_positions": et_cl_positions,
            }
            total += et_total
    except Exception as exc:
        errors.append(f"etrade: {exc}")
        log.warning("cash_budget_governance: etrade cash read failed: %s", exc)

    result["total"] = round(total, 2)
    result["error"] = "; ".join(errors) if errors else None
    result["source"] = "live" if not errors else ("partial" if total > 0 else "unavailable")
    return result


def get_open_cash_collateral_total_usd() -> dict:
    """Sum cash occupied by all open CASH_OCCUPYING_STRATEGIES positions.

    BCD: cash = abs(entry_premium) × contracts × 100 (debit paid)
    CSP: cash = short_strike × contracts × 100 (cash collateral)

    Returns:
        {"total": float, "positions": [...]}
    """
    try:
        from strategy.state import read_all_positions
        all_pos = (read_all_positions() or {}).get("positions", [])
    except Exception as exc:
        log.warning("cash_budget_governance: positions read failed: %s", exc)
        return {"total": 0.0, "positions": [], "error": str(exc)}

    positions: list[dict] = []
    total = 0.0
    for pos in all_pos:
        if str(pos.get("status") or "open").lower() not in {"", "open"}:
            continue
        sk = str(pos.get("strategy_key") or "")
        if sk not in CASH_OCCUPYING_STRATEGIES:
            continue
        n = _num(pos.get("contracts")) or 1.0
        # Prefer explicit cash_need_usd / max_loss_usd if the position carries it
        # (CSP and IC paper positions store this); else derive per strategy type.
        explicit = _num(pos.get("cash_need_usd") or pos.get("max_loss_usd"))
        if explicit is not None:
            cash_usd = explicit  # already a per-position total (× contracts baked in at open)
        elif sk == "bull_call_diagonal":
            # BCD: debit paid
            premium = _num(pos.get("actual_premium") or pos.get("model_premium")) or 0.0
            cash_usd = abs(premium) * n * 100.0
        elif sk.endswith("_csp"):
            # CSP: cash collateral = K × 100 × n
            strike = _num(pos.get("short_strike") or pos.get("strike")) or 0.0
            cash_usd = strike * 100.0 * n
        else:
            # IC or other: fall back to short_strike-based (defensive; should have cash_need)
            strike = _num(pos.get("short_strike") or pos.get("strike")) or 0.0
            cash_usd = strike * 100.0 * n
        positions.append({
            "trade_id": pos.get("trade_id"),
            "strategy_key": sk,
            "cash_usd": round(cash_usd, 2),
        })
        total += cash_usd

    return {"total": round(total, 2), "positions": positions}


# Backward-compat alias for external callers
def get_open_debit_total_usd() -> dict:
    return get_open_cash_collateral_total_usd()


# ── Core evaluator ─────────────────────────────────────────────────────────────

def evaluate_cash_collateral_budget(candidate: dict) -> dict:
    """SPEC-111/115: evaluate cash-budget gate for any cash-occupying strategy.

    Handles both debit (BCD via entry_debit_usd / debit_usd) and CSP cash
    collateral (q041_t2_* via cash_need_usd = K × 100).

    Args:
        candidate: governance candidate dict with strategy_key + cash amount field

    Returns:
        {"accepted": bool, "reason": str, "alert": bool, "stats": {...}}

    Fail-safe: on liquid_cash read failure → accepted=False.
    """
    sk = str(candidate.get("strategy_key") or "")
    if sk not in CASH_OCCUPYING_STRATEGIES:
        return {"accepted": True, "reason": "not_cash_occupying", "alert": False, "stats": {}}

    # Resolve cash_need: CSP uses cash_need_usd; BCD uses debit_usd / requested_bp_dollars
    cash_need = (
        _num(candidate.get("cash_need_usd"))
        or _num(candidate.get("debit_usd"))         # BCD backward compat
        or _num(candidate.get("entry_debit_usd"))   # BCD backward compat
        or _num(candidate.get("requested_bp_dollars"))
    )
    if cash_need is None:
        return {
            "accepted": False, "alert": False,
            "reason": "missing cash_need_usd / debit_usd / requested_bp_dollars",
            "stats": {},
        }
    candidate_cash = abs(cash_need)

    prefix = "debit_cash_budget" if sk == "bull_call_diagonal" else "cash_collateral"

    # Get liquid cash (fail-safe: block on unavailable)
    cash_data = get_current_liquid_cash()
    liquid_cash = cash_data.get("total") or 0.0
    source = cash_data.get("source")
    # SPEC-138 F4 — the cash denominator must know its rail composition. When a
    # broker rail drops mid-session (source="partial": E-Trade token expired but
    # Schwab still reads), the pool shrinks $152k→$105k and a healthy book
    # crosses the 60% cap purely from the missing rail. That is a data outage,
    # NOT a governance verdict — degrade the gate to ADVISORY (never a hard red
    # veto) and surface staleness so decision_trace shows the 135.3 advisory tier.
    rail_complete = source == "live"
    degraded = source == "partial"

    def _staleness() -> dict:
        present = sorted((cash_data.get("breakdown") or {}).keys())
        return {
            "rail_complete": rail_complete,
            "cash_source": source,
            "cash_error": cash_data.get("error"),
            "rails_present": present,
        }

    def _advisory(reason_tail: str, stats: dict) -> dict:
        """缺轨降级档：不 veto、不出红门；同口径数字仅供参考 + staleness 标注。"""
        return {
            "accepted": True,            # 数据降级不裁决 → 不硬 veto
            "outcome": "advisory",
            "reason": (
                "advisory_degraded: 数据降级中（现金轨不齐，"
                f"{cash_data.get('error') or '某轨缺席'}），治理判定暂挂；"
                f"{reason_tail}"
            ),
            "alert": False,
            "stats": {**stats, **_staleness(), "degraded": True},
        }

    if source == "unavailable":
        log.error("cash_budget_governance: liquid cash unavailable — blocking (fail-safe)")
        return {
            "accepted": False,
            "reason": "cash_read_unavailable",
            "alert": False,
            "stats": {
                "current_liquid_cash": 0.0,
                "currently_open_cash": 0.0,
                "candidate_cash": candidate_cash,
                "post_entry_total_cash": candidate_cash,
                "post_entry_utilization_pct": 0.0,
                "cap_pct": CAP_PCT,
                "alert_pct": ALERT_PCT,
                "cash_floor_usd": CASH_FLOOR_USD,
                "rail_complete": False,
            },
        }

    # Cash floor check
    if liquid_cash < CASH_FLOOR_USD:
        floor_stats = {
            "current_liquid_cash": liquid_cash,
            "currently_open_cash": 0.0,
            "candidate_cash": candidate_cash,
            "post_entry_total_cash": candidate_cash,
            "post_entry_utilization_pct": candidate_cash / max(liquid_cash, 1.0) * 100.0,
            "cap_pct": CAP_PCT,
            "alert_pct": ALERT_PCT,
            "cash_floor_usd": CASH_FLOOR_USD,
        }
        if degraded:
            return _advisory(
                f"同口径现金 ${liquid_cash:,.0f} < ${CASH_FLOOR_USD:,.0f} floor（缺轨压低，非真实击穿）",
                floor_stats)
        return {
            "accepted": False,
            "reason": f"cash_floor: liquid cash ${liquid_cash:,.0f} < ${CASH_FLOOR_USD:,.0f} floor",
            "alert": False,
            "stats": {**floor_stats, "rail_complete": rail_complete},
        }

    # Open cash collateral total
    open_data = get_open_cash_collateral_total_usd()
    open_cash = open_data.get("total") or 0.0
    # SPEC-138 F6 — the committed-cash read logs its error and returns total=0
    # on failure; the cap gate used to silently proceed on that 0 (under-counting
    # committed capital → could fail OPEN on an over-budget entry). Surface it:
    # a committed-side read failure degrades the gate to advisory (same posture
    # as an F4 rail gap), never a silent under-count.
    if open_data.get("error"):
        return _advisory(
            f"占用现金读取失败（{open_data.get('error')}），committed 侧无法核算 — "
            "cap 判定暂挂",
            {
                "current_liquid_cash": round(liquid_cash, 2),
                "currently_open_cash": None,
                "candidate_cash": round(candidate_cash, 2),
                "cap_pct": CAP_PCT,
                "alert_pct": ALERT_PCT,
                "cash_floor_usd": CASH_FLOOR_USD,
                "open_cash_read_error": open_data.get("error"),
            })

    post_entry = open_cash + candidate_cash
    utilization = post_entry / max(liquid_cash, 1.0)

    cap_threshold = CAP_PCT * liquid_cash
    alert_threshold = ALERT_PCT * liquid_cash

    stats = {
        "current_liquid_cash": round(liquid_cash, 2),
        "currently_open_cash": round(open_cash, 2),
        # Keep legacy key names for SPEC-111 test compatibility
        "currently_open_debit": round(open_cash, 2),
        "candidate_cash": round(candidate_cash, 2),
        "candidate_debit": round(candidate_cash, 2),
        "post_entry_total_cash": round(post_entry, 2),
        "post_entry_total_debit": round(post_entry, 2),
        "post_entry_utilization_pct": round(utilization * 100.0, 1),
        "cap_pct": CAP_PCT,
        "alert_pct": ALERT_PCT,
        "cash_floor_usd": CASH_FLOOR_USD,
        "rail_complete": rail_complete,
    }

    # Hard cap check
    if post_entry > cap_threshold:
        if degraded:
            return _advisory(
                f"同口径占用 ${post_entry:,.0f} = {utilization*100:.1f}% of "
                f"${liquid_cash:,.0f}（缺轨压低分母，非真实超限）",
                stats)
        return {
            "accepted": False,
            "reason": (
                f"{prefix}: post-entry cash ${post_entry:,.0f} "
                f"= {utilization*100:.1f}% of ${liquid_cash:,.0f} liquid "
                f"(cap {CAP_PCT*100:.0f}%)"
            ),
            "alert": False,
            "stats": stats,
        }

    # Alert check (accepted but warn PM) — a degraded read never rings a spurious
    # alert off the shrunk denominator; the advisory staleness carries the context.
    alert = (post_entry >= alert_threshold) and not degraded
    return {
        "accepted": True,
        "reason": "accepted" if not degraded else "accepted_degraded",
        "alert": alert,
        "stats": {**stats, **({"degraded": True, **_staleness()} if degraded else {})},
    }


# ── Decision logging ───────────────────────────────────────────────────────────

def log_cash_budget_decision(
    candidate: dict,
    decision: dict,
    *,
    path: Path | None = None,
) -> None:
    stats = decision.get("stats") or {}
    payload = {
        "ts": _now_utc(),
        "candidate_strategy": candidate.get("strategy_key"),
        "candidate_debit_usd": stats.get("candidate_debit"),
        "currently_open_debit": stats.get("currently_open_debit"),
        "current_liquid_cash": stats.get("current_liquid_cash"),
        "post_entry_utilization_pct": stats.get("post_entry_utilization_pct"),
        "decision": "accept" if decision.get("accepted") else "reject",
        "reason": decision.get("reason"),
        "alert_threshold_crossed": bool(decision.get("alert")),
        "stats": stats,
    }
    _append_decisions_log(payload) if path is None else (
        path.parent.mkdir(parents=True, exist_ok=True),
        path.open("a").write(json.dumps(payload, sort_keys=True) + "\n"),
    )


# Backward-compat alias — SPEC-111 callers use evaluate_debit_cash_budget
def evaluate_debit_cash_budget(candidate: dict) -> dict:
    """Deprecated alias for evaluate_cash_collateral_budget (SPEC-115 rename)."""
    return evaluate_cash_collateral_budget(candidate)


# ── Q091 crash 预算常数(PM ratified 2026-07-07)──────────────────────────────
# 最恶已批情景:dd 45% × β1.2 × haircut ×2.0;buffer $100k。治理常数(与
# CAP_PCT 同级):改动须重跑 research/q091 网格 + PM re-ratify。前端展示一律
# 经 resource_waterline() 实时计算——no-param-mirror 纪律,禁止硬编码结果值。
Q091_WORST_DD = 0.45
Q091_WORST_BETA = 1.2
Q091_WORST_HAIRCUT_X = 2.0
Q091_BUFFER_USD = 100_000.0

_EQUITY_TYPES = frozenset({"EQUITY", "ETF", "COLLECTIVE_INVESTMENT",
                           "MUTUAL_FUND", "EQ"})


def resource_waterline() -> dict:
    """资源水位(Portfolio Snapshot 卡片数据源):现金池 governed 视图 +
    Q091 最恶情景 crash-day 可部署容量,全部实时计算。
    Fail-soft:单 broker 失败 → partial=True;全失败 → available=False。
    与 Q091 脚本的差异:crash NLV 计入 cash-like(BOXX 在 crash 中保值)。"""
    import importlib

    committed = get_open_cash_collateral_total_usd()
    l_opt = float(committed.get("total") or 0.0)

    liquid_total = 0.0
    excess_worst = 0.0
    brokers: dict = {}
    errors: list[str] = []
    for broker in ("schwab", "etrade"):
        try:
            mod = importlib.import_module(f"{broker}.client")
            bal = mod.get_account_balances()
            pos = (mod.get_account_positions() or {}).get("positions") or []
            cash = _num(bal.get("cash_balance")) or 0.0
            cash_like = sum((_num(p.get("market_value")) or 0.0) for p in pos
                            if str(p.get("symbol") or "").upper() in CASH_LIKE_SYMBOLS)
            equity_mv = sum(
                (_num(p.get("market_value")) or 0.0) for p in pos
                if str(p.get("asset_type") or "").upper() in _EQUITY_TYPES
                and str(p.get("symbol") or "").upper() not in CASH_LIKE_SYMBOLS)
            maint = _num(bal.get("maintenance_margin")) or 0.0
            h0 = (maint / equity_mv) if equity_mv else 0.0
            e_dd = equity_mv * max(0.0, 1.0 - Q091_WORST_DD * Q091_WORST_BETA)
            nlv_dd = e_dd + cash + cash_like - l_opt / 2.0
            maint_dd = e_dd * min(h0 * Q091_WORST_HAIRCUT_X, 1.0)
            excess_worst += nlv_dd - maint_dd
            liquid_total += cash + cash_like
            brokers[broker] = {
                "cash": round(cash + cash_like, 2),
                "equity_mv": round(equity_mv, 2),
                "maint": round(maint, 2),
                "option_bp": _num(bal.get("option_buying_power")
                                  or bal.get("buying_power")),
            }
        except Exception as exc:
            errors.append(f"{broker}: {exc}")
            log.warning("resource_waterline: %s read failed: %s", broker, exc)
    if not brokers:
        return {"available": False, "error": "; ".join(errors)}

    cap_usd = CAP_PCT * liquid_total
    try:
        from strategy.selector import DEFAULT_PARAMS
        standard_debit = float(getattr(DEFAULT_PARAMS, "bcd_max_debit_usd", 22_000.0))
    except Exception:
        standard_debit = 22_000.0
    return {
        "available": True,
        "partial": bool(errors),
        # SPEC-138 F4: rail composition of the pool. When a broker rail dropped
        # (rail_complete=False), the shrunk pool inflates utilization / turns
        # cap_headroom negative ("已满 −$X") — the frontend must render this as a
        # data-degraded staleness state, never a hard "over-cap" verdict.
        "rail_complete": not errors,
        "rails_present": sorted(brokers.keys()),
        "degraded_error": "; ".join(errors) if errors else None,
        "cash": {
            "pool_usd": round(liquid_total, 2),
            "committed_usd": round(l_opt, 2),
            "utilization_pct": round(l_opt / liquid_total * 100.0, 1) if liquid_total else None,
            "cap_pct": CAP_PCT * 100.0,
            "cap_headroom_usd": round(cap_usd - l_opt, 2),
            "floor_usd": CASH_FLOOR_USD,
            "floor_distance_usd": round(liquid_total - CASH_FLOOR_USD, 2),
            "standard_debit_usd": standard_debit,
            "fits_standard_debit": bool(cap_usd - l_opt >= standard_debit),
        },
        "crash_budget": {
            "worst_excess_usd": round(excess_worst, 0),
            "buffer_usd": Q091_BUFFER_USD,
            "deployable_usd": round(excess_worst - Q091_BUFFER_USD, 0),
            "options_sleeve_max_loss_usd": round(l_opt, 2),
            "scenario": (f"dd {Q091_WORST_DD:.0%} × β{Q091_WORST_BETA} × "
                         f"haircut ×{Q091_WORST_HAIRCUT_X:g}"),
        },
        "brokers": brokers,
    }


# ── Standing monitor (SPEC-111 review 2026-07-07) ─────────────────────────────
#
# The June incident this fixes: liquid cash sat below the $30k floor for three
# straight weeks (6/5–6/26, standing utilization 155–204%) and the PM never
# heard about it — the floor only BLOCKS candidates, rejects don't ring, and
# the 75% alert only fires on ACCEPTED entries. Standing state (committed vs
# pool, independent of any candidate) was evaluated by nobody.
#
# This check runs once per trading day (16:50 q085 job) and pushes only on
# STATE TRANSITIONS, never daily spam:
#   floor breached / recovered            → ACTION / FYI
#   standing utilization crosses CAP_PCT  → ACTION (up) / FYI (down)
#   liquid pool moves ≥30% day-over-day   → FYI (denominator visibility)

DENOM_SWING_PCT = 0.30

# ── §5.4 对称复审判据(SPEC-111 复审,PM ratified 2026-07-07)────────────────
# 触发只推 ACTION 提请人工复审,绝不自动改参数。纸面判据若无自动检测就是
# 又一个"6 月哑巴"——所以装进 daily_standing_check。
REVIEW_TIGHTEN_UTIL = 55.0     # 收紧向:站立利用率 > 55%…
REVIEW_TIGHTEN_DAYS = 5        # …连续 5 个记录日
REVIEW_LOOSEN_DAYS = 20        # 放宽向:最近 20 个记录日(跨度 ≤30 自然日)…
REVIEW_LOOSEN_MIN_REJECTS = 2  # …每日 ≥2 笔 cap(非 floor)拒绝…
REVIEW_LOOSEN_MAX_UTIL = 40.0  # …且当前站立利用率 < 40%
REVIEW_SUPPRESS_DAYS = 20      # 同向触发后 20 天内不重发


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def _review_trigger_messages(util, prev_state: dict) -> list[tuple[str, str, str]]:
    """§5.4 判据评估。数据不足 → 静默;返回 (category, kind, body) 列表。
    日期一律取日志 ts 的 UTC 日历日(16:50 ET 写入 = 同一 UTC 日,自洽)。"""
    from datetime import date as _date

    today = datetime.now(timezone.utc).date()
    last_fired = prev_state.get("review_trigger_last") or {}
    msgs: list[tuple[str, str, str]] = []

    def _suppressed(kind: str) -> bool:
        d = last_fired.get(kind)
        try:
            return bool(d) and (today - _date.fromisoformat(str(d))).days < REVIEW_SUPPRESS_DAYS
        except ValueError:
            return False

    # 收紧向
    if util is not None and util > REVIEW_TIGHTEN_UTIL and not _suppressed("review_tighten"):
        by_date: dict[str, float] = {}
        for r in _read_jsonl(STANDING_LOG):
            d = str(r.get("ts", ""))[:10]
            u = (r.get("cash") or {}).get("standing_utilization_pct")
            if d and u is not None:
                by_date[d] = float(u)
        by_date[today.isoformat()] = float(util)
        days = sorted(by_date)[-REVIEW_TIGHTEN_DAYS:]
        if (len(days) >= REVIEW_TIGHTEN_DAYS
                and all(by_date[d] > REVIEW_TIGHTEN_UTIL for d in days)):
            msgs.append(("ACTION", "review_tighten",
                f"[现金池] 复审触发(收紧向):站立利用率连续 {REVIEW_TIGHTEN_DAYS} 个记录日 "
                f"> {REVIEW_TIGHTEN_UTIL:.0f}%(今日 {util:.1f}%)。"
                f"按预注册复审规则:提请人工复审,系统不自动改参数。"))

    # 放宽向
    if util is not None and util < REVIEW_LOOSEN_MAX_UTIL and not _suppressed("review_loosen"):
        rejects: dict[str, int] = {}
        for r in _read_jsonl(DECISIONS_LOG):
            if r.get("decision") != "reject":
                continue
            reason = str(r.get("reason") or "")
            if reason.startswith("cash_floor") or "cap" not in reason:
                continue
            d = str(r.get("ts", ""))[:10]
            rejects[d] = rejects.get(d, 0) + 1
        days = sorted(rejects)[-REVIEW_LOOSEN_DAYS:]
        if (len(days) >= REVIEW_LOOSEN_DAYS
                and all(rejects[d] >= REVIEW_LOOSEN_MIN_REJECTS for d in days)
                and (_date.fromisoformat(days[-1]) - _date.fromisoformat(days[0])).days <= 30):
            msgs.append(("ACTION", "review_loosen",
                f"[现金池] 复审触发(放宽向):最近 {REVIEW_LOOSEN_DAYS} 个记录日每日 "
                f"≥{REVIEW_LOOSEN_MIN_REJECTS} 笔 cap 拒绝,而站立利用率仅 {util:.1f}% "
                f"(<{REVIEW_LOOSEN_MAX_UTIL:.0f}%)——cap 可能与池规模脱钩。"
                f"按预注册复审规则:提请人工复审,系统不自动改参数。"))
    return msgs


def get_resource_snapshot() -> dict:
    """Both resource poles in one call: cash pool (scarce) + committed, and
    per-broker maintenance margin / option BP (abundant pole). Fail-soft:
    missing broker data leaves fields None, never raises."""
    snap: dict = {"ts": _now_utc()}
    cash = get_current_liquid_cash()
    committed = get_open_cash_collateral_total_usd()
    liquid = cash.get("total") or 0.0
    occupied = committed.get("total") or 0.0
    snap["cash"] = {
        "liquid_usd": liquid,
        "committed_usd": occupied,
        "standing_utilization_pct": round(occupied / liquid * 100.0, 1) if liquid > 0 else None,
        "cap_pct": CAP_PCT * 100.0,
        "cap_headroom_usd": round(CAP_PCT * liquid - occupied, 2) if liquid > 0 else None,
        "floor_usd": CASH_FLOOR_USD,
        "floor_breached": bool(liquid < CASH_FLOOR_USD),
        "source": cash.get("source"),
        "positions": committed.get("positions") or [],
    }
    snap["bp"] = {}
    for broker, reader in (("schwab", "schwab.client"), ("etrade", "etrade.client")):
        try:
            import importlib
            bal = importlib.import_module(reader).get_account_balances()
            nlv = _num(bal.get("net_liquidation"))
            maint = _num(bal.get("maintenance_margin"))
            snap["bp"][broker] = {
                "nlv": nlv,
                "maintenance_margin": maint,
                "maint_pct_nlv": round(maint / nlv * 100.0, 1) if maint and nlv else None,
                "option_bp": _num(bal.get("option_buying_power") or bal.get("buying_power")),
            }
        except Exception as exc:
            snap["bp"][broker] = {"error": str(exc)}
    return snap


def daily_standing_check(*, dry_run: bool = False) -> dict:
    """Evaluate standing cash-budget state; push on transitions. Returns the
    snapshot + list of messages emitted (for the q085 job summary)."""
    snap = get_resource_snapshot()
    c = snap["cash"]
    messages: list[tuple[str, str, str]] = []  # (category, kind, body)

    prev: dict = {}
    if STANDING_STATE.exists():
        try:
            prev = json.loads(STANDING_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}

    if c.get("source") == "unavailable":
        # No data — don't flap states on broker outage; report and keep prev.
        snap["messages"] = []
        snap["skipped"] = "cash_read_unavailable"
        return snap

    util = c.get("standing_utilization_pct")
    over_cap = bool(util is not None and util > CAP_PCT * 100.0)
    floor_breached = c["floor_breached"]
    prev_floor = bool(prev.get("floor_breached"))
    prev_over_cap = bool(prev.get("over_cap"))
    prev_liquid = _num(prev.get("liquid_usd"))

    util_txt = f"{util:.1f}%" if util is not None else "—"

    if floor_breached and not prev_floor:
        messages.append(("ACTION", "floor_breach",
            f"[现金池] 跌破 floor:流动现金 ${c['liquid_usd']:,.0f} < ${CASH_FLOOR_USD:,.0f}。"
            f"所有吃现金策略(BCD/T2/T3)从现在起被锁,直到现金恢复。"
            f"已占用 ${c['committed_usd']:,.0f}。"))
    elif prev_floor and not floor_breached:
        messages.append(("FYI", "floor_recover",
            f"[现金池] floor 恢复:流动现金 ${c['liquid_usd']:,.0f} ≥ ${CASH_FLOOR_USD:,.0f},"
            f"吃现金策略解锁(站立利用率 {util_txt})。"))

    if over_cap and not prev_over_cap:
        messages.append(("ACTION", "over_cap",
            f"[现金池] 站立利用率上穿 cap:已占用 ${c['committed_usd']:,.0f} = {util_txt} "
            f"of ${c['liquid_usd']:,.0f}(cap {CAP_PCT*100:.0f}%)。新吃现金开仓将被拒;"
            f"通常由现金池缩水或手动开仓引起。"))
    elif prev_over_cap and not over_cap:
        messages.append(("FYI", "under_cap",
            f"[现金池] 站立利用率回落 cap 之下:{util_txt} of ${c['liquid_usd']:,.0f}。"))

    if prev_liquid and prev_liquid > 0 and not messages:
        swing = (c["liquid_usd"] - prev_liquid) / prev_liquid
        if abs(swing) >= DENOM_SWING_PCT:
            headroom = c.get("cap_headroom_usd")
            headroom_txt = f"(cap 余量 ${headroom:,.0f})" if headroom is not None else ""
            messages.append(("FYI", "denom_swing",
                f"[现金池] 分母变动 {swing:+.0%}:${prev_liquid:,.0f} → ${c['liquid_usd']:,.0f}。"
                f"站立利用率现为 {util_txt}{headroom_txt}。"))

    try:
        messages.extend(_review_trigger_messages(util, prev))
    except Exception:
        log.exception("cash review trigger evaluation failed")

    snap["messages"] = [{"category": cat, "kind": kind, "body": body}
                        for cat, kind, body in messages]
    if not dry_run:
        for cat, kind, body in messages:
            try:
                from notify.gateway import escape, push as gw_push
                gw_push(cat, "系统状态", "现金预算站立监控", escape(body),
                        dedupe_key=f"cash_standing:{kind}")
            except Exception:
                log.exception("cash standing push failed")
        try:
            review_last = dict(prev.get("review_trigger_last") or {})
            for _, kind, _ in messages:
                if kind in ("review_tighten", "review_loosen"):
                    review_last[kind] = datetime.now(timezone.utc).date().isoformat()
            STANDING_STATE.parent.mkdir(parents=True, exist_ok=True)
            STANDING_STATE.write_text(json.dumps({
                "ts": snap["ts"],
                "liquid_usd": c["liquid_usd"],
                "committed_usd": c["committed_usd"],
                "floor_breached": floor_breached,
                "over_cap": over_cap,
                "review_trigger_last": review_last,
            }, sort_keys=True), encoding="utf-8")
            with STANDING_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({k: snap[k] for k in ("ts", "cash", "bp")},
                                   sort_keys=True, default=str) + "\n")
        except Exception:
            log.exception("cash standing state write failed")
    return snap
