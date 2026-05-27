"""One-shot backfill: mark 2026-05-22..2026-05-25 daily_snapshot rows as
partial because E*Trade refresh-token had expired and combined_nlv was
silently computed as schwab-only.

Rewrites data/daily_snapshot.jsonl in place:
  - combined_nlv  → None (was schwab_nlv-only)
  - partial_accounts → ["etrade"]

Safe to re-run — idempotent. Run from repo root:
    venv/bin/python scripts/_backfill_partial_etrade_2026_05_22_25.py
"""

import json
import shutil
from pathlib import Path

TARGET_DATES = {"2026-05-22", "2026-05-23", "2026-05-24", "2026-05-25"}


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    src = repo / "data" / "daily_snapshot.jsonl"
    if not src.exists():
        print(f"FAIL — {src} missing")
        return 1
    backup = src.with_suffix(".jsonl.bak-partial-etrade")
    shutil.copy2(src, backup)
    print(f"backup: {backup}")

    out_lines: list[str] = []
    edits = 0
    for raw in src.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        if row.get("date") in TARGET_DATES:
            etrade_nlv = (row.get("accounts") or {}).get("etrade", {}).get("nlv")
            if etrade_nlv is None and not row.get("partial_accounts"):
                row["combined_nlv"] = None
                row["partial_accounts"] = ["etrade"]
                edits += 1
                print(f"  {row['date']}: combined_nlv→null  partial_accounts=['etrade']")
        out_lines.append(json.dumps(row, ensure_ascii=False))

    src.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nedited {edits} rows; total rows={len(out_lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
