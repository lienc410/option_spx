# SPEC-089: E-Trade PM Account Integration (Read-Only)

Status: DONE

## Design Source

This is an **engineering-driven Spec**.

Design substance 来源：
- **PM**：已完成技术可行性研究（pyetrade / OAuth 1.0a / token 生命周期）
- **Planner**：将 PM 技术结论收口成 DRAFT Spec

这是一个只读账户集成 Spec：不涉及策略逻辑、不涉及 order placement、不涉及市场数据层（quotes / option chains）。

## 目标

将第二个 PM 账户（E-Trade，Portfolio Margin）接入仪表盘：

- 只读仓位（positions）+ 余额/margin（balances）
- 不重复 Schwab 的市场数据层
- E-Trade 区块失败时，Schwab 区块正常显示（fail-soft）

## 约束

- E-Trade 不提供 per-position PM margin（与 Schwab 相同），需自行从账户总维护金推算
- OAuth 1.0a（非 OAuth2）；access token 每天午夜 ET 过期
- 初始授权必须用户手动完成一次（浏览器 redirect + verifier code）
- 续期可自动化（23:00 ET renew_access_token()），但续期失败后需用户重新手动授权

## 功能项（Features）

### F1 — `etrade/auth.py`：OAuth 1.0a token 管理

- `request_token()` + `get_access_token(verifier)` 完整初始授权流
- `renew_access_token()` 续期（每日 23:00 ET 调用）
- token 持久化到本地文件（路径通过 config 指定）
- `is_token_valid()` 检查方法（让 client 在调用前 pre-check）

### F2 — `etrade/client.py`：positions + balances 封装

- `get_account_positions(account_id)` → 返回标准化 dict list
- `get_account_balances(account_id)` → 返回标准化 dict（含 net_liquidating_value、total_maintenance_margin、cash、margin_balance 等字段）
- 若 token 无效 / API 请求失败：fail-soft（返回 `None` 或空列表，记录 warning log，不抛出未捕获异常）

### F3 — `web/server.py`：新增 3 条路由

- `GET /api/etrade/balances` → JSON（balances dict 或 `{"error": "unavailable"}`）
- `GET /api/etrade/positions` → JSON（positions list 或 `{"error": "unavailable"}`）
- `GET /etrade/auth` → OAuth callback endpoint（接收 oauth_verifier，完成授权，重定向到 `/`）

### F4 — 每日 23:00 ET token 续期任务

- 接入现有 bot 调度器（`apscheduler` 或同类机制）或系统 cron
- 调用 `renew_access_token()`；记录 success / failure log
- 续期失败不抛出 uncaught exception，失败后由 F5 处理告警

### F5 — Token 过期 Telegram 告警

- 触发条件：`/api/etrade/balances` 或 `/api/etrade/positions` 因 token 失效返回失败
- 每次 token 失效状态最多发一次告警（不重复轰炸）；token 恢复后重置告警 flag
- 告警内容：「E-Trade token 已过期，请访问 [url]/etrade/auth 完成手动授权」

### F6 — `portfolio_home` 新增 E-Trade 账户区块

- E-Trade 独立区块（仓位列表 + 账户余额）
- 双账户合并 PM BP 展示（Schwab 维护金 + E-Trade 维护金 → 合并 total）
- E-Trade 不可用时区块显示「E-Trade 暂不可用」占位，不影响 Schwab 区块

## 验收标准（Acceptance Criteria）

- **AC1** — `etrade/auth.py` 初始授权流可端到端运行；token 持久化后重启进程仍可读取
- **AC2** — `etrade/client.py` 在 token 有效时返回真实账户数据；token 无效时 fail-soft（不抛出）
- **AC3** — `/api/etrade/balances` 和 `/api/etrade/positions` 返回格式正确的 JSON；`/etrade/auth` 完成 OAuth callback 并重定向
- **AC4** — 23:00 ET 续期任务触发可验证（log 中有续期记录）；续期失败不导致进程崩溃
- **AC5** — token 失效时 Telegram 告警发出，且在同一失效周期内不重复发送
- **AC6** — `portfolio_home` 展示 E-Trade 区块；E-Trade 不可用时 Schwab 区块正常加载，E-Trade 区块显示降级占位
- **AC7** — `etrade/` 模块中不调用任何 quotes / option chains / market data API
- **AC8** — 回归：现有 Schwab 集成、portfolio_home、/api/recommendation 等路径不受影响

## Out of Scope

- E-Trade option chain / quotes / Greeks
- Per-position PM margin 精确计算（同 Schwab 约束，只能从账户总维护金推算）
- 任何交易执行或下单功能
- E-Trade 侧的回测或研究功能

## 依赖

- `pyetrade` 库已安装（`pip install pyetrade`）
- E-Trade Developer account + Consumer Key / Consumer Secret（由 PM 提供，写入 config）
- 第一次授权必须有 browser 访问 old Air URL 的能力（cloudflared 隧道已存在）

## Review

- Implemented as a read-only E-Trade rail with lazy `pyetrade` loading and fail-soft semantics.
- AC1 PASS — `etrade/auth.py` supports request-token, callback token exchange, renewal, persisted token reload, and validity checks.
- AC2 PASS — `etrade/client.py` returns normalized balances/positions when authenticated and degrades to stale/unavailable payloads when token/config/API is unavailable.
- AC3 PASS — `/api/etrade/balances`, `/api/etrade/positions`, and `/etrade/auth` are wired and covered by route tests.
- AC4 PASS — 23:00 ET renewal job is registered in the Telegram bot scheduler and renewal failure does not raise uncaught exceptions.
- AC5 PASS — token-expiry alert is deduped per invalid period via persisted alert-state file and resets on recovery.
- AC6 PASS — `portfolio_home` now shows an E-Trade read-only balances/positions panel plus combined maintenance display; E-Trade failure leaves Schwab surfaces intact.
- AC7 PASS — `etrade/` only uses OAuth and account endpoints; no quotes / chains / market-data calls were added.
- AC8 PASS — regression tests confirmed existing Schwab, `portfolio_summary`, Telegram bot, `state_and_api`, and `/api/recommendation` behavior remain intact.
