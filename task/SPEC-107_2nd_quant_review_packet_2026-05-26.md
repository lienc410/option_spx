# SPEC-107 — Intraday Recommendation Governance — 2nd Quant Review Packet (Round 1)

**Date**: 2026-05-26
**Prepared by**: Quant Researcher
**Audience**: 2nd Quant Reviewer
**Stage**: SPEC DRAFT pre-PM-approval; final design check before Developer hand-off
**Reviewer response**: `task/SPEC-107_2nd_quant_review_packet_2026-05-26_Review.md`

---

## 0. TL;DR

SPEC-107 落实 Q076 P3 verdict（A2a + B）为可执行 SPEC。已通过 3 轮 2nd Quant review（P2 design / P2 verdict / P3 verdict）。本轮是 SPEC 自身的最后 design check —— 不是 re-litigate research conclusions，而是审查：

1. **SPEC scope 划分**是否守住边界（governance vs strategy semantics）
2. **AC 集合**是否覆盖所有关键 invariant
3. **Bypass list** 是否完整无漏
4. **Implementation 架构**选择（intraday governance 与 SPEC-103 解耦的方式）
5. **Backtest replay AC7** 的 tolerance 是否合理
6. **Deferred validation** 是否足够覆盖未被 12mo 样本覆盖的风险

请 reviewer 重点回答 §6 的 8 个具体问题。

---

## 1. Background — 三轮 review 链路

| Round | Date | Subject | Outcome |
|---|---|---|---|
| R1 | 2026-05-26 | Q076 P2 design — 4-variant mitigation replay | PASS w/ revisions（加 4-variant + hard targets） |
| R2 | 2026-05-26 | PM verdict on R1 + Quant P2 memo | ACCEPT A2a + B; 守 governance vs strategy semantics 边界 |
| R3 | 2026-05-26 | Q076 P3 robustness on 12mo | PASS w/ revisions（AC 从 6 扩到 8；+AC4/5 拆分 +AC8 regression test +stop-loss bypass） |
| **R4 (本轮)** | **2026-05-26** | **SPEC-107 自身** | **本 packet 待 review** |

R1-R3 已存档：
- `task/q076_phase2_2nd_quant_review_2026-05-26.md`
- `task/q076_phase2_2nd_quant_review_2026-05-26_Verdict.md`
- (R3 review embedded in PM message thread, 已 incorporated into SPEC-107)

---

## 2. SPEC-107 核心数据基础（已被前 3 轮 review 验证）

12-month replay (1736 bars, 251 days)：

| Variant | Flips | ↓vs base | ≤3h ep ↓ | EOD agree | Round-trips |
|---|---|---|---|---|---|
| baseline | 204 | — | — | 100% | 53 |
| **A2a + B (chosen)** | **93** | **-54%** | **-92%** | **93.2%** | **18** |

By VIX regime:
- LOW_VOL (<14) 15 bars: 0 episodes / 0 flips
- NEUTRAL (14-22) 1508 bars: governance 主战场
- HIGH_VOL (22-30) 203 bars: **0 BPS episodes**（governance dormant）
- STRESS (≥30) 10 bars: 0 BPS episodes（dormant）

49 non-BPS baseline disagreement bars **100%** 限于 non-sched bars (09:30 / 11:30 / 12:30 / 13:30 / 14:30) —— 0 at sched bars。

---

## 3. SPEC scope 五段（A-E）

| Section | 内容摘要 |
|---|---|
| **A** | A2a hysteresis state machine, [42-53 entry / 35-57 hold] bands, configurable, per-position |
| **B** | Scheduled actionable cadence, default [10:30, 15:30 ET], configurable |
| **C** | Bypass list: SPEC-103 daemon (R5/R6) + EXTREME_VOL + stop-loss + manual override |
| **D** | Frontend State Observation label + Actionable banner UX 视觉区分 |
| **E** | Decision log JSONL with 15 fields, append-only |

完整 SPEC 见 `task/SPEC-107.md`。

---

## 4. 8 个 Acceptance Criteria

| AC | 摘要 | Quant joint? |
|---|---|---|
| AC1 | Hysteresis state machine + unit tests, configurable params | Developer |
| AC2 | Sched cadence default `["10:30", "15:30"]`, configurable | Developer |
| AC3 | Bypass list enforced + 4-class unit tests + decoupling from SPEC-103 daemon | Developer |
| AC4 | Frontend "State Observation" label on non-sched bars | Frontend |
| AC5 | "Actionable Decision" + "Hard Exit" banners, Telegram sync | Frontend |
| AC6 | Decision log JSONL with 15 fields + rotation | Developer |
| **AC7** | **12mo backtest replay matches P3 numbers within ±5%** | **Quant + Developer joint** |
| **AC8** | **HIGH_VOL/STRESS regime regression test, 0 BPS governance intervention** | **Quant + Developer joint** |

