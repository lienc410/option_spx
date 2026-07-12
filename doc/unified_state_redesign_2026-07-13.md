# 从零重设计：统一状态机 × 三引擎 × 资源分配器

**Date**: 2026-07-13
**Owner**: Quant Researcher（Tier 3 设计综合）
**触发**: PM 2026-07-13——"这套逻辑闭环分布在多个课题不同时段，从零重新设计你会怎么做？"
**性质**: 设计备忘录（非 spec）。核心立场：**重新设计 ≠ 重写**——所有已验证参数、路由结果、风险 veto 原样保留（重写会丢掉 26 年验证基础）；重设计的价值在于把散落的布尔量收拢成**一个状态面 + 一张引擎-状态矩阵 + 一个资源分配器**，并让它可视化。

---

## 1. 研究闭环沉淀出的设计公理（每条都有实证出处）

| # | 公理 | 出处 |
|---|---|---|
| A1 | 账本有三个物理不同的收益引擎：**Premium（theta）/ Trend（delta+theta 混合）/ Convexity（长 gamma）**——方向决定什么时候输，premium 决定长期赚多少 | Q095 P1 |
| A2 | 市场在**趋势段与区间段**之间交替（区间 7 个/年、中位 25TD、因果 0-1 天可确认）；趋势引擎 79% 在区间顶部入场且整体赚钱；区间底部入场约 2× 好但 selector 流内结构性稀少 | P2b/P2c/K3 |
| A3 | Dip 触发（ddATH ≤−4%）89% 来自区间内/破位后；**无区间铺垫的突发型是全引擎的公敌**（4/4 前有已完结压缩期，短 vol 在该型亏 4×） | P6/094.4 |
| A4 | 账户是 **cash-bound 不是 BP-bound**；BCD/Q042 吃现金、BPS/IC 吃 BP；一张 BCD = $38-41k 整数下限；一次 Q042 = $78.6k | Q081/Q091/Q096 |
| A5 | 已证死路（设计禁区）：震荡停手 gate、下跌方向 gate、等回调入场、下沿入场硬规则、无条件近支撑 strike、mark-multiple 止损、滞后趋势止损救短权、流动性信号增强 | K3/Q082P9/E2/P2c/Q085P1a/原则2/原则1/P5 |

## 2. Layer 0 — 生存 veto（宪法层，一字不动）

`VIX ≥ 35 全停` / `second-leg（dd60≤−8% & VIX≥25）禁新短 vol` / `R1-R6 治理 cap（80/50/40/60/50）` / `现金 floor $30k` / `2008 型锁死保留`。任何下层逻辑不得越过。

## 3. Layer 1 — 统一市场状态面（重设计的核心新物）

现状的问题：vol regime、trend 信号、aftermath 布尔、episode 分类、dip 触发、sudden 分型散落在 5 个模块里各自被 ad hoc 消费。重设计收拢为**两轴 + 事件灯**，一个模块日更、落盘、可查历史：

```
Vol 轴(VIX):        CALM(<15) │ NORMAL(15-22) │ HIGH(22-35) │ EXTREME(≥35)
Structure 轴(价格):  TREND-UP │ TREND-DOWN │ RANGE(episode 检测器,因果分段)
事件灯(overlay):     DIP(ddATH≤−4%, 分 episode/sudden 型) · AFTERMATH(峰值≥28 回落10%)
                    · BACKWARDATION · SECOND-LEG · 弹药状态(cash vs $78.6k reserve)
```

全部因果可算、全部已有生产实现（RANGE=094.4 分类器；DIP 分型=094.4；其余=selector 现役信号）。**初期为 shadow 语义**：状态面只描述不路由，selector 原样——之后按 SPEC-118 式 bit-identical 迁移逐步让路由读状态面。

## 4. Layer 2 — 引擎-状态矩阵（交易条件逻辑 × 标的 × sizing × 退出，全表）

