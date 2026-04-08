# SPEC-040: Strike-Centered Option Chain Scan

## Review
- 结论：PASS
- AC1-AC5 全部通过
- strikeCount 动态放大（max(300, strike_window*20)）+ 本地裁剪正确
- cache key 含 center_key（int round），None 时向后兼容
- live sanity 已确认在 SPX ~7300 水位下邻域切片生效

Status: DONE

## 目标

**What**：
1. 优化 `SPEC-039` 的 Schwab option chain 扫描方式
2. 不再依赖宽泛的 `strikeCount` 默认窗口
3. 先用理论 strike 估一个中心，再围绕该中心做局部扫描

**Why**：
- 当前 `strikeCount=20` 对 `$SPX` 只拿到一段偏近 ATM 的链
- 对目标 `delta=0.20` 的 short call / short put，可能根本扫不到足够 OTM 的候选
- 结果会出现“Schwab 有链，但 scanner 全部 fallback”的假阴性

---

## 核心原则

- 只优化 `open-draft` 的 scanner 数据获取方式
- 不改动 `engine.py / signals / selector / backtest`
- 保持 `SPEC-039` 的评分与前端交互不变
- Schwab 未配置时仍回退到当前 BS 模型行为

---

## 功能定义

### F1 — 中心 strike 概念

在 `GET /api/position/open-draft` 中，每条待扫描 leg 已经有一个理论 strike：

- 来自现有 `find_strike_for_delta(...)`

这个值定义为：

```python
center_strike: int
```

scanner 后续的 option chain 请求应围绕 `center_strike` 收缩，而不是只靠 `strikeCount=20` 的默认链范围。

---

### F2 — `get_option_chain()` 新参数

扩展：

```python
def get_option_chain(
    symbol: str,
    option_type: str,
    target_dte: int,
    dte_range: int = 7,
    center_strike: float | None = None,
    strike_window: int = 10,
) -> list[dict]:
```

说明：
- `center_strike`：理论中心 strike
- `strike_window`：返回中心附近最多多少档候选

推荐做法：
1. 仍先用 `fromDate / toDate` 收缩 expiry 范围
2. 选出 OI 最高的有效 expiry
3. 在该 expiry 下按 `abs(strike - center_strike)` 排序
4. 只保留最近的 `strike_window` 档

---

### F3 — `build_strike_scan()` 接收中心 strike

扩展：

```python
def build_strike_scan(
    symbol: str,
    option_type: str,
    target_delta: float,
    target_dte: int,
    center_strike: float | None = None,
) -> dict:
```

逻辑：
- 先按 `center_strike` 收窄链
- 再复用 `SPEC-039` 已有的：
  - 硬过滤
  - score 计算
  - recommended 标记
  - fallback 机制

---

### F4 — `open-draft` 调用方式更新

`web/server.py` 在为每个 leg 生成 strike scan 时：

```python
center_strike = priced_legs[idx]["strike"]
```

然后：

```python
build_strike_scan(
    symbol=rec.underlying,
    option_type=leg["option"],
    target_delta=target_delta,
    target_dte=leg["dte"],
    center_strike=center_strike,
)
```

这意味着 scanner 会围绕当前理论 strike 的附近档位扫描，而不是盲扫一整段默认链。

---

### F5 — 过滤规则保持不变

`SPEC-039` 中这些规则不变：

- `spread_pct > 0.50` → 排除
- `open_interest < 100` → 排除
- `bid <= 0` → 排除
- `volume == 0` → 只降权，不排除

本 spec 的目标是：
- 提高“候选质量”
- 减少“不必要 IO”

而不是改变评分口径。

---

## 边界条件与约束

- 不新增四腿 schema
- Iron Condor 仍按 `SPEC-039` 当前澄清：只扫 call 侧
- Bull Call Diagonal 的 90 DTE long leg 仍不在范围内
- 不做实时自动刷新
- 不做自动选择 expiry 的逻辑重构
- **缓存 key 必须包含 `center_strike`**（防止不同 center 命中同一缓存）：格式如 `f"chain:{symbol}:{option_type}:{expiry}:{center_strike}"`；`center_strike=None` 时 key 不变（向后兼容）

---

## 不在范围内

- 调整 `open_interest` 的硬过滤阈值
- 对指数链引入单独评分公式
- 多步二次请求（例如先粗扫再精扫两轮）
- 对 scanner 结果做后台预热

---

## 验收标准

1. **AC1**：`get_option_chain(..., center_strike=...)` 只返回中心附近的局部候选，而不是宽泛整段链
2. **AC2**：`open-draft` 的 scanner 请求会把理论 strike 作为 `center_strike` 传入
3. **AC3**：在当前 `$SPX` short-call 场景下，比 `SPEC-039` 更容易拿到接近目标 delta 的候选
4. **AC4**：不影响 Schwab 未配置时的旧行为
5. **AC5**：前端 UI 与 `SPEC-039` 保持兼容，无需新增交互

---

## 实施顺序建议

1. 先扩展 `schwab/client.py` 的 `get_option_chain()`
2. 再把 `center_strike` 接进 `schwab/scanner.py`
3. 最后在 `web/server.py` 的 `open-draft` 调用点传入理论 strike

---

## 备注

依赖：
- `SPEC-039`

后续可能还需要单独一个增量 spec：
- 若中心扫描后仍频繁 fallback，再考虑放宽 `OI` 硬过滤或对 index options 使用不同流动性口径