AC7 tolerance：flips 93±5, ≤3h 3±1, EOD ≥90%, RT 18±2.

---

## 5. 已识别风险与开放问题

请 reviewer 直接判断每条。

### 5.1 Bypass list 完整性
**Quant claim**: 4 类 bypass（SPEC-103 daemon / EXTREME_VOL / stop-loss / manual override）覆盖所有需要 immediate execution 的场景。

**潜在 gap**:
- Selector 内部其它 hard signals（如 trend 突变 BULLISH→BEARISH 强方向翻转）？目前未明示 bypass，会被 hysteresis + sched-eval 延迟最多 1h
- DD Overlay armed state 变化（dd4/dd15 触发）也是 strategy-level signal，但 SPEC-094 dd 是 daily evaluator，应该不冲突
- Roll operations（trade lifecycle 内的 roll，与 entry recommendation 解耦）—— SPEC 假设这与 governance 独立。是否需要明示？

### 5.2 SPEC-103 daemon vs SPEC-107 governance 的 decoupling
**Quant claim**: SPEC-103 R5/R6 通过 daemon 实时 check，与 selector recommendation 解耦。SPEC-107 governance 只在 selector recommendation 之上 wrap, 不阻挡 R5/R6 hard rules。

**潜在 gap**:
- 如果某 candidate 通过 SPEC-107 governance (sched bar, hysteresis 同意 BPS open) 但触发 SPEC-103 R6 hard block，最终 decision pipeline 怎么 reconcile？需要明确 priority order
- SPEC 草案 §C bypass list 第 1 条说 "SPEC-103 daemon 独立运行 ✓"，但实施层是否真正 decoupling 还需 Developer 实施时确认

### 5.3 Hysteresis bands 来源
**Quant claim**: Entry [42, 53] / Hold [35, 57] 是 PM round-2 review 提议值，P3 12mo 验证有效。

**潜在 gap**:
- 这些 bands 没有正式 sensitivity 测试（P3 没扫描 ±3pp）
- 12mo 样本 IVP 范围 3.6-96.8，bands 处于中间位置；但 deep LOW_VOL 期 IVP < 35 时机器人会 close existing BPS（产品 semantics：不 hold）；而 deep HIGH_VOL 期 IVP > 57 时 close —— 这两边都是 production close-trigger semantics 的复制
- A2b (entry-only deviation) 数据上等价 A2a+B, 但被排除 in scope ✓（PM 已 cut）

### 5.4 AC7 tolerance ±5% 是否过松
**Quant claim**: 实施小 drift 允许（数值四舍五入、edge case 处理等）。

**潜在 gap**:
- 93 flips ±5 = 88-98 范围。如果实施 drift 到 95 flips（-53.4%），仍 PASS PM ≥50% target。OK
- 但 ≤3h episodes 3±1 = 2-4，相对单位变化大。值得收紧？
- EOD agreement ≥90% 而非 93.2%±tolerance，意图是给实施留余地，但如果实施落在 90.0% 就刚好压线。是否改 ≥92%？

### 5.5 AC8 regression test 设计细节
**Quant claim**: HIGH_VOL+STRESS regime 不应 trigger governance；用 P3 12mo 子集或 synthetic 数据测试。

**潜在 gap**:
- "Synthetic 数据" 是 plausible？应该用 12mo 真实子集（203 HIGH_VOL bars + 10 STRESS bars）
- 测试断言："0 BPS episodes generated by hysteresis"。但 hysteresis 在 baseline 推 BPS Normal 时才介入，HIGH_VOL 期 baseline 不推 BPS Normal，所以 hysteresis 自然 0 介入 —— 测试通过其实是 trivial。是否更强的断言？

### 5.6 Decision log 是否足够 audit
**Quant claim**: 15 字段足够回放、retrospective、bypass 频率监控。

**潜在 gap**:
- 缺 `last_actionable_decision_at` 字段方便用户知道"上一次可执行决策是几点"
- 缺 `next_actionable_decision_at` 字段方便 UI 倒计时
- 但这些可在 deploy 后 retrospective 时再补字段（向后兼容 JSONL）—— 是否本轮就加？

### 5.7 Frontend 实施粒度
**Quant claim**: AC4/AC5 拆分让前端有两个独立 task：label + banner。

**潜在 gap**:
- AC4 / AC5 没指定 colors / animations / 倒计时显示样式 —— 留给 frontend dev 按 `DESIGN.md`
- 是否需要 mock-up 或更明确的 UX spec？还是 trust frontend dev？

