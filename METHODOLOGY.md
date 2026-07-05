# METHODOLOGY.md — 研究与变更方法学规范

**版本**: v1.0-draft（2026-07-05，Q087 Track E；待 PM 终审 ratify）
**定位**: 流程与判定规则的单一真值。**本文档不含任何策略参数数值**——参数真值永远在代码里（grep 取真），这里只管"怎么做研究、怎么下结论、怎么变更系统"。每条规则标注出处（Q 编号/日期），保证可追溯、可挑战。

---

## 1. 研究生命周期（强制顺序）

```
Framing memo（预注册）→ Phase 执行 → G-review packet（task/）
→ 外审（常驻 reviewer subagent）→ Verdict → [采纳类] SPEC → dev handoff
→ 部署 + 首日验证回报 → 封账（总账一次性 seal）
```

- **预注册先于看数据**：信号清单、端点、门槛、切点候选全部在 framing 锁定；事后追加必须全 battery 统一施加并在修订日志留痕（Q085）
- **稳健性前置**：被撤回 ≥1 次的提案，悲观 bracket 等稳健性检查必须在 ratify 前完成，不得推到 commit-gate（Q083 P12）
- **G-review packet 与回复都放 `task/`**；kill 类与 adopt 类 verdict 一律外审（false negative 永不自然暴露，Q075/Q084）

## 2. 统计协议（默认栈，偏离需书面理由）

| 规则 | 内容 | 出处 |
|---|---|---|
| Studentized 推断 | 波动选择性信号的置换检验必须 studentize（raw mean-diff 对高波动日信号系统性偏松） | Q085 外审 |
| FDR 单批记账 | BH q=0.10 按 endpoint 批内做；**禁止跨批 pooling**（相关检验 pooling 是补贴不是惩罚）；总账收口时一次性 seal | Q085 外审 |
| 切点纪律 | 不扫描边界；改革候选 = 离散的、有先验理由的预注册清单；变量先验不豁免切点自由度 | Q083 G1 |
| 半样本选择/确认 | 规则选择（出场网格、停机参数）在前半样本选、后半样本确认 | Q085 P2c |
| 复制打折 | 跨市场复制按相关性打折；共享事件日的"复制"近循环（NDX/RUT vs SPX 相关 0.89+）；准独立市场（GDAXI 级）才算增量 | Q085 P1d/P1b |
| 事实先于 PnL | 条件分布事实不显著的信号不得进反事实模拟；不能用度量 X 派生的子样本验证 X-driven 规则 | Q083 G1 |
| 双判定标准 | 信号有无信息量 = Alpha 标准（vs 零显著）；槽位/执行改动 = Execution 标准（vs 现状显著优，必须对现状实际行为 head-to-head） | Q083 G2, Q085 P2d |
| 噪音门槛 | 策略比较级 ROE Δ < 0.5pp 视为噪音（bootstrap σ 校准） | Q080 P3 |
| Sharpe 口径 | exit-day unsmoothed 记账（daily MTM 线性平滑虚增 ~+0.7） | Q080 P1 |
| 边界软化双门槛 | freq AND ROE 同时达标 | Q079 |

## 3. 定价与数据协议

- **合成 credit 回测必须过 CALIB + 成本才有 ratify 资格**：BS-flat@VIX 高估卖权利金 2-4vp（真实链实测：put d.30=VIX−2/d.15=VIX+1；call 侧更贫）；统一定价库三模式 FLAT/CALIB/PESS，禁止默认模式，PESS bracket 参数禁止库内写死（SPEC-119）
- **短持有策略交易成本是一阶项**，必须入模（Q085 P3：成本翻转过一次 verdict）
- **今日尺度绝对值**：cash-bound 账户必须报 PM 当前 spot/现金下的绝对 $，历史摊薄比例不作为决策数字（Q083 P15，双次被抓）
- **代理有效性随结论野心重审**：同一代理可对窄 fact-claim 有效、对量化 claim 失效（Q081）
- **数据采集一律脚本化**，禁止手抄（含 handoff 测试向量——SPEC-116 手抄 12 个错 7 个）；不可得数据如实记录（HTTP 状态/付费墙）并注明采购路径
- **strict-JSON**：任何进浏览器/跨语言的 JSON 禁 NaN/Inf，写入前全字段 finite 断言

