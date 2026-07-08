# BP 使用率研究线重审计 — 2026-07-07

**Owner**: Quant Researcher(PM 2026-07-07 委托:"我怀疑之前的研究有明显的不合理")
**Scope**: "BP使用率太低"问题的全部过往研究与其产品化后果
**Thread**: Q021-P4 → IDLE_BP_OVERLAY_NOTE (4/26) → Q036 (4/26) → Q044/Q045→SPEC-084 (5/6-08, **已部署**) → Q046 (5/7) → Q041 attribution +SPEC-085 F3 (5/7) → Q073 (5/17) → Q081→SPEC-111 (6/1, **已部署**) → Q082 Option C (6/2) → 今日 T2 被 cash cap 阻断
**审计标准**: METHODOLOGY v1.1 + Q081 cash-bound 事实 + today-scale absolute 原则

---

## 0. 一句话结论

**这条线的"诊断"大多是对的,"框架"在 2026-06-01 已被 Q081 数据推翻但从未正式退役,而它留下的生产参数(SPEC-084)与新治理(SPEC-111)从未做过合成审计——今天(7/7)账户的实际约束已经与所有历史回测优化的约束不是同一个东西。**

最尖锐的矛盾:研究线正确地把"扩策略覆盖(Q041)"选为利用率主轴,然后把 T2 设计成 **cash-secured**——用账户里最稀缺的资源(现金,6/1 时 3.0% NLV)去填账户里最富余的资源(BP,同日 headroom 56%)的缺口。今天推送里 GOOGL/AMZN CSP 双双被 60% cash cap 阻断、同时 BP 大量闲置,就是这个矛盾的实况转播。

---

## 1. 对的(经审计维持)

| # | 结论 | 出处 | 审计意见 |
|---|---|---|---|
| 1 | rule-quality vs capital-allocation 两层区分 | IDLE_BP note §3 | 仍然成立,已入宪级习惯 |
| 2 | Overlay-F "hold 不产品化" | Q036 | 正确;且按后来校准的噪音门槛(Δ<0.5pp=噪音, Q080-P3),+0.074pp 本来就在噪音里,hold 比当时以为的更明显正确 |
| 3 | **闲置日来自信号稀缺而非 sizing 小**(17% 零仓日、61% 单策略日) | Q045 Phase 2D | 正确,是整条线里最有生命力的诊断 |
| 4 | 机制排序 C(扩覆盖)> A(继续加 sizing) | Q046 | 正确;A 的 cliff 证据(N2 20% 处 $/BP-day -113%)在其框架内真实 |
| 5 | per-trade target vs book-level、PM vs Reg-T 的口径校正,外部差距实为 ~5-10pp 而非 15pp+ | Q046 | 诚实、正确 |
| 6 | **cash-bound 事实**:现金 $37k=3.0% NLV,维持保证金 13.7%,BP headroom 56% | Q081 P0 (6/1 实测) | 整条线的分水岭,数据扎实 |
| 7 | debit cash cap 的治理概念(分母必须是被保护的稀缺资源) | Q081→SPEC-111 | 概念正确(校准问题见 §3.3) |
| 8 | 组合层统一 NLV 框架、~8% net 现实上限 | Q073 | 方法学正确,是账户级期望的唯一合法框架 |

---

## 2. 要改(明确不合理或不达现行标准)

### 2.1 框架层:"BP使用率太低是问题"已被推翻但未退役
- Q045 原文 "~89pp of account capital is idle on average" 在 cash-bound 事实下是**错误陈述**:资本从未闲置(在 QQQ/SPY/个股),闲置的只是 PM 风险额度(BP)。BP 的机会成本≈0(直到 crash 时它变成保命储备,见 §3.2)。
- 利用率是**输出**不是**目标**。把它当目标优化是 Goodhart:K×100 口径能把利用率"填满"而不产生任何经济内容(见 2.3)。
- **动作**:在 Q045/Q046 文档头部加 supersession stamp("framing superseded by Q081 cash-bound, 2026-06-01");Q046 的"向外部 20-30% 靠拢"目标句作废。

### 2.2 Q045 数字不过现行方法学(v1.1)
- **定价**:BS-flat sigma=VIX(先于 SPEC-119 CALIB),卖方 credit 系统性高估 1-2.5vp → 绝对 AnnROE(16-22%)与 Δ(+5.48pp)同比例虚高。
- **Sharpe**:daily-MTM 线性平滑(Q080-P1 证明虚增 ~+0.7);"Sharpe 反而改善 +0.05"这一卖点完全在 artifact 之内,unsmoothed 口径下方向未验证。
- **无 bootstrap CI、无 era 分层**;主窗口 2023-2026(牛市倾斜,Q082 已示范 3y 窗口代表性问题)。
- **"+20.7pp theoretical upper bound"应正式作废**:$/BP-day 对闲置 BP 的线性外推,无信号供给模型、无 crowding、无尾部放大。它当时给 Q041 的立项叙事定了不切实际的锚。
- **注意**:J3 的 Δ 本质是 ~1.5x sizing 的算术放大,方向可信;要改的是"若再用它论证进一步加 sizing,必须 CALIB+unsmoothed+era 重跑"。SPEC-084 参数本身不必回滚(见 §3.4 合成审计)。

### 2.3 "+22.21pp BP-fill"(Q041 attribution, SPEC-085 F3 输入)是口径通胀
- CSP BP 按 K×100 计。两种读法都推翻结论:
  - **cash-secured 读法**:K×100 是现金占用,不占 BP → BP-fill 贡献 ≈ 0,且消耗的是稀缺资源;
  - **PM-margin 读法**:真实 BP ≈ 12-18% notional → BP-fill ≈ +3-4pp,不是 +22pp。
