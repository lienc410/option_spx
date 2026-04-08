# SPEC-043: Wider Delta-Seeking Strike Scan

Status: CANCELLED — superseded by SPEC-045

## 目标

**What**：
1. 在现有 centered scan 基础上，提升 live strike scanner 对目标 delta 的命中率
2. 避免 scanner 只在理论 strike 邻域内返回明显偏离目标 delta 的候选
3. 保持现有前端交互与推荐表结构不变

**Why**：
- 当前 `SPEC-040` 已解决“扫错窗口”的问题
- 但 live `$SPX` 场景里，理论中心附近返回的实际合约 delta 仍可能远离目标值
- 结果是 scanner 虽然不再 fallback，却可能推荐一个 `live delta` 与 `target delta` 偏差很大的合约

---

## 核心原则

- 只改 `schwab/client.py` / `schwab/scanner.py`
- 不改 `engine.py / signals / selector / backtest`
- 不改前端 UI 结构
- 保留 `SPEC-039/040/042` 的既有评分框架和 relaxed OI 逻辑

---

## 功能定义

### F1 — 目标 delta 偏差检测

对每条候选 row，定义：

```python
delta_gap = abs(abs(actual_delta) - abs(target_delta))
```

当 centered scan 的最佳候选满足以下任一条件时，视为“命中不足”：

- `delta_gap > 0.08`
- 或 `rows` 为空

---

### F2 — 扩大扫描窗口

当前 `SPEC-040` 逻辑：
- 用 `center_strike`
- 取附近有限 `strike_window`

新增逻辑：
- 若首次 centered scan 命中不足，则扩大原始抓取窗口并重新局部裁剪
- 推荐实现为同一 expiry 下扩大 `strike_window`

示意：

```python
primary = get_option_chain(..., center_strike=center_strike, strike_window=10)
if miss_target(primary):
    secondary = get_option_chain(..., center_strike=center_strike, strike_window=24)
```

然后继续复用现有评分逻辑。

---

### F3 — 缓存隔离

扩大后的请求仍应命中独立缓存 key。

**实现要求**：修改 `schwab/client.py` 的 `_chain_cache_key()` 函数签名，加入 `strike_window` 参数：

```python
def _chain_cache_key(symbol, option_type, target_dte, dte_range, center_strike=None, strike_window=None):
    ...
    # center_strike 存在时，key 包含 center_key 和 strike_window
    return f"chain:{symbol}:{option_type}:{target_dte}:{dte_range}:{center_key}:{strike_window}"
```

注意：`strike_window=10` 时 `strikeCount=300`，`strike_window=24` 时 `strikeCount=480`，API 返回不同，必须有独立 key。`center_strike=None` 时（旧路径）key 格式不变，向后兼容。

---

### F2b — Secondary miss 时的返回策略

若 secondary scan（`strike_window=24`）仍命中不足（`delta_gap > 0.08` 或 `rows` 为空）：
- **返回 secondary 结果，不回退到 primary**
- 理由：宽窗候选池 >= 窄窗，secondary 始终不差于 primary
- `miss_target()` 基于 post-filter `rows` 中 `recommended=True` 的那条判断；若 `rows` 为空则直接视为 miss

---

### F4 — 推荐逻辑不变

保持：
- `scan_strikes()` 的评分规则不变
- `recommended=True` 仍只给排序第一的行
- 前端不新增字段

本 spec 的目标只是：
- 给评分器更合理的候选池

---

## 边界条件与约束

- 不新增二次网络请求超过 1 次
- 不做“多轮直到命中”的递归扫描
- 不改 `spread_pct` / `OI` 阈值
- 不为 put/call 设计不同扩窗策略
- Iron Condor 仍只扫 call 侧

---

## 不在范围内

- 前端展示 `delta_gap`
- 改动 Telegram / Dashboard 文案
- 调整理论 strike 计算方式
- 修改策略本身的目标 delta

---

## 验收标准

1. **AC1**：当 centered primary window 命中不足时，scanner 会扩大候选窗口再评估
2. **AC2**：缓存 key 能区分不同 `strike_window`
3. **AC3**：当前 `$SPX` short-call live 场景下，更容易拿到接近目标 delta 的候选
4. **AC4**：前端 schema 和交互保持兼容
5. **AC5**：普通未触发 miss-target 的场景不增加额外请求

---

## 备注

依赖：
- `SPEC-039`
- `SPEC-040`
- `SPEC-042`
