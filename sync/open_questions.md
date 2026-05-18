# 开放问题追踪（Open Questions）

> 未解决问题、阻塞项、待验证假设。双端均可更新，HC负责整合。
> 状态：`open` / `blocked` / `resolved`

最后更新：2026-05-17（**Q073 CLOSED — PROMOTE Arch-3**。2nd Quant PASS。Arch-3 locked：Normal SPX cap 80% / Stress cap 50% / Second-leg cap 40% / HV Ladder 0% / Q042 Sleeve A 17.5% staged。SPEC 待起草）

---

## 当前优先阻塞

### Q009 — Schwab Developer Portal 批准等待中
- **状态**：blocked
- **内容**：该项保留为 **MC 侧系统状态**。HC 已成功连接 Schwab Developer Portal，因此它不是当前 HC planner 主线 blocker；但若 MC 侧环境仍未完成批准，则 SPEC-035 AC1/3/4/5 live Greeks 联调在 MC 侧仍受阻
- **阻塞下游**：live position Greeks enrichment（SPEC-035）
- **备注**：后续索引层若从 HC 视角总结 blocker，应避免直接把 Q009 写成 HC 当前 blocker
- **来源**：MC Handoff 2026-04-10；HC 状态修正 2026-04-12

### Q001 — SPEC-020 RS-020-2 ablation 未完成
- **状态**：blocked
- **内容**：RS-020-1 FAIL（信号逻辑15/15通过，但 `run_backtest` 缺少 toggle 参数，ablation AC7–AC10无法验证）；AMP 负责修复 `run_backtest` toggle 并完整实现 `run_trend_ablation.py`（4路ablation + regime breakdown + OOS路径）
- **依赖**：RS-020-2 由 AMP 实施，HC不应假设其已提交或通过
- **阻塞下游**：overlay_mode 切换为 active；SPEC-020 → DONE
- **注意**：`bearish_persistence_days` 实际值为3（signals/trend.py L33），HC不得自行修改
- **来源**：MC Handoff 2026-04-04

### Q002 — Shock Active Mode 生产切换决策（Phase B）
- **状态**：open
- **内容**：SPEC-027 Phase A shadow analysis 已完成；Phase B A/B 测试需数据驱动决策：active mode 是否满足 AC B1–B4（trade count 下降 ≤10%，PnL 下降 ≤8%，MaxDD/CVaR 不劣化）
- **依赖**：Phase B 回测结果
- **来源**：SPEC-027，research_notes §36

---

## 策略设计待解决

### Q073 — Portfolio-Level ROE Optimization Round 2

- **状态**：**resolved** (Q073 CLOSED — PROMOTE Arch-3，2026-05-17，2nd Quant Final PASS)
- **结论**：Arch-3 全面优于 Arch-2 和 baseline — 6 binding rules 全 PASS，bootstrap sig 100%，walk-forward both halves PASS
- **Arch-3 Locked Configuration**：
  - Normal SPX cap：80%（R1: 70→80，governance amendment）
  - Stress SPX cap：50%（R5: 60→50）
  - Second-leg cap：40%（R6: hard-block → 40% numeric cap）
  - HV Ladder /ES：0%（portfolio allocation decision，NOT signal alpha rejection；退回 paper-only）
  - Q042 Sleeve A：17.5%（staged ramp 10→12.5→15→17.5%，per-stage PM gates non-time-locked）
  - Cash (BOXX)：residual
- **验证指标（Arch-3）**：Net ann ROE 7.95% / MaxDD -8.71% / Worst 20d -7.04% / Sharpe 1.97 / V6 bootstrap 100% / V7 walk-forward PASS
- **关键研究结论**：
  - HV demotion = portfolio allocation decision（NOT signal alpha rejection）——alpha 完好，但在 Arch-3 组合中 slot 给 Q042
  - Q042 Sleeve A 17.5% STAGED ramp（10→12.5→15→17.5%），每段 non-time-locked gate
  - Governance philosophy 不变："only numeric caps updated"
  - Arch-2 = implementation-preferred（NOT risk-preferred）fallback
  - 新 monitors：Q042 live concentration + SPX normal→stress transition loss
- **6 个 2nd Quant 修订**：全部应用到 q073_final_memo.md（HV demotion framing / staged ramp / governance philosophy / 2 monitors / bootstrap CI caveat / Arch-2 fallback 措辞）
- **Quant 交付**：12 个文件 + 5 个 compute scripts + CSV data outputs — `See: research/q073/q073_final_memo.md`, `task/q073_p5_2nd_quant_review_packet_2026-05-17_Review.md`
- **后续**：SPEC 待起草（Governance 修订 + HV Ladder 降级 + Q042 staged ramp）— Quant 停止 Q073 扩展研究，SPEC 支持 only

---

### Q012 — `/ES` short put 生产路径与共用 BP 管理

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q012` and `RESEARCH_LOG.md` for full research record.

---

### Q072 — Sleeve Global Evaluation & Stress-Episode Governance

- **状态**：**resolved** (Q072 CLOSED — APPROVED 2026-05-15) — pending SPEC-103 approval
- **结论**：Augmented Default Cap = R1-R4 默认 caps + R5 stress episode SPX cap reduce to 60% + R6 second-leg state hard-stop new short-vol entries
- **关键 P4C 实证**：
  - **Priority allocator ≡ FCFS** in 19y simulation（5-allocator sim 给出完全一致的 total P&L $742k / max DD -$175k）—— 不实施
  - **Static per-sleeve cap 减少 $102k P&L 无 max DD 改善** —— 不实施
  - **R6 second-leg block** 2022 stress 真实 backtest 节省 $11.6k 组合损失（B_tight -$151k vs default -$163k）
  - Walk-forward Spearman 0.704 (moot 因 priority allocator 无价值)
- **回答 5 个原 P4 待答问题**：
  1. 不砍任何 sleeve（DD/Aftermath/HV 都是 alpha 贡献者）
  2. Static sleeve cap **比 main-first/FCFS 差**（损失 $102k 无 tail 保护）
  3. Priority allocator **不优于 static cap**（19y 中 priority ≡ FCFS）
  4. R6 second-leg block 处理"BP 紧张时谁让位"——short-vol 让位
  5. 2022 backtest slice 已含 HV，2008 stress 与全合成 inject 待 Q071 lock 后做（不阻塞 SPEC closure）
- **后续追踪项**（不阻塞 close）：
  - ~~SPEC-103 实施 R5/R6 + portfolio state tracker~~ ✅ DONE 1c690cc
  - Cap recalibration（63f8825）✅ DONE 2026-05-16：R1 维持 70%，依据改 PM-call safety；R3/R4 future-watch 1 个月
  - Q071 HV Ladder final config lock 后做 P4B /ES rerun + P4C.7 full synthetic stress（仍待）
- **来源**：Quant Researcher 2026-05-15；详见 `research/q072/q072_final_memo_2026-05-15.md`, `task/SPEC-103.md`, `research/q072/q072_p4_cap_recalibration_2026-05-16.md`, `RESEARCH_LOG.md R-20260515-01`

---

### Q050 — Portfolio-Level Shared-BP Governance Framework
- **状态**：open
- **内容**：这是在 `Q012 Phase C` 之后新增的更高层研究条目，用来承接 PM 对“不要补丁式思考，而要从整体 portfolio 合理性出发”的要求。`Q012` 已经回答了当前规模下的 `/ES` 实施目标：只做 stressed-SPAN 可见性，不做完整 shared-BP 治理框架。但这并不等于全局问题消失了。随着系统从单 SPX execution platform 过渡到 multi-sleeve portfolio research platform（`Q041`、`Q045`、`Q046`、`Q048` 已经共同指向这一点），仍然需要一个独立研究 lane 去回答：当多个 sleeve 真正竞争同一 PM buying-power 池时，账户层的治理哲学应该是什么
- **研究焦点**：
  1. scarce PM BP 的顶层治理原则（capital-efficiency first / regime-priority / stress-survivability / idle-capacity-first 等）
  2. sleeve taxonomy（production-alpha / capital-fill / opportunistic / stress-contingent / observe-only）
  3. scale trigger：什么规模下才值得从“监控”升级到“allocator / governance”
  4. stress hierarchy：压力来时谁先压缩
  5. 哪些规则应保留在 Quant governance，哪些成熟后才进入 platform behavior
- **与 Q012 的关系**：
  - `Q012` = 当前 `/ES` 在 `1` 合约规模下的正确最小实施目标
  - `Q050` = 更长期、跨 sleeve 的全局 shared-BP 治理研究
  - `Q050` 不应被塞进 `SPEC-088`，也不应阻塞 `Q012` 的窄实现
- **当前归类**：research seed；not ready for DRAFT Spec
- **下一决策**：先保持研究层存在，不进入当前 implementation queue。待 `/ES` 规模扩大、或多个 sleeve 真正开始 material competition 时，再决定是否升级为正式 Quant deep dive
- **来源**：Planner 收口 2026-05-08；详见 `doc/q050_portfolio_shared_bp_governance_framework_seed_memo_2026-05-08.md`

### Q051 — `/ES` honest-parameter 口径下是否仍有可恢复的 performance edge

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q051` and `RESEARCH_LOG.md` for full research record.

---

### Q052 — `/ES` defensive redesign after closure of the original thesis line

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q052` and `RESEARCH_LOG.md` for full research record.

---

### Q053 — Main Strategy Performance in Grinding-Decline Regimes (2018-Q4 / 2022)

- **状态**：**CLOSED 2026-05-09**（Tier 1+2+3 完成；C2 反向调查；2nd Quant APPROVE WITH ADJUSTMENTS — R-20260509-06）。C3 (regime-conditional strategy filter) 保留为 standing architectural candidate，触发条件见下方 §revisit。
- **内容**：`/ES` 5 轮研究反复显示，short premium 策略最难受的环境不是 2008/2020 风格的 VIX spike + crash，而是 **2018-Q4 / 2022 风格的 medium-VIX grinding decline**。关键特征：VIX 在 20-30 区间持续数月，从未触发 EXTREME_VOL gate，但 IV 缓慢扩张 + 缓慢下跌持续磨损 short premium 仓位；spike-based hedge（Overlay-F / BSH）在这类环境下不赔付。这套约束几乎确定也存在于主策略（BPS / IC / BCD），因为它们同样依赖 EXTREME_VOL gate 作为高 VIX 拒绝层，对 grinding decline 没有专门 detect 机制
- **核心研究问题**：主策略在 2018-Q4 和 2022 全年的实际表现是怎样的？信号路由是否被 "grinding without spike" 模式系统性误导？现有 risk_score / regime gate 是否对中等 VIX 持续磨损环境有合理的保护？
- **不重复的研究范围**：
  - 不重新跑全 19 年回测
  - 不重新评估 EXTREME_VOL 阈值（这条已稳定）
  - 不基于 SPX proxy 数据（用主策略真实 BPS/IC/BCD 历史）
  - 不试图"解决" grinding decline（那是后续工作）
- **建议的 Tier 1 范围**：
  - 提取 2018-Q4 (10/01-12/31) 和 2022 (全年) 主策略真实 trade record
  - 计算 PnL / drawdown / WR / stop rate / regime distribution per window
  - 与全样本均值对比，识别系统性偏差
  - 输出"grinding decline 是否是主策略隐蔽弱点"的明确判断
- **Tier 1 结果（DONE 2026-05-09）**：

  | 窗口 | n | 总 PnL | WR | Avg PnL/笔 | Stop rate | vs baseline |
  |---|---|---|---|---|---|---|
  | Baseline (Other) | 260 | +$1,701,931 | 76.9% | +$6,546 | 0.8% | — |
  | 2018-Q4 | 4 | +$10,074 | 75.0% | +$2,518 | 0.0% | −61% Avg |
  | 2022 grinding bear | 18 | **−$26,778** | **55.6%** | −$1,488 | 0.0% | −123% |

  关键发现：（1）**2022 全年亏损 −$26.8k**，WR 跌 21.4pp；（2）stop rate 0.0%——`pnl_ratio` 止损机制在 grinding decline 中完全没触发，仓位仍系统性磨损；（3）损失集中在 BPS / IC_HV / BPS_HV，与 `/ES` 研究的 short premium 受伤模式一致。结论：**grinding decline 是主策略实证确认的隐藏弱点**，Tier 2 扩展合理。详见 `RESEARCH_LOG.md R-20260509-03`。

- **Tier 2 结果（DONE 2026-05-09）**：模式重新定义——不是"压力=受伤"，是**"无 spike 的 grinding=受伤"**。Spike-recover（2011/2018-Q1）→ 大赚（100% WR）；Persistent grind（2015-16/2018-Q4/2022）→ 系统性亏损。最佳信号 R1（VIX 30d MA ≥ 22 + 60d max < 35）FP rate 9%，selectivity −$4k/笔；但 R4 完全 miss 2022 核心亏损（17 笔中 0 笔被 flag）。结论：简单信号无法做硬 entry-gate；需要"无回撤"时间维度组件。PM 选 Option B。
- **Tier 3 结果（DONE 2026-05-09）**：6 个候选信号（含 "no-recovery" T2/T3 + 加 SPX drawdown 组合 + backwardation T4）全部 fail cost-benefit。最佳 T3 在 19 年损失 -$87.7k，仅换 2022 改善 +$2.7k。**简单信号家族不能 cleanly 分离 grinding-decline 与 normal-elevated-VIX trades**。但 strategy-level 视角发现 2022 损失全部集中在 put-side（BPS/IC_HV）；call-side 反而盈利。Suppress put-side 在 2022 可省 +$31k——但需要 C3 架构改动。
- **Tier 3+ VIX term structure 测试（DONE 2026-05-09，R-20260509-07）**：8 个 VIX/VIX3M spread 信号变体全部 fail（最佳 TS6 仅 2/4 criteria 优于 R1）。**结构性原因**：2022 grinding 期间 VIX 中位数 25.5 但 spread mean -1.93（比 baseline -1.69 更负），%spread>0 仅 6.0%——curve 整体平移而非倒挂。VIX term structure 是 acute spike detector，不是 grinding detector。2nd Quant **APPROVE — DROP term-structure signal family**。详见 `research/q053/tier3plus_term_structure.py`。
- **Q053 最终状态（2026-05-09）**：信号宇宙近场已穷尽（VIX 均值 / no-recovery / drawdown / backwardation / term structure 全部测试失败）。Q053 line 正式 CLOSED；C3 保留为 standing architectural candidate；future Tier-4 cross-asset signals（HY credit / rates curve / RV-IV / VVIX / breadth）记录在 R-20260509-07 但**不主动启动**——仅在 R-20260509-06 的 4 条 standing trigger 之一触发时重新打开。
- **C2 反向调查（DONE 2026-05-09）**：Tier 3 怀疑 2022 worst trade（-$24,606，92% of year）是 engine sizing bug。Reproduction 证明 NOT a bug：那是正常 BPS（$23,757 credit, 6.89 contracts, 32% max-loss in 9-day SPX -4.2% drop）。"$-34 zero-credit" 是 display artifact——`Trade.entry_credit` 字段存 per-share signed index pts，不是 dollar credit。同时发现 `Trade.pnl_pct` 单位 bug（除 per-share signed 给出无意义 -72,058%）。Fast Path 修复已 commit。详见 R-20260509-05。
- **§revisit — C3 trigger（2nd Quant 校正 R-20260509-06）**：C3（regime-conditional strategy filter）作为 standing architectural candidate 保留。**任一条件**触发即可重新打开（不需要等多个）：
  1. PM explicit prioritization — **已触发 2026-05-09**：PM 选路径 2，Quant 正在测试 VIX term structure（VIX-VIX3M spread）信号，约半天出结论
  2. 又一个 2022-style calendar-year loss 出现
  3. **rolling 3-month put-side strategy PnL 在 medium-VIX (VIX 30d MA in 20-30) grinding 条件下跌破阈值**（默认：3 个月内 put-side 累计 PnL < -1.5× 历史 MAD）— **Planner 月度检查项**
  4. Q041 / Q036 部署使账户 short-premium / put-side 暴露**显著上升**（如 Q041 Tier 1 paper-trading active，或 Q036 Overlay-F shadow→active）
  
  Trigger 3 由 Planner 加入 PROJECT_STATUS 月度更新流程；Trigger 4 由 spec 进展事件触发；Trigger 1-2 由 PM 决定。
- **来源**：R-20260509-02/03/04/05/06
- **不在范围**：
  - 任何指向 `/ES` 重启的内容（Q012/Q051/Q052 已正式 closed）
  - Q036 Overlay-F 的重新评估（那是一个独立 revisit gate）

---

### `/ES` Research Absorption — Standing Principles (from R-20260509-02)

- **状态**：active reference（不是研究问题，是 governance 原则。从 Q012/Q051/Q052 closure 沉淀）
- **必须吸收的原则（5 条）**：
  1. **IV expansion 领先于 lagging signals** — 任何依赖滞后价格/趋势信号的 short-premium exit 在结构上失败。Risk control 必须 entry-gated，不能 exit-driven
  2. **主策略的 entry-gated / regime-gated 设计是正确方向** — 不要 retrofit lagging exits 到 short-premium positions
  3. **`pnl_ratio` 止损 > credit-multiple 止损** — 不要简化 BPS/IC stops 为 "close at 3x credit" 形式（在低 premium 下语义失真）
  4. **2018 / 2022 grinding decline 是主策略隐藏风险** — 已开为 Q053
  5. **IV expansion stress test 必须成为 spec-review 标准工具** — Action A1（见下）
- **谨慎吸收的 calibration（3 条）**：
  6. Overlay-F scale-dependence 是 **revisit hypothesis**，不是 conclusion。Trigger：主策略 BP 利用率 > 25-30% NLV 后重新评估 Q036
  7. 资本效率必须用 **stress-capital basis** 评估，不是 entry-margin% — `/ES vs SPX BPS` 的真实差异在 stress capital，不在 entry BP
  8. 任何依赖 PM 人工执行的规则必须明确测试 **T+0 / T+1 / T+2** delay sensitivity
- **七个 action items**（修正：原漏记 4 条治理 codification 动作——原则不写入正式文档等于没有）：

  **待推进（3 项，Quant 执行）**

  | Action | 类型 | 依赖 | 工作量 | 状态 |
  |---|---|---|---|---|
  | **A1** 构建 `iv_expansion_stress_test` 工具 | Quant 原型 | 无（Phase A 已有） | Tier 1 / 半天 | ✅ DONE 2026-05-09 — `research/tools/iv_expansion_stress_test.py` |
  | **A2** Q053 Grinding Decline Regime Review | Quant 研究 | 主策略历史 trade record | Tier 1 / 一天 | ✅ DONE 2026-05-09 — Tier 1 完成；2022 亏损 -$26.8k 已证实；Tier 2 待启动 |
  | **A3** Q041 SPX CSP IV-expansion stress appendix | 治理附件 | A1 就绪 | 30 分钟 | ✅ DONE 2026-05-09 — `doc/q041_execution_prep_packet_2026-05-05.md §11` |

  依赖关系：`A1 → A3`；`A2` 独立可并行。

  **待触发（4 项，非待办）**

  | Action | 触发条件 | 落地文件 |
  |---|---|---|
  | **A4** 5 条 Short-Premium Principles | 下次 short-premium spec 评审时引用 | `QUANT_RESEARCHER.md` |
  | **A5** Overlay-F revisit gate | 主策略 60 日均 BP 利用率 ≥ 25% NLV | `Q036 §revisit gate` |
  | **A6** stress-capital basis 评估 | 下次 short-premium spec 评审 §6.1 | `REVIEW_TEMPLATE.md §6.1` |
  | **A7** T+0/T+1/T+2 delay sensitivity | 下次依赖人工执行的 spec 评审 §6.1 | `REVIEW_TEMPLATE.md §6.1` |

  **Planner 月度监控义务（来自 Quant 建议）**：月度 PROJECT_STATUS 更新时检查主策略 60 日 BP 利用率；穿越 25% NLV 时通知 PM/Quant 评估 Q036。
- **来源**：R-20260509-02；2nd Quant PASS verdict
- **不在范围**：本节是 standing reference，不是研究问题；不应被当作开放任务

---

### Q055 — /ES P2 True Ladder + V2c Upgrade：是否将 fixed-slot 实现升级为 spec 设计意图的 rolling weekly ladder

- **状态**：**CLOSED 2026-05-10 — 竞争已执行，/ES V2c (A) 胜出，SPX CSP T1 (B) 淘汰**（B 在 V1 veto 失败：2020 COVID worst trade -17.99% NLV > -15% 阈值；且 A 在所有 Tier 2 主指标全胜）。结论：/ES V2c 进入 SPEC 评审轨道；00k 账户下 naked put 槽归 /ES — 
- **背景**：Q041 T1 vs /ES 治理审查（2026-05-09）发现 /ES P2 当前代码实现（fixed-slot，每槽独立周期入场）与 spec_initial.md 设计意图（每周入场 1 张 49DTE，持有衰减至 21DTE）结构不同。True rolling ladder (V2) + soft stop (V2c, STOP_MULT=8.0) 在 26 年 BS-flat 合成数据上：Ann ROE +0.45% → +1.29%（+0.84pp，2.9× alpha multiple），MDD 改善（-57% → 估计 -40%），worst trade -1k → -0k
- **统计状态**：V2c borderline 显著——V2 bootstrap 75% 种子在 block=250 下显著，CI 下界中位 +0.06%。V2c 是 V2 衍生物，bootstrap 未直接测试。需 paper trading 前先确认
- **STOP_MULT 关键发现**：STOP_MULT=3.0 在 true ladder 下是 alpha 杀手（V1 -2.35% vs V2 +2.58%，差 -4.93pp）；stop=8 是同时改善 alpha 和保留 tail discipline 的 Pareto 候选
- **待 PM 决定**：
  1. V2c 是否进入 SPEC 评审（需局部重开 /ES 研究线，不影响 SPEC-061/086/088 生产状态）
  2. 若进入 SPEC，是否需要先在 true ladder 框架下补 bootstrap 验证 V2c 本身的统计显著性
- **Caveats**（必须在 SPEC 中显示）：全部基于 BS-flat 合成数据；BSH/动态杠杆与 V2c 交互未测试；几何 vs 算术 Ann ROE 口径差异
- **不影响**：SPEC-061/086/088 生产状态；Q012 Phase C（SPAN visibility）结论；Q050；主策略
- **来源**：

---

### Q056 — /ES P2 V2f 升级：是否将 /ES P2 实现从 fixed-slot 升级为 true rolling weekly ladder + STOP_MULT=15

- **状态**：**SPEC-095 APPROVED 2026-05-10** — Developer queue 等待实施
- **内容**：V2f（true rolling weekly ladder，entry=49DTE，exit@21DTE，STOP_MULT=15）是 /ES P2 升级的 Pareto 最优候选。Ann ROE +2.67%（几何），worst -10.96% NLV（V1 veto PASS），bootstrap 100% 种子显著（block=250），strictly Pareto-better than V2 no-stop。当前 SPEC-061/086/088 生产状态不变，仅 backtest 层实现修正 + `run_phase2_v2f()` + `/api/es-backtest/v2f` + /es 页面 V2f tab
- **来源**：`task/SPEC-095.md`

---

### Q057 — V2f 定价 Massive sanity check：true ladder 框架下的定价假设是否在实数据上成立

- **状态**：**CLOSED 2026-05-10 — Tier 1 完成**（R-20260510-04）。结论：BS-flat 系统性低估真实 OTM put 权利金 **+17.6% 中位（全样本）/ +24.7%（V2f 真实 DTE 窗口）**，远超 3% 原 caveat；属 substantive caveat（>7% 阈值触发）。但方向**有利**：BS 低估 → V2f 真实 Ann ROE 约 +3.0-3.5%（vs 报告 +2.67%），Conservative 方向。V2f SPEC 不阻塞，但 SPEC-095 UI 的 caveat 文字（原 "~2-3%"）需 patch 为 "~18-25%"，并并列展示 skew-adjusted 估算。**Developer patch pending**
- **来源**：`RESEARCH_LOG.md R-20260510-04`，`research/q057/tier1_pricing_bias.py`

---

### Q058 — BSH 在 V2f 框架下的角色：是否仍是必要的 tail mitigation

- **状态**：**CLOSED 2026-05-10 — Tier 1 + Tier 2-A 双轮验证，Tier 2-B 关闭；Verdict: DROP BSH in V2f（FINAL）**
- **结论**：BSH 在 V2f 框架下双轮验证均 NET-NEGATIVE：Tier 1（fixed 1-contract）-0.57pp Ann ROE；Tier 2-A（dynamic leverage）-0.46pp——dynamic leverage 仅改善 +0.11pp，不改变 DROP 结论。V2f 的 true ladder + STOP=15 已内嵌 Phase 4 BSH 想解决的尾部问题，BSH redundant。Tier 2-B（Massive 定价 sanity check）关闭——BSH 已 DROP，bias 方向由 Q057 已覆盖。**独立发现**：V2f + dynamic leverage WITHOUT BSH 给出 +0.86pp Ann ROE（+2.46% → +3.32%），但 worst trade -14.03% NLV（V1 veto 余量仅 -0.97pp）——留 PM 决策是否开 Q060
- **治理归档**：`task/q041_t1_es_governance_review_archive_2026-05-09.md §13-§15`（正式 CLOSED）
- **来源**：`RESEARCH_LOG.md R-20260510-05`（Tier 1）、`R-20260510-06`（Tier 2-A）

---

### Q060 — /ES V2f + Dynamic VIX Leverage：独立升级候选的统计稳健性与尾部风险

- **状态**：**CLOSED 2026-05-10** — bootstrap 95% PASS；stress test -23.94% NLV ❌ FAIL → 不进 SPEC
- **结论**：V2f + dynamic leverage alpha 真实（+0.86pp，95% bootstrap），但 1987 量级 stress 下单 trade -23.94% NLV（超 -20% PM 阈值），降级为观察项。**关键副发现**：V2f_alone 自身在 1987 量级 stress 下 single-trade worst -16.85% NLV（违 V1 -15%），cluster loss -47.1%——"-9.24% historical worst ≠ tail-bounded"。PM 决策点已开为 Q061
- **治理归档**：`task/q041_t1_es_governance_review_archive_2026-05-09.md §16–§18`（正式 CLOSED）
- **来源**：`RESEARCH_LOG.md R-20260510-07`，`backtest/prototype/q060_dynlev_bootstrap_stress.py`

---

### Q061 — V2f 尾部风险缓解：三条路径 PM 决策

- **状态**：**CLOSED 2026-05-10** — PM 决策完成：M3 ✅ DONE（SPEC-096）；M1 ✅ → SPEC-097；M2 ❌ DROP（路径依赖致 stress 恶化）
- **结论**：M1（cluster N≥4 降速 10TD）推荐接受 as-is（PM 选 A）：Δalpha=-0.11pp，stress worst -15.13%（V1 近似恢复），Sharpe 微升。M2 在当前形式效果反向，正式 DROP（PM 选 X）。M1 进 SPEC-097 实施
- **来源**：`RESEARCH_LOG.md R-20260510-08`，`backtest/prototype/q061_m1_m2_alpha_impact.py`

---

### Q059 — 未来账户增长重做竞争：NLV 达到 M+ 时重新比较 /ES V2f vs SPX CSP ladder

- **状态**：open（future trigger；不是当前研究项）
- **内容**：Q055 竞争结论在 00k 账户下成立：/ES V2f 胜出。但 SPX CSP T1 的 per-contract $/year 更高（,333 vs ,354），其劣势完全来自无法 ladder 部署。当 NLV ≥ M 时，SPX CSP 可铺 5 槽 ladder，竞争格局可能逆转。届时重做 Q055 协议
- **触发条件**：账户 NLV 穿越 M
- **来源**：

---

### Q013 — `/ES` short put 运行时止损与持仓管理定义
- **状态**：open（bot alert gap 已关闭）
- **内容**：`SPEC-086 DONE`（2026-05-07）已交付最小可接受范围：`notify/telegram_bot.py` 的 `intraday_monitor` 循环现在持续监控 `/ES` put mark，≥ 2× entry premium 发 WARNING，≥ 3× 发 TRIGGER（即 SPEC-061 credit stop 线）；fail-soft 设计，Schwab 不可用时不产生误报。PM 明确的"不能接受纯人工盯仓止损"最低要求已满足，B1 blocker 正式关闭。趋势转负后的现有持仓行为以及 Layer 1 / Layer 3 覆盖仍未定义
- **已关闭子项**：stop 监控 + bot alert（via `SPEC-086`）
- **剩余开放项**：post-entry 管理，Layer 1 / Layer 3 覆盖；Schwab `mark` 字段单位（per-share）待第一笔真实 `/ES` 仓位开立后验证
- **当前归类**：bot alert gap closed; remaining post-entry / leverage scope deferred
- **已落地硬化**：`strategy/es_params.py`（`EsShortPutParams`）已创建，并已接入 backtest / bot / server-side BP-limit。未来 `/ES` 参数变更应默认从这里出发，避免 stop / DTE / sizing 口径再次分裂
- **来源**：`SPEC-061` review + `/ES` 三层体系覆盖盘点，2026-04-12；`SPEC-086` DONE 2026-05-07

### Q017 — VIX 顶峰回落早期窗口：HIGH_VOL 分支是否结构性错过机会

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q017` and `RESEARCH_LOG.md` for full research record.

