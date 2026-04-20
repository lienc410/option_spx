#!/usr/bin/env bash
# capture_oldair_502_snapshot.sh — 在 old Air 上抓取 502 故障快照
# 用法：
#   bash scripts/capture_oldair_502_snapshot.sh
#   bash scripts/capture_oldair_502_snapshot.sh "after-login-502"
#
# 输出：
#   logs/oldair_502_snapshot_<timestamp>[_label].txt

set -u

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$PROJ_DIR/logs"
TS="$(date +"%Y%m%d_%H%M%S")"
LABEL="${1:-}"
SAFE_LABEL=""

if [ -n "$LABEL" ]; then
  SAFE_LABEL="_$(printf '%s' "$LABEL" | tr ' ' '_' | tr -cd '[:alnum:]_-')"
fi

OUT_FILE="$OUT_DIR/oldair_502_snapshot_${TS}${SAFE_LABEL}.txt"
mkdir -p "$OUT_DIR"

cat > "$OUT_FILE" <<EOF
=== old Air 502 Snapshot ===
Local timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Optional label: ${LABEL:-<none>}

Browser notes to fill manually:
- 502 page UTC timestamp:
- Final URL after Access login:
- Any browser/network observations:

EOF

echo "Writing snapshot to: $OUT_FILE"

{
  echo "=== Local Public Check ==="
  date -u +"UTC now: %Y-%m-%dT%H:%M:%SZ"
  echo
  echo "--- curl -I https://www.portimperialventures.com/ ---"
  curl -I --max-time 10 https://www.portimperialventures.com/ || true
  echo
} >> "$OUT_FILE" 2>&1

ssh oldair 'bash -s' >> "$OUT_FILE" 2>&1 <<'EOF'
set +e

section() {
  printf '\n=== %s ===\n' "$1"
}

run() {
  local title="$1"
  shift
  printf '\n--- %s ---\n' "$title"
  "$@"
  local status=$?
  printf '[exit=%s]\n' "$status"
}

section "Remote Identity"
run "date -u" date -u +"%Y-%m-%dT%H:%M:%SZ"
run "hostname" hostname
run "ifconfig (192.168.68.x)" /bin/sh -lc "ifconfig | grep 'inet 192.168.68.'"

section "launchd Status"
run "launchctl print web" /bin/sh -lc "launchctl print gui/\$(id -u)/com.spxstrat.web | sed -n '1,80p'"
run "launchctl print cloudflared" /bin/sh -lc "launchctl print gui/\$(id -u)/com.spxstrat.cloudflared | sed -n '1,100p'"
run "launchctl print cloudflared-b" /bin/sh -lc "launchctl print gui/\$(id -u)/com.spxstrat.cloudflared-b | sed -n '1,100p'"

section "Local Origin Health"
run "curl root via 127.0.0.1" /bin/sh -lc "curl -sS -o /dev/null -D - http://127.0.0.1:5050/ | sed -n '1,20p'"
run "curl recommendation via 127.0.0.1" /bin/sh -lc "curl -sS -o /dev/null -D - http://127.0.0.1:5050/api/recommendation | sed -n '1,20p'"
run "curl performance via 127.0.0.1" /bin/sh -lc "curl -sS -o /dev/null -D - http://127.0.0.1:5050/api/performance/live | sed -n '1,20p'"
run "curl root via localhost" /bin/sh -lc "curl -sS -o /dev/null -D - http://localhost:5050/ | sed -n '1,20p'"

section "Cloudflared Metrics"
run "cloudflared metrics summary (primary :60123)" /bin/sh -lc "curl -sS http://127.0.0.1:60123/metrics | egrep 'cloudflared_(tunnel_(total_requests|request_errors|ha_connections|response_by_code)|proxy_connect_streams_errors)' | sort"
run "cloudflared metrics summary (secondary :60124)" /bin/sh -lc "curl -sS http://127.0.0.1:60124/metrics | egrep 'cloudflared_(tunnel_(total_requests|request_errors|ha_connections|response_by_code)|proxy_connect_streams_errors)' | sort"

section "Process Snapshot"
run "ps cloudflared" /bin/sh -lc "ps aux | grep cloudflared | grep -v grep"
run "listening 5050" /bin/sh -lc "lsof -nP -iTCP:5050 -sTCP:LISTEN"

section "Cloudflare Tunnel Config"
run "config.yml" sed -n "1,120p" /Users/macbook/.cloudflared/config.yml
run "config-connector-b.yml" sed -n "1,120p" /Users/macbook/.cloudflared/config-connector-b.yml

section "Recent Logs"
run "tail cloudflared err" tail -n 120 /Users/macbook/Library/Logs/cloudflared/err.log
run "tail cloudflared err-b" tail -n 120 /Users/macbook/Library/Logs/cloudflared/err-b.log
run "tail web err" tail -n 120 /Users/macbook/Library/Logs/spx-strat/web.err.log
EOF

echo "Snapshot complete: $OUT_FILE"
