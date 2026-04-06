# SPEC-035: Schwab API Read-Only Integration

## 目标

**What**：接入 Schwab Developer API，读取以下信息：
1. 账户当前持仓（实际合约 + 当前市值）
2. 期权实时报价（bid/ask/mark）
3. 实时希腊值（delta/gamma/theta/vega）
4. 账户 Buying Power 使用量

**Why（read-only，不做下单）**：
- 替代 BS 模型的每日估值，显示真实市价 PnL
- Dashboard Position Panel 显示实时 delta/theta，辅助持仓管理决策
- BP 真实使用量显示，取代 Margin 页的静态估算

---

## Schwab API 背景

**认证方式**：OAuth2 Authorization Code Flow
- Client ID / Client Secret 来自 Schwab Developer Portal
- Access Token：有效期 30 分钟
- Refresh Token：有效期 7 天，需定期手动刷新或自动续期
- Token 存储：`~/.spxstrat/schwab_token.json`（不放项目目录，避免意外 commit）

**主要 endpoint（均为 GET，read-only）**：

| 功能 | Endpoint |
|------|---------|
| 账户列表 | `GET /trader/v1/accounts` |
| 账户持仓 | `GET /trader/v1/accounts/{accountNumber}?fields=positions` |
| 期权报价 | `GET /marketdata/v1/chains?symbol=SPX&...` |
| 单一报价 | `GET /marketdata/v1/{symbol}/quotes` |
| 账户余额 | `GET /trader/v1/accounts/{accountNumber}` |

---

## 功能定义

### F1 — Token 管理模块（schwab/auth.py）

**首次 setup（一次性手动操作）**：
```
python -m schwab.setup
```
引导用户完成 OAuth2 授权流程，生成初始 token 文件。

**自动续期**：
- 每次 API 调用前检查 access token 是否过期（< 5 分钟剩余）
- 若过期，用 refresh token 自动获取新 access token
- Refresh token 本身在 6 天后提醒用户重新授权（7天有效期前 1 天）

**Token 文件结构**：
```json
{
  "access_token":  "...",
  "refresh_token": "...",
  "expires_at":    "2026-04-05T11:30:00",
  "refresh_expires_at": "2026-04-12T10:00:00",
  "account_number": "12345678"
}
```

**错误处理**：
- Token 过期且无法 refresh（refresh token 也过期）→ 返回 `{"schwab": "auth_required"}`
- API 限流（429）→ 返回缓存值 + 标注 `"stale": true`
- 网络错误 → 同上

---

### F2 — 数据拉取模块（schwab/client.py）

**`get_account_positions()`**：
返回当前账户的所有期权持仓，解析出：
```python
{
  "symbol":       "SPX 260505C05400",   # OCC symbol
  "description":  "SPX May 05 2026 5400 Call",
  "quantity":     -2,                  # 负数 = short
  "mark":         3.05,
  "bid":          3.00,
  "ask":          3.10,
  "delta":        -0.28,
  "gamma":        0.002,
  "theta":        -0.15,
  "vega":         0.80,
  "unrealized_pnl": 42.0,
}
```

**`get_option_quote(symbol: str)`**：
获取单个合约的实时报价 + 希腊值。

**`get_account_balances()`**：
返回：
```python
{
  "buying_power":      85000.0,
  "option_buying_power": 85000.0,
  "net_liquidation":   152000.0,
  "initial_margin":    18000.0,
  "maintenance_margin": 15000.0,
}
```

**缓存策略**：
- 市场开盘时（09:30–16:00 ET）：内存缓存 60 秒
- 收盘后：内存缓存 300 秒（5分钟）
- 进程重启：无缓存（重新请求）

---

### F3 — 新增 API endpoints（server.py）

```
GET /api/schwab/status       ← token 状态（有效/过期/未配置）
GET /api/schwab/positions     ← 实时持仓 + Greeks
GET /api/schwab/balances      ← 账户 BP + 余额
```

**`/api/schwab/status` 响应**：
```json
{
  "configured": true,
  "authenticated": true,
  "token_expires_in": 1240,
  "refresh_expires_in": 518400,
  "stale": false
}
```

---

### F4 — Dashboard 集成

**Position Panel 扩展**（有持仓 + Schwab 已配置时）：

现有 Position Panel 下方新增一行 "Live Greeks" 区块：

```
LIVE GREEKS (Schwab)
Δ −0.28  Γ 0.002  Θ −0.15/day  V 0.80
Mark $3.05  Bid $3.00  Ask $3.10
Unrealized PnL: +$42  (Model: +$38)
```

