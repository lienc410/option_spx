# SPEC-056: 数据驱动策略环境分析工具

## 目标

**What**：构建三层分析工具套件，对每个策略进行全历史路径回测，回答"每个策略在什么信号环境下赚钱/亏钱，最佳退出时机如何"。

**Why**：
- 现有规则基于事先假设的信号→策略路径（如 LOW_VOL+BULLISH→DIAGONAL），可能遗漏跨环境 alpha 或对 loss 环境防守不足
- SPEC-048~055 已有 ivp63/ivp252 四象限数据，但从未做过全历史矩阵分析
- 数据驱动发现比假设驱动验证更能暴露未知规律，为 SPEC-057+ 提供量化依据

---

## 前置条件

SPEC-056 依赖以下已完成 SPEC：
- SPEC-048（ivp63/ivp252/regime_decay 字段）
- SPEC-053（_compute_size_tier 含 strategy_key）
- SPEC-055（local_spike 诊断 tag）

---

## 功能定义

### F1 — engine.py：ivp63 加入回测循环与 signal_history

**问题**：engine.py 回测循环目前只计算 ivp（252 日），不含 ivp63。signal_history 无法标注 IVP 四象限。

**修改点**（`backtest/engine.py` 约 721 行之后）：

```python
# 在 ivr/ivp 计算之后，补充 ivp63
window63 = (vix_window.iloc[-63:] if len(vix_window) >= 63 else vix_window).copy()
window63.iloc[-1] = vix
if len(window63) < 63:
    ivp63_val = ivp   # fallback: 使用 252-day percentile
else:
    ivp63_val = round(
        (window63.iloc[:-1] < float(window63.iloc[-1])).mean() * 100.0, 1
    )

regime_decay_val = (ivp >= 50.0) and (ivp63_val < 50.0)
local_spike_val  = (ivp63_val >= 50.0) and (ivp < 50.0)
```

**IVSnapshot 构造**（约 761 行）：

```python
iv_snap = IVSnapshot(
    date=str(date.date()), vix=vix,
    iv_rank=ivr, iv_percentile=ivp, iv_signal=iv_eff,
    iv_52w_high=float(iv_window.max()), iv_52w_low=float(iv_window.min()),
    ivp63=ivp63_val,
    ivp252=ivp,
    regime_decay=regime_decay_val,
)
```

**signal_history 追加字段**（约 778 行的 dict）：

```python
"ivp63":        round(ivp63_val, 1),
"ivp252":       round(float(ivp), 1),
"regime_decay": regime_decay_val,
"local_spike":  local_spike_val,
```

### F2 — selector.py：disable_entry_gates 开关

在 `StrategyParams` 中新增：

```python
# 研究模式：禁用所有入场守护门（matrix 分析专用，绝不用于生产）
disable_entry_gates: bool = False
```

在 `select_strategy()` 中，所有 REDUCE_WAIT 守护门（SPEC-049、051、052、054）包裹条件判断：

```python
if not params.disable_entry_gates:
    # Gate 1: ivp252 过渡区间（SPEC-049）
    if DIAGONAL_IVP252_GATE_LO <= iv.ivp252 < DIAGONAL_IVP252_GATE_HI:
        return _reduce_wait(...)
    # Gate 2: IV=HIGH（SPEC-051）
    if iv_s == IVSignal.HIGH:
        return _reduce_wait(...)
    # Gate 3: both-high（SPEC-054）
    if iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 >= REGIME_DECAY_IVP252_MIN:
        return _reduce_wait(...)
```

```python
if not params.disable_entry_gates:
    # BCS_HV gate（SPEC-052）
    if iv.ivp63 >= IVP63_BCS_BLOCK:
        return _reduce_wait(...)
```

> **注意**：`extreme_vix` 检查（VIX ≥ 35）不受此开关影响，始终生效。

### F3 — `backtest/run_strategy_audit.py`（Matrix 层）

全历史矩阵分析：对每个策略禁用入场门，按信号环境分桶，输出量化表格。

