"""SPEC-123 — BCD family governance: D1 halt state machine + D2 quote-gate.

Family = bull_call_diagonal, both lanes (LOW_VOL×BULLISH main cell + SPEC-113
carve). Data: realized fills from data/closed_trades.jsonl + daily chain-mark
rows this module appends to data/q087_bcd_marks.jsonl (mid primary, natural
recorded in parallel). Evaluated once per trading day inside the 16:50 q085
job (daily_update); the halt state is consumed by the LIVE selector wrapper
only — backtests never read it.

RUN CHARACTERISTIC (PM-ratified, keep in every push):
P(last-6-realized-trades sum < 0 | the BCD edge is REAL) ≈ 39-48% per rolling
window — a D1 halt is a ROUTINE REVIEW EVENT that is EXPECTED to fire
repeatedly over the strategy's life even when nothing is wrong. All copy below
uses review language ("例行复核"), never alarm language, and never 🚨.

Recovery from halt requires an explicit PM review + fresh quote comparison:
    python -m strategy.bcd_governance --pm-clear "复审结论……"
"""
from __future__ import annotations

import json
import logging
import math
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "q087_bcd_governance_state.json"
MARKS_PATH = ROOT / "data" / "q087_bcd_marks.jsonl"
CLOSED_TRADES = ROOT / "data" / "closed_trades.jsonl"
SHADOW_PATH = ROOT / "data" / "q087_bcd_quote_shadow.jsonl"
ET = ZoneInfo("America/New_York")

BCD_KEY = "bull_call_diagonal"

# ── D1 halt gates (task/SPEC-123.md §1, PM 2026-07-05) ───────────────────────
GATE1_LAST_N = 6                       # last 6 realized trades sum < 0
GATE2_WINDOW_DAYS = 548                # ~18 calendar months
GATE2_MIN_TRADES = 3                   # realized+marked < 0 with n >= 3
GATE3_MONTH_MARK_DD_USD = -12_000.0    # single calendar month marked PnL
GATE4_FAMILY_CUM_USD = -15_000.0       # realized+marked → full halt + PM review

# ── D2 quote-gate (§2) ────────────────────────────────────────────────────────
QUOTE_GATE_DAYS = 10                   # LOW_VOL quote days needed
QUOTE_GATE_TOL_VP = 1.0                # |median moff drift| tolerance, c30 & c70
FIRST_TRADES_ONE_LOT = 5               # post-unlock 1-contract advisory span

log = logging.getLogger("bcd_governance")


# ── state io ──────────────────────────────────────────────────────────────────

def read_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def is_halted() -> dict | None:
    """Halt info dict or None. Consumed by the live selector wrapper."""
    st = read_state()
    return st.get("halt") or None


def pm_clear(note: str) -> None:
    """PM explicit review clears the halt (SPEC-123: recovery is manual only)."""
    st = read_state()
    st["halt"] = None
    st.setdefault("pm_reviews", []).append(
        {"at": datetime.now(ET).isoformat(timespec="seconds"), "note": note})
    _write_state(st)


# ── ledger readers ────────────────────────────────────────────────────────────
#
# SPEC-127 §1 记账衔接（状态机注释，防歧义）：D1 “最近 6 笔实现”（G1）的计数
# 单位 = cycle 实现事件。每次 roll 的短腿平仓是一个真实决策点，atomic roll 流程
# 会向 closed_trades.jsonl 追加一行 cycle 行（cycle_event=True, close_reason=
# "roll", realized_pnl = roll 净 credit×100×contracts）——该行与整仓平仓行一样
# 进入 _realized_rows()，参与 G1/G2/G4 求和。mark 类门天然兼容：roll 后
# record_daily_marks 只标记新结构（entry + value），已入袋的 roll 收入由 cycle
# 行承载，家族求和（realized + marked）保持恒等，不重复计。

def _realized_rows() -> list[dict]:
    rows = []
    if CLOSED_TRADES.exists():
        for line in CLOSED_TRADES.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("strategy_key") == BCD_KEY and r.get("realized_pnl") is not None:
                rows.append(r)
    rows.sort(key=lambda r: str(r.get("closed_at", "")))
    return rows


