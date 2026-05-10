# Strategy Status Snapshot — 2026-05-10

**生成者**：Planner  
**目的**：本轮治理审查（Q041 T1 vs /ES，2026-05-09 起）的正式收口文件。记录所有关键策略决策的最终状态，供未来 Quant review 和 PM 决策参考。  
**参考归档**：`task/q041_t1_es_governance_review_archive_2026-05-09.md §1–§18`（完整研究记录）

---

## 1. Naked Put 策略槽位归属（永久决定）

**结论：naked put 槽位永久归 /ES。Q041 T1 SPX CSP 路径正式关闭。**

| 候选 | 结论 | 原因 |
|---|---|---|
| **/ES V2f**（真正滚动周梯形，STOP=15）| **胜出，独占 naked put 槽** | V1 veto PASS（historical worst -9.24% NLV）；bootstrap 100% seeds 显著；Ann ROE +2.46%（geometric, BS-flat 26yr） |
| Q041 T1 SPX CSP Δ0.20 DTE30 | **正式淘汰**（非暂缓）| V1 veto FAIL（2020 COVID worst -17.99% NLV > -15%）；Tier 2 主指标全负于 /ES V2f |

竞争协议（Q055）执行日期：2026-05-10。结论在 $500k 账户下成立。重议触发条件：账户 NLV ≥ $2M（Q059）。

---

## 2. /ES V2f 当前实现状态

### 2.1 已落地

| 内容 | 状态 | SPEC |
|---|---|---|
| True rolling weekly ladder（entry=49TD，exit@21TD，STOP_MULT=15）backtest 层实现 | ✅ DONE | SPEC-095 |
| `/api/es-backtest/v2f` 端点 + `/es-backtest` V2f tab（V0 vs V2f 对比）| ✅ DONE | SPEC-095 |
| V2f tail risk warning（-17% single / -47% cluster，1987 量级）| ✅ DONE | SPEC-096 |

### 2.2 进行中

| 内容 | 状态 | SPEC |
|---|---|---|
| M1 Cluster Throttle（N≥4 并发时入场频率 5→10 TD）| APPROVED，Developer 实施中 | SPEC-097 |

### 2.3 关键性能指标（BS-flat 26yr，baseline mode）

| 指标 | V2f（SPEC-095）| V2f + M1（SPEC-097 目标）|
|---|---|---|
| Ann ROE 几何 | +2.46% | +2.35% |
| Sharpe（daily-return annualized）| 0.22 | 0.23 |
| Historical worst % NLV | -9.24% | -10.96% |
| 1987 stress worst single % NLV | -16.85%（违 V1）| -15.13%（V1 近似恢复，剩 0.13pp 缺口）|
| 1987 stress cluster % equity | -47.12% | -44.07% |
| Bootstrap sig_rate（block=250, 20 seeds）| 100% | 继承（M1 仅改入场 cadence，不改 trade-level distribution 结构）|

**口径注**：
- Ann ROE 几何 = (final_eq / start_eq)^(1/yrs) − 1。q055 wider-stop sweep 用算术口径报 +2.67%（archive §11），与 +2.46% 仅差 21bp 算术-几何换算。本文档统一使用几何口径
- Sharpe 0.22 来自 [metrics_portfolio.py](backtest/metrics_portfolio.py:52) 风格的 daily-return annualized；早期 Q058 archive 报 Sharpe 0.15 是 trade-level 口径，两者不可直接对比
- V2f Historical worst -9.24% 来自 Q061 [run_v2f()](backtest/prototype/q061_m1_m2_alpha_impact.py) baseline；q055 wider-stop sweep 报 worst -10.96%（archive §11）—— 不同 simulator 在同一 sim_df 下 worst trade 取值微差，本文档采用 Q061 实测
- V2f+M1 Historical worst -10.96% 是 Q061 实测：M1 把 entry cadence 由 5TD 延至 10TD，concurrent 配置变化导致 single-trade worst 略深，但仍 V1 PASS

