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
        lng = _leg_quote(calls, o.get("long_expiry") or o.get("expiry"), o.get("long_strike"))
        sht = _leg_quote(calls, o.get("expiry"), o.get("short_strike"))
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
    fired: list[dict] = []
    realized = _realized_rows()
    marks = _marks_history()
    latest = _latest_open_marks(marks)
    marked_sum = sum(float(m["pnl_mid"]) for m in latest.values())

    # Gate 1 — last 6 realized sum < 0 (needs a full window)
    if len(realized) >= GATE1_LAST_N:
        s = sum(float(r["realized_pnl"]) for r in realized[-GATE1_LAST_N:])
        if s < 0:
            fired.append({"gate": "G1_last6_realized",
                          "detail": f"最近 {GATE1_LAST_N} 笔实现和 ${s:,.0f} < 0"})

    # Gate 2 — 18-month realized+marked < 0 with n >= 3
    cutoff = (date.fromisoformat(today) - timedelta(days=GATE2_WINDOW_DAYS)).isoformat()
    recent = [r for r in realized if str(r.get("closed_at", "")) >= cutoff]
    n2 = len(recent) + len(latest)
    s2 = sum(float(r["realized_pnl"]) for r in recent) + marked_sum
    if n2 >= GATE2_MIN_TRADES and s2 < 0:
        fired.append({"gate": "G2_18m_combined",
                      "detail": f"18 个月实现+标记和 ${s2:,.0f} < 0（n={n2}）"})

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
    if month_dd <= GATE3_MONTH_MARK_DD_USD:
        fired.append({"gate": "G3_month_mark_dd",
                      "detail": f"{month} 标记回撤 ${month_dd:,.0f} ≤ ${GATE3_MONTH_MARK_DD_USD:,.0f}"})

    # Gate 4 — family cumulative (all realized + current marks) → full halt
    cum = sum(float(r["realized_pnl"]) for r in realized) + marked_sum
    if cum < GATE4_FAMILY_CUM_USD:
        fired.append({"gate": "G4_family_cum", "full_halt": True,
                      "detail": f"家族累计（实现+标记）${cum:,.0f} < ${GATE4_FAMILY_CUM_USD:,.0f}"})

    return fired


def _halt_message(fired: list[dict], today: str) -> str:
    # H-4: gate details carry raw "<" comparisons — they killed the 7/6 push
    # (Telegram HTML parse 400). Escape at the push boundary; the state file
    # keeps plain text.
    def _esc(s: str) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = "\n".join(f"  · {f['gate']}: {_esc(f['detail'])}" for f in fired)
    full = any(f.get("full_halt") for f in fired)
    head = "[BCD 治理] 例行复核事件 — D1 门触发，BCD 格降级为 wait"
    if full:
        head = "[BCD 治理] 例行复核事件 — G4 家族累计门触发，BCD 全停，请 PM 复审"
    return (
        f"{head}（{today}）\n{lines}\n"
        "背景：P(6 笔和<0 | 边际为真) ≈ 39-48%/窗口——本事件是预期内的例行复核，"
        "不构成告警。恢复需 PM 显式复审 + fresh 报价对照："
        "python -m strategy.bcd_governance --pm-clear \"...\""
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
    st = read_state()
    days = _lowvol_quote_days()
    return {
        "unlocked": bool(st.get("quote_gate_unlocked")),
        "unlocked_at": st.get("quote_gate_unlocked_at"),
        "days": len(days),
        "needed": QUOTE_GATE_DAYS,
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
    return (f"[BCD 治理] D2 前置门解锁（{today}）：LOW_VOL 报价 {len(days)} 天 ≥ "
            f"{QUOTE_GATE_DAYS}，CALIB 偏移复核通过（{detail}）。"
            f"解锁后首 {FIRST_TRADES_ONE_LOT} 笔 1 张锁定（advisory，PM 手动执行自律）。")


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


# ── daily driver (runs inside the q085 16:50 job) ─────────────────────────────

def daily_update(today: str, calls=None, regime: str | None = None,
                 *, dry_run: bool = False) -> dict:
    summary: dict = {"date": today}
    ran_marker = ROOT / "data" / ".q087_bcd_gov_ran"
    ran_marker.parent.mkdir(parents=True, exist_ok=True)
    ran_marker.touch()

    def push(msg: str) -> None:
        summary.setdefault("pushes", []).append(msg)
        if not dry_run:
            try:
                from notify.event_push import _send
                _send(msg)
            except Exception:
                log.exception("bcd governance push failed")

    # 1. daily marks
    try:
        summary["marks"] = record_daily_marks(calls, today)
    except Exception as exc:
        log.exception("bcd marks failed")
        summary["marks_error"] = str(exc)

    # 2. first-realized-close trigger (pre-registered review)
    st = read_state()
    n_realized = len(_realized_rows())
    if n_realized > int(st.get("realized_seen", 0)):
        st["realized_seen"] = n_realized
        _write_state(st)
        push(f"[BCD 治理] 预注册复审触发：BCD 平仓落 ledger（累计 {n_realized} 笔实现）。"
             "请 PM+Quant 按 D1 预注册流程复审。")

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
            push(msg)
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
