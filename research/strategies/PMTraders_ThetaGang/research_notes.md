# PMTraders / thetagang Strategy Discussion Research Notes

目的：沉淀外部社区（主要是 Reddit 的 `PMTraders` 与 `thetagang`）中，和本项目可能相关的策略主张、风险案例与可测试假设。

适用范围：
- 这不是生产 Spec
- 这不是可直接执行的实现任务列表
- 这是一份“外部讨论筛选与转译”文档，用来帮助 PM / Planner / Claude 判断哪些观点值得进入正式研究

相关背景：
- 当前项目核心系统为 `SPX Credit`
- 当前并行研究主线为 `ES_Puts`
- 本文重点评估外部社区内容是否能：
  - 支持现有研究结论
  - 提供新的可测试假设
  - 暴露当前系统尚未覆盖的风险

---

## 1. 结论先行

本轮外部讨论分析后，最值得认真对待的内容只有三类：

1. `SoMuchRanch` 的 `/ES short put` 三层体系
2. 2024-08-05 PM 爆仓案例所揭示的低波动期 vega 集中风险
3. `risk reversal as vol skew harvesting` 这个候选独立 alpha 假设

整体判断：

- `SoMuchRanch /ES` 体系不是新主线，而是对现有 `ES_Puts` 研究的高质量外部佐证
- 爆仓案例是风险管理教材，不构成新策略方向
- risk reversal 值得进入候选假设池，但还远不到 Spec
- 绝大多数 `thetagang` 热门内容都属于幸存者偏差、轶事或不可验证噪音

---

## 2. 研究方法与筛选标准

本次不是做情绪观察，而是做“可研究性筛选”。

筛选标准只有 4 个：

1. 是否有明确规则，而不是纯经验口号
2. 是否存在可映射到本项目的结构
3. 是否能转化成可回测或可验证假设
4. 是否能提供现有研究没有覆盖的新信息

因此：
- 赚钱截图不算证据
- 单次爆仓截图不自动等于普遍规律
- 只有当帖子能被转译成“Topic / Findings / Risks / Next Tests”时，才值得进入项目语境

---

## 3. 值得认真对待的主张

### 3.1 SoMuchRanch：`/ES short put` 的完整三层体系

这是本次分析里质量最高的外部内容。

原因：
- 有明确的量化框架，而不是“看盘感觉好就加仓”
- 核心约束是 `VIX` 分档 + `BPu` 上限
- 强调 trend context、杠杆纪律与 tail hedge，不是单纯卖 put 收 theta
- 有多年实盘修正痕迹，尤其是经历大回撤后的体系迭代

它与本项目 `ES_Puts` 研究的结构高度平行：

| 外部体系 | 本项目 ES_Puts |
|---|---|
| Long beta layer | Long SPY Layer 1 |
| `/ES` short puts | Layer 2 theta engine |
| BSH / tail protection | Layer 3 BSH |
| VIX-based leverage caps | Phase 3 leverage table |
| 趋势过滤后才积极开仓 | Phase 1 / 2 trend filter |

最重要的不是“参数完全一致”，而是：
- 外部实盘者独立演化出了与我们相近的体系结构
- 这提升了 `ES_Puts` 研究结论的外部可信度

尤其值得注意的点：
- `-300% premium stop` 在外部实盘语境中也被视为合理边界
- 2022 年大回撤后，更强调 trend filter 权重
- 说明我们研究里“trend filter 改善 MaxDD”的发现，并不是孤立的回测产物

当前结论：
- 作为 `Q012` 的外部验证材料，价值高
- 不产生一个独立新课题

### 3.2 Blowup on 2024-08-05：低波动期 vega 集中的结构性危险

这个案例最重要的地方不是“有人亏了很多钱”，而是它揭示了 PM 账户的结构性陷阱。

案例核心机制：
- 低 VIX 环境下，portfolio margin 对某些结构给出较低维持保证金
- 交易者因此在低波动期积累了极高的 vega 集中
- 当 VIX 在极短时间内从低位爆发时，margin requirement 被快速重估
- 如果组合又具有负 vega、尾部凸性差，就会触发连锁 liquidation

关键洞察：
- 这不是简单的 delta 错误
- 而是“低波环境下 PM 容许过多 vega 集中”的制度性问题

对本项目的映射：
- 支持我们已经实施的保护性 gate 思路
- 特别是 `SPEC-049`、`SPEC-052` 这种在特定 vol 条件下转入 `REDUCE_WAIT` 的方向
- 也提醒未来任何新策略，都不能只盯 delta / theta，而忽略 vega concentration

当前结论：
- 作为风险管理案例，价值高
- 但不需要单独立 Spec
- 更适合作为未来 review 新策略时的“反例检查模板”

### 3.3 Trading Responsibly on PM：多策略独立性不是加分项，而是结构性要求

这类帖子最有价值的部分，不是具体收益数字，而是对 PM 账户结构的经验总结：

- 单一策略集中度过高，是 PM 账户最常见的脆弱点之一
- regime change 来临时，单策略账户没有缓冲层
- 多策略并行不是为了“看起来分散”，而是为了防止单一路径失效时净值断裂

