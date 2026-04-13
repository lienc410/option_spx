# SPX Strategy System — Strategy Status 2026-04-12
**Date: 2026-04-12 | 承接 `strategy_status_2026-04-10.md`**

*本版新增内容：*
- *SPEC-061：/ES Short Put 最小生产 Cell — DONE*
- *ES Puts 覆盖缺口盘点（Layer 1 / Layer 3 / -300% stop 实施状态）*
- *Reddit 社区研究评估（不含 Spec 变更）*

*以下章节无变更，请参阅 `strategy_status_2026-04-10.md`：*
- *§1–2：系统定位 / 历史回测基准*
- *§3：信号体系（IVP 多时间窗口）*
- *§4：SPX Credit 决策矩阵（LOW_VOL / NORMAL / HIGH_VOL / EXTREME_VOL）*
- *§5：StrategyParams（25 个字段）*
- *§6：SPX Credit 仓位 Sizing（regime decay / local_spike size-up）*
- *§7：Recommendation 字段（local_spike tag）*

---

## 新增：/ES Short Put 生产组件（SPEC-061，2026-04-12）

### 组件定位

`/ES Short Put` 作为独立生产组件，通过专用 API 路径接入现有系统，**不改动 SPX Credit 主推荐路由**。

当前状态：**最小生产 Cell（MVP）**，仅覆盖入场路径和 BP 检查。止损执行、趋势转负后持仓行为、多 DTE ladder、动态杠杆表、BSH 均不在当前范围内。

### 策略参数

| 参数 | 值 |
|------|----|
| 标的 | `/ES` options（欧式，期货期权） |
| 结构 | 裸卖 put（naked short put） |
| 目标 DTE | 45 |
| 目标 delta | 0.20 |
| 仓位 | 单槽、1 张（硬上限，不可因 VIX 或 BP 余量自动加仓）|
| 止损 | -300% credit（3× 权利金）|
| BP 上限 | 当前总 margin + /ES BP ≤ NLV × 20% |

**实测 BP 数字**：Schwab Order Confirmation 确认 /ES short put buying power effect = **$20,529 / 合约**（20 delta，正常波动率环境下）。

### 入场规则

```
入场条件（全部满足）：
─────────────────────────────────────────────────
  1. Trend filter = BULLISH
     （NEUTRAL / BEARISH / 数据缺失 → 拒绝）

  2. Schwab live BP 可读取（authenticated + not stale）

  3. 当前无 /ES short put 持仓

  4. 当前总 margin + $20,529 ≤ NLV × 20%

  5. /ES 期权链可提供 45 DTE / 20 delta 合约数据

  满足全部条件 → 生成 /ES short put 1-lot 候选
─────────────────────────────────────────────────
```

任何一条不满足：系统按保守口径拒绝，不做乐观回退。

### API 路径

| 端点 | 用途 |
|------|------|
| `GET /api/es/recommendation` | 返回 trend filter 结果和候选推荐（不含 BP 检查）|
| `GET /api/es/position/open-draft` | 完整开仓前检查（trend + live BP/NLV + 持仓检测 + 选链），返回候选合约 |

开仓执行使用现有 `POST /api/position/open`（strategy_key = `"es_short_put"`）。

### 与 SPX Credit 的资金关系

`/ES` options margin 与 SPX Credit positions 共用同一 Schwab options buying power 池（不是独立 SPAN 池）。

**BP 检查逻辑含义**：
- 若 SPX Credit 当前占用 $60k margin，/ES 加入后预计总 $80,529 < $100k（20% × $500k）→ 通过
- 若 SPX Credit 占用 $90k，加入后 $110,529 > $100k → 拒绝

这意味着 /ES 的可用空间受现有 SPX Credit 仓位规模制约。两个策略的开仓时序可能产生隐性竞争。

**SPAN 动态扩张**：/ES 的 $20,529 是静态估算值（VIX ~19 时观测）。实际 SPAN margin 随 VIX 动态上升；持仓期间 VIX 急升时，已开 /ES 仓位的 margin 要求会自动上升，同时 MTM 亏损——此双重压力未被当前 BP 检查建模。

