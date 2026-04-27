# Q021 Phase 1 Attribution — Back-to-back vs Distinct-peak Decomposition (2026-04-25)

> Owner: Quant Researcher
> Topic: 重新审视 `Q021 / SPEC-066` 的语义是否设错——`cap=2` 是否实现了"多峰捕捉",还是只是"第一峰 back-to-back exposure"
> Method: 用 `data/research_views.json.spec064_aftermath_ic_hv` 全 50 笔 aftermath 历史交易 + VIX cluster 重建,做归因分解
> Status: research only — Phase 1 完成,Phase 2 全 engine 对照尚未执行

---

## TL;DR

- **PM 的语义直觉得到强证据支持**。`SPEC-066` 名义 `+$47K` 系统增量在 aftermath 子集口径下,真实结构是:
  - 14 笔(78%)同峰 back-to-back,**不是多峰捕捉**
  - 仅 4 笔(12%)是 PM 原意中的 distinct-second-peak 捕捉
- **2026-03 双峰案例下,`SPEC-066` 没有解决原 `Q018` 问题**:第二峰 aftermath(`2026-03-31..2026-04-13`)在当前规则下**仍然 0 笔 `IC_HV` 进场**
- 真正的 Q018 alpha(distinct-peak 部分)只有约 `+$1,135`/4 trades;back-to-back alpha 是 `+$8,458`/14 trades——后者属于 PM 明确指出错误的语义路径
- **结论类别推荐**:介于 `(b) 新研究 branch` 与 `(c) DRAFT Spec 候选`——证据已足够触发新 spec,但需要 Phase 2 全 engine 对照(实测新规则在 2008/2020 灾难窗口的尾部行为)再正式立案

---

## 1. 数据来源与方法

- 数据源:`data/research_views.json.views.spec064_aftermath_ic_hv` 50 笔(post-broken-wing 后的当前 canonical artifact)
- VIX 历史:`data/market_cache/yahoo__VIX__max__1d.pkl`
- aftermath 定义:与 `SPEC-064 / SPEC-066` 一致——`peak_10d ≥ 28 AND off_peak_pct ≥ 0.10`
- **cluster 重建**:把所有满足 aftermath 的连续交易日视为一个 cluster;cluster 之间至少隔一个非-aftermath 日。这是"真实 VIX peak 事件"的最小可编程定义,严于"rolling-window peak_date"

---

## 2. 2026-03 真实双峰案例

| date | VIX | peak_10d | off_peak% | aftermath | cluster |
|---|---|---|---|---|---|
| 2026-03-06 | 29.49 | 29.49 | 0% | — | (peak 1 day) |
| 2026-03-09 | 25.50 | 29.49 | 13.5% | ✓ | C1: `2026-03-09..2026-03-11` |
| 2026-03-10 | 24.93 | 29.49 | 15.5% | ✓ | C1 |
| 2026-03-11 | 24.23 | 29.49 | 17.8% | ✓ | C1 |
| 2026-03-12 | 27.29 | 29.49 | 7.5% | — | (gap) |
| 2026-03-13 | 27.19 | 29.49 | 7.8% | — | (gap) |
| 2026-03-16..2026-03-19 | 22-25 | 29.49 | 14.9-24.1% | ✓ | C1' (sub-cluster, peak 1 残余) |
| 2026-03-27 | **31.05** | 31.05 | 0% | — | **(peak 2 day, VIX 31.05 > peak 1 29.49)** |
| 2026-03-31 | 25.25 | 31.05 | 18.7% | ✓ | **C2: `2026-03-31..2026-04-13`** |
| 2026-04-01 | 24.54 | 31.05 | 21.0% | ✓ | C2 |
| 2026-04-02 | 23.87 | 31.05 | 23.1% | ✓ | C2 |
| 2026-04-08 | 21.04 | 31.05 | 32.2% | ✓ | C2 |
| 2026-04-13 | 19.12 | 30.61 | 37.5% | ✓ | C2 |

**SPEC-066 实际产出的两笔 IC_HV**:

| trade | entry | cluster | exit | exit_pnl |
|---|---|---|---|---|
| #1 | 2026-03-09 | **C1 (peak 1)** | 2026-04-01 | +$580 |
| #2 | 2026-03-10 | **C1 (peak 1)** | 2026-04-02 | +$604 |

