#!/bin/bash
# Install launchd cron jobs on oldair for Schwab token keep-alive and E-Trade daily re-auth.
# Run on LOCAL machine:  bash scripts/install_crons.sh
#
# What this installs:
#   com.spxstrat.schwab_refresh  — runs every 6 hours, keeps Schwab token alive indefinitely
#   com.spxstrat.etrade_refresh  — runs at 05:30 ET daily, headless E-Trade re-auth

set -euo pipefail

REMOTE="oldair"
REPO="~/SPX_strat"
PLIST_DIR="~/Library/LaunchAgents"
LOG_DIR="~/Library/Logs/spx-strat"
VENV="${REPO}/venv/bin/python3"

echo "==> Installing cron jobs on ${REMOTE}..."

# ── 1. Schwab token keep-alive (every 6 hours = 21600 seconds) ────────────────
ssh "$REMOTE" "mkdir -p ${LOG_DIR}"

ssh "$REMOTE" "cat > ${PLIST_DIR}/com.spxstrat.schwab_refresh.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spxstrat.schwab_refresh</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/macbook/SPX_strat/venv/bin/python3</string>
        <string>/Users/macbook/SPX_strat/scripts/schwab_token_refresh.py</string>
    </array>
    <key>StartInterval</key>
    <integer>21600</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/macbook/Library/Logs/spx-strat/schwab_refresh.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/macbook/Library/Logs/spx-strat/schwab_refresh.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/macbook</string>
    </dict>
</dict>
</plist>
EOF

# ── 2. E-Trade daily status check + Telegram notify at 06:00 ET ───────────────
# E-Trade tokens hard-expire at midnight ET. We can't auto-renew across midnight
# (renew_access_token only handles 2h inactivity timeout, not the midnight
# boundary). So instead, check the token each morning and notify if it's
# expired — user clicks the link in the Telegram message to use the web UI
# re-auth at /etrade/reauth.
ssh "$REMOTE" "cat > ${PLIST_DIR}/com.spxstrat.etrade_refresh.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spxstrat.etrade_refresh</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/macbook/SPX_strat/venv/bin/python3</string>
        <string>/Users/macbook/SPX_strat/scripts/etrade_status_notify.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/macbook/Library/Logs/spx-strat/etrade_refresh.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/macbook/Library/Logs/spx-strat/etrade_refresh.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/macbook</string>
    </dict>
</dict>
</plist>
EOF

# ── Load both plists ───────────────────────────────────────────────────────────
echo "==> Loading plists..."
ssh "$REMOTE" "launchctl unload ${PLIST_DIR}/com.spxstrat.schwab_refresh.plist 2>/dev/null || true"
ssh "$REMOTE" "launchctl load  ${PLIST_DIR}/com.spxstrat.schwab_refresh.plist"
ssh "$REMOTE" "launchctl unload ${PLIST_DIR}/com.spxstrat.etrade_refresh.plist 2>/dev/null || true"
ssh "$REMOTE" "launchctl load  ${PLIST_DIR}/com.spxstrat.etrade_refresh.plist"

echo ""
echo "==> Done. Cron jobs installed:"
echo "    Schwab  — every 6 hours (keep-alive, logs: ~/Library/Logs/spx-strat/schwab_refresh.log)"
echo "    E-Trade — daily at 06:00 ET (status check + Telegram notify if expired, logs: ~/Library/Logs/spx-strat/etrade_refresh.log)"
echo ""
echo "==> Verify:"
ssh "$REMOTE" "launchctl list | grep 'schwab_refresh\|etrade_refresh'"
