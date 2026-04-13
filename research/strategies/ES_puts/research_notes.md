# ES Puts Research Notes

目的：让 MC 环境在不依赖聊天上下文的情况下，能够理解并尽量重现本轮 ES Put 研究。

适用范围：
- 研究对象是原始 `/ES short puts` 体系的 **SPX proxy 版本**
- 当前结论仍属 **research track**
- 本文件记录的是“如何复现实验”和“当前读到什么结论”，不是生产 Spec

相关文件：
- [spec_initial.md](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/spec_initial.md)
- [spec.md](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/spec.md)
- [backtest.py](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/backtest.py)

## 1. 研究目标

本轮研究不是要一次性实现完整 `/ES` 实盘体系，而是先回答 4 个问题：

1. Trend filter 是否真的有 alpha，或者至少能显著改善风险控制？
2. 多 DTE 梯度是否优于单一 45 DTE？
3. VIX 动态杠杆表是否能提升 risk-adjusted return？
4. Black Swan Hedges 和现有 SPX Credit 的低相关性，是否使该体系有组合价值？

研究最终采用“分 Phase 逐层加复杂度”的方式，而不是一次建完整系统。

## 2. 原始体系与本研究的映射

原始实盘体系来自 `spec_initial.md`，核心三层：

1. Long VTI 70%
2. `/ES` naked short puts
3. Black Swan Hedges

本研究为了快速验证方向，做了两个近似：

1. `/ES` 用 `SPX` 近似
2. `Long VTI` 用 `Long SPY` 近似

原因：
- `/ES` 历史期权数据获取难度高
- 先用现有 SPX/VIX 数据验证“方向是否值得继续”

因此，当前结果是：
- **方向验证有效**
- **不能直接当成生产级 /ES 结论**

## 3. 回测代码入口

主脚本：
- [backtest.py](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/backtest.py)

主入口：

```python
if __name__ == "__main__":
    print("ES_Puts — Phase 1 + 2 + 3 + 4 ($500k, 2000–present)\n")
    run_all(verbose=False)
```

默认行为：
- 起始时间：`2000-01-01`
- 账户规模：`$500,000`
- 自动连续运行 Phase 1 到 Phase 4

如果 MC 环境有同样代码与数据，可直接运行：

```bash
python research/strategies/ES_puts/backtest.py
```

如果 MC 环境不能直接跑代码，也可以根据本文件的参数和结果表做“研究复核”。

## 4. 共享参数冻结

这些参数在 [backtest.py](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/backtest.py:1) 顶部冻结：

```python
TARGET_DELTA   = 0.20
STOP_MULT      = 4.0
PROFIT_TARGET  = 0.10
GAMMA_DTE      = 5
SPX_MULTIPLIER = 100
WARMUP_DAYS    = 64
```

解释：
- `TARGET_DELTA = 0.20`
  对应原始体系的约 20-delta short put
- `STOP_MULT = 4.0`
  put 价格涨到 entry premium 的 4 倍时止损
  这等价于 short premium 视角的 `-300%`
- `PROFIT_TARGET = 0.10`
  put 价格降到 entry premium 的 10% 时平仓
  等价于 `+90% profit`
- `GAMMA_DTE = 5`
  剩余 DTE 小于等于 5 时提前平仓，避免 gamma risk

## 5. 数据与信号依赖

数据加载来自：

- `signals.vix_regime.fetch_vix_history`
- `signals.trend.fetch_spx_history`

趋势信号不是主观判断，而是直接复用主工程里的 ATR-normalized trend：

- `_compute_atr14_close`
- `_classify_trend_atr`
- `TREND_THRESHOLD`

这点非常重要，因为本研究的 trend filter 结论，依赖的是：
- **现有工程里的 ATR trend 实现**
- 不是人工主观“看起来像上涨趋势”

因此，MC 若想重现研究，必须把“trend filter”理解为：
- 与主系统一致的 ATR-normalized trend gate
- 不是自由发挥的 discretionary timing

## 6. BP / 保证金建模

本研究后来修正了最关键的 sizing 假设。

早期粗估：
- 15% of notional

最终采用：
- OCC / Schwab Portfolio Margin 近似公式

代码见：
- `_bp_per_contract(...)`

公式：

```text
Method A = 15% × underlying × $100 − OTM_amount + premium_received
Method B = 10% × strike × $100 + premium_received
BP = max(Method A, Method B)
```

关键结论：
- 对 20-delta / 45 DTE 这类短 put，实际 PM 大约是 **notional 的 10.7%**
- 不是之前粗算的 15%

