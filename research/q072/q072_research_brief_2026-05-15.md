# Q072 Research Brief — Sleeve Global Evaluation
## Drawdown Overlay × Aftermath × HV Ladder — Episode-Level BP / Greek / Path Risk

**Date**: 2026-05-15
**Owner**: Quant Researcher
**Status**: Design locked, ready to execute
**Upstream design review**: `task/q072_sleeve_global_eval_design_review_2026-05-15.md` + `_Review.md`（PASS WITH REVISIONS）
**Revisions incorporated**: episode-level overlap、capital stack by pool、Greek path 全重建、blocked-entry counterfactual、two-path scenario decomposition、P4 Aftermath 口径修正

---

## 0. 研究问题

主策略之外的三个 sleeve（Drawdown Overlay / Aftermath / HV Ladder）都在 high vol 或市场承压时启动。

**核心担忧**：同一压力窗口里，多个 sleeve 同时占用 BP、同向承受回撤、并挤压主策略/其它机会。

**必须回答**：
1. 三个 sleeve 是不是同一笔风险换三个名字？（共激活 + entry profile）
2. Sleeve 同时在场时 BP / Greek / drawdown 是分散还是叠加？（capital stack + Greek path + co-loss）
3. 加入完整 sleeve pack 相对 main-only 的 marginal $/BP-day 与尾部代价是否值得？（ablation）
4. Sleeve 在 stress 期是否阻塞主策略入场？（blocked-entry counterfactual）

---

## 1. 三个 Sleeve 现状

| Sleeve | 来源 | 入场触发 | Greek | 状态 | BP pool |
|---|---|---|---|---|---|
| **Drawdown Overlay** | Q042 / SPEC-094(.1) | dd4 lenient / dd15+MA10 reclaim，ATM/+5% call vertical DTE 90 | Long delta / long gamma | Paper trading（自 2026-05-10）| SPX PM |
| **Aftermath**（permission label） | SPEC-064 | VIX peak_10d ≥ 28 且 off-peak ≥ 10%，feed BPS HV | Short vega / short gamma（via BPS HV）| Production | SPX PM |
| **HV Ladder** | Q071 V2f | HIGH_VOL（VIX ≥ 22）+ trend_ok，/ES rolling ladder DTE 49→21，STOP_MULT=15 | Short delta / short vega | Research（Q071 closure 待）| /ES futures (SPAN) |

**两个 pool 物理不互通**：SPX PM pool 容纳 main + Drawdown Overlay + BPS_HV；/ES SPAN 容纳 HV Ladder。Q072 输出必须按 pool 分层，组合层只能用经济意义上的 stress overlay。

---

## 2. Phase 设计

### P1 — Co-activation + Episode-Level Capital Stack

**目标**：识别 sleeve 在时间和资本上的共存模式。

**Stress episode 定义**：连续日 stress flag 为 True，stress flag =
```
VIX ≥ 22
OR SPX drawdown from 20d/60d high ≥ 4%
OR any sleeve active
```
（中断条件：连续 ≥ 3 个 stress flag 为 False 的交易日）

**日级输出**：
- 每日 4 个 boolean: `{main_active, dd_overlay_active, aftermath_active, hv_ladder_active}`
- 共激活矩阵 3×3（sleeve 两两）+ main × sleeve
- 4-way co-occurrence table（16 states × 占比）

**Episode 级输出**：
- `P(≥2 sleeves active within same episode)`
- `P(3 sleeves active within same episode)`
- episode 长度分布（median / max / P95）
- episode-level peak combined BP
- episode-level peak drawdown

**Capital stack 输出（按 pool 分层三张图）**：
- SPX PM pool: main + Drawdown Overlay + Aftermath/BPS_HV daily stacked BP（% NLV）
- /ES futures pool: HV Ladder SPAN margin（% allocated NLV）
- Combined economic stress proxy: SPX PM BP + /ES SPAN normalized to combined NLV

**指标**：average BP / P90 / P95 / peak；peak during stress episodes；days with BP > 30% / 40% / 50% NLV（per pool）。

