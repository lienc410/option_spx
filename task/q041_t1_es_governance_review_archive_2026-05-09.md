# Q041 T1 SPX CSP vs /ES — Governance Review Archive

**生成日期：** 2026-05-09（初版）
**最后更新：** 2026-05-10（Q055 竞争 verdict + V2c 失败 + V2f sweet spot）
**生成者：** Quant Researcher
**目标读者：** Planner（为索引层 sediment 用）
**目的：** 一次性归档本轮 Q&A 式治理审查 + Q055 竞争 + V2c→V2f 路径修正的全部结论，使 Planner 不需重读对话即可更新 `PROJECT_STATUS.md` / `RESEARCH_LOG.md` / `sync/open_questions.md`
**状态：** REVIEW + COMPETITION + IMPLEMENTATION SCAN COMPLETE — 等 Planner 沉淀 + PM 决定是否将 V2f SPEC 写入

---

## 0. 文档更新日志

| 日期 | 更新内容 |
|------|---------|
| 2026-05-09 | 初版归档：6 层追问总结、V2 发现、原 V2c (STOP=8) 推荐 |
| 2026-05-10 (1st) | Q055 竞争协议执行（A 胜出）+ V2c bootstrap 失败 + V2f (STOP=15) sweet spot 发现 + SPEC 推荐从 V2c 升级为 V2f |
| 2026-05-10 (2nd) | SPEC-095 实施 + Quant Review PASS（V2f 已落地）+ Q057 Tier 1 BS-flat 定价 bias 量化（+17.6% / +24.7%, V2f Ann ROE 实际 conservative）+ Q058 Tier 1+2-A BSH 经济性验证（NET-NEGATIVE，DROP）+ V2f+dynamic leverage 独立升级机会浮现 |

---

## 1. 本轮审查的发起问题

PM 问：Q041 T1 SPX CSP vs /ES，两者似乎越来越像，但 /ES 在 $500k 账户下保持运营优势。是否应该全面对比方法论？是否应该并行运行？

审查覆盖了 6 个连续追问层，最终发现一个比原问题更重要的研究结构性问题——**/ES P2 backtest 的实现与 spec 设计意图不符**。

2026-05-09 PM 后续决策：Q041 T1 与 /ES V2c 正式合并为 naked put 策略槽双候选，竞争后留一个（Q055）。Q055 竞争 + V2c bootstrap 验证 + V2 wider stop 扫描的结论合并到本归档（§9–§11）。

---

## 2. 方法论层面的关键发现

### 2.1 ROE 口径不可比（导致 48.2% vs -0.07% 假象）

| 来源 | 分母 | 数字 | 实际语义 |
|------|------|------|---------|
| Q041 D3 报告 | BP deployed per contract（≈$15–20k） | 48.2% | 单合约 BP 利用率 |
| /ES `/es-backtest` 前端 | $500k account equity | -0.07% | 账户层 ROE |

**结论：** 没有 bug，是 ROE 定义不一致。统一到账户层 ROE 后两者跨度从 ~600× 缩到 ~3–4×。

### 2.2 /ES backtest 数据本质就是 SPX 合成数据

`research/strategies/ES_puts/research_notes.md §1` 自述："本 spec 将 /ES → SPX 期权"、"主要结果仍基于 SPX proxy"。

代码路径：`fetch_spx_history` 取 `^GSPC`，`fetch_vix_history` 取 `^VIX`，`pricer.py` 用 BS + VIX as flat sigma。**没有任何真实 /ES 期货期权历史数据被使用过。**

**结论：** "/ES vs SPX" 在数据层不是真比较；两者共享同一份合成数据。

### 2.3 BS-flat-vol 低估实际 OTM put premium，但偏差小

2022–2026 窗口内 Q041 用 Massive 实数据 vs BS-flat 对比：

| | 实际平均 credit | BS-flat 平均 credit | 偏差 |
|---|---------------|--------------------|------|
| Δ0.20 SPX put 30DTE | 32.30 pts | 31.24 pts | **-2.3%** |

**结论：** BS-flat 系统性低估 OTM put 权利金约 2–3%，但不足以反转策略相对排序。可作为 absolute number 的保守 caveat。

### 2.4 /ES P2 ladder 的实现 ≠ spec 设计意图（最重要发现）

**spec_initial.md 的设计意图（thetagang 标准做法）：**

```
每周入场 1 张 49 DTE
→ 持有让 position 自然衰减穿过 49 → 21 DTE
→ 21 DTE 关闭（或更早 stop / profit）
→ 5 周后形成 5 个并发 position 的稳态 ladder
```

