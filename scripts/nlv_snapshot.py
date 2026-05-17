"""Daily NLV snapshot — runs at market close to record combined account NLV.

Idempotent: skips if today's date already recorded. Feeds /api/portfolio/nlv-change
which computes today's $ + % change vs previous trading day for the hero strip.
"""
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import pytz

ROOT = Path(__file__).resolve().parents[1]
NLV_HISTORY = ROOT / "data" / "nlv_history.jsonl"
ET = pytz.timezone("America/New_York")
API_URL = "http://127.0.0.1:5050/api/portfolio/summary"


def _today_et() -> str:
    return datetime.now(ET).date().isoformat()


def _already_recorded(date_str: str) -> bool:
    if not NLV_HISTORY.exists():
        return False
    with NLV_HISTORY.open() as f:
        for line in f:
            try:
                if json.loads(line).get("date") == date_str:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def main() -> int:
    today = _today_et()
    if _already_recorded(today):
        print(f"[nlv_snapshot] already recorded for {today}")
        return 0

    try:
        with urllib.request.urlopen(API_URL, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as exc:
        print(f"[nlv_snapshot] failed to fetch summary: {exc}", file=sys.stderr)
        return 1

    accounts = data.get("account_breakdown") or {}
    schwab_nlv = accounts.get("schwab_nlv")
    etrade_nlv = accounts.get("etrade_nlv")

    if not isinstance(schwab_nlv, (int, float)) or schwab_nlv <= 0:
        print(f"[nlv_snapshot] schwab_nlv invalid ({schwab_nlv}) — aborting", file=sys.stderr)
        return 1

    combined = float(schwab_nlv) + (float(etrade_nlv) if isinstance(etrade_nlv, (int, float)) else 0.0)
    rec = {
        "date": today,
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "schwab_nlv": round(float(schwab_nlv), 2),
        "etrade_nlv": round(float(etrade_nlv), 2) if isinstance(etrade_nlv, (int, float)) else None,
        "combined_nlv": round(combined, 2),
    }

    NLV_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with NLV_HISTORY.open("a") as f:
        f.write(json.dumps(rec) + "\n")

    print(f"[nlv_snapshot] saved date={today} combined=${combined:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