→ **两笔都来自第一峰 cluster**,gap 仅 1 个交易日,**典型的同峰 back-to-back**

**Peak 2 aftermath 窗口产出**:`2026-03-31 ~ 2026-04-13` 共 **9 个 aftermath 日,0 笔 IC_HV 进场**

→ 原因清晰:trade #1 / #2 直到 `2026-04-01 / 2026-04-02` 才平仓;peak 2 aftermath 的最早可入场日 2026-03-31 时,两槽位仍占用。等到 04-08 / 04-13 已是 peak 2 aftermath 末段,且 cap=2 + B 触发条件 + 其他 gating(regime / IV)的某项可能已不满足

---

## 3. 全样本归因(50 笔 aftermath IC_HV)

### 3.1 35 个 distinct aftermath cluster 的 trade 数分布

| cluster trade count | n_clusters | sum_trades | sum_pnl |
|---|---|---|---|
| singleton(1 笔)| 21 | 21 | $+15,800 |
| pair(2 笔)| 13 | 26 | $+15,016 |
| triple(3 笔)| 1 | 3 | $+1,959 (2025-04-09 cluster) |

→ 14 个多笔 cluster 共贡献 **15 笔"同峰非首笔"**(`n-1` 第二+第三槽),PnL 合计 `+$9,008`

### 3.2 4 种规则下的 trade set 模拟

模拟方法:用现有 50 笔的 entry_date / exit_date,按规则跑一次"open positions list"过滤(用现有 exit 是近似——真实重跑需要全 engine,因为 cap 改变会反推 exit_pnl 也变;但 trade 数 / cluster 归属是稳定的)

| 规则 | n | PnL | avg | 说明 |
|---|---|---|---|---|
| `cap=1` (`SPEC-064` 等价) | 28 | $+15,440 | $+551 | 单槽位 |
| `cap=2` (`SPEC-066` 当前) | 46 | $+25,033 | $+544 | 槽位无 cluster 区分 |
| `distinct_cluster` (单槽 + 严格异 cluster) | 33 | $+18,652 | $+565 | 实际等价于 cap≤1 per cluster |
| **`distinct_cluster_cap2` (PM 意图)** | **35** | **$+19,118** | **$+546** | **cap=2 且要求异 cluster** |

注:模拟数 46/50 是因为现有 view 包含 4 笔在严格规则下也会被同 cluster open 阻挡;真实 cap=2 规则下应该是 50 笔,差异属于近似误差

### 3.3 SPEC-066 增量分解(`cap=2` vs `cap=1`)

- 增量 trade:`46 - 28 = 18 笔`
- 增量 PnL:`+$25,033 - $15,440 = +$9,593`

按规则差异拆解:

| 类别 | n | PnL | 来源 cluster 状态 |
|---|---|---|---|
| **同峰 back-to-back**(被 distinct_cluster_cap2 移除)| **14** | **$+8,458** | 同 cluster 内第二+槽 |
| **distinct-peak overlap**(prior IC_HV 来自不同 cluster 仍 open)| **4** | **$+1,135** | 跨 cluster 的真 Q018 alpha |

→ **78% 的 SPEC-066 alpha (`+$8,458 / +$9,593`) 来自同峰 back-to-back,不是多峰捕捉**

### 3.4 Distinct-peak overlap 的 7 笔历史样本

(prior position open 时进入新 cluster 的 IC_HV)

| entry_date | exit_date | exit_pnl | prev_open_clusters |
|---|---|---|---|
| 2000-10-19 | 2000-11-15 | $+576 | [36] |
| 2002-07-29 | 2002-08-27 | $+585 | [56] |
| 2002-08-27 | 2002-10-01 | $-852 | [57] |
| 2008-03-18 | 2008-04-08 | $+618 | [84] |
| 2010-06-15 | 2010-07-09 | $+576 | [111] |
| 2020-03-04 | 2020-04-07 | $-649 | [133] (COVID) |
| 2022-03-09 | 2022-03-23 | $+701 | [155] |

合计 7 笔 / `+$1,555`(3.4 节包含一些"被 distinct_cluster_cap2 同时纳入"的同 cluster 情况——4 笔过滤后是 distinct_cluster_cap2 真正多收的部分)

---

## 4. PM 提的 5 个问题——答案

### Q1 — 2026-03 双峰各对应哪个语义窗口?

