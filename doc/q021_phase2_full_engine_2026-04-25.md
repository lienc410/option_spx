# Q021 Phase 2 — Distinct-Peak vs Back-to-Back, Full Engine

Date: 2026-04-25
Author: Quant Researcher
Phase 1 reference: `doc/q021_phase1_attribution_2026-04-25.md`
Prototype: `backtest/prototype/q021_phase2_distinct_peak.py`

## TL;DR

PM 的语义直觉机制上**成立**（distinct-cluster 规则确实捕到 2026-03 第二峰），
但全引擎跑下来**经济上不成立**：

- V3 (pm_intent + cap=2) 比 V1 (spec066) **净亏 -$9,200**（系统层面），IC_HV 子集 -$8,207
- V2 (pm_intent 无 cap) 表面 +$943 优于 V1，但 max concurrent IC_HV 飙到 **6**（V1 仅 2），运行不可接受
- 2026-03 case PM flag 的捕第二峰确实出现（V2/V3 抓到 03-16），但增量仅 +$111
- V1 spec066 的 disaster window 表现仍然最佳（V2/V3 在 GFC + Tariff 都更差）

**Recommendation: 保留 SPEC-066，将语义偏差记录入 `sync/open_questions.md` Q021 close-out，不开 DRAFT spec。**

---

## 1. 实验设置

### 1.1 Variants

| Variant | 规则 | OFF_PEAK | 含义 |
|---|---|---|---|
| **V0 baseline** | cap=1 | 0.05 | 前 SPEC-064/066 |
| **V1 spec066** | cap=2 | 0.10 | 当前生产（reference） |
| **V2 pm_intent** | aftermath 内同 cluster max 1，其他无 cap | 0.10 | PM 纯净版假设 |
| **V3 pm_intent+cap2** | aftermath 同 cluster max 1 + 全局 cap=2 | 0.10 | PM Q4 "minimum rule" |

### 1.2 Cluster 定义（同 Phase 1）

- 一日为 "aftermath" iff `peak_10d_VIX ≥ 28` 且 `off_peak_pct ≥ 0.10`
- 连续 aftermath 日构成一个 cluster（cluster_id = 起始日）
- 历史样本：**990 aftermath days / 172 distinct clusters**

### 1.3 实施

通过 `inspect.getsource(engine.run_backtest)` 取出函数源码，把 `_already_open` 块替换为对 `_q021_block_cluster()` helper 的调用，再在 engine 模块 namespace 内 `exec` 出 patched 版本。**全引擎链路（BP ceiling / shock engine / overlay）都参与**。

---

## 2. 结果

### 2.1 系统层 PnL / 风险

| Variant | n trades | Total PnL | Sharpe | MaxDD | Δ vs V0 | MaxConc IC_HV |
|---|---:|---:|---:|---:|---:|---:|
| V0 baseline | 404 | +400,734 | 0.41 | -13,213 | — | 2 |
| V1 spec066 | 400 | **+403,850** | **0.42** | **-10,323** | +3,116 | **2** |
| V2 pm_intent | 405 | +404,793 | 0.41 | -12,617 | +4,059 | **6 ⚠** |
| V3 pm_intent+cap2 | 389 | +395,643 | 0.41 | -10,323 | -5,091 | 2 |

### 2.2 IC_HV 子集

| Variant | n | Total PnL | avg | win% | Sharpe |
|---|---:|---:|---:|---:|---:|
| V0 baseline | 111 | +68,053 | +613 | 84.7% | +0.62 |
| V1 spec066 | 107 | +71,169 | +665 | 86.9% | **+0.67** |
| V2 pm_intent | 112 | +72,112 | +644 | 85.7% | +0.58 |
| V3 pm_intent+cap2 | 96 | +62,961 | +656 | 85.4% | +0.63 |

### 2.3 V1 → V2 trade-set diff（spec066 vs pm_intent 纯净版）

- **Dropped by pm_intent**: 23 trades / net $+17,166（多为同 cluster back-to-back 第二腿）
- **Gained by pm_intent**: 28 trades / net $+18,109（部分为 distinct cluster，部分为 BP-freed 后的非 aftermath HV 第二腿）
- 净增量：+$943 — 但代价是 max concurrent IC_HV 从 2 升到 6

V3 (cap=2 收紧 V2)：
- Dropped: 23 trades 同上
- Gained: 较 V2 少很多（cap=2 阻挡了部分非 aftermath HV 第二腿）
- 系统净亏 vs V1: -$9,200

### 2.4 2026-03 Double-peak 真实案例

| Variant | 入场 | Cluster | PnL | 备注 |
|---|---|---|---:|---|
| V0/V1 | 03-09, 03-10 | peak1, peak1 | +$1,184 | back-to-back |
| V2/V3 | 03-09, 03-16 | peak1, peak2 | +$1,295 | distinct cluster ✓ |

PM hypothesis 在此 case 上验证为真，**增量 +$111**。这是 PM intent 在 2026-03 case 下的*真实*经济价值。