## 4. Verdict 规范

- **分时代呈现强制**（2026-07-04 PM ratify）：kill 类结论必须给近 24 个月/滚动窗口切片（n 可见）；"历史上曾失效"≠"现在失效"；全样本聚合单独出现视为不完整
- **Status-quo bias 自审**（三次实例 Q081/Q082/Q085）：写"无需改动"前检查——挑战者门槛是否严于现任自身能通过的？可计算的反事实是否算过才降级？不确定性是否被默认解读为"利于现状"？
- **未量化 caveat 不作支撑**："caveat 方向有利于本 verdict"的论证必须量化成 bracket，符号被算反过（Q082 CV1）
- **叙事纪律**（Q087 A1/A3 双实例）：凡"从未被发现/验证"类主张先 grep 代码注释与 SPEC/Q 档案；凡标"生产/实际"的数字必须引用 ledger 行数来源
- **Thesis recentering**：phase 数据推翻原 framing 时，下一 phase 开头显式 reframe（Q081）
- **Reviewer 按字面交付**：指定"加一栏/分布/分层"是 raw-data 要求，不得用摘要替代（Q081）
- **Kill 档案带防翻案标签**：结构性失配（调参不能复活）与参数性失败分开记录（Q084）
- **产物完备**：verdict 引用的每个数字必须有可执行 runner（results-only 存根三次前科：P2e/P3b/A3）

## 5. 采纳与姿态规则

- **自适应姿态**（PM 2026-07-04 ratify）：不存在全天候门；时代条件性采纳四件套缺一不可——(a) 诚实的"现在有效"测量（start-year 全梯呈现，防切窗）(b) 预承诺降级/恢复规则（参数采纳前锁定）(c) 定期复盘 (d) 模型-现实有分歧时 paper-first（测量计门槛，非时长计）
- **边界**：自适应哲学只管 Layer-2 收入 edge；Layer-1 求生锁（2008 型/EXTREME）静态，PM 2026-07-03 单独确认
- **已采纳 sleeve 的证据等级**：resume/加仓论证只认 live/paper 流水，历史回测失去投票权（Q085 外审 C5）
- **Guard 分级**：行为中性重构 → bit-identical 断言；行为变更 → paper-first/外审；参数变更 → Track A 式审计 + PM ratify
- **策略比较指标包**：marginal $/BP-day、worst trade、disaster window、CVaR 全套（Q073）

## 6. 角色与接口

| 角色 | 权责 | 接口 |
|---|---|---|
| PM | 优先级、风险姿态、行为变更 ratify、资金决策 | checkpoint / AskUserQuestion；知情确认书面留痕于 SPEC |
| Quant（主会话） | 研究、审计、全部 SPEC 起草；**不写生产代码** | SPEC + handoff（task/），含 AC 与代码 stub |
| Dev | 生产实施、部署、首日验证 | 回报 commit hash + AC 结果；外部 API 字段读取的 AC 必须含非 mock 集成冒烟（SPEC key-mismatch 前科） |
| 外审 reviewer（常驻 subagent） | 每个 kill/adopt verdict、方法学变更、分诊抽查 | 攻击点显式列出；回复入 task/；数字必须代码复核 |
| Planner | program board、归档、跨会话锚点 | 阶段摘要 |

## 7. 文档与数据纪律

- **禁参数镜像文档**（STRATEGY_STATE 前科：4 处 drift 首审即现）；唯一例外 = 代码自动 dump + CI diff enforcement；审计工作表允许（dated snapshot + file:line 引用 + "真值在代码"声明）
- 回测磁盘缓存失效必须绑定算法 git-hash（SPEC-118），改算法后主动提醒刷新
- Memory → 本文档的晋升路径：重复出现 ≥2 次的教训编入本文档并加出处；本文档修订走 PM ratify

---
*修订日志: v1.0-draft 2026-07-05 初稿（Q083-Q087 全部教训编纂）*