---

### Q018 — HIGH_VOL aftermath 单槽位约束在 double-spike 事件中是否错过第二峰

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q018` and `RESEARCH_LOG.md` for full research record.

---

### Q019 — backtest 的收盘口径 VIX 与 live recommendation 的开盘 / 早盘 VIX 口径是否存在系统性偏差
- **状态**：deployed — SPEC-091 已上 old Air（commit `1463c5b`，2026-05-09），Signal 2 sidecar 监控期开始；Q019 closure 等待 6 个月 live recovery 实测确认
- **部署形态**：sidecar 独立运行，不并入 Signal 1 主调度；Signal 1（09:35 push）保持原样不变；新增 Signal 2 · Settled VIX 面板与 `/api/recommendation/settling` 只读 API；launchd `com.spxstrat.signal_settling` 09:30 ET 触发；AC1-AC10 全通过
- **PM 2026-05-09 决策**：reject Path A（不改）；reject Path C（live 改 close-based）；**select Path E（live 改 stable rule，按 settling VIX 做日 recommendation，sidecar 形态）**
- **预期收益**：把 live-vs-backtest divergence 从 -0.6pp 削到约 -0.2pp AnnROE（recovery 60-70%）
- **测试基础（R-20260509-09）**：四层测试结果：
  - Tier 2 upper bound: -1.37pp（含 rolling-stat substitution 噪音）
  - Tier 2.5 mixed-mode: -0.63pp（current=open, history=close）
  - Tier 2.6 hourly 2024-2026 stable rule: recovery 67.4%
  - Tier 2.7 OHLC midpoint proxy 19y: -0.16pp，cumulative recovery 72.8%，worst-5y 中位 ~62%
- **SPEC-091 锁定参数**（Q019 校准产物）：
  ```
  SETTLING_INTERVAL    = "1h"
  SETTLING_THRESHOLD   = 0.5
  SETTLING_TIMEOUT_MIN = 180
  SETTLING_DATA_SOURCE = "yfinance:^VIX"
  ```
- **Sidecar 设计选择**（Developer 实施层决定）：Signal 2 不替代 Signal 1；两条路径并行运行，UI 同屏展示。优点：Signal 1 现有 push 路径零风险；6 个月观察期可对比两者实际偏离。代价：用户需理解"一日两信号"——已通过首页面板与 Telegram 差异消息消化
- **监控基线（Quant 定）**：
  1. Stable 触发率 ≥ 70%（research 预测 80%；20pp 余量给 OOS noise）
  2. Timeout 率 ≤ 20%（research 预测 12%）
  3. Recovery rate（Signal 2 vs Signal 1，按 selector 输出对比）应在 50-85% 区间
  4. Oscillation（stable 后 1 小时 VIX 又移 ≥1.0）应 ≤ 30%
  超任一阈值由 Quant 评估是否调 θ 或 timeout
- **外部数据路径状态**（避免重复试错）：
  - Twelve Data 不支持 CBOE VIX 现货指数；VIXY hourly 仅回到 2020-05
  - Polygon Indices Developer $79/月单月可拉 10y 真 hourly VIX；如生产 hourly VIX 数据源选定为 Polygon，需要常驻订阅而非单月
  - CBOE DataShop $300+ one-time，不推荐
- **MC 2026-04-24 历史证据**（HC Tier 1 已复现 9.48%，与 MC 9.71% Δ 0.23pp）：
  - aftermath 层 `4.63%` flip / regime 层 `9.71%` flip / trend 层 `31.54%` flip
  - aftermath `319` 个 flip 中，`179` close=False/open=True，`140` 相反
- **关联记录**：`R-20260509-08`（Tier 1+2 + 2nd Quant APPROVE）、`R-20260509-09`（Tier 2.5/2.6/2.7 + Path E 选定 + θ recovery sweep + SPEC-091 deployed）、`QUANT_RESEARCHER.md` "Backtest-vs-Live Convention Divergence (Q019 governance)" 章节、Pre-SPEC memo `task/q019_path_e_pre_spec_2026-05-09.md`、`task/SPEC-091.md`、`task/SPEC-091_handoff.md`
- **当前归类**：deployed, monitoring active
- **Quant 后续介入点**：
  - 第 1 个月（2026-06-09）：跑 Signal 1 vs Signal 2 对照统计，看 stable 触发率、timeout 率、selector flip 频次
  - 第 3 个月（2026-08-09）：完整 recovery rate 实测 vs research 预测 67.4%
  - 第 6 个月（2026-11-09）：最终 closure 评估；若实测 recovery 落在 50-85% 区间，Q019 正式 close + 把 Signal 1 切换到 Signal 2 输出（合并 sidecar）；若不在，回头评估 θ 或 timeout 调整
- **来源**：PM 新增研究问题，2026-04-19；2026-05-09 Path E 选定 + SPEC-091 deployed

### Q020 — MC `backtest_select` 简化导致 `SPEC-064 AC10` artifact count 偏少
- **状态**：open
- **内容**：MC 报告其 `backtest_select` pipeline 的简化路径会让 `SPEC-064` 的 aftermath research view artifact count 比预期偏少，触发 `AC10` 计数区间的偏移。HC 端 artifact 计数（`49`）已是当前 canonical 数据；本项追踪的是 MC 端简化的回填决策
- **HC 影响**：暂无直接代码影响；监控 MC 后续是否要求 HC 同步调整
- **当前归类**：MC-side housekeeping
- **来源**：`MC_Handoff_2026-04-24_v3.md`、`MC_Response_2026-04-25_v2.md` §4

### Q021 — `Q018 / SPEC-066` 的 aftermath 多槽位语义是否设错：应抓第二峰回落，而不是 back-to-back 连抓两次
- **状态**：resolved / closed（PM 2026-05-02 最终裁定：保留 SPEC-066，不开 SPEC-067；Phase 1-4 sizing-curve 全部完成）
- **历史编号**：HC 自 2026-04-20 起原记为 `Q020`；2026-04-25 PM 接受 MC 编号约定后改为 `Q021`，与 MC handoff / response 对齐
- **内容**：PM 在复盘 `2026-03` 的 double-spike 真实案例时指出，当前 `SPEC-066` 的 `cap=2 + B` 逻辑虽然成功捕捉了两笔 `IC_HV`（`2026-03-09` 与 `2026-03-10`），但这两笔是紧邻的 back-to-back 开仓，而不是“第一峰后的机会未完成、第二个峰值形成后再抓第二次回落”。若策略设计的真正意图是后者，那么 `Q018` 研究与 `SPEC-066` 的收益中，可能混入了语义错误的 alpha
- **关键问题**：需要区分三件事：
  1. `cap=2 + B` 的增量收益里，有多少来自同一峰后的紧邻 back-to-back `IC_HV`
  2. 有多少来自真正的 distinct-second-peak aftermath 机会
  3. 如果要求“第二笔必须对应新峰或至少满足 re-arm 语义”，当前 `SPEC-066` 的 `+$47K / Sharpe +0.02` 还剩多少
- **为什么这不是直接回滚**：目前这只是语义与归因问题，不是已证实的实现错误。`SPEC-066` 仍可能在总量上有效，只是研究目标可能定义得过宽。应先做归因研究，再决定是：
  - 保留 `SPEC-066`
  - 收紧为“distinct-second-peak only”
  - 或推翻并重做 aftermath 多槽位逻辑
- **建议最小 Phase 1**：
  - 将 `SPEC-066` 新增的 `IC_HV` 交易拆成：
    - 同峰 back-to-back
    - distinct-second-peak
    - 其他
  - 对比各自的 trade count / total PnL / avg / Sharpe / MaxDD 贡献
  - 同时构造一个对照变体：`single-slot + re-arm only after new peak`
- **2026-04-25 进展**：
  - Phase 1（信号层归因）完成：`doc/q021_phase1_attribution_2026-04-25.md` — 同峰 back-to-back 占 SPEC-066 增量 78% 笔数 / 88% 美元
  - Phase 2（全引擎 4 变体）完成：`doc/q021_phase2_full_engine_2026-04-25.md` — V3 (distinct-cluster only) 系统 -$9,200 vs V1 (SPEC-066)；max conc IC_HV V2=6 不可用；2026-03 双峰 case 增量仅 +$111
  - 1st Quant 初步建议 `(a) 保留 SPEC-066 close Q021`
  - 2nd Quant review (`tests/q021_2nd_quant_handoff_2026-04-25.md`) CHALLENGE：证据不足以 close；要求开 Phase 3 small pack（half-size 变体 + 2018-2026 切片 + BP gap 拆解）
  - PM 2026-04-25 决策：approve Phase 3，Q021 保持 open；cluster 阈值 sweep 推迟到 Phase 4 看 Phase 3 结果再定
  - Phase 3（V_A/V_B/V_C 三变体）完成：`doc/q021_phase3_half_size_2026-04-25.md` — half-size 否决，BP crowding 假设否决（非 IC_HV PnL 跨变体严格相同 $332,681），recent slice 排序一致；1st Quant 推荐回到 (a) 保留 SPEC-066
  - PM 反问 "V_A 是不是相当于 IC_HV 直接 2× size"，追加 V_D = aftermath 首笔 2× size + 双峰可两次入场
  - **V_D 全样本 +$431,673（V_A +$403,850 的 +6.9%），Sharpe 0.45 vs 0.42，MaxDD -$9,749 vs -$10,323（更优）**；非 IC_HV PnL 仍严格相同（无 portfolio interaction 副作用）；2026-03 case +$2,589 vs V_A +$1,184
  - V_D 代价：tail risk × 2（COVID 单笔 -$3,314 vs V_A -$1,657），BP-adjusted return -2.8%，MaxConc IC_HV 升至 3
  - 2nd Quant Round 2 review (`task/q021_2nd_quant_review_handoff_2.md`) CHALLENGE V_D：marginal $/BP-day = $3.37 < V_A baseline $4.85 → leverage drag 嫌疑；要求 sizing-curve study (V_E/V_J/V_H/V_G) + 永久标准指标包
- **2026-04-26 进展**（Phase 4）：
  - PM 决策：永久 standing rule — 所有未来 strategy/spec 比较必须含完整指标包（marginal $/BP-day、worst trade、disaster window、max BP%、concurrent 2× 天数、CVaR 5%）。已存为 memory `feedback_strategy_metrics_pack.md`
  - Phase 4 6 变体 sizing-curve study 完成：`doc/q021_phase4_sizing_curve_2026-04-26.md`、prototype `backtest/prototype/q021_phase4_sizing_curve.py`
  - **关键发现**：所有 sizing-up 变体 marginal $/BP-day 全部低于 V_A baseline $4.85 — V_G $3.83 / V_D $3.37 / V_J $2.98 / V_E $2.70。**整条 sizing curve 在 [1×, 2×] 区间无 smart-edge**，V_D 的 +6.9% PnL 是 leverage drag 而非 smarter rule
  - V_J (no-overlap rule, MaxBP 28%) 与 V_E (1.5× full overlap) PnL 几乎相等（+$10K），证实 V_D 多挣的 +$17K 主要来自 distinct-cluster 同时 2× leverage
  - V_G disaster cap 是最干净 doubler（disaster +$176 vs V_D -$748），但 marginal 仍 < baseline，**保留为 future spec 候选不晋升**
  - V_H split-entry 等价于 V_A − 1 trade，无 alpha；2nd Quant 的 1×+1× 假设否决
  - **更新推荐回到 (a) 保留 SPEC-066 close Q021**：sizing curve study 否决了 V_D 的 promote 候选地位；不开 SPEC-067
- **PM 2026-05-02 最终裁定**：approve。`Q021` 正式关闭，保留 `SPEC-066` 不变，不开 `SPEC-067`
- **当前归类**：resolved / closed
- **与新主线关系**：`Q021` 现在应被视为 **rule-layer evidence base / pilot input**，而不是未来 capital-allocation 研究的父容器。其结论仍然有效：`V_D` 不是更好的 canonical rule；若未来要研究 idle BP deployment，应在新问题下按组合级资本池重新建模
- **来源**：PM 对 `2026-03` 真实 double-spike case 的语义复盘，2026-04-20

### Q036 — Idle BP Deployment / Capital Allocation：在组合级资本池下，是否应将持久闲置 BP 受控部署，以合理提高账户级 ROE
- **状态**：shadow / hold（生产 posture 维持 shadow，但已绑定 revisit gate；详见 2026-05-09 Overlay-F revisit gate 条件）
- **2026-05-09 Overlay-F revisit gate condition（来自 R-20260509-02 Action A5）**：
  - **trigger**：主策略账户级 BP 利用率（time-weighted average，过去 60 个交易日）≥ **25% NLV**（softer trigger）或 ≥ **30% NLV**（harder trigger）
  - **rationale**：`/ES` 研究证明 BSH 类 hedge 是 scale-dependent；当前 Q036 Overlay-F 边际贡献 +0.074pp 低，**部分原因可能是**主策略 BP 利用率结构性偏低（SPEC-084 后 ~16% NLV），hedge cost 相对 theta 收入比例不经济
  - **不能直接类比 `/ES` BSH**：Overlay-F 是 sizing 而非 hedge cost，scale-dependence 的具体机制可能不同。所以这是 **revisit hypothesis**，不是 conclusion
  - **触发后应该做的研究**：在新 BP 利用率水平下，重新评估 Overlay-F 在 idle-BP 不再"持久且足够大"时的真实经济性。可能结论是"现在 idle BP 已经被 Q041 占用，Overlay-F 失去意义"——也可能是"在更高 BP 利用率下，Overlay-F 边际贡献从 +0.074pp 上升到有意义的水平"
  - **不要在 BP 25% 之前重开 Overlay-F 研究**：维持当前 shadow 观察 + 不升级 active 的状态
  - **触发监测责任**：Planner 在每月 PROJECT_STATUS 更新时检查主策略 BP 利用率；当 60 日均值首次穿越 25% 时通知 PM/Quant 评估
- **内容**：PM 已明确项目顶层 objective 重置为：**首要目标是合理最大化账户级 ROE**。这里的 “合理” 明确包含：控制风险暴露、避免大回撤、避免 margin stress / forced liquidation risk、避免坏 regime 下的隐藏集中。这个目标**不同于**单纯最大化 `Sharpe`、`PnL/BP-day`、或某条规则的语义纯度。由此产生一个新问题：当 baseline rule 与 baseline size 已经应用后，如果账户仍有显著 idle BP，是否应通过受控 capital-deployment overlay 来提高账户级 ROE
- **为什么这不是 `Q021` 继续延长**：`Q021` 已经足够回答 rule-layer 问题：“`V_D` / `V_G` 等 sizing-up 变体不应替代 `V_A SPEC-066` 成为新的 canonical rule”。但这并不自动回答 capital-allocation 问题：“若 baseline 长期留有可观 idle BP，而这些 BP 没有更优用法，是否应通过 overlay 部署出去？” 这两个问题的 objective function 不同，必须分开治理
- **当前 PM 边界**：
  - 顶层目标：合理最大化 account-level ROE
  - 当前 opportunity-cost baseline：`A`（若无更好用途，idle BP 可以保持闲置）
  - 建模层级：按**组合级资本池**建模，而不是单策略局部池
  - pilot use case：如需试点，可先用 `IC_HV aftermath`，但它只是试点，不预设为最终通用答案
- **需要回答的最小问题**：
  1. baseline 下 idle BP 是否真的“持久且足够大”，值得研究 overlay
  2. baseline + overlay 是否提高账户级 `ROE` / 年化 `ROE`
  3. incremental overlay 带来的 tail cost 是多少：`MaxDD`、`CVaR 5%`、disaster-window damage、peak BP%、margin-stress proxy、forced-liquidation proxy
  4. overlay 是否优于当前机会成本基线（目前为“保持 idle BP 不动”）
  5. 如果 overlay 消耗 BP，是否会 crowd out 更好的 baseline 交易
- **推荐研究 framing**：
  - 不再问：“Should `V_D` replace `V_A`?”
  - 改问：“Should the system add a controlled idle-BP deployment overlay, modeled at the combination-level capital pool, to improve reasonable account-level ROE?”
- **与 `Q021` 的关系**：
  - `Q021` 作为 rule-layer evidence base 保留
  - `IC_HV aftermath` 可作为 `Q036` 第一试点
  - 但 `Q036` 不应重新打开完整 `Q021` semantic tree，也不应把 overlay 结果误写成 `SPEC-066` 规则替换结论
- **下一步建议**：先交 Quant 做 feasibility-level 研究，不开 Spec，不改生产规则；待 Quant 给出 idle-BP persistence、ROE uplift、tail-cost、opportunity-cost 四件事的证据后，再决定是否需要 DRAFT Spec 或更高层 portfolio-allocation branch
- **2026-04-26 Quant framing 更新**：
  - 2nd Quant / Quant 当前共识：`Q036` 是 **capital-allocation** 问题，不是 `Q021` 的 rule-replacement 延长线
  - overlay 的边际经济门槛不是 `V_A` 的 `+$4.85 / BP-day`，而是 **idle baseline ≈ `$0 / BP-day`**
  - baseline BP 使用率初步判断约 `12.5%` 平均、`14%` 峰值，意味着 idle BP 结构性 `>= 86%`，因此“是否值得研究 overlay”这件事本身答案偏向 **yes**
  - 但目前仍**不能**把任何 sizing-up 变体当成已批准 overlay：因为 account-level `MaxDD`、`CVaR 5%`、disaster-window damage、margin-stress / forced-liquidation proxy 还没算
  - 也不能直接把 `Q021 Phase 4` 的数值搬过来当最终答案：一旦加入 idle-BP threshold gating，真实触发形状会变，PnL 和 tail 都会同时下降
- **当前 Quant 推荐**：
  - `Phase 1`（必须先做）：idle BP baseline measurement + regime-conditional distribution
  - `Phase 2`（仅在 Phase 1 支持时）：只测 3 个 conditional overlay 试点
    - `1.5x first-entry`
    - `2x disaster-cap`
    - `2x no-overlap`
    - 且全部要求 `idle BP threshold` 作为前置 gating
- **2026-04-26 Phase 1 实测完成**：
  - detail layer: `doc/q036_framing_and_feasibility_2026-04-26.md`
  - prototype: `backtest/prototype/q036_phase1_idle_bp_baseline.py`
  - **容量结论已答**：V_A SPEC-066 baseline 下，平均 BP 使用仅 `8.68%`，平均 idle BP `91.32%`；aftermath 日 `100%` 具备 `>= 70%` idle BP；disaster 期 idle 仍在 `86–97%`
  - 因此 `Q1`（idle BP 是否持久且足够大）答案是 **yes**
  - **新主风险发现**：aftermath 日已有 `>= 2` 个 short-gamma 仓位的比例约 `47%`（full）/ `54%`（recent），说明 overlay 的首要约束不是 deploy 容量，而是 short-gamma stacking
  - `Q2/Q3/Q4` 仍未答完：overlay 是否改善 account-level ROE、增加多少 tail cost、是否优于 idle baseline，仍需 Phase 2 才能回答
  - `Q5` 的 minimum pilot shortlist 维持不变：`Overlay-A 1.5x conditional` / `Overlay-B 2x + disaster cap` / `Overlay-C 2x + no-overlap`
- **PM 2026-04-26 决策**：批准 `Phase 2`
  - 研究范围保持窄：仅测 `Overlay-A` / `Overlay-B` / `Overlay-C`
  - `idle BP threshold gating` 继续作为所有变体的强前置门
  - 不开 `SPEC`
  - 不改生产
  - 不重开 `Q021` 语义争论
- **2026-04-26 Phase 2 完成**：
  - 三个试点都对 idle capital 给出正增量回报：
    - `Overlay-A`: `+6,780` total PnL，`+0.054pp` annualized ROE
    - `Overlay-B`: `+10,706`，`+0.088pp`
    - `Overlay-C`: `+9,364`，`+0.077pp`
  - 但三者都**还不够**支持进入 DRAFT overlay spec：
    - uplift 量级仅 `+0.05` 到 `+0.09` annualized ROE points
    - `CVaR 5%` 都从 `-4,309` 变差到 `-4,382`
    - peak system `BP%` 从 baseline `30%` 升到 `31% / 38% / 34%`
  - `Overlay-B` 的 disaster-window net 最干净（`+302`，与 baseline 持平），但 peak BP 最高
  - `Overlay-C` 的 stacking guardrail 最强（pre-existing `>= 2` short-gamma 环境命中率 `0%`），但回报略低、disaster net 不如 `B`
  - `Overlay-A` 基本可淘汰：回报最弱、disaster net 最差
  - crowd-out check 全部为 `OK`
  - idle-BP utilization 极低（仅消耗 baseline idle budget 的 `0.39%` 到 `0.46%`）
- **当前 Quant/Planner 推荐**：
  - `Q036` **不应 drop**
  - 但也**不应进入 DRAFT overlay spec discussion**
  - 如继续，只建议收缩到 `Overlay-B` 与 `Overlay-C`
- **2026-04-26 Phase 3/4 收缩更新**：
  - guardrail refinement 新增：
    - `Overlay-D_hybrid` = `Overlay-B + Overlay-C`
    - `Overlay-E_hyb80` = `Overlay-D + idle BP >= 80%`
  - 结果：`D/E` 证明 stacking 可以清零且保住 `B` 的 disaster-window net，但 uplift 被压到仅 `+0.046pp` annualized ROE；`E` 与 `D` 完全同值，说明 `80% idle gate` 在该局部是 inert
  - 再进一步的窄测试给出 **lead candidate**：
    - `Overlay-F_sglt2` = `2x` iff `idle BP >= 70%`、`VIX < 30`、且 `pre-existing short-gamma count < 2`
  - `Overlay-F` 结果：
    - total PnL `+412,855`
    - annualized ROE uplift `+0.074pp`
    - 比 `Overlay-D` 的 `+0.046pp` 明显更好
    - 接近 `Overlay-B` 的 `+0.088pp`
    - `SG>=2 = 0%`
    - disaster-window net `+301`
    - peak BP `34%`（低于 `Overlay-B` 的 `38%`）
  - 这意味着 `Q036` 首次出现了一个像样的折中点：**比 `B` 更干净，比 `D` 更不保守**
- **当前 Quant/Planner 推荐（最新）**：
  - `Q036` 仍然 **不应 drop**
  - 仍然 **不应进入 DRAFT overlay spec discussion**
  - 但如果继续，已不建议横向扩更多变体；应只围绕 `Overlay-F_sglt2` 做 very narrow confirmation：
    1. yearly attribution
    2. overlay-fire 分布（regime / VIX bucket / pre-existing short-gamma count）
    3. recent-era robustness (`2018+`)
- **PM 2026-04-26 决策（最新）**：
  - 批准继续，但只批准 `Overlay-F_sglt2` 的 final narrow confirmation
  - 不再横向扩新候选
  - 不回到 `Q021`
  - 不开启 spec discussion
  - 该轮完成后，应进入 PM decision-packet 阶段，而不是继续无界扩研究树
- **PM 2026-05-02 最终方向裁定**：
  - HC 接受 MC 侧更接近 `escalate / productization stack` 的方向
  - 这意味着：`Q036` 作为“是否继续朝产品化方向前进”的方向性问题已经收口
  - `SPEC-075 / SPEC-076` 在 HC 端不再因 canonical 分歧而 deferred；后续若推进，属于 adoption / prerequisite / implementation-planning 问题，而不是继续研究 `hold vs escalate`
  - 这**不等于**立即 productize，也**不等于**现在就开 DRAFT spec；它只表示 HC 不再把 MC 的路线当作需先争论的研究分歧
- **2026-05-03 补充**：
  - `sync/mc_to_hc/MC Response 2026-05-02_v2.md` §4 已提供 `SPEC-075 / SPEC-076` adoption 输入包，内容包括：
    - spec 全文位置
    - MC file list / patch scope
    - `overlay_f_mode` posture（`disabled / shadow / active`）
    - old runtime 影响面
    - 最小 regression / tieout 验证口径
  - 因此，`Q036` 这条线在 HC 侧当前**不再**处于“等 adoption 包”状态；剩余工作是本地化 adoption planning 与 staged rollout，而不是继续索要上游定义
- **2026-05-03 adoption-fit clarifier**：
  - Quant 当前 verdict：**needs one more Quant clarification pass**
  - 这不是重开 `Q036` 研究，也不是否定 MC adoption 包，而是要求 HC 在交给 Developer 前再把本地 acceptance / guardrail / evidence 边界写实
  - `SPEC-075` 应原样 adopt 的核心：
    - 仅 `IC_HV`
    - `idle_bp_pct >= 0.70`
    - `VIX < 30`
    - `short-gamma count < 2`
    - posture 仍为 `disabled -> shadow -> active`
  - HC 必须额外锁死的 guardrails：
    - **position-count** `short-gamma` productization 语义
    - live state 缺失 / stale 时 **fail closed**
    - disabled 下 recommendation payload 行为保持 inert
    - MC `web/html/spx_strat.html` → HC 本地真实路径映射必须写死
    - backtest / live portfolio-state builder 一致性检查
  - `SPEC-076` shadow 观察期最少必须看到：
    - trade / PnL 与 disabled 一致
    - shadow fires 与 active backtest fire count 同量级
    - 每条 would-fire 有完整 context（date / strategy / VIX / idle BP / SG count / mode / factor / rationale）
    - bot / dashboard 不把 shadow 误解释成 actual size-up
  - 该轮 clarification 现已完成，Developer 结论是：已经足够形成 **HC 本地 implementation-ready planning package**
- **2026-05-03 Developer planning update**：
  - 第一批正式文件面已固定：
    - new: `strategy/overlay.py`、`scripts/overlay_f_review_reports.py`、`doc/OVERLAY_F_REVIEW_PROTOCOL.md`、`tests/test_overlay_f_gate.py`、`tests/test_overlay_f_monitoring.py`
    - modified: `strategy/selector.py`、`backtest/engine.py`、`backtest/portfolio.py`、`web/templates/index.html`
  - 正式 file-map 已确认：
    - MC `web/html/spx_strat.html`
    - HC `web/templates/index.html`
  - 最稳妥实施顺序已固定：
    1. 075/076 共同准备 file-map / guardrails / validation package
    2. 先实现 `SPEC-075`
    3. 再实现 `SPEC-076`
    4. 统一执行 `disabled -> shadow -> active` 三层验证
  - old Air 影响面已明确：
    - `web`
    - `bot`
    - telemetry (`data/overlay_f_shadow.jsonl`, `data/overlay_f_alert_latest.txt`)
    - 最小部署需重启 `com.spxstrat.web` 与 `com.spxstrat.bot`
- **2026-05-03 Developer implementation update**：
  - `SPEC-075/076` 已在 HC 本地实现，当前 posture 固定为 `overlay_f_mode = "disabled"`
  - `SPEC-075` 已落地：
    - new: `strategy/overlay.py`
    - modified: `strategy/selector.py`, `backtest/engine.py`
    - tests: `tests/test_overlay_f_gate.py`
    - handoff: `task/SPEC-075_handoff.md`
  - `SPEC-076` 已落地：
    - modified: `strategy/overlay.py`, `strategy/selector.py`, `web/server.py`, `web/templates/index.html`
    - new: `scripts/overlay_f_review_reports.py`, `doc/OVERLAY_F_REVIEW_PROTOCOL.md`
    - tests: `tests/test_overlay_f_monitoring.py`
    - handoff: `task/SPEC-076_handoff.md`
  - 当前 guardrails / wiring 已覆盖：
    - `position-count` short-gamma 语义
    - live fail-closed
    - disabled payload inert
    - shared backtest/live portfolio-state & evaluation path
  - 本地验证已通过：
    - `tests.test_overlay_f_gate` + `tests.test_overlay_f_monitoring`: `10/10 PASS`
    - `tests.test_state_and_api` + `tests.test_bcd_filter` + `tests.test_bcd_stop` + `tests.test_engine_stop_wiring`: `36/36 PASS`
    - `compileall`: PASS
    - `main.py --dry-run`: PASS
    - 3y disabled parity spot: `57` trades / `$79,933.69`，与 tieout #3 disabled baseline 一致
  - 尚未执行：
    - commit / push
    - old Air pull
    - old Air `web` / `bot` restart
  - 当前下一步：
    - commit / push
    - old Air pull
    - old Air `web` / `bot` restart
    - first `shadow` flip
- **2026-05-03 PM 决策**：
  - PM 选择 `B`
  - 含义：本地 disabled implementation review 通过，批准进入 first old Air `shadow` rollout
  - 边界不变：
    - 仍按 `disabled -> shadow -> active`
    - 当前只批准 `shadow`
    - 不批准 `active`
  - 因此这条线的当前下一步不再是“是否批准 shadow”，而是 Developer 执行：
    - commit / push
    - old Air pull
    - 重启 `com.spxstrat.web` / `com.spxstrat.bot`
    - 启动 `shadow` 观察
- **2026-05-03 Developer shadow rollout update**：
  - first old Air `shadow` rollout 已完成
  - commit: `458231e` (`SPEC-075/076: roll Overlay-F to shadow`)
  - 已 push 到 `origin/main`
  - old Air 已执行：
    - pull latest `main`
    - `pip install -e .`
    - restart `com.spxstrat.web`
    - restart `com.spxstrat.bot`
  - 当前 runtime posture：
    - `overlay_f_mode = "shadow"`
    - 明确 **不是** `active`
  - 当前运行验证：
    - local web health `200`
    - `/api/recommendation` `200`
    - 当前 recommendation 正常返回 `Bull Put Spread`
    - no-side-effect check:
      - disabled strategy = `bull_put_spread`
      - shadow strategy = `bull_put_spread`
      - same strategy = `True`
      - shadow factor = `1.0`
      - shadow would_fire = `False`
      - shadow fail_closed = `False`
  - telemetry / artifacts 当前状态：
    - `data/` 可写
    - `data/overlay_f_shadow.jsonl` 与 `data/overlay_f_alert_latest.txt` 目前**尚不存在**
    - 这是预期行为：当前 writer 仅在 shadow/active 的 would-fire 事件出现时写盘
  - 已知限制：
    - 当前还没有真实 Overlay-F shadow event
    - 第一轮有意义的 review 需等待满足 gate 的 `IC_HV` 候选出现
- **当前归类**：resolved at direction level / shadow-live on old Air / observation pending meaningful would-fire samples
- **2026-04-26 Phase 5 final confirmation 完成**：
  - detail layer: `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
  - prototype: `backtest/prototype/q036_phase5_overlay_f_confirmation.py`
  - top line 维持：
    - baseline total PnL `+$403,850`
    - `Overlay-F` total PnL `+$412,855`
    - delta `+$9,005`
    - annualized ROE uplift `+0.074pp`
  - **yearly attribution**：
    - positive delta years `11 / 27`
    - negative delta years `4 / 27`
    - zero years `12 / 27`
    - 最大单一年份贡献为 `2022 +$1,896`，仅占 absolute yearly delta 的 `17.6%`
    - 去掉最强 `1` 年后仍有 `+$7,111`
    - 再去掉前 `2` 年（`2022`, `2008`）后仍有 `+$5,285`
    - 结论：uplift 是“稀疏但分散”的，不是靠 `1–2` 个年份撑起来
  - **overlay-fire distribution**：
    - fire count `23`
    - 全部发生在 `HIGH_VOL`
    - `VIX 20-25: 5`，`25-30: 18`
    - pre-existing short-gamma count：`0: 9`，`1: 14`，`>=2: 0`
    - mean idle BP at fire 约 `80.5%`
    - 结论：guardrail 实际触发分布与设计一致，没有在危险 stacking 区间偷偷加码
  - **recent-era robustness (`2018+`)**：
    - delta total PnL `+$4,395`
    - annualized ROE uplift `+0.040pp`
    - MaxDD 基本持平（`-9,405` vs `-9,392`）
    - `CVaR 5%` 持平（`-3,798` vs `-3,798`）
    - fire count `10`，且仍全部满足 `HIGH_VOL / SG < 2` 结构
    - 结论：recent era 仍为正，但 uplift 比全样本更薄
  - **最终研究判断**：
    - `Overlay-F_sglt2` 已完成 final narrow confirmation
    - 当前没有证据支持继续扩研究树
    - 但也还不足以自然推进到 `DRAFT overlay spec discussion`
    - 最合适的下一步已不是继续做更多 variant，而是进入 **PM decision packet**