### 2.5 Cluster 覆盖度

| Variant | IC_HV in aftermath | clusters hit | multi-per-cluster | avg trades/hit |
|---|---:|---:|---:|---:|
| V0 baseline | 57 | 38 | 18 | 1.50 |
| V1 spec066 | 60 | 41 | 18 | 1.46 |
| V2 pm_intent | 51 | **48** | 3 | 1.06 |
| V3 pm_intent+cap2 | 49 | **47** | 2 | 1.04 |

V2/V3 确实**多触达 7 个 cluster**（48 vs 41），符合 PM "多峰捕捉" 的语义目标。但触达增加并未转化为 PnL 增加。

### 2.6 Disaster windows

| Variant | n | W/L | Net | Detail |
|---|---:|---|---:|---|
| V0 baseline | 7 | 3W/4L | -$2,588 | 2008 GFC 2×(-$2,890) |
| V1 spec066 | 5 | 3W/2L | **+$302** | GFC 0; COVID -1,657; Tariff +1,959 |
| V2 pm_intent | 4 | 2W/2L | -$374 | GFC 0; COVID -1,657; Tariff 2× +1,283 |
| V3 pm_intent+cap2 | 4 | 2W/2L | -$374 | 同 V2 |

**V1 spec066 disaster 表现最优**。V2/V3 在 Tariff 窗口少抓 1 笔（同 cluster 被屏蔽）。

---

## 3. 直接回答 PM Q5

> 你建议这件事的结论属于哪一类：(a) 保留 SPEC-066 不动，只记录语义偏差 / (b) 新开一个 research branch / (c) 足够收敛，可以准备新的 DRAFT Spec 候选

**结论：(a) 保留 SPEC-066，记录语义偏差。**

证据链：

1. **PnL 不支持 DRAFT spec**：V3（PM 最小规则）系统层 -$9,200 vs V1，IC_HV Sharpe 持平或略差。
2. **Risk-adjusted 不支持**：MaxDD V1=V3，但 V1 的 PnL/$DD 比更高；disaster window V1 净 +$302 vs V3 净 -$374。
3. **V2 (pure pm_intent) 表面 +$943 但 max concurrent 6**：HC live 端 BP / 操作复杂度无法接受。
4. **2026-03 case 增量仅 +$111**：单点 anecdote 不足以支撑结构性规则替换。
5. **语义偏差真实存在**：SPEC-066 的 +$3,116 alpha 中，全引擎下大部分仍来自 same-cluster back-to-back（与 Phase 1 信号层 14 trades $+8,458 一致）。这是 *exposure increase*，不是 PM 设想的 *multi-peak capture*。但目前没有更好的规则替换它。

---

## 4. 给 PM 的具体行动建议

**Action 1（必做）— Quant 提交**：
- 把本文件 + Phase 1 attribution 一同纳入 `sync/open_questions.md` Q021 entry，状态从 `research` 改为 `closed`，结论 = "SPEC-066 alpha 证实主要来自 same-peak back-to-back（语义偏差），但 distinct-cluster 替代规则在全引擎下不优；保留 SPEC-066"
- 在 `RESEARCH_LOG.md` 加一行 R-20260425-XX 引用 Phase 1 + Phase 2

**Action 2（建议但非必要）— PM 决策**：
- 是否在 `task/SPEC-066.md` 的 changelog 中加一段 "Quant 2026-04-25 复审：alpha 实际为 same-cluster back-to-back exposure 增加，不是多峰捕捉；distinct-cluster 替代规则验证为 PnL 负面（Q021 Phase 2）"

**Action 3（不建议）**：
- 不开 DRAFT spec
- 不在 Q032 V3-C / Q029 live-scale 等下游 spec 链中阻塞 SPEC-066

---

## 5. 边界与未覆盖

1. **size scaling 未测**：原 Phase 1 deliverable 提到的 "back_to_back_half_size"（second slot 0.5×）未实施。如果 PM 仍想救 PM intent，可以问 "如果 distinct-cluster 第二仓走半 size，Sharpe 能不能赢 V1"。但鉴于 V3 已 -$9,200，半 size 期望降一半到 -$4,500，仍不优。
2. **样本切片未做**：V3 vs V1 的差异是否集中在某段时间（例：2010-2015 低 vol 时期）未细分。如果 PM 认为该段不代表未来，可补做 2018-2026 切片。
3. **Cluster 阈值敏感性未做**：cluster 用 `peak ≥ 28 ∧ off ≥ 0.10`；其他阈值（如 25/0.05）未扫描。

如 PM 认为以上某项需要补做，可以延伸；否则 Q021 在此收口。

---

## 6. 输出物

- `backtest/prototype/q021_phase2_distinct_peak.py` — 4 variant 全引擎 prototype
- `doc/q021_phase1_attribution_2026-04-25.md` — Phase 1 信号层归因
- `doc/q021_phase2_full_engine_2026-04-25.md` — 本文（Phase 2 全引擎结果）