| 状态\引擎 | **Premium（吃 BP）** | **Trend（吃 BP 或 cash）** | **Convexity Q042（吃 cash）** |
|---|---|---|---|
| CALM × TREND-UP | IC（权利金薄，弱） | **BCD carve**（IV_LOW，SPEC-113）1 张标准 / BPS Δ0.30 | armed 待命 |
| NORMAL × TREND-UP | BPS Δ0.30/0.15 | BPS 或 BCD（按 IVP 路由） | armed |
| NORMAL × **RANGE** | **IC（NEUTRAL 路由，区间的静态收割）** | 照常入场（K3：震荡入场显著赚钱，不设 gate） | **戒备态：89% 触发源于此 → 弹药 reserve 持续检查（提示不拦）** |
| HIGH × any | HV 半仓变体 + backwardation/ivp63 gates | BCS_HV（bearish 时） | armed（触发无 VIX 条件） |
| HIGH × AFTERMATH | **V3-A broken-wing IC bypass**（特批通道） | — | armed |
| EXTREME | 全停 | 全停 | armed（sudden 型触发→空仓 advisory 已覆盖） |
| **DIP 事件 · episode 型** | — | — | **FIRE：ATM/+2.5% call spread D30（首选）；现金不足→BPS fallback Δ0.30/0.15（收益差 3.7-7.4× 提醒）** |
| **DIP 事件 · sudden 型** | — | — | FIRE + **advisory 空仓**（该型短 vol 亏 4×，call spread 自身 3/4 亏） |

**Sizing（全部现值）**：Premium/Trend = bp_target 按 regime（NORMAL 4.5%/HIGH 半仓 0.5×/booster shadow 90%），BCD 整数 1 张标准（Q096）；Convexity = 12.5% NLV staged（→17.5% 按 SPEC-104 阶梯）。
**退出（全部现值）**：Premium/Trend = pnl_ratio 止损（−0.50/−0.35，绝不 mark-multiple）+ profit target + 21DTE roll + **禁滞后趋势止损**（原则 1）；BCD campaign = collapse buyback ≤15% + **短腿 ≤7DTE 强制决策点**（P3 新纪律）+ trend-flip 退出；Q042 = hold-to-expiry D30（Tier 4 TP/stop 待 2027-05 review）。

## 5. Layer 3 — 资源分配器（cash 与 BP 为一等公民）

1. **弹药规则**：RANGE 状态活跃期间，liquid − 在场 debit ≥ $78.6k 为绿；跌破 → FYI（平静日补弹药，非崩盘日卖资产）。第二笔并发 BCD = 花掉一次抄底子弹（$118k ✓ / $158k ✗ 算术）——开仓表单提示。
2. **表达替换**（已部署 094.4）：同一 bullish 观点按资源选结构——cash 足 → call spread（凸性最优）；cash 短 + episode 型 → BPS（吃 BP）；sudden 型 → 空仓。
3. **计量纪律**：所有比较强制 $/BP-day + $/cash-day 双指标；BCD 引擎数字带 `(engine ~0.6ct)` 透镜。

## 6. 与现状的差异清单（诚实账）

**不变（绝大部分）**：全部路由结果、参数、veto、退出规则——矩阵只是把现状**写成一张表**。
**新增（仅三处，证据已备，全部提示不拦）**：①RANGE 期间弹药就绪从"触发时检查"前移为"状态期间持续可见"；②sudden/episode 分型常显（现只在触发时算）；③RANGE 内带内位置软指引显示（P2c，n=11 不规则化）。
**组织变化**：状态面单模块化 + 日志化（状态历史本身成为未来研究的数据资产）。

## 7. 可视化设计——"状态地图"（让 PM 一眼看到现在在哪里）

**设计目标**：不是又一个数据仪表盘，是**这张矩阵的活版**——当前状态点亮、引擎眼下开着哪几个、资源余量对着门槛。三栏：