### P2 — Entry Profile + Regime Clustering

**目标**：判断三个 sleeve 入场是否在 regime 特征上真正错位，还是同一信号的三个名字。

**每次 sleeve 入场打标签**：
- VIX 水平、VIX 10d slope
- SPX 距 20d high 回撤幅度（ddATH）
- IVP_252
- VIX term structure slope（VIX/VIX3M，如可用）
- 距上一次任意 sleeve 入场的间隔天数
- regime label（NEUTRAL / HIGH_VOL / EXTREME_VIX，已有定义）

**输出**：
- 三个 sleeve 的 entry 特征密度叠加图（每维 1 张）
- 聚类分析（k-means / DBSCAN）看入场点是否自然分成 3 簇
- 入场间隔分布（sleeve i fire → sleeve j fire 的天数）

### P3 — Path / Greek / Co-loss Analysis

**目标**：量化 sleeve 同场时 portfolio 真实压力，包含 Greek netting、入场后路径、和情景分解。

#### P3.1 — Post-entry path（每笔 sleeve trade）

- 1d / 3d / 5d / 10d / 20d / exit P&L
- MAE / MFE（开仓后最大不利/有利浮动）
- time to max pain（天数）
- time to recovery（如有）
- entry 当日 portfolio 整体 BP 占用、Greek 暴露

#### P3.2 — Portfolio Greek path 重建（19y 全历史）

**接受重建**（PM 已确认）：

- 逐 trade 重建 portfolio-level Greek（delta / gamma / vega / theta）daily snapshot
- 复用 Q066 co-firing 的 Greek snapshot 逻辑（vol surface 从 IV 历史插值，期权 Greek 用 Black-Scholes 单点估计）
- 输出每日 4 维 Greek 时间序列 + sleeve-attributed Greek（分别按 sleeve 标记贡献）

**特定时点 Greek 快照**：
- sleeve entry 前一日 / 后一日
- 每笔 trade 的 MAE 日
- portfolio daily P&L 最差 5% 的所有交易日
- 每个 stress episode 的 peak BP 日

#### P3.3 — Co-loss 测试

- 4×4 daily P&L 相关矩阵（main + 3 sleeves）
  - 全样本相关
  - **worst-5% 日（按 portfolio total daily P&L）条件相关**
- Co-loss 率：`P(sleeve j P&L < 0 | sleeve i P&L 在 worst 5%)` vs 独立基线
- CVaR 5%：单 sleeve / 任两个组合 / 三 sleeve 全开 / sleeve + main 组合

#### P3.4 — Two-path stress decomposition

历史 stress episode 分类（episode 起始 30d 内 SPX/VIX 路径）：

| Path | 定义 | 预期 sleeve 表现 |
|---|---|---|
| Fast recovery | episode 终止时 SPX ≥ episode 起点，VIX 回落 > 50% from peak | DD Overlay wins, short-vol sleeves likely win |
| Sideways vol crush | SPX 波幅 < ±3%，VIX 从 peak 单调回落 | Aftermath/HV win, DD may decay |
| Second-leg selloff | episode 内出现新 ddATH 低点 | all can lose |
| Pure vol spike | VIX > 30 但 SPX 回撤 < 5% 且快速恢复 | DD weak, short-vol sleeves hurt |

每类 episode 内各 sleeve 平均 P&L、worst trade、Greek path 对比。验证 "Greek 反向是否真 hedge"。

### P4 — Corrected Ablation + Blocked-Entry Counterfactual

**修正口径**：Aftermath 不是 standalone sleeve，是 BPS_HV permission gate。

#### P4A — SPX PM pool ablation

| 组合 | 含义 |
|---|---|
| A | Main only（baseline）|
| B | Main + Drawdown Overlay |
| C | Main + BPS_HV with aftermath permission ON |
| D | Main + Drawdown Overlay + BPS_HV with aftermath permission ON |

**对比**：A→B→C→D 渐进，量化每个组件 marginal 贡献。

#### P4B — /ES pool ablation