这会直接影响：
- 可开合约数
- avg P&L
- 回撤
- bootstrap 显著性

所以 MC 若要复核研究，必须使用这个修正后的 PM 逻辑，而不是 15% 粗估。

## 7. Phase 设计与复现方式

### Phase 1

目标：
- 只验证 `trend filter` 是否有方向性价值

结构：
- 单一 45 DTE 槽位
- 单一 short put
- `baseline`：无 filter
- `filtered`：只有 trend filter 允许时才开新仓

代码入口：
- `run_phase1("baseline")`
- `run_phase1("filtered")`

参数：

```python
P1_ENTRY_DTE      = 45
P1_INITIAL_EQUITY = 500_000.0
P1_BP_TARGET      = 0.10
```

预期读法：
- 看 `filtered` 是否比 `baseline` 更高 avg P&L
- 看止损率是否下降
- 看 bootstrap CI 是否跨零

### Phase 2

目标：
- 测试 DTE 梯度是否提升稳定性

结构：
- DTE slots: `21 / 28 / 35 / 42 / 49`
- 最多 5 个并发槽位
- 每槽单独开仓

代码入口：
- `run_phase2("baseline")`
- `run_phase2("filtered")`

参数：

```python
P2_DTE_SLOTS      = [21, 28, 35, 42, 49]
P2_INITIAL_EQUITY = 500_000.0
P2_BP_TARGET      = 0.05
```

预期读法：
- Phase 2 不是要证明收益远高于 Phase 1
- 主要看交易笔数、bootstrap 显著性、以及 drawdown 是否更稳定

### Phase 3

目标：
- 在 Phase 2 基础上加入 VIX-based leverage table 和 BSH 成本拖累

代码入口：
- `run_phase3("baseline")`
- `run_phase3("filtered")`

关键新增：
- VIX 分档决定总 BP ceiling
- 每周 / 每月扣除 BSH 成本
- 但 Phase 3 还 **没有** 建模 BSH 赔付

VIX 杠杆表：

```python
P3_LEVERAGE_TABLE = [
    (40, 0.50),
    (30, 0.40),
    (20, 0.35),
    (15, 0.30),
    ( 0, 0.25),
]
```

BSH 成本：

```python
BSH_WEEKLY_COST_PCT  = 0.0004
BSH_MONTHLY_COST_PCT = 0.0008
BSH_VIX_THRESHOLD    = 15.0
```

预期读法：
- `baseline` 若无 trend filter，动态杠杆会在高 VIX 下放大亏损
- 所以 Phase 3 主要回答的是：
  `leverage table` 不能脱离 `trend filter` 单独成立

### Phase 4

目标：
- 在 Phase 3 基础上加入 BSH payoff modeling
- 同时测与现有 SPX Credit 的相关性

代码入口：
- `run_phase4("filtered")`
- `run_phase4_correlation(...)`

关键新增：
- 对 SPY BSH put 做每日 Black-Scholes repricing
- 不再只是 cost-only drag
- 与主工程 SPX Credit 的 daily returns 做相关性比较

预期读法：
- 看 BSH 赔付是否改善最小净值和最终净值
- 看与现有 SPX Credit 是否低相关

## 8. 当前应复现的核心结果

### Phase 1 结果

| 指标 | SPX Credit | baseline | filtered |
|------|------------|----------|----------|
| 年化收益 | 8.2% | -0.1% | 0.2% |
| 最大回撤 | -13.1% | -18.3% | -16.0% |
| Sharpe | 1.33 | -0.00 | 0.08 |
| 胜率 | — | 78.7% | 80.6% |
| avg P&L/trade | — | -$12 | +$29 |
| 止损率 | — | 19.0% | 16.0% |
| Bootstrap CI | — | `[-83,+65]` | `[-60,+112]` |

解读：
- 方向是对的
- 但未达统计显著
- 单槽位过 sparse

### Phase 2 结果

| 维度 | baseline | filtered |
|------|----------|----------|
| 年化收益 | 1.3% | 1.2% |
| 最大回撤 | -38.5% | -23.3% |
| Sharpe | 0.16 | 0.20 |
| 笔数 | 1966 | 1317 |
| avg P&L | $97 | $135 |
| Bootstrap | `[-33,+238]` | `[+30,+276]` |

解读：
- filtered 首次达到显著
- trend filter 更像 risk-control alpha，而不是 pure return alpha

### PM 校正后的结果

修正后：
- 同样 BP target 下，可做约 `1.40x` 更多合约