- 原文 caveat 4 称 "mildly overstated" ——低估了约 5-6 倍的口径差。**动作**:F3 数值重述,SPEC-085 carrier 同步。

### 2.4 尾部披露必须换算到今天规模
- Q045 的 worst-trade -8.82% 是 $150k notional 上的 -$13,235;今天 NLV ~$1.24M、现金池 $152k。live 建议文案 "risk ≤ 4.5% of account" 的 "account" 是 PM 手动代入的。**动作**:以今天 NLV/现金池重述 worst-trade / CVaR 绝对值(feedback_absolute_at_today_scale,同类问题 Q083 已被抓两次)。

### 2.5 Q036 re-trigger 条件引用了低于噪音门槛的量级
- 触发器里 "marginal $/BP-day ≥ +10" 类条件在 +0.074pp 量级上不可测。若保留 hold 状态,触发条件需按噪音门槛重写;否则事实上等于 silent drop(note 自己警告过这一点)。

---

## 3. 没想到(审计新发现,按优先级)

### 3.1 【最高】扩张轴与资源画像的终点矛盾 + T2 collateral 模式决策缺失
- 线的结论=靠 Q041 扩覆盖填闲置;T2 落地=cash-secured(SPEC-115 Phase A, cash = K×100);账户事实=cash 稀缺、BP 富余。
- **今天实况**:liquid $152,346,已占用 ~$76.6k(50.3%),60% cap 余量 $14.8k < 任何一笔 T2 CSP(~$23-34k)→ T2 结构性被锁死,同时 BP 闲置。
- **需要 PM 决策**(不是 quant 单方面建议):T2 维持 cash-secured(则它与 BCD 竞争同一现金池,cap 阻断是正确行为,但"扩覆盖填 BP"的叙事作废),或改 PM-margin naked put(资源画像匹配,但引入 assignment/单名跳空尾部,需独立治理 + 2nd quant read)。两条路都成立,唯独"维持现状且继续叫它 BP-fill 轴"不成立。

### 3.2 【高】联合 crash BP 压力从未建模——"闲置 BP"的真实成本
- BP headroom 是 $1.24M 重 beta 账本的 crash 吸收垫(E-Trade 6/1 维持保证金已 17.4%)。2008-replay 下:beta 缩水 + PM house margin 扩张 + 期权 sleeve BP 膨胀是**同一天**发生的。
- 所有 BP-utilization 研究(Q036 Guardrail B 只做了 $150k sleeve 局部)都没算过"crash 日所需 BP 储备下限"。没有这个数,"BP 闲置太多"就没有可辩护的目标水位。**建议立项**(半天到一天的量级,用 Q073 stress 工具链)。

### 3.3 【高,日历上已到期】SPEC-111 复审
- Q082 Option C 约定 30-60 天 live test(自 6/2 起,今天第 35 天)→ **复审窗口已开**。
- 证据基数是 $37k 池 + BCD-only;现在池 $152k(4x)、cap 约束到了证据基外的新工具类(CSP collateral);tripwire 只有单向(触 55% → 收紧到 50%),没有放宽/重划范围的对称判据 —— 教科书式 status-quo bias 结构(memory 已三次实例)。
- 复审需回答:60% 比例在 $152k 规模下的绝对含义;CSP collateral 是否与 BCD debit 同池;对称触发条件。

### 3.4 【中】合成审计缺口
- SPEC-084 (bp_target 15/15/14) 在 35/50 ceilings + 独立引擎下校准;之后叠加了 Q073/SPEC-105 Arch-3 caps、SPEC-111 cash cap、BCD 治理 wait。每层各自验证过,**合成后的系统从未整体重仿真**:今天实际 binding 的约束(cash cap)不是任何一次回测优化时的约束(BP ceilings)。Q087-Q088 审的是策略 verdict,不是 sizing/治理栈。
- J3 是否在合成系统下仍是(可行的)最优,未知。

### 3.5 【中】利用率度量统一 + 仪表化
- 现存三个互不兼容的"利用率":回测 bp_pct(基于 $150k/$500k notional)、live PM maint/NLV(6/1=13.7%)、K×100 口径。**建议**:钦定 utilization := PM maintenance margin ÷ NLV,live 实测进 Command Center(PM BP 反推公式已有,research_pm_bp_calculation),今后任何"利用率"主张必须用这一个数。

### 3.6 【中,非本线但同源】Beta 集中度无主
- Q081 P0 obs 4:QQQ+SPY $749k = 60.4% NLV(单一 broker $447k)。标了"值得单独 review"后无人认领。它与 §3.2 是同一场 crash 的两面。

### 3.7 【低】Q045↔Q073 数字从未对账
- 22.39%/17.41%(sleeve, $150k)与 ~8% net(unified NLV)并存于文档,PM-facing 期望值应只有 Q073 框架一个。加一段官方对账说明即可。

---

## 4. 建议的处置顺序

1. **SPEC-111 复审 + T2 collateral 模式决策**(§3.1+§3.3)——日历已到期,且是当前唯一 binding 的约束。
2. **联合 crash BP 储备建模**(§3.2)——给"可部署 BP"定义下限,所有后续 utilization 讨论的前提。
3. **文档卫生**:supersession stamps、+20.7pp/+22.21pp 作废与重述、利用率度量钦定(§2.1/§2.2/§2.3/§3.5)——半天内可清完。
4. **合成栈重仿真**(§3.4)——量级较大,可在 1-2 之后立项。

*审计者利益披露:Q045/Q046/Q041-attribution 均出自本席位。本审计按 v1.1 标准回溯,不为旧结论辩护。*
