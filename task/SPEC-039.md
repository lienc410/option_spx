# SPEC-039: Option Chain Liquidity Scanner for Open Draft

## 目标

**What**：在 `GET /api/position/open-draft` 中集成真实期权链扫描，根据 delta、bid-ask spread 和 open interest 推荐流动性最优的 strike，替代纯 BS 模型的理论 strike。

**Why**：
- BS 模型反推的 δ0.20 strike 在实际市场中可能流动性极差（spread 宽、OI 低）
- 用户无法在录入前知道哪个 strike 成交条件最优
- Schwab API 已接入，可实时获取真实期权链数据

**核心原则**：
- 只影响 `open-draft` 预填，不改动 backtest engine / signals / selector
- Schwab 未配置时 fallback 到现有 BS 模型行为（向后兼容）
- 最终 strike 由用户在 Open modal 确认，scanner 只做推荐

---

## 功能定义

### F1 — Option Chain 数据拉取（`schwab/client.py`）

新增函数：

```python
def get_option_chain(
    symbol: str,
    option_type: str,         # "CALL" or "PUT"
    target_dte: int,
    dte_range: int = 7,       # 扫描 target_dte ± dte_range 天内的到期日
) -> list[dict]:
```

调用 Schwab `/marketdata/v1/chains`：

```
GET /marketdata/v1/chains
  ?symbol=SPX
  &contractType=PUT
  &strikeCount=20
  &includeQuotes=TRUE
  &fromDate={target_date - dte_range}
  &toDate={target_date + dte_range}
```

每个 strike 返回字段：
```python
{
  "expiry":          "2026-05-05",
  "strike":          5480.0,
  "bid":             1.20,
  "ask":             1.35,
  "mid":             1.275,
  "spread_pct":      0.118,   # (ask - bid) / mid
  "delta":           -0.21,
  "open_interest":   1240,
  "volume":          85,
  "dte":             28,
}
```

缓存：市场开盘时 60 秒，收盘后 300 秒（与现有缓存策略一致）。

---

### F2 — 流动性评分（`schwab/scanner.py`）★ 新文件

#### 硬性过滤（先排除）

| 条件 | 处理 |
|------|------|
| `spread_pct > 0.50` | 排除 |
| `open_interest < 100` | 排除 |
| `bid <= 0` | 排除（无市场） |

`volume == 0`：非交易时段常见，不排除，但评分中降权（见下）。

#### 评分公式（越低越好）

```python
import math

delta_distance = abs(actual_delta - target_delta)
volume_penalty = 0.1 if volume == 0 else 0.0

score = (
    delta_distance          * 0.4
    + spread_pct            * 0.4
    + (1 / math.log(open_interest + 1)) * 0.2
    + volume_penalty
)
```

#### 推荐逻辑

- 过滤后按 score 升序排列
- `recommended = True` 标记 score 最低的一条
- 若过滤后无结果（全部被排除），fallback 到 BS 模型 strike，标注 `scan_fallback: true`

---

### F3 — `open-draft` endpoint 扩展（`web/server.py`）

**Schwab 已配置时**，`GET /api/position/open-draft` 额外返回：

```json
{
  "strategy_key":  "bear_call_spread_hv",
  "short_strike":  5490,
  "long_strike":   5540,
  "model_premium": 1.28,
  "expiry":        "2026-05-12",
  "dte":           35,
  "legs":          [...],
  "strike_scan": {
    "short_leg": [
      {
        "strike":        5490,
        "expiry":        "2026-05-12",
        "bid":           1.20,
        "ask":           1.35,
        "mid":           1.275,
        "spread_pct":    0.118,
        "delta":         -0.21,
        "open_interest": 1240,
        "volume":        85,
        "score":         0.312,
        "recommended":   true
      },
      ...
    ],
    "long_leg": [
      {
        "strike":        5540,
        "expiry":        "2026-05-12",
        "bid":           0.45,
        "ask":           0.55,
        "mid":           0.50,
        "spread_pct":    0.200,
        "delta":         -0.10,
        "open_interest": 620,
        "volume":        40,
        "score":         0.280,
        "recommended":   true
      },
      ...
    ],
    "scan_fallback": false
  }
}
```

**Schwab 未配置时**：`strike_scan` 字段不出现，行为与现在完全相同。

**扫描 leg 范围**：基于现有两档 strike 字段（`short_strike` / `long_strike`）：
- BPS/BCS/BPS_HV/BCS_HV：short leg + long leg 各一次扫描
- Iron Condor：`short_strike`（short call）+ `long_strike`（long call）两腿扫描；put 侧需要四腿 schema 扩展，留给后续 SPEC

