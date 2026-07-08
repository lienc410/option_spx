"""SPEC-117.6 — central ops heartbeat monitor (D-1 proposal A).

Runs on oldair 17:30 ET Mon-Fri (after every producer job's window). Checks:
  1. launchctl exit/PID state for every registered com.spxstrat.* job
     (keepalive jobs must have a live PID; calendar jobs' last exit must be
      in the registry's allow_exit)
  2. output freshness assertions from ops/heartbeat_registry.json
     (catches "job never ran" — the blind spot of self-reporting)
  3. registry coverage: any com.spxstrat.* label seen in launchctl but
     missing from the registry is itself a violation (new jobs must register)

Telegram: violations → 🚨 detail list; all green → single ✅ line (the daily
green line doubles as the reverse heartbeat: no line = monitor itself is dead).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

ET = ZoneInfo("America/New_York")
REGISTRY = ROOT / "ops" / "heartbeat_registry.json"

_US_HOLIDAYS = frozenset({
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26",
    "2027-05-31", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
})


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in _US_HOLIDAYS


def _launchctl_state() -> dict[str, dict]:
    """label -> {pid: int|None, exit: int} for com.spxstrat.* jobs."""
    out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    state: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or "com.spxstrat" not in parts[2]:
            continue
        pid = int(parts[0]) if parts[0].strip().isdigit() else None
        try:
            code = int(parts[1])
        except ValueError:
            code = 0
        state[parts[2].strip()] = {"pid": pid, "exit": code}
    return state


def _check_freshness(spec: dict, now: datetime) -> str | None:
    """Return violation string or None."""
    raw = spec["path"].replace("{today}", now.date().isoformat())
    p = Path(raw) if raw.startswith("/") else ROOT / raw
    rule = spec.get("rule", "daily_26h")

    if rule == "trading_day" and not _is_trading_day(now.date()):
        return None  # nothing expected on non-trading days

    if not p.exists():
        return f"missing output {raw}"
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=ET)

    if rule == "trading_day":
        if mtime.date() < now.date():
            return f"stale output {raw} (mtime {mtime:%m-%d %H:%M}, expected today)"
    elif rule == "weekly_8d":  # Sunday jobs: one missed week + 1 day grace
        if (now - mtime) > timedelta(days=8):
            return f"stale output {raw} (mtime {mtime:%m-%d %H:%M}, >8d old)"
    else:  # daily_26h
        if (now - mtime) > timedelta(hours=26):
            return f"stale output {raw} (mtime {mtime:%m-%d %H:%M}, >26h old)"
    return None


DEFERRED_MD = ROOT / "task" / "DEFERRED.md"


def _is_first_monday(d: date) -> bool:
    return d.weekday() == 0 and d.day <= 7


def _deferred_digest(now: datetime, path: Path | None = None) -> str | None:
    """SPEC-124 §4 — monthly exposure of the deferred-items ledger.

    On the first Monday of each month, summarize task/DEFERRED.md: overdue
    rows (复核期限 column parses as a date < today) pinned on top, plus counts
    of upcoming/date-less (条件/事件挂起) rows. Returns None on other days or
    when the ledger is missing/empty."""
    if not _is_first_monday(now.date()):
        return None
    p = path or DEFERRED_MD
    if not p.exists():
        return None
    overdue: list[str] = []
    upcoming = conditional = 0
    import re as _re
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| #") or set(line) <= {"|", "-", " "}:
            continue
        # split on UNESCAPED pipes only — item names may contain "\|"
        # (e.g. "LOW_VOL\|NEUTRAL 格改路由")
        cells = [c.strip().replace("\\|", "|")
                 for c in _re.split(r"(?<!\\)\|", line.strip("|"))]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        item, deadline, owner = cells[1], cells[4], cells[5]
        m = None
        for tok in deadline.replace("～", " ").replace("~", " ").split():
            try:
                m = date.fromisoformat(tok)
                break
            except ValueError:
                continue
        if m is None:
            conditional += 1
        elif m < now.date():
            overdue.append(f"  ⏰ #{cells[0]} {item}（期限 {m.isoformat()}，owner {owner}）")
        else:
            upcoming += 1
    if not (overdue or upcoming or conditional):
        return None
    head = f"📒 DEFERRED 台账月度摘要 {now:%Y-%m}（每月首个周一自动推送）"
    lines = [head]
    if overdue:
        lines.append(f"逾期未复核 {len(overdue)} 项（置顶）：")
        lines.extend(overdue)
    lines.append(f"在期 {upcoming} 项 · 条件/事件挂起 {conditional} 项 · 全文 task/DEFERRED.md")
    # SPEC-132 — Q090 前瞻证据流 n 进度（重开条件进度条，随同一月度 FYI 走）
    try:
        from strategy.structure_map import progress
        p = progress()
        lines.append(
            f"Structure Map 证据积累: 已记 {p['days_logged']} 天 · "
            f"墙触发样本 {p['s3_n']}/{p['s3_target']}（攒满可正式检验）· "
            f"当日贴墙样本 {p['s1s_n']}/{p['s1s_target']}（攒满可重开研究）")
    except Exception:
        pass  # non-fatal — digest 主体照发
    return "\n".join(lines)


def run(now: datetime | None = None, *, dry_run: bool = False) -> list[str]:
    now = now or datetime.now(ET)
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    jobs = reg["jobs"]
    lc = _launchctl_state()
    violations: list[str] = []

    registered = {j["label"] for j in jobs}
    for label in lc:
        if label not in registered:
            violations.append(f"{label}: not in heartbeat registry — register it")

    for j in jobs:
        label = j["label"]
        kind = j.get("kind", "calendar")

        if kind == "marker":
            v = _check_freshness(j["freshness"], now)
            if v:
                violations.append(f"{label}: {v}")
            continue

        st = lc.get(label)
        if st is None:
            violations.append(f"{label}: not loaded in launchd")
            continue
        if kind == "keepalive" and st["pid"] is None:
            violations.append(f"{label}: keepalive job has no live PID (last exit {st['exit']})")
        allow = j.get("allow_exit", [0])
        if st["exit"] not in allow and st["pid"] is None:
            violations.append(f"{label}: last exit {st['exit']} (allowed {allow})")
        if "freshness" in j:
            v = _check_freshness(j["freshness"], now)
            if v:
                violations.append(f"{label}: {v}")

    # H-4: surface Telegram delivery counters — a final send failure (both
    # HTML and plain-text attempts dead) is a violation; fallback-only days
    # get an FYI line so formatting bugs stay visible without alarming.
    push_note = ""
    try:
        stats_path = ROOT / "logs" / "push_stats.json"
        if stats_path.exists():
            stats = json.loads(stats_path.read_text())
            d = stats.get(now.date().isoformat(), {})
            failed, fb = int(d.get("failed", 0)), int(d.get("fallback", 0))
            if failed:
                violations.append(f"push: {failed} 条推送两次发送均失败（sent {d.get('sent', 0)}, fallback {fb}）")
            elif fb:
                push_note = f"\n  ℹ push: {fb} 条降级为纯文本送达（HTML parse 失败）"
    except Exception:
        pass

    n = len(jobs)
    if violations:
        msg = f"🚨 ops heartbeat {now:%m-%d %H:%M} — {len(violations)} violation(s) / {n} jobs\n" + \
              "\n".join(f"  · {v}" for v in violations[:15]) + push_note
    else:
        msg = f"✅ ops {n}/{n} green · {now:%m-%d %H:%M}" + push_note

    digest = _deferred_digest(now)

    if dry_run:
        print(msg)
        if digest:
            print(digest)
    else:
        from notify.gateway import escape, push as gw_push
        # SPEC-126: violations need attention (ACTION, rings); the daily green
        # line and the monthly DEFERRED digest are FYI (silent). Bodies are
        # plain text (violation strings can carry '<') → whole-body escape.
        gw_push("ACTION" if violations else "FYI", "系统状态", "", escape(msg))
        if digest:
            gw_push("FYI", "系统状态", "", escape(digest))
        print(msg)
    return violations


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="SPEC-117.6 ops heartbeat")
    p.add_argument("--dry-run", action="store_true", help="print, no Telegram")
    args = p.parse_args()
    run(dry_run=args.dry_run)
    return 0   # heartbeat itself always exits 0; violations travel via Telegram


if __name__ == "__main__":
    sys.exit(main())
