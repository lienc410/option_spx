"""One-shot: patch today's daily_snapshot row with v4 BP split fields.

Run once on oldair after deploying the v4 schema bump. Without this,
today's row stays on v3 (no options/equity split) and the journal BP
chart falls back to legacy behavior for today only. Tomorrow's 16:30 ET
snapshot writes v4 natively.
"""
from __future__ import annotations
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
import pytz

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "daily_snapshot.jsonl"
ET = pytz.timezone("America/New_York")
BASE = "http://127.0.0.1:5050"


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _r(v, dec=2):
    n = _num(v)
    return round(n, dec) if n is not None else None


def main() -> int:
    today = datetime.now(ET).date().isoformat()
    if not HISTORY.exists():
        print("[patch] no daily_snapshot.jsonl yet", file=sys.stderr)
        return 1
    rows = []
    with open(HISTORY) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        print("[patch] daily_snapshot.jsonl empty", file=sys.stderr)
        return 1

    # Find today's row
    target_idx = None
    for i, r in enumerate(rows):
        if r.get("date") == today:
            target_idx = i
            break
    if target_idx is None:
        print(f"[patch] no row for {today} — nothing to patch", file=sys.stderr)
        return 0

    try:
        with urllib.request.urlopen(f"{BASE}/api/portfolio/summary", timeout=30) as resp:
            summary = json.loads(resp.read())
    except Exception as exc:
        print(f"[patch] /api/portfolio/summary failed: {exc}", file=sys.stderr)
        return 1

    buckets = summary.get("bp_usage_by_bucket") or {}
    accounts = summary.get("account_breakdown") or {}
    schwab_m = _num(accounts.get("schwab_maintenance_margin")) or 0.0
    etrade_m = _num(accounts.get("etrade_maintenance_margin")) or 0.0
    schwab_eq_d = _num(buckets.get("equity_margin_dollars")) or 0.0
    etrade_eq_d = _num(buckets.get("etrade_equity_dollars")) or 0.0
    options_d = max(0.0, (schwab_m - schwab_eq_d) + (etrade_m - etrade_eq_d))
    equity_d  = schwab_eq_d + etrade_eq_d
    options_pct = (_num(buckets.get("spx_live_bp_pct")) or 0.0) + (_num(buckets.get("etrade_options_bp_pct")) or 0.0)
    equity_pct  = (_num(buckets.get("equity_margin_bp_pct")) or 0.0) + (_num(buckets.get("etrade_equity_bp_pct")) or 0.0)

    spx_block = rows[target_idx].setdefault("strategies", {}).setdefault("spx_spread", {})
    spx_block["options_bp_pct"]     = _r(options_pct, 2)
    spx_block["equity_bp_pct"]      = _r(equity_pct, 2)
    spx_block["options_bp_dollars"] = _r(options_d, 2)
    spx_block["equity_bp_dollars"]  = _r(equity_d, 2)
    rows[target_idx]["schema_version"] = 4

    with open(HISTORY, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"[patch] {today} options={options_pct:.2f}% (${options_d:.0f}) "
          f"equity={equity_pct:.2f}% (${equity_d:.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