### 2.4 生产代码状态

**零改动**：SPEC-061（/ES live bot）/ SPEC-086（credit stop monitor）/ SPEC-088（SPAN visibility）均保持 DONE 状态。所有 V2f 工作在 backtest 研究层，未进入生产执行路径。

---

## 3. BSH（Black Swan Hedges）在 V2f 框架下的结论

**结论：DROP。BSH 在 V2f 框架下 NET-NEGATIVE，不推荐。**

| 研究 | 结果 |
|---|---|
| Q058 Tier 1（fixed 1-contract）| Ann ROE -0.57pp（+2.46% → +1.89%）；Sharpe 0.15→0.00（trade-level 口径）；26yr 累计 BSH cost -$260k，cumulative payoff +$66k；2020 COVID 期间 V2f+full PnL -$37,754 vs V2f alone -$29,357（BSH 净亏 $8k）|
| Q058 Tier 2-A（dynamic leverage）| Ann ROE -0.46pp；BSH hit rate 由 57% 升至 80% 但仍未 break-even；DROP 结论强化 |

**机制**：V2f 的 true ladder + STOP=15 已内嵌 Phase 4 BSH 想解决的尾部问题。多数 trade 走完整 49→21 DTE ladder cycle 自然退出（stop_loss 触发率 ~0.3×/yr vs Phase 4 的 ~50×/yr）。BSH redundant。

原 Phase 3/4 结论（基于 V0 fixed-slot）不可移植到 V2f。

---

## 4. Dynamic VIX Leverage 在 V2f 框架下的结论

**结论：Alpha 真实但尾部不可接受，不进 SPEC。**

| 指标 | V2f alone | V2f + dynlev |
|---|---|---|
| Ann ROE | +2.46% | +3.32%（+0.86pp）|
| Bootstrap sig_rate | 100% | 95% |
| 1987 stress single | -16.85% NLV | **-23.94% NLV**（超 PM -20% 阈值）|

Dynamic leverage 在极端尾部将 single-trade loss 放大 1.42×。V2f + dynamic leverage 降级为研究观察项（Q060 CLOSED）。

---

## 5. V2f 尾部风险已知边界

**重要**：SPEC-095 历史 worst -9.24% NLV 基于 26yr BS-flat 数据（实际最坏事件 = COVID 2020 V-shape）。

1987 量级 synthetic stress test（Q060）结果：
- **V2f alone**：single-trade worst -16.85% NLV（违 V1 -15%），cluster -47.1%
- **V2f + M1**：single-trade worst -15.13%（V1 近似恢复），cluster -44.1%

"-9.24% historical worst ≠ tail-bounded"。SPEC-096 已在 UI 显式披露。

---

## 6. Q041 研究线当前状态

| Tier | 状态 | 说明 |
|---|---|---|
| **T1 SPX CSP** | ❌ **正式淘汰**（2026-05-10）| Q055 竞争 V1 veto FAIL；naked put 槽永久归 /ES |
| **T2 GOOGL/AMZN CSP** | 🟡 Paper-trading active（tail-caveated）| 2nd Quant review：缺 COVID tail 数据，explicit caveat 要求 |
| **T3 COST/JPM IC** | 🔵 Observe-only | Q055 不影响 Tier 3 |

前端 `/q041` 和 `/q041/backtest` 页面已按此状态实现（SPEC-093 DONE）。

---

## 7. 方法论层面已确定的 Caveats（需在未来所有 /ES review 中显式列出）

1. **BS-flat 低估真实 OTM put premium +17-25%**（Q057：full window +17.57%；V2f 实际 DTE 区间 +24.71%）——V2f 真实 Ann ROE 估计 +3.0-3.5%（方向有利，数字偏保守）
2. **"historical worst ≠ tail-bounded"**——1987 量级 sudden gap-down 估计 V2f single -17% / cluster -47%
3. **全部研究基于 BS-flat 合成数据**——没有任何真实 /ES 期货期权历史数据被使用；数据源是 SPX 合成期权定价
4. **BSH / dynamic leverage 在 V2f 下的经济性已测，DROP**——Phase 3/4 结论不可移植

