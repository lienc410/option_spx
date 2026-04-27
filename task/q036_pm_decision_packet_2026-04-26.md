# Q036 PM Decision Packet — Idle BP Capital-Allocation Overlay

- Date: 2026-04-26
- Prepared by: Quant Researcher
- Audience: PM
- Topic: `Q036 — Idle BP Deployment / Capital Allocation`
- Branch state on entry: `ready for PM decision packet` (synthesis of 2nd / 3rd Quant review, verdict `PASS WITH CAVEAT`)

---

## 1. PM Decision Question

> 是否将 `Overlay-F_sglt2` 升级为 DRAFT overlay spec 讨论的对象，还是先按 research candidate 留在现状？

---

## 2. Recommendation

**`hold as research candidate, do not productize now`**

理由（一句话版）：经济收益是真实但偏薄的（`+0.074pp` ann ROE, `+0.040pp` recent），治理已干净到不会引入新风险，但**没有 knockout 量级证据值得现在承担产品化的工程与治理复杂度**。最合理的姿态是：保留候选 + 设清晰 re-trigger 条件，等更强证据出现再 escalate。

不是 `escalate` 的原因：

- `+0.040pp` recent-era uplift 在 PM 当前 “reasonably maximize ROE” 的口径下，不是 _显著_ 的提升
- 产品化前必须先做 gate 对齐重跑（详见 §3 caveat 与 §4），属于真实工程成本
- 当前没有任何信号表明再多花一轮研究能把 uplift 推大

不是 `drop` 的原因：

- 11/27 年正贡献、灾难窗口 net 不退化、`SG≥2 = 0`、recent era 仍正向
- 这些都不像 false branch；丢掉等于丢掉一个已经收敛到 frontier 的候选

---

## 3. Evidence Pack

详细结果见：

- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- `task/q036_quant_review_packet_2026-04-26.md` §11 (methodology caveat)

### 3.1 Account-level uplift

| 指标 | Baseline | Overlay-F | Δ |
|---|---:|---:|---:|
| Total PnL (full sample 2000–2026) | `+$403,850` | `+$412,855` | `+$9,005` |
| Annualized ROE (full) | `8.675%` | `8.748%` | `+0.074pp` |
| Total PnL (recent 2018+) | `+$164,958` | `+$169,353` | `+$4,395` |
| Annualized ROE (recent) | `5.544%` | `5.583%` | `+0.040pp` |
| Positive delta years | — | — | `11 / 27` |
| Single-year top contributor share | — | — | `17.6%` (2022) |

**读法**：uplift 真实但偏薄；不是单年驱动；recent-era 比 full-sample 更薄，没有 regime decay 但也没有 regime improvement。

### 3.2 Tail / disaster posture

| 指标 | Baseline | Overlay-F | Δ |
|---|---:|---:|---:|
| MaxDD (full) | `-10,323` | `-9,749` | improved |
| CVaR 5% (full) | `-4,309` | `-4,382` | worse by `74` |
| MaxDD (recent) | `-9,405` | `-9,392` | flat |
| Disaster window net (2008 / 2020 / 2025) | `+301` | `+301` | unchanged |
| Peak system BP% | `30%` | `34%` | up 4pp |

**读法**：disaster posture 完全没退化。CVaR 边际变差但量级 (`-$74`) 远小于 PnL 增量 (`+$9,005`)。Peak BP 从 30% → 34% 是 overlay 的固有成本（多用了一些 idle BP）。

### 3.3 Governance cleanliness

- 触发分布：23 fires / 27 年，全部在 `HIGH_VOL`，集中在 `VIX 25-30`（18 笔）
- 触发时 pre-existing short-gamma count（position-count 口径）：`SG=0: 9` / `SG=1: 14` / `SG≥2: 0`
- 触发时平均 idle BP：`80.5%`（远高于 70% 的 gate）
- Disaster window 不开新仓（VIX < 30 cap 起作用）

**Caveat（已披露）**：gate 用 family-deduplicated count，cleanliness 报告用 position-count；本样本两种口径给出**相同**的 fire 分布，cleanliness claim 在更严格口径下也成立。完整披露见 `task/q036_quant_review_packet_2026-04-26.md` §11。这是 presentation issue，不是 numerical issue；产品化阶段必须修，hold 阶段不必修。

---

## 4. Costs / Risks of `escalate`

