# SPEC-018: Evaluation Metrics Reform — Tail Stats, Regime Breakdown, Distribution Shape

## 目标

**What**：在现有 `compute_metrics` 输出基础上，补充四类缺失的评估维度：
1. **Calmar ratio**（TotalPnL / |MaxDD|）— 衡量 drawdown 调整后回报
2. **CVaR 5% / 10%**（条件尾部均值）— 极端场景下的平均损失
3. **PnL 分布形态**（skewness / excess kurtosis）— 揭示结构性不对称
4. **Regime-specific Sharpe / WR / MaxDD**（体制分层）— 识别哪个体制是系统弱点

**Why**（Prototype 实证，`SPEC-018_metrics_reform.py`，2026-03-30，26yr 386 笔）：

现有 `compute_metrics` 仅输出 Sharpe / WR / TotalPnL，无法区分：
- 策略是"高胜率但偶发大输"（short-vol 典型）还是"均匀分布"
- 哪个 regime 贡献了大部分损失
- 尾部损失的绝对量（止损阈值设定依据）

---

## 核心数据（Prototype 结果，2000–2026 vs 2022–2026）

### 整体 extended metrics

| 指标 | 26yr (n=386) | 3yr (n=69) | 解读 |
|------|-------------|-----------|------|
| Total PnL | $+192,234 | $+28,662 | — |
| Win Rate | 75.6% | 66.7% | 3yr 降低 |
| Sharpe | 1.54 | 1.15 | 3yr 降低 |
| Max DD | $−7,329 | $−6,811 | 相近 |
| **Calmar** | **26.23** | **4.21** | 3yr 显著恶化 |
| CVaR 5% | $−2,591 | $−2,564 | 尾部一致 |
| CVaR 10% | $−2,003 | $−2,293 | 3yr 尾部更重 |
| **Skewness** | **−0.62** | **−0.08** | 26yr 负偏；3yr 趋近对称 |
| **Kurtosis** | **+2.85** | **+0.32** | 26yr 厚尾；3yr 近正态 |
| Payoff ratio | 0.92 | 1.06 | short-vol 结构：avg_loss ≥ avg_win |

### Regime 分层（关键发现）

| Regime | 26yr Sharpe | 3yr Sharpe | 26yr MaxDD | 3yr MaxDD |
|--------|------------|-----------|-----------|---------|
| LOW_VOL | 1.69 | 1.66 | $−6,237 | $−3,820 |
| NORMAL | 1.19 | 1.28 | **$−10,260** | $−3,035 |
| HIGH_VOL | **1.83** | **0.60** | $−4,458 | $−4,458 |

### 各策略尾部损失对比（26yr）

| 策略 | n | Skewness | CVaR 5% | Payoff | WR |
|------|---|---------|---------|--------|-----|
| Bull Call Diagonal | 111 | −0.02 | $−1,963 | **1.81** | 63% |
| Bull Put Spread HV | 79 | −2.09 | $−2,108 | 0.67 | 80% |
| Bear Call Spread HV | 79 | −2.70 | **$−1,639** | 0.67 | 80% |
| Iron Condor | 49 | **−2.66** | **$−5,045** | 0.43 | 84% |
| Iron Condor HV | 45 | −2.05 | $−2,151 | 0.64 | 84% |
| Bull Put Spread | 23 | −1.53 | $−2,991 | 1.04 | 74% |

---

## 关键发现

### 发现 1：Calmar ratio 揭示 3yr 体制恶化（26.23 → 4.21）

26yr Calmar=26.23 说明整体 drawdown 控制良好（$192k 回报 / $7.3k MaxDD）。3yr Calmar=4.21 显示 2022–2026 期间 drawdown 相对收益更大，印证熊市拖拽。这直接支持 SPEC-015（vol spell 限流）的必要性。

### 发现 2：HIGH_VOL Sharpe 3yr 断崖（1.83 → 0.60）

这是所有 regime 中跌幅最大的。26yr HIGH_VOL 是最高 Sharpe 的 regime（1.83），但 3yr 骤降至 0.60，是三个 regime 中最低的。说明 2022–2026 的 HIGH_VOL 期间（BPS_HV、BCS_HV、IC_HV 活跃）表现显著低于历史平均。

这印证了 SPEC-016（haircut 分析）的结论：HV 信用策略真实 alpha 有限；以及 SPEC-015（spell age throttle）的必要性。

### 发现 3：Iron Condor 是结构性最差的策略（尾部三项最差）

- Skewness −2.66（负偏最严重，罕见大亏 tail 最重）
- CVaR 5% $−5,045（最差 5% trades 平均亏损是所有策略中最大）
- Payoff ratio 0.43（avg_win 仅为 avg_loss 的 43%）