- **2026-04-26 2nd Quant review 结果**：
  - 总 verdict：**CHALLENGE**
  - 已通过部分：framing 正确、`Overlay-F_sglt2` 作为 lead candidate 站得住、yearly attribution / disaster posture / recent slice 结论方向成立
  - 指出的不一致：`Overlay-F` gate 用 **family-deduplicated** count，framing / cleanliness metric 用 **position-count**
- **2026-04-26 3rd Quant review 结果**：
  - 总 verdict：**PASS** — ready for PM decision packet
  - 同意 framing 与 lead candidate；不应进 DRAFT spec discussion
  - 承认 recent-era uplift 偏薄、full-sample CVaR 未全面改善
- **2026-04-26 Quant Researcher 综合 verdict**：**`PASS WITH CAVEAT`**
  - 关键事实核对：Phase 5 §3 cleanliness claim (`SG>=2 = 0/23`) 是从 engine 的 **position-count** metric 算出来的（[q036_phase5_overlay_f_confirmation.py:67](backtest/prototype/q036_phase5_overlay_f_confirmation.py#L67) 读 `rows_by_date[d].short_gamma_count`，即 [engine.py:1073](backtest/engine.py#L1073) 写入的 position-count），不是从 gate 的 family-dedup metric 算出来的
  - 也就是说 cleanliness 报告用的是更严的 metric，本样本下两种口径 fire 分布完全一致 → 这是 **presentation issue, not numerical issue**
  - 2nd Quant CHALLENGE 在事实核对后偏严；3rd Quant PASS 不提语义分叉偏松；交集是 PASS WITH CAVEAT
  - 已执行最小动作：往 `task/q036_quant_review_packet_2026-04-26.md` 加 §11 Methodology Note (Post-Review Addendum)，披露 gate-vs-metric 口径分叉、本样本下 cleanliness claim 在 position-count 下也成立、productization 阶段必须把 gate 对齐到 position-count
  - **不**重跑 Phase 4 / Phase 5；**不**改 prototype；packet 可发 PM
- **PM 2026-04-26 决策（最新）**：
  - PM 选择 **`B`**
  - 含义：将 `Overlay-F_sglt2` 推进到更正式的 overlay 治理讨论 / 下一阶段 planning packet
  - **不**等于：
    - `DRAFT overlay spec discussion`
    - Developer implementation
    - live rollout
  - methodology caveat 继续保留：若未来真走向 productization，gate 必须对齐到 position-count short-gamma semantics
- **当前归类**：**formal overlay discussion approved**（含披露的 caveat；仍未进入 DRAFT spec）
- **2026-04-26 Quant 最新交付**：
  - 新增 PM-facing packet：`task/q036_pm_decision_packet_2026-04-26.md`
  - 该 packet 的 recommendation 不是 `escalate`，也不是 `drop`
  - Quant 明确建议：
    - **hold as research candidate, do not productize now**
  - 主要理由：
    - uplift 真实但偏薄（full `+0.074pp` annualized ROE；recent `+0.040pp`）
    - governance cleanliness 已足够避免 `drop`
    - 但没有 knockout 量级证据值得现在承担产品化复杂度
    - 若 `escalate`，仍需先做 gate 对齐重跑与一整层治理落地
    - 若 `hold`，主要代价是机会成本与需要明文记录 re-trigger 条件，防止 branch 变成隐性 `drop`
  - **因此当前最准确状态**：
    - 不是 `ready for DRAFT overlay spec discussion`
    - 不是 `drop`
    - 而是 **等待 PM 对 hold vs productize 的最终拍板**
- **来源**：`task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md`、PM 2026-04-26 对 objective reset 的明确回复

### Q037 — `profit_target = 0.60` broad rule audit：HC 已对齐默认值，AC3 量级差距现已解释到足够程度
- **状态**：open（de-escalated; explanation largely sufficient）
- **内容**：MC 将 `profit_target 0.50 -> 0.60` 作为 broad rule audit 的主发现，并通过 `SPEC-077` 落地。HC reproduction sprint 已完成 `SPEC-077` 代码对齐：`StrategyParams.profit_target = 0.60`、两处 `web/server.py` fallback override 同步、credit-side `params.stop_mult` wiring 已锁定。操作层面已与 MC production posture 对齐
- **HC 当前结论**：`SPEC-077` 已在 HC 端闭合为 `DONE`，但属于 **documented AC3 shortfall** 收口，而不是“全样本量级完全复现”。HC 的 full-sample rerun（`2007-01-01`，19.32y）只得到：
  - `Δ annualized ROE = +0.0856pp`
  - 远低于 MC `Q037 Phase 2A` 的 `+0.91 ~ +1.03pp`
  - 也低于 `SPEC-077 AC3` 的 `≥ +0.5pp` 阈值
- **已知候选原因**：
  1. compounding-baseline / annualized ROE 口径差异
  2. debit-side `-0.50` 硬编码（现已由 `SPEC-080` 正式闭合）
  3. HC `SPEC-056c` / MC `SPEC-054` 的永久 DIAGONAL 分歧
- **当前建议**：
  - 不回滚 `SPEC-077`
  - 不再阻塞 tieout / reproduction sprint
  - 但应将这条量级差距保留为一个明确 follow-up：在 `SPEC-080` 落地后做一次 attribution run，确认上面三条里哪一条是主因
- **2026-05-02 Quant 最新判断**：
  - 这不是 HC dashboard / `SPEC-078` 的计算 bug
  - metric 口径最多只能解释**一部分**：
    - 同一 HC full-sample ledger 下
    - `final_equity_compound / $100k` = `+0.0856pp`
    - `simple PnL / $100k / years` 也只能到 `+0.3504pp`
    - 若分母改成 `$50k`，simple 最多到 `+0.7009pp`
  - 因此若要解释 MC 的 `+0.91~+1.03pp`，必须再叠加：
    - 不同 denominator / ROE definition
    - 或不同 trade path
  - 本轮也基本排除了 `SPEC-080` / debit-side hardcode 作为当前主因：`bcd_stop_tightening_mode=disabled` 与 `active` 的 full-sample PT delta 完全相同
- **2026-05-03 Quant 更新**：
  - 现在可以确认两点：
    1. HC 不是 metric bug；`SPEC-078` 的 `final_equity_compound` 口径自洽，`+0.0856pp` 是该口径下的正确读数
    2. HC / MC 至少存在混合差异：metric 口径能把 HC 同一 ledger 的 uplift 从 `+0.0856pp` 放大到约 `+0.3504pp`，但仍到不了 MC 的 `+0.9088pp`
  - 当前最可能的剩余来源排序：
    1. sample window（MC `1999-01-01 → 2026-05-02` vs HC `2007-01-01 → today`）
    2. strategy/path mix（MC uplift 最大贡献在 `bull_put_spread`，而 HC 主正贡献来自 `Iron Condor / IC_HV`）
    3. exit reason timing（MC 的主机制是 `50pct_profit(_early)` 大量迁移到 `roll_21dte`）
  - `SPEC-080` / debit-side hardcode 现在基本不是主因：HC 已验证 `bcd_stop_tightening_mode=disabled` 与 `active` 的 full-sample PT delta 完全相同
- **当前最小下一步**：
  - 不再继续大范围 HC 盲跑
  - 若需要正式收口，只补一页窄的 attribution note：
    - HC displayed `+0.0856pp` 是 CAGR/final-equity 口径
    - same-ledger simple 口径约 `+0.3504pp`
    - 剩余到 MC `+0.9088pp` 主要由更长 sample window 与不同 path / strategy mix 解释
- **与 PM 的关系**：当前不需要 PM 再为 `SPEC-077` 是否上线拍板；需要 PM 后续决定的是，这个 ~10× 量级差距是否值得提升为独立调查问题（候选 `Q040`）
- **当前归类**：post-spec attribution open（但优先级已下降）
- **来源**：`task/SPEC-077.md`、`doc/baseline_2026-05-02/ac3_summary.json`、`sync/hc_to_mc/HC_return_2026-05-02.md`

### Q038 — `BCD comfortable top` + `BCD stop tightening` 研究弧（Path C）已在 HC 复现，并已进入 old Air shadow runtime
- **状态**：resolved（Path C reproduced; shadow deployed on old Air）
- **内容**：MC 将 `Q038` 定义为一条完整研究弧，而不只是两个彼此独立的小 spec。HC reproduction sprint 已完成：
  - `SPEC-079`：`BCD comfortable top` entry filter
  - `SPEC-080`：`BCD debit stop tightening`
  - 两者默认 toggle 都保持 `disabled`
- **HC reproduction 结果**：
  - `SPEC-079` / `SPEC-080` 都已 `DONE`
  - tieout #3 证明在 `disabled` 模式下对 trade flow **零回归**
  - 在 `PT=0.50 + both active` 的预览场景中，`2026-04-30` 的一笔 `BCD` 被 `risk_score=3` 正常拦截，证明 `SPEC-079` 逻辑已生效
- **PM / Developer 2026-05-02 结果**：
  - HC 已实际切到 `shadow`
  - old Air 已同步包含 `SPEC-079/080` 的代码并重启 `web + bot`
  - `bcd_comfort_filter_mode = "shadow"`
  - `bcd_stop_tightening_mode = "shadow"`
  - `GET /api/recommendation -> 200`，live recommendation path 正常
- **剩余含义**：
  - 后续重点转为 monitoring / observation
  - `SPEC-079` 的 shadow 现在可在 live path 上观察，日志目标为 `data/bcd_filter_shadow.jsonl`
  - `SPEC-080` 的 shadow 目前主要仍是 engine/backtest 层 wiring；old Air live path 暂不会自然产生对应的 live shadow stop 日志
  - 若未来还要扩到 `state-conditional stop` 等新方向，应以新 follow-up 形式管理，而不是把当前 shadow rollout 继续当作 open blocker
- **2026-05-03 Quant monitoring protocol**：
  - shadow 观察期的目标不是证明 alpha，而是验证：
    1. `SPEC-079` comfortable-top 条件在 live recommendation path 中是否按设计被识别
    2. shadow 是否只记录、不改变推荐、不阻断交易、不影响 bot / web
    3. 触发样本是否落在原设计想防的 BCD 风险区（低 `VIX`、从 `30d high` 回落、仍高于 `MA50`）
  - `SPEC-079` review 的最低字段：
    - `date`
    - `mode`
    - `vix`
    - `dist_30d_high_pct`
    - `ma_gap_pct`
    - `risk_score`
    - `would_block`
  - 核心判断不是“日志越多越好”，而是：
    - `would_block=true` 是否只出现在三条件全满时
    - 是否集中在预期 BCD 风险环境
    - 是否完全无 recommendation side-effect
  - `SPEC-080` 当前应明确写成：
    - **engine/backtest-observable shadow + live posture alignment**
    - 不应期待 old Air 自然产出丰富 live-side stop shadow event
  - 建议 cadence：
    - 最短 `4` 周，正常 `4–8` 周
    - 每周 fixed review 一次
    - BCD candidate 日 / 近阈值市场日做 event-driven quick check
  - 只有在观察期内：
    - 无 false positive
    - 无 runtime side-effect
    - 触发语义可解释
    - 样本足够可审查
    时，才值得让 PM 讨论 `active`
- **当前归类**：resolved for planning / in runtime shadow observation
- **来源**：`task/SPEC-079.md`、`task/SPEC-080.md`、`doc/tieout_3_2026-05-02/README.md`、`sync/hc_to_mc/HC_return_2026-05-02.md`

### Q039 — `IC regular` 残余 gap：更像 high-IVP `NORMAL IC` fallback / gate 差异，而非 slot blocking
- **状态**：resolved（attribution sufficient；post-SPEC-084 refresh 2026-05-09 确认 gap 不变，bp_target lift 与 selector 正交）
- **内容**：在 HC reproduction sprint 的 tieout #2 / #3 之后，HC↔MC 的主残余 gap 依然明显：
  - `PT=0.50` 模式下仍约 `+5` trades / `+$30k` 量级
  - 其中最大单项始终是 `IC regular`：
    - HC `13` 笔
    - MC `6` 笔
- **为什么它现在应从 candidate 升级为 open question**：
  - 在 `SPEC-074 / 077 / 078 / 079 / 080` 全部复现后，这个 gap 仍未消失
  - 因此它已不再只是“可能会被 reproduction 自动吸收的小尾差”
  - 而是一个会实质影响 HC↔MC 收敛度的正式研究问题
- **当前最可能根因**（按 HC assessment / tieout 结果综合）：
  1. `IVP` gate sensitivity（尤其 `ivp252 >= 55` 一类路径）
  2. trend / ATR persistence 默认值或触发时机差异
  3. HC `SPEC-056c` vs MC `SPEC-054` 的永久 Gate 1 分歧对 `BCD/IC` 分布的二次影响
- **2026-05-03 Quant 更新**：
  - MC 提供的 6 笔 `IC regular` ledger 支持当前判断：
    - 这更像 high-IVP `NORMAL IC` fallback / gate 差异
    - 而不是 slot blocking
  - 关键理由：
    - MC 6 笔中只有 2 笔与 HC 共有，HC-only 有 11 笔
    - HC 13 笔中已有 `9/13` 落在 `ivp252 >= 55`
    - `0/13` 落在 `50~65` 临界区
    - `0/13` 显示为已有同类 slot occupied
  - 这说明它并不是“55 附近轻微阈值抖动”问题，先做 `IVP` sweep 价值不高
- **当前建议**：
  - 不把它当作 reproduction bug
  - 也不立刻开 spec
  - 先作为正式 research question 保留，下一步只做一个 **mini attribution table**：
    - MC 6 笔：`entry date / 是否 HC 共有 / entry VIX / entry SPX / exit reason / PnL`
    - HC-only 11 笔：`entry date / ivp252 bucket (<30, [30,55), >=55) / trend state / slot occupied / HC route reason`
    - 结论桶：`high-IVP fallback/gate / low-IV bug candidate / MC-missing despite valid [30,55) / other`
  - 只有当 mini table 显示大量 HC-only 落在 `<30` 或 `[30,55)` 仍异常缺失时，才考虑升级
- **PM 2026-05-02 定位**：
  - 保持在研究位置
  - 当前不提升成更强的 parity-investigation 主线
- **与 Q020 的关系**：
  - `Q020` 当前仍是 MC-side housekeeping / `SPEC-064 AC10` artifact count 问题
  - `Q039` 则是 tieout #2/#3 之后留下的 **HC↔MC strategy-mix gap 主问题**
- **当前归类**：research — narrow attribution only
- **来源**：`task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md`、`doc/tieout_2_2026-05-02/README.md`、`doc/tieout_3_2026-05-02/README.md`、`sync/hc_to_mc/HC_return_2026-05-02.md`

### Q029 — research/live notional parity：engine `qty = 1` 与 selector `SizeTier` 不一致
- **状态**：resolved / closed（PM 2026-05-09 approved SPEC-072.1，Quant 同日实施 F8-F11，smoke tests pass）
- **2026-05-09 Quant Tier 1 结论（R-20260509-10）**：
  - **Engine 无 `qty=1` bug**：`backtest/engine.py:_position_contracts()` 已经按 `account × bp_target / bp_per_contract` 做 fractional sizing。MC 表述 "engine 用 1 SPX 模拟" 是 reporting-layer 单位口径解读问题，不是 engine 计算 bug
  - **不需要 engine 重构**
  - **SPEC-072 frontend dual-scale 仅覆盖 4/8 主 template**：`index.html`/`backtest.html`/`margin.html`/`spx.html` 已 covered；`matrix.html`/`portfolio_backtest.html` 未 covered；CSV 导出无 scale 列；manually-authored docs 无 governance 强制
  - **影响范围（3y 实测）**：HIGH_VOL 15.8% trades，$7,914 / 3y ≈ 3% PnL。19y 估算 ~3-5% PnL；但在 grinding decline / aftermath 研究中权重显著更高
- **SPEC-072.1 patch（DRAFT）**：Fast Path ~1h work，4 个改动：
  - F8 — `matrix.html` 引入 spec072_helpers + HV cell avg_pnl 双值
  - F9 — `portfolio_backtest.html` 引入 spec072_helpers + HV row 双值
  - F10 — CSV 导出加三列 `live_scale_factor` / `live_scaled_exit_pnl_usd` / `live_scaled_total_bp`
  - F11 — `QUANT_RESEARCHER.md` + `REVIEW_TEMPLATE.md §6.1.7` governance 条款
- **历史背景**：MC 2026-04-24 `5-dim parity audit` 提出此 parity issue，缓解方案为 Q033 Option B+E（reporting dual columns）；SPEC-072 完成 4 个主 template；Q029 Tier 1 (HC 2026-05-09) 发现剩余 4 处缺口
- **Q029 closure 已完成**：SPEC-072.1 状态 DONE（2026-05-09）；F8 matrix.html dual-scale + F9 portfolio_backtest.html helper inject + F10 CSV 三列 + F11 QUANT_RESEARCHER + REVIEW_TEMPLATE governance 全部落地
- **PM live smoke 待办**（未 block closure）：在 `/matrix` 与 `/portfolio_backtest` 浏览器实测看 HV cell 双值；下次 export CSV 验证三列在
- **来源**：`MC_Handoff_2026-04-24_v3.md`、Q029 Tier 1 evaluation `R-20260509-10`、`task/SPEC-072.md`、`task/SPEC-072.1.md`

### Q041 — Large-Cap Equity Option Income Overlay：是否值得作为独立 equity-income sleeve 进入正式研究池
- **状态**：**Tier 1 SPX CSP 正式淘汰（2026-05-10 Q055 竞争结论）**；V1 veto 失败（2020 worst -17.99% NLV > -15%），且 Tier 2 主指标全负于 /ES V2c。**Tier 2 GOOGL/AMZN CSP 独立继续（不受影响）。Tier 3 COST/JPM IC observe-only 不受影响**
- **内容**：Quant 已完成正式理论评估。结论不是 `drop`，也不是近端 spec，而是：这份候选材料里存在三个可被机构化研究的模块，但当前项目在数据层面还没有通过 `Gate 0`。因此它现在应被视为一个**已进入研究池、但尚未获准分配建模带宽**的独立题目
- **已确认可研究的模块**：
  1. `mega-cap covered call overlay`
  2. `cash-secured put on a strict high-quality whitelist`
  3. `defined-risk earnings short-vol`（credit spread / protected structure，而非裸卖）
- **明确排除项**：
  - naked earnings short option
  - `RSI 99` reversal discretionary short
  - 单名股票极端事件押反转
  - 社媒式“月收租金额”口径
- **机构化定义方向**：
  - 这条线应被定义为独立的 `equity-income sleeve`
  - 不应并入当前 `SPX` 主策略代码主线
  - 与 `Q036` 的关系主要是未来账户级 capital-allocation 竞争，而不是当前研究阶段的直接依赖
- **当前最高优先级不是建模，而是 Gate 0**：
  - HC 是否能获得历史 per-name 个股期权数据
  - 最低要求：大致 `2004–2026`、覆盖 whitelist、含 options OHLC / implied vol / OI 深度
  - 若 Gate 0 FAIL：`Q041` 暂缓，不进入 Phase 1
  - 若 Gate 0 PASS：最小 Phase 1 应先做
    - `BXM / PUT / WRIT` benchmark analysis
    - covered-call-only whitelist pilot
- **2026-05-03 Gate 0 scaffold update**：
  - Quant 已完成 forward-collection scaffold：
    - `research/q041/init.py`
    - `research/q041/whitelist.py`
    - `research/q041/collect_chains.py`
    - `~/Library/LaunchAgents/com.spxstrat.q041_collect.plist`
    - `.gitignore` 已加入 `data/q041_chains/`
    - `pyproject.toml` 已加入 `pyarrow>=15`
  - 当前围栏保持干净：
    - 未触碰 `engine.py / strategy/ / signals/ / web/ / notify/ / schwab/*`
    - 仅 read-only reuse `schwab.auth` + `schwab.client._parse_chain_response / _normalize_quote`
    - 写盘只在 `data/q041_chains/{date}/`
  - Smoke test（`AAPL --force`）已通过：
    - `2462` 行（`1231 calls + 1231 puts`）
    - `20` 个到期日（`2026-05-04 → 2027-03-19`）
    - 输出 `AAPL.parquet + _underlying.parquet + _summary.json`
    - 体量估算约 `700 KB/day` 全白名单、约 `175 MB/year`
  - 但这**不等于** Gate 0 已通过：
    - 当前只说明 forward collection 可行
    - 历史 per-name options 覆盖（`~2004–2026`）仍未确认
  - 当前下一步：
    - 手动执行 `launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_collect.plist`
    - 在首个 weekday run 后检查：
      - `logs/q041_collect.log`
      - `logs/q041_collect.out.log`
      - `logs/q041_collect.err.log`
      - `data/q041_chains/YYYY-MM-DD/` 是否拿到 `10` 个 symbol parquet + `_summary.json`
- **2026-05-03 Gate 0 collector refinement update**：
  - `SPX` 问题已定位并修复：
    - 根因：Schwab API gateway body-buffer overflow；`$SPX` 行权价过密（`5-point` increment）× 大 `DTE` 窗口导致响应体超限
    - 修复：`$SPX` 单独使用 `strikeCount=100`、`DTE=180` 天
    - 结果：覆盖约 `40` 个到期日、`4159` calls，足够服务当前主策略链数据积累
  - `/ES` 已从该 whitelist 路径移除：
    - 原因：Schwab `/marketdata/v1/chains` 不支持期货期权，返回 `400 Bad Request`
    - 结论：`/ES` futures options 需要独立数据源（如 CME DataSuite 或第三方）
  - 当前 forward-collection whitelist 已更新为 `12` 个标的：
    - `10` 个 large-cap 名称
    - `SPX`
    - `QQQ`
  - 当前日规模估算：
    - 约 `45K` 行
    - 约 `800KB` parquet / day
  - 当前下一步：
    - 仍是等待首次 weekday `16:30 ET` 自动触发
    - 首跑后重点确认：
      - `10` 个个股 + `SPX` + `QQQ` 是否都成功落盘
      - `BRK/B` → `BRK_B.parquet` 是否工作正常
      - `logs/q041_collect*.log` 是否无 symbol-level 异常
  - **2026-05-03 old Air deployment update**：
    - old Air 已对齐到 `origin/main @ a112d33`
    - `pyarrow-24.0.0` 已安装
    - `Q041` collector 已作为独立 launchd job 部署：
      - `~/Library/LaunchAgents/com.spxstrat.q041_collect.plist`
      - command: `/Users/macbook/SPX_strat/venv/bin/python -m research.q041.collect_chains`
    - `Q036` posture 未变：
      - 仍是 `overlay_f_mode = "shadow"`
      - 未进入 `active`
    - `web` / `bot` 本轮未重启，原因是：
      - 本次仅涉及 research scaffold / `pyarrow` / attribution notes
      - 不涉及新的 live recommendation path 代码变更
      - 当前 runtime health 仍正常
    - manual smoke 已通过：
      - `python -m research.q041.collect_chains --symbols AAPL --force --verbose`
      - 产出 `2462` rows
      - 成功写入：
        - `data/q041_chains/2026-05-03/AAPL.parquet`
        - `data/q041_chains/2026-05-03/_underlying.parquet`
        - `data/q041_chains/2026-05-03/_summary.json`
    - launchd smoke 已通过：
      - job executed under launchd
      - runs = `1`
      - last exit code = `0`
      - weekend gate 生效，`non-trading day (Sun) — skipping`
    - 当前最重要的下一检查点：
      - 首个 weekday `16:30 ET` 自动 run
      - `12` 个 whitelist symbol 是否全部落盘
      - `BRK/B -> BRK_B.parquet`
      - `logs/q041_collect*.log` 是否无 symbol-level 错误
- **2026-05-03 Massive historical-source update**：
    - PM 已开通 `Massive.com` `Options Developer` 账户
    - 定位：一次性批量下载历史数据后取消订阅
    - 当前历史规格：
      - 深度约 `4` 年（`~2022-05` 起）
      - 覆盖美国期权市场（经 `OPRA`）
      - Developer 计划下历史可访问部分实质上是 `day_aggs_v1` S3 flat files：`OHLCV + volume + transactions`
      - 不含历史 bid/ask quotes（该项需更高计划）
    - symbol 覆盖预验证：
      - 白名单 `17/17` symbol reference PASS
      - `SPXW` PASS
      - `BRK/B` PASS
      - OHLCV aggregates PASS
    - 当前执行路径：
      - Massive 负责历史批量下载（约 `2022–2026`）
      - Schwab forward collector 自 `2026-05-03` 起继续积累新增链数据
      - 两者在 Phase 1 中拼接使用
    - 关键约束：
      - 这不是原始设想的 `2004–2026` 全历史深度
      - `/ES` 仍不在该数据路径中
      - 若未来需要历史 bid/ask 或更长深度，仍可能需要补数据源
    - 当前 Gate 0 结论：
      - **PASS WITH CONSTRAINTS**
      - 可以开始历史下载和本地转换
      - 但未来所有 Phase 1 结果都必须显式注明数据窗口与 quote-depth 约束
- **2026-05-03 data-alignment note update**：
  - `doc/q041_data_alignment_note_2026-05-03.md` 已写入，当前总判断是：
    - **`ready to collect and align`**
    - 但 Phase 1 前必须先完成 Massive 历史段与 Schwab 近期段的 schema / overlap / tolerance 对齐
  - 当前正式拼接方向：
    - Massive = 历史 canonical
    - Schwab = 近期 canonical
    - overlap = 校验窗口，不双重入库
  - 当前最关键的新约束不是 symbol mapping，而是字段缺口：
    - Massive `day_aggs` 历史段 **无 Greeks / IV / OI**
    - Schwab 当前 forward parquet **也没有 IV**
    - 这意味着“hybrid path 可拼接”并不等于“Phase 1 已具备完整 IV-sensitive 建模数据”
  - 当前认定：
    - 历史段可先用 OHLCV / close / volume 进入受限研究
    - 但若后续建模依赖历史 delta / IV / OI，则仍需额外数据补充或明确降级方案
  - 当前建议并行动作：
    - Developer：执行 Massive 历史批量下载与本地转换（见 `SPEC-081`）
    - Quant：确认 Schwab raw chain response 中是否存在 IV / full Greeks 字段但当前未被采集（见 `SPEC-082`）
    - 在这两步完成前：
      - `Q041` 仍然不是 Phase 1 回测开跑状态
      - 更准确说是：**Gate 0 pass with constraints / alignment phase**
  - **2026-05-03 overlap validation protocol update**：
    - `doc/q041_overlap_validation_protocol_2026-05-03.md` 已写入
    - Quant 当前正式建议不是“边下载边零散 spot check”，而是：
      - **20 个交易日正式校验**
      - **10 天修正与复验缓冲**
    - 不选 `10–15` 个交易日：
      - 不足以覆盖月度 rollover 边界
      - 也不足以覆盖较低频标的（如 `ASML / TSM / PANW`）
    - 不直接把 `30` 天全部用于纯观察：
      - 需要留出后 `10` 天处理校验中暴露出的 schema / field / naming 问题
  - 当前 overlap 期间最关键的持续指标是：
    - `symbol / expiry / strike` 命中率
      - `price` 偏差
      - `volume` rank correlation
      - 以及 `IV / Greeks / OI` 完整率与 `SPX / SPXW`、`BRK/B` 稳定性
    - Quant 已明确把差异分成两类：
      - **可吸收**：
        - volume 点值偏差（用 rank 不用点值）
        - `price <= 2%`
        - Massive 历史段 `Greeks / IV / OI = null`
        - 稀疏标的零行日
        - Massive `T+1` 延迟
      - **阻止 stitching**：
        - `symbol match < 85%`
        - `price > 5%`
        - `expiry / strike` key 解析错误
        - `IV` 单位混淆未修正
        - `SPX / SPXW` 行数偏差 `> 20%`
    - 修正顺序也已固定：
      - `symbol normalization`
      - `date / timestamp`
      - `price field mapping`
      - `IV` 单位口径
      - `missingness handling`
      - `canonical source priority`
    - 30 天结束时，PM 的唯一判断依据应是：
      - **逐标的 Reconciliation Report / Table**
      - 所有 checklist 条件全部通过，Phase 1 才可入场
    - 当前最合理的节奏：
      - `SPEC-081/082` 产物一旦可用，立即启动 overlap 计时
      - 目标在 `2026-05-30` 左右提交 Reconciliation Report 给 PM
  - **2026-05-03 SPEC-082 implementation update**：
    - Developer 已本地实现 `SPEC-082`：
      - `schwab/client.py` 的 `_parse_chain_response` 现在保留：
        - `iv`
        - full Greeks
        - `expiry_type`
        - `open/high/low/close`
        - `last`
      - `research/q041/collect_chains.py` 已把这些列追加到 forward parquet schema
      - 本地 readback 已确认 `AAPL` / `SPX` parquet 中存在新增列
    - 当前实现层面是成功的，但 live-data validation **尚未完全通过**：
      - `iv` 原始值出现：
        - `iv_min = -999.0`
        - `iv_max = 629.206`
      - `expiry_type` 在 `AAPL` 上返回的是 `['S', 'W']`，不是原先预期的 `['M', 'W']`
    - 当前最合理解释不是“实现失败”，而是：
      - Schwab 原始字段语义仍需 Quant 解释
      - `-999` 很可能是缺失 / sentinel
      - `S/W/M` 的含义需要按 Schwab 语义重新定义，而不是按原假设硬套
    - 因此：
      - `SPEC-082` 可以视为 **implemented locally**
  - **2026-05-03 D1 Data Sanity update**：
    - `doc/q041_d1_data_sanity_report_2026-05-03.md` 已写入，结论为 **PASS**
    - 历史 Massive parquet 当前已满足进入 `D2 Benchmark Replication` 的最低质量门槛：
      - `17/17` 标的覆盖完整
      - 约 `1,000` 交易日窗口整体可用
      - `0` null close
      - `0` negative close
      - `0` OHLC 顺序违规
    - 当前已识别并固定的异常/边界：
      - `SPX` 有 `3` 个节假日异常（`Memorial Day / Juneteenth / July 4`）→ 过滤规则 `F2`
      - stale price 比例约 `0.78%–2.60%`，其中约 `65%` 为 penny 期权（`close <= $0.05`）→ 过滤规则 `F1`
      - `AMZN 2025-10-31` 出现单日 `37` 行、仅 `0-DTE` 合约的稀疏异常，已记录但不阻塞回测
    - 当前历史 IV / Greeks 的结论也更清楚了：
      - 在目标流动性区域，`BS` 反推 `IV` 样本有效率约 `92.8%`
      - 当前观测范围约 `18%–76%`
      - 无 `>200%` 异常值
      - delta 单调性 PASS
      - put-call parity 误差 `< 2%` PASS
    - 当前已固定的 D3/D4 前置过滤规则：
      - `F1`: `close > 0.10`（或至少 `> 0.05`）以排除 penny/stale 噪音
      - `F2`: 用官方 US 市场日历排除已识别节假日
      - `F3`: `dte >= 7`
      - `F4`: `|moneyness| <= 30%`（IV 计算域）
    - Planner 含义：
      - `Q041` 仍保持 **dual-source overlap validation** 主线不变
      - 但 `Phase 1 / D1` 已完成，不再是 `D1-ready`
      - 当前可以正式进入 **`D2 Benchmark Replication`**
  - **2026-05-04 D2 Benchmark Replication update**：
    - `doc/q041_d2_benchmark_replication_2026-05-04.md` 已写入，结论为 **PASS**
    - 当前 benchmark 复现精度已经足以作为 D3 比较基线：
      - 逐月相关系数 `0.9715`
      - MAE `0.43% / cycle`
      - `4` 年累计误差仅 `-1.24%`
    - 当前含义不是“BXM 完美复刻”，而是：
      - 数据管线
      - ATM 选择
      - 基本 P&L 核算
      已经验证到足以支持 D3 模块比较
    - 当前固定下来的 D3 比较基线：
      - `BXM` 官方 Sharpe：`1.23`
      - `BXM` 复现 Sharpe：`1.22`
      - `BXM` 复现 Sharpe（`3%` 滑点）：`1.14`
      - `ATM CSP` Sharpe：`0.81`
      - `ATM CSP` Sharpe（`3%` 滑点）：`0.73`
    - 当前样本窗口下的结构性结论：
      - `BXM` 在强牛市主导窗口中每年均落后 `SPX` 绝对回报
      - 但 `Sharpe` 更高、回撤更浅
      - `ATM CSP` 显示更稳定的 premium-harvest 轮廓：
        - 胜率 `76.6%`
        - 年化 `BP-day ROE` 约 `+4.15%`（无滑点）
    - 当前已固定的 D3 目标门槛：
      - Covered Call / Module A：
        - `Sharpe >= 1.33`（较官方 `BXM` 基线 `+0.10`）
      - CSP / Module B：
        - `Sharpe >= 0.83`
        - 年化 `BP-day ROE >= 4.0%`
    - Planner 含义：
      - `Q041` 现在已经从 **`D2-ready`** 推进到 **`D2 PASS / D3-ready`**
      - 下一步应启动 `D3 Module A/B`
      - 同时保持 overlap validation 独立继续，不与 D3 比较基线混淆
  - **2026-05-04 Phase 2 planner-context update**：
    - `task/q041_phase2_planner_context.md` 已写入，可作为 `Q041 Phase 2` 的单一短版规划入口
    - 当前文档用途不是替代原始研究报告，而是：
      - 用一页快速重建 D1 / D2 / D3 / D4 结论
      - 固定当前 production-candidate shortlist
      - 明确列出不应重复回测的排除项
      - 把剩余工作按 `P0 / P1 / P2` 收敛为直接可排队的任务
    - 当前已固定的 Phase 2 candidate shortlist：
      - `SPX CSP Δ0.20 DTE30`
      - `GOOGL CSP Δ0.20 DTE21`
      - `AMZN CSP Δ0.25 DTE21`
      - `COST` earnings iron condor (`T-3`, `1.0x`)
      - `JPM` earnings iron condor (`T-3`, `1.0x`)
    - 当前已固定的不应重复测试项包括：
      - `META` earnings IC
      - `JPM CSP`
      - 全部 `DTE21 SPX CC/CSP`
      - earnings put spread
      - `AMZN/MSFT` earnings IC
    - 当前最关键的 Phase 2 任务顺序：
      - `P0-1`：`SPX DTE45` overlap-corrected rerun
      - `P0-2`：`COST/JPM` 财报样本延伸
      - `P1-1`：IVR entry filter
      - `P1-2`：`GOOGL/AMZN CSP` 更长历史验证
    - Planner 含义：
      - 后续 `Q041 Phase 2` 路由默认先读这份 context
      - 只有在需要细节或复核时再回到 D3 / D4 全文
      - 但 `Q041` 数据口径仍处在 **alignment / semantic cleanup** 阶段
      - 在 Quant 对 IV / `expiry_type` 做完语义确认前，不应把这些字段直接当作 Phase 1 canonical 输入
  - **2026-05-04 Phase 2 P0-1 overlap-artifact triage**：
    - Quant 已完成 `P0-1` 分析，当前总判断是：
      - **SPX DTE45 CC/CSP 的高 Sharpe 几乎可以确定是 overlap artifact**
      - 当前数字不可直接用于生产候选判断，必须重跑
    - overlap 来源已明确：
      - 当前 D3 的 roll 逻辑是“每月 3rd Friday 进一个 cycle”
      - 但 `DTE45` 持仓约 `45` 天，而月度 roll 间距约 `28–35` 天
      - 因此相邻 cycle 会形成约 `15` 天重叠
      - 本质上等价于在未显式建模的情况下使用了约 `1.5x` 的隐式资本占用 / 杠杆
    - Quant 当前对指标污染的排序是：
      - 最严重：`BP-day ROE`
      - 严重：`cumulative / annualized return`、`Sharpe`
      - 中等：组合层面的 `MaxDD / CVaR`
      - 基本不受影响：`win rate`
    - 当前唯一推荐的 overlap-corrected rerun 规则：
      - **只有在前一个 DTE45 cycle 已完全到期时，才允许进入新的 cycle**
      - 若当月 3rd Friday 仍早于前一 cycle 到期日，则跳过该月
      - 预期有效样本数将从约 `46` 降到约 `23–24`
    - 当前最小必要重跑范围已固定为：
      - `SPX CC/CSP × Δ0.20 / 0.25 / 0.30`
      - 共 `6` 个 DTE45 组合
      - 不扩大到 `DTE21 / DTE30`、个股、或 Module C
    - 当前验收口径：
      - `CC`：
        - `Sharpe >= 1.33` 且 `MaxDD <= -8.96%` → 保留为正式候选
        - `Sharpe 1.00–1.32` → 降级为观察项
        - `Sharpe < 1.00` 或 `MaxDD > -8.96%` → 直接淘汰
      - `CSP`：
        - `Sharpe >= 0.83` 且 `BP-day ROE >= 4.0%` → 保留为正式候选
        - `Sharpe 0.70–0.82` → 降级为观察项
        - `Sharpe < 0.70` → 直接淘汰
      - 附加规则：
        - 若 overlap 修正后 `N < 20`，则结论自动降级为观察项
    - Planner 含义：
      - `DTE45` 当前不能进入生产 shortlist
      - `P0-1` 现在是一个必须先完成的 fast-path 原型 rerun
      - 推荐交付物是短 note：
        - `doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md`
  - **2026-05-04 Phase 2 P0-1 completion update**：
    - Quant 已完成 overlap-corrected rerun，当前最终结论是：
      - **`SPX CC DTE45`：淘汰**
      - **`SPX CSP DTE45`：降级为观察项**
    - 当前核心数字（采用 Align A / B 平均作为保守估计）：
      - `CC Δ0.20 / 0.25 / 0.30 DTE45`
        - Sharpe 约 `1.19 / 1.23 / 1.25`
        - MaxDD 约 `-15%`
        - 对照门槛 `Sharpe >= 1.33` 且 `MaxDD <= -8.96%`
        - 结论：**全部失败，直接淘汰**
      - `CSP Δ0.20 / 0.25 / 0.30 DTE45`
        - 平均 Sharpe 约 `1.57 / 1.35 / 1.34`
        - 形式上高于 `0.83`
        - 但对齐高度敏感：
          - 例如 `Δ0.20` 的 `Align A = 3.22`、`Align B = -0.08`
        - 结论：**均值通过，但稳定性不足，统一降级为观察项**
    - 当前最关键的风险解释已固定：
      - `2025-04` 关税崩盘 cycle 是决定性事件
      - 单一尾部 cycle 足以把全年 `CSP DTE45` 从强正 Sharpe 打到近零
      - 这说明此前高 Sharpe 不是稳健生产优势，而是高度依赖对齐时机
    - Planner 含义：
      - `P0-1` 已可视为 **resolved**
      - `SPX DTE45 CC/CSP` 均不进入 Phase 2 正式生产候选
      - 生产 shortlist **保持不变**：
        - `SPX CSP Δ0.20 DTE30`
        - `GOOGL CSP Δ0.20 DTE21`
        - `COST/JPM` earnings iron condor (`T-3`, `1.0x`)
      - `Q041 Phase 2` 下一主线前移为：
        - `P0-2`：`COST/JPM` 财报历史延伸
        - 其后才是 `P1-1 IVR filter` 与 `P1-2 GOOGL/AMZN` 更长历史验证
  - **2026-05-04 CC DTE45 benchmark-relative read**：
    - Quant 进一步把修正后的 `CC DTE45` 拿去和 `D2` 的 `BXM / SPX buy-and-hold` 基线做了同窗口对比（`2022-05-20 → 2026-04-17`，`3%` 滑点）
    - 当前结论更强了：
      - `CC DTE45` 不只是“没通过内部 Phase 2 门槛”
      - 它在这个窗口里对两个主流对手都**没有竞争力**
    - 对 `BXM`：
      - 修正后 `CC DTE45` 累计回报约 `+47% ~ +52%`
      - `BXM` 约 `+46%`
      - 表面上累计回报略高
      - 但 `CC DTE45` 的 `MaxDD ≈ -15%`，明显差于 `BXM ≈ -9%`
      - `Sharpe 1.19–1.25` 也没有形成稳定、干净的优势
    - 对 `SPX buy-and-hold`：
      - 修正后 `CC DTE45` 累计回报远低于 `buy-and-hold +82.7%`
      - 同时回撤还更深（`~ -15%` vs `-12.2%`）
      - 也就是说：
        - 没换来真正的下行保护
        - 却丢掉了大量上行
    - 当前最合理的结构性解释是：
      - `OTM covered call` 收的 premium 不足以显著缓冲下跌
      - 但牛市里仍会因为 call 被打到而失去大量上涨段
      - overlap 版之前“看起来很好”的主要原因，仍然是隐式资本效率被高估
    - Planner 含义：
      - `CC DTE45` 的淘汰结论现在不只是内部阈值判断
      - 也是一个 **benchmark-relative fail**
      - 后续若要解释为什么 `CC DTE45` 被移出候选池，应优先引用这一层补充证据
  - **2026-05-03 SPEC-081 / 082 review closure update**：
    - Quant 已 review 两个 spec，当前结论：
      - `SPEC-081` = **PASS / DONE**
      - `SPEC-082` = **PASS / DONE**
    - `SPEC-082` 的 code path 被确认是对的；先前的 AC3 / AC4 不通过，不是实现 bug，而是 spec 假设错了
    - Quant 已通过 Fast Path 执行最小清洗：
      - `collect_chains.py` 中对 Schwab `iv <= 0`（含 `-999.0` sentinel）改为 `null`
    - Schwab `expiry_type` 的正式口径现改为：
      - `W = Weekly`
      - `S = Standard monthly`
      - `Q = Quarterly`
      - `M = End-of-month`（少见）
    - 因此后续：
      - overlap validation protocol
      - reconciliation scripts
      - summary/report templates
      都应使用 `S` 来识别常规月度到期，而不再沿用早先的 `M/W` 假设
    - 这也意味着：
      - `Q041` 不再处于“collector / schema build-out”主状态
      - 当前正式进入 **overlap validation** 阶段
      - 剩余 blocker 是 reconciliation，不是 `SPEC-081/082` 实现能力
  - **2026-05-03 dual-source conclusion update**：
    - 当前最终数据口径已进一步收束为：
      - **历史段（`2022–2026`）**
        - `OHLCV`：✅ 来自 Massive flat files
        - `Greeks / IV / OI`：❌ 历史不可用，且 Massive Developer 计划无法回填
      - **近期段（从现在起）**
        - `OHLCV`：✅
        - `Greeks / IV / OI`：✅ 可通过每日 Massive snapshot 或 Schwab forward 逐日积累
    - 特别说明：
      - `open_interest` 是 end-of-day snapshot 值
      - 这意味着从今天起可以每天积累 `OI` 历史
      - 但 `2022–2026` 的历史 `OI` 仍无法回填
    - 因此：
      - 原 `alignment note` 与 `overlap protocol` 结论仍成立
      - 无需因“当前 snapshot 可得”而回头改写历史段约束
    - 关于历史 `Greeks / IV`：
      - Quant 现确认 `BS / BAW` 反推在技术上可行
      - 对流动性较好、`ATM ±20%`、中等 `DTE` 合约可信度较高
      - 对 deep `ITM/OTM`、零成交、stale close 合约不可靠
    - 但当前 recommendation 是：
      - **hold**
      - 先完成 overlap validation
  - **2026-05-04 overlap validation first formal M1–M10 read**：
    - Quant 当前一句话 verdict：
      - **mixed but acceptable**
    - 当前两侧落盘状态是干净的：
      - Massive historical `17/17` parquet 全在，无空文件
      - Schwab forward `17/17` symbol parquet 全在，并带 `_summary.json` / `_underlying.parquet`
    - 当前真实可比较 session 应统一按：
      - **`2026-05-01`**
      - 解释：forward 目录日期虽是 `2026-05-03`，但 `_underlying.parquet` 的 `quote_time` 对应 `2026-05-01` 收盘后
    - 当前 raw full-chain 指标与可比较 subset 指标必须分开读：
      - raw contract-key match 约 `49%`
      - 这主要反映 **Schwab full quoted chain** vs **Massive traded-only-like universe** 的分母差异
      - 真正有交易 / 有持仓意义的子集已经高度收敛：
        - `volume > 0` 子集 4-key match：`99.87%`
        - `open_interest > 0` 子集 4-key match：`100%`
        - `volume > 0` 子集 expiry match：`100%`
    - 价格层面：
      - matched near-ATM / liquid sample 中位偏差 `0.00%`
      - 最大偏差仅 `0.13%`
      - 当前最大的 `M4` 偏差来自 deep-ITM Massive `day_close` 陈旧，而不是系统性价格分歧
      - 因此 `M4 <= 2%` 门槛应只适用于 **liquid / price-bearing contracts**（例如 `delta 0.10–0.50` 段），不应对全链硬套
    - IV / Greeks / OI 当前应这样理解：
      - Schwab 字段存在性完整，不是 schema 丢列
      - Massive IV 单位是 **decimal**
      - Schwab IV 单位是 **percentage**
      - 正式 `M6` 比较前必须先做 `×100` normalization
      - `SPX` Massive Greeks / IV 为空，当前更像 provider 结构性限制，而不是 collector bug
      - 建议把 `SPX` 的 `M7` 从“跨源验证”降级为 **Schwab 单源监控**
    - 当前不阻塞 overlap 计时、但应尽快处理的工程/协议项：
      - formal key-match gate 改成 traded / price-bearing subset 分母
      - 历史侧 `SPX/SPXW` 显式保留或稳定重建 weekly 标记
      - `logs/q041_collect.out.log /.err.log` 的缺失要么文档化、要么补齐
      - Schwab option row 的 `open=0` 语义需要确认
    - Planner 含义：
      - `Q041` 现在不是“完全一致”
      - 但已经到达 **可接受收敛、继续 overlap validation** 的状态
      - 当前最需要修的是 protocol / semantics，不是 collector 主链路
      - 在 Phase 1 设计时再决定是否需要单独打开历史 `Greeks` 反推原型（例如 `enrich_greeks.py`）
    - 这也带来一个重要口径更新：
      - `Q041 Phase 1 / D1 Data Sanity`
      - 现在可以在 `data/q041_historical/` 上先行开展
      - 不必等 overlap validation 全部完成
      - overlap validation 仍然是 stitched dual-source dataset 的正式入场门槛
  - **2026-05-05 Phase 2 final summary update**：
    - `doc/q041_phase2_summary_2026-05-05.md` 已写入，当前结论是：
      - **Phase 2 全部任务完成（`P0 / P1 / P2` 全部关闭）**
      - `Q041` 不再处于 “Phase 2 队列执行中”，而是进入 **候选分层 + paper-trading 准备 + overlap validation 并行继续** 的状态
    - 当前最终候选分层已固定：
      - ✅ **正式候选**
        - `SPX CSP Δ0.20 DTE30`
      - 🔵 **正式候选边缘**
        - `GOOGL CSP Δ0.20 DTE21`
        - `AMZN CSP Δ0.25 DTE21`
      - 👁️ **观察候选**
        - `COST` earnings iron condor (`T-3`, `1.0x`)
        - `JPM` earnings iron condor (`T-3`, `1.0x`)
    - 当前已正式关闭的 Phase 2 子任务结论：
      - `P0-1`：
        - `SPX CC DTE45` 淘汰
        - `SPX CSP DTE45` 降级为观察项
      - `P0-2`：
        - `COST/JPM` 更长历史延伸因 Massive pre-2022 `403 Forbidden` 转为 **CLOSED-C**
        - 接受 `2022–2026` 四年窗口，但因此仅保留观察候选定位
      - `P1-1`：
        - `IMR / IVR` 风格过滤整体是弱信号
        - `COST` 不建议实施
        - `JPM` 仅可作为 paper-trading 阶段可选参数
      - `P1-2`：
        - `GOOGL / AMZN` pre-2022 同样拿不到，保持四年窗口
        - 因 Sharpe 仍强，升级为正式候选边缘而非观察项
      - `P2-1`：
        - `SPX CSP DTE30` 2022 熊市压测通过
        - 维持当前正式候选地位
      - `P2-2`：
        - earnings IC 在 `VIX < 15` 区间表现明确较差
        - `VIX >= 15` 是当前最有价值的治理 / paper-trading 过滤候选
    - 当前最关键的数据约束没有变化：
      - Massive pre-2022 S3 仍全部 `403 Forbidden`
      - 因此：
        - `GOOGL / AMZN` 缺 `2019–2021 / COVID` 样本
        - `COST / JPM` 也缺 COVID 财报阶段
      - 这解释了为什么个股 CSP 只到“正式候选边缘”，而 earnings IC 只到“观察候选”
    - Planner 含义：
      - `Q041` 下一步不再是继续执行 `P0-2 / P1-1 / P1-2`
      - 而是：
        - 保持 overlap validation 跑到正式 reconciliation endpoint
        - 为 `SPX CSP Δ0.20 DTE30` 准备 paper-trading / monitoring 口径
        - 将 `GOOGL / AMZN` 作为带尾部 caveat 的次级 paper-trading 候选
        - 将 `COST / JPM` 作为观察位，若进入 paper trading 需先累计更多财报周期
    - 当前 planner 已补充下一棒材料：
      - `task/q041_2nd_quant_review_packet_2026-05-05.md`
      - 用于请 2nd Quant review：
        - 当前候选分层是否合理
        - `SPX CSP DTE30` 是否足以进入下一阶段执行准备
        - `GOOGL / AMZN` 是否应保持”正式候选边缘”
        - `COST / JPM` 是否应继续停留在观察位
        - overlap validation 是否应继续作为并行 admission track，而不是重开 Phase 2
  - **2026-05-05 2nd Quant PASS Routing B + execution-prep packet**：
    - 2nd Quant 对全部 5 个问题均给出明确答复，总判断 **PASS — Routing B**
    - 分层确认如下：
      - **Tier 1（正式 paper trading）**：`SPX CSP Δ0.20 DTE30`
        - 证据最干净，2022 压测通过；IV compression trap = sizing 问题，不是 filter 问题
        - 2022 Jan–Apr 缺失为 caveat，但不阻塞 paper trading
      - **Tier 2（borderline formal / tail-caveated paper trading）**：`GOOGL CSP Δ0.20 DTE21` / `AMZN CSP Δ0.25 DTE21`
        - 信号强（Sharpe 2.28 / 1.50），不应降为 observe-only
        - 必须标注 COVID 尾部 caveat；sizing 应低于 Tier 1
      - **Tier 3（observe-only / 谨慎 paper trading）**：`COST` / `JPM` earnings IC
        - VIX≥15 是真实的 governance / entry filter（有经济解释）
        - JPM IMR≥33% 只作 optional paper-trading refinement（不统一实施）
    - Overlap validation 与候选晋升分离：
      - Overlap validation 继续作为 stitched dataset admission track
      - 不阻塞 paper trading 入场
    - Execution-prep packet 已写入 `doc/q041_execution_prep_packet_2026-05-05.md`：
      - BP 预算：Tier 1 ≤20% / Tier 2 combined ≤15% / Tier 3 ≤5% / Q041 总上限 ≤40%
      - 入场流程、per-cycle 记录字段、月度检查、升级 / 降级触发规则已全部定义
    - `Q041` 当前状态：**paper trading 入场 unblocked**
      - 不再需要新的 Phase 2 研究扫描
      - 下一工作：按 packet 执行 paper trading + 继续 overlap validation 并行进行
  - **2026-05-05 overlap-validation checkpoint 升级**：
    - Quant 当前最新一句话 verdict：
      - **`converging as expected`**
    - 这比前一轮 `mixed but acceptable` 更强，但仍不是“overlap validation 已完成”
    - 当前真实可比 session 口径：
      - Massive 仍以 `2026-05-01` 为最新可比较日
      - Schwab `2026-05-03` / `2026-05-04` snapshot 反映的是后续 EOD 状态
      - 因此真正严格的 same-day `M4` 比较，要等 Massive `2026-05-04` 日切片落盘后才第一次成立
    - 当前核心收敛指标已明显过线：
      - `M1 traded key match`：`99.2%`（`vol>0` 子集，过 `≥90%` 阈值）
      - `M2 expiry match`：`97.5%`
      - `M5 volume rank-corr`：`0.879`
      - `M6` near-money IV completeness：`100%`
      - `M7 Greeks`：`100%`
      - `M8 OI completeness`：`100%`
      - `M9 SPX/SPXW` 偏差仍在容忍带内
      - `M10 BRK/B` 命名稳定
    - 当前最重要的口径修正已经明确：
      - raw full-chain key match 约 `58.7%` 不应再被当成 fail
      - 正式 gate 应使用 traded / price-bearing subset，而不是 Schwab 全 quoted chain 做分母
      - Schwab `iv=-999` 视为 sentinel / null，正式 `M6` 统计必须过滤
      - `Schwab expiry_type` 正确语义：
        - `W = weekly`
        - `S = standard monthly`
        - `M = special month-end`
      - 因此 `M9` 的月度比较应按 `S`，不是旧的 `M`
    - 当前需要尽快修正、但**不阻塞** overlap 计时的事项：
      - `M3` strike-match 脚本 bug（应改为 merge 比较）
      - `iv=-999` null policy 写入 pipeline / protocol
      - `M9` 协议文字按 `W/S/M` 更新
    - 当前明确结论：
      - **无真正 blocker**
      - overlap validation 继续作为 stitched dataset admission / reconciliation track
      - 不阻塞当前 Tier 1 / Tier 2 / Tier 3 的 paper-trading routing
  - **2026-05-06 same-day M4 + cleanup 完成**：
    - `download_massive.py` 增量拉取 May 4–5 数据成功（80,012 rows，17/17 symbols）
    - **M4 同日比较**（Schwab `last` vs Massive `close`，2026-05-04）：
      - 全体匹配 n=29,733：median `|Δ|` = **0.000%**，>2% = 2.3% → **STRONG PASS**
      - SPX ATM (|δ|0.20–0.75)：median 0.000%，>2% = 13.9%（低成交量 strike 时间差，结构性，非数据错误）
      - 协议修正已写入：M4 必须用 Schwab `last`，不得用 `close`（前日收盘）或 `mid`
    - **M3 修复**（merge-based）：SPX 99.8%、GOOGL 83.6%、AMZN 85.8% → PASS；overall 80.3%
    - **M6**：near-money IV 100% 全符号，iv=-999 sentinel = 0 → STRONG PASS
    - **M7/M8**：Greeks/OI 100% → PASS
    - **M9 协议文字修正**：`doc/q041_overlap_validation_protocol_2026-05-03.md` 已更新，S=standard monthly，不是 M
    - 当前 overlap validation 状态：**converging as expected**，已有同日数据支撑
  - **2026-05-06 old Air 三条 Q041 数据流全部就位**：
    - `com.spxstrat.q041_collect`（Schwab chain，16:30 ET）：✅ 正常
    - `com.spxstrat.q041_massive_snapshot`（Massive REST 快照，16:35 ET）：✅ 正常
    - `com.spxstrat.q041_massive_historical`（Massive S3 历史 OHLC，08:15 ET）：✅ **新加载**
      - 修复：old Air venv 缺 `boto3`，已安装
      - bootstrap：全量历史 2022-05-06 → 2026-05-05，17 parquets，28,959,022 rows，约 20 分钟
      - 已知 exit code 1：每次运行尝试下载当天 S3 flatfile 返回 403（T+1 lag，预期行为），不影响数据积累
      - 后续每天 08:15 ET 增量拉取前一交易日 OHLC，无需手动触发
- **2026-05-03 runtime-alignment note**：
  - `Q036` posture 本轮未变化：
    - old Air 仍是 `overlay_f_mode = "shadow"`
    - 当前 recommendation 仍显示 `overlay_factor = 1.0`
    - `overlay_would_fire = False`
  - 本轮未重启 `web` / `bot`，原因是：
    - `a112d33` 仅引入 research scaffold、`pyarrow` 和 attribution notes
    - 不涉及新的 live recommendation/runtime code path
    - 当前 runtime health 正常
- **2026-05-03 Massive historical-data clarification（更正）**：
  - 先前记录"含 EOD aggregates / trades / greeks / IV / OI"的说法**已被推翻**
  - 经 Quant live 测试确认：
    - Massive Developer 计划仅 `day_aggs_v1` 可访问
    - `day_aggs_v1` 字段：`ticker / open / high / low / close / volume / transactions / window_start`——**无 Greeks / IV / OI**
    - 所有非 `day_aggs_v1` S3 路径（trades / minute_aggs / quotes）在 Developer 计划下返回 `403`
    - Massive REST snapshot API 返回当日实时数据，**不支持 `as_of` 历史查询**
  - 结论：历史 Greeks / IV / OI 在当前 Massive Developer 计划下**完全不可用**
  - 后续 Phase 1 中需要历史 delta targeting 或 IV-sensitive 分析时，须明确降级方案（如 BAW 反推）
- **2026-05-03 Phase 1 设计 + GPT Quant Review 更新**：
  - 文档已写入：`doc/q041_phase1_design_2026-05-03.md`
  - 已提交 GPT 外部 Quant Review；回复见 `doc/q041_phase1_design_GPTreview.md`
  - Quant 已审阅 GPT review，**主要接受**以下调整：
    1. **Phase 1 重组为 4 个交付物**（顺序不可颠倒）：
       - `D1 Data Sanity Report`（数据质量验证）
       - `D2 Benchmark Replication`（BXM / PUT Index 复现）
       - `D3 Module A/B Conservative Backtest`（Covered Call + CSP 参数扫描）
       - `D4 Module C Event Study`（财报 IV crush 事件研究）
    2. **模块顺序改为 A → B → C**（原设计为 C → A → B）
       - Module C 需要最多数据基础设施（vol surface、精确 IV、spread 定价），应排最后
    3. **交易成本模型必须显式建模**：option close ≠ executable mid；参考 slippage table
    4. **BP 定义改为 3 层**：standalone BP / sleeve BP / account marginal BP；主要 ROE 指标 = marginal $/BP-day
    5. **白名单分 3 层**：
       - Tier 1 核心：`AAPL MSFT AMZN GOOGL META JPM WMT COST QQQ SPX`
       - Tier 2 高波动：`NVDA TSLA AMD PANW`（小仓位独立评估）
       - Tier 3 观察：`ASML TSM BRK/B`（流动性待确认）
    6. **Module C CVaR 规则已更正**：定义风险 spread 不可能超过 max loss，原规则逻辑错误；改为账户级仓位上限（单事件 ≤ X% NAV，财报周 ≤ Y% NAV）
  - **Quant 小分歧**（不影响 Phase 1 结构）：
    - `BRK/B` 应留 Tier 2（流动性 check 待做），不应降至 Tier 3
    - Vol surface 是 Module B put skew 分析的重大问题，但不阻塞 Phase 1 D3
  - **Overlap validation 与 D1 的关系**：
    - Overlap 20 天校验窗口继续运行（目标 `2026-05-30` 提交 Reconciliation Report）
    - 但 D1 数据质量报告**不依赖** Schwab 与 Massive 的 overlap 结果
    - D1 仅使用 `data/q041_historical/` 历史 parquet，可立即开始
- **当前归类**：Phase 1 / D1 Data Sanity（可立即开始）
- **来源**：`research/strategies/Large-Cap Equity Option Income Overlay/Large-Cap Equity Option Income Overlay.md`；Quant 评估，2026-05-03

### Q054 — Unusual Whales 订阅数据 Alpha 研究

- **状态**：**KILLED 2026-05-10**（Tier 0 完成，R-20260510-10）— 当前订阅层级无 CSV export / API，历史数据不足，EV 为负，不启动 Tier 1
- **数据源**：PM 持有 Unusual Whales 订阅（options flow、dark pool prints、large unusual volume、congressional disclosures、institutional positioning）
- **核心问题**：Unusual Whales 数据是否包含对主策略（BPS / IC / BCD）或 Q041 sleeve 有增量价值的信号？候选方向（不代表已决定研究哪条）：
  1. **options flow 作为 entry timing 信号**：unusual call/put volume surge 是否与 VIX regime 转换或 IV expansion 有预测关系
  2. **dark pool prints 作为方向性 filter**：大宗成交方向是否能提供 SPX 短期偏差的独立信号
  3. **institutional positioning overlay**：与 Q041 equity sleeve 候选（GOOGL/AMZN/COST/JPM）的已知持仓方向是否能辅助 entry 或 avoidance 判断
- **不在范围（当前）**：congressional trading（与主策略无直接关联）；任何需要 real-time streaming 的架构改动
- **Tier 0 结论**：当前订阅无 API / CSV export（仅 web UI）；历史回溯不足；EV 估算为负。research/q054/ 保留（若 PM 升级到 3yr prepay 或 Lifetime 解锁 CSV，pilot 可原地重启）
- **副产品**：UW eyeball check（可选 sanity check）已折入 `task/q042_manual_sop.md §B`，含学术 disclaimer 和 < 10% override 频率约束
- **来源**：PM 2026-05-09；`RESEARCH_LOG.md R-20260510-10`

---

### Q042 — Directional Drawdown / Reversal Overlay：是否值得在当前 income-first 主线之外单独开启显式方向性分支
- **状态**：**SPEC-094 IMPLEMENTED 2026-05-10** — F1-F9 已全部实施，paper-trading 已启动
- **APPROVED Spec**: `task/SPEC-094.md` (Status: APPROVED)
- **Final config（Tier 3 deep-dive 后）**:
  - **Drawdown 定义**: ddATH（running max from 2007-01-01）— 修正自 dd60_rolling
  - **Sleeve A**: dd4 ddATH_lenient（re-arm at ddATH ≥ -2%），**no MA filter**，10% sizing — 1.3 trades/yr, 64% win, +5.11%/yr, -16.3% DD
  - **Sleeve B**: dd15 ddATH_lenient + **MA10 reclaim**，10% sizing — 0.26 trades/yr, **100% win** (5/5), +2.12%/yr, **0% DD**
  - **Structure**: ATM/+5% call spread, DTE 90, T+1 open
  - **跨 sleeve 完全独立**（各自 armed state）— BP 偶尔合计 20%（109/4868 天 = 2.2%）
  - **Combined cap**: 20%（governance backstop: `min(20%, max(0, 60% − main_bp%))`）
  - **Symbol**: **SPX-only**（XSP 路径删除 2026-05-10 PM scope decision）
  - **Activation threshold**: NLV ≥ **$200k**（SPX 1-contract minimum sizing 边界）
  - **预期组合年化**: ~+7.2% (sleeve A +5.1% + sleeve B +2.1%)
  - **F4 deployment hard gate**: ✅ **PASSED retroactively from oldair 5-day archive** (2026-05-04 → 05-08; median delta 5.65%, max 8.0% << 15% threshold). Caveats: collector strike window 当时只到 +3.4% OTM（forward 已识别 1-line fix）；5 天全部低 vol regime（VIX 17-18），首次 live HIGH_VOL trigger 强制 re-validation
- **23 acceptance criteria (AC1-AC23)**，详见 SPEC-094
  - **Execution**: T+1 open
  - **Hold**: to expiry (Tier 4 to test 50% TP / 50% stop)
- **Critical Tier 3 findings**:
  - DTE 30 is **4-5× more drift-sensitive** than DTE 90 (T_close → T+1_close: −19/$100BP vs −5)
  - **dd15 naive unfiltered is unviable**: 28-35 max consec losses, −42% to −62% worst 12m windows (2008-2009 GFC)
  - With no-overlap rule, dd15 naive DTE 120 has **90% win rate, 1 max consec loss** (n=10)
  - dd12+reclaim DTE 90 filtered: 62% win, 3 max consec, n=13
  - Both options viable — paper-trade decides
- **Pre-deployment hard gate**: F4 5-day broker-API midpoint vs model-debit tie-out, median delta < 15%
- **Tier 1 三问回答**（`research/q042/q042_tier1_memo_2026-05-09.md`）：
- **Tier 2 winner（`research/q042/q042_tier2_memo_2026-05-09.md`）**：
  - **Trigger**: dd60 ≥ 12% + 30-day 内 close > MA50 reclaim
  - **Structure**: ATM/+5% call spread, DTE 30
  - **Sizing**: 1% account / entry, 20% account 绝对 cap
  - **Economics（raw, pre-tx-cost）**: median +$3.53 / $100 BP-day = **~7.3× V_A baseline**, win rate 73%, n=41 over 19 years
  - **Economics（post tx-cost haircut estimate）**: +$2.5-3.0 / $100 BP-day, ~+0.8-1.2% account / yr at 1% account/entry
- **Tier 2 关键发现**：
  - **P1 Trigger grid**: dd12+MA50 reclaim 12m median +42.7% / positive 92.7%；dd15 naive n=192 / 12m positive 97.9%；OOS robust 两段 (2007-18 / 2019-26)；MA200 reclaim & term_normalize 已 drop
  - **P2 Structure grid**: 短 DTE (30) + 紧 spread (3-5%) 在 $/BP-day 上压倒 LEAP / long call / ratio
  - **P3 BP gate**: **Tier 1 Q3 concern 方向错了** — 主策略在 HIGH_VOL 自动 de-gross (BPS_HV/IC_HV)，19y backtest mean BP usage 6.3%、median 4.3%；default gate `min(20%, max(0, 60% − main_bp%))` 在 19 年里 fire rate 0%；保留为 governance backstop（regime-conditional on main-strategy params）
- **Tier 3 / SPEC drafting 必修 unknowns**:
  1. Live SPX chain pricing（替代 BS+skew approximation）
  2. Ratio 1×2 PM margin reality check（live PM margin during VIX>30）
  3. Re-trigger spacing 规则（避免 long drawdown 期间多次入场）
  4. Exit rule MVP 测试（held to expiry vs 50% TP/stop）
  5. SPX vs XSP 选择
  6. Account-scale 激活门槛
- **Tier 1 三问回答**（`research/q042/q042_tier1_memo_2026-05-09.md`）：
  1. **回撤深度 vs forward return** — dd60 ≥ 10% 起边际清晰：12-mo median **+21%**（dd10）/ **+30%**（dd15），positive rate 82-100% vs 无条件 +13% / 79%。MA50 reclaim filter 提升 win rate 但砍样本 88%（不是 free lunch）
  2. **结构选择** — ATM/+5% **call spread**（DTE 90）是唯一过 V_A baseline 的结构（中位 $1.49/$100 BP-day = **3.1× baseline**）；LEAP ATM marginal 正但 18% baseline；LEAP Δ0.35 结构性负（19% win rate, median −100% premium）
  3. **regime 兼容性** — dd10 trigger 时 **98.5%** 在 HIGH_VOL（VIX>22）；dd15+ 100% HIGH_VOL；与主策略 BPS_HV / IC_HV 强重叠 → BP 容量直接竞争（vega 维度反向但 BP 维度同向）
- **结论**：✅ 2/3 问题正面（Q1 + Q2）；Q3 是 Tier 2 必修 sizing 课题不是 edge-killer
- **Tier 2 scope（推荐）**：
  - Trigger calibration: dd10/dd15 × reclaim/breadth/term-structure confirmations grid，weighted by waiting cost
  - Structure refinement: 30-120 DTE × ATM-to-Δ-target grid + ratio spread / risk reversal；用 IV-surface 重定价（VIX-as-σ 在 Tier 1 偏保守）
  - **BP-stacking gate**（必修）: default 提议 cap = `min(20% account, max(0, 60% account − main_strategy_BP%))`
  - OOS check: 2007-2018 vs 2019-2026 split
- **Caveats**：无 transaction costs / slippage；VIX-as-σ 无 skew（spread 数字方向上保守）；dd20 sample n=88
- **Output artifacts**：
  - 备忘：`research/q042/q042_tier1_memo_2026-05-09.md`
  - 脚本：`research/q042/q042_tier1_feasibility.py`
  - Seed memo：`doc/q042_directional_overlay_seed_memo_2026-05-04.md`
  - RESEARCH_LOG: R-20260509-11
- **下一决策（PM）**：promote to Tier 2 / hold / drop. Tier 2 不会启动直到 PM 明确批准
- **Q062 结构参数验证（2026-05-10）**：在 Sleeve A dd4（n=25）和 Sleeve B dd15+MA10（n=5）实际触发样本上独立验证（三 Tier）。结论：SPEC-094 参数（ATM/+5%, DTE 90, call spread）在 per-sleeve 基础测试中成立。进一步 Tier 1→2→3 全网格扫描（D30 候选）后 PM 决策升级为 **SPEC-094.1**：Sleeve A 替换为 D30/2.5%（AnnROE +9.94% vs baseline +5.02%，bootstrap p=0.09 PM 接受）。见 `task/SPEC-094.1.md` 和 `RESEARCH_LOG.md R-20260510-15`。
- **SPEC-094.1 APPROVED（2026-05-10）**：Sleeve A 参数替换（DTE 90→30, offset 5%→2.5%, no-overlap 90→30 days）。Sleeve B 不变。当前 2026-03-12 仓位 grandfather 至 2026-06-10。Developer 10 ACs 待实施。

---

### Q062 — Q042 结构参数 per-sleeve 优化
- **状态**：**CLOSED 2026-05-10**（R-20260510-12）
- **来源**：PM 授权（2026-05-10）— Q042 SPEC-094 参数从未在 dd4 / dd15+MA10 实际触发样本上 per-sleeve 验证
- **结论**：SPEC-094 参数完全确认，ATM/+5%, DTE 90, call spread 两 sleeve 均最优
- **Key finding**：Sleeve A VIX 中位 20.6（低于 dd12 样本 33.3），win rate 68% < Tier 2/3 80%（预期；dd4 浅回撤 alpha 弱于深回撤）；结构排名不受 VIX 差异影响
- **不在范围**：Far-OTM spread（Sleeve A 明确反推荐，6 consec losses）；Sleeve B long call 统计不显著
- **复查触发**：Sleeve B paper trading 积累至 n≥15（当前 n=5）
- **Artifacts**：`research/q042/q062_memo_2026-05-10.md`，`q062_p1/p2/p3_*.csv`


### Q071 — ES Sell Put 整合策略研究（/ES V2f + Q041 T1）
- **状态**：**CLOSED 2026-05-14（PROMOTE，2nd Quant review 完成）**
- **来源**：PM 希望整合 /ES V2f（结构骨架）与 Q041 T1（IV/regime 入场质量思想），形成统一 ES Sell Put 策略
- **2nd Quant review**：**REVISE**（2026-05-14）——原设计是"加 IVP 43-55 gate"的 filter 移植，不是完整策略设计。三个核心问题：①IVP signal 迁移存疑（Q063 alpha 在 SPX DTE30 验证，/ES V2f 结构完全不同）；②窄 IVP window 可能打断 rolling ladder 时间分散优势；③缺 portfolio/margin governance 层
- **重构后研究架构（P0–P5）**：
  - P0：目标函数（ROE 改善 OR MaxDD 改善，否决条件：V1 FAIL / bootstrap < 80% / SPAN > 30% NLV）
  - P1：V2f entry attribution by IVP × VIX bucket（不加 gate，先看 edge 是否存在）
  - P2：Gate candidates（从 attribution 数据驱动，测 IVP≤55 / ≥43 / 43-55 / VIX<30 / VIX≥22 等 8 变体）
  - P3：Cadence-aware 实现（hard skip vs delay retry vs size scale 0.5x）
  - P4：STOP=15 尾部交互证明（验证 V2f STOP 是否真正解决 Q041 T1 尾部问题）
  - P5：完整 portfolio viability（Ann ROE / Sharpe / MaxDD / stress SPAN / bootstrap / 2008/2020/2022）
- **关键发现**：
  - IVP 43-55 被实证驳斥（ann_roe 1.04%→0.07%，-0.98pp）——Q041 假设不能迁移到 V2f 语境
  - G6（VIX ≥ 22）数据驱动发现：ann_roe +1.14%，sharpe 0.34，MaxDD -9.7%（vs baseline -33.3%），bootstrap 100%（baseline 0%），2020 COVID +3.1%（vs -23.4%）
  - V2f_base bootstrap sig_rate = 0%：生产 baseline 本身边缘脆弱，G6 是创造显著性而非增强
  - G6 仅 21% 交易日有仓（vs baseline 86%），PM 接受低 capital deployment
  - Mode B = Mode A（IVP/VIX 5TD 内不翻面）；Mode C 反向破坏（半仓重引入 excluded trades）
  - STOP=15 在 G6 下冗余，保留作 defense-in-depth
- **P0 判定**：Criterion B PASS（ROE flat +0.09pp，DD 改善 23.6pp ≫ 2pp 门槛），V1 PASS，bootstrap PASS，SPAN 15% NLV < 30% ceiling → PROMOTE
- **2nd Quant 修订（2026-05-14）**：策略 rename → ES High-Vol Sell Put Ladder；Q041 framing 改为 regime-quality concept 迁移；STOP=15 → "unused historical safeguard"；bootstrap sig 加 production fragility caveat；promote level → DRAFT SPEC + paper/shadow（非 production）；review obligation → 12mo AND ≥10 entries OR 24mo；Q072 IVP 增量判别为 OPTIONAL post-SPEC
- **下一步**：起草 SPEC-XXX ES High-Vol Sell Put Ladder（2nd Quant §7 已给出 entry rules / structure / risk controls / monitoring 建议起点）
- **Artifacts**：`research/q071/q071_memo_2026-05-14.md`（已按 review 修订），`task/q071_2nd_quant_review_2026-05-14.md`，11 个 CSV，5 个 phase scripts，`q071_engine.py`，`RESEARCH_LOG.md R-20260514-01`

---

### Q070 — Aftermath Peak VIX 阈值敏感性 Sweep
- **状态**：**CLOSED 2026-05-13**（R-20260513-10，无 2nd Quant review——结论为 status quo 维持）
- **来源**：PM 发现 2025-11-20 VIX 峰值 26.4 被 `AFTERMATH_PEAK_VIX_10D_MIN=28` 门槛排除，质疑门槛是否过高
- **研究路径**：P1 threshold sweep {22,24,25,26,27,28} → P2 BPS HV trade 归因 → P3 2025-11-20 case study
- **关键发现**：

| Threshold | 新增 Window | LOW_VOL 污染率 | 新增 BPS HV trades (19yr) |
|---|---|---|---|
| 27 | +17 | 5.9% | 1 |
| 26 | +31 | 9.7% | 1 |
| **25** | **+47** | **27.7% ← 跳升** | 2 |
| 24 | +72 | 51.4% | 2 |

- **分水岭**：threshold=25 处 LOW_VOL 污染率急跳（9.7%→27.7%），且 19yr 仅新增 1-2 笔实际 trade，无统计意义
- **P3 结论**：2025-11-20 瓶颈是同期 IC_HV 持仓占用 BP，而非门槛设计问题
- **额外结论（Quant）**：aftermath 不建议独立出去做 sleeve——本质同向短 vega（Q066 Greek 表已确认），独立后只是把同一风险分两账本，且加重 co-loss tail risk
- **结论**：**`AFTERMATH_PEAK_VIX_10D_MIN=28` 维持不变，置信度高**
- **Artifacts**：`research/q070/`，`RESEARCH_LOG.md R-20260513-10`

---

### Q066 — Aftermath vs Q042 Co-firing 频率实证
- **状态**：**CLOSED 2026-05-12**（R-20260512-02）
- **来源**：两个 addon（主策略 aftermath routing 和 Q042 Drawdown Overlay）是否存在信号重叠、BP 竞争或 Greek 叠加风险
- **研究内容**：19yr 日线级 co-firing 频率分析 + Greek 正交性论证文档
- **核心结论**：

| 度量 | 结果 | 解读 |
|---|---|---|
| Day-level overlap rate | 0.9%（5/553）| 几乎零同步触发 |
| Q042-A ±5TD co-fire with Aftermath | 26%（9/35）| 74% Q042-A 是 vol-quiet drawdown，aftermath 永不触发 |
| Q042-B ±5TD co-fire with Aftermath | 80%（4/5）| B 是深崩盘天然伴随 VIX spike；但 N=5 小样本 |
| Aftermath windows ±5TD co-fire with Q042-A | 14%（13/90）| 86% aftermath 是 vol-only 事件 |
| Aftermath windows ±5TD co-fire with Q042-B | 7%（6/90）| 93% aftermath 不伴随深崩盘 |

- **Greek 正交性**（`doc/addon_greek_orthogonality_2026-05-12.md`）：

| Greek | Aftermath | Q042 |
|---|---|---|
| Vega | − | + |
| Gamma | − | + |
| Delta | 微 − | + |
| Theta | + | − |

四维度全反向——共持仓时是 partial hedge 非 duplicate risk

- **结论**：**两个 addon low-overlap / non-redundant，不应合并、不应竞争**；BP 冲突已由 `q042_gate.py` joint cap 解决
- **2nd Quant review**：PASS WITH CAVEAT（4 项修订落地）。语言从"orthogonal"→"non-redundant"（Greek hedge 在 PnL 层未量化）；Q042-B "monitor as sample grows"；Greek wording caveat 加入；co-fire downside scenario 子节新增
- **Co-loss failure mode**：正式列入 portfolio failure modes。live 中若观察到一次 co-fire 同向亏损 → 立即触发 Q067
- **Q067 standing monitoring**（不主动启动）。触发条件：Q042 paper→live / B 样本扩充（n≥10）/ cap 上调 / live co-fire co-loss 出现
- **PM 无需立即行动**：维持双 addon 现状
- **Artifacts**：`task/q066_cofiring_2nd_quant_review_packet_2026-05-12_Review.md`，`doc/addon_greek_orthogonality_2026-05-12.md`，`research/q066/q066_memo_2026-05-12.md`

---

### Q065 — Aftermath EXTREME_VIX=40 阈值敏感性研究
- **状态**：**CLOSED 2026-05-12**（R-20260512-01）
- **来源**：Q064 P1 中 2025-04-09 出现 1-day aftermath window，PM 质疑 `EXTREME_VIX=40` 是否过严，是否应放宽至 42/45
- **研究路径**：P1 blocked days 扫描 → P2 threshold sweep（baseline_40 / loosen_42 / loosen_45 / peak×0.85）→ P3 不启动（三变体全 fail）
- **关键结论**：

| 变体 | Trap Rate | 判定 |
|---|---|---|
| baseline_40（生产）| — | ✅ 保留 |
| loosen_42 | 41.2%（7/17 新增日 5TD 内 VIX 反弹 ≥45）| ❌ |
| loosen_45 | 47.2%（17/36）；2009 局部 72.2% | ❌ |
| peak×0.85 | 78.9%（56/71）| ❌ |

- **机制**：VIX 40-45 区间且 off-peak ≥10% 的"看似回落"日，历史上有 41-72% 概率 5TD 内反弹至 ≥45，是 GFC/COVID 真实尾部波动结构，不是噪音
- **2025-04-09**：19yr 第 6 个边界 case，本身无 trap，但 41% 同类 setup 会 trap——不能为救单点打开普遍漏洞
- **结论**：**`EXTREME_VIX=40` 维持，`selector.py` 不动，P3 永久 closed**
- **后续 action**：Q064 P1 加 merged-windows 辅助视图（≤2TD gap 合并）——独立工单，不属于 Q065 范围
- **Artifacts**：`research/q065/q065_memo_2026-05-12.md`，`q065_p1/p2_*.py`，`RESEARCH_LOG.md R-20260512-01`

---

### Q069 — IVP Gate Smoothed/Slope-aware 变体研究
- **状态**：**CLOSED 2026-05-13**（R-20260513-09）
- **来源**：Q067/Q068 延伸——测试 SMA/EWM smoothed IVP 或 slope-aware IVP 是否解决 jitter 问题
- **结论**：**全部失败**。smoothing 引入 lag，已知 2026-02-25 bad trade 被重新放行；slope-aware worst trade 恶化
- **正式 wording**：hard IVP_252 ≥ 55 gate 是 **tested frameworks 内** empirical local optimum（不写"永远不能解决"）
- **Artifacts**：`research/q069/q069_phase2_memo_2026-05-13.md`，`RESEARCH_LOG.md R-20260513-09`

---

### Q068 — IVP Gate MA-timing Override + Regime Stop 研究
- **状态**：**CLOSED 2026-05-13**（R-20260513-09）
- **来源**：Q067 jitter 实证后，测试 MA cross / regime-conditional stop 能否在不改 gate 的情况下改善表现
- **结论**：**全部失败**。P6-P7 所有变体 worst trade 恶化至 -$15k（vs baseline -$9k），robustness FAIL
- **核心 takeaway**：PM intuition is valid as trading observation, but not stable enough for rule-level adoption
- **Artifacts**：`RESEARCH_LOG.md R-20260513-09`

---

### Q067 — IVP Gate Threshold Jitter 研究
- **状态**：**CLOSED 2026-05-13**（R-20260513-09）
- **来源**：Q063 发现 gate 有效，但 PM 质疑 IVP 在边界附近是否频繁 flip（jitter 问题）
- **P1 实证**：7.37% historical / 11.5% recent daily flip rate；61% reverse within 5 TD；15% 126d-vs-252d window disagreement——**jitter 是真实的**
- **P2 结论**：hysteresis / multi-horizon / cross-window 所有 jitter fix 变体全部失败（alpha 流失或 worst trade 恶化）
- **核心 takeaway**：Jitter is real, but all tested jitter fixes are worse than the hard gate
- **Artifacts**：`RESEARCH_LOG.md R-20260513-09`

---

### Q064 — Aftermath 路由回测 + Spell Reset Sensitivity（P1–P9）
- **状态**：**CLOSED 2026-05-13（FULLY CLOSED — P1–P9 + SPEC-100 DEPLOYED commit b894e26）**
- **来源**：主策略 `is_aftermath()` 路由到 V3-A IC HV，P1–P4 初步显示 $/BP-day 低 62%，疑似可 revert
- **研究路径**：P1–P6（routing review）→ P7–P9（spell reset sensitivity）→ 2nd Quant review × 2
- **P1–P6 结论**：V3-A gate-bypass 价值确认，SPEC-064 保留。V3-A 真实价值 = 绕过 post-vol-shock cells 中 reduce_wait gates，捕捉 ~$30k+ alpha
- **P7–P9 结论（spell reset mechanism，12 variants engine replay）**：

| 变体 | 结果 | 判定 |
|---|---|---|
| P8: max_trades_per_spell 2→3 | +$11k ann | ✅ 采纳 → **SPEC-100** |
| P9a: hysteresis 3d/5d | -$20.7k（-20%）| ❌ 拒绝 |
| P9b: no-high-reset | -$16.3k（-16%）| ❌ 拒绝 |
| P9c: spell_age_cap 30→90 | +1 trade only | ⏸ 延后 |
| P9d: 所有 combos | 单调恶化 | ❌ 拒绝 |

- **Design Principles 固化**：vix_low_reset 单日触发 deliberate；vix_high_reset(≥35) 是 event-boundary reset 非冗余；age_cap=30 near-optimal
- **方法论 learning**：spell gate 行为不能从 code structure 直觉推断，必须 engine replay（Quant 3/3 预测全错）
- **SPEC-100 DEPLOYED**（commit b894e26）：`max_trades_per_spell: 2→3`，三套 backtest cache 已刷新
- **Standing obligations**：2027-05-13 12-month live review；spell #3 单笔亏损 ≥ -$3k 或连续 HV spell ≥ 60d → 临时 Quant review
- **Artifacts**：`research/q064/`，`task/q064_aftermath_2nd_quant_review_packet_2026-05-12_Review.md`，`RESEARCH_LOG.md R-20260512-03, R-20260513-04`

---

### Q063 — SPX 主策略 IVP<55 Gate Robustness Review（含 Q067/Q068/Q069 延伸）
- **状态**：**CLOSED 2026-05-11（§13 supplement 2026-05-13，Q067/Q068/Q069 全线确认）**
- **来源**：PM hypothesis「IVP<55 gate 在低 VIX 环境下产生 false alarm，应放宽」
- **结论**：**REJECT relaxation，keep gate unchanged，no SPEC change**
- **研究路径**：Phase 1 VIX-stratified blocked trades → Phase 2 candidate gate comparison → Phase 3 OOS robustness → Phase 4 decay-weighted
- **关键发现**：
  - Phase 1：低 VIX blocked entries WR 63%（vs allowed 83%），avg P&L $389（vs $2,323）——低 VIX 时 gate 仍有效
  - Phase 2：候选 A（relax gate）19y unweighted +$6k，但 Phase 3 OOS test 期 A loses -$907/yr
  - Phase 4：decay 越重 A 越差——3y HL A loses -$19,237；last 5y A loses -$13,730；last 3y A loses -$7,700
  - 2024-2026 gate 挡住 5 笔 entries，counterfactual P&L = -$13.7k（gate 是高价值真信号）
- **Mechanism**：VIX=15-17 + IVP=60-65 不矛盾——vol 已 compress 到 1y 高分位（相对）即使 absolute 低；gate 在 recent regime shift（2022+ 结构性低 vol 但 IV spike 仍阶段性高）下更重要
- **延伸研究（Q067/Q068/Q069，2026-05-13）**：jitter / MA-timing / smoothed IVP 三条路全部失败，BPS_NNB_IVP_UPPER=55 最终确认为 tested frameworks 内 empirical local optimum。Q070+ 重启需满足 4 条高门槛之一（非传统框架 / Bayesian / live evidence / routing 重大变化）
- **selector.py:187-203 inline comment** 已固化三条 takeaways：VIX 绝对值低 ≠ IVP 相对位置低；jitter real but fixes worse；PM intuition valid but not rule-stable
- **Artifacts**：`task/q063_phase4_closure_memo_2026-05-11.md`，`task/q063_q067_q068_q069_closure_2nd_quant_review_2026-05-13.md`，`RESEARCH_LOG.md R-20260511-01, R-20260513-09`

---

### Q043 — Q041 scanner / bot support：在 visualization / attribution surface 稳定后，是否应补一层只读 scanner + shadow notification 支持
- **状态**：open（future support seed / medium-low priority）
- **内容**：
  - `SPEC-083` 已完成 `Q041` 的最小 paper-trading support surface：
    - ledger
    - manual logging
    - budget tracking
    - review export
    - minimal visibility
  - PM 进一步提出一个很自然的支持面想法：
    - 自动扫描 `Tier 1 / Tier 2 / Tier 3` 的潜在入场时机
    - 对已记录的 paper trades 给出 close / expiry / earnings T-3 review 提醒
    - 通过现有 bot 或单独 dev bot 推送“建议开仓 / 关仓 / review”信息
- **当前定位**：
  - 这是一个 **future support branch**
  - 不应 retroactively 扩进 `SPEC-083`
  - 不应直接并入当前 SPX 主 recommendation engine
  - 不应立即进入正式 bot / live recommendation surface
- **建议未来 phase**：
  - `Q043-A`：read-only scanner + candidate audit log
  - `Q043-B`：dev bot / shadow notification
  - `Q043-C`：existing paper-trade reminder support
- **推荐边界**：
  - 先 scanner，后 notification
  - 先 dev / shadow，后正式 surface
  - 不做自动下单
  - 不做自动平仓
  - 不做 broker write integration
  - 不把 `Q041` 变成第二套产品系统
- **为什么现在不推进**：
  - 当前 `Q041` 的主路径已转向 attribution / visualization + overlap validation；`SPEC-085` 虽已 DONE，但新的 read-only surfaces 与 `SPEC-087` Portfolio Command Center 仍处于刚上线后的稳定化阶段
  - overlap validation 也还有 cleanup / checkpoint 工作
  - 过早把 scanner / bot 推进正式 runtime，最容易带来 noisy recommendation、budget 语义不稳、与主 SPX 信息流混淆
- **当前建议**：
  - 只作为未来支持面备忘保留
  - 等 `SPEC-085` read-only surface / `SPEC-087` command-center 用法沉淀、以及 overlap-validation 路径进一步稳定后，再考虑是否起一个窄 spec（例如 shadow scanner / dev-bot support）
- **参考备忘**：`doc/q043_q041_scanner_and_bot_seed_memo_2026-05-05.md`

### Q045 — Account-Level ROE Optimization Across Strategy Matrix：联合 bp_target lift（取代分散的单策略优化）

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q045` and `RESEARCH_LOG.md` for full research record.

---

### Q046 — 外部 BP 使用率 benchmark 与账户级 deployment efficiency：我们是否仍然结构性低利用？
- **状态**：open（benchmark complete / mechanism map complete）
- **触发**：`SPEC-084` 上线后，PM 继续追问：即使联合 `bp_target` 已抬高，系统平均 BP 使用率仍仅约 `15.9%`，是否仍显著低于主流 short-premium 账户的组合层 active allocation？这一问题直接影响账户级 ROE 的后续优化方向。
- **Quant 结论（一句话）**：我们的 `~16%` 表面看低于外部 `25%–30%`，但在 **PM defined-risk 口径** 下实际差距只约 `~5–10pp`，不是 `15pp+`；下一条最值得推进的机制是 **C（broader strategy / underlying coverage）**，因为只有 C 能直接触及 `17%` 的 fully-idle days。
- **benchmark normalization 结果**：
  - 外部 `25%–50%` 常说的是 **portfolio-level capital at work**，不是单笔 `bp_target`
  - Reg-T / CSP / naked-short 框架下的 `30%`，换算到 PM defined-risk 组合后，等效差距显著缩小
  - 对一个保守-中性 PM defined-risk 玩家而言，我们并非“极度低利用”；只是仍有中等幅度的 deployment gap
- **机制排名**：
  1. **C — 更广的策略 / 标的覆盖（首选）**：唯一能直接攻击 `17%` fully-idle days；对应当前载体就是 `Q041`
  2. A — 继续加大现有 sizing：`Q045` 已收割大部分价值，余量受 cliff / tail 限制
  3. B — 放宽 concurrency / overlap：不能碰 fully-idle days，且 concentration risk 更差
  4. D — 调整 ceiling：只是 enabler，不是 standalone axis
- **对 Q041 的影响**：
  - `Q041` 不再只是“diversified income overlay / paper-trading support”
  - 在 post-`Q045` 阶段，它应被正式视为 **primary account-level deployment-efficiency mechanism axis**
- **明确排除**：
  - 不因为本结论立刻再改 live sizing
  - 不 retroactively 调整已有真实仓位
  - 不重开 `SPEC-084`
  - 不单独因为 Q046 而改 ceiling
- **建议下一步**：
  - 不再把长周期 paper-trading 当作默认主路径
  - 将 `Q041` 的 portfolio-value 量化建立在已接受的 Tier 3 attribution artifact 上
  - 保持 overlap-validation 继续独立运行，作为 stitched data admission track
- **当前归类**：research framing complete / next work shifts to `Q041` attribution-backed platform support
- **参考备忘**：`doc/q046_bp_utilization_external_benchmark_seed_memo_2026-05-07.md`

### Q048 — Portfolio-State Architecture Transition Plan：从单 SPX 执行平台到组合层研究平台的过渡设计

- **状态**：open（planning / architecture item）
- **触发**：在 `Q041 + Q045 + Q046` 之后，项目顶层目标已经明确转向账户级 deployment efficiency / ROE，但当前系统主轴仍是“一个 SPX 主推荐 + 一个当前仓位 + 一个 SPX 回测宇宙”。PM 判断这是一个阶段切换点，需要从高维度重新审视后端、状态模型、账本模型和前端信息架构。
- **核心诊断**：
  - 当前 live rail 仍围绕单一 `current_position.json` 与单一 `Recommendation`
  - `Q041` 已经引入第二条 rail：多记录 paper ledger + 预算 / review 语义
  - 现在代码库事实上并存两套模型：
    - 主系统：single-live-position SPX rail
    - `Q041`：multi-record portfolio-expansion experiment rail
  - 这意味着问题已不再是“再加一个策略”，而是“如何支持 portfolio-level research 而不污染当前 SPX 生产主线”
- **Q048 要回答的不是实现细节，而是 planning 边界**：
  1. 最小 portfolio-state abstraction 应是什么（如 `PortfolioPosition` / `PortfolioBook` / `BudgetSnapshot`）
  2. live / paper / observe-only 账本语义如何统一
  3. recommendation 是否需要从 `single answer` 拆成 `candidates[] + selected_primary + portfolio_constraints`
  4. 最小 portfolio summary / attribution surface 应先支持什么，不应先支持什么
  5. 哪些问题继续留在 research/governance 层，哪些值得 platformize
- **建议阶段路线**：
  - Stage 0：正式承认双 rail 并存（SPX live rail vs Q041 experiment rail）
  - Stage 1：先做 portfolio-state / unified-ledger 抽象，不先改大 UI
  - Stage 2：recommendation 内部分层（candidate set vs selected action）
  - Stage 3：最小组合层 summary surface
  - Stage 4：attribution-first research interface（BP 利用率、idle-day capture、overlap matrix）
  - Stage 5：再决定是否需要统一 multi-book routing
- **明确排除**：
  - 不是大重写 Spec
  - 不立即重做 dashboard
  - 不立即合并 Q041 与 SPX live runtime
  - 不承诺 full multi-underlying joint backtest engine
- **当前归类**：planning item / architecture lane
- **建议下一步**：
  - 先用 Q048 收口 transition plan
  - 暂不直接开 implementation Spec
  - `Q041` 继续按当前 attribution artifact + overlap-monitoring 双轨积累证据
- **参考备忘**：`doc/q048_portfolio_state_architecture_transition_plan_seed_memo_2026-05-07.md`

### Q049 — Multi-Sleeve Read-Only Recommendation & Visualization Surface（由 Q048 收口出的窄实施方向）

- **状态**：ARCHIVED 2026-05-09 — See `doc/open_questions_archive.md#q049` and `RESEARCH_LOG.md` for full research record.

---

### Q044 — BPS spread sizing 与账户级 ROE：当前 10% BP 单笔是否系统性留有过多闲置？

**[已被 Q045 取代 / 2026-05-06]** — Q044 A1 (BPS-only +1.51pp) 是 Q045 J3 NORMAL 维度的真子集。Tier 1/Tier 2 工作作为证据基础保留。

- **状态**：open（research seed / low-medium priority）
- **触发问题**：PM 提出 BPS 在 NORMAL 环境下每笔使用 ≤ 10% 账户 BP，天花板 35%，正常只有一笔 BPS 持仓时结构性闲置 ~25%，是否是"浪费 BP"？能否通过加大 spread width 或合约数来提升账户级 ROE？
- **内容**：
  - 当前参数：`bp_target_normal = 0.10`，`bp_ceiling_normal = 0.35`，SPEC-024 的"2× scale"设计假设同时 2 笔
  - live recommendation 写"Full size — risk ≤ 3% of account"，与 10% BP target 并存但含义不同
  - BPS 是 defined-risk 垂直价差，spread width 直接决定最大亏损，加大规模路径：
    1. 加宽 spread width（如 70pt → 120pt，同样 1 contract）
    2. 加倍合约数（同一 width，2 contracts）
  - 两条路径的 ROE / CVaR / marginal $/BP-day 差异需回测验证
  - 结构性闲置 BP（~25%）与 Q036 Overlay-F 竞争同一资源
- **关键依赖**：
  - Q036 Overlay-F active 决策（目前仍是 shadow）——两者竞争同一闲置 BP，Q036 决策先于 Q044 深入
  - 明确 live PM 账户中 BPS 的 actual Schwab BP consumed（Portfolio Margin 下可能有折扣）
- **初步直觉**：加大 BPS 有 ROE 上行潜力，但 marginal $/BP-day 可能递减（wider spread 的 credit ratio 通常低于窄 spread），尾部绝对亏损额更大
- **明确排除**：不改入场条件（IVP gate / regime / VIX 趋势）；不改 delta 目标（δ0.30/δ0.15）；不改 DTE（30）；不允许 BPS 重叠持仓
- **建议下一步**：Tier 1 Quick Scan（Sonnet，现有回测框架，3 个 width variant），读 marginal $/BP-day 和 worst trade，再决定是否进入 Tier 2
- **当前归类**：seed / 不进活跃队列，等 Q036 shadow observation 结果后再评估是否推进
- **参考备忘**：`doc/q044_bps_sizing_roe_seed_memo_2026-05-06.md`

### Q032 — aftermath broken-wing `V3-C (LC = 0.03)` 是否值得替换当前 `V3-A`
- **状态**：open（monitoring）
- **内容**：MC 已将 aftermath broken-wing 的当前落地形态定为 `V3-A = LC 0.04 + LP 0.08`，`DTE = 45` 不变；`V3-C = LC 0.03` 没有被直接否决，但因为 liquidity concern 被降级为 monitor-and-revisit 候选
- **触发条件**：先积累前 `5–10` 笔 live aftermath；只有当 `V3-A` 的 worst-case 表现满足预期，且 `LC = 0.03` 的流动性观察也可接受时，才重新打开升级评估
- **当前归类**：monitoring only
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q034 — strike rounding `/5 grid` 与 engine 整数 round 的精度漂移
- **状态**：open（低优先级）
- **内容**：MC 提醒当前 engine strike rounding 仍是整数 round，而 live 执行在部分腿上是 `/5` grid；理论上会带来最多 `±2.5` 点的精度漂移。MC 认为这只在 precision execution matching 的场景下才 material，不是当前主线
- **当前归类**：optional / low priority
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q035 — future live-scale backtest engine / RDD
- **状态**：open（长期）
- **内容**：若项目未来希望 backtest engine 直接输出 live-scale 数字，而不是由 `research scale × live_factor` 换算，则需要单独的 live-scale engine architecture / RDD 分支。MC 明确建议暂缓，不要把它作为当前 sync 后的默认下一步
- **当前归类**：long-term / defer by default
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q003 — L3 Hedge 实盘实现（v2）
- **状态**：open
- **内容**：当前 v1 中 L3 实际执行与 L2 相同（全平仓位）；真正的 long put spread hedge 待立新SPEC并验证
- **当前归类**：waiting on dependency / priority decision
- **建议**：ChatGPT review 推荐优先推进
- **来源**：SPEC-026，research_notes §35

### Q004 — `vix_accel_1d` L4 fast-path（COVID类极速崩溃）
- **状态**：open
- **内容**：3日窗口在COVID类5日内极速崩溃中有滞后；`vix_accel_1d` fast-path 可提升响应，但需backtest验证避免日内噪声误触发
- **当前归类**：research only
- **来源**：SPEC-026，research_notes §35

### Q005 — 多仓 trim 精细化
- **状态**：open（中期）
- **内容**：当前 L2/L4 触发时全平所有仓位；多仓扩展后可改为按 shock 贡献排序优先关闭最高风险仓位，提高资本效率
- **依赖**：多仓引擎
- **当前归类**：waiting on dependency
- **来源**：research_notes §35

---

## 信号研究待验证

### Q006 — ADX 辅助确认
- **状态**：open（低优先级）
- **内容**：若 SPEC-020 OOS 期仍有 >20% 误触发，考虑 ADX 作为辅助确认信号
- **依赖**：SPEC-020 RS-020-2 OOS 结果
- **来源**：SPEC-020 §39

### Q007 — Vol Persistence Model（senior quant review §5.2）
- **状态**：open（中期，P3）
- **内容**：高波持续性模型，目前 spell_age_cap 为固定参数，可改为数据驱动
- **来源**：research_notes §5.2

### Q008 — ATR v2（Bloomberg H/L版）
- **状态**：open（低优先级，P5）
- **内容**：当前 ATR 用收盘价差分近似（无需 H/L 数据）；v2 升级到真实 ATR 需 Bloomberg H/L 数据
- **来源**：SPEC-020

---

## DIAGONAL 样本追踪

### Q011 — regime decay DIAGONAL 样本验证
- **状态**：open
- **内容**：DIAGONAL ivp252 ≥ 50 且 ivp63 < 50 区间（regime decay）：n=8，Sharpe +3.56；样本偏小，需真实交易验证后才能确认 SPEC-053 的 DIAGONAL size-up 有效性
- **依赖**：真实交易数据积累
- **来源**：MC Handoff 2026-04-10（新增）

---

## 已解决（存档）

| 编号 | 问题 | 结论 | 解决日期 |
|------|------|------|---------|
| — | Daily portfolio metrics vs trade-level 哪个作为主指标 | Daily portfolio 作为主决策依据，trade-level 保留用于策略族ROM排名 | 2026-04-01 |
| — | Overlay L2 AND还是OR条件 | AND：防止VIX正常上升但组合风险可控时误触 | 2026-04-01 |
| — | book_core_shock 信号路径（freeze触发后的缺陷）| 每日独立计算，不依赖入场路径 | 2026-04-01 |
| — | ATR阈值选择（1.0 vs 其他）| 1.0，gap_sigma分布与原+1%band最接近 | 2026-04-02 |
| Q010 | local_spike DIAGONAL 真实交易 n 计数 | `SPEC-055b` 已实施，`local_spike` 已进入 DIAGONAL full size-up；不再作为前置 open question 追踪 | 2026-04-10 |
| Q014 | 撤销 DIAGONAL Gate 1（`SPEC-049` ivp252 marginal zone） | Quant 已通过 Fast Path 在 `strategy/selector.py` 删除 Gate 1 分支；当前生产逻辑仅保留 Gate 2（`IV=HIGH`）及其余 LOW_VOL + BULLISH 有效规则 | 2026-04-15 |
| Q016 | VIX recovery window dead zone（Dead Zone A 独立方向） | 条件 alpha 验证失败：recovery context 内 `NORMAL + HIGH + BULLISH` BPS 不显著，`SPEC-060 Change 3` 应保持 `REDUCE_WAIT`；后续研究并回 `Q015` / Dead Zone B | 2026-04-18 |
| Q015 | BPS `NORMAL + BULLISH` IVP gate 窄幅放宽（`50 -> 55`） | OOS 验证通过后，Quant 已通过 Fast Path 将 `BPS_NNB_IVP_UPPER` 从 `50` 提高到 `55`；该窄变更已不是 open question，未来若继续研究更广泛 IVP / IC redesign，应作为新问题处理 | 2026-04-19 |