这和本项目已有发现高度呼应：
- `ES_Puts` 与 `SPX Credit` 的历史日收益相关性约 `r = -0.028`
- 这说明 `ES_Puts` 的最大价值，可能不是 standalone edge，而是组合层独立性

但也要立刻看到限制：
- 低相关不等于风险独立
- 两个策略在真实账户里可能共用 buying power
- 在压力期也可能同时承压

因此，这个外部观点最好的落点不是“开新课题”，而是：
- 把“条件相关性验证”并入 `Q012` 的验收逻辑

### 3.4 Risk Reversal as Vol Skew Harvesting

这是外部讨论里最像“新候选 alpha”的主张。

核心结构：
- 卖 `.15 delta` put
- 买 `.15 delta` call
- 同时 short stock 做 delta hedge
- 通常以 `30 DTE` 左右滚动

其逻辑是：
- equity index options 长期存在 put skew
- put IV 往往高于相对称 call IV
- 因此 risk reversal 在某种意义上是在 harvest skew premium
- short stock / delta hedge 用于剥离方向暴露，使策略更接近做 skew 而不是做 market beta

为什么值得保留：
- 逻辑自洽
- 与现有 `SPX Credit` 不同，不是传统 theta harvesting
- 如果成立，可能形成新的独立 return stream

为什么不能高估：
- 帖子没有给出足够可复现的规则细节
- hedge 规模明显带有固定账户痕迹，不是标准化参数
- 执行腿数更多，成本更高，实盘细节更复杂

当前结论：
- 值得进入候选假设池
- 适合未来做 `Phase 0 prototype`
- 当前不应抢占 `Q012`

---

## 4. 明确应视为噪音的内容

### 4.1 thetagang 大量热门帖子

整体上，热门内容中高比例属于：
- meme
- 盈亏截图
- 单次经验贴
- 没有 benchmark 的“我这三年一直赚钱”

这些内容最大的问题不是“错”，而是：
- 不可验证
- 无法转译成可测试规则
- 极易放大幸存者偏差

### 4.2 Wheel、lotto、裸 call 爆仓类帖子

这些帖子可以提供一些情绪层或风险教育层的信息，但通常不提供：
- 可复制的入场规则
- 可验证的风险预算框架
- 长样本统计

因此：
- 不能直接进入研究主线
- 也不值得消耗正式研究资源

### 4.3 “Max Leverage, Minimal Risk” 这类大账户 offset 结构

这类结构往往依赖：
- 极大账户规模
- 券商 PM offset 规则
- ETF 与衍生品组合的特殊资本认定

对本项目当前账户规模和目标而言：
- 不可迁移
- 也不具普适性

因此直接 `drop`。

---

## 5. 可转化为正式研究的候选假设

本次分析里，真正值得写进候选池的只有 4 个假设。

### H1：Risk Reversal 是否能系统性 harvest SPX vol skew

来源：
- 外部帖子 “I wish I had an edge”

候选测试方向：
- 固定 `30 DTE`
- 固定 `.15 delta` short put / long call
- 加入标准化 delta hedge 规则
- 回测 `2000–2026`
- 做 bootstrap 与 regime 分层

如果推进，这将是一个新研究主题，不应混入 `Q012`。

### H2：`-300% premium stop` 是否确实优于 `-200% / -500%`

来源：
- `SoMuchRanch` 实盘经验
- 本项目 `ES_Puts` 当前默认参数

当前项目虽然已默认用 `-300%`，但这并不等于已充分证明其最优性。

更准确的研究问题应是：
- 该 stop 是否在 Sharpe / MaxDD / bootstrap 稳定性之间提供最佳折衷

这可以作为 `Q012` 后续阶段的参数验证项。

### H3：BSH payoff 是否与 skew / VIX spike 强度显著相关

来源：
- 爆仓案例对尾部事件的提醒
- `SoMuchRanch` 的 BSH 体系

研究目标：
- 在极端 VIX 事件中，BSH 的赔付能否稳定覆盖 short premium 主体的尾部损失
- payoff 是否与 skew 水平或 spike 速度相关

这更像 `ES_Puts` 第二阶段或第三阶段课题，不是当前最小 DRAFT Spec 范围。

### H4：多策略独立性是否需要 `r < 0.1` 才足以改善组合尾部

来源：
- PM 账户分散化的外部经验
- 本项目已观测到的 `ES_Puts ↔ SPX Credit` 低相关

真正该验证的是：
- 平时低相关是否能延续到压力期
- `VIX > 40` 条件下的相关性是否仍足够低

这是最适合直接并入 `Q012` 验证框架的候选项。

---

## 6. 四个核心 Topic 的结构化判断

### T1：Risk Reversal as Vol Skew Harvesting

- Topic: SPX risk reversal（卖 `.15 delta` put，买 `.15 delta` call，并配 delta hedge）作为候选独立 alpha
- Findings: 逻辑建立在 equity index put skew 长期存在的事实上；若执行细节成立，策略可能更接近 harvest skew 而非方向性 theta
- Risks / Counterarguments: 外部帖子缺少参数细节、执行成本高、regime stability 未知、hedge 规则不明确
- Confidence: 方向假设高，参数可复现性低
- Next Tests: 固定规则 prototype，回测 `2000–2026`，做 bootstrap 与相关性分析
- Recommendation: `hold`