与 SPEC-016 结论一致（IC adj_rom 最低，4腿结构摩擦最大），IC 的尾部分布是最危险的。

### 发现 4：Bull Call Diagonal 是分布最健康的策略

- Skewness ≈ 0（近对称）
- Payoff ratio 1.81（avg_win 是 avg_loss 的 1.81 倍）
- 虽然 WR 仅 63%（最低），但当它赢时赢得多，输时输得少

这是 Diagonal 策略被 SPEC-016 haircut 后仍然排名 #4 的结构原因：它的回报分布形态优于所有信用策略。

### 发现 5：NORMAL regime 26yr MaxDD 最大（$−10,260）

出人意料：NORMAL regime（VIX 15–22）的 26yr MaxDD 最大（$−10,260），超过 LOW_VOL 和 HIGH_VOL。可能是因为 NORMAL 期间 IC（4腿）是主要策略，而 IC 的极端亏损最大（见发现 3）。3yr 中 NORMAL MaxDD 仅 $−3,035，说明这是长期历史中偶发性极端事件造成的。

### 发现 6：系统负偏是结构性的 short-vol 特征

26yr Skewness = −0.62，Payoff ratio = 0.92（avg_loss > avg_win）：这是所有 short-vol premium 系统的结构性特征——靠高 WR（75.6%）和频繁小赢维持正期望，但承担偶发大亏的尾部风险。

3yr Skewness = −0.08（趋近对称），Payoff = 1.06：2022–2026 表现更均匀，没有 26yr 中 2008、2020 那样的极端亏损 tail，但 WR 也下降了（66.7%）。

---

## 实现任务

**本 SPEC 为研究性发现文档，但建议在 `compute_metrics` 中加入以下轻量扩展**（Codex 实现）：

### `backtest/engine.py` — `compute_metrics` 新增字段

```python
def compute_metrics(trades, label=""):
    ...
    # 新增（SPEC-018）
    pnls = np.array([t.exit_pnl for t in trades])
    sorted_pnl = np.sort(pnls)
    calmar = total_pnl / abs(max_dd) if max_dd != 0 else 0.0
    cvar5  = float(sorted_pnl[:max(1, int(len(pnls)*0.05))].mean())
    cvar10 = float(sorted_pnl[:max(1, int(len(pnls)*0.10))].mean())
    skew   = float(pd.Series(pnls).skew())
    kurt   = float(pd.Series(pnls).kurtosis())

    return {
        ...（现有字段）...
        "calmar":  calmar,    # Total PnL / |MaxDD|
        "cvar5":   cvar5,     # 最差 5% trades 均值
        "cvar10":  cvar10,    # 最差 10% trades 均值
        "skew":    skew,      # PnL skewness
        "kurt":    kurt,      # PnL excess kurtosis
    }
```

### `notify/telegram_bot.py` — `_format_metrics_msg` 或相关报告函数

在 backtest 报告底部增加一行：
```
Calmar: {calmar:.1f}  CVaR5%: ${cvar5:+,.0f}  Skew: {skew:+.2f}
```

---

## 不在范围内

- Regime 分层报告作为常规输出（复杂度不对等）
- 动态 VaR 计算（需持仓期日度数据）
- 蒙特卡洛 confidence interval
- 每策略独立 calmar / CVaR 报告（可由 prototype 随时运行）

---

## Prototype

路径：`backtest/prototype/SPEC-018_metrics_reform.py`

关键结论：

| 维度 | 26yr | 3yr | 警示 |
|------|------|-----|------|
| Calmar | 26.23 | 4.21 | 3yr 退化 6× |
| CVaR 5% | $−2,591 | $−2,564 | 尾部一致，约 2.5 张合约的单次止损 |
| Skew | −0.62 | −0.08 | 结构性负偏，3yr 趋近对称 |
| HIGH_VOL Sharpe | 1.83 | 0.60 | 3yr HV 策略大幅退化 |
| Iron Condor CVaR5% | $−5,045 | — | IC 尾部最危险 |

---

## Review

- 结论：PASS
- AC1–4 全部通过（手动验证，telegram 包未安装但 bot 代码目视确认）
- 额外亮点：空列表边界改为返回完整零值 dict（超出 SPEC 要求），skew/kurt NaN 边界处理正确

---

## 验收标准

1. `compute_metrics` 返回的字典新增 `calmar`、`cvar5`、`cvar10`、`skew`、`kurt` 五个字段
2. Telegram bot 的 backtest 报告中包含 Calmar ratio 和 CVaR 5%
3. `run_backtest(start_date="2024-01-01")` 正常完成，无异常
4. `compute_metrics(trades=[])` 不抛出异常（空列表边界处理）

---
Status: DONE
