# SPEC-114 Developer Handoff

**SPEC**: [task/SPEC-114.md](SPEC-114.md)
**Date issued**: 2026-06-06
**Estimated effort**: ~0.5 day (smaller than SPEC-113)
**Status**: pre-implementation. PM ratified 2026-06-06 (alignment conclusion §8 Q2 + Q4).

---

## TL;DR — What you're doing

Two related changes:

1. **Replace `daily_alignment_check.py` → `daily_chain_sanity.py`**: dual-source 验证已结束（Massive 6/3 last run）。新脚本只检查 Schwab 单源的健康度（symbol completeness / row count anomaly / IV completeness / underlying EOD presence）。
2. **`collect_chains.py` SPX/QQQ retry guard**: 18 日数据有 2 次 Schwab 没拉到 SPX/QQQ（11.1% rate），对 SPX CSP Δ0.20 DTE30 formal candidate 有直接影响。给 index symbols 加 3x retry + Telegram alert on final fail.

Telegram 共用现有 `notify/telegram_bot.py` push helper。

---

## Files to change

| File | Action | 说明 |
|---|---|---|
| `research/q041/daily_chain_sanity.py` | **NEW** (~250 lines) | 参考 `daily_alignment_check.py`，删 massive 依赖 + M4 部分 |
| `research/q041/daily_alignment_check.py` | **MOVE** | → `research/q041/_archived/daily_alignment_check.py.2026-06-06` |
| `research/q041/collect_chains.py` | **EDIT** | add `INDEX_SYMBOLS` + `_fetch_with_retry` + alert write |
| `tests/test_chain_sanity.py` | **NEW** | AC-1/2/3 |
| `tests/test_collect_chains_retry.py` | **NEW** | AC-4/5/6 |
| oldair: `~/Library/LaunchAgents/com.spxstrat.q041_chain_sanity.plist` | **NEW** (deploy) | replace archived `q041align.plist` |

---

## Code stubs

### 1. `daily_chain_sanity.py` skeleton

```python
"""Q041 daily Schwab single-source chain sanity check.

Replaces daily_alignment_check.py (which compared Schwab vs Massive).
Massive ended 2026-06-03 (SPEC-114). This script monitors Schwab-only
chain quality on the 17-symbol whitelist.

Daily Telegram report sent regardless; alert only if any sanity check fails.
"""
from __future__ import annotations
import argparse, json, logging, os, sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from research.q041.whitelist import WHITELIST

ET = ZoneInfo("America/New_York")
SCHWAB_ROOT = REPO_ROOT / "data" / "q041_chains"
OUTPUT_PATH = REPO_ROOT / "data" / "q041_chain_sanity_daily.jsonl"
ALERT_STATE_PATH = REPO_ROOT / "data" / "q041_chain_sanity_alert_state.jsonl"
ROLLING_WINDOW = 7  # days for S2 median

# Reuse non-trading-day helper from daily_alignment_check.py
_US_HOLIDAYS_2026 = {...}  # same as alignment_check

@dataclass
class SanityRecord:
    date: str
    s1_symbol_coverage: int  # n_collected
    s1_total: int = 17
    s2_row_anomaly_count: int | None = None  # n_symbols out of band
    s2_anomaly_details: list[str] = None  # ["AAPL n=1800 vs median 2870 (63%)"]
    s3_iv_completeness_pct: float | None = None
    s4_underlying_presence: int | None = None
    alert_fired: bool = False
    notes: str = ""

def _compute_s1(date_dir: Path) -> tuple[int, list[str]]:
    """Count collected whitelist symbols (exclude _underlying)."""
    found = {p.stem for p in date_dir.glob("*.parquet")} - {"_underlying"}
    missing = sorted(set(WHITELIST) - found)
    return len(found), missing

def _compute_s2(date_dir: Path, history_dirs: list[Path]) -> tuple[int, list[str]]:
    """Per-symbol row count vs 7-day rolling median."""
    anomalies = []
    for sym in WHITELIST:
        cur_f = date_dir / f"{sym}.parquet"
        if not cur_f.exists():
            continue
        cur_n = len(pd.read_parquet(cur_f))
        hist_ns = []
        for hd in history_dirs:
            hf = hd / f"{sym}.parquet"
            if hf.exists():
                hist_ns.append(len(pd.read_parquet(hf)))
        if len(hist_ns) < 3:  # not enough history
            continue
        median_n = sorted(hist_ns)[len(hist_ns) // 2]
        if cur_n < 0.5 * median_n or cur_n > 2.0 * median_n:
            anomalies.append(f"{sym} n={cur_n} vs median {median_n} ({100*cur_n/median_n:.0f}%)")
    return len(anomalies), anomalies

def _compute_s3(date_dir: Path) -> tuple[float | None, int]:
    """IV completeness in 0.25-0.75 |Δ| (inherited from M6)."""
    total, valid = 0, 0
    for sym in WHITELIST:
        f = date_dir / f"{sym}.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        if "delta" not in df.columns or "iv" not in df.columns:
            continue
        near = df[df["delta"].abs().between(0.25, 0.75, inclusive="both")]
        total += len(near)
        valid += int((near["iv"].notna() & (near["iv"] > 0.0)).sum())
    if total == 0:
        return None, 0
    return round(100 * valid / total, 1), total

def _compute_s4(date_dir: Path) -> int:
    """Underlying EOD bars present."""
    underlying_f = date_dir / "_underlying.parquet"
    if not underlying_f.exists():
        return 0
    return len(pd.read_parquet(underlying_f))

def _alerts_to_fire(rec: SanityRecord, missing_syms: list[str]) -> list[str]:
    out = []
    if rec.s1_symbol_coverage < rec.s1_total:
        out.append(f"S1: missing symbols: {missing_syms}")
    if rec.s2_row_anomaly_count and rec.s2_row_anomaly_count > 0:
        out.append(f"S2: row anomaly: {'; '.join(rec.s2_anomaly_details[:5])}")
    if rec.s3_iv_completeness_pct is not None and rec.s3_iv_completeness_pct < 95.0:
        out.append(f"S3: IV completeness {rec.s3_iv_completeness_pct:.1f}% < 95%")
    if rec.s4_underlying_presence is not None and rec.s4_underlying_presence < rec.s1_total:
        out.append(f"S4: underlying EOD {rec.s4_underlying_presence}/{rec.s1_total}")
    return out

def main():
    # parse --date arg (default = today ET)
    # ... determine target_date
    # ... check non-trading-day → write skip record, exit
    # ... locate date_dir + last 7 history dirs
    # ... compute S1/S2/S3/S4
    # ... build SanityRecord
    # ... alerts = _alerts_to_fire(...)
    # ... build report text + alert text
    # ... append OUTPUT_PATH
    # ... if alerts: write ALERT_STATE_PATH + push Telegram alert
    # ... always push daily Telegram report
    pass

if __name__ == "__main__":
    main()
```