颜色规则：
- delta 负值 → red（short position）
- unrealized PnL 正值 → green，负值 → red
- 若 Schwab 数据 stale（缓存超时）→ 显示灰色 `⚠ stale` 标注

**刷新频率**：
- 市场开盘时：与 intraday bar 同频，60 秒刷新
- 收盘后：5 分钟刷新

---

### F5 — Margin 页 BP 升级

Margin 页现有"Account-Level BP Summary"区块（静态数据）下方，新增：

```
LIVE BP (Schwab)          [Last updated: 10:32 ET]
Buying Power Used:   $18,000 / $103,000  (17.5%)
Remaining BP:        $85,000
Net Liquidation:     $152,000
```

若 Schwab 未配置，该区块显示 "Schwab not configured — see setup guide"。

---

### F6 — 与 Trade Log 的联动（SPEC-034 前提）

当 SPEC-034 的 trade log 中有开仓记录（含 short_strike / long_strike / expiry）时：
- Schwab client 自动构建对应合约的 OCC symbol
- 主动查询该合约的实时报价
- 与 actual_premium 对比，计算 live PnL

若无 trade log（仅 state.py 持仓），仅显示账户持仓快照，不做对比。

---

## 新增文件

| 文件 | 用途 |
|------|------|
| `schwab/__init__.py` | 包入口 |
| `schwab/auth.py` | OAuth2 token 管理、自动续期 |
| `schwab/client.py` | API 调用封装、缓存、错误处理 |
| `schwab/setup.py` | 一次性授权引导脚本 |
| `~/.spxstrat/schwab_token.json` | Token 存储（项目外） |

**不新增**：不修改 engine.py / signals / strategy 层

---

## 边界条件与约束

- **read-only**：不实现任何下单、修改、取消 endpoint
- **降级优雅**：Schwab 未配置或 token 过期时，Dashboard / Margin 页静默隐藏 Live 区块，不报错
- **账户隔离**：token 文件存储在 `~/.spxstrat/`，不放项目目录，不 commit
- Schwab API 每分钟有 rate limit（约 120 次/分钟），缓存策略必须严格执行
- 仅支持单账户（Portfolio Margin 账户）
- 期权合约匹配依赖 trade log 中的 short_strike / long_strike / expiry，若无则只显示账户快照
- 本 SPEC 依赖 SPEC-034 完成后才能实现 F6（live PnL 对比）

---

## Setup 说明（给 PM）

```bash
# 1. 在 Schwab Developer Portal 创建 app，获得 client_id / client_secret
# 2. 运行一次性授权
venv/bin/python -m schwab.setup
# 3. 按提示登录 Schwab，授权后 token 自动保存
# 4. 重启 web 进程即可在 Dashboard 看到 Live Greeks
```

---

## 不在范围内

- 下单 / 修改 / 取消订单
- 历史成交记录拉取（Schwab transactions API）
- 多账户支持
- VIX 期货实时报价
- Schwab streaming API（WebSocket 实时推送）

---

## Review

- 结论：PASS（代码层）
- AC2/6/7/8/9 通过代码核查与降级路径测试
- AC1/3/4/5 需真实 Schwab 凭证联调才能完整验证（需先在 Schwab Developer Portal 创建 app，配置 SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET，运行 `venv/bin/python -m schwab.setup`）
- token 管理逻辑正确：ensure_access_token() 在剩余 < 5 分钟时自动 refresh，不中断服务
- live_position_snapshot() 的合约匹配逻辑：优先匹配 expiry + short_strike，fallback 到第一个持仓；依赖 SPEC-034 trade log 中有 short_strike / expiry 才能精确匹配

---

## 验收标准

1. **AC1**：`python -m schwab.setup` 完成授权后，`~/.spxstrat/schwab_token.json` 存在
2. **AC2**：`/api/schwab/status` 返回 `{"configured": true, "authenticated": true, ...}`
3. **AC3**：`/api/schwab/positions` 返回持仓列表（含 Greeks），格式符合 F2 定义
4. **AC4**：`/api/schwab/balances` 返回 BP 数据
5. **AC5**：Dashboard Position Panel 有 Live Greeks 区块（Schwab 已配置 + 有持仓时）
6. **AC6**：Schwab 未配置或 token 过期时，Dashboard 不报错，Live Greeks 区块静默隐藏
7. **AC7**：Margin 页显示 Live BP 区块（Schwab 已配置时）
8. **AC8**：Access token 过期时自动 refresh，不中断服务
9. **AC9**：市场开盘时缓存 60 秒，收盘后 300 秒

---

Status: DONE
