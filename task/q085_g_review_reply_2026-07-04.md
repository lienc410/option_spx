# Q085 G-Review Reply — S2-BPS 自适应采纳提案外审

**Date**: 2026-07-04
**Reviewer**: independent external quant reviewer (same reviewer as task/q085_p1_p2_external_review_2026-07-03.md)
**Verdict**: **RATIFY-WITH-CONDITIONS** — 条件 C1（风险数字更正 + PM 基于更正数字重新 ratify）与 C6（CALIB 可复现性）为 **blocking**；其余条件为采纳前必办。
**Verification**: P2a/P2b/P2c/P2d/P3 全部重跑复现（P3 逐数字一致：challenger CALIB -$53/笔、-$2,244/yr；P3b 时代切片从 P3 trade store 复现：2024+ n=16 +$591、2025+ n=10 +$1,014 win 80%；P2c S6-MES 2024+ n=38 +$210、rolling-24m 91→111→113→135→219 全部复现）。

---

## Part A — 前次未完成的 P2 结果确认盘（packet §3.5）

**(a) 预注册门槛下全槽位 FAIL：CONFIRMED。**
- P2a 实现正确且是对我要求的正确升级：Welch on-vs-off studentized 统计量、观察值与 null 同一统计量、per-batch BH 不 pooling（修复了我指出的 pooling 补贴问题）。7 个幸存 cell 重现：rsi2/down3/ibs @fwd1 A、rsi2/ibs @fwd5 A、ibs/down3 @fwd5 B。与我的预测集一致（我版本中的 F1_sma5_10/F4_rev3 差异来自我用 on-vs-stratum 而非 on-vs-off，非实现分歧）。
- P2c 实现核对无误：select/confirm 协议按注册执行；K3 bracket 三选一实现与注册一致；sizing 用全样本 p5（轻度 in-sample，但符号不变性使其对 FAIL 裁决无影响）。最差七年 2014-2021 -$31/事件 → FAIL 成立。
- S5-HV（p=0.10 关闭）、S3（前提消失 + 17.4% 可行性）关闭方向保守，接受。

**(b) S2 塌缩入 S6 的推理**：当时成立（fwd21 事实不显著 → 24-45DTE 结构无事实基础，按"事实先于 PnL"纪律正确）。P2d 的基准更正（执行类决策应对现任而非平均日，per `feedback_decision_type_governs_significance_standard`）是合法的重开路径，且它同时暴露了对挑战者用"最差七年"、对现任从未用同尺的双标——这个自查是诚实的。塌缩推理无遗漏检验。

**(c) Paper-trade 选项**：无反对——已被本 packet 吸收；见 Part C 条件。

**(d) 实现旗标**：P2b 镜像 battery 实现正确；IBS>0.8 @fwd5 p=0.0005（置换下限）且 fwd1/21 家族支持，可承重。其余 4 个 fwd1-only 幸存者（p=0.017-0.03）**仅因 12-test 小批 BH 宽松而过线**（在 329-test 总账下全灭）——标注"不得在其他槽位复用，复用前重测"。因 S6-MES 已 FAIL，此宽松度对本提案不承重（packet 自我标注恰当）。

## Part B — Packet §3 五个攻击点的回答（全部带复算数字）

**B1. 近期窗口的 n（攻击点 1）——比 packet 呈现的更弱，必须重述。**
完整 start-year ladder（challenger CALIB，我从 P3 store 复算）：

| 窗口 | n | mean/笔 | t |
|---|---|---|---|
| 2019+ | 39 | +$291 | 1.38 |
| 2020+ | 31 | +$345 | 1.39 |
| 2021+ | 30 | +$327 | 1.27 |
| 2022+ | 27 | +$350 | 1.28 |
| 2023+ | 24 | +$348 | 1.14 |
| **2024+** | 16 | **+$591** | 1.56 |
| **2025+** | 10 | **+$1,014** | 2.09 |

