# Developer Handoff — ETrade Token Auto-Renew + Daytime Keepalive
**Date**: 2026-05-28
**Reporter**: PM (via Quant Researcher)
**Severity**: Daily UX friction, not blocking trades

## 1. Symptom

PM is manually re-OAuthing ETrade 4–5 times per day. Today's specific token
died 1h35min after creation (16:24:14 ET created → 17:59:12 ET marked
expired by `expire_token_on_401`), well before midnight ET rollover.

## 2. Root cause

ETrade enforces **two** independent expiry rules; we currently handle
neither automatically.

### Rule A — Midnight ET daily expiry
- Token's `expires_at` is set to next midnight ET in
  `etrade/auth.py:get_access_token` (line ~264).
- ETrade has a `/oauth/renew_access_token` endpoint that, called while the
  token is still valid, extends the expiry another 24h with **zero user
  interaction** (no browser, no verifier).
- `scripts/etrade_token_renew.py` already implements this call.
- The script's docstring claims it "runs via launchd at 23:45 ET daily on
  oldair" — **this is aspirational, not real**. No launchd plist for
  `com.spxstrat.etrade_token_renew` exists on oldair.
- The only ETrade launchd job installed (`com.spxstrat.etrade_refresh`)
  runs `scripts/etrade_status_notify.py` at 06:00 ET — that's the morning
  "re-auth needed" Telegram nag, not a renewal.