### 当前已知局限性（MVP scope 有意决定）

| 局限 | 说明 | 优先级 |
|------|------|--------|
| -300% stop 无自动触发 | 当前仅为文案规则；止损依赖人工监控和手动执行 | 高 |
| 趋势转负后持仓行为未定义 | 生产中无规则；建议：持有至 stop 或 21 DTE 强制平仓 | 高 |
| SPAN 动态扩张未建模 | BP 检查基于静态 $20,529，VIX spike 时实际 BP 占用更高 | 中 |
| Layer 1（Long SPY）、Layer 3（BSH）均不存在 | 与 SoMuchRanch 完整体系相比，当前 /ES 路径在无 beta 缓冲、无尾部对冲条件下独立运行 | 低（有意 scope）|

---

## 8. SPEC 执行状态（截至 2026-04-12）

### 新增 DONE

| SPEC | 主题 | 状态 |
|------|------|------|
| SPEC-061 | /ES Short Put 最小生产 Cell | DONE |

### 待实现（APPROVED）

なし。当前无待实施 Spec。

SPEC-044（Delta Deviation Display in Open Modal）亦已实施并 Review 通过，Status 已更新为 DONE。

SPEC-048~061 全部 DONE。

---

## 9. 回测基准（无变更）

SPX Credit 策略基准（含全部 SPEC-048~060 修订）：

| 指标 | 数值 |
|------|------|
| 年化收益率 | **8.2%** |
| 最大回撤 | **-13.1%** |
| Sharpe | **1.33** |
| Sortino | 1.05 |
| Calmar | 0.63 |
| 总笔数 | 310 |
| 胜率 | 70.3% |
| 总 PnL (2000–2026) | $349,785 |

/ES Short Put 组件目前没有独立生产基准，参考 `research/strategies/ES_puts/spec.md` §最新研究结果。

---

## 10. 开放问题（截至 2026-04-12）

| 编号 | 状态 | 内容 |
|------|------|------|
| Q012 | open | /ES shared-BP 管理；运行时止损监控；SPEC-061 后续扩展决策 |
| Q011 | open | regime decay DIAGONAL 样本小（回测 n≈8），需真实交易验证 |
| Q010 | open | local_spike DIAGONAL 真实交易 n 计数（SPEC-055b 前置条件，n=0）|
| Q002 | open | Shock active mode Phase B 验证 |
| Q003 | open | L3 Hedge v2 实盘实现 |
| Q004 | open | vix_accel_1d L4 fast-path |
| Q005 | open | 多仓 trim 精细化 |
| Q001 | blocked | SPEC-020 ablation（等待 AMP）|

**Q012 当前决策面**：
1. SPEC-061 MVP 已上线，入场路径完整
2. 运行时止损监控（bot alert / 自动触发）是下一个最高优先级缺口
3. 趋势转负后持仓行为需要在第一笔真实 /ES 仓位建立前明确定义
4. Strategy #3（long /ES calls）作为候选研究项，不在当前 SPEC 队列中
5. 条件相关性（r | VIX > 40）作为未来 /ES 扩展 Spec 的 AC 之一

---

## 11. 研究候选（2026-04-12 新增，暂 hold）

| 假设 | 来源 | 状态 |
|------|------|------|
| H1：Risk reversal 作为 vol skew 收割工具（.15 delta RR + SPY short）| PMTraders Reddit | hold；backtest 验证未启动 |
| H2：Strategy #3（long /ES calls，12 DTE，20 delta，BULLISH regime）| SoMuchRanch 体系 | hold；未进入研究实现 |
| H3：条件相关性（ES Puts vs SPX Credit，r | VIX > 40）| Phase 4 延伸 | 建议作为 Q012 下一步研究点 |

以上均为研究 track 候选，PM 决策是否推进研究实现。详见 `doc/research_notes.md §53`。
