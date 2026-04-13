# Codex 实施指令 — SPEC-048 ~ SPEC-055

**日期**：2026-04-10
**来源**：HC Claude（Quant Researcher）
**优先级**：必须按顺序实施（有依赖关系）

---

## 依赖顺序

```
SPEC-048（建立 ivp63/ivp252/regime_decay 基础设施）
    ↓
SPEC-049, SPEC-051, SPEC-052, SPEC-053, SPEC-054, SPEC-055
（并行，均依赖 SPEC-048 的新字段）
    ↓
SPEC-050（独立研究工具，不依赖上述，可最后实施）
```

**SPEC-048 必须先实施完毕，其他 SPEC 才能开始。**

---

## SPEC-048：IVP Multi-Horizon Fields + Regime Decay

### 文件：`signals/iv_rank.py`

#### 1. `IVSnapshot` 新增字段

```python
@dataclass
class IVSnapshot:
    date:          str
    vix:           float
    iv_rank:       float
    iv_percentile: float
    iv_signal:     IVSignal
    iv_52w_high:   float
    iv_52w_low:    float
    ivp63:         float = 0.0   # ★ 新增：63 交易日 IVP
    ivp252:        float = 0.0   # ★ 新增：252 交易日 IVP（等于 iv_percentile）
    regime_decay:  bool  = False # ★ 新增：ivp252 >= 50 AND ivp63 < 50
```

#### 2. 新增常量

```python
IVP63_LOOKBACK = 63   # 新增
# LOOKBACK_DAYS = 252  ← 已有，勿改
```

#### 3. `get_current_iv_snapshot()` 新增 ivp63 / ivp252 / regime_decay 计算

在现有计算 `iv_pct` 之后，追加：

```python
# ivp63：过去 63 交易日中 VIX 低于今日的百分比
window63 = df["vix"].iloc[-IVP63_LOOKBACK:].copy()
if current_vix is not None:
    window63.iloc[-1] = float(current_vix)
ivp63 = round((window63.iloc[:-1] < float(window63.iloc[-1])).mean() * 100.0, 1)
if len(window63) < IVP63_LOOKBACK:
    ivp63 = iv_pct  # 数据不足时 fallback 到 ivp252

ivp252 = iv_pct  # 复用已有计算，重命名语义

regime_decay = (ivp252 >= 50.0) and (ivp63 < 50.0)
```

并在 `IVSnapshot(...)` 构造中传入这三个新字段。

#### 4. `IVSnapshot.__str__` 可选更新

在输出末尾追加：
```python
f" | ivp63={self.ivp63:.1f} ivp252={self.ivp252:.1f} regime_decay={self.regime_decay}"
```

---

### 文件：`strategy/selector.py`

#### 5. 新增常量（在现有 IVP 常量之后）

```python
# IVP multi-horizon thresholds (SPEC-048~055)
REGIME_DECAY_IVP63_MAX   = 50   # ivp63 须 < 50（regime decay 条件）
REGIME_DECAY_IVP252_MIN  = 50   # ivp252 须 >= 50（regime decay 条件）
LOCAL_SPIKE_IVP63_MIN    = 50   # ivp63 须 >= 50（local_spike / both-high 条件）
LOCAL_SPIKE_IVP252_MAX   = 50   # ivp252 须 < 50（local_spike 条件）
IVP63_BCS_BLOCK          = 70   # BCS_HV 拦截阈值（SPEC-052）
DIAGONAL_IVP252_GATE_LO  = 30   # SPEC-049 过渡区间下限
DIAGONAL_IVP252_GATE_HI  = 50   # SPEC-049 过渡区间上限
```

#### 6. `Recommendation` 新增 `local_spike` 字段

```python
@dataclass
class Recommendation:
    ...（已有字段不变）...
    local_spike: bool = False  # ★ 新增：ivp63 >= 50 AND ivp252 < 50（诊断 tag only）
```

#### 7. `_build_recommendation()` 新增 `local_spike` 参数

