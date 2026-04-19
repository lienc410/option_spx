#!/usr/bin/env bash
# check_oldair_cloudflared.sh — 检查 old Air 上 cloudflared / web 本地健康，可选自愈
# 用法：
#   bash scripts/check_oldair_cloudflared.sh
#   bash scripts/check_oldair_cloudflared.sh --heal
#
# 设计原则：
# - 只检查 old Air 本地 origin 与 tunnel metrics
# - 不使用公网 URL 作为自愈触发条件
# - 连续 2 次失败才会重启 cloudflared

set -euo pipefail

HEAL=0
if [[ "${1:-}" == "--heal" ]]; then
  HEAL=1
fi

ssh oldair 'bash -s' "$HEAL" <<'EOF'
set -euo pipefail

HEAL="${1:-0}"
STATE_DIR="/Users/macbook/Library/Caches/spx-strat"
STATE_FILE="$STATE_DIR/cloudflared_health_failures.txt"
METRICS_URL="http://127.0.0.1:60123/metrics"
ROOT_URL="http://127.0.0.1:5050/"
SERVICE="gui/$(id -u)/com.spxstrat.cloudflared"
mkdir -p "$STATE_DIR"

failures=0
if [[ -f "$STATE_FILE" ]]; then
  failures="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
fi
if [[ ! "$failures" =~ ^[0-9]+$ ]]; then
  failures=0
fi

status_ok=1
root_ok=1
metrics_ok=1
ha_connections=""
request_errors=""
total_requests=""

if ! launchctl print "$SERVICE" >/tmp/spx_cloudflared_launchctl.txt 2>/dev/null; then
  status_ok=0
fi

if ! curl -fsS --max-time 5 "$ROOT_URL" >/tmp/spx_cloudflared_root.html 2>/dev/null; then
  root_ok=0
fi

metrics_payload=""
if metrics_payload="$(curl -fsS --max-time 5 "$METRICS_URL" 2>/dev/null)"; then
  ha_connections="$(printf '%s\n' "$metrics_payload" | awk '/^cloudflared_tunnel_ha_connections / {print $2; exit}')"
  request_errors="$(printf '%s\n' "$metrics_payload" | awk '/^cloudflared_tunnel_request_errors / {print $2; exit}')"
  total_requests="$(printf '%s\n' "$metrics_payload" | awk '/^cloudflared_tunnel_total_requests / {print $2; exit}')"
  if [[ -z "$ha_connections" || "$ha_connections" == "0" ]]; then
    metrics_ok=0
  fi
else
  metrics_ok=0
fi

if [[ "$status_ok" -eq 1 && "$root_ok" -eq 1 && "$metrics_ok" -eq 1 ]]; then
  echo 0 > "$STATE_FILE"
  printf 'health=ok status=running root=ok metrics=ok ha_connections=%s request_errors=%s total_requests=%s failures=0\n' \
    "${ha_connections:-na}" "${request_errors:-na}" "${total_requests:-na}"
  exit 0
fi

failures=$((failures + 1))
echo "$failures" > "$STATE_FILE"

healed=0
if [[ "$HEAL" -eq 1 && "$failures" -ge 2 ]]; then
  launchctl kickstart -k "$SERVICE"
  healed=1
  echo 0 > "$STATE_FILE"
fi

printf 'health=degraded status=%s root=%s metrics=%s ha_connections=%s request_errors=%s total_requests=%s failures=%s healed=%s\n' \
  "$status_ok" "$root_ok" "$metrics_ok" "${ha_connections:-na}" "${request_errors:-na}" "${total_requests:-na}" "$failures" "$healed"
exit 1
EOF