def open_bcd_positions() -> list[dict]:
    """Resolved open (un-closed, un-voided) BCD positions from the trade log.
    Ids flagged duplicate_open_count>0 (2026-06-03 collision, migration
    pending) are counted as ONE position — see SPEC-123_ledger_id_migration_note."""
    from logs.trade_log_io import resolve_log
    out = []
    for row in resolve_log():
        o = row.get("open") or {}
        if (not row.get("voided") and row.get("close") is None
                and o.get("strategy_key") == BCD_KEY
                and not o.get("paper_trade")):
            out.append(row)
    return out


# ── daily chain marks ─────────────────────────────────────────────────────────

def _leg_quote(calls, expiry: str, strike: float):
    e = calls[(calls.expiry.astype(str) == str(expiry)) & (calls.strike == float(strike))]
    return e.iloc[0] if len(e) else None


def record_daily_marks(calls, date_str: str) -> list[dict]:
    """Mark every open BCD position off today's call chain. Value convention:
    value = long.mid − short.mid (what closing collects, positive);
    entry actual_premium is signed with debit NEGATIVE (ledger convention),
    so pnl = (entry_premium + value) × 100 × contracts. Natural parallel:
    sell long at bid / buy short back at ask."""
    out: list[dict] = []
    if calls is None or not len(calls):
        return out
    for pos in open_bcd_positions():
        o = pos["open"]
        try:
            entry = float(o.get("actual_premium"))
            contracts = float(o.get("contracts") or 1)
        except (TypeError, ValueError):
            continue
        # SPEC-127 §2: after a roll the CURRENT short leg lives in the last
        # roll event's new_short — the open event keeps the original short.
        from strategy.campaign import current_short_leg
        cur_short = current_short_leg(pos)
        lng = _leg_quote(calls, o.get("long_expiry") or o.get("expiry"), o.get("long_strike"))
        sht = _leg_quote(calls, cur_short.get("expiry"), cur_short.get("strike"))
        if lng is None or sht is None:
            out.append({"date": date_str, "trade_id": pos["id"], "error": "legs_not_in_chain"})
            continue
        value_mid = float(lng.mid) - float(sht.mid)
        value_nat = float(lng.bid) - float(sht.ask)
        row = {
            "date": date_str,
            "trade_id": pos["id"],
            "entry_premium": entry,
            "contracts": contracts,
            "value_mid": round(value_mid, 4),
            "value_natural": round(value_nat, 4),
            "pnl_mid": round((entry + value_mid) * 100 * contracts, 2),
            "pnl_natural": round((entry + value_nat) * 100 * contracts, 2),
        }
        if pos.get("duplicate_open_count"):
            row["duplicate_open_pending_migration"] = True
        for k, v in row.items():
            if isinstance(v, float) and not math.isfinite(v):
                raise ValueError(f"bcd mark non-finite {k}={v}")
        out.append(row)
    if out:
        MARKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MARKS_PATH.open("a", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    return out


def _marks_history() -> list[dict]:
    rows = []
    if MARKS_PATH.exists():
        for line in MARKS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def _latest_open_marks(marks: list[dict]) -> dict[str, dict]:
    """trade_id -> latest mark row (only for currently-open positions)."""
    open_ids = {p["id"] for p in open_bcd_positions()}
    latest: dict[str, dict] = {}
    for r in marks:
        if r.get("trade_id") in open_ids and "pnl_mid" in r:
            cur = latest.get(r["trade_id"])
            if cur is None or str(r["date"]) >= str(cur["date"]):
                latest[r["trade_id"]] = r
    return latest


# ── D1 gate evaluation ────────────────────────────────────────────────────────

def evaluate_gates(today: str) -> list[dict]:
    """Returns fired gates as dicts (empty = healthy). Mid marks are primary."""
    fired, _trace = evaluate_gates_detailed(today)
    return fired


def evaluate_gates_detailed(today: str) -> tuple[list[dict], list[dict]]:
    """SPEC-135 — (fired, all_gates_trace)：四门逐个入 trace（含未触发的，
    label_human 与门定义同居此处，随门改动同 commit）。evaluate_gates 行为
    不变（薄包装，返回 fired 部分）。"""
    fired: list[dict] = []
    trace: list[dict] = []
    realized = _realized_rows()
    marks = _marks_history()
    latest = _latest_open_marks(marks)
    marked_sum = sum(float(m["pnl_mid"]) for m in latest.values())

    def _node(check: str, label_human: str, detail: str, hit: bool,
              inputs: dict, code_ref: str) -> None:
        trace.append({"layer": "governance", "check": check,
                      "label_human": label_human, "detail": detail,
                      "inputs": inputs, "outcome": "veto" if hit else "pass",
                      "code_ref": code_ref, "branch_taken": True,
                      "kind": "evidence", "stage": "governance"})

    # Gate 1 — last 6 realized sum < 0 (needs a full window)
    g1_hit = False
    if len(realized) >= GATE1_LAST_N:
        s = sum(float(r["realized_pnl"]) for r in realized[-GATE1_LAST_N:])
        g1_hit = s < 0
        if g1_hit:
            fired.append({"gate": "G1_last6_realized",
                          "label_human": f"最近 {GATE1_LAST_N} 笔合计门（安全刹车）",
                          "detail": f"最近 {GATE1_LAST_N} 笔实现和 ${s:,.0f} < 0"})
        _node("g1_last6",
              f"最近 {GATE1_LAST_N} 笔实现结果合计是否转负（转负 = 例行复核，非失效判定）",
              f"合计 ${s:,.0f} vs 0（计数口径：整仓平仓与 roll 短腿周期各计一笔）",
              g1_hit, {"last_n_sum": round(s, 2), "n": GATE1_LAST_N}, "SPEC-123 G1")
    else:
        _node("g1_last6",
              f"最近 {GATE1_LAST_N} 笔实现结果合计是否转负",
              f"实现样本不足（{len(realized)}/{GATE1_LAST_N} 笔）——本门不评估",
              False, {"n_realized": len(realized)}, "SPEC-123 G1")

    # Gate 2 — 18-month realized+marked < 0 with n >= 3
    cutoff = (date.fromisoformat(today) - timedelta(days=GATE2_WINDOW_DAYS)).isoformat()
    recent = [r for r in realized if str(r.get("closed_at", "")) >= cutoff]
    n2 = len(recent) + len(latest)
    s2 = sum(float(r["realized_pnl"]) for r in recent) + marked_sum
    g2_hit = bool(n2 >= GATE2_MIN_TRADES and s2 < 0)
    if g2_hit:
        fired.append({"gate": "G2_18m_combined",
                      "label_human": "18 个月合计门",
                      "detail": f"18 个月实现+标记和 ${s2:,.0f} < 0（n={n2}）"})
    _node("g2_18m",
          "该策略家族 18 个月合计（已实现 + 持仓按市价折算）是否转负",
          f"合计 ${s2:,.0f} vs 0（n={n2}，满 {GATE2_MIN_TRADES} 笔才评估）",
          g2_hit, {"sum_18m": round(s2, 2), "n": n2, "min_n": GATE2_MIN_TRADES},
          "SPEC-123 G2")

    # Gate 3 — single calendar month marked drawdown
    month = today[:7]
    month_dd = 0.0
    by_trade: dict[str, list[dict]] = {}
    for r in marks:
        if "pnl_mid" in r:
            by_trade.setdefault(r["trade_id"], []).append(r)
    for tid, rows in by_trade.items():
        rows.sort(key=lambda r: str(r["date"]))
        in_month = [r for r in rows if str(r["date"])[:7] == month]
        if not in_month:
            continue
        before = [r for r in rows if str(r["date"])[:7] < month]
        base = float(before[-1]["pnl_mid"]) if before else 0.0
        month_dd += float(in_month[-1]["pnl_mid"]) - base
    g3_hit = month_dd <= GATE3_MONTH_MARK_DD_USD
    if g3_hit:
        fired.append({"gate": "G3_month_mark_dd",
                      "label_human": "单月标记回撤门",
                      "detail": f"{month} 标记回撤 ${month_dd:,.0f} ≤ ${GATE3_MONTH_MARK_DD_USD:,.0f}"})
    _node("g3_month_dd",
          "本月持仓按市价折算的回撤是否超过单月上限",
          f"{month} 回撤 ${month_dd:,.0f} vs 上限 ${GATE3_MONTH_MARK_DD_USD:,.0f}",
          g3_hit, {"month_dd": round(month_dd, 2), "limit": GATE3_MONTH_MARK_DD_USD},
          "SPEC-123 G3")

    # Gate 4 — family cumulative (all realized + current marks) → full halt
    cum = sum(float(r["realized_pnl"]) for r in realized) + marked_sum
    g4_hit = cum < GATE4_FAMILY_CUM_USD
    if g4_hit:
        fired.append({"gate": "G4_family_cum", "full_halt": True,
                      "label_human": "家族累计全停门",
                      "detail": f"家族累计（实现+标记）${cum:,.0f} < ${GATE4_FAMILY_CUM_USD:,.0f}"})
    _node("g4_family_cum",
          "该策略家族开账以来累计（实现 + 标记）是否击穿全停线（击穿 = 全停 + PM 复审）",
          f"累计 ${cum:,.0f} vs 全停线 ${GATE4_FAMILY_CUM_USD:,.0f}",
          g4_hit, {"family_cum": round(cum, 2), "limit": GATE4_FAMILY_CUM_USD},
          "SPEC-123 G4")

    return fired, trace


def _halt_message(fired: list[dict], today: str) -> str:
    # H-4: this returns PLAIN text (summary/state keep it readable). Escaping
    # happens once, whole-body, in daily_update's push() — the 7/6 fix escaped
    # only the gate details and the 背景 line's raw "<0" below killed the 7/7
    # push all over again. Never escape fragments.
    lines = "\n".join(f"  · {f.get('label_human', f['gate'])}: {f['detail']}"
                      for f in fired)
    full = any(f.get("full_halt") for f in fired)
    head = "[BCD 治理] 例行复核事件 — 安全刹车触发，BCD 暂停开新仓"
    if full:
        head = ("[BCD 治理] 例行复核事件 — 家族累计亏损击穿全停线，"
                "BCD 全线暂停，请 PM 复审")
    return (
        f"{head}（{today}）\n{lines}\n"
        "背景：即使策略边际为真，6 笔合计转负的概率也有约 39-48%/窗口——"
        "本事件是预期内的例行复核，不构成告警。恢复需 PM 显式复审 + "
        "fresh 报价对照：python -m strategy.bcd_governance --pm-clear \"...\""
    )


# ── D2 quote-gate ─────────────────────────────────────────────────────────────

def _lowvol_quote_days() -> list[str]:
    """Distinct dates with a usable LOW_VOL BCD quote in the shadow file."""
    days = set()
    if SHADOW_PATH.exists():
        for line in SHADOW_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (r.get("regime") == "LOW_VOL" and not r.get("error")
                    and "long_mid" in r and "short_mid" in r):
                days.add(str(r["date"]))
    return sorted(days)


def quote_gate_status() -> dict:
    # label_human 与门逻辑同居（SPEC-136 单源原则）：digest / selector
    # rationale / 手动开仓 advisory 一律取此字段，禁止各处手写第二套。
    st = read_state()
    days = _lowvol_quote_days()
    return {
        "unlocked": bool(st.get("quote_gate_unlocked")),
        "unlocked_at": st.get("quote_gate_unlocked_at"),
        "days": len(days),
        "needed": QUOTE_GATE_DAYS,
        "label_human": (f"真实报价已积累 {len(days)}/{QUOTE_GATE_DAYS} 天"
                        f"（满 {QUOTE_GATE_DAYS} 天才评估 BCD 重开）"),
    }


def _calib_drift_ok(lowvol_days: list[str]) -> tuple[bool, str]:
    """|median moff over LOW_VOL days − calibration-window median| <= 1vp for
    the BCD legs (c30, c70). Reads the production monitor rows by date."""
    from pricing.calibration import SKEW_MONITOR, _read_rows
    rows = {str(r.get("date")): r for r in _read_rows(SKEW_MONITOR)}
    detail = []
    for field in ("c30_moff", "c70_moff"):
        all_vals = [float(r[field]) for r in rows.values()
                    if isinstance(r.get(field), (int, float))]
        lv_vals = [float(rows[d][field]) for d in lowvol_days
                   if d in rows and isinstance(rows[d].get(field), (int, float))]
        if len(lv_vals) < QUOTE_GATE_DAYS or not all_vals:
            return False, f"{field}: LOW_VOL 样本不足（{len(lv_vals)}/{QUOTE_GATE_DAYS}）"
        delta = abs(statistics.median(lv_vals) - statistics.median(all_vals))
        detail.append(f"{field} |Δ|={delta:.2f}vp")
        if delta > QUOTE_GATE_TOL_VP:
            return False, f"{field} |Δ|={delta:.2f}vp > {QUOTE_GATE_TOL_VP}vp"
    return True, "; ".join(detail)


def check_quote_gate_unlock(today: str) -> str | None:
    """Called daily; returns a push message when the gate just unlocked."""
    st = read_state()
    if st.get("quote_gate_unlocked"):
        return None
    days = _lowvol_quote_days()
    if len(days) < QUOTE_GATE_DAYS:
        return None
    ok, detail = _calib_drift_ok(days)
    if not ok:
        log.info("bcd quote-gate: days=%d but drift check not passed (%s)", len(days), detail)
        return None
    st["quote_gate_unlocked"] = True
    st["quote_gate_unlocked_at"] = today
    _write_state(st)
    return (f"[BCD 治理] 重开前置条件已满足（{today}）：LOW_VOL 环境真实报价已积累 "
            f"{len(days)} 天（≥ {QUOTE_GATE_DAYS}），报价-模型偏移复核通过（{detail}）。"
            f"重开后前 {FIRST_TRADES_ONE_LOT} 笔每笔限 1 张（提示性纪律，PM 手动执行）。")


def first5_advisory() -> str | None:
    """After unlock: '1 张锁定 (k/5)' until 5 BCD opens have landed."""
    st = read_state()
    unlocked_at = st.get("quote_gate_unlocked_at")
    if not st.get("quote_gate_unlocked") or not unlocked_at:
        return None
    from logs.trade_log_io import resolve_log
    k = sum(1 for row in resolve_log()
            if (o := row.get("open") or {}).get("strategy_key") == BCD_KEY
            and not o.get("paper_trade") and not row.get("voided")
            and str(o.get("timestamp", ""))[:10] >= str(unlocked_at))
    if k >= FIRST_TRADES_ONE_LOT:
        return None
    return f"解锁后首 {FIRST_TRADES_ONE_LOT} 笔 1 张锁定（当前 {k}/{FIRST_TRADES_ONE_LOT}）"


# ── SPEC-127 §4 — H-5 短腿动作引擎（21-DTE + collapse 双触发） ────────────────
#
# H-5 根因：BCD catalog 写明 “Close the entire position when the short leg
# reaches 21 DTE”，但动作从未接进任何 daily 驱动——生产仓位曾 11 DTE 仍 HOLD。
# 本引擎每日（16:50 q085 job 内）对每个 open BCD 仓位评估两个机械触发：
#   1. 短腿 ≤ 21 DTE
#   2. 短腿残值 ≤ 15% 该短腿入场权利金（collapse buyback，Q089 幸存项，
#      PM ratify 2026-07-06；仓位状态触发非择时——roll 即同时平旧开新，
#      不留等待裁量）
# 触发 → gateway ACTION “CLOSE 或 ROLL”，附链上建议新短腿（45 DTE |Δ|0.30，
# 与 SPEC-122 shadow 同款腿）。roll 后短腿 expiry 更新 → DTE 时钟按新短腿重置，
# dedupe key 随 expiry 变化自动重新武装。

SHORT_ACTION_DTE = 21
COLLAPSE_RESIDUAL_FRAC = 0.15


def _suggest_new_short(calls) -> dict | None:
    """链上建议新短腿：45 DTE |Δ|0.30（复用 SPEC-122 shadow 的选腿器）。"""
    if calls is None or not len(calls):
        return None
    try:
        from notify.q087_bcd_quote_shadow import (
            SHORT_DELTA_TARGET, SHORT_DTE_TARGET, _pick_leg)
        row = _pick_leg(calls, SHORT_DTE_TARGET, SHORT_DELTA_TARGET)
        if row is None:
            return None
        return {
            "strike": float(row.strike),
            "expiry": str(row.expiry),
            "dte": int(row.dte),
            "delta": round(float(row.delta), 3),
            "bid": float(row.bid),
            "mid": float(row.mid),
        }
    except Exception:
        log.exception("bcd new-short suggestion failed")
        return None


def evaluate_short_leg_actions(today: str, calls=None) -> list[dict]:
    """Returns one action dict per triggered open BCD position (empty =
    nothing to do). Pure evaluation — pushing happens in daily_update."""
    from strategy.campaign import current_short_leg

    actions: list[dict] = []
    suggestion = None
    for pos in open_bcd_positions():
        cur = current_short_leg(pos)
        expiry = cur.get("expiry")
        if not expiry:
            continue
        try:
            short_dte = (date.fromisoformat(str(expiry)[:10])
                         - date.fromisoformat(today)).days
        except ValueError:
            continue
        triggers: list[str] = []
        if short_dte <= SHORT_ACTION_DTE:
            triggers.append(f"短腿 {short_dte} DTE ≤ {SHORT_ACTION_DTE}")
        residual = None
        entry_credit = cur.get("entry_price")
        if calls is not None and len(calls) and cur.get("strike") is not None:
            q = _leg_quote(calls, expiry, cur["strike"])
            if q is not None:
                residual = float(q.mid)
        if (residual is not None and entry_credit
                and residual <= COLLAPSE_RESIDUAL_FRAC * float(entry_credit)):
            triggers.append(
                f"短腿残值 {residual:.2f} ≤ {COLLAPSE_RESIDUAL_FRAC:.0%} × 入场权利金 "
                f"{float(entry_credit):.2f}（collapse buyback）")
        if not triggers:
            continue
        if suggestion is None:
            suggestion = _suggest_new_short(calls)
        actions.append({
            "trade_id": pos["id"],
            "short_strike": cur.get("strike"),
            "short_expiry": expiry,
            "short_dte": short_dte,
            "residual_mid": residual,
            "short_entry_price": entry_credit,
            "triggers": triggers,
            "suggested_new_short": suggestion,
        })
    return actions


def _fmt_strike(v) -> str:
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return "?"


def _action_message(a: dict) -> str:
    lines = [
        f"短腿 C{_fmt_strike(a['short_strike'])} exp {a['short_expiry']}（{a['short_dte']} DTE）",
        "触发: " + "；".join(a["triggers"]),
        "机械规则动作: CLOSE 或 ROLL（二选一，今日执行）",
    ]
    s = a.get("suggested_new_short")
    if s:
        lines.append(
            f"建议新短腿（45 DTE |Δ|0.30 同 shadow 款）: C{_fmt_strike(s['strike'])} "
            f"exp {s['expiry']}（{s['dte']} DTE, Δ{s['delta']:+.2f}, "
            f"bid {s['bid']:.2f} / mid {s['mid']:.2f}）")
    else:
        lines.append("建议新短腿: 链上数据不可用，按 45 DTE |Δ|0.30 手动选腿")
    lines.append("Roll 登记: /spx 持仓卡 Roll 按钮；roll 后 21-DTE 时钟按新短腿重置")
    return "\n".join(lines)


# ── daily driver (runs inside the q085 16:50 job) ─────────────────────────────

def daily_update(today: str, calls=None, regime: str | None = None,
                 *, dry_run: bool = False) -> dict:
    summary: dict = {"date": today}
    ran_marker = ROOT / "data" / ".q087_bcd_gov_ran"
    ran_marker.parent.mkdir(parents=True, exist_ok=True)
    ran_marker.touch()

    def push(msg: str, category: str = "ACTION", *, about: str = "系统状态",
             title: str = "", dedupe_key: str | None = None) -> None:
        # SPEC-126: halt / pre-registered review = ACTION (PM 复审动作)，
        # quote-gate unlock = FYI (静默)。治理类 about 固定 系统状态；
        # SPEC-127 §4 短腿动作 about = 持仓 <trade_id>。
        summary.setdefault("pushes", []).append(msg)
        if not dry_run:
            try:
                from notify.gateway import escape, push as gw_push
                # all bodies from this module are plain text — whole-body
                # escape at the boundary (H-4, twice-bitten)
                gw_push(category, about, title, escape(msg), dedupe_key=dedupe_key)
            except Exception:
                log.exception("bcd governance push failed")

    # 1. daily marks
    try:
        summary["marks"] = record_daily_marks(calls, today)
    except Exception as exc:
        log.exception("bcd marks failed")
        summary["marks_error"] = str(exc)

    # 1.5 SPEC-127 §4 (H-5) — 短腿 21-DTE / collapse 双触发 → CLOSE 或 ROLL
    try:
        actions = evaluate_short_leg_actions(today, calls)
        summary["short_leg_actions"] = actions
        for a in actions:
            push(_action_message(a), category="ACTION",
                 about=f"持仓 {a['trade_id']}",
                 title="BCD 短腿到期管理 — CLOSE 或 ROLL",
                 dedupe_key=f"bcd_short_action:{a['trade_id']}:{a['short_expiry']}")
    except Exception as exc:
        log.exception("bcd short-leg action evaluation failed")
        summary["short_leg_actions_error"] = str(exc)

    # 2. first-realized-close trigger (pre-registered review)
    st = read_state()
    n_realized = len(_realized_rows())
    if n_realized > int(st.get("realized_seen", 0)):
        st["realized_seen"] = n_realized
        _write_state(st)
        push(f"[BCD 治理] 预注册复审触发：BCD 实现事件落 ledger（累计 {n_realized} 笔——"
             "计数口径：整仓平仓与 roll 短腿周期各计一笔）。"
             "请 PM+Quant 按预注册复审流程复核（报价对照 + 边际复核）。")

    # 3. D1 gates
    try:
        fired = evaluate_gates(today)
        summary["gates_fired"] = [f["gate"] for f in fired]
        if fired and not is_halted():
            st = read_state()
            st["halt"] = {"at": today, "gates": fired,
                          "full_halt": any(f.get("full_halt") for f in fired)}
            _write_state(st)
            push(_halt_message(fired, today))
    except Exception as exc:
        log.exception("bcd gate evaluation failed")
        summary["gates_error"] = str(exc)

    # 4. D2 quote-gate (only meaningful while LOW_VOL quotes accumulate)
    try:
        msg = check_quote_gate_unlock(today)
        if msg:
            push(msg, category="FYI")
        summary["quote_gate"] = quote_gate_status()
    except Exception as exc:
        log.exception("bcd quote gate check failed")
        summary["quote_gate_error"] = str(exc)

    return summary


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="SPEC-123 BCD governance")
    p.add_argument("--pm-clear", metavar="NOTE",
                   help="PM explicit review: clear the halt with a review note")
    p.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.pm_clear:
        pm_clear(args.pm_clear)
        print("halt cleared; review note recorded")
        return 0
    print(json.dumps({"halt": is_halted(), "quote_gate": quote_gate_status()},
                     indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