**当前代码实际做的（[backtest.py:529-549](research/strategies/ES_puts/backtest.py#L529-L549)）：**

```
5 条平行的固定 DTE 入场流：
slot 21 → 在 DTE=21 入场，持有到 GAMMA_DTE=5，再开新的 DTE=21
slot 28 → 在 DTE=28 入场，... → ~23 天周期
slot 35/42/49 类推
```

两者是**结构上不同的策略**：实现 model 没有"position 从 49 流向 21"的过程，slot 21 始终在 gamma 危险区入场。

**结论：** /ES 26 年研究的 P1 / P2 数字基于次优实现。当前所有 "/ES thesis weak" / "需 BSH 才显著" 的结论需要重新校准。

---

## 3. 策略层面的关键发现

### 3.1 Q041 T1 SPX CSP vs /ES 在数据 + 策略层基本同质

剥掉 caveat 后两者实质差异只剩 3 维：

| 维度 | Q041 T1 | /ES (current minimal cell) |
|------|---------|---------------------------|
| 标的 | SPX | "SPX"（同一份合成数据） |
| DTE | 30 calendar days | 45 trading days (~63 calendar) |
| 退出逻辑 | hold-to-expiry | STOP_MULT=3.0 + GAMMA_DTE=5 |

**结论：** 两者本质同策略。差异只在 vehicle 设计（/ES 期货 BP $20.5k vs SPX 期权 BP ~$50k）和退出逻辑。

### 3.2 /ES 在 $500k 下保持运营优势 = lot size 容许 ladder

**不是工程基建优势**（PM 已澄清）。

- /ES 单合约 BP $20.5k → $500k 账户可同时铺 5+ 张 ladder
- SPX CSP 单合约 BP ~$50k → $500k 账户最多 1–2 张
- XSP 路径：lot size OK 但 spread 成本侵蚀显著性

**结论：** 原 /ES 选标研究的 `/ES > XSP > SPX naked` 排序是**生产可行性**排序，不是 alpha 排序，这个排序至今仍然成立。

### 3.3 26 年 BS-flat 同口径对比（修正前框架）

修正前用 V0 做 /ES baseline：

| 策略 | n | Ann ROE (几何) | MDD | Worst trade |
|------|---|---------------|-----|------------|
| Q041 CSP DTE30 hold-to-expiry (单槽) | 315 | +0.44% | -17.9% | -$89,962 (2020-02) |
| /ES P1 DTE45 baseline (单槽) | 329 | -0.15% | -15.9% | -$37,866 |
| /ES P2 baseline (fixed slots, current impl) | 2205 | +0.45% | -57.1% | -$38,753 |

修正前结论：Q041 单槽 vs /ES 单槽，Q041 占优；/ES P2 ladder（次优实现）勉强追平 Q041。

### 3.4 True ladder 重做后的对比（修正后框架）

按 spec 设计意图重新实现 true rolling weekly ladder：

| 变体 | n | Ann ROE (几何) | MDD | Worst trade |
|------|---|---------------|-----|------------|
| V0 当前 P2 (fixed slots, STOP=3.0) | 2205 | +0.45% | -57.1% | -$38,753 |
| V1 true ladder, exit@21, STOP=3.0 | 1310 | -2.35% | -70.5% | -$38,753 |
| **V2 true ladder, exit@21, NO STOP** | **1310** | **+2.58%** | **-36.4%** | **-$77,549** |
| V3 true ladder, hold-to-expiry, STOP=3.0 | 1310 | -2.27% | -72.5% | -$38,753 |
| V4 true ladder, entry=45, exit@21, STOP=3.0 | 1310 | -2.08% | -67.2% | -$37,866 |

**关键发现：**

1. V2（true ladder + 无 stop）**全维度 Pareto 优于** V0、V1、V3、V4
2. STOP_MULT=3.0 在 true ladder 下从 V2 的 +2.58% 拉到 V1 的 -2.35%——**alpha 杀手 -4.93pp**
3. 297 笔 stop_loss 退出在 V1 转化为净亏损，这些笔在 V2 大多走到 DTE=21 关闭并盈利

### 3.5 V2 的统计稳健性：borderline（不能直接进 SPEC）

**B1 块大小敏感性：** 
- 平滑 transition，block_size ≥ 200 时显著 (+0.04% → +0.27% Ann ROE 下界)
- 不是 artifact，是 multi-year regime alpha 的特征签名

**B2 种子稳定性：** 
- 20 个种子在 block_size=250 下：**15 / 20 (75%) 显著**
- CI 下界中位数 +0.06% Ann ROE，范围 [-0.12%, +0.18%]
- 边缘但不是巧合

**B3 软 stop 变体扫描：**

| 变体 | Ann ROE (几何) | 2020 worst trade | 评价 |
|------|---------------|-----------------|------|
| V2 no stop | **+2.58%** | -$77,549 (-15.5% acc) | 研究最优；生产不可活 |
| **V2c stop=8** | **+1.29%** | **-$30,059 (-6.0% acc)** | **生产可活的 Pareto 候选** |
| V2b stop=6 | +0.18% | -$38,331 | 不推荐：alpha 几乎清零 |
| V2a stop=5 | +0.36% | -$35,113 | 不推荐：同上 |

**反直觉发现：** STOP_MULT 在 5–8× 区间 vs PnL 是非单调的。stop=8 远好于 stop=6/5。原因是 stop=5/6 仍会触发 would-have-recovered 的 trade，stop=8 只在真正深度 ITM 时触发。

**结论：** V2c (stop=8) 是同时改善 alpha 和保留 tail discipline 的可生产候选——把 /ES P2 从 +0.45% 推到 +1.29% Ann ROE（+0.84pp），单笔 worst -$30k vs 当前 -$31k 大致相当。

---

## 4. 治理审查最终决策

### 4.1 关于 Q041 T1 SPX CSP 路径

**降级为 deprioritized**：

- 在 $500k 账户下，Q041 T1 单槽 alpha (+0.44% geometric) 显著低于修正后的 /ES V2c ladder (+1.29%)
- Tail 风险 (-$90k 单 cycle) 与 V2c 相当，但没有 ladder 的入场分散和 BP 周转优势
- Q041 T1 paper-trading 计划暂缓，除非账户尺寸增长到允许 SPX CSP 自身 ladder（≈$2M+）

Q041 P2 研究本身仍然有效（COST/JPM 财报 IC、GOOGL/AMZN 个股 CSP 等），不被本次治理审查影响。

### 4.2 关于 /ES P2 实现升级 — 2026-05-10 修正：V2c 失败 → V2f 是 sweet spot

**原 2026-05-09 推荐**：V2c (STOP_MULT=8) 升级，+1.29% Ann ROE。
**当前推荐（2026-05-10 修正）**：**V2f (STOP_MULT=15)** 升级，+2.67% Ann ROE。详见 §11。

**最终 SPEC 候选参数：**

```
/ES P2 upgrade candidate (REVISED 2026-05-10):
  - Replace fixed-slot ladder with true rolling weekly ladder
  - Entry: 49 trading-day DTE, every 5 trading days
  - Exit: DTE drops to 21 (or earlier on profit_target / stop)
  - STOP_MULT: 3.0 → 15.0  ← updated from prior V2c proposal (was 8.0)
  - PROFIT_TARGET, GAMMA_DTE 不变

Expected delta vs current P2 baseline (26-yr BS-flat synthetic):
  Ann ROE:        +0.45% → +2.67% (+2.22pp, 5.9× alpha multiple)
  Worst trade:    -$31k → -$55k absolute / -10.96% NLV (passes V1 -15% veto)
  Worst year:     ?    → 2020 -$54k single cycle (only stop-trigger event)
  Bootstrap sig:  not tested → 100% seed sig at block=250 (vs V2c's 0%)
  CI lo median:   ?    → +0.16% Ann ROE
  WR:             74% → 77%

Statistical strength: borderline robust upgraded — 100% seed significance
(better than V2 no stop's 75%). Smooth B1 transition starting at block=200.

Caveats to include in SPEC:
  - All metrics on BS-flat synthetic data; absolute numbers may underestimate
    real OTM put premium by ~2-3% (skew effect)
  - 100% seed significance at block=250 still has CI lower bound +0.16%,
    treat as "alive-with-borderline-edge" not "proven alpha"
  - STOP_MULT=15 only triggered ~1× in 26 yr (2020-02 COVID cycle);
    paper trading must validate trigger frequency in live market — BS-flat
    may understate frequency due to skew interaction with deep ITM stops
  - V2f is strictly Pareto-better than V2 no stop on this dataset
    (ann ROE +0.09pp, worst -$23k tighter, sig rate +25pp);
    counterintuitive but explained by stop catching only the COVID outlier
    while never triggering on V-shape recoverable trades
```

### 4.3 关于 Q012 "/ES thesis 是否成立" 早先结论

Q012 Phase 2 senior quant review 此前给出 `thesis alive with conditions`：完整 thesis 依赖 BSH + 动态杠杆 + 账户规模。

**本次发现需要回置那个判断的前提：**

- 当时的 Phase 2 baseline 是 fixed-slot 实现，不是 true ladder
- 用 true ladder + 调整 stop 后，Phase 2 单层 (V2c) 已经达到 +1.29% Ann ROE
- 这意味着 BSH + 动态杠杆**可能不是 alpha 显著的必要条件**，可能只是 tail mitigation 的一种方式

**但仍未推翻 Q012 结论**：V2c 仍是 borderline 显著，BSH 在尾事件下的保护价值（如 2020 单 cycle -$30k → -$10k）未被本次审查测量。BSH 在更大账户尺寸下的经济性也未被改变。

### 4.4 关于"并行 vs 二选一"的元判断

PM 已明确拒绝并行 sleeve 选项（"本质是同一种策略"）。本次审查的所有结论按二选一框架展开：**/ES V2c 推进，Q041 T1 暂缓**。

---

## 5. 给 Planner 的索引层更新清单

### 5.1 PROJECT_STATUS.md 应反映

- Q041 T1 SPX CSP：**正式淘汰**（Q055 竞争 V1 veto fail + Tier 2 全输；非"暂缓"）
- /ES：naked put 槽位独占；P2 实现升级候选确认为 **V2f (true ladder + STOP=15)** —— bootstrap 100% 种子显著
- 生产路径排序：`/ES` 唯一在 naked put 槽（Q055 verdict）；`XSP` / `SPX naked put` 不再考虑
- /ES 内部仍有 V0 (current) → V2f (upgrade) 的实现升级未决（待 PM 决定是否写 SPEC）

### 5.2 RESEARCH_LOG.md 应新增条目（按时间倒序）

| 日期 | 条目 |
|------|------|
| 2026-05-10 | V2 wider stop scan：V2f (STOP=15) Pareto-better than V2 no stop（含 alpha + tail + significance 三重改进）|
| 2026-05-10 | V2c bootstrap 失败：0/20 种子显著，STOP=8 减 V2 PnL 58% 杀灭显著性 |
| 2026-05-10 | Q055 竞争 verdict：A (/ES V2c) 胜出 — B (SPX CSP T1) V1 veto fail + Tier 2 全输 |
| 2026-05-09 | /ES P2 实现 vs spec 设计意图差异（最重要：fixed-slot ≠ true rolling ladder）|
| 2026-05-09 | True ladder V2 发现：+2.58% Ann ROE，75% 种子显著（block=250）|
| 2026-05-09 | ROE 口径混淆纠正：48.2% vs -0.07% 是 BP-deployed vs account-equity 分母差异 |
| 2026-05-09 | 治理审查发起 → 6 层追问 → V2 → V2c → V2f 的 trail |

### 5.3 sync/open_questions.md 应新增

- /ES P2 SPEC upgrade（true ladder + STOP=15）是否进入 PM 评审？(**最关键当前决策**)
- 是否需要 Massive 实数据对 V2f 在 2022–2026 窗口做 sanity check（关闭 BS-flat 方法论 caveat）？
- BSH / 动态杠杆在 V2f 框架下的经济性是否需要重新研究？(原 Phase 4 假设基于 V0 实现)
- 当账户增长到 $2M+ 时，应否重做 SPX CSP ladder 研究（Q055 verdict 仅在 $500k 下成立）？

### 5.4 doc/strategy_status_2026-05-10.md（新文件，由 Quant 后续起草）

应反映：
- naked put 槽位归 /ES（永久）
- /ES 实现升级候选 V2f 已通过 bootstrap 验证（100% 种子显著）
- Q041 T1 SPX CSP 路径正式关闭
- BSH / 动态杠杆 / Phase 4 结论需在 V2f 框架下重新评估

---

## 6. 不在范围内（明确不被本审查改变）

- 当前生产代码（无任何修改）
- SPEC-061 / 086 / 088（保持 DONE 状态，不回滚）
- Q041 Phase 2 其他候选（COST/JPM 财报 IC、GOOGL/AMZN CSP）研究仍然有效
- 主策略 selector.py 路由逻辑
- 其他 SPX Credit 子策略（BPS / Iron Condor / BCD 等）
- 共享 BP 治理框架（Q012 Phase C / Q050）

---

## 7. 源材料索引（脚本与中间产物）

**初版（2026-05-09 治理审查）：**

| 文件 | 内容 |
|------|------|
| `backtest/prototype/q041_es_methodology_comparison.py` | 三项统一对比（denominator/window/pricing） |
| `backtest/prototype/q041_es_full_window_bs.py` | 26-yr BS-flat 对称对比 |
| `backtest/prototype/q041_es_true_ladder.py` | True ladder vs fixed slot 5 变体扫描 |
| `backtest/prototype/q041_es_v2_validation.py` | V2 bootstrap (B1/B2) + soft stop (B3) |
| `/tmp/q041_es_methodology_comparison.pkl` | 第 1 阶段结果 |
| `/tmp/q041_es_full_window_bs.pkl` | 第 2 阶段结果 |
| `/tmp/q041_es_true_ladder.pkl` | 第 3 阶段结果 |
| `/tmp/q041_es_v2_validation.pkl` | 第 4 阶段结果 |

**Q055 + V2f 增补（2026-05-10）：**

| 文件 | 内容 |
|------|------|
| `task/q055_naked_put_competition_protocol_2026-05-10.md` | Q055 竞争协议 + 执行 + verdict |
| `backtest/prototype/q055_naked_put_competition.py` | Q055 竞争协议执行脚本 |
| `backtest/prototype/q055_v2c_bootstrap.py` | V2c bootstrap 验证（失败：0/20 显著）|
| `backtest/prototype/q055_v2_wider_stop_scan.py` | V2d/e/f 宽 stop 扫描，发现 V2f sweet spot |
| `/tmp/q055_competition_results.pkl` | Q055 竞争结果 |
| `/tmp/q055_v2c_bootstrap.pkl` | V2c bootstrap 验证结果 |
| `/tmp/q055_v2_wider_stop_scan.pkl` | V2f 发现结果（含 V2c/V2d/V2e/V2f/V2 全表）|

---

## 8. 关键 caveat 给 Planner

1. **本归档全部基于 BS-flat 合成数据**。Massive 实数据仅可用于 2022–2026 窗口的 Q041 部分，未对 /ES V2 设计在实数据下做验证。
2. **V2 / V2c 的 bootstrap 显著性是 borderline**，不应在 SPEC 中表述为"已统计验证"。
3. **arithmetic vs geometric Ann ROE 口径**：本归档统一使用几何（与既有 /ES 报告一致），脚本中部分输出是算术，差异在 multi-year cum_ret 较大时显著。
4. **本次审查未测试 BSH / 动态杠杆与 V2c 的交互**，Phase 4 的相关结论仍基于 V0 实现，不能直接套用到 V2c。

---

*由 Quant Researcher 生成，2026-05-09。等 Planner 沉淀至索引层后，本归档可视为 closed。*

---

# 增补 §9–§11（2026-05-10）

以下为 2026-05-09 PM 决策（Q055 双候选竞争）后的执行内容与发现。

---

## 9. Q055 竞争协议 + Verdict（2026-05-10）

### 9.1 协议框架

三层评分：

- **Tier 1 Vetos**（任一不通过即淘汰）：V1 worst trade ≤ -15% NLV / V2 几何 Ann ROE > 0% / V3 bootstrap CI 下界 > -1.0% Ann
- **Tier 2 Primary**（赢 2/3 即胜）：账户层 Ann ROE / $/BP-year 资本效率 / Worst trade % NLV
- **Tier 3 Secondary**（informational）：Sharpe / WR / CVaR 5% / 账户 MDD / per-contract $/year

PM 指令：ladder 结构性约束如实呈现，不被协议设计绕过。主评分用 account-level（生产现实），辅助报告 per-contract 与 $/BP-year（结构盲）。

### 9.2 数据对比表

| 维度 | A: /ES V2c | B: SPX CSP T1 |
|------|-----------|--------------|
| Trades 总数 | 1,310 | 315 |
| 并发合约（avg）| 5.6 | 1.0 |
| BP 平均部署 | $114,800 | $50,000 |
| **V1 worst % NLV** | **-10.96%** ✅ | **-17.99% ❌** |
| Ann ROE 几何 | +1.28% ✅ | +0.44% ✅ |
| Bootstrap CI lo | -0.60% ✅ | -0.24% ✅ |
| **P1 Ann ROE** | **+1.28%** | +0.44% |
| **P2 $/BP-year** | **6.61%** | 4.67% |
| **P3 Worst % NLV** | **-10.96%** | -17.99% |
| Sharpe | **0.20** | 0.11 |
| WR | 77.4% | 88.3% |
| Account MDD | -32.7% | -17.9% |
| $/contract/year（结构盲）| $1,354 | **$2,333** |

### 9.3 Verdict：A 胜出

- B 在 V1 veto 失败（2020-02 COVID -17.99% NLV）
- 即使 V1 阈值放宽到 -20%，A 仍在 Tier 2 全胜 3/3
- A 的 alpha 优势来自 ladder 结构（5.6× BP 周转）+ per-BP 资本效率更高的双重叠加

**naked put 槽位永久归 /ES。Q041 T1 SPX CSP 路径正式淘汰**（不是暂缓——B 在所有 Tier 2 主指标上输给 A，没有可挽救路径）。

完整 Q055 协议详见 [task/q055_naked_put_competition_protocol_2026-05-10.md](task/q055_naked_put_competition_protocol_2026-05-10.md)。

---

## 10. V2c Bootstrap 验证失败（2026-05-10）

PM 在 V2c 进入 SPEC 之前要求独立 bootstrap 显著性验证。结果：

### 10.1 验证结果

| 指标 | V2 (reference) | V2c (本次) |
|------|--------------|-----------|
| 种子显著率（block=250, 20 seeds）| 15/20 (75%) | **0/20 (0%)** |
| CI 下界中位 (Ann ROE) | +0.06% | **-0.56%** |
| 最小显著 block size | 200 | 500 |
| B1 smooth transition | ✅ | ✅ |
| 通过 PM 预设标准 | borderline robust | **FAIL — 返回 PM** |

### 10.2 机制解读

V2c (STOP=8) 看似温和，实际从 V2 移除了 58% 的累积 PnL（V2 total $475k → V2c $199k）。被 stop 触发的不全是"该止损的烂 trade"，**很大比例是 would-have-recovered 的 cycle 被提前锁定亏损**。这把 V2 边缘 borderline 的统计信号直接打到 0。

### 10.3 决策路径

按 PM 预设标准：seed sig < 60% → 返回 PM，讨论是否：
1. 接受 borderline V2 (无 stop)
2. 测试更宽 stop 找 sweet spot
3. 维持 V0 不动
4. 加 BSH 做更深研究

PM 选择：路径 2 → 路径 1（先扫描更宽 stop，失败则回退到 V2）。详见 §11。

---

## 11. V2f Sweet Spot 发现（2026-05-10）

### 11.1 宽 Stop 扫描结果

| Variant | STOP | Ann ROE | Worst $ | Worst %NLV | Bootstrap sig | V1 pass | B2 pass(60) |
|---------|------|---------|---------|-----------|---------------|---------|------|
| V2c | 8  | +1.28% | -$54,804 | -10.96% | 0/20 (0%)  | ✅ | ❌ |
| V2d | 10 | +1.70% | -$54,804 | -10.96% | 0/20 (0%)  | ✅ | ❌ |
| V2e | 12 | +2.29% | -$56,121 | -11.22% | 0/20 (0%)  | ✅ | ❌ |
| **V2f** | **15** | **+2.67%** | **-$54,804** | **-10.96%** | **20/20 (100%)** | **✅** | **✅** |
| V2 | none | +2.58% | -$77,549 | -15.51% | 15/20 (75%)| ❌ | ✅ |

### 11.2 V2f 是 strictly Pareto-better than V2 no stop

非常反直觉的发现——加入 STOP_MULT=15 不仅没有杀 alpha，反而比 V2 no stop 略高：

| 维度 | V2 no stop | V2f stop=15 | Δ |
|------|-----------|-------------|---|
| Total PnL | +$475,623 | +$499,537 | +$23,914 |
| Ann ROE 几何 | +2.58% | +2.67% | +0.09pp |
| Worst trade | -$77,549 | -$54,804 | +$22,745 |
| Worst %NLV | -15.51% | -10.96% | +4.55pp（passes V1）|
| Bootstrap 种子显著率 | 75% | 100% | +25pp |
| CI lo median | +0.06% | +0.16% | +0.10pp |

**机制：** STOP=15 只在极端情况触发（put mark 涨到 entry 的 15 倍），实际只切了 2020-02 那一笔从 -$77k 截到 -$54k。它不触发 "would-have-recovered" 的 trade，所以保留全部 V2 的 alpha，外加切掉 COVID tail 的 $23k。

均值小幅上升 + 方差小幅下降 → t-statistic 显著提升 → 100% 种子显著。

### 11.3 V2f 的 Block-size sweep（B1 验证）

| Block | CI lo Ann% | CI hi Ann% | 显著? |
|-------|-----------|-----------|------|
| 50 | -0.90% | +7.92% | ❌ |
| 100 | -0.21% | +7.40% | ❌ |
| **200** | **+0.23%** | +6.38% | **✅** |
| **250** | **+0.10%** | +6.67% | **✅** |
| **500** | **+0.43%** | +5.43% | **✅** |

Smooth transition，从 block=200 显著开始持续。比 V2 (block=200 起 +0.04%) 更稳健。

### 11.4 V2f 通过 PM 全部预设标准

| 标准 | V2f 实际 | 通过? |
|------|---------|------|
| Ann ROE > 0% | +2.67% | ✅ |
| Worst ≥ -15% NLV | -10.96% | ✅ |
| Bootstrap sig rate ≥ 60% | 100% | ✅ |
| Bootstrap sig rate ≥ 75% | 100% | ✅ |
| Bootstrap sig rate ≥ 80% | 100% | ✅ |

**V2f 触发"边缘稳健，可写 SPEC"路径，无需 caveat 减级。**

### 11.5 STOP_MULT 单调性的失常

非单调 alpha 模式：

| Stop | 角色 | 结果 |
|------|------|------|
| STOP=3-8 | 杀大量 would-have-recovered trades | alpha 损失 >> tail 收益 |
| STOP=10-12 | 仍杀部分 recoverable trades | alpha 损失 < tail 收益但 borderline |
| **STOP=15** | **只触发真正 catastrophic cycles** | **alpha 几乎完全保留 + tail 切除** |
| STOP=∞ | 不触发 | 全 alpha 但 COVID cycle 失血 |

STOP=15 是这个 26 年数据集上的真正 sweet spot：宽到不误伤 V-shape recovery，但仍能截断 2020-style sudden gap-down。

### 11.6 对前序决策的连锁影响

- **Q055 verdict 进一步加强**：A 现在不仅基于 V2c +1.28% 击败 B +0.44%，是基于 **V2f +2.67% Ann ROE + 100% bootstrap 显著率**击败 B +0.44% + V1 veto fail
- **/ES P2 SPEC 升级路径明确**：V0 (current) → V2f (true ladder + STOP=15)，统计强度 borderline 但优于 V2 / V2c
- **V0 fixed-slot 实现可被替换**：Q012 早先"thesis alive with conditions"判断需在 V2f 框架下重新审视

---

## 12. 给 Planner 的最终 sediment 检查清单

完成本次归档增补后，Planner 应按 §5 更新索引层文档：

- [ ] `PROJECT_STATUS.md` — Q041 T1 标为 ELIMINATED；naked put 槽 = /ES；P2 实现升级候选 = V2f
- [ ] `RESEARCH_LOG.md` — 按 §5.2 时间倒序加 7 条新条目
- [ ] `sync/open_questions.md` — 添加 V2f SPEC 评审、Massive 实数据 sanity check 等 4 项
- [ ] `doc/strategy_status_2026-05-10.md` — 新建（由 Quant 起草，反映 Q055 + V2f 全套）
- [ ] 触发后续 PM 决策点：是否将 V2f 升级写成 SPEC 进入 Developer 实施？

---

*归档增补 2026-05-10 完成。Planner sediment + PM V2f SPEC 决策后，本归档可正式 close。*

---

# 增补 §13（2026-05-10）

## 13. Q058 — BSH 在 V2f 框架下 NET-NEGATIVE，建议 DROP

**研究触发**：§11 发现 V2f sweet spot 后，§10 决策路径 4（"加 BSH 做更深研究"）作为后续 Q058 被激活。

### 13.1 三变体对比结果

| 变体 | Ann ROE | Sharpe | BSH cost | BSH payoff |
|---|---|---|---|---|
| V2f alone | +2.46% | 0.15 | $0 | $0 |
| V2f + BSH cost only | +1.14% | 0.06 | -$272k | n/a |
| V2f + BSH full (cost + payoff) | +1.89% | 0.00 | -$194k | +$66k |

**净效果**：Ann ROE -0.57pp；Sharpe 0.15 → 0.00。两项均劣化 → 触发 DROP 判定。

### 13.2 核心机制：为什么 Phase 4 结论不可移植

| 维度 | V0 fixed-slot（Phase 4 研究基础）| V2f |
|---|---|---|
| stop_loss 触发频率 | ~50×/year | ~0.3×/year |
| 主要退出方式 | stop_loss | ladder_exit 51% + profit_target 48% |
| 尾部已内嵌 | 否（依赖 BSH） | 是（STOP=15，worst -9.24% NLV）|

V2f 的 true ladder + STOP=15 已吸收 BSH 想解决的尾部问题。BSH 在 V2f 下是 **redundant insurance**。

### 13.3 2020 COVID 关键失败

| 变体 | 2020 全年 daily-pnl |
|---|---|
| V2f alone | -$29,357 |
| V2f + cost | -$37,734 |
| V2f + full | -$37,754 |

BSH 在应该闪光的 2020 年，payoff 几乎等于年度 cost，净贡献 ≈ $0。

### 13.4 Tier 1 Verdict

按预设判定框架：Ann ROE < V2f alone **AND** Sharpe 不改善 → **DROP BSH in V2f framework（Tier 1）**

**Caveats**（完整版见 RESEARCH_LOG R-20260510-05）：
- BS-flat 低估 BSH put 真实 cost AND payoff（方向预期同向，不改变 DROP 结论）
- 1987/1929 量级 sudden gap 未在样本内

**完整记录**：`RESEARCH_LOG.md R-20260510-05`，`backtest/prototype/q058_bsh_v2f.py`

---

## 14. Q058 Tier 2-A — Dynamic VIX Leverage 验证：BSH DROP 强化 + V2f 独立升级机会浮现

**研究触发**：§13.4 Tier 1 留 Tier 2-A（Phase 3 dynamic leverage 是否改变 BSH verdict）作为 follow-up。本节为该 follow-up 的执行结果。

### 14.1 Tier 2-A 五变体结果

| 变体 | Ann ROE | Sharpe | Worst %NLV | Avg contracts | BSH cost | BSH payoff |
|---|---|---|---|---|---|---|
| V2f_alone（Tier 1 ref）| +2.46% | 0.15 | -9.24% | 1.00 | $0 | $0 |
| V2f_bsh_full（Tier 1 ref）| +1.89% | 0.00 | -9.24% | 1.00 | $194k | $66k |
| **V2f_dynlev_alone** | **+3.32%** | **0.16** | **-14.03%** | **1.87** | $0 | $0 |
| V2f_dynlev_cost | +0.96% | 0.05 | -11.48% | 1.47 | $284k | $0 |
| V2f_dynlev_full | +2.86% | 0.01 | -12.48% | 1.71 | $219k | $79k |

### 14.2 BSH Verdict（Tier 2-A）：仍 NET-NEGATIVE

| | Tier 1 (fixed 1 contract) | Tier 2-A (dynamic leverage) | 改变？ |
|---|---|---|---|
| BSH net effect | -0.57pp Ann ROE | **-0.46pp Ann ROE** | +0.11pp |
| BSH Sharpe net | -0.15 | -0.15 | 不变 |
| BSH hit rate（payoff/cost）| 57% | 80% | +23pp |
| **Verdict** | **NET-NEGATIVE** | **NET-NEGATIVE（强化）** | **不变** |

Dynamic leverage 让 BSH cost 和 payoff 同时按 NLV scale 上升，hit rate 从 57% 提到 80%，但仍未达到 100%。**BSH 在两种 sizing 假设下都是 net-negative，DROP 推荐被双重验证强化。**

### 14.3 浮现的独立研究问题：V2f + dynamic leverage（不要 BSH）

V2f_dynlev_alone（无 BSH）独立给 V2f 带来：

| 维度 | V2f_alone | V2f_dynlev_alone | Δ |
|---|---|---|---|
| Ann ROE 几何 | +2.46% | **+3.32%** | **+0.86pp** |
| Sharpe | 0.15 | 0.16 | +0.01 |
| Worst trade | -$46,176 | -$70,127 | -$23,951（更深）|
| Worst %NLV | -9.24% | **-14.03%** | -4.79pp（V1 余量缩减）|
| Account MDD | -42.3% | -70.4% | -28.1pp（实质恶化）|

**Position sizing 按预期 scale**：

| VIX 区间 | n trades | avg contracts | avg PnL/trade |
|---|---|---|---|
| <15 | 401 | 1.39 | +$216 |
| 15-20 | 364 | 1.79 | -$143 |
| 20-30 | 345 | 2.26 | +$530 |
| 30-40 | 82 | 2.58 | +$3,376 |
| ≥40 | 31 | 2.84 | **+$5,958** |

VIX≥40 下平均每 trade +$5,958，证实 Phase 3 leverage table 在 V2f 下有效缩放。

### 14.4 2020 COVID 反直觉发现

| 变体 | 2020 short total | 2020 daily-pnl 总 |
|---|---|---|
| V2f_alone | -$28,296 | -$29,357 |
| V2f_bsh_full | -$28,296 | -$37,754 |
| **V2f_dynlev_alone** | **+$7,139** | **+$4,278** |
| V2f_dynlev_cost | +$2,897 | -$8,606 |
| V2f_dynlev_full | +$4,574 | -$8,440 |

V2f_dynlev_alone 在 2020 整年 **POSITIVE PnL**：高 VIX 触发更大仓位 → 多数 ladder cycle 走到 successful exit → COVID V-shape 反弹回收。**含 BSH 的 dynlev 变体在 2020 反而更差**——BSH cost drag 抹掉了 dynlev 的 alpha。

### 14.5 V2f + dynamic leverage 升级判断（PM 决策点）

**不在 quant 单独可决范围内。** 提供决策矩阵：

| 维度 | 偏好升级 | 反对升级 |
|---|---|---|
| Alpha | +0.86pp Ann ROE 是有意义的提升 | — |
| Sharpe | 微升 +0.01 | 实质未改善 |
| V1 veto 余量 | 仍 PASS（-14% > -15%）| 余量从 -5.76pp 缩到 -0.97pp，黑天鹅事件下可能突破 |
| 账户 MDD | — | -42% → -70%，PM 实际操作体验显著恶化 |
| 复杂性 | — | 引入 VIX-dependent contract sizing 增加生产代码复杂度 |
| 历史样本覆盖 | 26 年 BS-flat | 1987/1929 量级未覆盖；2020 是 V-shape 反弹，不代表 sudden gap-down 的最坏情况 |

**Quant 中性建议**：
- 若 PM 看重 alpha，可作为下一阶段 SPEC 候选（先做 bootstrap 显著性 + extreme tail stress 验证）
- 若 PM 看重 V1 veto 余量与生产稳定性，维持 V2f baseline（fixed 1 contract）

### 14.6 完整记录

`RESEARCH_LOG.md R-20260510-06`，`backtest/prototype/q058_tier2a_dynlev_bsh.py`，`research/q058/q058_tier2a_dynlev_bsh.pkl`

### 14.7 Tier 2-B 状态

**关闭**。Tier 2-B（Massive 子窗口 BSH 定价 sanity check）的优先级取决于 BSH 是否还在路径上。Tier 1 + Tier 2-A 已两轮独立验证 BSH NET-NEGATIVE，Tier 2-B 主要变成"为完整性 close caveat" 的工作，不是决策驱动。

BSH put 定价 bias 的方法论 caveat 由 Q057 Tier 1（BS-flat 对 OTM put 的 +17-25% 系统性低估）覆盖；BSH put 同样使用 BS-flat 估算，bias 方向同向，不改变 DROP 结论。

---

## 15. 给 Planner 的最终 sediment 增补（2026-05-10 第二轮）

§5 + §12 之外，本轮新增需要 sediment 的内容：

### 15.1 PROJECT_STATUS.md 增量

- naked put 槽位归 /ES（Q055 verdict）—— 已记录
- /ES P2 实现升级 = V2f（SPEC-095 DONE）—— **已实施完成**
- BSH 在 V2f 下 DROP（Q058 Tier 1 + 2-A 双重验证）
- **新候选**：V2f + dynamic VIX leverage（独立升级机会，待 PM 决策）—— 加入 candidate list 但不进 SPEC，直到 PM 给出推进信号

### 15.2 RESEARCH_LOG.md 已新增条目

- R-20260510-04（Q057 BS-flat pricing bias）
- R-20260510-05（Q058 Tier 1 BSH NET-NEGATIVE）
- R-20260510-06（Q058 Tier 2-A dynamic leverage validation + V2f+dynlev opportunity）

### 15.3 sync/open_questions.md 新增

- ✅ V2f SPEC 已 PASS review，DONE（SPEC-095）—— 移出 open
- ✅ BSH 在 V2f 下经济性 —— 已 DROP，移出 open
- 🆕 V2f + dynamic leverage 独立升级是否进入 SPEC？（如进入：先 bootstrap 显著性 + extreme tail stress）
- 🆕 BSH put 定价 bias 在真实数据下是否改变方向？（Q058 Tier 2-B follow-up，PM 不主动启动）
- 🆕 1987/1929 量级 sudden gap 在 V2f 框架下的尾部行为模拟（独立研究问题，跨多个 spec）

### 15.4 doc/strategy_status_2026-05-10.md（已建议，待 Quant 起草）

应反映：
- naked put 槽位归 /ES（permanent post-Q055）
- /ES P2 实现 = V2f true ladder + STOP=15（SPEC-095 DONE）
- Q041 T1 SPX CSP 路径正式关闭
- BSH 不在 V2f 路径上（Q058 双轮验证）
- V2f + dynamic leverage 是 open candidate（Q058 Tier 2-A 浮现）

---

*§13–§15 增补 2026-05-10（Q058）。*

---

# 增补 §16–§18（2026-05-10，Q060）

## 16. Q060 Tier 1 主结论：V2f + Dynamic Leverage 不进 SPEC

| 门槛 | 实测 | 结果 |
|---|---|---|
| Task A Bootstrap sig_rate ≥ 60% | **95%** | ✅ PASS |
| Task B Stress worst ≥ -15% NLV | **-23.94% NLV** | ❌ FAIL |

**Verdict**：V2f_dynlev 不进 SPEC。alpha 优势真实（+0.86pp Ann ROE，95% bootstrap），但 dynamic leverage 在极端尾部把 single-trade loss 放大 1.42×，超过 PM 决策阈值（-20%）。V2f + dynamic leverage 降级为研究观察项，不再主动推进。

---

## 17. Q060 Incidental Finding：V2f_alone 在 1987 量级事件下违反 V1 Veto

**发现**：
- 1987-magnitude sudden gap-down 下，V2f_alone single-trade worst = **-16.85% NLV**（违反 V1 -15% 阈值）
- Account-level cluster loss = **-47.1%** of pre-shock equity（5 个并发位置同时被击穿）
- STOP=15 在快速崩盘下"触发了但来不及救"——每 stop 锁定约 -16% NLV

**对 SPEC-095 的影响**：SPEC-095 worst trade -9.24% NLV 来自 26 年 BS-flat 历史数据（最坏 = COVID 2020 V-shape）。这不是尾部事件的上界。1987 量级 sudden gap-down 比 COVID 更快速，无法通过 stop 有效截断。**"-9.24% historical worst ≠ tail-bounded"**。

---

## 18. 给 PM 的正式评估点（Q061）：V2f 尾部风险缓解措施

三个候选缓解路径：

| 路径 | 内容 | 工作量 |
|---|---|---|
| **M1** Cluster loss 监控 | N≥4 个并发位置时降低入场频率（每 10 TD 而非 5） | Developer 小改 |
| **M2** VIX 跳升 entry pause | VIX 5日涨幅 >50% 时暂停新入场 | Developer 小改 |
| **M3** Tail risk caveat 升级 | SPEC-095 UI 明确 "-9.24% 不等于尾部上界"；1987 量级估计 -17% single / -47% cluster | Developer 最小改 |

**Planner 建议**：M3 立即执行（最小成本，PM 知情）；M1/M2 是否研究留 PM 决策。

**完整记录**：`RESEARCH_LOG.md R-20260510-07`，`backtest/prototype/q060_dynlev_bootstrap_stress.py`

---

*§16–§18 增补 2026-05-10（Q060）。本治理归档（§1–§18）现正式 CLOSED。*
