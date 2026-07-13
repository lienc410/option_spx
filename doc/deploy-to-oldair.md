# Deploying a New App to Old Air + Cloudflare

**Audience**: Owner (you)  
**Old Air specs**: macOS 12.7.6 Monterey · user `macbook` · SSH alias `oldair`  
**Cloudflare tunnel**: `spx-strat` (ID `6d4708bc-69de-4f96-a3d8-1fc32e4543f2`) · domain `portimperialventures.com`

---

## Overview

Old Air is a macOS machine that runs web apps as persistent background services via **launchd** (macOS's process manager). Public access is provided via a **Cloudflare Tunnel** — no port-forwarding or static IP required.

The deployment flow for a new app is:

```
1. Copy project to Old Air
2. Set up Python venv + install deps
3. Test app runs manually
4. Create launchd plist (auto-start + auto-restart)
5. Add hostname to cloudflared config
6. Add DNS record in Cloudflare dashboard
7. Verify end-to-end
```

---

## Step 1 — Copy the project

```bash
# Option A: clone from GitHub
ssh oldair "git clone https://github.com/you/your-app.git ~/your-app"

# Option B: rsync from local machine
rsync -avz --exclude '.git' --exclude '__pycache__' \
    ~/code/your-app/ oldair:~/your-app/
```

---

## Step 2 — Create Python venv and install dependencies

```bash
ssh oldair "
  cd ~/your-app
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt
"
```

> **Note**: Old Air has system Python 3.9.6. If your app needs a newer version,
> install it first: `brew install python@3.11` and use
> `/usr/local/bin/python3.11 -m venv venv`.

---

## Step 3 — Create `.env` file

```bash
ssh oldair "cat > ~/your-app/.env << 'EOF'
SECRET_KEY=your-secret-here
DATABASE_URL=sqlite:///data/app.db
PORT=5100
EOF"
```

> Each app must use a **unique port**. Currently occupied ports on Old Air:
>
> | Service | Port |
> |---|---|
> | SPX Strat web | 5050 |
> | (your new app) | pick 5100, 5200, etc. |

---

## Step 4 — Test the app manually

Before wiring up launchd, confirm the app starts and responds:

```bash
ssh oldair "cd ~/your-app && ./venv/bin/python app.py &"
ssh oldair "sleep 3 && curl -s http://localhost:5100/ | head -c 100"
# Kill the test process
ssh oldair "pkill -f 'python app.py'"
```

---

## Step 5 — Create launchd plist

Create `~/Library/LaunchAgents/com.<yourapp>.web.plist` on Old Air.

```bash
ssh oldair "mkdir -p ~/Library/Logs/your-app"

cat << 'EOF' | ssh oldair "cat > ~/Library/LaunchAgents/com.yourapp.web.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.yourapp.web</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/macbook/your-app/venv/bin/python</string>
    <string>/Users/macbook/your-app/app.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/Users/macbook/your-app</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>ProcessType</key>
  <string>Interactive</string>

  <key>StandardOutPath</key>
  <string>/Users/macbook/Library/Logs/your-app/web.out.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/macbook/Library/Logs/your-app/web.err.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key>
    <string>/Users/macbook</string>
  </dict>
</dict>
</plist>
EOF
```

Load and start it:

```bash
ssh oldair "launchctl load ~/Library/LaunchAgents/com.yourapp.web.plist"
sleep 3
ssh oldair "curl -s http://localhost:5100/ | head -c 100"
```

**Common launchd commands:**

```bash
# Check status (PID shown means running; - means stopped)
ssh oldair "launchctl list | grep yourapp"

# Restart after config/code change
ssh oldair "launchctl stop com.yourapp.web && launchctl start com.yourapp.web"

# View logs
ssh oldair "tail -50 ~/Library/Logs/your-app/web.err.log"

# Remove completely
ssh oldair "launchctl unload ~/Library/LaunchAgents/com.yourapp.web.plist"
```

---

## Step 6 — Add hostname to Cloudflare tunnel

There is **one tunnel** (`spx-strat`) already connected to Old Air with 8 HA connections. You add new hostnames to its ingress rules.

### 6a. Edit cloudflared config on Old Air

```bash
ssh oldair "cat ~/.cloudflared/config.yml"
# You'll see the ingress section. Add your new hostname BEFORE the catch-all.
```

Edit `~/.cloudflared/config.yml`:

```bash
ssh oldair "cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: 6d4708bc-69de-4f96-a3d8-1fc32e4543f2
credentials-file: /Users/macbook/.cloudflared/6d4708bc-69de-4f96-a3d8-1fc32e4543f2.json

loglevel: info
transport-loglevel: warn
metrics: 127.0.0.1:60123
protocol: http2

heartbeat-interval: 5s
heartbeat-count: 5

originRequest:
  retries: 5
  connectTimeout: 10s

ingress:
  - hostname: www.portimperialventures.com
    service: http://127.0.0.1:5050
  - hostname: yourapp.portimperialventures.com   # ← add this line
    service: http://127.0.0.1:5100               # ← and this
  - service: http_status:404
EOF"
```

Also update the **second tunnel config** (`config-connector-b.yml`) with the same ingress block:

```bash
ssh oldair "cat > ~/.cloudflared/config-connector-b.yml << 'EOF'
tunnel: 6d4708bc-69de-4f96-a3d8-1fc32e4543f2
credentials-file: /Users/macbook/.cloudflared/6d4708bc-69de-4f96-a3d8-1fc32e4543f2.json

loglevel: info
transport-loglevel: warn
metrics: 127.0.0.1:60124
protocol: http2

heartbeat-interval: 5s
heartbeat-count: 5

originRequest:
  retries: 5
  connectTimeout: 10s

ingress:
  - hostname: www.portimperialventures.com
    service: http://127.0.0.1:5050
  - hostname: yourapp.portimperialventures.com   # ← same addition
    service: http://127.0.0.1:5100
  - service: http_status:404
EOF"
```

Restart both tunnels to pick up the new ingress rules:

```bash
ssh oldair "
  launchctl stop com.spxstrat.cloudflared
  launchctl stop com.spxstrat.cloudflared-b
  sleep 2
  launchctl start com.spxstrat.cloudflared
  launchctl start com.spxstrat.cloudflared-b
  sleep 3
  launchctl list | grep cloudflared
"
```

### 6b. Add DNS record in Cloudflare dashboard

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **portimperialventures.com** → **DNS**
2. Click **Add record**:

   | Field | Value |
   |---|---|
   | Type | `CNAME` |
   | Name | `yourapp` |
   | Target | `6d4708bc-69de-4f96-a3d8-1fc32e4543f2.cfargotunnel.com` |
   | Proxy status | **Proxied** (orange cloud ☁️) |
   | TTL | Auto |

3. Click **Save**.

> **Note**: You only have one domain (`portimperialventures.com`). All subdomains live under it.
> `yourapp.portimperialventures.com` will be the public URL.

---

## Step 7 — Verify end-to-end

```bash
# Test from your local machine (not Old Air)
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://yourapp.portimperialventures.com/
# Expected: HTTP 200 (or 302 if your app redirects)

# Check tunnel is routing correctly
ssh oldair "tail -5 ~/Library/Logs/cloudflared/err.log"
# Should see: 200 OK for yourapp.portimperialventures.com
```

DNS propagation is instant (Cloudflare manages it). The tunnel is already connected — no waiting.

---

## Step 8 — Deploying updates

For code changes after initial deploy:

```bash
# Pull latest code
ssh oldair "cd ~/your-app && git pull"

# Restart the service
ssh oldair "launchctl stop com.yourapp.web && launchctl start com.yourapp.web"

# Verify
sleep 3
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://yourapp.portimperialventures.com/
```

---

## Troubleshooting

### App shows 502 Bad Gateway

1. Check if the app is running: `ssh oldair "launchctl list | grep yourapp"`
2. Check app logs: `ssh oldair "tail -30 ~/Library/Logs/your-app/web.err.log"`
3. Check if the port is listening: `ssh oldair "lsof -i :5100"`
4. Check tunnel is up: `ssh oldair "curl -s http://127.0.0.1:60123/metrics | grep ha_connections"`
   — should show `4`.

### App starts then immediately crashes

Check the stderr log for Python errors:
```bash
ssh oldair "tail -50 ~/Library/Logs/your-app/web.err.log"
```

Common causes:
- Missing env vars → add them to `.env` or the plist `EnvironmentVariables` dict
- Port already in use → pick a different port
- Import error → activate venv and test manually first

### launchctl load fails

```bash
# Validate plist syntax
ssh oldair "plutil -lint ~/Library/LaunchAgents/com.yourapp.web.plist"
# Must print: OK
```

### DNS not resolving

The CNAME target must be exactly `6d4708bc-69de-4f96-a3d8-1fc32e4543f2.cfargotunnel.com` and the Proxy status must be **orange (Proxied)**, not grey (DNS only).

---

## Reference — Current Old Air services

| Label | Port | URL |
|---|---|---|
| `com.spxstrat.web` | 5050 | `www.portimperialventures.com` |
| `com.spxstrat.bot` | — | Telegram bot (no HTTP) |
| cloudflared (primary) | — | metrics on `127.0.0.1:60123` |
| cloudflared (secondary) | — | metrics on `127.0.0.1:60124` |

When adding a new app, **pick a port not in this table**. Recommended: 5100, 5200, 5300, ...

---

## SPX_strat 专属规则：运行时 state 与 git（SPEC-094.6，2026-07-12）

**事故背景**：old Air 上用 `git stash` 解 pull 冲突，把 git-tracked 的
`data/q042_state.json` 打回 HEAD 全零 6 次，Q042 running ATH 被静默重锚，
2026-06-10 一次真实触发（ddATH −4.51%）被漏。

**规则（不可协商）**：

1. **old Air 上禁止 `git stash` / `git checkout -- <runtime file>` / `git reset --hard`。**
   pull 被 dirty tracked 文件挡住时，正确处理是把该文件 untrack
   （`git rm --cached` + `.gitignore`，走一个 spec），不是 stash。
2. **运行时可变文件（state/ledger/log）永不 git-tracked。** 持久性由
   SPEC-117.1 L1（日备）/L2（周备 iCloud）负责，git 只管代码与冻结的研究工件。
   现有 ignore 清单见 `.gitignore` SPEC-094.6 节。
3. **新增运行时文件时**：先进 `.gitignore` 再写代码；review 时检查
   `git status` 不得出现它。
4. tracked 研究工件（如 `q042_backtest_trades.csv`、`q042_f4_tieout_history.csv`）
   只能由入库脚本再生/追加后**在本地机 commit**，old Air 只 pull——两边同改
   必然拒绝 pull。