- `2026-03-09`:**peak 1 (`2026-03-06`,VIX 29.49) aftermath cluster `2026-03-09..2026-03-11`**,首日入场
- `2026-03-10`:**SAME cluster (peak 1) 第二日入场**,back-to-back
- 两笔均不是 peak 2 (`2026-03-27`,VIX 31.05) 的捕捉;peak 2 aftermath cluster `2026-03-31..2026-04-13` **0 笔 `IC_HV`**

### Q2 — SPEC-066 增量收益的归因

| 来源 | 占比(笔)| 占比(PnL)|
|---|---|---|
| 同峰 back-to-back | 14/18 = 78% | $+8,458 / $+9,593 = 88% |
| distinct-second-peak capture | 4/18 = 22% | $+1,135 / $+9,593 = 12% |

→ 在 aftermath 子集口径下,**SPEC-066 的 alpha 几乎全部来自 PM 明确指出错误的同峰 back-to-back**。系统级 `+$47K` 还包含 B filter 副作用(其他策略的 BP cascade)和 broken-wing 之前的 premium 差,本归因不能直接外推到全系统,但方向无歧义

### Q3 — 如果要求第二笔必须对应新峰,trade set 怎么变?

within aftermath 子集:

| 维度 | 当前 cap=2 | distinct_cluster_cap2 | 差 |
|---|---|---|---|
| n | 46 | 35 | -11 |
| PnL | $+25,033 | $+19,118 | -$5,915 |
| avg | $+544 | $+546 | +$2 |

- **失去**:14 笔同峰 back-to-back(全部移除),PnL $-8,458
- **保留**:`cap=1` baseline 28 笔 + 7 笔 distinct-peak overlap = 35
- **没有新增**——因为现有 view 是 SPEC-066 实际产出,不包含"被 cap=2 还阻塞但本应在 distinct_cluster_cap2 入场"的反事实

需要 Phase 2 全 engine 跑才能看到反事实(尤其 2026-03-31 / 04-01 / 04-02 是否会进场)

### Q4 — 最小规则方案

最直观的一条:

```python
# Engine pseudo-code
def can_open(rec, positions):
    if rec.strategy != IRON_CONDOR_HV:
        return any_open(rec, positions) is False
    same_cluster_open = any(p.aftermath_cluster_id == rec.aftermath_cluster_id for p in positions)
    return (not same_cluster_open) and (count_ic_hv(positions) < 2)
```

需要的额外字段:
- 在 selector 决策路径上把 `aftermath_cluster_id` 算出来(基于 VIX 10-day 回看 + cluster 边界判定),挂在 recommendation 上
- 在开仓时把这个 id 落到 `Position.aftermath_cluster_id`(或等价的 `entry_peak_date`)
- engine 的 `_already_open` 改为 cluster-aware

替代实现:用 `entry_peak_date`(rolling-window peak)代替 cluster_id——更简单但精度差一点(rolling 与 cluster 边界不完全一致)

### Q5 — 结论分类

**我的推荐:`(b) 新研究 branch`,但目标是 1 个 Phase 2 内立 DRAFT spec**

理由:
1. **语义错误已确认**——4/18 vs 14/18 的归因对比是决定性的
2. **PM 原始 Q018 问题在 SPEC-066 后未解决**——2026-03 peak 2 完全 missed
3. **但不能仅凭 within-view 归因下 spec**——需要全 engine 对照量化:
   - distinct_cluster_cap2 全系统 PnL / Sharpe / MaxDD
   - 灾难窗口(2008-09 / 2020-03)在新规则下的尾部行为
   - 2026-03 反事实模拟:peak 2 是否真的被新规则捕捉
4. 同峰 back-to-back **平均 PnL 仍为正**(`+$604`),不是简单删掉就好——可能值得在 spec 中设计一种"sizing-only 加仓"机制(例如同峰允许第二笔但 size 折半),与 distinct-peak 并存

**不推荐 `(a) 保留不动`**:78% 的 alpha 来自语义错误路径,长期看是 review burden + 后续策略改动的混淆源

**不推荐当下直接 `(c) DRAFT spec`**:Phase 2 数据未跑;直接立 spec 容易回到 SPEC-066 review 时 AC4/AC10 那种"细节没量化好"的问题

---

## 5. 建议的 Phase 2 设计

