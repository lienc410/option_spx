#!/bin/bash
# Weekly service recycle — Sunday 08:00 ET (PM ratified 2026-07-07; the
# monthly full-machine reboot was explicitly declined as too risky for a
# gui/501 LaunchAgent stack — services recycle instead).
#
# 1. rotate oversized launchd logs (bot.err.log reached 119MB on 7/7 —
#    httpx INFO every 10s; the logger is also being quieted in code, this
#    is the backstop). Keeps one .1.gz generation.
# 2. kickstart the long-lived processes: bot (PTB+APScheduler, observed
#    graceful self-exits on Telegram 502 bursts), both cloudflared tunnels.
#    web is NOT touched here — it already restarts nightly at 04:00.
# 3. touch the heartbeat marker (registry rule weekly_8d).
set -u
LOGDIR="$HOME/Library/Logs/spx-strat"
MARKER="$HOME/SPX_strat/data/.last_weekly_recycle"
MAX_BYTES=$((50 * 1024 * 1024))

for f in "$LOGDIR"/*.log; do
  [ -f "$f" ] || continue
  size=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if [ "$size" -gt "$MAX_BYTES" ]; then
    gzip -c "$f" > "$f.1.gz"      # overwrite previous generation
    : > "$f"                       # truncate in place (launchd keeps the fd)
    echo "$(date '+%F %T') rotated $f ($size bytes)"
  fi
done

for label in com.spxstrat.bot com.spxstrat.cloudflared com.spxstrat.cloudflared-b; do
  /bin/launchctl kickstart -k "gui/$(id -u)/$label" && \
    echo "$(date '+%F %T') recycled $label"
done

touch "$MARKER"