```python
def _build_recommendation(
    strategy: StrategyName,
    *,
    ...（已有参数不变）...
    local_spike: bool = False,    # ★ 新增
) -> Recommendation:
    ...
    return Recommendation(
        ...（已有字段不变）...
        local_spike = local_spike,  # ★ 新增
    )
```

#### 8. `_compute_size_tier()` 新增（新函数，替代 `_size_rule` 的 regime decay 逻辑）

在 `_size_rule()` 之后插入：

```python
def _compute_size_tier(
    strategy_key: str,
    iv: IVSnapshot,
    vix: VixSnapshot,
    iv_s: IVSignal,
    t: TrendSignal,
) -> str:
    """
    Two-tier sizing with regime decay override for DIAGONAL only (SPEC-053).
    """
    if iv.regime_decay and strategy_key == StrategyName.BULL_CALL_DIAGONAL.value:
        return "Full size — regime decay: vol cooling from elevated base (SPEC-053)"
    # Fall through to original _size_rule logic
    vix_rising = (vix.trend == Trend.RISING)
    signals_favor_sell = iv_s in (IVSignal.HIGH, IVSignal.NEUTRAL)
    if not vix_rising and signals_favor_sell:
        return "Full size — risk ≤ 3% of account (signals agree + VIX flat/falling)"
    return "Half size — risk ≤ 1.5% of account (VIX rising or signals mixed)"
```

---

## SPEC-049：DIAGONAL Gate — ivp252 过渡区间

### 文件：`strategy/selector.py`

在 `select_strategy()` 的 `LOW_VOL + BULLISH` 分支（当前约第 575 行）：

**在原有入场逻辑之前插入**（第一道门）：

```python
if t == TrendSignal.BULLISH:
    # ── Gate 1 (SPEC-049): ivp252 marginal zone ──────────────────
    if DIAGONAL_IVP252_GATE_LO <= iv.ivp252 <= DIAGONAL_IVP252_GATE_HI:
        return _reduce_wait(
            f"LOW_VOL + BULLISH but ivp252={iv.ivp252:.0f} in {DIAGONAL_IVP252_GATE_LO}–{DIAGONAL_IVP252_GATE_HI} "
            "marginal zone — long-term vol environment transitional; DIAGONAL edge reduced",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
            params=params,
        )

    # ── Gate 2 (SPEC-051): IV=HIGH in LOW_VOL ────────────────────
    # ... (SPEC-051 在此插入，见下)

    # ── Gate 3 (SPEC-054): both-high ────────────────────────────
    # ... (SPEC-054 在此插入，见下)

    # 通过全部门 → DIAGONAL
    action = get_position_action(
        StrategyName.BULL_CALL_DIAGONAL.value,
        is_wait=False,
        strategy_key=catalog_strategy_key(StrategyName.BULL_CALL_DIAGONAL.value),
    )
    local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
    return _build_recommendation(
        StrategyName.BULL_CALL_DIAGONAL,
        vix=vix, iv=iv, trend=trend,
        legs=[
            Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
            Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
        ],
        size_rule=_compute_size_tier(
            StrategyName.BULL_CALL_DIAGONAL.value, iv, vix, iv_s, t
        ),
        rationale="LOW_VOL + BULLISH — theta is cheap; use 45 DTE short leg to widen collection window",
        position_action=action,
        macro_warning=macro_warn,
        local_spike=local_spike,   # ★ SPEC-055
    )
```

---

## SPEC-051：DIAGONAL Gate — IV=HIGH

在 Gate 1（SPEC-049）之后，Gate 3（SPEC-054）之前插入：

```python
    # ── Gate 2 (SPEC-051): IV=HIGH in LOW_VOL ────────────────────
    if iv_s == IVSignal.HIGH:
        return _reduce_wait(
            f"LOW_VOL + BULLISH but IV=HIGH (IVP={iv.iv_percentile:.0f}) — "
            "vol expansion signal in low-vol regime; DIAGONAL short leg exposed",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
            params=params,
        )
```

---

## SPEC-054：DIAGONAL Gate — both-high

在 Gate 2（SPEC-051）之后，最终 DIAGONAL 入场之前插入：