代表性变化：
- Phase 1 filtered avg P&L：`$143 -> $216`
- Phase 2 filtered avg P&L：`$135 -> $189`
- Phase 2 filtered max DD：`-23.3% -> -30.4%`
- Phase 2 filtered bootstrap：`[+47,+393]`

解读：
- 核心结论不变
- 只是幅度更真实，也更清楚暴露了 naked put 的风险

### Phase 3 结果

| 模式 | 年化 | 最大回撤 | Bootstrap |
|------|------|----------|-----------|
| P2 filtered | 1.6% | -30.4% | `[+47,+393]` |
| P3 baseline | -1.9% | -71.5% | 不显著 |
| P3 filtered | 0.0% | -44.0% | `[+71,+415]` |

解读：
- trend filter 是动态杠杆表的必要配套
- 否则高 VIX 反而成了“加速爆仓”的放大器

### Phase 4 结果

| 指标 | P3 cost-only | P4 BSH payoff |
|------|--------------|---------------|
| 年化收益 | 0.0% | 1.3% |
| Sortino | 0.05 | 0.98 |
| 最小净值/起始 | 57.3% | 64.0% |
| 最终净值 | $501k | $699k |
| avg P&L | $216 | $256 |

补充：
- 文中出现的 `MaxDD -93.1%` 是从 BSH 赔付推升的高水位回落计算出来的，不代表真实本金曾只剩 6.9%
- 更值得看的是：任意历史时点下，P4 净值都高于 P3

相关性：
- 与现有 SPX Credit 的 Pearson 日收益相关系数约为 `-0.028`

解读：
- 如果研究最终成立，组合分散化价值可能比 standalone CAGR 更重要

## 9. MC 复现实验时要避免的误读

1. 不要把这看成 `/ES` 最终实盘结论
   当前是 `SPX proxy` 研究，不是 CME 真实期权历史回测

2. 不要把 trend filter 理解成 discretionary market timing
   这里用的是主工程 ATR-normalized trend

3. 不要把 Phase 3 的坏结果理解为 leverage table 无效
   真正结论是：`leverage table + no trend filter` 无效

4. 不要把 Phase 4 的高峰值回撤误读成真实资本归零
   BSH payoff 的复利峰值会扭曲传统 MaxDD 读数

5. 不要直接从完整体系跳到生产 Spec
   研究结论支持的是“先缩成最小 cell”，不是“全系统立刻实现”

## 10. 当前最稳妥的研究结论

当前状态：`hold`

可认为已经相对稳定的结论：
- Trend filter 大概率有效，主要提升风险控制
- 多 DTE 梯度提高统计稳定性
- 动态杠杆表必须与 trend filter 配套
- BSH payoff 对尾部保护有实际作用
- 与现有 SPX Credit 接近零相关，值得继续追踪

仍未解决的关键不确定点：
- /ES 真实数据验证
- naked put 独立风险引擎
- 完整体系是否值得实现，还是只提取其中一个最强 cell

## 11. 推荐的下一步

如果 MC 端要继续推进，建议下一步只研究这个最小单元：

- `/ES short put`
- 单一 45 DTE
- 20 delta
- trend filter
- `-300%` credit stop
- 不加入动态杠杆表
- 不加入 BSH

原因：
- 最容易隔离 trend filter 的真实贡献
- 最接近一个可后续转成 `DRAFT Spec` 的实现单元
- 能避免完整体系一次性建模的复杂度爆炸

## 12. 生产路径评估更新（2026-04-12）

这一节不是新的策略回测，而是回答一个更接近生产的问题：

- 在约 `$500k` 账户下，ES Puts 到底应该走 `SPX naked put`、`XSP`，还是原始设计里的 `/ES`？
- 如果真的进入生产流程，最小可行单元应如何约束？

### 12.1 先确认的基础事实

当前项目**没有** `XSP` 历史数据，也**没有** bid-ask / spread 建模。

主工程与研究脚本默认使用的是：
- Black-Scholes `mid-price`
- 无成交摩擦
- 无订单簿流动性约束

因此，任何关于 `XSP` 或 `/ES` 的流动性 / spread 讨论，都属于：
- 生产路径评估
- 账户层与执行层可行性分析
- 不是回测引擎已经原生支持的能力

### 12.2 `SPX naked put` 路径基本排除

在 `$500k` 账户下，`SPX` 单张 notional 太大，导致 lot size 约束非常明显。

相对于研究里使用的分数合约近似：
- 真实整数 `SPX` 合约无法像回测那样细粒度缩放
- 在单槽 / 低 BP target 条件下，容易出现“理论上有正期望，实盘却开不出仓”的问题