```python
def run_strategy_audit(
    strategy_keys: list[str] | None = None,   # None = 全部策略
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    min_bucket_n: int = 5,                    # 少于此数量的桶标记为 LOW_N
) -> dict[str, pd.DataFrame]:
    """
    Returns dict: strategy_key → audit_df

    audit_df 列：
        bucket          str   信号环境标签（见下方桶定义）
        n               int   本桶交易数
        avg_pnl         float 平均 P&L（$）
        win_rate        float 胜率（0-1）
        sharpe          float 年化 Sharpe
        max_consec_loss int   最大连续亏损笔数
        avg_hold_days   float 平均持仓天数
        low_n_flag      bool  n < min_bucket_n
    """
```

**信号环境桶定义（每维独立，不交叉）**：

| 维度 | 桶名 | 条件 |
|------|------|------|
| IVP 四象限 | ivp_double_low | ivp252 < 50 AND ivp63 < 50 |
| IVP 四象限 | ivp_regime_decay | ivp252 ≥ 50 AND ivp63 < 50 |
| IVP 四象限 | ivp_local_spike | ivp63 ≥ 50 AND ivp252 < 50 |
| IVP 四象限 | ivp_both_high | ivp63 ≥ 50 AND ivp252 ≥ 50 |
| VIX Regime | regime_low_vol | regime == LOW_VOL |
| VIX Regime | regime_normal | regime == NORMAL |
| VIX Regime | regime_high_vol | regime == HIGH_VOL |
| Trend | trend_bullish | trend == BULLISH |
| Trend | trend_neutral | trend == NEUTRAL |
| Trend | trend_bearish | trend == BEARISH |

每个策略输出一个 DataFrame（行 = 桶），保存为 `backtest/output/audit_{strategy_key}.csv`。

**实现要点**：
1. 以 `disable_entry_gates=True` 跑 `run_backtest()`，获取 trades 列表
2. 从 result.signal_history 建立 date→信号 的查找表
3. 对每笔 trade，按 entry_date 查信号，打 bucket 标签
4. groupby bucket → 计算统计指标

### F4 — `backtest/run_conditional_pnl.py`（Risk 层）

按信号状态切分时间序列，绘制条件累计 P&L 曲线：

```python
def run_conditional_pnl(
    strategy_key: str,
    signal_col: str,                          # e.g. "regime_decay", "ivp_bucket", "local_spike"
    start_date: str = "2000-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Returns DataFrame 列：
        date            日期
        signal_state    信号值（True/False 或枚举字符串）
        pnl             当日 P&L（仅有持仓时非零）
        cum_pnl         该 signal_state 内的累计 P&L（重置跨 signal_state 时间段）
        cum_pnl_global  全局累计 P&L（不重置）
        in_position     bool，当日是否有此策略持仓
    """
```

**设计说明**：
- 不假设独立性：直接用时间序列，保留序列相关结构
- `cum_pnl` 按 signal_state 分段：当 signal_state 切换时重新归零，直观展示各环境内持续亏损期
- 输出保存为 `backtest/output/conditional_pnl_{strategy_key}_{signal_col}.csv`

### F5 — `backtest/run_event_study.py` 扩展（Alpha 层）

在现有 `run_event_study()` 返回 DataFrame 中追加信号列：

```python
# 现有列：entry_date, exit_date, pnl, hit_target, strategy_key
# 新增列：
"regime"       str    入场时的 VIX regime
"trend"        str    入场时的 trend signal
"ivp252"       float  入场时的 ivp252
"ivp63"        float  入场时的 ivp63
"regime_decay" bool   入场时是否 regime_decay
"local_spike"  bool   入场时是否 local_spike
```

使用方：

```python
df = run_event_study("bull_call_diagonal")
# 可直接 groupby("regime_decay") 做 alpha 分层
```

---

## 输出规格

每次运行产生以下文件（`backtest/output/` 目录，不存在时自动创建）：