### T2：低波期 vega 集中是 PM 账户的尾部陷阱

- Topic: Portfolio margin 在低波动期放大 vega 集中的结构性风险
- Findings: 爆仓案例说明，低 VIX 本身并不安全；真正危险的是“低 VIX + 高 vega concentration + 动态 margin 重估”
- Risks / Counterarguments: 单案例不能替代统计结论；结构本身也不等同于本项目常规 spread
- Confidence: 机制高，普遍性中等
- Next Tests: 若未来做新策略，应加入 vega concentration review；无需独立立项
- Recommendation: `drop`

### T3：`/ES` 三层体系的外部实盘反馈

- Topic: SoMuchRanch 的 `/ES short put + long beta + BSH` 体系与本项目 `ES_Puts` 的一致性
- Findings: 外部实盘反馈与本项目 `Phase 1–4` 研究高度平行；特别支持 trend filter、杠杆纪律、`-300% stop` 与 BSH 的设计方向
- Risks / Counterarguments: 单一成功者样本，公开记录存在选择性偏差，账户规模与执行条件未完全透明
- Confidence: 方向高，参数层中等
- Next Tests: 继续按 `Q012` 最小范围推进；未来可单独评估作者提到的 bullish long-call 变体
- Recommendation: `hold -> Q012`

### T4：多策略独立性是 PM 账户的结构性要求

- Topic: 单策略 PM 账户在 regime change 下的脆弱性，与低相关策略组合的必要性
- Findings: 外部经验与我们现有的 `r = -0.028` 发现一致；`ES_Puts` 的生产价值很大程度来自组合层，而非 standalone edge
- Risks / Counterarguments: 历史低相关不保证压力期仍低相关；共用 BP 池会削弱“独立性”的实际效果
- Confidence: 高
- Next Tests: 计算压力期条件相关性，例如 `r | VIX > 40`
- Recommendation: `enter Q012 acceptance criteria`

---

## 7. 与当前项目路线的映射

### 7.1 对 `Q012` 的影响

外部讨论最重要的作用，不是产生一个全新的 `ES_Puts` thesis，而是强化以下判断：

1. `/ES` 三层体系的方向不是孤立想法，外部有成熟实盘者独立走到了类似结构
2. `trend filter + leverage discipline + BSH` 这三件事是强绑定关系
3. `ES_Puts` 是否值得进入生产，不该只看 standalone PnL，而应看组合层独立性
4. 若真的进入 DRAFT Spec，条件相关性验证应被明确写入验收框架

### 7.2 对现有已实施保护逻辑的影响

爆仓案例提供的不是新规则，而是对现有方向的外部支持：

- 低波期不代表安全
- vega 集中在某些结构里比 delta 更危险
- 在特定 vol 条件下减少进攻性，是合理的

因此它更像：
- 现有 gate 设计的外部佐证
- 而不是新建一个研究分支

### 7.3 对未来候选研究池的影响

真正新增的候选主题只有一个：

- `risk reversal as vol skew harvesting`

其余内容：
- 要么并入 `Q012`
- 要么作为风险案例留档
- 要么直接忽略

---

## 8. 当前推荐分类

| 内容 | 分类 | 理由 |
|---|---|---|
| SoMuchRanch `/ES` 三层体系 | `hold -> Q012` | 外部验证强，但不构成独立新课题 |
| Risk reversal / vol skew harvesting | `hold` | 值得进入候选假设池，需原型验证 |
| 2024-08-05 爆仓案例 | `drop` | 风险机制已被现有保护方向部分覆盖 |
| 多策略独立性要求 | `enter Q012 AC` | 最适合并入条件相关性验证 |
| 大账户 offset 结构 | `drop` | 与当前账户规模不匹配 |
| thetagang 常见 wheel / lottos / memes | `drop` | 噪音，不可验证 |

---

## 9. 当前推荐动作

如果 PM / Planner 要把这份外部研究转成项目层动作，最合理的是：

1. 把 `SoMuchRanch` 结论作为 `Q012` 的外部支持材料
2. 把“压力期条件相关性”加入 `Q012` 的验证条件
3. 把 `risk reversal` 放进候选假设池，但不抢占当前主线
4. 不为爆仓案例或 thetagang 噪音单独立项

---

## 10. 最终判断

这轮 Reddit / PMTraders / thetagang 分析并没有推翻当前项目路线。

它提供的真正增量只有两点：

1. `/ES` 三层体系在外部有可信的实盘共鸣，说明 `ES_Puts` 研究方向并不孤立
2. `ES_Puts` 是否值得进入生产，更应该看“压力期下的组合独立性”而不是单纯看平时相关性或单策略收益

因此，这份外部研究最适合扮演的角色是：
- `Q012` 的支持性证据
- 候选假设池的补充材料
- 风险 review 的反例库

而不是一个需要立刻转成 Spec 的新主线。
