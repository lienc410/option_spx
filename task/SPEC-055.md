# SPEC-055: DIAGONAL local_spike Diagnostic Tag

## 目标

**What**：在 `Recommendation` 中新增 `local_spike: bool` 字段，作为诊断标签（diagnostic tag only）。当 `ivp63 ≥ 50 AND ivp252 < 50` 时为 True，否则 False。不影响 size tier，不影响策略选择。

**Why**：
- F005 研究：local_spike 子条件（n=12），平均 +$3,918，胜率 92%，Sharpe +4.12
- 尽管数据显示正 alpha，n=12 样本量不足以支持 sizing 决策（ChatGPT Review REVISE，采纳 2 条）
- 当前以诊断 tag 形式保存：追踪真实交易数量，达到 n=25 后重新评估 size-up（SPEC-055b）

## ChatGPT Review REVISE 结论

**采纳**：
- n=12 太小，不足以支持 sizing 决策 → 降级为 tag
- 两种状态混淆（local_spike 与 regime_decay 分别是 ivp63 高/ivp252 低 vs ivp63 低/ivp252 高）→ 明确分离

**驳回**：
- "DIAGONAL 是 delta-driven 故 IV 信号无关" → 与 SPEC-049/051/054 研究结论矛盾
- "两个发散方向都 size-up" → 仅保留 regime_decay（F004 验证），local_spike 降级为 tag
- "timing 不成熟" → 改 tag 已解决

---

## 功能定义

### F1 — `Recommendation.local_spike` 字段

```python
@dataclass
class Recommendation:
    ...
    local_spike: bool = False   # ivp63 ≥ 50 AND ivp252 < 50（近期 vol spike，长期基准未高）
```

### F2 — 计算逻辑（在 `select_strategy()` 内）

```python
local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
```

### F3 — 传入所有 Recommendation 构造

所有调用 `_build_recommendation()` 的位置需传入 `local_spike=local_spike`。

### F4 — API 响应（`/api/recommendation`）

JSON 响应包含 `local_spike: bool` 字段。

### F5 — UI 展示

`index.html` 在 Decision Strip 中展示 `local_spike` 标签，颜色：灰蓝色（`#607d8b` 或类似）。

---

## 常量

```python
LOCAL_SPIKE_IVP63_MIN  = 50   # ivp63 须 ≥ 50
LOCAL_SPIKE_IVP252_MAX = 50   # ivp252 须 < 50
```

---

## 不在范围内

- **不** 触发 size-up（此为 SPEC-055b 的前置条件）
- **不** 拦截 DIAGONAL 入场（local_spike 场景不 REDUCE_WAIT）
- SPEC-055b（size-up 重评）需等到真实交易 n ≥ 25 笔后由 PM 决定

---

## 验收标准

- AC1. `Recommendation.local_spike` 字段存在，default=False
- AC2. ivp63=60, ivp252=40 时 `local_spike=True`
- AC3. ivp63=60, ivp252=60 时 `local_spike=False`（both-high，SPEC-054 已拦截）
- AC4. ivp63=40, ivp252=40 时 `local_spike=False`
- AC5. `/api/recommendation` JSON 响应包含 `local_spike` 字段
- AC6. `local_spike=True` 时不改变 size tier（仍为正常 Full/Half 判断）

## Review
- 结论：PASS
- Recommendation.local_spike: bool = False 字段已存在
- 计算在 DIAGONAL 最终入场时：ivp63 >= 50 AND ivp252 < 50
- local_spike 不影响 size tier（_compute_size_tier 不读此字段）
- /api/recommendation 使用 asdict() 序列化，local_spike 自动包含在 JSON 响应中
- 19/19 测试通过，含串联顺序验证（T16–T19）

---

Status: DONE