| 组合 | 含义 |
|---|---|
| E | HV Ladder only |
| F | SPX pack（D）+ HV Ladder economic overlay（合并 P&L stream，不合并 BP）|

**指标包（standard metrics pack，全部 normalized）**：
- total P&L / Sharpe / max DD / CVaR 5% / worst trade / worst 20d window
- **marginal P&L per incremental BP-day**
- **marginal CVaR per incremental BP-day**
- **marginal drawdown per incremental BP**
- annualized return on average BP

#### P4C — Blocked-entry counterfactual（修订版）

**修订溯源**：本节按 round 2 2nd Quant review (`task/q072_priority_scoring_2nd_quant_review_packet_2026-05-15_Review.md`) 全面重写。原 z-score / 4 维分桶 / `(0.4, 0.4, 0.2)` 公式已废弃。**核心原则**：Eligibility first, priority second，P4C 是 research allocator 非 production 实施。

##### P4C.0 — Step 1: Eligibility Filter（hard overlay）

priority ranking 之前先做 eligibility 过滤，任何不通过的 candidate **不进入 ranking**：

```
candidate passes its own strategy entry rules
AND account-level BP/SPAN cap not breached:
    SPX PM pool BP   <= X% NLV   (initial X=70)
    /ES SPAN         <= Y% NLV   (initial Y=20)
    combined stress  <= Z% NLV   (initial Z=80)
AND sleeve-specific cap not breached:
    DD Overlay combined cap 20% NLV (per SPEC-094)
    Aftermath/BPS_HV exposure cap (initial 15% NLV)
    HV Ladder slot cap (per V2f MAX_SLOTS)
AND portfolio marginal risk acceptable:
    portfolio_CVaR_after - portfolio_CVaR_before <= ΔCVaR_cap
    short-vega notional after entry <= short_vega_cap
    short-delta notional after entry <= short_delta_cap
```

`X/Y/Z` 及 cap 值的初版从 production 现状反推，P4C 内做 sensitivity（±10pp）。

##### P4C.1 — Step 2: Candidate Score（global rank-percentile）

通过 eligibility 的 candidate 进入 ranking。**改用 global rank-percentile，废弃 per-strategy z-score**。

```
return_score = percentile(expected $/BP-day across ALL historical candidates)
tail_score   = percentile(tail_risk_per_BP across ALL historical candidates)

priority = 0.6 × return_score − 0.4 × tail_score
```

**`expected $/BP-day` 与 `tail_risk_per_BP` 的取法**：candidate 入场时刻按 **strategy-specific 2 维 key** 查表，取该桶的 median `$/BP-day` 与 worst trade + |CVaR 5%|；所有 candidate 的两个值合并成全局分布，再算各自 percentile。

**Strategy-specific 分桶 key**：

| Strategy | 分桶 key（2 维）|
|---|---|
| Main BPS NNB / IC | `regime × IVP bucket` |
| Drawdown Overlay (A/B) | `ddATH bucket × VIX bucket` |
| Aftermath / BPS_HV permission | `VIX peak/off-peak state × current VIX bucket` |
| HV Ladder | `VIX bucket × trend_ok / VIX trend` |

分桶具体区间：
- VIX bucket: `[<15, 15-18, 18-22, 22-26, 26-30, 30-40, ≥40]`
- IVP bucket: `[<30, 30-43, 43-55, 55-70, ≥70]`
- regime: `LOW_VOL / NEUTRAL / HIGH_VOL / EXTREME_VIX`
- ddATH bucket: `[<2%, 2-5%, 5-10%, ≥10%]`

##### P4C.2 — Step 3: Confidence Haircut（shrinkage to parent）

```
if bucket_n >= 20:
    use bucket statistic
elif 5 <= bucket_n < 20:
    statistic = 0.5 × bucket + 0.5 × parent strategy distribution
else:  # n < 5
    use parent strategy distribution
```

Aftermath 19y 仅 15 笔 → 大部分 candidate 会落到 parent strategy shrink，这是预期行为，不视为问题。

##### P4C.3 — Step 4: Tie-Break（Tier 仅在真实平手）