### 5.8 Q077 (Low-IVP semantics) 与 SPEC-107 时间线
**Quant claim**: Q077 独立轨道，与 SPEC-107 并行；不影响 SPEC closure。

**潜在 gap**:
- 如果 Q077 最终结论是 "low-IVP 不应 force close existing BPS"（A2b 方向），那么 selector.py 改了之后 SPEC-107 的 A2a hysteresis 下沿 (IVP < 35 close) 是否变得多余甚至冲突？
- SPEC-107 实施时是否要预留 future-compat hook？

---

## 6. Review Questions（请明确回答）

**Q1 — SPEC scope 边界**
SPEC-107 scope 五段（A-E）是否完整？是否有缺失的 governance 元素（如 multi-position state、cross-strategy coordination）应该纳入而 SPEC 当前忽略？

**Q2 — Bypass list 完整性**
4 类 bypass（SPEC-103 daemon / EXTREME_VOL / stop-loss / manual override）是否覆盖所有需要 immediate execution 的场景？特别请检查 §5.1 提到的 trend 突变、DD Overlay armed state、roll operations 是否需要补入 bypass list。

**Q3 — SPEC-103 vs SPEC-107 priority reconciliation**
当 SPEC-103 R6 second-leg block 与 SPEC-107 hysteresis "open BPS" 决策冲突时，priority 应该如何 reconcile？SPEC-107 草案假设 SPEC-103 总是 win，但是否需要在 AC3 明示这个 priority order？

**Q4 — AC7 tolerance**
12mo backtest replay tolerance（flips 93±5, ≤3h 3±1, EOD ≥90%）是否合理？还是应该收紧到 ±3% 防止实施 drift？特别 EOD agreement 90% 下限：实施落在 90.0% 时刚好压 PM 当初的 hard target，没有 safety margin。是否改 ≥92%？

**Q5 — AC8 regression test 强度**
"HIGH_VOL/STRESS regime 不 generate BPS governance intervention" 这个断言在 production 测试时，是否需要更强的设计验证（如 fuzz IVP/VIX 在 HIGH_VOL 区间，看 governance 是否仍 dormant）？还是 12mo 真实子集足够？

**Q6 — Decision log 字段**
当前 15 字段足够 audit + retrospective？是否需要加 `next_actionable_decision_at` / `last_actionable_decision_at` 字段？还是 deferred 补字段？

**Q7 — Hysteresis bands sensitivity**
是否在 SPEC closure 前需要做 entry/hold bands ±3pp sensitivity 测试？或者推迟到 deferred validation 3？

**Q8 — Q077 vs SPEC-107 forward compat**
如果未来 Q077 结论支持 selector low-IVP entry-only 改动（即 production selector 在持仓时不 emit `CLOSE_AND_WAIT`），SPEC-107 的 A2a hysteresis 下沿 (IVP < 35 force close) 会变得多余甚至冲突。是否需要在 SPEC-107 实施时预留 future-compat hook（如 `hysteresis_lower_force_close: bool = True` config flag）？

---

## 7. 不在范围内（reviewer 不需评估）

- **Q076 P1-P3 研究结论本身** — 已通过前 3 轮 review
- **A2b alternative** — PM verdict 已 cut, out-of-scope
- **Low-IVP semantics research (Q077)** — 独立轨道，不在 SPEC-107
- **Selector strategy logic** — 不修
- **Daily backtest engine** — 不修
- **/ES recommendation** — 独立 governance, 不在本 SPEC
- **SPEC-103 daemon** — 已运行；本 SPEC 通过 bypass list 解耦

---

## 8. 参考

```
task/SPEC-107.md                                                ← SPEC 草案
research/intraday/q076_findings_2026-05-26.md                   ← P1 diagnostic
research/intraday/q076_p2_findings_2026-05-26.md                ← P2 verdict
research/intraday/q076_p3_findings_2026-05-26.md                ← P3 robustness
research/intraday/q076_p3_metrics_overall.csv                   ← AC7 reference numbers
research/intraday/q076_p3_metrics_by_regime.csv                 ← AC8 reference
data/market_cache/spx_vix_1h_aligned_12mo.pkl                   ← AC7 source data
task/q076_phase2_2nd_quant_review_2026-05-26.md                 ← R1 review
task/q076_phase2_2nd_quant_review_2026-05-26_Verdict.md         ← R2 verdict
task/SPEC-103.md                                                ← daemon dependency
task/SPEC-064.md or selector.py is_aftermath()                  ← aftermath gate context
strategy/selector.py                                             ← baseline (NOT modified)
strategy/sleeve_governance.py                                    ← potential host module
signals/iv_rank.py                                               ← IVP_252 source
DESIGN.md                                                        ← UX color/typography baseline
```