参考 `daily_alignment_check.py` 中 Telegram push helpers / non-trading-day logic / argparse — 直接复用。删除所有 `_compute_m1 / _compute_m4 / massive_*` 代码。

### 2. `collect_chains.py` retry guard

定位现有 fetch 调用点（grep `get_option_chain`）并替换。

```python
import time
INDEX_SYMBOLS = {"SPX", "QQQ"}
INDEX_RETRY_MAX = 3
INDEX_RETRY_BACKOFF_SEC = 30
COLLECTOR_ALERT_PATH = REPO_ROOT / "data" / "q041_collector_alert.jsonl"

def _fetch_chain_with_retry(sym: str, *, logger=None) -> pd.DataFrame | None:
    attempts = INDEX_RETRY_MAX if sym in INDEX_SYMBOLS else 1
    last_err = None
    for i in range(attempts):
        try:
            df = _fetch_chain(sym)
            if df is not None and len(df) > 0:
                if i > 0 and logger:
                    logger.info(f"{sym} fetch succeeded on attempt {i+1}/{attempts}")
                return df
            last_err = "empty_chain"
        except Exception as e:
            last_err = repr(e)
        if logger:
            logger.warning(f"{sym} fetch attempt {i+1}/{attempts}: {last_err}")
        if i < attempts - 1:
            time.sleep(INDEX_RETRY_BACKOFF_SEC)
    # final fail
    if sym in INDEX_SYMBOLS:
        _emit_collector_alert(sym, last_err)
    return None

def _emit_collector_alert(symbol: str, reason: str) -> None:
    rec = {
        "date": date.today().isoformat(),
        "symbol": symbol,
        "reason": f"empty_chain_after_{INDEX_RETRY_MAX}_retries:{reason}",
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
    }
    with open(COLLECTOR_ALERT_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    # Telegram
    try:
        from notify.telegram_bot import push_message  # adjust to actual helper
        push_message(
            f"🚨 Q041 Collector Failure\n"
            f"{symbol} chain fetch failed {INDEX_RETRY_MAX}x at "
            f"{datetime.now(ET).strftime('%H:%M ET')}.\n"
            f"Q041 SPX CSP DTE30 signal will be UNAVAILABLE today."
            if symbol == "SPX" else
            f"🚨 Q041 Collector Failure\n"
            f"{symbol} chain fetch failed {INDEX_RETRY_MAX}x at "
            f"{datetime.now(ET).strftime('%H:%M ET')}."
        )
    except Exception as e:
        logging.warning(f"Telegram alert failed: {e}")
```

