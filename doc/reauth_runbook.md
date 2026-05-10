# Re-Auth Runbook — Schwab & E-Trade

> 最后更新：2026-05-10

---

## 日常自动化（正常情况无需操作）

| 平台 | 机制 | 触发时间 | 日志 |
|---|---|---|---|
| Schwab | `schwab_token_refresh.py` — 调用 refresh_access_token()，refresh_token 随之轮换 | 每 6 小时（launchd） | `~/Library/Logs/spx-strat/schwab_refresh.log` |
| E-Trade | `etrade_token_renew.py` — 调用 E-Trade `/oauth/renew_access_token` API | 每天 23:45（launchd） | `~/Library/Logs/spx-strat/etrade_refresh.log` |

---

## 判断是否需要手动 re-auth

```bash
ssh oldair "cd ~/SPX_strat && venv/bin/python3 -c \"
from schwab.auth import token_status as s
from etrade.auth import token_status as e
print('Schwab:', s())
print('ETrade:', e())
\""
```

- `authenticated: True` → 正常，不需要操作
- `authenticated: False` + `token_expires_in` 为负 → 需要 re-auth（见下方步骤）

---

## Schwab 手动 re-auth

**何时需要**：cron 连续 7 天没跑（oldair 关机 / 休眠），refresh token 过期。

**在本机 Mac 运行**（需要本地浏览器）：

```bash
cd /Users/lienchen/Documents/workspace/SPX_strat
venv/bin/python3 scripts/schwab_reauth.py
```

流程：
1. 自动生成临时自签名证书，启动本地 HTTPS 回调服务器（端口 8182）
2. 浏览器自动打开 Schwab 授权页
3. 登录 Schwab → 点击 Authorize
4. 浏览器跳转到 `https://127.0.0.1:8182/callback` 时出现证书警告：
   - **Chrome**：在警告页面直接键盘输入 `thisisunsafe`（不要点输入框，直接打）
   - **Safari**：显示详细信息 → 访问此网站
5. 看到 "Authorization successful. You may close this tab." → 完成
6. 脚本自动 scp token 到 oldair

**完成后验证**：

```bash
ssh oldair "cd ~/SPX_strat && venv/bin/python3 -c \
  'from schwab.auth import token_status; print(token_status())'"
# 期望：authenticated: True, refresh_expires_in: ~604800
```

---

## E-Trade 手动 re-auth

**何时需要**：oldair 在 23:45 休眠导致续期 cron 没跑，token 过了午夜失效。

### 方法一：通过 web 界面（推荐，最快）

在本机 Mac 运行：

```bash
cd /Users/lienchen/Documents/workspace/SPX_strat
venv/bin/python3 scripts/etrade_reauth.py
```

或直接在浏览器打开：`https://www.portimperialventures.com/etrade/auth`

流程：
1. 脚本调用 web server 的 `/etrade/auth`，获取 E-Trade 授权链接
2. 浏览器自动打开 E-Trade 登录页
3. 登录 E-Trade → 点击 Accept/Authorize
4. E-Trade 页面显示 verifier code（5 位字母数字，如 `QK8GN`）
5. 脚本等待轮询，若 web server 自动处理回调则无需输入

若 5 分钟内轮询未成功（web server 回调未触发），改用方法二。

### 方法二：手动 verifier exchange

```bash
# 步骤 1：获取新的 E-Trade 授权链接
ssh oldair "cd ~/SPX_strat && venv/bin/python3 -c \"
from dotenv import load_dotenv; load_dotenv('.env')
from etrade.auth import request_token
print(request_token().get('authorize_url'))
\""
# 复制打印出的链接，在浏览器打开

# 步骤 2：登录 E-Trade，点击 Accept，记下 verifier code

# 步骤 3：立刻（<5分钟内）在 oldair 上 exchange（替换 XXXXX 为实际 verifier）
ssh oldair "cd ~/SPX_strat && venv/bin/python3 -c \"
from dotenv import load_dotenv; load_dotenv('.env')
from etrade.auth import get_access_token, token_status
get_access_token('XXXXX')
print(token_status())
\""
```

⚠ **注意**：request token 有效期约 5 分钟，步骤 2→3 必须在此时间内完成。

**完成后验证**：

```bash
ssh oldair "cd ~/SPX_strat && venv/bin/python3 -c \
  'from etrade.auth import token_status; print(token_status())'"
# 期望：authenticated: True
```

---

## 重装 cron（oldair 重置后）

```bash
# 在本机运行
cd /Users/lienchen/Documents/workspace/SPX_strat
bash scripts/install_crons.sh
```

安装内容：
- `com.spxstrat.schwab_refresh` — 每 6 小时
- `com.spxstrat.etrade_refresh` — 每天 23:45

验证已装载：

```bash
ssh oldair "launchctl list | grep 'schwab_refresh\|etrade_refresh'"
# 期望：两行，PID 列为 - 或数字
```

---

## 相关文件

| 文件 | 用途 |
|---|---|
| `schwab/auth.py` | Schwab OAuth 2.0 核心（token 读写、refresh、exchange） |
| `etrade/auth.py` | E-Trade OAuth 1.0a 核心（renew_access_token 实现） |
| `scripts/schwab_reauth.py` | 本机运行的一次性完整 re-auth（含 HTTPS 回调服务器） |
| `scripts/schwab_token_refresh.py` | cron 用的轻量 refresh 脚本 |
| `scripts/etrade_reauth.py` | E-Trade 半自动 re-auth（调用 web server 流程） |
| `scripts/etrade_reauth_headless.py` | E-Trade Playwright 无头 re-auth（若有账号密码可用） |
| `scripts/etrade_token_renew.py` | cron 用的日常续期脚本（无需密码） |
| `scripts/install_crons.sh` | 在 oldair 安装两个 launchd cron |
| `~/.spxstrat/schwab_token.json` | Schwab token 存储（oldair） |
| `~/.spxstrat/etrade_token.json` | E-Trade token 存储（oldair） |
