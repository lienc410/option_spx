# SPEC-042: Index Option Liquidity Filter Relaxation

Status: APPROVED

## 目标

**What**：
1. 优化 Schwab live strike scanner 在指数期权上的候选过滤
2. 避免 `$SPX` 已拿到邻域链数据却因 `open_interest < 100` 被整批清空
3. 保持 `SPEC-039/040` 的 centered scan 与前端交互不变

**Why**：
- 当前 `$SPX` live chain 常出现：
  - 已经扫到理论 strike 邻域
  - `bid > 0`
  - 但 `open_interest = 0`
  - 且部分合约点差仍可接受
- 由于 `SPEC-039` 将 `open_interest < 100` 设为硬过滤，scanner 会直接 fallback
- 结果是“有链数据，但无推荐”，影响手动录入体验

---

## 核心原则

- 只调整 `schwab/scanner.py` 的流动性过滤逻辑
- 只对指数链生效，首版仅限 `SPX`
- 不改 `engine.py / signals / selector / backtest`
- 不改 `SPEC-039/040` 的 centered chain 获取方式
- 不新增前端交互

---

## 功能定义

### F1 — 指数链识别

scanner 需要知道当前链是否属于指数产品。

首版规则：

```python
is_index_symbol = symbol.upper() in {"SPX", "$SPX"}
```

仅当 `is_index_symbol == True` 时，应用本 spec 的 relaxed OI 逻辑。

---

### F2 — OI 硬过滤改为降权

当前硬过滤：

```python
if open_interest < 100:
    continue
```

调整后：

- 普通产品：保持原规则不变
- 指数产品（首版仅 `SPX`）：取消 `open_interest < 100` 的硬排除
- 改为把低 OI 计入评分 penalty

示意：

```python
if not is_index_symbol and open_interest < 100:
    continue

oi_penalty = ...
```

---

### F3 — 评分公式扩展

保持原本四项框架不变：

- delta 偏离
- spread_pct
- OI
- volume penalty

但对于指数链：
- 低 OI 不再直接 `continue`
- 而是在 score 中体现更高 penalty

推荐做法：

```python
if is_index_symbol:
    oi_penalty = 0.35 if open_interest <= 0 else 0.2 * (1 / math.log(open_interest + 2))
else:
    oi_penalty = 0.2 * (1 / math.log(open_interest + 1))

score = (
    abs(actual_delta - float(target_delta)) * 0.4
    + spread_pct                             * 0.4
    + oi_penalty
    + volume_penalty
)
```

说明：
- `oi_penalty` **替换**原 `(1 / math.log(open_interest + 1)) * 0.2` 项，不是叠加
- `open_interest == 0` 时 penalty 最高 0.35，仍明显降权但不全部丢弃
- `volume == 0` 仍保留轻度降权（+0.1）
- 非指数路径的 `log(open_interest + 1)` 在 OI=0 时分母为零；当前靠硬过滤（`< 100`）屏蔽，实现时不要误删非指数的 `continue`

---

### F4 — 其他硬过滤保持不变

这些规则不变：

- `bid <= 0` → 排除
- `spread_pct > 0.50` → 排除

本 spec 只放宽 OI 口径，不放宽价格质量底线。

---

### F5 — 推荐逻辑不变

仍保持：

- 按 score 升序排序
- 第一名 `recommended = True`
- 若最终候选为空，则 `scan_fallback = True`

即：
- 前端 UI 不需要修改
- `/api/position/open-draft` 不需要修改 schema

---

## 边界条件与约束

- 首版仅处理 `SPX`
- 不为 ETF/个股链改规则
- 不单独修改 `spread_pct` 阈值
- 不改 centered scan 窗口大小
- 不新增“soft fallback”或解释标签
- 不做多轮请求

---

## 不在范围内

- 改动 `SPEC-040` 的 centered chain 机制
- 新增 scanner 原因解释 UI
- 为不同指数引入不同 penalty 参数
- 引入 Greeks/vega/skew 的额外评分项
- 对 put/call 分别定不同流动性规则

---

## 验收标准

1. **AC1**：`SPX` 链中 `open_interest = 0` 的候选不再被硬过滤全部丢弃
2. **AC2**：普通产品仍保持 `open_interest < 100` 的原硬过滤逻辑
3. **AC3**：`bid <= 0` 与 `spread_pct > 0.50` 的排除规则不变
4. **AC4**：`/api/position/open-draft` 返回 schema 不变，前端无需新增交互
5. **AC5**：当前 `$SPX` short-call live 场景下，比 `SPEC-040` 更容易得到非 fallback 的推荐结果

---

## 实施顺序建议

1. 扩展 `schwab/scanner.py`，让 `scan_strikes()` 感知 symbol
2. 保留普通产品原逻辑
3. 对 `SPX` 加 relaxed OI penalty
4. 补测试：
   - `SPX` 低 OI 仍可保留候选
   - 非 `SPX` 低 OI 仍被排除

---

## 备注

依赖：
- `SPEC-039`
- `SPEC-040`

后续可能的增量 spec：
- 若 relaxed OI 后仍频繁 fallback，可考虑新增”fallback reason”展示
- 若表现稳定，再考虑把相同规则扩展到其他 index symbols

## Review
- 结论：PASS
- AC1-AC5 全部通过
- P1 fix 已落地：score 公式用 `oi_penalty` 变量替换原 OI 项，非指数路径同样使用变量，一致
- `_is_index_symbol()` 独立函数，便于后续扩展到其他指数
- live sanity 已验证：SPX short-call 场景 rows=1, fallback=False

Status: DONE