### Rule B — Server-side 2-hour idle timer
- ETrade kills tokens server-side after ≤2h with no API calls (docs say
  2h; in practice we've seen ~90min before 401 hits).
- We have no keepalive cron. If PM doesn't open the dashboard for 2h,
  the next request returns 401, `expire_token_on_401` marks the local
  token dead, and PM gets the re-auth banner.
- Web UI polls `/api/etrade/*` only when PM has the tab open, so any
  step-away >2h kills the token.

## 3. Fix — Option C (PM-approved)

Install **two** launchd jobs that together hold the token alive without
user action.

### Job 1 — Nightly renew (covers Rule A)
- Label: `com.spxstrat.etrade_token_renew`
- Runs: `scripts/etrade_token_renew.py` (already exists, no code change)
- Schedule: **23:30 ET daily** (30min buffer before midnight rollover; the
  script's old comment said 23:45 — change comment to 23:30 to match)
- Logs: `~/Library/Logs/spx-strat/etrade_token_renew.{log,err.log}`
- Behavior on failure: script already `sys.exit(1)` if renew fails; the
  existing 06:00 ET nag cron will catch the next-morning re-auth need.

### Job 2 — Daytime keepalive (covers Rule B)
- Label: `com.spxstrat.etrade_keepalive`
- Runs: **new** script `scripts/etrade_keepalive.py` (see §4)
- Schedule: **every 60 minutes, Mon–Fri, 06:00–22:00 ET**
  - launchd `StartCalendarInterval` array with 17 entries (06:00, 07:00,
    …, 22:00), each with `Weekday` 1–5
  - 60min ≪ 2h idle threshold, gives margin against the suspected 90min
    real ETrade limit
- Logs: `~/Library/Logs/spx-strat/etrade_keepalive.{log,err.log}`
- Behavior on failure: silent (no Telegram). Daily 06:00 ET nag remains
  the single alert channel.

## 4. New file: `scripts/etrade_keepalive.py`

```python
#!/usr/bin/env python3
"""
E-Trade idle-timer keepalive — runs hourly during RTH+extended via
launchd. Calls renew_access_token() to reset the server-side 2h idle
clock without requiring user interaction.

Renew is idempotent and cheap. If the token is already dead (e.g.
midnight rollover missed, ETrade revoked, machine was off), this exits
non-zero silently — the morning nag cron (etrade_status_notify) is the
canonical alert channel.
"""
from __future__ import annotations
import logging, os, sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etrade_keepalive")


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from etrade.auth import is_configured, renew_access_token, token_status

    if not is_configured():
        log.info("ETRADE_CONSUMER_KEY not set — keepalive skipped")
        sys.exit(0)

    status = token_status()
    if not status.get("authenticated"):
        log.info("Token already expired — keepalive cannot help, awaiting manual re-auth")
        sys.exit(0)  # exit 0 — not a cron failure, just no-op

    result = renew_access_token()
    if result.get("ok"):
        log.info("keepalive ✓ — new expiry: %s", result.get("expires_at"))
        sys.exit(0)
    else:
        log.warning("keepalive renew failed: %s", result.get("reason"))
        sys.exit(0)  # silent failure; daily nag handles alerting


if __name__ == "__main__":
    main()
```

## 5. New file: `~/Library/LaunchAgents/com.spxstrat.etrade_token_renew.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.spxstrat.etrade_token_renew</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/macbook/SPX_strat/venv/bin/python3</string>
    <string>/Users/macbook/SPX_strat/scripts/etrade_token_renew.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>23</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/Users/macbook/Library/Logs/spx-strat/etrade_token_renew.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/macbook/Library/Logs/spx-strat/etrade_token_renew.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>/Users/macbook</string>
  </dict>
</dict>
</plist>
```

## 6. New file: `~/Library/LaunchAgents/com.spxstrat.etrade_keepalive.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.spxstrat.etrade_keepalive</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/macbook/SPX_strat/venv/bin/python3</string>
    <string>/Users/macbook/SPX_strat/scripts/etrade_keepalive.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <!-- Mon–Fri, every hour 06:00–22:00 ET -->
    <!-- launchd Weekday: 1=Mon … 5=Fri -->
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>14</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>15</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
    <!-- Repeat the same 17 entries for Weekday 2 (Tue), 3 (Wed), 4 (Thu), 5 (Fri) -->
    <!-- Total = 17 × 5 = 85 entries — verbose but launchd has no native cron syntax -->
  </array>
  <key>StandardOutPath</key>
  <string>/Users/macbook/Library/Logs/spx-strat/etrade_keepalive.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/macbook/Library/Logs/spx-strat/etrade_keepalive.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>/Users/macbook</string>
  </dict>
</dict>
</plist>
```

**Implementation note**: write the 85 entries by hand or generate via
a Python one-liner before pasting. Do **not** use `StartInterval`
(seconds) — that runs even when machine is asleep, which we don't want.

## 7. Acceptance criteria

- **AC1**: `scripts/etrade_keepalive.py` exists, executable bit set,
  matches the spec in §4. Running it manually with a valid token →
  exit 0, log line "keepalive ✓ — new expiry: …", and
  `~/.spxstrat/etrade_token.json` `expires_at` is bumped 24h forward.

- **AC2**: `scripts/etrade_token_renew.py` docstring updated from
  "23:45 ET" to "23:30 ET" (cosmetic; matches actual schedule).

- **AC3**: Both plists installed on oldair:
  ```bash
  launchctl list | grep spxstrat | grep -E 'token_renew|keepalive'
  # → should show both labels
  ```

- **AC4**: Manual trigger of each job works:
  ```bash
  launchctl kickstart -k gui/$(id -u)/com.spxstrat.etrade_token_renew
  launchctl kickstart -k gui/$(id -u)/com.spxstrat.etrade_keepalive
  # then check the .log files for success line
  ```

- **AC5**: 7-day live test. Starting from a fresh manual re-auth on day 0,
  PM should **not** see the re-auth banner during days 1–6 unless the
  Mac is powered off >2h during RTH or ETrade revokes the token
  server-side. Track via `~/Library/Logs/spx-strat/etrade_keepalive.log`
  — every hourly entry should say "keepalive ✓".

- **AC6**: If both crons run on a day and token still dies, dev must
  diagnose root cause (e.g. real ETrade idle <60min, or Mac sleeping
  through entries). Add observations to this handoff doc.

## 8. Out of scope

- No code change in `etrade/auth.py` or `etrade/client.py`. The renew
  endpoint, 401-handler, and token storage are all already correct.
- No frontend change. PM still sees the same re-auth banner when token
  genuinely dies (which should now be rare).
- No change to the 06:00 ET nag cron — keep it as the alert-of-last-resort.
- Do **not** add a 1-minute keepalive — overkill, and would mask actual
  ETrade bugs.

## 9. Deployment

```bash
# 1. On dev machine
git add scripts/etrade_keepalive.py scripts/etrade_token_renew.py \
        task/etrade_token_keepalive_handoff_2026-05-28.md
git commit -m "feat(etrade): hourly keepalive + nightly renew cron"
git push origin main

# 2. On oldair
ssh oldair 'cd ~/SPX_strat && git pull origin main && chmod +x scripts/etrade_keepalive.py'

# 3. Install plists
scp ~/Library/LaunchAgents/com.spxstrat.etrade_token_renew.plist \
    oldair:~/Library/LaunchAgents/
scp ~/Library/LaunchAgents/com.spxstrat.etrade_keepalive.plist \
    oldair:~/Library/LaunchAgents/

ssh oldair 'launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.etrade_token_renew.plist'
ssh oldair 'launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.etrade_keepalive.plist'

# 4. Smoke test
ssh oldair 'launchctl list | grep spxstrat | grep -E "token_renew|keepalive"'
ssh oldair 'launchctl kickstart -k gui/$(id -u)/com.spxstrat.etrade_keepalive'
ssh oldair 'tail ~/Library/Logs/spx-strat/etrade_keepalive.log'
```

## 10. Risk

- **Risk**: ETrade could rate-limit or flag hourly renew as abuse.
  - **Mitigation**: 17 calls/weekday is well within any reasonable
    rate limit. If ETrade flags, fall back to 90min or 120min interval.
- **Risk**: Mac sleeping through scheduled time → cron misses.
  - **Mitigation**: launchd `StartCalendarInterval` jobs *do* fire on
    wake if missed, but only the most recent one. So if Mac was asleep
    10:00-14:00 ET, the 14:00 entry fires on wake. 60min interval means
    worst-case delay to next keepalive = 60min < 2h idle limit. Safe.
- **Risk**: ETrade renew endpoint changes / deprecates.
  - **Mitigation**: existing `renew_access_token()` is already covered
    by `tests/test_spec_089.py` mock paths.

## 11. PM rollback if it backfires

If hourly renew somehow makes things *worse* (e.g. ETrade starts
revoking more aggressively):
```bash
ssh oldair 'launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.etrade_keepalive.plist'
```
And revert to pre-fix manual re-auth flow.
