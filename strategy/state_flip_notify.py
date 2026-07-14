"""SPEC-142 — 状态转换 FYI 通知（结构轴 / Vol 轴翻转当日推送）。

F1  比对 state_surface.jsonl 今日行 vs 上一交易日行的 structure_state /
    vol_state；任一变化 → gateway FYI（quiet），dedupe `state_flip_{axis}_{date}`
    保证每轴每日至多一条。正文 = 翻转事实 + 新状态的当下事实行：
      - 进入 RANGE：箱体确认行 + 弹药检查行（89% dip 源于此态的既有配对）
      - 离开 RANGE：破箱方向 + 方向基率行（Q097 P3/P3b 双面事实版）
F2  正文禁结构建议词（_BANNED）；模板 drift 由 _assert_clean 当场 raise——
    契约违规必须响，不静默改写（同 gateway prepare 哲学）。
F3  任一侧状态缺失 / 今日行是 backfill → 该轴跳过不误报；首跑 90 行回填
    不逐行触发（只比对最新两个日期）。
dry_run  构建不推送：不触 gateway（零 dedupe 落盘零消息）。

Rollback：从 scripts/daily_snapshot.py 摘除 _state_flip_hook 一行即回退。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from strategy.state_surface import STATE_SURFACE_LOG

# F2 禁令（AC-142-2 负向断言同源；Q098 教训：状态通知只说是什么，不说做什么）
_BANNED = ("IC", "BPS", "BCD", "建议", "优先", "更适合", "适合做")

# Q097 P3b 双面事实（纯基率，无建议词；P3b 修正"上破=benign"乐观偏差）
_UP_BREAK_LINE = ("历史上 63% 的破箱是向上破，多数在 ~3 周内于更高位置形成新箱体"
                  "（平移换箱，而非新一轮单边）；但已知 4 次崩盘全部发生在‘弱上破’"
                  "（收盘只探出箱顶不足 1%）之后 5-10 个交易日内——上破后 20 个交易日内"
                  "演变成崩盘的历史概率约 3.3%")
_DOWN_BREAK_LINE = ("历史上 37% 的破箱是向下破；下破后 20 个交易日的尾部风险是上破的"
                    "两倍（再跌 7% 以上的概率 14% vs 7%），其中包含直接转入趋势下跌的"
                    "真裂口（如 2026-03-13）")
_RANGE_AMMO_PREFIX = "历史上 89% 的抄底触发发生在箱体状态 → 现金弹药检查："


def _assert_clean(text: str) -> str:
    """F2 守卫：模板演化若引入建议词，当场 raise（loud，不静默清洗）。"""
    for w in _BANNED:
        if w in text:
            raise ValueError(f"SPEC-142 F2 violation: banned word {w!r} in push text")
    return text


def _fmt_usd(v: object) -> str:
    try:
        return f"${float(v):,.0f}"  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "n/a"


def _latest_two_rows(path: Path) -> tuple[Optional[dict], Optional[dict]]:
    """按日期取最新两个不同日期的行（每日期保留最后一行，防手工重放重复）。"""
    if not path.exists():
        return None, None
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
        if d:
            by_date[d] = r
    if not by_date:
        return None, None
    dates = sorted(by_date)
    today = by_date[dates[-1]]
    prev = by_date[dates[-2]] if len(dates) >= 2 else None
    return prev, today


def _break_direction(spx: Optional[float], prev_sa: dict, new_state: str) -> Optional[str]:
    """破箱方向：优先按 昨日箱体 vs 今日价 的事实比较；箱体不可得时退回
    新状态方向（TREND_UP/DOWN）；MIXED 且无箱体 → None（省略方向行）。"""
    lo, hi = prev_sa.get("band_lo"), prev_sa.get("band_hi")
    if spx is not None and lo is not None and hi is not None:
        if spx > float(hi):
            return "up"
        if spx < float(lo):
            return "down"
    return {"TREND_UP": "up", "TREND_DOWN": "down"}.get(new_state)


def _structure_body(old: str, new: str, today_row: dict, prev_row: dict) -> list[str]:
    surf = today_row.get("surface") or {}
    sa = surf.get("structure_axis") or {}
    lines: list[str] = []
    if new == "RANGE":
        day, lo, hi = sa.get("episode_day"), sa.get("band_lo"), sa.get("band_hi")
        if day is not None and lo is not None and hi is not None:
            band_pct = (float(hi) - float(lo)) / ((float(hi) + float(lo)) / 2) * 100.0
            lines.append(f"已确认：过去 {int(day)}TD 困于 {float(lo):,.2f}–{float(hi):,.2f}"
                         f"（{band_pct:.1f}% 箱）")
        ammo = surf.get("ammo") or {}
        if ammo.get("status") == "ok":
            mark = "✓" if ammo.get("ready") else "✗"
            lines.append(f"{_RANGE_AMMO_PREFIX}liquid {_fmt_usd(ammo.get('liquid'))} "
                         f"vs reserve {_fmt_usd(ammo.get('reserve_need'))} {mark}")
        else:
            lines.append(f"{_RANGE_AMMO_PREFIX}n/a（ammo 源不可用，不阻塞通知）")
    elif old == "RANGE":
        spx = ((surf.get("trend_signal") or {}).get("spx"))
        prev_sa = ((prev_row.get("surface") or {}).get("structure_axis") or {})
        direction = _break_direction(spx, prev_sa, new)
        arrow = {"up": "向上", "down": "向下"}.get(direction or "", "")
        px = f" @ {float(spx):,.2f}" if spx is not None else ""
        box = ""
        if prev_sa.get("band_lo") is not None and prev_sa.get("band_hi") is not None:
            box = (f"（原箱体 {float(prev_sa['band_lo']):,.2f}–"
                   f"{float(prev_sa['band_hi']):,.2f}）")
        lines.append(f"{arrow}破箱{px}{box}")
        if direction == "up":
            lines.append(_UP_BREAK_LINE)
        elif direction == "down":
            lines.append(_DOWN_BREAK_LINE)
    return lines


def notify_state_flips(date: Optional[str] = None,
                       log_path: Optional[Path] = None,
                       dry_run: bool = False,
                       _push: Optional[Callable[..., bool]] = None) -> dict:
    """比对最新两行并推送翻转 FYI。返回 {status, date, flips, pushed}。

    date 提供时要求日志最新行就是该日（否则 skip——防止拿陈旧日志误报）；
    _push 仅测试注入。
    """
    path = Path(log_path) if log_path is not None else STATE_SURFACE_LOG
    prev, today = _latest_two_rows(path)
    if today is None or prev is None:
        return {"status": "skipped", "reason": "insufficient_log_rows",
                "date": date, "flips": [], "pushed": 0}
    tdate = str(today.get("date"))
    if date is not None and tdate != str(date):
        return {"status": "skipped", "reason": f"log_latest={tdate}!=asked={date}",
                "date": date, "flips": [], "pushed": 0}
    if today.get("backfill"):
        return {"status": "skipped", "reason": "today_row_is_backfill",
                "date": tdate, "flips": [], "pushed": 0}

    pusher = _push
    esc: Callable[[str], str] = lambda s: s
    if pusher is None and not dry_run:
        from notify.gateway import escape as _gw_escape, push as _gw_push
        pusher, esc = _gw_push, _gw_escape

    flips: list[dict] = []
    pushed = 0
    for axis, field in (("structure", "structure_state"), ("vol", "vol_state")):
        old, new = prev.get(field), today.get(field)
        if not old or not new:                      # F3: n/a 侧跳过不误报
            flips.append({"axis": axis, "skip": "state_na", "old": old, "new": new})
            continue
        old, new = str(old), str(new)
        if old == new:
            continue
        if axis == "structure":
            title = f"结构轴翻转：{old} → {new}"
            body_lines = _structure_body(old, new, today, prev)
        else:
            vix = ((today.get("surface") or {}).get("vol_axis") or {}).get("vix")
            vix_s = f"（VIX {float(vix):.1f}）" if vix is not None else ""
            title = f"Vol 轴翻转：{old} → {new}{vix_s}"
            body_lines = []
        body = "\n".join(body_lines)
        _assert_clean(title + "\n" + body)
        rec = {"axis": axis, "old": old, "new": new, "title": title, "body": body,
               "dedupe_key": f"state_flip_{axis}_{tdate}"}
        if dry_run:
            rec["dry_run"] = True
        else:
            sent = pusher("FYI", "系统状态", title, esc(body),
                          dedupe_key=rec["dedupe_key"])
            rec["sent"] = bool(sent)
            pushed += 1 if sent else 0
        flips.append(rec)
    return {"status": "ok", "date": tdate, "flips": flips, "pushed": pushed}
