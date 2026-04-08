# SPEC-045: Delta-Seeking Strike Scan via Interpolation

Status: APPROVED

## 目标

**What**：
1. 一次性拉取宽窗期权链，利用 delta 对 strike 的单调性，通过穿越点插值直接定位目标 delta 所在 strike
2. 替代 SPEC-043 的迭代扩窗方案，单次 API 请求解决问题

**Why**：
- 当前 centered scan（SPEC-040）在理论 strike 邻域内取 10 档，live delta 可能远离目标（gap > 0.08）
- 迭代扩窗（SPEC-043 草案）需要多次 API 请求，且没有利用 delta 的结构性信息
- Delta 对 strike 严格单调：PUT |delta| 随 strike 递增，CALL delta 随 strike 递减
- 单调性允许直接扫描找到 delta 穿越点，线性插值估算最优 strike，**零额外 API 请求**

**取代**：SPEC-043（Wider Delta-Seeking Strike Scan）— 完全覆盖，SPEC-043 取消实施。

---

## 核心原则

- 只改 `schwab/client.py` / `schwab/scanner.py`
- 不改 `engine.py / signals / selector / backtest`
- 不改前端 UI 结构，API schema 保持兼容
- 保留 SPEC-039/040/042 的既有评分框架和 relaxed OI 逻辑

---

## 功能定义

### F1 — 宽窗单次拉取

新增常量：

```python
_WIDE_STRIKE_WINDOW = 80   # 覆盖 ±400pt（每5点一档），足以容纳 δ0.20 在极端 VIX 下的位置
```

当 `center_strike` 存在时，`get_option_chain()` 统一使用 `strike_window=_WIDE_STRIKE_WINDOW` 拉取宽链。宽链拉取一次后缓存，后续同参数请求直接命中缓存。

`center_strike=None`（旧路径）行为不变。

---

### F2 — Delta 穿越插值（`_seek_target_delta_strike()`）

```python
def _seek_target_delta_strike(
    chain: list[dict],
    target_delta: float,   # 目标绝对 delta，如 0.20
) -> float | None:
    """
    利用 delta 对 strike 的单调性，在宽窗链中找到 |delta| 穿越 target_delta
    的相邻两档，线性插值估算最优 strike。

    PUT:  |delta| 随 strike 单调递增 → 从低到高扫，找穿越点
    CALL: delta   随 strike 单调递减 → 同样从低到高扫，delta 在递减，
          abs(delta) 也递减，穿越点从另一侧逼近

    返回插值 strike（float），调用方四舍五入到最近5倍数。
    若链为空或无有效 delta，返回 None（fallback 到原始 center_strike）。
    """
    rows = sorted(
        [r for r in chain if r.get("delta") is not None],
        key=lambda r: float(r["strike"]),
    )
    if not rows:
        return None

    abs_deltas = [abs(float(r["delta"])) for r in rows]
    strikes    = [float(r["strike"]) for r in rows]

    # 单次线性扫描找穿越区间
    for i in range(len(rows) - 1):
        lo, hi = abs_deltas[i], abs_deltas[i + 1]
        if min(lo, hi) <= target_delta <= max(lo, hi):
            if hi == lo:
                return strikes[i]
            t = (target_delta - lo) / (hi - lo)
            return strikes[i] + t * (strikes[i + 1] - strikes[i])

    # target 超出链覆盖范围：返回最近边界
    if abs(abs_deltas[0] - target_delta) <= abs(abs_deltas[-1] - target_delta):
        return strikes[0]
    return strikes[-1]
```

---

### F3 — `build_strike_scan()` 新流程

```python
_WIDE_STRIKE_WINDOW   = 80
_SCORE_WINDOW         = 10   # 插值落点两侧各保留多少档进评分器

def build_strike_scan(
    symbol: str,
    option_type: str,
    target_delta: float,
    target_dte: int,
    center_strike: float | None = None,
) -> dict:
    if center_strike is None:
        # 旧路径：不做 delta seeking，行为与 SPEC-040 前完全相同
        rows = scan_strikes(
            get_option_chain(symbol, option_type, target_dte),
            target_delta=target_delta,
            symbol=symbol,
        )
        return {"rows": rows, "scan_fallback": not bool(rows)}

    # 1. 一次性拉宽链（缓存）
    wide_chain = get_option_chain(
        symbol, option_type, target_dte,
        center_strike=center_strike,
        strike_window=_WIDE_STRIKE_WINDOW,
    )

    # 2. 插值找最优 strike
    sought = _seek_target_delta_strike(wide_chain, abs(float(target_delta)))
    if sought is not None:
        best_center = round(sought / 5.0) * 5   # 对齐到最近5倍数
    else:
        best_center = center_strike              # fallback 到 BS 理论值

    # 3. 从宽链中截取 best_center 邻域
    sorted_chain = sorted(wide_chain, key=lambda r: float(r.get("strike") or 0))
    idx = min(
        range(len(sorted_chain)),
        key=lambda i: abs(float(sorted_chain[i]["strike"]) - best_center),
        default=0,
    )
    lo = max(0, idx - _SCORE_WINDOW)
    hi = min(len(sorted_chain), idx + _SCORE_WINDOW + 1)
    candidate_chain = sorted_chain[lo:hi]

    # 4. 评分推荐
    rows = scan_strikes(candidate_chain, target_delta=target_delta, symbol=symbol)
    return {"rows": rows, "scan_fallback": not bool(rows)}
```