```
┌─ ①市场状态 ────────────┬─ ②引擎面板 ──────────────┬─ ③资源面板 ─────────┐
│ Vol 轴滑块: ●NORMAL     │ Premium: ● ON → IC       │ Cash $152k          │
│ Structure: ●RANGE 第46天│   (NEUTRAL×RANGE 路由)    │  ├─ 在场 debit $0   │
│ 事件灯:                 │ Trend:   ● ON → BPS/BCD  │  └─ Q042 reserve    │
│  DIP ○ (ddATH −0.5%,   │   (79% 顶部入场为常态)     │     $78.6k ✓绿      │
│   距 −4% 还差 3.5pp)    │ Convexity: ◐ ARMED       │ BP 15.8% / cap 80%  │
│  AFTERMATH ○ SECOND-LEG ○│  (RANGE 戒备态,若触发:    │ 短vol 15.8% / 50%   │
│  BACKWARDATION ○        │   episode 型→call spread) │                     │
└─────────────────────────┴──────────────────────────┴─────────────────────┘
     底部: 状态时间轴(过去 90 天的状态色带) + 今日 selector 推荐 + 触发预演
```

关键交互：**触发预演**——点 DIP 灯可看"若明天触发会发生什么"（分型判定→弹药分支→建议结构与行权价）；**状态时间轴**——90 天状态色带让 6 月那种"5-05 起就在区间里"一目了然。数据全部来自现有 API（/api/q042/state、sleeve-governance/state、recommendation）+ 状态面新 API（一个端点）。交互 mockup 已出（见 Artifact），真实实现须按 DESIGN.md（theme.css tokens）。

## 8. 实施路径建议（供 PM 排期）

| 步 | 内容 | 量级 |
|---|---|---|
| S1 | 状态面模块 + API + 日志（shadow 语义，零路由变更） | 小 spec |
| S2 | 状态地图页（§7） | 中 spec（前端） |
| S3 | 三个提示增量（§6 新增项）挂进状态面 | 并入 S1/S2 |
| S4（远期） | selector 路由逐步读状态面（bit-identical 迁移，SPEC-118 式） | 分批小 spec |

S1+S2 合计工程量与一次 SPEC-094.x 相当；S4 不设时限——迁移的收益是消灭未来的"布尔散落"类缺陷（本轮 094.2-094.4 修的每一个坑都源于此）。

---

## 9. 与现有 surface 的关系映射与整合建议（2026-07-13，PM 追问）

### 9.1 核心诊断

现有 Portfolio 页是**按 spec 出生顺序长出来的**——每个 spec 一张卡，组织维度是 provenance（哪个文件批的）而非 function（服务决策的哪一层）。DESIGN.md 已有裁决"Spec IDs are provenance, not names"，本节将其推广到信息架构：**卡片应按决策系统的层组织**。四层骨架就是重组坐标系。

### 9.2 映射表

| 现有 surface | 骨架归属 | 诊断 |
|---|---|---|
| **Sleeve Stress Governance 卡** | Layer 0 veto + Layer 1 stress/second-leg/booster 灯 + Layer 3 BP caps | **三层混装一张卡**——veto 哲学、市场状态、资源上限是三种不同刷新率/不同读法的信息 |
| **SPX 卡** | Layer 2 Trend+Premium 引擎（SPX 池）今日视图 | 引擎视角正确，缺状态面上下文（不显示 RANGE/episode/分型） |
| **Stress Put Ladder（/ES HV Ladder）** | Layer 2 Premium 引擎的 /ES 变体（独立 SPAN 池），SPEC-104 降级 0% 配置 | 保持 demoted 现状；在骨架中是"premium 引擎的第二标的"，非独立层 |
| **Q078 Entry Ladder（shadow）** | Layer 2 SPX 引擎的**执行 cadence 子行** | 独立成卡是 provenance 组织法产物；Stage 2 前一行状态足够 |
| **sleeves（Q041 T2/T3）** | **骨架外独立 alpha 宇宙**（单名 earnings），仅在 Layer 3 现金处交汇（CSP 已在 SPEC-111 universe） | 不并入 SPX 状态机；资源面板显示其 cash 占用即可 |
| **DD Overlay 卡** | Layer 2 Convexity 引擎 | 已有 ddATH/armed，缺 RANGE 戒备态与分型常显（骨架 §6 增量②） |
| **Resource Waterline 卡** | Layer 3 的**现金半边** | BP 半边在 governance 卡里——Layer 3 被劈在两张卡 |
| **SPX 策略矩阵页** | Layer 2 的**静态规则书**（selector 两引擎 cell 路由 + 回测统计） | 只覆盖两引擎；无 Q042 行；与 live 状态无联动 |
| **4 泳道** | **资本 sleeve 维度**（SPX / /ES / Q041 / DD Overlay） | 与引擎维度**正交**：泳道答"钱在哪个账本"，引擎答"什么逻辑在交易"——SPX 泳道内装着两个引擎。两个视图都保留 |

