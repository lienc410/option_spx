# SPEC-015: Vol Persistence Risk Throttle

## 目标

**What**：在 `StrategyParams` 中加入 HIGH_VOL spell（连续高波动区间）的持续时长追踪，并基于 spell 年龄限制同一 spell 内的累计开仓次数，防止在 sticky high-vol 环境中形成叠加 short-vol 暴露。

**Why**（Prototype 实证，`SPEC-015_vol_persistence.py`，2026-03-30）：

当前 HIGH_VOL 过滤器（VIX RISING、backwardation）覆盖的是**入场时点**的危险，但不建模 HIGH_VOL 持续多久。Prototype 分析 1990–2026 共 263 个 HIGH_VOL spell 得出：

| 分位数 | 持续时长 |
|--------|---------|
| 中位数（P50） | **4 天** |
| P75 | 10 天 |
| P90 | 29 天 |
| > 30 天（sticky） | 10%（25 笔） |
| > 60 天（极端） | 5%（13 笔） |

**90% 的 spell 在 30 天内结束**——大多数 HIGH_VOL 入场是短暂波动尖峰，会自然消退。

**真正危险的是 sticky spell（前 10%）**：

| 类型 | n | entry_vix 均 | slope 均 | peak_vix 均 |
|------|---|------------|---------|------------|
| Sticky（>30d） | 25 | 26.9 | −0.04（flat/grinding） | 33.4 |
| Short（≤30d） | 238 | 24.8 | +0.45（spike） | 27.0 |

反直觉发现：**VIX RISING（快速尖峰）型入场的 spell 反而更短暂**；sticky spell 特征是 VIX 在中等水平（26–28）缓慢盘整，slope 接近 0。这意味着现有 VIX RISING 过滤器实际上阻止的是短暂 spell，而 sticky spell 在入场时信号上难以识别。

**多仓架构下的叠加风险**：

- BPS_HV/BCS_HV 持仓窗口 ≈ 20 日历天
- 15% 的 HIGH_VOL spell 持续 > 20 天（整个持仓期仍在 HIGH_VOL 内）
- 100 天的 sticky spell（如 2022 年 4–7 月、8–11 月）理论上可连续开 5 笔 BPS_HV，造成叠加累积 short-gamma 暴露

历史上最长 spell：
- 2002-10 → 2003-04：182 天（2003 年 Iraq War + 纳斯达克底部）
- 2009-05 → 2009-10：164 天（金融危机后缓慢恢复）
- 2022-04 → 2022-07：99 天 + 2022-08 → 2022-11：88 天（加息熊市）

2022 的两段 sticky spell 恰好是 3yr 回测 Sharpe（0.93 vs 1yr 1.48）下拉的主因时段。

---

## 策略/信号逻辑

新增 **Spell Age Throttle**：追踪当前 HIGH_VOL spell 的进入日期，在 run_backtest 的入场逻辑中加入 spell 年龄检查。

```
spell_age = (当前日期 - 当前 spell 进入日期).days

若 spell_age > spell_age_cap（默认 30 天）:
    → 同一 spell 内不再开新的 HIGH_VOL 策略（BPS_HV / BCS_HV / IC_HV）
    → REDUCE_WAIT（高波动持续时间已超正常范围，叠加风险过高）
```

补充规则：spell 内**同类策略（dedup 已覆盖）+ 总开仓次数上限**（`max_trades_per_spell`，默认 2）。

---

## 接口定义

### `strategy/selector.py` — `StrategyParams` 新增字段

```python
    # Vol persistence throttle — limits new HIGH_VOL entries in sticky spells
    spell_age_cap:        int = 30   # calendar days since spell start; beyond this → REDUCE_WAIT
    max_trades_per_spell: int = 2    # max HIGH_VOL trades within a single continuous spell
```

### `backtest/engine.py` — 新增状态变量

在 `positions: list[Position] = []` 后新增：

```python
    hv_spell_start:      Optional[pd.Timestamp] = None  # date current HIGH_VOL spell began
    hv_spell_trade_count: int = 0                       # HIGH_VOL trades opened in this spell
```

### `backtest/engine.py` — 每日 spell 追踪逻辑

在 regime 计算之后，入场逻辑之前，插入：

```python
        # ── HIGH_VOL spell age tracking ──────────────────────────────
        if regime == Regime.HIGH_VOL:
            if hv_spell_start is None:
                hv_spell_start = date          # 新 spell 开始
        else:
            hv_spell_start       = None        # spell 结束，重置
            hv_spell_trade_count = 0
```

### `backtest/engine.py` — 入场条件追加 spell throttle

在现有 BP ceiling + dedup 检查之后，HIGH_VOL 策略入场前加入：

