## 1. 一句话总判断

**PASS with tiering — Q041 Phase 2 足以支持下一阶段 execution-prep / paper-trading 路由，但不同候选必须分层：SPX CSP DTE30 正式进入；GOOGL/AMZN CSP 带尾部 caveat 同步进入；COST/JPM earnings IC 只能 observe-only / cautious paper trade，不应晋升正式候选。** 

---

## 2. SPX CSP DTE30

**结论：支持进入 next-stage execution prep / paper trading。**

这是当前 Q041 最干净的候选。理由：

* Phase 2 后仍是 clean leader。
* `2022` bear-stress 没有推翻它；2022 年仅 1 个亏损 cycle，全年仍为正收益。
* 全期表现足够强：`N=30`，WR `97%`，CumPnL `+$763`，Sharpe `2.18`，MaxDD `−2.84%`。
* 风控结论是对的：不要加 brittle static filters，核心是 **position sizing discipline**。`2022-08-19` 的 “IV compression trap” 是 sizing / risk-budget 问题，不是简单 filter 能解决的问题。

**2nd Quant caveat：**
SPX CSP DTE30 仍不是 production-ready。它只适合进入 paper-trading / execution-prep。最大 caveat 是 `2022 Jan–Apr` 缺失，尤其 2022 年 4 月那段下跌没有覆盖。这个 caveat 不足以阻止 paper trading，但必须写进 downstream packet。

**建议：**
进入 paper trading；建议维持 planner 给出的单 cycle 名义敞口上限，不要因为历史 MaxDD 低就提前放大 size。

---

## 3. GOOGL / AMZN CSP

**结论：同意 “borderline formal candidates” 标签，不应降为 observe-only，也不应提升到 SPX 同等级。**

这两个名字的 signal 足够强，不能简单放入观察桶：

* GOOGL Sharpe `2.28`
* AMZN Sharpe `1.50`
* 四年窗口已覆盖 2022 bear regime
* 明显强于 earnings IC 分支的证据质量。

但它们也不应和 SPX CSP DTE30 放在同一 confidence tier：

* 缺 `2019–2021 / COVID`
* single-name gap / idiosyncratic tail 没有被真正验证
* 个股 CSP 的尾部不是指数 CSP 的简单缩放版，尤其在 mega-cap 出现叙事断裂、监管、AI capex、earnings shock 时，loss path 会更跳跃。

**我的 routing：**
允许进入 paper-trading packet，但必须明确标注：

> “borderline formal / tail-caveated candidate”

并且 sizing 应低于 SPX CSP，不应默认同等 capital budget。

---

## 4. COST / JPM earnings IC

**结论：observe-only routing 正确；不支持晋升正式候选。**

这条分支有 signal，但证据太薄：

* COST 只有 `N=15`
* JPM 只有 `N=9`
* 没有 COVID-era earnings sample
* 财报事件天然存在 gap / realized move tail，单一事件可以支配年度表现。

我同意 planner 对两个过滤项的处理：

### VIX ≥ 15

**可以作为 real governance / entry candidate。**

P2-2 显示 VIX<15 是 earnings IC 的明确亏损区，VIX≥15 过滤后 aggregate cum_pnl `+9%`、WR `+4pp`。这是一个有经济解释的过滤：低 VIX 下 premium 太薄，IC 的双边尾部不值得卖。

### JPM IMR ≥ 33%

**只能作为 optional paper-trading refinement。**

它对 JPM 看起来有增益，但样本太小，且 COST 上反而伤害表现。Planner 把它限定为 JPM paper-trading 阶段可选，而不是统一规则，是正确的。

**我的 routing：**
COST/JPM earnings IC 不进入 formal candidate lane。可以做 observe-only / cautious paper trading，目标是积累真实事件样本，而不是验证已经足够强的策略。

---

## 5. Overlap validation interaction

**结论：同意当前 separation。**

Overlap validation 应继续，但它不应该阻塞当前 candidate routing。

原因：

* 当前 review 的问题是 next-stage candidate governance，不是重新判断 Phase 1/2 broad screening。
* Planner 已明确：overlap validation 是 stitched dataset admission / reconciliation work，不是重开 historical ranking 的理由。
* Phase 2 已经把最明显受 overlap 影响的 DTE45 分支降级或淘汰：CC DTE45 淘汰，CSP DTE45 降为观察。

**但要保留一个 governance caveat：**
对于 stitched dataset 的任何正式生产声明，overlap validation 必须完成；但对于 paper-trading packet / execution-prep，当前证据已经够用。

---

## 6. Final routing recommendation：**B**

**选择 B — packet for `SPX + GOOGL/AMZN` together, with tiered caveats.**

具体 routing：

### Tier 1 — Formal paper-trading / execution-prep

* `SPX CSP Δ0.20 DTE30`

理由：证据最干净，2022 压测通过，下一步应该从研究转向 execution discipline、sizing、纸面交易监控。

### Tier 2 — Borderline formal / tail-caveated paper trading

* `GOOGL CSP Δ0.20 DTE21`
* `AMZN CSP Δ0.25 DTE21`

理由：signal 足够强，值得进入同一 packet；但必须明确低于 SPX CSP 的 confidence tier。

### Tier 3 — Observe-only / cautious paper trading

* `COST earnings IC`
* `JPM earnings IC`

理由：event alpha 可能存在，但 N 太小、COVID 缺失、事件尾部强，不应晋升 formal。VIX≥15 可作为观察规则，JPM IMR≥33% 只能作为 paper-trading refinement。

**Final verdict：PASS — choose routing B.**