---

### F4 — 缓存 key 含 strike_window（修复 SPEC-040 遗留问题）

`_chain_cache_key()` 当前不含 `strike_window`。引入宽窗后，不同 `strike_window` 对应不同 `strikeCount`（`max(300, window*20)`），API 返回不同，必须隔离。

**修改 `_chain_cache_key()`**：

```python
def _chain_cache_key(
    symbol: str,
    option_type: str,
    target_dte: int,
    dte_range: int,
    center_strike: float | None = None,
    strike_window: int | None = None,
) -> str:
    if center_strike is None:
        return f"chain:{symbol}:{option_type}:{target_dte}:{dte_range}"
    center_key = int(round(float(center_strike)))
    w = int(strike_window) if strike_window is not None else 0
    return f"chain:{symbol}:{option_type}:{target_dte}:{dte_range}:{center_key}:{w}"
```

`center_strike=None` 时 key 格式不变（向后兼容）。

---

### F5 — 推荐逻辑与前端不变

- `scan_strikes()` 评分规则、`recommended=True` 逻辑不变
- `build_strike_scan()` 返回 schema 不变：`{"rows": [...], "scan_fallback": bool}`
- `web/server.py` 和 `index.html` 无需修改

---

## 边界条件与约束

- **单次 API 请求**：`center_strike` 存在时固定用 `strike_window=80`，无迭代，无额外请求
- `_seek_target_delta_strike()` 返回 `None` 时 fallback 到原始 `center_strike`，行为不差于 SPEC-040
- 若穿越点在链覆盖范围之外（极端情形），返回最近边界 strike，不崩溃
- delta 为 None 的合约在插值阶段跳过（评分阶段同样会跳过）
- `center_strike=None` 时行为与 SPEC-040 完全相同
- 不改 `spread_pct / OI` 阈值
- Iron Condor 仍只扫 call 侧

---

## 不在范围内

- 前端展示 `delta_gap`（由 SPEC-044 负责）
- 改动 Telegram / Dashboard 文案
- 修改策略目标 delta
- 对 vol smile 做曲线拟合（线性插值已足够）
- 多轮请求

---

## 修改文件

| 文件 | 改动 |
|------|------|
| `schwab/client.py` | `_chain_cache_key()` 加入 `strike_window`；`get_option_chain()` 调用点同步更新 |
| `schwab/scanner.py` | 新增 `_seek_target_delta_strike()`、`_WIDE_STRIKE_WINDOW`、`_SCORE_WINDOW` 常量；`build_strike_scan()` 改用插值流程 |

---

## 验收标准

1. **AC1**：`center_strike` 存在时，`build_strike_scan()` 只触发一次 Schwab API 请求
2. **AC2**：插值后的 best_center 比原始 BS center_strike 更接近实际 δ=target 的 strike
3. **AC3**：当宽链覆盖范围内存在 δ=0.20 的合约时，推荐候选的 `delta_gap <= 0.08`
4. **AC4**：`_seek_target_delta_strike()` 在全链 |delta| 均高于或低于 target 时，返回最近边界，不崩溃
5. **AC5**：`center_strike=None` 时行为与 SPEC-040 完全相同
6. **AC6**：不同 `strike_window` 有独立 cache key，不互相污染
7. **AC7**：`/api/position/open-draft` 返回 schema 不变，前端兼容

---

## 依赖

- SPEC-039（scan_strikes / build_strike_scan 基础接口）
- SPEC-040（center_strike 参数）
- SPEC-042（relaxed OI for SPX）

**取代 SPEC-043**（已 APPROVED，未实施，由本 SPEC 完全覆盖，SPEC-043 标记为 CANCELLED）

## Review
- 结论：PASS
- AC1–AC7 全部通过
- 插值精度验证：[(7310, 0.22)→(7320, 0.19)]，target=0.20，插值结果 7316.67 ✅
- 加分：build_strike_scan() 附加 delta_gap + interpolated_center 字段，为 SPEC-044 预埋数据

Status: DONE