### 9.3 整合建议（三合、三不动）

**合 ①——Layer 3 归一**：Resource Waterline 扩成完整"资源分配器"卡：cash（现有）+ BP caps（从 governance 卡迁入）+ **弹药 reserve 线（$78.6k）与并发 BCD 余量**（新）。Governance 卡瘦身为纯 Layer 0/1：veto 状态灯 + stress/second-leg/booster + active cap regime 一行。收益：资源问题一张卡答完（"我还能开什么"），治理问题一张卡答完（"系统现在禁什么"）。

**合 ②——矩阵活化**：策略矩阵页与本备忘录 §4 引擎-状态矩阵合并：(a) 加 **you-are-here 高亮**（当前 cell 由状态面驱动）；(b) 补 **DIP 事件行**（Q042 触发逻辑与弹药分支进矩阵）；(c) 行组织从 regime×trend 单维升级为"状态 × 引擎"。矩阵从回测统计表升级为**活的规则书**——State Map hero 点进来就是它。

**合 ③——State Map 为顶层**：State Map 不替换任何卡，是"现在在哪"的新顶层：①栏借调 governance 卡的事件灯，②栏借调 SPX/DD Overlay 卡的今日状态 + Q078 ladder 一行，③栏 = 合①后的资源卡摘要。现有卡降为 drill-down（点引擎进卡）。Portfolio home 顶部加 State Map hero 条（一行当前状态），替代现在"进页面自己扫六张卡拼状态"的读法。

**不动 ①**：Q041 sleeves 独立泳道——独立 alpha 宇宙，逻辑不进 SPX 状态机。**不动 ②**：/ES HV Ladder 维持 SPEC-104 demoted 展示。**不动 ③**：泳道（资本视角）与引擎（决策视角）两个正交维度都保留——不强行统一。

### 9.4 实施排序修订

S2（状态地图页）拆为 S2a（State Map 新页 + hero 条）与 S2b（合①资源卡重组 + 合②矩阵活化）——S2a 零迁移纯新增先行；S2b 动现有卡，走一次 design review 再实施。

---

## 10. PM 设计评审五条约束（2026-07-13，全部吸收，mockup v2 已改）

1. **Open Position 与 Portfolio Snapshot 为不动锚点**——两个 section 原样保留，任何整合不得触碰（升格为"不动 ④⑤"）。
2. **Layer 3 必须显式呈现 Cash Pool 与 BP Pool 双池**（原图 A 只画了规则漏了池本体）——v2 已改：CASH POOL（liquid + 弹药线 + 并发 BCD 余量）与 BP POOL（SPX PM/short-vol 双 cap 条 + /ES SPAN 行）为 Layer 3 的主体，规则是池上的操作。
3. **图 A 与图 B 合并裁决（PM 直觉采纳）**：State Map 页 = **图 A 的活版**——四层架构图本身点亮当前状态（Layer 0 veto 灯、Layer 1 双轴+事件灯、Layer 2 引擎徽章、Layer 3 双池量表），不再有独立的"三栏页面"与"架构图"两个东西。图 B 仅存的独有内容（现有卡怎么迁）降级为**一次性施工图**，不是页面。原示意图 artifact 保留作施工参考。
4. **可读性**：PM 要读的内容一律主文字色（--text），次级色仅限 section 标签与真正的 chrome；meta 行字号上调。呼应既有纪律 `feedback_text_muted_banned` 的延伸：--text-2 也不得用于关键阅读内容。
5. **迁移安全**：现 Portfolio 页并行保留于 `/portfolio_old`，新组织稳定使用后再议退役——S2b 施工前提。
