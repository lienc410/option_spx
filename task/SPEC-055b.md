# SPEC-055b: DIAGONAL local_spike Size-Up（Full）

## 目标

**What**：将 `local_spike` 条件（ivp63 ≥ 50 AND ivp252 < 50）从诊断 tag 升级为 DIAGONAL Full size-up 触发条件，与 regime_decay 并列。

**Why**：
- SPEC-056 矩阵分析（全历史禁门）：local_spike DIAGONAL n=13，avg +$3,516，WR 77%，Sharpe 3.07
- 四种口径（F005 原始、禁门 event study、启门 event study、禁门矩阵）全部指向同一方向，Sharpe 始终是所有 DIAGONAL 子集最高
- F005 原始 WR 92% 因小样本偏高，修正后约 75%，但 alpha 方向无争议
- PM 已决策：全仓 size-up（Full）

## 前置条件

SPEC-055（local_spike 诊断 tag）已 DONE。`local_spike: bool = False` 字段已存在于 `Recommendation`。

---

## 功能定义

### F1 — `_compute_size_tier()` 新增 local_spike 判断

```python
def _compute_size_tier(strategy_key, iv, vix, iv_s, t) -> str:
    if iv.regime_decay and strategy_key == StrategyName.BULL_CALL_DIAGONAL.value:
        return "Full size — regime decay: vol cooling from elevated base (SPEC-053)"
    # SPEC-055b: local_spike size-up
    local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
    if local_spike and strategy_key == StrategyName.BULL_CALL_DIAGONAL.value:
        return "Full size — local spike: near-term vol elevated above calm long-term base (SPEC-055b)"
    return _size_rule(vix, iv_s, t)
```

常量复用 SPEC-055 已有定义（`LOCAL_SPIKE_IVP63_MIN=50`，`LOCAL_SPIKE_IVP252_MAX=50`），无需新增。

---

## 不在范围内

- 不改动 `Recommendation.local_spike` 字段（保留诊断 tag，仍序列化到 API）
- 不改动其他策略的 size tier
- SPEC-054 both_high 门是否撤销另议（SPEC-056c）

---

## 验收标准

- AC1. DIAGONAL + local_spike=True（ivp63=60, ivp252=40）→ size_rule 返回包含 "Full size" 的字符串
- AC2. DIAGONAL + local_spike=True 时 `Recommendation.local_spike` 仍为 True（tag 未被覆盖）
- AC3. BPS + local_spike=True → 不触发 Full（走正常 _size_rule）
- AC4. DIAGONAL + double_low（ivp63=40, ivp252=40）→ 不触发 Full

## 实施方式

Fast Path（单文件 `strategy/selector.py`，改动 ≤ 10 行，仅修改 `_compute_size_tier()` 内部逻辑）

---

Status: DONE
