#!/bin/bash
# SPEC-117.1 — L1 daily pull backup of oldair's non-regenerable data.
# Runs on the LOCAL machine (lienchen) via com.spxstrat.local_backup_pull.plist (05:00).
#
# Layers:
#   L1 (this script, daily):  oldair data/ + secrets -> ~/backups/oldair/
#   L2 (weekly, Sunday branch below): data-only tar.zst -> iCloud Drive
#       (secrets deliberately excluded from L2; they stay on the FileVault-
#        encrypted local disk only)
#   L3 (quarterly, manual): restore drill — checksum-compare one day's
#       SPX.parquet against oldair (see SPEC-117 completion report for the
#       first drill's evidence).
#
# On L1 success we touch a marker ON OLDAIR so the oldair-side heartbeat
# monitor (SPEC-117.6) can assert backup freshness without reaching back
# into this machine.
set -uo pipefail

DEST="$HOME/backups/oldair"
LOG="$HOME/Library/Logs/spx-strat-local/backup_pull.log"
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/spxstrat-backup"
MARKER="SPX_strat/data/.last_backup_pull"

mkdir -p "$DEST/data" "$DEST/secrets" "$(dirname "$LOG")"
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

fail=0

# ── L1: data (includes q041_chains / historical / all ledgers) ────────────────
rsync -az --delete \
  --exclude "market_cache/" \
  --exclude "__pycache__" \
  oldair:SPX_strat/data/ "$DEST/data/" >> "$LOG" 2>&1 || fail=1

# ── L1: secrets (tokens, tunnel creds, env) ───────────────────────────────────
rsync -az oldair:.spxstrat/ "$DEST/secrets/spxstrat/" >> "$LOG" 2>&1 || fail=1
rsync -az oldair:.cloudflared/ "$DEST/secrets/cloudflared/" >> "$LOG" 2>&1 || fail=1
rsync -az oldair:SPX_strat/.env "$DEST/secrets/env" >> "$LOG" 2>&1 || fail=1

if [ "$fail" -eq 0 ]; then
  ssh oldair "touch $MARKER" >> "$LOG" 2>&1 || true
  log "L1 pull OK ($(du -sh "$DEST" 2>/dev/null | cut -f1))"
else
  log "L1 pull FAILED — see above"
fi

# ── L2: weekly data-only archive to iCloud (Sundays) ─────────────────────────
if [ "$(date +%u)" = "7" ] && [ "$fail" -eq 0 ]; then
  mkdir -p "$ICLOUD_DIR"
  wk="$ICLOUD_DIR/oldair-data-$(date +%Y%m%d).tar.gz"
  tar czf "$wk" -C "$DEST" data >> "$LOG" 2>&1 \
    && log "L2 weekly archive OK -> $wk" \
    || log "L2 weekly archive FAILED"
  # retention: keep last 8 weekly archives
  ls -t "$ICLOUD_DIR"/oldair-data-*.tar.gz 2>/dev/null | tail -n +9 | xargs rm -f 2>/dev/null
fi

exit $fail