```
if abs(priority_i - priority_j) < 5 percentile points:
    apply Tier tie-break
else:
    priority score 主导
```

**Tier 顺序**（refined per reviewer）：
- Tier 1: rare + historically positive + cannot be delayed（Aftermath positive 历史；DD15 stress reclaim）
- Tier 2: high-vol opportunity sleeves（HV Ladder, BPS HV normal）
- Tier 3: repeatable / stable strategies（main BPS NNB, IC, DD Overlay dd4）

稀缺但弱的信号不进 Tier 1。

##### P4C.4 — Step 5: 影子 Trade Lifecycle 与 Counterfactual

- 修改 backtest engine（research 副本，不动 production），每个 entry decision 点：
  - 实际逻辑：通过 eligibility + priority ranking 分配 BP，未中签或不通过 eligibility 的 candidate 跳过实仓
  - 影子记录：未中签 candidate 同时生成 virtual entry（按当时 vol surface 估 size / entry premium / Greek）
- 用历史价格 forward fill 影子 trade 的 lifecycle（forward strike / forward vol / exit per 策略 roll rule）
- 计算影子 trade counterfactual P&L、MAE、Greek 占用
- 归因到具体 blocker：哪个组件（sleeve 或 portfolio cap）那天把它挡掉

**关键产出**：
- blocked trade count（按 blocker × blocked strategy 矩阵）
- blocked trade counterfactual aggregate P&L（"机会成本"）
- blocked trade counterfactual drawdown（"避开的尾部"——也是收益）
- 净 opportunity cost = P&L 机会损失 − drawdown 规避收益
- 阻挡原因分类：eligibility-blocked（BP/cap/CVaR）vs priority-blocked（排名不够）

##### P4C.5 — Step 6: 对照组 + Sensitivity（5 个组合）

| 组 | 规则 |
|---|---|
| A | main-first（production 当前默认）|
| B | sleeve-first（stress 期 sleeve 抢 BP）|
| C | FCFS（先到先得，按 candidate trigger 时序）|
| **D** | **static sleeve caps**（Main 70% / DD 10-20% / Aftermath-BPS_HV 10-15% / HV Ladder 独立 /ES cap）|
| **E** | **priority-based（P4C.0–C.4 完整 stack，主组）**|

跨 5 组对比 portfolio total P&L / Sharpe / max DD / CVaR 5% / blocked-entry 数量与质量 / worst 20d window / realized peak BP。

**Priority 权重 sensitivity**（仅对主组 E）：
- baseline: `(0.6, 0.4)`
- 扰动: `(0.5, 0.5), (0.7, 0.3), (0.4, 0.6)`

##### P4C.6 — Walk-Forward Robustness

单次 train/test split（不做 full rolling）：
```
Train priority tables on 2007–2018
Test allocation on 2019–2026
```
对比 in-sample (全 19y 训练全 19y 评估) vs out-of-sample (2019-2026 评估) 的 P&L / CVaR / ranking 稳定性。若 OOS 显著差于 IS，记为 overfit warning，memo 标注。

##### P4C — 范围声明

**P4C 是 research allocator，不等于 production 实施**。即使结论支持 priority-based，production 采用前需另开 SPEC（含 live BP 监控 / 实时 ranking / fallback 规则）。Q072 memo 只输出 "是否值得开 SPEC" 的判断，不做实施。

---

## 3. 数据源

| 数据 | 路径 | 用途 |
|---|---|---|
| 19y daily VIX + aftermath flags | `research/q064/q064_p1_daily_flags.csv` | P1 episode 检测、Aftermath active 标记 |
| 19y baseline trades（main + BPS_HV）| `research/q042/baseline_19y_trades.csv` | P1 main_active 区间、P3 daily P&L、P4 ablation |
| Drawdown Overlay 触发 + trade list | `research/q062/` + SPEC-094 backtest output | P1/P3/P4 DD Overlay 表现 |
| HV Ladder（V2f）trade list | `research/strategies/ES_puts/backtest.py` 输出（占位用当前 V2f baseline 参数）| P1/P2，**P3/P4 待 Q071 final lock** |
| SPX 历史 OHLC | `data/spx_daily.csv`（已有）| P3 path classification、blocked-entry forward fill |
| IV 历史 surface | `data/iv_surface/`（Q066 用过）| P3.2 Greek 重建 |
| NLV 历史路径 | baseline backtest 输出 | P1 capital stack normalize |

