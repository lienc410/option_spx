# Q021 2nd Quant Review

## 总体结论

**CHALLENGE（温和挑战）** 关于 1st Quant 的 `(a) 保留 SPEC-066，不开 DRAFT spec` recommendation。

我的判断不是说 **SPEC-066 必须推翻**，而是：

> **现有证据不足以支持“结案并关闭问题”**。
> 最多支持：**SPEC-066 暂时保留为 operational baseline，同时继续小范围验证 Q021。**

换句话说：

* ✔ 可以继续运行 SPEC-066（默认版本）
* ❌ 但当前研究强度不足以证明 PM 提出的“语义错配”已被否决
* ❌ 也不足以证明 V3 / 半 size / cluster-sensitive 方案一定劣后

---

# 方法学审查

---

## Phase 1 cluster 定义

### 评价：**Useful diagnostic，not decision-grade evidence**

Phase 1 的价值是：

> 快速确认 PM 直觉是否值得继续研究。

它做到了这一点：

* same-peak back-to-back 占增量多数
* 2026-03 双峰案例与 PM 观察一致

所以作为 **signal-layer attribution**，Phase 1 是有价值的。

---

### 但作为决策依据存在三类限制

## 1. Cluster 定义内生于既有规则

使用：

* peak ≥ 28
* off_peak ≥ 10%

这与既有 selector 逻辑接近，但这意味着：

> 用旧规则定义 cluster，再证明旧规则产生 same-cluster exposure

有一定 circularity（循环定义）风险。

---

## 2. “同 cluster 第2笔” ≠ 无效重复暴露

同一 cluster 第二笔可能来自：

* 新的 IV 条件
* 新的 trend 条件
* 第一笔已改善仓位结构
* 市场仍提供 premium edge

所以：

> same-cluster ≠ automatically bad

---

## 3. 按 trade count / trade pnl 归因，不等于 marginal capital value

真实问题应是：

> 第二笔 trade 是否提升组合质量（PnL / DD / convexity）

而不是单纯：

* 多了几笔
* 赚了多少钱

---

### 结论

Phase 1 可以支持：

> “问题真实存在，值得 Phase 2”

但不能单独支持：

> “066 错了” 或 “066 对了”

---

# Phase 2 patch 正确性

## 评价：方向合理，但 prototype evidence 低于正式 engine evidence

1st Quant 用 `inspect.getsource + replace + exec` patch engine，这种方法在 exploratory research 可接受。

但作为 close-out 证据，有三个弱点：

---

## 1. Patch fragile

任何：

* source format 变化
* local variable 名称变化
* side-effect ordering

都可能让结果 subtly drift。

---

## 2. cur_cluster=None fallback 太强

```python
if cur_cluster is None:
    return False
```

这使 V2 非 aftermath 日完全不受限，max concurrent = 6。

这不是纯 PM intent，而是：

> PM intent + permissive engineering shortcut

因此 V2 不应作为严肃 production candidate。

---

## 3. V1 vs V3 逻辑对照不够 clean

如果想证明：

> V1 superior to V3

最好做的是：

* identical engine
* identical selectors
* only one changed variable

当前 patch route 仍存在 hidden-path possibility。

---

### 结论

Phase 2 结果可用于：

> ranking hypothesis

但不应单独用于：

> close the question definitively

---

# 全引擎一致性

## 评价：比 Phase 1 强很多，但仍缺 sensitivity layer

你们已进入正确层级：

> 全引擎 > signal replay

这是正确升级。

但缺：

* cluster threshold sensitivity
* size scaling variant
* recent-era slice
* BP congestion attribution decomposition

所以仍未达到 finality。

---

# 数据归因审查

---

## Claim A：78% 同峰 back-to-back

### 判断：**Directionally believable, numerically over-interpretable**

我相信方向：

> 多数增量来自 same-cluster second entries

但不建议把：

* 78%
* 88%

这种数字当精确 truth。

原因：

* cluster definition sensitive
* attribution unit arbitrary
* no confidence interval

### 我的结论

把它理解成：

> “大部分增量 likely 来自 same-cluster exposure”

即可。

---

## Claim B：2026-03 双峰案例

### 判断：**Valid anecdote, not sufficient sample**

这个案例非常有价值，因为它来自 live intuition。

但它只是：

> one compelling case study

不能据此重构全系统。

### 我的结论

它足以触发 review，不能单独决定 rewrite。

---

## Claim C：V3 -$9,200 vs V1

### 判断：**Most important number, but not conclusive**

26 年总样本下 -$9.2k：

* 年化约 -$350
* 对 options strategy 噪音级别很小

这意味着：

> statistically weak
> economically modest

所以它支持：

> V3 未明显优于 V1

但不支持：

> V1 decisively better than V3

---

## 更关键：你们自己提出的 $27k gap 问题很重要

如果 gained/dropped trade pnl 与 system pnl 对不上：

> 大概率是 BP crowding / interaction effect

这其实说明：

> 研究重点已从单策略切换到 portfolio mechanics

而 1st Quant 没有完整展开这一层归因。

这是主要缺口。

---

## Claim D：Disaster window

### 判断：Too few observations

4–7 trades 的窗口比较，统计意义极弱。

它只能说明：

> 没有发现 V1 在灾难窗明显更差

不能说明：

> V1 disaster superiority established

---

# 漏掉的变体 / 需要补做

---

## 1. Half-size same-cluster 2nd entry（最高优先级）

你们自己提到过，但没做。

这是最自然的 compromise：

> 保留 second peak optionality
> 降低 same-peak stacking

这是我认为当前最值得补做的 variant。

---

## 2. Recent-era slice（2018–2026）

当前 live relevance 高于 2000–2010。

要回答 PM 的问题，应优先看：

* vol regime changed era
* post-COVID era
* modern VIX dynamics

---

## 3. Cluster sensitivity sweep

测试：

* peak 26 / 28 / 30
* off_peak 8 / 10 / 12

若结论不稳，则当前 close-out 不成立。

---

## 4. BP congestion attribution

明确拆解：

* 新 IC_HV 自身 pnl
* 挤掉其他 trade 的机会成本
* margin occupancy cost

否则 system-vs-subset 的差异解释不完整。

---

# 最终建议

## 推荐决策：**暂时保留 SPEC-066，但不要 close Q021**

更准确表述：

> Keep SPEC-066 as current production baseline.
> Open a narrow DRAFT / follow-up test pack for 2–3 focused variants.

---

## 我建议的下一步最小研究包（低成本）

只做三组：

### Variant A（当前）

SPEC-066

### Variant B（半 size）

same-cluster 第2笔允许，但 size=50%

### Variant C（distinct cluster only）

当前 V3-like clean version

然后只比较：

* 2018–2026
* full sample
* BP-adjusted return
* max DD
* live interpretability

---

# 为什么不建议直接结案

因为 PM 的核心 concern 不是纯 pnl，而是：

> 语义一致性
> 风险可解释性
> exposure quality

这些在当前研究中只被部分回答。

---

# 一句话总结

> 1st Quant 已证明：推翻 066 的证据不足。
> 但尚未证明：066 已经是最优答案。

所以我的 stance 是：

## **保留运行，继续验证，不应宣布结案。**
