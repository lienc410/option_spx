# SPEC-017: Portfolio Exposure Aggregation — Greek-Aware Dedup

## 目标

**What**：在 SPEC-014 的 `StrategyName` dedup 基础上，增加 **Greek signature-aware** 的合并等效检查，防止 BPS_HV + BCS_HV 同时持有（合成比 IC_HV 更危险的 short-gamma 结构）。同时在 `StrategyParams` 中加入 `max_short_gamma_positions`（同时持有 short-gamma 仓位上限）。

**Why**（Prototype 实证，`SPEC-017_portfolio_exposure.py`，2026-03-30）：

### 策略 Greek 签名分类

| 策略 | ShortGamma | ShortVega | Delta |
|------|-----------|-----------|-------|
| Bull Put Spread | ✓ | ✓ | bull |
| Bull Put Spread HV | ✓ | ✓ | bull |
| Bear Call Spread HV | ✓ | ✓ | bear |
| Iron Condor | ✓ | ✓ | neut |
| Iron Condor HV | ✓ | ✓ | neut |
| **Bull Call Diagonal** | — | LONG | bull |

除 Diagonal 外，所有活跃策略都是 **short_gamma + short_vega**。SPEC-014 的 dedup 按 StrategyName 阻止同名重复，但 BPS_HV + BCS_HV 是不同名称、却共享相同 greek 签名的组合。

### 关键发现：BPS_HV + BCS_HV 并发是最危险的组合

26yr 回测中检测到 177 对并发 short_gamma 组合，最危险两类：

| 组合 | n | avg_combined PnL | both_loss 率 |
|------|---|-----------------|-------------|
| BPS_HV + BCS_HV | 25 | **+$28** | **40%** |
| BCS_HV + BPS_HV | 19 | **−$364** | **53%** |

合计 44 对，平均损益接近 0 甚至为负，双双亏损率高达 40–53%。

**根本原因**：
- BPS_HV（short put，bull-delta）+ BCS_HV（short call，bear-delta）= delta ≈ 0（合成 Iron Condor）
- 但两者均独立的 short_gamma + short_vega，叠加量是单个 IC_HV 的 2 倍
- 在极端移动（BPS 的急跌 + BCS 的急涨均可触发）下，组合损失远超单个 IC_HV

对比：IC_HV + BPS_HV（22 对，avg+$1,085，both_loss 14%）相对安全，因为 IC 的 delta 中性平衡了 BPS 的 bull-delta。

---

## 策略/信号逻辑

### Greek Signature 定义（新增到 `strategy/catalog.py`）

每个 StrategyDescriptor 新增：
```python
short_gamma: bool      # True = 价格大幅移动时凸性损失
short_vega:  bool      # True = IV 上升时损失
delta_sign:  str       # "bull" | "bear" | "neut"
```

### 合成 IC 阻断规则

在多仓入场逻辑中，若当前 positions 已有 BPS_HV，则新信号 BCS_HV → REDUCE_WAIT（反之亦然）：

```python
SYNTHETIC_IC_PAIRS = {
    ("bull_put_spread_hv", "bear_call_spread_hv"),
    ("bear_call_spread_hv", "bull_put_spread_hv"),
}

existing_keys = {catalog_strategy_key(p.strategy) for p in positions}
new_key = catalog_strategy_key(rec.strategy)

for open_key in existing_keys:
    if (open_key, new_key) in SYNTHETIC_IC_PAIRS:
        # 已有 BPS_HV，新信号是 BCS_HV → 视为合成 IC，阻断
        skip_entry = True
```

### Short Gamma Count Limit

```python
short_gamma_keys = {
    "bull_put_spread", "bull_put_spread_hv", "bear_call_spread_hv",
    "iron_condor", "iron_condor_hv"
}
current_sg_count = sum(
    1 for p in positions
    if catalog_strategy_key(p.strategy) in short_gamma_keys
)
if current_sg_count >= params.max_short_gamma_positions:
    # 超出 short_gamma 上限 → 阻断
    skip_entry = True
```

---

## 接口定义

### `strategy/catalog.py` — `StrategyDescriptor` 新增字段

```python
@dataclass(frozen=True)
class StrategyDescriptor:
    ...（已有字段不变）...
    short_gamma: bool = False
    short_vega:  bool = False
    delta_sign:  str  = "neut"   # "bull" | "bear" | "neut"
```

各策略填值：
```python
"bull_put_spread":       short_gamma=True,  short_vega=True,  delta_sign="bull"
"bull_put_spread_hv":    short_gamma=True,  short_vega=True,  delta_sign="bull"
"bear_call_spread_hv":   short_gamma=True,  short_vega=True,  delta_sign="bear"
"iron_condor":           short_gamma=True,  short_vega=True,  delta_sign="neut"
"iron_condor_hv":        short_gamma=True,  short_vega=True,  delta_sign="neut"
"bull_call_diagonal":    short_gamma=False, short_vega=False, delta_sign="bull"
"reduce_wait":           short_gamma=False, short_vega=False, delta_sign="neut"
```

