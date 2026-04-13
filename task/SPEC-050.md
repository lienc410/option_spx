# SPEC-050: Non-Overlapping Event Study Tool

## 目标

**What**：建立 `backtest/run_event_study.py` 和 `backtest/run_event_study_analysis.py`，对每个策略的入场信号触发窗口做 non-overlapping event study，评估入场信号是否具有统计 alpha。

**Why**：
- 现有回测是 sequential simulation，无法直接区分"入场信号本身的 alpha"vs"exit timing 的 alpha"
- Event study 方法：提取每个入场信号触发后固定持有期（fixed_hold）的收益，确保窗口不重叠，消除 survivor bias 和 autocorrelation

**研究性质**：仅新增研究工具脚本，不改变任何交易逻辑、selector、engine。

---

## 功能定义

### F1 — `backtest/run_event_study.py`

```python
def run_event_study(
    strategy_key: str,
    fixed_hold_days: int,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
) -> pd.DataFrame
    # 对每个 entry signal 触发日 t：
    # 计算 t → t+fixed_hold_days 的 fixed-hold P&L
    # 保证窗口 non-overlapping：若前一事件还在 hold 期内，跳过
    # 返回 DataFrame: date, entry_signal_day, pnl, strategy_key
```

### F2 — `backtest/run_event_study_analysis.py`

```python
def analyze_event_study(df: pd.DataFrame) -> dict
    # 计算：n, avg_pnl, win_rate, sharpe, p_value
    # 分析 fixed_hold 未触及利润目标的子集（pure entry alpha）
```

---

## 研究发现（F001–F003）

| 发现 | 内容 |
|------|------|
| F001 | n=89，DIAGONAL 平均 +$1,577，胜率 72% |
| F002 | DIAGONAL 是唯一有入场信号 alpha 的策略；fixed_hold 未触目标时均赚 $1,062 |
| F003 | IC fixed_hold=21 天胜率 0%；IC 的 alpha 完全来自 exit timing，与入场信号无关 |

---

## 不在范围内

- 不改变任何 selector / engine / 交易逻辑
- 仅新增研究脚本（`backtest/` 目录下）

---

## 验收标准

- AC1. `run_event_study()` 正确实现 non-overlapping 窗口逻辑
- AC2. DIAGONAL n=89、胜率 ~72% 可由脚本复现
- AC3. IC fixed_hold=21 天胜率接近 0% 可复现

## Review
- 结论：PASS
- run_event_study.py 实现 non-overlapping 窗口逻辑（last_exit 追踪）
- run_event_study_analysis.py 输出 n / avg_pnl / win_rate / sharpe / avg_pnl_no_target
- 两个文件均为研究工具，不改变任何交易逻辑

---

Status: DONE