---

## 4. Phase 顺序与 Early Stop / Continue Rules

**严格串行**（PM 确认）：

```
P1 ──► P2 ──► P3 ──► P4
        │      │
        │      └─ skip P3 if P1 shows:
        │           pairwise active overlap <5%
        │           AND episode overlap <10%
        │           AND peak SPX PM BP stack never > 30% NLV
        │
        └─ skip P3.4 scenario decomposition if P2 shows entry profile fully overlap
```

**MUST continue P3 if**：
- episode overlap > 10%
- OR any stress window has ≥ 2 sleeves active
- OR peak BP stack > 30–40% NLV

**HV Ladder 时机**：
- P1/P2：用当前 V2f baseline 参数作占位运行
- **P3/P4**：等 Q071 final memo / SPEC candidate 锁定后再做（避免 trade list 变动导致重做）

**P4 启动门槛**：P1/P3 显示 meaningful overlap / capital competition，或 PM 主动要 sleeve cap rule，或 HV Ladder goes live/paper。

---

## 5. 判断锚点

### P1 共激活率（三层）

| 区间 | 含义 | 行动 |
|---|---|---|
| < 10% | low overlap | 可跳过 P3，转 light monitoring |
| 10–30% | moderate | 必跑 P3 |
| > 30% | meaningful | P3/P4 全套必做 |
| > 50% | high redundancy | 触发 sleeve cap 设计建议 |

### P3 相关性

- **全样本 corr > 0.3 → watch**
- **worst-5% 日 corr > 0.3 → material**
- **co-loss 率 > 独立基线 × 1.5 → material**

### P4 Promote condition（若 PM 用此评估决定 sleeve cap / 优先级）

```
marginal $/BP-day > 0
AND CVaR 不恶化超过阈值（建议：组合 CVaR 5% 恶化 < +20%）
AND worst 20d window 不变差超过 +10%
```

---

## 6. 输出文件清单

```
research/q072/
├── q072_research_brief_2026-05-15.md             ← 本文档
├── q072_p1_episode_detection.py                  ← episode 定义 + 共激活 + capital stack
├── q072_p1_daily_flags.csv                       ← 19y 每日 4-state + episode_id
├── q072_p1_episodes.csv                          ← 每 episode 一行：起止、长度、sleeve 出场顺序、peak BP
├── q072_p1_capital_stack.csv                     ← 19y daily BP stack by pool
├── q072_p1_coactivation_matrix.csv
├── q072_p2_entry_profile.py
├── q072_p2_entries.csv                           ← 每 sleeve 入场一行 + 全部 regime 标签
├── q072_p2_clustering.csv
├── q072_p3_path_greek.py
├── q072_p3_trade_paths.csv                       ← 每 sleeve trade 的 post-entry path
├── q072_p3_portfolio_greeks.csv                  ← 19y daily portfolio Greek + sleeve attribution
├── q072_p3_coloss_matrix.csv
├── q072_p3_scenarios.csv                         ← episode × path-class × sleeve P&L 表
├── q072_p4_ablation.py                           ← P4A + P4B
├── q072_p4_ablation_results.csv                  ← A-F 组合 standard metrics pack
├── q072_p4_eligibility_log.csv                   ← 每个 candidate × day 的 eligibility 通过/blocker 原因
├── q072_p4_priority_lookup.csv                   ← strategy-specific 2维分桶 → global percentile 映射表
├── q072_p4_bp_competition_log.csv                ← 每个 BP 竞争日的 ranking + winner + losers
├── q072_p4_blocked_entries.csv                   ← blocked trade 全列表 + counterfactual P&L（含 eligibility vs priority 分类）
├── q072_p4_opportunity_cost.csv                  ← blocker × blocked strategy 矩阵
├── q072_p4_priority_sensitivity.csv              ← (return_w, tail_w) sensitivity 4 组
├── q072_p4_rule_comparison.csv                   ← A/B/C/D/E 5 组对照（含 static cap）
├── q072_p4_walkforward.csv                       ← 2007-2018 train / 2019-2026 test IS vs OOS 对比
└── q072_memo_<date>.md                           ← 最终 memo（含 PM 决策建议 + production SPEC 提示）
```

