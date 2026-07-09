"""SPEC-137 §2 / SPEC-123 §4a — 2026-06-03 `_bcd_001` duplicate-open migration.

Run ON OLDAIR after deploying the code (resolve_log support for
duplicate_open_resolution). Append-only + idempotent: it appends ONE
disambiguation correction event and refuses to append a second time (marker
check). It never edits or deletes existing ledger rows.

Behavior determination (SPEC-123 §4a, dev + Quant, 2026-07-08)
─────────────────────────────────────────────────────────────
The two `open` events under id `2026-06-03_bcd_001` (11:24:03 and 11:24:05)
are a DOUBLE-CLICK / RETRY artifact, not two independent positions:

  * 2 seconds apart, near-identical fields (migration note: "两条 open 字段接近");
  * caused by the id-allocation race the ID_ALLOC_LOCK fix closed — allocation
    ran before the multi-second governance eval, so two concurrent submits both
    computed `_001`;
  * bcd_governance.open_bcd_positions has always counted this id as ONE
    position (duplicate_open_count>0 → 1).

So §4a's "double-click" branch applies. But a plain id-level `void` would nuke
the WHOLE position (the first, real open included), so we disambiguate with an
append-only `correction` carrying `duplicate_open_resolution: "collapse"`:
resolve_log then keeps the first open, drops the collision flag to 0, and the
13:31 correction (target=open) is no longer ambiguous — there is one open.

campaign 归组复核不变: the id stays `_001`, so its degenerate one-member
campaign is unchanged.

Verify after running:
    from logs.trade_log_io import resolve_log
    row = next(r for r in resolve_log() if r["id"] == "2026-06-03_bcd_001")
    assert row["duplicate_open_count"] == 0      # collision resolved
    assert row["open"] is not None               # real position intact
    assert not row["voided"]                     # position NOT voided
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DUP_ID = "2026-06-03_bcd_001"
NOTE = ("SPEC-137 §2 / SPEC-123 §4a：11:24:05 的第二笔 open 系双击/重试误提交"
        "（与 11:24:03 字段一致，2s 间隔，id 分配竞态），非独立仓位。收敛为单笔"
        "真实持仓，清 duplicate_open_count；13:31 的 correction 目标随之不再歧义。")


def _already_applied(load_log) -> bool:
    return any(
        r.get("id") == DUP_ID and r.get("event") == "correction"
        and r.get("duplicate_open_resolution") == "collapse"
        for r in load_log()
    )


def apply_migration() -> int:
    from logs.trade_log_io import append_event, load_log, resolve_log

    opens = [r for r in load_log()
             if r.get("id") == DUP_ID and r.get("event") == "open"]
    if len(opens) < 2:
        print(f"[skip] {DUP_ID}: found {len(opens)} open event(s), no collision "
              f"to migrate (nothing to do)")
        return 0
    if _already_applied(load_log):
        print(f"[idempotent] {DUP_ID}: collapse correction already present — no-op")
        return 0

    ts = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    append_event({
        "id": DUP_ID,
        "event": "correction",
        "timestamp": ts,
        "target_event": "open",
        "fields": {},                      # patch nothing — base_open stays first open
        "duplicate_open_resolution": "collapse",
        "note": NOTE,
    })

    row = next(r for r in resolve_log() if r["id"] == DUP_ID)
    assert row["duplicate_open_count"] == 0, row
    assert row["open"] is not None and not row["voided"], row
    print(f"[done] {DUP_ID}: collapse correction appended; "
          f"duplicate_open_count={row['duplicate_open_count']} (was {len(opens)}), "
          f"position intact (voided={row['voided']})")
    return 1


if __name__ == "__main__":
    apply_migration()