因此，这条路径可以视为：
- 研究代理工具有效
- 生产实现路径无效

### 12.3 `XSP` 路径能解决 lot size，但 spread 成本偏重

公开市场经验下，`XSP` 的问题不是合约规模，而是成交摩擦：

- 20-delta OTM put 的 bid-ask 百分比通常高于 `SPX`
- 10 张 `XSP` 的总摩擦成本通常高于 1 张 `SPX`
- 小账户最容易被大量小合约的 spread 拖累

基于 Phase 4 filtered 的结果（`avg P&L ~= $256 / trade`）做敏感性分析：

| Round-trip spread cost / trade | 调整后 avg P&L | 95% CI 下界 | 统计显著性 |
|---|---:|---:|---|
| `$0` | `$256` | `$79` | 保持 |
| `$60` | `$196` | `$19` | 勉强保持 |
| `$120` | `$136` | `-$41` | 消失 |
| `$180` | `$76` | `-$101` | 消失 |
| `$240` | `$16` | `-$161` | 消失 |

可读法：
- `XSP` 不是不能做
- 但在较现实的 base case 下，spread 足以让统计显著性消失
- 它更像“权限受限时的降级方案”，而不是首选生产路径

### 12.4 `/ES` 路径的实测账户结论

在 Schwab 账户内，已实测到一笔 `/ES` short put 的关键数据：

| 项目 | 数值 |
|---|---:|
| Buying Power Effect | `$20,529 / 合约` |
| Max Profit | `$3,162.50` |
| Max Loss | `$314,337.50` |
| 实收 net credit | `$3,159.68` |
| Round-trip commission | `$2.82` |
| Bid-ask spread | `$87.50 / 合约`（单边按 `$1.75 x $50` 估算） |
| Resulting Buying Power for Options | `$442,740` |

补充：
- 观察到的合约是 `EWK26`（End-of-Month Weekly）
- 券商页面提示其为 `non-standard option series`
- 这说明流动性结论不能直接泛化到所有标准季度合约

最重要的直接结论是：
- `$500k` 账户下，`/ES` 的整数 lot size **完全可行**
- 不是“勉强 1 张”，而是已经足以支持单槽 `1` 张、较高 VIX 下 `1–2` 张的部署

### 12.5 `/ES` 的 spread 成本相对可接受

对 `/ES` 来说，绝对 spread 金额比 `XSP` 大，但它相对收取 premium 的比例更低。

已知：
- 单张 entry premium 约 `$3,162`
- `-300%` stop 对应亏损约 `$9,487`
- round-trip 成本保守估计约 `$87–175 / 张`

若用研究中的 `avg P&L = $256`，按实际 `/ES` BP 缩放到 `BP = $20,529`：

```text
Expected avg P&L per contract
~= 256 x (20,529 / 25,000)
~= $210
```

扣掉 `$87` 级别的 round-trip 摩擦后，净值仍约：

```text
$210 - $87 = $123 / contract
```

因此：
- `/ES` spread 成本并不可以忽略
- 但与 `XSP` 相比，更可能保住正向期望和统计显著性

### 12.6 先前一个关键假设被推翻：`/ES` 与 SPX Credit 共用 BP 池

之前一度假设：
- `/ES` 使用独立 futures / SPAN 池
- `SPX Credit` 使用独立 SPX options PM 池
- 两者可以几乎互不影响地并行部署

实测账户页面并不支持这个判断。

从 `Resulting Buying Power for Options` 的变化可见：
- 这笔 `/ES` short put 的 `$20,529` margin
- 直接从当前 options buying power 中扣除

这意味着在当前账户视图下：
- `/ES` 与 `SPX Credit` **共用同一个 BP 池**
- 两个策略不是“天然独立资金源”
- 后续若并行运行，必须统一做 BP 分配管理

这是本轮生产路径评估里最重要的修正之一。

### 12.7 共用 BP 条件下的合并约束

先看单独的 `/ES` 占用：

| VIX | ES Puts BPu 上限 | `$500k` 预算 | 可开合约总数 | 每槽（5 槽） |
|---|---:|---:|---:|---:|
| `< 15` | `25%` | `$125k` | `6` | `1` |
| `15–20` | `30%` | `$150k` | `7` | `1` |
| `20–30` | `35%` | `$175k` | `8` | `1–2` |
| `30–40` | `40%` | `$200k` | `9` | `1–2` |
| `> 40` | `50%` | `$250k` | `12` | `2` |

这说明 lot size 不是问题。