---

## 8. 下一个决策触发条件

| 触发 | 内容 |
|---|---|
| 账户 NLV ≥ $2M | Q059：重做 /ES V2f vs SPX CSP ladder 竞争 |
| 首次 live HIGH_VOL trigger（VIX ≥ 22）| Quant 回放 Q042 F4 backfill 重验 delta |
| Q019 Signal 2 第 1 月（2026-06-09）| Quant 跑 Signal 1 vs Signal 2 对照统计 |
| Q042 6-month paper（2026-11-10）| Sleeve A/B realized WR vs baseline |
| Q053 C3 Trigger 3 激活（rolling 3mo put-side PnL < -1.5× MAD in medium-VIX）| Planner 月度检查项 |

---

*本文档反映 2026-05-10 研究线收口状态。下次更新触发条件：V2f 进入 paper trading 或 live execution、或 Q059 竞争重议。*

---

## Quant 签字 / 修订记录

**签字**：Quant Researcher（2026-05-10）
**状态**：数字口径已与 RESEARCH_LOG R-20260510-04~08 / archive §10–§13 / Q061 实测 cross-check 一致，**正式收口**。

**本轮 Quant 修订项（2026-05-10，Planner 草案 → 收口版）**：

1. **§1 V2f row**：Ann ROE +2.67% → **+2.46%（geometric, BS-flat 26yr）**；historical worst -10.96% → **-9.24%**（统一为 Q061 实测口径）
2. **§2.3 性能表**：移除"+2.55%（实测）"未注明来源数；统一 Ann ROE 为 +2.46% 几何；新增 cluster % equity 行；新增"口径注"四条澄清 Ann ROE 几何 vs 算术、Sharpe daily-return vs trade-level、Q061 vs q055 worst trade 取值差异
3. **§2.3 V2f+M1 historical worst**：-9.24% → **-10.96%**（Q061 实测：M1 把 entry cadence 5→10 TD 后 single-trade worst 略深）。SPEC-097 决策依据修正
4. **§3 BSH Tier 1**：补充 26yr 累计 cost -$260k / payoff +$66k 数字；将"2020 COVID payoff ≈ 年度 cost"改为"2020 COVID 期间 BSH 净亏 $8k"（archive §13 实测 PnL 差）；Sharpe 加注 trade-level 口径
5. **§7 caveat 1**：+18-25% → **+17-25%**（Q057 full window +17.57%，下界精确）

**Quant 视角下未修订项**：

- §6 Q041 Tier 2/3 状态：PM/Planner 决策范围
- §8 触发条件：政策面，Quant 不背书；但建议 Q059 触发时协议至少包含 i) 真实期权数据（非 BS-flat），ii) 1987 量级 stress 子任务
- §2.2 SPEC-097 状态"APPROVED"：PM 在 Q061 量化前已预批 M1 进 SPEC；Q061 今日（2026-05-10）量化结果支持 PM 决策（Δalpha=-0.11pp，stress worst -16.85→-15.13），无 SPEC 回退理由

**Quant 仍持的两条 caveat**：

- **V2f+M1 stress worst -15.13% 仍未完全跨过 V1 veto -15% 门槛**（剩 0.13pp 缺口）。如 PM 要求严格余量，需进一步研究（M1 阈值 4→3，或 M1 + short-DTE force-close 组合）
- **本文档全部 stress 数字基于单一 anchor 2022-11-09 + 单一 shock magnitude（-30%/5d, VIX 25→60）**。Tier 2 sensitivity 未做；不同 anchor / 不同 shock magnitude 下的数字可能漂移