```python
    # ── Gate 3 (SPEC-054): both-high ─────────────────────────────
    if iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 >= REGIME_DECAY_IVP252_MIN:
        return _reduce_wait(
            f"LOW_VOL + BULLISH but ivp63={iv.ivp63:.0f} >= 50 AND ivp252={iv.ivp252:.0f} >= 50 "
            "(both-high) — near-term AND long-term vol stressed; DIAGONAL tail risk too high",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
            params=params,
        )
```

---

## SPEC-052：BCS_HV Gate — ivp63 高压拦截

### 文件：`strategy/selector.py`

在 `HIGH_VOL + BEARISH` 分支，现有 `VIX_RISING` 检查之后插入：

```python
        # P3 (SPEC-052): ivp63 >= 70 — VIX at 63-day high, mean reversion risk too elevated
        if iv.ivp63 >= IVP63_BCS_BLOCK:
            return _reduce_wait(
                f"HIGH_VOL + BEARISH but ivp63={iv.ivp63:.0f} >= {IVP63_BCS_BLOCK} — "
                "VIX at 63-day high; mean reversion risk too elevated for BCS_HV short call",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BEAR_CALL_SPREAD_HV.value,
                params=params,
            )
```

---

## SPEC-053：Regime Decay → DIAGONAL Only（已在 SPEC-048 §8 实现）

`_compute_size_tier()` 的实现已包含此逻辑（strategy_key 参数判断）。无需额外修改。

**验证点**：
- `_compute_size_tier(StrategyName.BULL_CALL_DIAGONAL.value, ...)` 在 regime_decay=True 时返回 "Full size — regime decay..."
- `_compute_size_tier(StrategyName.BULL_PUT_SPREAD.value, ...)` 在 regime_decay=True 时**不触发** Full override，走原 _size_rule 逻辑

---

## SPEC-055：local_spike 诊断 Tag（已在 SPEC-049 §DIAGONAL 入场中实现）

`local_spike` 字段已在 DIAGONAL 最终入场时计算并传入 `_build_recommendation()`。

**额外要求**：
1. 在所有其他 `_build_recommendation()` 调用点，`local_spike` 保持默认 False（不需要传参，有默认值）
2. `web/server.py` 的 `/api/recommendation` endpoint 中，确保 `local_spike` 字段被序列化到 JSON 响应（如已用 `dataclasses.asdict()` 或类似方法，自动包含）

---

## SPEC-050：Non-Overlapping Event Study Tool

### 新文件：`backtest/run_event_study.py`

```python
"""
Non-overlapping event study for strategy entry signals.
Evaluates whether the entry signal itself (independent of exit timing)
has statistical alpha.
"""
from __future__ import annotations
import pandas as pd
from backtest.engine import run_backtest
from strategy.selector import StrategyName


def run_event_study(
    strategy_key: str,
    fixed_hold_days: int = 21,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    For each entry signal trigger day, compute the fixed-hold P&L.
    Windows are non-overlapping: if a previous window is still active, skip.

    Returns DataFrame with columns:
        entry_date, exit_date, pnl, hit_target (bool), strategy_key
    """
    result = run_backtest(start_date=start_date, end_date=end_date)
    trades = result.trades

    filtered = [t for t in trades if t.strategy_key == strategy_key]
    filtered.sort(key=lambda t: t.entry_date)

    rows = []
    last_exit = None
    for trade in filtered:
        entry = pd.Timestamp(trade.entry_date)
        if last_exit is not None and entry <= last_exit:
            continue  # skip overlapping window
        exit_date = entry + pd.Timedelta(days=fixed_hold_days)
        last_exit = exit_date
        rows.append({
            "entry_date":  entry,
            "exit_date":   exit_date,
            "pnl":         trade.net_pnl,
            "hit_target":  trade.exit_reason == "50pct_profit",
            "strategy_key": strategy_key,
        })

    return pd.DataFrame(rows)
```

### 新文件：`backtest/run_event_study_analysis.py`

