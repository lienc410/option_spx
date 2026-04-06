# Frontend Design Evaluation — HC Claude
# Date: 2026-04-04

---

## 总体判断

定位准确，执行扎实。四页结构（决策 / 矩阵 / 研究 / 参考）覆盖了核心工作流。
视觉设计克制专业，信息密度合理。
但从实际交易操作角度，有几个功能缺口值得认真讨论。

---

## 逐页评估

### Dashboard（/）— 最核心，问题也最集中

**优点**

- Signal Strip → Recommendation 的信息层级清晰
- Intraday Bar 只在开市时显示，避免噪音
- 自动刷新节奏合理（推荐5分钟、日内60秒）

**关键缺口**

**缺口 1：Open Position Panel 信息太少**

当前只显示策略名 + 开仓日期 + roll次数。
交易员每天打开 Dashboard 最想知道的是：

- 已持仓几天？还剩多少 DTE？
- 当前 unrealized P&L 估算？
- 距 50pct profit target 还差多少？
- 距 stop_loss 还有多少缓冲？

server.py 的 `/api/position` 有 strategy/opened_at，
但没有实时重估逻辑。这是最高优先缺口。

**缺口 2：Signal Strip 缺乏方向感**

VIX 显示 22.5，但这是过去30天的高点还是低点？
IV Rank 显示 65，但在上升还是下降？
Signal Strip 是快照，没有方向感。
缺一条极简 sparkline 或 "30d range" 提示。

**缺口 3：推荐卡没有历史胜率锚点**

推荐卡显示 "Bull Put Spread"，但没有：
"历史同类条件下 WR=78%，n=102"

量化交易员需要感受到推荐背后的统计支撑，
不只是文案 rationale。

---

### Matrix（/matrix）— 设计思路对，但单指标不够

**优点**

- 可点击格子看 trade 明细
- 3Y / 10Y / All 切换有价值

**关键缺口**

**缺口 4：WR 是不完整的绩效指标**

WR=80% 但 avg_win=$200 / avg_loss=-$2000 是灾难。
每个格子至少需要：WR + Avg PnL 两个数字。
最好加 E[PnL] = WR × avg_win + (1-WR) × avg_loss。

**缺口 5：没有"你现在在哪个格子"的高亮**

Matrix 是静态策略地图，不告诉你今天落在哪个格子。
Dashboard 和 Matrix 是两个独立孤岛，没有连接。

---

### Backtest（/backtest）— 功能最丰富，有结构性风险

**优点**

- Equity Curve + SPX Trade 图是标配，已实现
- Grid Search 有 max 3 params 限制，防过拟合意识好

**关键缺口**

**缺口 6：Grid Search 没有 in-sample / out-of-sample 警告**

SPEC-021 Protocol 4：在同一份数据上优化 filter 后，
验证必须在独立 OOS 窗口。
但 UI 里 start_date 完全由用户自填，没有任何提示。
用户可以在 2000-2026 全段做 sweep，结果是纯 in-sample 优化。
这是一个认知陷阱，应加警告文字。

**缺口 7：只有 MaxDD 数字，没有 Drawdown 时序图**

单一数字遮盖了回撤结构。
2011 年 -$7,500 是3天内还是3个月内恢复？
这对判断策略风险非常关键。

**缺口 8：没有 Year-by-Year PnL 柱状图**

Stress year analysis（2008/2011/2015/2020/2022）
是本系统研究的核心关切（SPEC-023）。
但 Backtest 页看不到年度拆解，必须跑 prototype 才能看到。
应作为标准视图。

---

### Margin（/margin）— 静态文档，有一个真正的功能缺口

**优点**

- 把 Schwab PM 逻辑文档化是必要的，是知识锚点

**关键缺口**

**缺口 9：没有 live BP 利用率计算器**

这是 Margin 页最大空缺：
今天如果开一个 BPS，estimated BP 是多少？
当前账户还有多少 BP 余量？
目前完全是静态文档，核心功能缺失。

---

## 跨页面结构性缺口

| 缺口 | 影响 |
|------|------|
| 四页相互独立，无数据联动 | Dashboard 推荐和 Matrix 历史胜率没有连线 |
| 无 trade journal（实际成交记录） | 系统推荐 ≠ 实际执行，无法追踪差异 |
| 无 Telegram 通知历史回溯 | 错过的警告无法事后查看 |
| Mobile 未适配 | 开盘时可能需要手机查看日内 alert |

---

## 优先级建议

### 高优先（影响每日操作）

1. Open Position Panel 加入 days_held / DTE remaining / unrealized PnL 估算
2. Matrix 格子加 Avg PnL（不只是 WR）
3. Dashboard 推荐卡加一行 "历史同条件 WR=xx%, n=xx"

### 中优先（影响研究质量）

4. Backtest 加年度 PnL 柱状图（Year-by-Year）
5. Backtest Grid Search 加 OOS 警告提示
6. Margin 加 live BP calculator

### 低优先（体验优化）

7. Signal Strip 加30日区间提示（sparkline 或 range bar）
8. Matrix 高亮当前信号所在格子

---

## 评估来源

- 代码：web/server.py, web/templates/*.html
- 参考研究：SPEC-021（filter complexity）, SPEC-023（stress analysis）
- 评估日期：2026-04-04