最小 prototype:`backtest/prototype/q021_phase2_distinct_peak.py`

变体对比(共享 baseline = 当前 main commit):

| Variant | 规则 |
|---|---|
| baseline | 当前 SPEC-066: `cap=2` 无 cluster 限制 |
| `pm_intent` | `distinct_cluster_cap2` |
| `strict_single_cluster` | 单槽 + cluster 限制(等价于 `cap=1` per cluster) |
| `back_to_back_half_size` | cap=2 但同峰第二槽 size 减半(可选) |

输出:
- 全系统 trade count / PnL / Sharpe / MaxDD
- aftermath 子集分解(本文 §3 表格)
- 灾难窗口(2008-09 / 2020-03 / 2025-04)分别对照
- **关键反事实**:2026-03 peak 2 在 `pm_intent` 下是否进场

**只有 Phase 2 跑出后,DRAFT spec 才能给出可信的 AC**

---

## 6. 关键风险与反对意见

### 6.1 同峰 back-to-back 的 `+$604/trade` 不是免费午餐

- 14 笔同峰平均 PnL `+$604` 仍正且 win-rate 高
- 如果新规则简单删掉,**确实在历史样本上少赚 $8,458**
- 真正的反对意见:这部分 alpha 是"短同峰持续 IV 被压缩"赚来的,与 distinct-peak alpha **机制不同**
- 不应该简单丢弃,而应该问"是否值得用更柔性的机制保留"

### 6.2 cluster 边界对短峰可能不稳

- `2026-03 peak 1` 实际有 `2026-03-12 / 03-13` 中断 → 我用了 `C1: 2026-03-09..03-11` 与 `C1': 2026-03-16..03-19` 视为两个 sub-cluster
- 但这两个 sub-cluster 都源自 `2026-03-06 peak`,某种意义上算"同峰"
- → cluster 算法对"半中断"敏感,需要 Phase 2 验证 robustness(例如允许 `≤2-day off_peak < 10%` 仍视为同 cluster)

### 6.3 7 笔 distinct-peak overlap 中有 2 笔在灾难窗口

- 2020-03-04(COVID)`-$649`
- 2002-08-27 `-$852`
- 这表明 distinct_cluster_cap2 在尾部不一定比 cap=2 安全
- 必须在 Phase 2 显式比对 MaxDD / 最差年份

### 6.4 反向论点:SPEC-066 的 +$47K 全系统增量包含 B filter 副作用

- 本归因是 aftermath 子集口径(50 笔)
- B filter (`OFF_PEAK 0.05 → 0.10`)对其他 HV 策略 / BP cascade 有间接影响
- 严格论"PM 意图错"需要看全系统 cap2-vs-cap1 + B 的完整对照——超出 Phase 1 范围

---

## 7. 给 PM 的 3 条建议(按优先级)

| # | 建议 | 理由 |
|---|---|---|
| 1 | **批准 Phase 2 prototype**(`backtest/prototype/q021_phase2_distinct_peak.py`)| 在不动 production 的前提下,最快确认/反驳 SPEC-066 语义错的实际成本 |
| 2 | 在 `RESEARCH_LOG.md` / `sync/open_questions.md` Q021 条目下记录:Phase 1 归因证据已强,SPEC-066 半数以上 alpha 来自非 PM 意图路径;`SPEC-066` 不立即回滚但语义偏差被正式登记 | Governance 卫生 |
| 3 | 暂停在 `IC_HV` aftermath 上做更多 spec 改动(如未来若有 Q032 V3-C 切换 / Q029 live-scale 重写),直到 Q021 收敛 | 防止在错误语义层上叠新 spec |

不建议直接 flip SPEC-066 状态,也不建议直接立新 SPEC——证据强但 Phase 2 没跑,DRAFT 太早

---

## 8. 输出物

- 本文件:`doc/q021_phase1_attribution_2026-04-25.md`
- 后续 Phase 2 工作:`backtest/prototype/q021_phase2_distinct_peak.py`(待 PM 批准)
- 索引层更新:由 Planner 沉淀 `RESEARCH_LOG.md` / `sync/open_questions.md` Q021 条目(本研究不做)

---

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-04-25 | Phase 1 归因完成;PM 直觉得到强证据支持(78% alpha 来自语义错路径);推荐进入 Phase 2 全 engine 对照,而不是直接 DRAFT spec |