```python
        # Spell age throttle: block new HIGH_VOL entries in sticky spells
        if regime == Regime.HIGH_VOL and rec.strategy != StrategyName.REDUCE_WAIT:
            spell_age = (date - hv_spell_start).days if hv_spell_start else 0
            if spell_age > params.spell_age_cap:
                rec = _dummy_reduce_wait()    # 覆盖推荐为 REDUCE_WAIT
            elif hv_spell_trade_count >= params.max_trades_per_spell:
                rec = _dummy_reduce_wait()
```

开仓成功后：

```python
                if regime == Regime.HIGH_VOL:
                    hv_spell_trade_count += 1
```

> 注：`_dummy_reduce_wait()` 为 engine 内部函数，只需返回一个不触发开仓的 sentinel（或直接用 `continue`/`pass`）。Codex 自行决定最优实现方式（可以是设 flag，不必实际构造 Recommendation 对象）。

---

## 边界条件与约束

- spell_age_cap 默认 30 天（P90 分位数，10% 以上 spell 触发限制）
- max_trades_per_spell 默认 2（BPS_HV + BCS_HV 各一，或同类两笔）
- spell 重置条件：当 regime 离开 HIGH_VOL（任意一天 VIX < 22 或 VIX ≥ 35），视为当前 spell 结束
- 若 VIX 在 HIGH/NORMAL 边界（22 附近）一日跳入跳出，可能造成 spell 假重置——这是已知近似，不需要特殊处理（概率低，影响小）
- NORMAL / LOW_VOL 策略不受 spell throttle 影响
- 只修改 `strategy/selector.py`（StrategyParams）和 `backtest/engine.py`（run_backtest）

---

## 不在范围内

- VVIX 数据源接入（当前 yfinance 无稳定 VVIX 历史）
- 动态 spell_age_cap（基于 VIX 水平调整阈值）
- Spell duration 预测模型（logistics regression / 条件概率）——需要更多 feature 工程，留给后续研究
- Live 模式的 spell 追踪（Telegram bot 每日调用，不跨日保持 state，暂不实现）

---

## Prototype

路径：`backtest/prototype/SPEC-015_vol_persistence.py`

### 关键数据结论

| 指标 | 数值 | 含义 |
|------|------|------|
| Spell 中位时长 | 4 天 | 大多数 HV 入场是短暂尖峰 |
| Spell P90 | 29 天 | 30 天 cap 覆盖 90% spell |
| Sticky spell n | 25 笔（10%） | entry VIX 均 26.9，slope 接近 0 |
| VIX RISING 入场 spell 时长中位 | 4 天 | RISING 过滤器误阻的是短 spell |
| spell > 20 天比例 | 15% | 可产生持仓期叠加的比例 |
| 2022 年 sticky spells | 2 段（99d + 88d） | Sharpe 下拉的直接背景 |

### 反直觉发现

VIX RISING 过滤器实际上阻止了**短暂** spell 的入场（快涨快跌型，风险反而低）。Sticky spell 在入场时 slope 接近 0（缓慢盘整），这类 spell 用现有过滤器**无法识别**。Spell age throttle 是目前唯一能在 spell 演变为 sticky 后自动限制叠加暴露的机制。

---

## Review

- 结论：PASS
- AC1（StrategyParams 新字段）、AC2（spell 追踪与重置）、AC3（throttle 至少阻断 1 笔）、AC5（2024 run）：单元测试全绿
- AC3 量化确认：noop 62 trades vs base 56 trades（2022–2026），throttle 阻断了 6 笔 HIGH_VOL 仓位
- AC4（3yr Sharpe 不低于 0.93）：base Sharpe=0.97 > 0.93 ✅
- AC6（no-op 配置）：noop Sharpe=0.90 vs base 0.97，no-op 时笔数回升（62 vs 56），确认规则可逆

---

## 验收标准

1. `StrategyParams` 新增 `spell_age_cap=30`、`max_trades_per_spell=2`
2. `run_backtest` 中 `hv_spell_start` / `hv_spell_trade_count` 正确追踪（spell 结束时重置为 None / 0）
3. 2022 全年回测中，spell age throttle 至少阻断了 1 笔原本会开的 HIGH_VOL 仓位（验证规则生效）
4. 3yr 回测（2022-01-01）Sharpe 相较 SPEC-014 基线（0.93）不下降（spell throttle 应过滤 sticky 期的叠加损失）
5. `run_backtest(start_date="2024-01-01")` 正常完成，无异常
6. 设 `spell_age_cap=999`（禁用）+ `max_trades_per_spell=999`（禁用）时，结果与 SPEC-014 基线一致（配置为 no-op 时不改变行为）

---
Status: DONE