且按日历年：**2023 = -$108（n=8）、2024 = -$43（n=6）均为负**；"2024+ +$591"全部由 2025-26 的 9-10 笔承载；2018 年 -$1,274/笔（n=5）就在近旁。packet 引用的两个窗口恰是扫描的最大值，单测 t≤2.1。**BPS 载具的"当前时代有效"证据 = 2025-26 年 9-10 笔，post-hoc 选窗**——本身不足以支撑任何采纳。
真正较强的"当前时代"证据是 **S6-MES 事件流**（无定价模型风险、纯价差）：2024+ n=38 +$210 (t≈2.9)、自 2020 起 ladder 单调改善——packet 把它当"佐证"，实际它才是主证据，BPS 切片是弱佐证。**条件 C2 要求按此重排证据链。**（注意 MES 流是 A 层入场，与 challenger 层不同——外推仍有一步。）
更长 paper 期是否必要：见 C3——单位应是"观测事件数/校准测量数"，不是周数。按近期 ~7.3 笔/年，4-8 周期望 **<1 个信号事件**，作为 edge 验证是零；作为报价验证也只有 1-2 个信号日。

**B2. 降级参数移植（攻击点 2）——两处问题。**
(i) **(10, 6) 不在 P2e 预注册网格内**（网格 = (K=10,re=5)/(K=20,re=10)）。按 house 纪律"清单之外的切点无效"，要么用 (10,5)，要么在采纳前显式重注册 (10,6) 并说明理由。
(ii) 移植后的统计牙齿我已量化（per-trade sd $923，iid 正态近似 + 滚动模拟）：若当前时代 edge 真实（+$591），false-halt ≈ 2%/窗口；死亡时代（-$288/笔）下**触发停机前累计学费：均值 -$3,090、p5 -$7,651**；检测滞后 ≈ 10 笔 ≈ **1.4 年**（7.3 笔/yr）。规则可用，但 packet 引用的学费（$1-3k）低估了约一倍、尾部低估更多——并入 C1。另：P2e 证明这类 reactive stop 救不了 zero-mean chop，但 BPS-CALIB 的死亡形态是**持续负 bleed（-$288/笔）而非 chop**——trailing stop 恰好对 bleed 型有效。这是对提案有利的机制论证，packet 可以合法引用（P2e 结论不构成反对）。

**B3. CALIB 时代外推（攻击点 3）——方向正确，节奏必须制度化，且当前不可复现（见 C6）。**
偏移量（d0.30=VIX−2.0 / d0.15=VIX+1.0）测自 2026-06/07 单月、VIX 15-22。用于当前时代评估 = regime 匹配，恰当；用于 26y 全样本 kill = 超出测量域的外推，但方向保守（高 VIX 时 skew 更陡、对卖方更不利），kill 用途可接受。**恢复/继续的合法性依赖偏移量仍然成立** → C3 要求：paper 通道从第一天起每日记录 d0.30/d0.15 相对 VIX 偏移（任意日皆可测，不必等信号日）；CALIB 每季度重测 + regime 翻转后强制重测；从 paper 恢复实盘前必须有 fresh CALIB。若测得偏移比 CALIB 恶化 >0.5vp → 自动回 paper。

**B4. 多次翻转史（攻击点 4）——"P3b 无新参数"的立场不成立，但自适应结构本身是正确的解毒剂。**
事实：era 切片的起始日就是参数，且是在全样本 FAIL 后对 ~7 个候选窗口扫描后引用最好的两个（B1 的 ladder 证明中间窗口 t≈1.1-1.4、日历 2023/2024 为负）。姿态切换是 PM 权限内的风险决策（不评判），但它在两次门槛失败**之后**到达，时序本身是 selection 风险，必须按 `feedback_post_withdrawal_proposals_front_load_robustness` 入档披露（C5）。
我不因此 REJECT 的原因：提案的结构（1 张、paper-first、预承诺降级、季度复盘）正是把"不可事前验证的时代条件性主张"转换为**有界实时实验**的正确工具；从此刻起唯一合法的证据增量是 live/paper 流水——C5 同时锁死"不得再用历史重切片论证 resume/加仓"。

**B5. P2 系列确认项（攻击点 5）**：见 Part A，全部确认。

## Part C — 采纳条件（C1、C6 blocking）