---

### F4 — Open Position Modal 扩展（`index.html`）

当 `strike_scan` 存在时，每个 leg 的 Strike 输入框下方各显示一张扫描结果表：

```
Short Strike  [5490        ▼]

  Strike  Expiry    Bid   Ask  Spread  Delta   OI    Score
  ★5490  May-12   1.20  1.35   11.8%  -0.21  1240   0.31  ← 推荐
   5480  May-12   0.90  1.40   43.5%  -0.19    85   0.59
   5500  May-12   1.55  1.75   12.5%  -0.23   980   0.33

Long Strike   [5540        ▼]

  Strike  Expiry    Bid   Ask  Spread  Delta   OI    Score
  ★5540  May-12   0.45  0.55   20.0%  -0.10   620   0.28  ← 推荐
   5530  May-12   0.60  0.90   40.0%  -0.12   210   0.51
```

- ★ 标记推荐 strike
- 点击任意行 → 自动填入对应 leg 的 Strike 输入框
- spread_pct > 30% 的行用橙色标注（警示但不禁用）
- `scan_fallback: true` 时显示提示："No liquid strikes found — using model estimate"

---

## 边界条件与约束

- 扫描只在 `open-draft` 时触发，不在 `POST /api/position/open` 提交时再次验证
- Schwab API 限流（120次/分）：scanner 共享现有缓存，同一参数 60 秒内不重复请求
- SPX 期权到期日为每周三/周五 + 月度，scanner 自动找 target_dte 最近的有效到期日
- `dte_range=7` 意味着最多扫描 2~3 个到期日，取 OI 最高的那个到期日的链
- 不影响 backtest engine（继续用 BS 模型）
- 不改动 signals / strategy / selector 层

---

## 不在范围内

- 自动选择 expiry（到期日仍由推荐逻辑决定，scanner 在给定 expiry 附近扫描）
- 实时 Greeks 更新（open modal 打开后不自动刷新扫描结果）
- Bull Call Diagonal 的 long leg（90 DTE，流动性结构不同，单独 SPEC）
- Iron Condor put 侧两腿（需要四腿 schema 扩展，单独 SPEC）

---

## 新增文件

| 文件 | 用途 |
|------|------|
| `schwab/scanner.py` | 流动性评分逻辑（filter + score + recommend）|

**修改文件**：
- `schwab/client.py`：新增 `get_option_chain()`
- `web/server.py`：`open-draft` 调用 scanner，返回 `strike_scan`
- `web/templates/index.html`：Open modal 显示扫描结果表

---

## 接口定义

### `schwab/scanner.py`

```python
def scan_strikes(
    chain: list[dict],
    target_delta: float,
) -> list[dict]:
    """
    过滤 + 评分期权链，返回按 score 升序排列的列表。
    每条记录新增字段：score, recommended。
    若无通过过滤的 strike，返回空列表。
    """

def build_strike_scan(
    symbol: str,
    option_type: str,     # "CALL" or "PUT"
    target_delta: float,
    target_dte: int,
) -> dict:
    """
    调用 get_option_chain() + scan_strikes()，
    返回 {"short_leg": [...], "scan_fallback": bool}
    """
```

---

## 验收标准

1. **AC1**：Schwab 已配置时，`/api/position/open-draft` 返回 `strike_scan`，每个 leg 均有独立扫描列表
2. **AC2**：`spread_pct > 0.50` 或 `open_interest < 100` 或 `bid <= 0` 的 strike 不出现在结果中
3. **AC3**：每个 leg 的推荐 strike（`recommended: true`）为该 leg score 最低的一条
4. **AC4**：某 leg 所有 strike 被过滤掉时，`scan_fallback: true`，该 leg fallback 到 BS 模型值
5. **AC5**：Schwab 未配置时，`open-draft` 行为与现在完全相同，无 `strike_scan` 字段
6. **AC6**：Open modal 每个 leg 下方各显示独立扫描表，点击任意行填入对应 leg 的 Strike 输入框
7. **AC7**：推荐 strike 有 ★ 标记；`spread_pct > 30%` 的行有橙色警示
8. **AC8**：扫描结果 60 秒内缓存，不重复调用 Schwab API

---

## 依赖

- SPEC-034（open-draft endpoint 基础）
- SPEC-035（Schwab client + auth）

---

## Review
- 结论：PASS
- AC1-AC8 全部通过
- `$SPX` symbol 规范化修复（SPX 直接请求 400）已包含
- bull_call_diagonal long leg 跳过符合 SPEC 约定，前端有提示

Status: DONE