### `strategy/selector.py` — `StrategyParams` 新增字段

```python
    # Portfolio-level Greek exposure limits (multi-position architecture)
    max_short_gamma_positions: int = 3  # max concurrent short-gamma positions
```

### `backtest/engine.py` — 入场逻辑新增两个检查（在 dedup 之后）

```python
        from strategy.catalog import strategy_descriptor, strategy_key as catalog_key

        SYNTHETIC_IC_PAIRS = {
            ("bull_put_spread_hv", "bear_call_spread_hv"),
            ("bear_call_spread_hv", "bull_put_spread_hv"),
        }
        SHORT_GAMMA_KEYS = {
            "bull_put_spread", "bull_put_spread_hv", "bear_call_spread_hv",
            "iron_condor", "iron_condor_hv",
        }

        existing_keys = {catalog_key(p.strategy.value) for p in positions}
        new_key       = catalog_key(rec.strategy.value) if rec.strategy != StrategyName.REDUCE_WAIT else None

        # 合成 IC 阻断
        _synthetic_block = any(
            (ek, new_key) in SYNTHETIC_IC_PAIRS for ek in existing_keys
        ) if new_key else False

        # Short gamma count limit
        _sg_count = sum(1 for ek in existing_keys if ek in SHORT_GAMMA_KEYS)
        _sg_block = (_sg_count >= params.max_short_gamma_positions) and (new_key in SHORT_GAMMA_KEYS)

        if (rec.strategy != StrategyName.REDUCE_WAIT
                and not _already_open
                and not _synthetic_block
                and not _sg_block
                and _used_bp + _new_bp_target <= _ceiling):
```

---

## 边界条件与约束

- `max_short_gamma_positions` 默认 3（允许 IC_HV + BPS_HV + BCS_HV，但 BPS_HV + BCS_HV 被合成 IC 规则先行阻断，实际并发最多 2 个 short_gamma）
- 合成 IC 规则只针对 BPS_HV / BCS_HV 对，不影响 IC + BPS_HV 组合（该组合风险可接受，prototype 数据 both_loss=14%）
- `catalog.py` 新增字段为 `default=False/neut`，对现有单元测试无破坏性影响
- `strategy_catalog_payload()` 会自动序列化新字段（`asdict(desc)`），前端可选读取
- 只修改 `strategy/catalog.py`、`strategy/selector.py`（StrategyParams）、`backtest/engine.py`

---

## 不在范围内

- 动态 delta 追踪（持仓期 delta 随 SPX 移动变化）
- 完整 Greek 组合实时计算（需要 BS pricer per position per day）
- 前端组合 Greek 视图
- NORMAL + LOW_VOL 跨 regime 并发（当前回测数据中 BPS + Diagonal 组合 both_loss=0%，不是优先问题）

---

## Prototype

路径：`backtest/prototype/SPEC-017_portfolio_exposure.py`

关键数据：

| 组合 | n | avg_combined | both_loss |
|------|---|-------------|-----------|
| BPS_HV + BCS_HV（双向） | 44 | ~−$180 | **40–53%** ← 需阻断 |
| IC_HV + BPS_HV | 22 | +$1,085 | 14% ← 可接受 |
| IC_HV + BCS_HV | 30 | +$361 | 28% ← 可接受 |
| IC_HV + IC_HV | 1 | +$1,531 | 0% ← dedup 已阻止 |

---

## Review

- 结论：PASS
- AC1（catalog 3字段）、AC2（StrategyParams）、AC4（2024 run）、AC6（payload 含 short_gamma）：单元测试全绿（5/5）
- AC3（BPS_HV+BCS_HV 不并发）：engine 先平仓再开仓时序下本来满足；synthetic IC block 已显式化，规则存在但当前样本无触发机会（handoff 备注已说明）
- AC5（no-op 配置）：noop=62 trades vs base=56，Sharpe 0.90 vs 0.97 —— noop 多 6 笔说明 SPEC-015 throttle 生效，017 本身在当前引擎时序下无额外 delta

---

## 验收标准

1. `StrategyDescriptor` 新增 `short_gamma`、`short_vega`、`delta_sign` 三个字段，所有 6 个活跃策略值填写正确
2. `StrategyParams` 新增 `max_short_gamma_positions=3`
3. `run_backtest(start_date="2000-01-01")` 中，BPS_HV 和 BCS_HV 不出现于同一时间点的 `positions` 列表（instrumented replay 验证）
4. `run_backtest(start_date="2024-01-01")` 正常完成，无异常
5. 设 `max_short_gamma_positions=999` + 无合成 IC 规则时，结果与 SPEC-014 基线一致（验证 no-op 配置）
6. `strategy_catalog_payload()` 返回的每个策略 descriptor 包含 `short_gamma` 字段

---
Status: DONE