- **C1（blocking）风险数字更正 + 重新 ratify**：packet §2.5 的"死亡年代伤害 -$31~-53/笔"是错误引用（-$31 = S6-MES 最差七年；-$53 = BPS CALIB **全样本**均值）。本提案载具的死亡年代真值 = **CALIB 最差七年 -$288/笔（PESS -$293）**，学费到停机：均值 ≈ -$3.1k、p5 ≈ -$7.7k、滞后 ≈1.4 年。cascade 数字核对无误（CALIB 下 21%、均值 -$566、26 年 2 次触 35）。PM 的姿态 ratification 是在低估 ~5 倍的死亡年代数字上做出的——**必须以更正数字重新 ratify**（informed consent；per `feedback_unquantified_caveat_sign_risk`）。
- **C2 证据链重排**：G-review 档案发布完整 start-year ladder（含 2023/2024 日历年为负、2018 年 -$1,274）；主证据 = MES 事件流（n=38, t≈2.9, 无模型），BPS 切片降级为"post-hoc 选窗弱佐证 n=9-16"并注明 MES 为 A 层的外推 gap。
- **C3 Paper 门以测量计，不以周计**：live 开关 = （≥8 周）AND（≥2 个信号日全报价记录，真实 credit 与 CALIB 合成差 ≤15%）AND（每日偏移监控均值在 CALIB ±0.5vp 内）。CALIB 季度重测 + regime 翻转重测；resume 前 fresh CALIB。
- **C4 降级规则**：参数回到 (10,5) 或显式重注册 (10,6)；SPEC 中写明检测滞后与学费分布（C1 数字）；追加**硬性累计止损**：sleeve 自成立累计 PnL ≤ -$5k（或 PM 自定并预承诺的数）→ 无条件全停 + 外审后才可重启。1 张锁定：≥20 个 live/paper 事件且 trailing-10 均值 >0 之前不得提任何加仓；加仓 = 新 G-review。
- **C5 自由度披露入档**：kill→revive(P2d)→withdraw(P3)→revive(P3b+姿态) 全链 + era 窗口扫描事实记入档案；此后 resume/加仓决策只准引用预承诺规则与 live/paper 流水，禁止历史再切片。
- **C6（blocking）CALIB 可复现**：偏移量（d0.30=VIX−2.0 / d0.15=VIX+1.0 / ATM=VIX−4.3）在 repo 内**无数据无脚本**（`data/q041_chains/` 仅 2 天，非声称的 2026-05-29..07-03 共 23 天）。这是同时承载 withdraw 与 revive 的唯一定价模型。封账前必须提交：测量脚本 + 23 天逐日提取的偏移表（或原始快照）。同理 P2e/P3b 目前只有 docstring 存根——提交可执行形式（P3b 可为 P3 store 之上的薄切片脚本）。
- **C7（次要）**：blocked/NORMAL 为今日参数重构的 point-in-time 注记（我首轮审查条款，仍未见于 packet）；季度报表须含与现任 sleeve 的同期持仓重叠（组合层堆叠，1 张下有界）；P2b 非 IBS 幸存者标注不得复用。

## 裁决理由摘要

预注册门槛下 K2 DOCUMENT 是正确的研究侧裁决（全部复现确认）。自适应采纳是 PM 权限内的风险姿态，其证据基础诚实版本为："信号 1-5td 边际为真（多方法稳健）；MES 流显示当前时代 edge 抬升（n=38, t≈2.9, 无模型）；BPS 载具当前时代证据弱（9-16 笔、扫描选窗）；摩擦裁决悬于一个当前不可复现的 23 天校准。" 在 1 张 + 预承诺降级 + 硬性累计止损 + 测量化 paper 门之下，该实验的最坏学费是一个预先写死的数字，而其信息价值（真实 credit 终结 BASE/CALIB 之争 + 真实 OOS 事件流）为正。故 RATIFY-WITH-CONDITIONS 而非 REJECT；若 C1/C6 不被接受，则本裁决自动转为 REJECT（理由：在错误风险数字上取得的 ratification 无效 + 承载性校准不可验证）。