```python
"""
Analyze event study results.
"""
from __future__ import annotations
import math
import pandas as pd
from backtest.run_event_study import run_event_study
from strategy.selector import StrategyName


def analyze_event_study(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    n = len(df)
    avg_pnl = df["pnl"].mean()
    win_rate = (df["pnl"] > 0).mean()
    std = df["pnl"].std()
    sharpe = (avg_pnl / std * math.sqrt(252 / 21)) if std > 0 else 0.0
    no_target = df[~df["hit_target"]]
    avg_no_target = no_target["pnl"].mean() if not no_target.empty else float("nan")
    return {
        "n":               n,
        "avg_pnl":         round(avg_pnl, 0),
        "win_rate":        round(win_rate, 3),
        "sharpe":          round(sharpe, 2),
        "avg_pnl_no_target": round(avg_no_target, 0),
        "n_no_target":     len(no_target),
    }


if __name__ == "__main__":
    for key in [
        StrategyName.BULL_CALL_DIAGONAL.value,
        StrategyName.IRON_CONDOR.value,
        StrategyName.BULL_PUT_SPREAD.value,
    ]:
        df = run_event_study(key, fixed_hold_days=21)
        stats = analyze_event_study(df)
        print(f"\n=== {key} ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
```

---

## 测试要求

### 新增测试文件：`tests/test_spec_048_055.py`

覆盖以下场景：

```python
# SPEC-048
# T1: IVSnapshot.ivp63 存在且为 float
# T2: ivp252 == iv_percentile
# T3: regime_decay=True 当 ivp252=60, ivp63=40
# T4: regime_decay=False 当 ivp252=60, ivp63=60（both-high，不是 decay）

# SPEC-049
# T5: LOW_VOL+BULLISH+ivp252=35 → REDUCE_WAIT

# SPEC-051
# T6: LOW_VOL+BULLISH+iv_s=HIGH+ivp252=20 → REDUCE_WAIT（Gate 2）

# SPEC-054
# T7: LOW_VOL+BULLISH+ivp63=60+ivp252=60+iv_s=NEUTRAL → REDUCE_WAIT（Gate 3）
# T8: LOW_VOL+BULLISH+ivp63=60+ivp252=25+iv_s=NEUTRAL → DIAGONAL（local_spike=True）
#     ivp252=25 < 30，通过 Gate 1；ivp63=60 >= 50 且 ivp252=25 < 50 → local_spike=True

# SPEC-052
# T9: HIGH_VOL+BEARISH+ivp63=75 → REDUCE_WAIT
# T10: HIGH_VOL+BEARISH+ivp63=65 → BCS_HV（其他条件通过前提下）

# SPEC-053
# T11: _compute_size_tier(DIAGONAL, regime_decay=True) → "Full size — regime decay..."
# T12: _compute_size_tier(BPS, regime_decay=True) → 不包含 "regime decay"

# SPEC-055
# T13: Recommendation.local_spike 存在，默认 False
# T14: LOW_VOL+BULLISH+ivp63=60+ivp252=25 → Recommendation.local_spike=True
#      ivp252=25 通过 Gate 1（< 30）；ivp63=60 >= 50 且 ivp252=25 < 50 → local_spike=True
# T15: LOW_VOL+BULLISH+ivp63=40+ivp252=25 → Recommendation.local_spike=False
#      ivp63=40 < 50 → local_spike 条件不满足

# Gate 顺序（串联）
# T16: LOW_VOL+BULLISH+ivp252=35 → 被 Gate 1 拦截（不到 Gate 2/3）
# T17: LOW_VOL+BULLISH+ivp252=20+iv_s=HIGH → 被 Gate 2 拦截（通过 Gate 1）
# T18: LOW_VOL+BULLISH+ivp252=20+iv_s=NEUTRAL+ivp63=60 → 被 Gate 3 拦截
# T19: LOW_VOL+BULLISH+ivp252=20+iv_s=NEUTRAL+ivp63=40 → DIAGONAL（通过全部门）
```

---

## 完成后请提供 handoff 文件

`task/SPEC-048-055_handoff.md`，内容：
- 修改的文件列表（含行号）
- 各 AC 验收状态
- 是否有偏离 SPEC 的实施决策（需注明原因）