主循环用 `_fetch_chain_with_retry(sym)` 替换原 `_fetch_chain(sym)`.

### 3. `com.spxstrat.q041_chain_sanity.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.spxstrat.q041_chain_sanity</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/macbook/SPX_strat/venv/bin/python</string>
    <string>-m</string>
    <string>research.q041.daily_chain_sanity</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/macbook/SPX_strat</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>45</integer><key>Weekday</key><integer>1</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>45</integer><key>Weekday</key><integer>2</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>45</integer><key>Weekday</key><integer>3</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>45</integer><key>Weekday</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>45</integer><key>Weekday</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key>
  <string>/Users/macbook/SPX_strat/logs/q041_chain_sanity.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/macbook/SPX_strat/logs/q041_chain_sanity.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/Users/macbook/SPX_strat/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
```

---

## Test plan

```bash
# Unit tests
arch -arm64 venv/bin/python -m pytest tests/test_chain_sanity.py tests/test_collect_chains_retry.py -v

# AC-1 (good day)
arch -arm64 venv/bin/python -m research.q041.daily_chain_sanity --date 2026-06-03

# AC-2 (5/12 known SPX/QQQ missing)
arch -arm64 venv/bin/python -m research.q041.daily_chain_sanity --date 2026-05-12
# expect S1=15/17 + Telegram alert

# AC-3 (Memorial Day)
arch -arm64 venv/bin/python -m research.q041.daily_chain_sanity --date 2026-05-25
# expect skipped:non_trading_day record, no alert

# Deploy
scp com.spxstrat.q041_chain_sanity.plist oldair:~/Library/LaunchAgents/
ssh oldair launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_chain_sanity.plist

# AC-7 (wait for next 16:45 ET → check output)
ssh oldair "tail -1 /Users/macbook/SPX_strat/data/q041_chain_sanity_daily.jsonl"
```

---

## AC checklist

- [ ] AC-1 — clean day: S1=17/17, S2=0, S3=100%, S4=17/17, no alert
- [ ] AC-2 — 5/12 missing day: S1=15/17 + alert text `S1: missing symbols: [QQQ, SPX]`
- [ ] AC-3 — non-trading-day: skip record, no alert
- [ ] AC-4 — SPX 3 retries fail: write collector_alert + Telegram push
- [ ] AC-5 — SPX retry 2 succeed: write parquet normally, no alert
- [ ] AC-6 — Non-index sym fail: silent skip (existing behavior preserved)
- [ ] AC-7 — launchd: next 16:45 ET trigger writes sanity record

---

## Deploy

```bash
# After all ACs green locally
git push origin main
ssh oldair "cd ~/SPX_strat && git pull"
# scp the new plist
scp com.spxstrat.q041_chain_sanity.plist oldair:~/Library/LaunchAgents/
ssh oldair "launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_chain_sanity.plist"
# verify
ssh oldair "launchctl list | grep q041"
```

Expected post-deploy:
```
-  0  com.spxstrat.q041_collect       (existing)
-  0  com.spxstrat.q041_chain_sanity  (new)
```

---

## Notes

- **No backtest cache refresh needed** — monitoring layer only.
- **No production runtime impact** — `selector.py`/`catalog.py` untouched.
- 第一周 daily Telegram 报告 — PM 看格式是否 OK，必要时 fine-tune label / icon.
- `data/q041_overlap_daily.jsonl` 历史保留（read-only），新 `q041_chain_sanity_daily.jsonl` 平行开始写。

---

## Open questions for dev

1. `notify/telegram_bot.py` push helper 的实际函数签名（`push_message(text)` / `send_alert(channel, text)` / 别的）— 用 grep 确认后调用。
2. `_fetch_chain` 的实际函数名 + 是否已经有 retry/timeout wrapper — 改造前先 verify。
3. 17-symbol whitelist 当前 `research/q041/whitelist.py::WHITELIST` 是 17 项还是 18 项 — 确认匹配 SPEC-114 §3 S1 假设。

ping Quant 如果其中任何一条有歧义。

---

## Cross-references

- [task/SPEC-114.md](SPEC-114.md) — spec
- [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md)
- [research/q041/daily_alignment_check.py](../research/q041/daily_alignment_check.py) — 旧脚本，改名归档
- [research/q041/collect_chains.py](../research/q041/collect_chains.py) — 收集器