如果 PM 选择 escalate to DRAFT spec discussion：

1. **必须先做 gate 对齐**
   - 把 `_preexisting_short_gamma_count` (`backtest/prototype/q036_phase4_short_gamma_guard.py:33-35`) 改成 position-count（去 `set(...)`）
   - 重跑 Phase 4 / Phase 5，重新核 23 笔 fire 数字
   - 数值预期不大变（本样本两种口径分布一致），但不做这一步 SPEC 不能写
   - 工程量小，但是一道无法跳过的 gate

2. **治理复杂度落地**
   - SPEC 需要描述 3 个并列条件（idle BP / VIX / SG count）+ boosted-first 阻断规则
   - 引入一个新的 capital-allocation layer 抽象，这是当前系统第一个此类 overlay
   - 一旦写入 production，未来任何新策略 family 都得考虑与该 overlay 的 short-gamma 共生关系

3. **经济回报 vs 复杂度比例不利**
   - 全样本 `+0.074pp` ann ROE / 27 年 = 平均每年 `+$334` 增量
   - recent era 平均每年 `+$549`
   - 即便假设量级在未来 regime 上不退化，相较于额外的产品化工程与持续治理成本，性价比不强

4. **不可逆性低，但仍是真投入**
   - 该 overlay 在 production 中可以 toggle off，不锁定方向
   - 但 SPEC 评审、回测保护、live 监控都需要 attention

---

## 5. Costs / Risks of `hold as research candidate`

如果 PM 选择 hold（推荐选项）：

1. **机会成本（最主要的 risk）**
   - full sample 平均每年 `+$334` 不被实现
   - recent era 平均每年 `+$549` 不被实现
   - 在 27 年累计 `+$9,005` 的口径下，每多 hold 一年的成本约为 recent-era 的 `+$549`

2. **Branch 状态需要明文记录**
   - 必须在 `sync/open_questions.md` / `RESEARCH_LOG.md` 中明确写：lead candidate = `Overlay-F_sglt2`、状态 = hold、verdict = PASS WITH CAVEAT
   - 否则未来重新捡起来时会重复整轮研究
   - 这件事工作量极小

3. **再触发的明确信号需要事先约定**
   - 建议设以下任意一条作为 re-trigger 条件：
     - 出现新的、与现有 IC_HV aftermath 互补的 short-gamma family（增加 idle 部署候选）
     - recent-era uplift 的 marginal `$ / BP-day` 在新数据下越过某个 threshold（例如 `>= +10`）
     - 出现一个非 IC_HV 的 capital-allocation overlay 候选，与 F 共同摊掉产品化成本
   - 没有 re-trigger 条件，hold 容易演变成 “永远不再回头” 的隐性 drop

4. **不会 lock-in 任何东西**
   - hold 不消耗 production 容量，不需要 SPEC 评审
   - 任何时候 PM 都可以说 “现在 escalate”，研究状态都保留好

---

## 6. Already-Settled Items

为避免 PM review 时被卷回上游讨论，下列事项已在 synthesis 阶段确认，**本 packet 不重新论证**：

1. **Verdict 已定**：`PASS WITH CAVEAT`，状态 = `ready for PM decision packet`，**不是** `ready for DRAFT overlay spec discussion`
2. **Lead candidate 已定**：`Overlay-F_sglt2` = `2x` iff `idle BP ≥ 70%` AND `VIX < 30` AND `pre-existing short-gamma count < 2`；不再扩 variant 树
3. **Caveat 已披露**：gate-vs-metric short-gamma count 口径分叉，本样本下不影响 cleanliness claim；产品化前必修，PM packet 不必修；详见 `task/q036_quant_review_packet_2026-04-26.md` §11
4. **Scope 已定**：仅 capital-allocation layer，对照基准是 idle baseline，**不是** `V_A / SPEC-066` 的 rule-layer `$4.85 / BP-day`；不与 `Q021` rule-replacement 重叠

---

## 7. Decision Form

请 PM 在以下三选一中明确选择：

- [ ] `escalate to DRAFT spec discussion` — 接受 §4 列出的产品化成本与必修的 gate 对齐工作
- [ ] `hold as research candidate, do not productize now` — 接受 §5 列出的机会成本，按 §5.3 设置 re-trigger 条件后归档
- [ ] `drop` — 放弃整条 branch（Quant 不推荐，理由见 §2）
