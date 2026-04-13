# SPEC-048: IVP Multi-Horizon Signal Fields + Regime Decay Concept

## 目标

**What**：
1. 在 `IVSnapshot` / `signals/iv_rank.py` 中新增 63 日与 252 日两个 IVP 窗口字段（`ivp63`、`ivp252`）
2. 定义"regime decay"子条件：`ivp252 ≥ 50 AND ivp63 < 50`（长期压力高位，近期已冷却）
3. 在 `_compute_size_tier()` 中为 regime decay 状态添加 HALF → FULL 的 size-up 逻辑

**Why**：
- 现有 `iv_percentile`（252 日 IVP）只提供长期 IV 基准，无法区分"vol 仍在高位"vs"vol 已从高位回落"
- F004 研究发现 regime decay 对 DIAGONAL 有显著正 alpha（Sharpe +3.56）
- 建立多时间窗口 IVP 是后续所有 IVP 四象限 gate 的基础设施

**注意**：SPEC-048 初版对所有策略启用 regime decay size-up；事后发现仅 DIAGONAL 有效（F004），BPS/BPS_HV/BCS_HV 均为负。SPEC-053 修正为 DIAGONAL 专属。

---

## 功能定义

### F1 — ivp63 / ivp252 字段

`IVSnapshot` 新增：
```python
ivp63:  float   # 63 交易日 IVP（过去 63 天中 VIX 低于今日的百分比）
ivp252: float   # 252 交易日 IVP（即现有 iv_percentile，重命名/复用）
```

`signals/iv_rank.py` 新增 `ivp63` 计算：
```python
ivp63 = (vix_close.iloc[-63:] < current_vix).mean() * 100
```

### F2 — regime_decay 标志

```python
REGIME_DECAY_IVP63_MAX  = 50   # ivp63 须低于此值
REGIME_DECAY_IVP252_MIN = 50   # ivp252 须高于此值

regime_decay: bool = ivp63 < REGIME_DECAY_IVP63_MAX and ivp252 >= REGIME_DECAY_IVP252_MIN
```

### F3 — _compute_size_tier size-up（初版，SPEC-053 修正）

```python
def _compute_size_tier(strategy_key: str, iv: IVSnapshot, vix: VixSnapshot) -> str:
    if iv.regime_decay:
        # 初版：所有策略 HALF → FULL（错误，SPEC-053 修正为仅 DIAGONAL）
        return "Full"
    ...
```

---

## 验收标准

- AC1. `IVSnapshot.ivp63` 字段存在，值为 0–100 之间的浮点数
- AC2. `IVSnapshot.ivp252` 等于原 `iv_percentile`（向后兼容）
- AC3. `regime_decay` 在 `ivp252 ≥ 50 and ivp63 < 50` 时为 True
- AC4. `_compute_size_tier` 在 regime decay 时返回 Full（初版，SPEC-053 修正后仅 DIAGONAL 生效）

---

## 修正历史

- SPEC-048 初版 size-up 应用于全策略 → 被 SPEC-053 修正为 DIAGONAL 专属

## Review
- 结论：PASS
- IVSnapshot 新增 ivp63 / ivp252 / regime_decay 字段，默认值正确（0.0 / 0.0 / False）
- ivp63 计算逻辑正确：63 日窗口，数据不足时 fallback 到 iv_pct
- ivp252 == iv_pct（向后兼容）
- regime_decay = ivp252 >= 50 AND ivp63 < 50，逻辑正确
- IVP63_LOOKBACK = 63 常量已定义

---

Status: DONE