---

## 7. 工作量预估（informational only）

| Phase | 工作量 | 备注 |
|---|---|---|
| P1 | 1 天 | 数据已就绪 |
| P2 | 0.5–1 天 | regime 标签 + 聚类 |
| P3.1–3.3 | 1 天 | path + co-loss |
| P3.2 Greek 全 19y 重建 | **1–2 天** | 复用 Q066 Greek snapshot 逻辑，扩展到全历史 daily |
| P3.4 scenario decomposition | 0.5–1 天 | path classifier + per-class 汇总 |
| P4A/B ablation | 1 天 | 4 组 backtest |
| P4C.0 Eligibility filter + portfolio caps 实现 | **0.5 天** | hard ceilings + marginal CVaR check |
| P4C.1 global rank-percentile + strategy-specific 分桶 | **1 天** | 4 套 2 维 key + 全局 percentile 映射 |
| P4C.2 confidence haircut (shrinkage) | **0.5 天** | parent-bucket fallback 逻辑 |
| P4C.3 tie-break + Tier | 0.2 天 | |
| P4C.4 影子 trade lifecycle + counterfactual | **1.5–2 天** | backtest engine 改造 + virtual trade forward fill |
| P4C.5 sensitivity + 5 个对照组（含 static cap） | **1 天** | 5 组 backtest + 权重 sensitivity |
| P4C.6 walk-forward (单次 split) | **0.5–1 天** | 2007-2018 train / 2019-2026 test 对比 IS/OOS |
| Memo + 收口 | 0.5 天 | |
| **合计** | **~11–13 天** | 不分日历日，按工作日估 |

P3/P4（待 HV Ladder lock）约 3.5–5 天可在 Q071 closure 后再做。

---

## 8. 不在范围

- 修改任何生产代码（Q072 全部在 research 层，backtest engine 改造也在 research 副本）
- 重新评估单个 sleeve 自身参数（DD Overlay sizing / Aftermath threshold / HV Ladder DTE 已各自 lock）
- Sleeve-level position cap 的实施 SPEC（若 Q072 结论需要，另开 SPEC-xxx）
- /ES margin pool 与 SPX PM pool 的合并讨论
- 重新触发 Q070 aftermath threshold 讨论

---

## 9. 关键依赖与风险

1. **HV Ladder trade list 占位 → 最终 lock 后需重跑 P3/P4**。P1/P2 用占位结果作 directional reading，不下最终结论。
2. **Greek 重建 vol surface 插值精度**：Q066 已验证插值对短端期权可接受，长端（DTE 90 DD Overlay）精度待 P3.2 入手时再校准。如插值误差 > 10%，需另议方法。
3. **P4C eligibility cap 初值 `X/Y/Z = 70/20/80`**：从 production 现状反推，但 short-vega / short-delta cap 没有现成基准。P4C 入手时先按"历史 P95 短 vega notional × 1.2"作初值，再 sensitivity 验证。
4. **Drawdown Overlay paper trading 数据只有 5 天**（自 2026-05-10），P3 必须依赖 backtest 重放，无 live tape 校准。Memo 需明确这个 caveat。
5. **Walk-forward 单次 split 不足完全证伪 overfit**：P4C.6 只是单次 train/test，若 OOS 显著差于 IS，memo 标 overfit warning，不下 production 建议。Full rolling walk-forward 留 future work。
6. **P4C 是 research allocator，非 production**：即使结论支持 priority-based，production 采用前需另开 SPEC。Q072 memo 输出 "是否值得开 SPEC" 的判断。