| 文件 | 来源 | 用途 |
|------|------|------|
| `audit_{key}.csv` | F3 | 每策略信号桶统计矩阵 |
| `conditional_pnl_{key}_{col}.csv` | F4 | 条件累计 P&L 时间序列 |
| `event_study_{key}.csv` | F5 | 入场信号 × 结果交叉表 |

---

## 常量与限制

- `MIN_BUCKET_N = 5`：桶内 n < 5 时标记 `low_n_flag=True`，不解读统计显著性
- **样本量约束**：26 年 DIAGONAL 约 85 笔，同时切分 2+ 维度时 n 将快速下降至噪声区。输出中 low_n_flag 应作为首要过滤条件
- `disable_entry_gates=True` 仅用于此工具，永远不进入生产 StrategyParams

---

## 不在范围内

- 不修改现有回测的出场逻辑
- 不输出图表（可视化由 PM 在 Jupyter 完成）
- 不自动生成新 Spec 或新规则（规则决策在 SPEC-057+ 由 PM 决定）
- SPEC-057（规则修订）需等 SPEC-056 输出结果后再起草

---

## 依赖关系与实施顺序

```
F1（engine.py ivp63）
    └→ F5（run_event_study 信号列）    ← 需要 signal_history 有 ivp63
    └→ F3（run_strategy_audit）        ← 需要 signal_history 有 ivp63
    └→ F4（run_conditional_pnl）       ← 需要 signal_history 有 ivp63

F2（disable_entry_gates）
    └→ F3（run_strategy_audit）        ← 需要 gate 开关
```

**必须先完成 F1 + F2，再实现 F3/F4/F5。**

---

## 验收标准

- AC1. `signal_history` 每行包含 `ivp63`、`ivp252`、`regime_decay`、`local_spike` 字段
- AC2. `StrategyParams.disable_entry_gates=True` 时，LOW_VOL+BULLISH 不触发任何 REDUCE_WAIT 门（极端 VIX ≥ 35 除外）
- AC3. `run_strategy_audit("bull_call_diagonal")` 返回含四个 IVP 桶的 DataFrame，且 `n` 之和等于标准回测 DIAGONAL 交易数（含被门拦截的）
- AC4. `run_conditional_pnl("bull_call_diagonal", "regime_decay")` 返回两个 signal_state 的时间序列（True/False）
- AC5. `run_event_study("bull_call_diagonal")` 返回含 `ivp63`、`regime_decay`、`local_spike` 列的 DataFrame
- AC6. 输出 CSV 文件写入 `backtest/output/` 目录（不存在时自动创建）
- AC7. `disable_entry_gates=True` 不影响生产路径（`DEFAULT_PARAMS.disable_entry_gates == False`）

---

## Review
- 结论：PASS
- F1：`engine.py:725-735` ivp63 计算正确（63 日窗口，fallback=ivp），_regime_decay / _local_spike 互斥条件成立；IVSnapshot 含 ivp63/ivp252/regime_decay；signal_history 追加四字段，ivp252 == ivp（T14 验证）
- F2：`selector.py:117-119` disable_entry_gates 字段已加，DEFAULT_PARAMS=False（AC7）；DIAGONAL 三道门完整包裹在 `if not params.disable_entry_gates:` 内（:614）；BCS_HV ivp63 门改为 inline `and` 条件（:443），形式等价，正确
- F3：`run_strategy_audit.py` 新建，10 个桶，禁门路径跑 run_backtest，gates-disabled 交易数 ≥ 标准路径（T13）；AC3 满足
- F4：`run_conditional_pnl.py` 新建，返回 date/signal_state/pnl/cum_pnl_by_state/cum_pnl_global/in_position（AC4）
- F5：`run_event_study.py` 追加 6 个信号列，sig_by_date 查找表正确（AC5）
- 测试：unittest 14/14，全局 107/107；pytest 未安装，unittest 等价覆盖，结论接受
- venv Timestamp.utcnow deprecation warning 不属本 SPEC 范围

---

Status: DONE