但若把 `SPX Credit` 一起算进去，约束会变成：

| VIX | SPX Credit BPu | `/ES` 原始表 | 合计 | 备注 |
|---|---:|---:|---:|---|
| `< 15` | `6%` | `25%` | `31%` | 可接受 |
| `15–20` | `8%` | `30%` | `38%` | 可接受 |
| `20–30` | `10%` | `35%` | `45%` | 偏高 |
| `30–40` | `10%` | `40%` | `50%` | 危险边缘 |
| `> 40` | `8%` | `50%` | `58%` | 不宜接受 |

结论不是“不能并行”。
真正结论是：
- 原始 `/ES` 杠杆表是为独立账户设计的
- 一旦与 `SPX Credit` 共池，它就偏激进了

### 12.8 最大尾部风险：SPAN 会动态扩张

`SPX Credit` 的 spread margin 有一个重要特征：
- 最大风险通常在建仓时就已知
- 市场继续恶化时，亏损会扩大，但 margin 不会像裸卖期货期权那样大幅自动重估

而 `/ES` short put 不同：
- 它的 SPAN margin 会随着 VIX 和风险参数上升而自动扩张

估算读法可近似为：

| VIX 水平 | `/ES` SPAN / 合约 | 5 合约总 BP |
|---|---:|---:|
| `15` | `~$13k` | `~$65k` |
| `20` | `$20,529` | `~$103k` |
| `30` | `~$28k` | `~$140k` |
| `60` | `~$40k` | `~$200k` |

这意味着如果 VIX 从 `20` 飙到 `60`：
- 你不需要新增任何仓位
- 已有 `5` 张 `/ES` put 的 margin 需求就可能从 `~$103k` 自动膨胀到 `~$200k`
- 同一时刻，这些 short puts 的盯市亏损也在同步扩大

因此，尾部风险不是单一一把刀，而是两把刀同时来：
- 亏损扩大
- BP 占用同步扩张

这也是为什么 `/ES` 即便路径更合理，也不能直接照搬原始杠杆表。

### 12.9 当前更合理的生产收缩方式

如果 PM 决定让这条线进入 `DRAFT Spec`，范围应当比最初想象更小。

当前最合理的最小单元是：

- 单槽
- `1` 张 `/ES` put
- `45 DTE`
- `20 delta`
- trend filter 允许时才开新仓
- `-300%` credit stop
- 不含动态杠杆表
- 不含 BSH
- `/ES` 总 BP 占用不超过 `NLV 20%`

这个范围的意义是：
- 先验证 trend filter 在真实成交环境下是否仍有 alpha
- 同时把 SPAN 扩张风险限定在账户能承受的区间
- 先不把“多槽”“杠杆表”“BSH”“组合级 beta+theta”一起绑进来

### 12.10 到这一步后的判断更新

当前对生产路径的排序应更新为：

1. `/ES`
2. `XSP`
3. `SPX naked put`

原因分别是：

- `/ES`
  lot size 可行，佣金低，spread / premium 比可接受，但要处理共用 BP 与 SPAN 扩张
- `XSP`
  lot size 可行，但 spread 更容易侵蚀统计显著性
- `SPX naked put`
  在 `$500k` 账户下整数合约粒度过粗，基本不适合作为生产路径

当前研究判断也应从早前的：
- `hold，等账户权限确认`

更新为：
- `可以进入 DRAFT Spec`
- 但前提是严格限制范围，并把共享 BP 作为硬约束写进 Spec

## 13. 最小复现清单

MC 若要“根据文件重现研究”，最少需要确认以下几点：

1. 使用 [spec_initial.md](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/spec_initial.md:1) 理解原始实盘体系
2. 使用 [spec.md](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/spec.md:1) 理解 SPX proxy 研究范围
3. 使用 [backtest.py](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/backtest.py:1) 作为唯一代码真源
4. 确认参数冻结：
   `TARGET_DELTA=0.20`
   `STOP_MULT=4.0`
   `PROFIT_TARGET=0.10`
   `P1_ENTRY_DTE=45`
   `P2_DTE_SLOTS=[21,28,35,42,49]`
5. 确认使用的是 ATR-normalized trend，而非主观趋势
6. 确认保证金已用 OCC 公式校正，而非 15% 粗估
7. 复现时优先比较：
   `Phase 1 baseline vs filtered`
   `Phase 2 baseline vs filtered`
   `Phase 3 baseline vs filtered`
   `Phase 4 P3 cost-only vs P4 BSH payoff`

做到这 7 点，MC 基本就能重建本轮研究的主要逻辑和结论。
