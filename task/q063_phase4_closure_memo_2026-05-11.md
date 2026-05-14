# Q063 Closure Memo — IVP<55 Gate Robustness Confirmed

**Date**：2026-05-11
**Researcher**：Quant
**Verdict**：**REJECT relaxation. Keep IVP < 55 gate unchanged.**
**Status**：CLOSED

---

## 0. TL;DR

PM 提出 hypothesis：「IVP<55 gate 在低 VIX 环境下产生 false alarm」。Q063 三 Tier + decay-weighted + recent-window 四层检验后，**hypothesis 被数据精确反向 reject**。Gate 在最近 2024-2026 期间挡住的 5 笔 entries 累计 counterfactual P&L = **-$13.7k**。Gate 不是 false alarm，是高价值真信号。

---

## 1. Hypothesis vs Data

| 假设 | 数据 |
|---|---|
| Gate 在低 VIX 过度保守 | Phase 1：低 VIX BLOCKED entries WR 63% (vs ALLOWED 83%)，avg P&L $389 (vs $2,323)。即使在低 VIX，blocked entries 显著差于 allowed |
| Relax gate 应提升 ann ROE | Phase 2：候选 A unweighted +$6,069 over 19y。但 Phase 3 OOS test 期 A LOSES -$907/yr |
| Recent regime 更应 favor relax | **Phase 4 完全反转**：3y HL decay → BL wins +$19,237；last 5y → A loses -$13,730 |

---

## 2. Mechanism — 为什么 gate 在低 VIX 仍然 valuable

**Counter-intuitive 但 empirically robust**：

- VIX=15-17 + IVP=60-65 不是矛盾，是「vol 已 compress 到 1y 高分位（相对）」即使「absolute level 低」
- 这种 setup 在 2024-2026 实证为「**complacency before mean reversion**」
- IV pricing 在此区间 underprice tail——BPS sells put at high IVP but absolute premium reasonable; max-loss event probability is mispriced
- Gate 正确识别此 setup 并 reduce_wait

PM 的 perception「block 后市场没崩 → gate 错」忽略了 counterfactual 的真实形态：
- 不是「市场 crash」，而是「市场 chop / sharp 1-2 周 pullback + theta decay → trade hit debit-double stop」
- PM 看不到「不入场则不亏」，只看到「不入场也没赚」

---

## 3. Quant Forensic — Recent 5 trades counterfactual

A 在 2024-2026 期间放进的 5 笔 added trades 实证 P&L：

```
year  added_trades  added_pnl
2024     +3         -$4,825
2025     +1         -$3,723
2026     +1         -$5,181
────────────────────────────
total    +5         -$13,729
```

**5 笔被 gate 挡住的 trades 平均亏 $2,746/笔**。在 PM 1h/day day-job 约束下，这是非常 material 的损失保护。

---

## 4. 推广性 insight

Q063 是一个 **「PM intuition tested and reversed by data」** 的典型案例。Quant lane 的价值正是提供这种 counterfactual 测试，避免 perception bias 驱动的 SPEC 修订。

类似的 perception biases 应警惕：
1. **Survivor bias on blocked entries**：看到的是「block 后没崩」，看不到「if 入场 will lose」
2. **Recency bias on absolute VIX**：2023-2025 异常低 vol regime 让 absolute VIX 看似过低；IVP 相对分位仍 valid
3. **Counterfactual blindness**：缺少「同时跑 baseline 与候选 + 比较 forward returns」的 mental model

---

## 5. Q063 关闭 — 不修订 SPEC

| 项 | 状态 |
|---|---|
| SPEC change | **None** — IVP < 55 gate 保留 |
| Code change | None |
| Deploy | Not required |
| Live recommendation today | 保持 reduce_wait (IVP=64 ≥ 55)，gate 正在 protect |

---

## 6. Watchlist（可选 follow-up，PM 决定）

| 选 | 含义 | 优先级 |
|---|---|---|
| Strengthen gate | IVP > 50 in low-VIX block (gate even tighter)——既然 gate 在 low VIX 真正起作用，也许阈值可更紧 | Low（先验更复杂的 gate 容易 overfit） |
| Q063.1 IVP-IVR-VIX3M 联合 gate | 探索三因子复合 gate 是否优于纯 IVP | Low（边际收益可能更小） |
| Q063.2 BPS gate 重写为 prob-based | 用 ML / regression 直接预测 tail prob 而非 threshold | Medium-Low（工程量大） |

---

## 7. Artifacts

- `research/q063/q063_phase1_vix_stratified_blocked_trades.py`
- `research/q063/q063_phase2_candidate_gates.py`
- `research/q063/q063_phase3_robustness.py`
- `research/q063/q063_phase4_decay_weighted.py`
- `research/q063/q063_phase1_blocked_trades.csv`
- `research/q063/q063_phase2_gate_comparison.csv`
- `task/q063_phase4_closure_memo_2026-05-11.md`（本文档）

---

## 8. Quant standing recommendation

**Live recommendation for 2026-05-11 unchanged**：
- Main SPX strategy currently in `reduce_wait` (IVP=64 ≥ 55)
- This is the **gate working as designed**——历经 Q063 验证，**no override warranted**
- Wait for IVP to drop below 55 (1y rolling will gradually shift as old high-IV bars roll out of window)
- 若 PM 想 manually override（个案判断），按 SPEC-094 主策略 manual SOP 流程；但 Q063 数据建议**默认尊重 gate**

Q063 closed.

---

## 9. Supplement 2026-05-13 — Q067 Threshold Jitter & Window Sensitivity

2nd Quant 提出 "IVP 55 是 rank-jump 工件不是经济悬崖" 担心；PM 加入窗口长度敏感性问题。Q067（[research/q067/q067_memo_2026-05-13.md](../research/q067/q067_memo_2026-05-13.md)）量化结果：

| 量化项 | 结果 | 说明 |
|---|---|---|
| Rank-jump empirically 确认 | VIX median [55,60) IVP = 17.27，[50,55) = 17.85 | 穿过 55 时 actual VIX 可下降 |
| Daily flip rate (19yr) | **7.37%** | 359 / 4871 TD |
| Daily flip rate (最近 1 年) | **11.5%** | 显著恶化 |
| 5-TD flip-flop | **61%** (219 / 359) | 阈值附近极不稳定 |
| Window 126 vs 252 disagree | **15.15%** TD | |
| Window 252 vs 504 disagree | **15.60%** TD | |
| Window 分歧落在 IVP [40,70] | **69.8%** | jitter 与窗口是同一现象 |

**结论修订**（不动 Q063 verdict 主体）：

1. ✅ **Q063 verdict 仍成立**：keep `BPS_NNB_IVP_UPPER = 55` simple hard gate；不放宽
2. ⚠ **承认 gate 性质**：empirical low-vol repricing filter，非经济悬崖
3. ⚠ **Phase 2 升级 standing monitoring → 条件研究任务**（触发条件：live 中 candidate entry 首次落在 IVP [50, 65] 区间）
4. ⚠ **窗口选择需 SPEC review 显式记录**：当前 252d 是默认值不是最优值；126d 会多 block ~3pp、504d 会少 block ~3pp

**Phase 2 推荐研究内容（条件触发后）**：

| 变体 | 设计 | 备注 |
|---|---|---|
| 收紧式 hysteresis | block if IVP > 55；unblock only if IVP < 50 持续 N TD (N=3/5/10) | **不放宽 block，更严格 unblock** |
| Multi-horizon agreement | block if ivp252 > 55 AND ivp63 > 50 | 要求 short-window 也确认 |
| 跨窗口稳定性 | block if **任一**窗口 > 55；或 **多数**窗口 > 55 | 测试 window-agnostic gate |

**禁止测试**：放宽 block 阈值（55 → 60/65 等）——已被 Q063 Phase 5 否决，重复研究浪费 cycle。

**生产文档化建议**（[strategy/selector.py:175](../strategy/selector.py#L175) 上方加注释）：

```text
# BPS_NNB_IVP_UPPER = 55 is an empirical low-vol repricing filter, NOT a
# precise volatility cliff. Q067 (2026-05-13) confirmed rank-jump artifact:
# VIX median in IVP [55, 60) is LOWER than in [50, 55). 7.37% historical /
# 11.5% recent daily decision flip rate; 61% of flips reverse within 5 TD.
# Q063 Phase 4 + Phase 5 evidence supports this hard gate; relaxation
# alternatives all underperformed. Standing monitoring: candidate-entry
# IVP jitter sensitivity for Phase 2 hysteresis trigger.
```

**Status**：Q063 main verdict UNCHANGED；Q067 supplement filed；Phase 2 conditional research backlog opened（不主动启动）。

---

## 10. Supplement 2026-05-13 — Q067 Phase 2 EXECUTED — All variants FAIL

PM 决定提前启动 Phase 2（不等 live trigger）。详 [research/q067/q067_phase2_memo_2026-05-13.md](../research/q067/q067_phase2_memo_2026-05-13.md)。

**结果**：5 个变体在 19yr backtest + flip rate 度量下全部 **fail strict dominance**：

| 变体 | bps_n | Δ Ann PnL | flip rate | Δ worst | 决策 |
|---|---|---|---|---|---|
| V0 baseline | 38 | — | 7.89% | -$9,379 | ref |
| V1a hyst N=3 | 15 | -$2,433 | 4.15% | -$2,642 worse | ❌ |
| V1b hyst N=5 | 5 | -$3,920 | 3.41% | +$5,700 | ❌ |
| V1c hyst N=10 | 0 | -$4,194 | 2.32% | $0 (no trades) | ❌ |
| V2 multi-horizon | 48 | +$956 | 8.74% worse | -$2,642 worse | ❌ |
| V3 crosswin any | 10 | -$3,473 | 8.76% worse | $0 | ❌ |

### 三方向各自的死因

| 方向 | 死因 |
|---|---|
| V1 hysteresis | Unblock 收紧 → block 总量增加 → alpha 流失（线性单调）|
| V2 multi-horizon | AND 联立实质放宽 block → 落入 Q063 Phase 5 否决领域；两 horizon 抖动叠加反而 flip rate 恶化 |
| V3 cross-window any | 三 percentile series 独立抖动 → OR 联立放大 flip rate |

### 综合 verdict

**Q063 + Q067 双 phase 实证一致**：`IVP_252 ≥ 55` simple hard gate 是 19yr 样本下的 empirical local optimum。

- ✅ **生产 production 保持不变**（`BPS_NNB_IVP_UPPER = 55`, `LOOKBACK_DAYS = 252`）
- ✅ Phase 2 backlog **正式关闭**（已实证，无 strict-dominance 变体）
- ⚠ 若 PM 未来 willing to trade $2.4k/yr alpha for halved flip rate → V1a (N=3) 是可选 fallback；但 Quant 当前不推荐
- ⚠ Jitter 是 percentile 度量内在性质，threshold-based gate 无法消除。若要彻底解决需 **非 threshold-based** signal（如 smoothed IVP / regime detection），属新研究方向（potential Q068）

### Phase 2 close-out

| 状态 | 内容 |
|---|---|
| Q063 main verdict | UNCHANGED |
| Q067 Phase 1 (jitter measurement) | DONE |
| **Q067 Phase 2 (variants test) | DONE — ALL FAIL** |
| Production code | UNCHANGED |
| 待加注释到 [strategy/selector.py:175](../strategy/selector.py#L175) | 是（Phase 2 结果纳入注释段落，由 Developer 后续动 code）|

**Status**：Q063 + Q067 全部 CLOSED。Production code 注释更新作为单独工单交付 Developer（不动 functional logic）。

---

## 11. Supplement 2026-05-13 — Q068 也 CLOSED (三轮一致 verdict)

PM 提出 Q068 hypothesis：IVP > 55 gate 在低波环境下漏掉 SPX 靠近 MA10 的 dip-entry。Q068 完整执行 Round 1（粗设计）+ Phase 6（narrow override per 2nd quant）+ Phase 7（regime stops）。

详 [research/q068/q068_memo_2026-05-13.md](../research/q068/q068_memo_2026-05-13.md) + 2nd Quant review:
- [task/q068_ma_timing_2nd_quant_review_packet_2026-05-13.md](q068_ma_timing_2nd_quant_review_packet_2026-05-13.md)
- [task/q068_ma_timing_2nd_quant_review_packet_2026-05-13_Review.md](q068_ma_timing_2nd_quant_review_packet_2026-05-13_Review.md) — **PASS / KEEP V0**

### Q068 综合结果

| 维度 | 结果 |
|---|---|
| Round 1 6 变体 | 仅 V5c (+$552/yr) 干净 +alpha 但缺 guardrails |
| Phase 6 narrow override (P6A/B/C) | 全部 worst trade 恶化 -$5.7k 到 -$6.3k；Go 条件未全 PASS |
| Phase 7 regime stops | V0+stops 损害 alpha -$23k 到 -$40k；P6A × S1 救 worst 但 -$1k/yr 保险费 |
| 2026-02-25 hard check | ✅ 所有 override 当日 block |
| 2026-05-04 + 2026-05-12 dips | P6B/C 救得了，但这些变体 19yr fail |
| PM 5/7 example | baseline 已 allow (IVP=45.6 < 55)，不需 override |

### 三轮一致 verdict

**Within the tested IVP-threshold / hysteresis / MA-timing / regime-stop family, current hard `IVP > 55` gate remains the best production rule.**

| 研究 | 测试方向 | 结果 |
|---|---|---|
| Q063 Phase 5 | Multi-factor relaxation | REJECTED |
| Q067 Phase 2 | Hysteresis / multi-horizon / cross-window | ALL FAIL |
| Q068 Phase 6 | MA-timing override (narrow) | ALL FAIL Go 条件 |
| Q068 Phase 7 | Regime stops (VIX rise / MA10 break) | Stops are not free |

### Q063 / Q067 / Q068 全部 CLOSED

| 项 | 状态 |
|---|---|
| `BPS_NNB_IVP_UPPER = 55` | UNCHANGED |
| `LOOKBACK_DAYS = 252` | UNCHANGED |
| MA override / hysteresis / regime stop | ALL REJECTED |
| Formal paper trade | NOT STARTED |
| Q069 regime-conditional research | NOT STARTED |
| Engine.py research-mode flags | KEEP (default disabled) — `regime_stop_*` + `force_strategy` 类似 |
| 可选 shadow tag for future monitoring | NOT IMPLEMENTED (PM 未要求) |

未来若要重启 IVP-gate 相关研究，应是**真正不同的 hypothesis**（如 smoothed IVP / regime detection），不是继续在 hard gate 周边小修小补。

**Status**：Q063 + Q067 + Q068 全部 CLOSED。Production code 不动。Research-mode flags 保留为可复用 infrastructure。

---

## 12. Supplement 2026-05-13 — Q069 也 CLOSED (五方向一致 verdict)

PM 推进 2nd Quant 提议的 "smoothed IVP / regime detection / 非 threshold-based" 方向。Q069 完整执行 Phase 1 (smoothing 5 变体) + Phase 2 (slope-aware 4 变体)。

详 [research/q069/q069_phase1_memo_2026-05-13.md](../research/q069/q069_phase1_memo_2026-05-13.md) + [research/q069/q069_phase2_memo_2026-05-13.md](../research/q069/q069_phase2_memo_2026-05-13.md)

### Q069 综合结果

| Phase | 变体 | 主要 failure |
|---|---|---|
| Phase 1 Smoothed IVP | SMA 3/5/10 + EWM α=0.3/0.1 | Lag → 全部 worst trade -$15,119 |
| Phase 2 Slope-aware | M1-M4 | **全部放行 2026-02-25 hard guardrail** + flip rate 反而恶化 |

### Phase 1 vs Phase 2 揭示的 fundamental

- Phase 1 smoothing 死因: lag → 错过 risk ramp-up
- Phase 2 slope-aware 死因: 错过 "elevated but easing" risk

**两类 failure modes 互斥但都坏** → threshold-based gate "软化"在统计上无法 simultaneously avoid 两类 failure。

### 五方向一致 verdict

| 研究 | 方向 | 结果 |
|---|---|---|
| Q063 Phase 5 | Multi-factor relax | REJECTED |
| Q067 Phase 2 | Hysteresis | ALL FAIL |
| Q068 Phase 6 | MA timing override | ALL FAIL Go 条件 |
| Q068 Phase 7 | Regime stops | Stops not free |
| Q069 Phase 1 | Smoothed IVP | ALL FAIL (lag) |
| Q069 Phase 2 | Slope-aware IVP | ALL FAIL hard guardrail |

**Hard `IVP > 55` gate 在 tested space 是 confirmed empirical local optimum**。

### Q063 / Q067 / Q068 / Q069 全部 CLOSED

| 项 | 状态 |
|---|---|
| `BPS_NNB_IVP_UPPER = 55` | **UNCHANGED (final)** |
| `LOOKBACK_DAYS = 252` | UNCHANGED |
| Smoothed IVP | REJECTED |
| Slope-aware IVP | REJECTED |
| Regime-state R1/R2 | NOT STARTED（重复 M3/M4 framework）|
| Non-threshold-based (Bayesian / ML / continuous-score) | 独立 future SPEC，非 Q069 phase |
| Engine research-mode flags | KEEP (Q068 P7 added, default disabled) |

### 关键判断

> **"This is not something more research effort can solve. It is a fundamental statistical property of percentile-based threshold gates."**

5 个独立方向 unanimous fail 是足够强的证据。Future PM 决策应：
- 接受 "IVP > 55 is final answer in tested space"
- 把研究 effort 转向其他 strategy parameters
- 仅在有真正不同的 framework (probabilistic / Bayesian / cross-asset) 时再重启 IVP gate 研究，且作为独立 SPEC

**Status**：Q063 + Q067 + Q068 + Q069 全部 CLOSED。Production code 不动。

---

## 13. Supplement 2026-05-13 — Closure APPROVED by 2nd Quant

完整 review: [task/q063_q067_q068_q069_closure_2nd_quant_review_2026-05-13.md](q063_q067_q068_q069_closure_2nd_quant_review_2026-05-13.md)

### Closure verdict (per 2nd Quant)

> **APPROVE CLOSURE.** Q063, Q067, Q068, and Q069 collectively provide sufficient evidence that the current hard `IVP_252 >= 55` BPS NNB gate should remain unchanged. The gate is noisy and has known percentile-rank jitter, but every tested repair path either re-admits bad trades, worsens worst-trade risk, reduces long-run alpha, or fails hard-guardrail checks. Close all IVP-gate micro-optimization work. Future research should only reopen this area under a genuinely different probabilistic or cross-asset risk framework.

### Mechanism explanation 必须保留在 strategy docs（per 2nd Quant §1）

> **VIX 绝对值低，不代表 IVP 相对位置低**。
> VIX 15-17 + IVP 60-65 可能是 "complacency before mean reversion"，**不是**安全卖 premium 的窗口。

这是 IVP/VIX 一切争论的 baseline 解释。已嵌入 [strategy/selector.py:185](../strategy/selector.py#L185) inline 注释。

### Code comment 已实施 (per 2nd Quant §5)

[strategy/selector.py:187-203](../strategy/selector.py#L187) `BPS_NNB_IVP_UPPER = 55` 上方 inline 注释，记录：
- Q063 confirmed relaxation re-admits negative-alpha entries
- Q067 confirmed jitter (7.37%/11.5% flip rates) 但 fixes 都失败
- Q068 MA-timing override + regime stops 失败
- Q069 smoothed + slope-aware 失败
- Mechanism: low VIX absolute ≠ low IVP relative

### Q067 核心 takeaway 必须记录（per 2nd Quant §2）

> **Jitter is real, but tested jitter fixes are worse than the original hard gate.**

### Q068 核心 takeaway 必须记录（per 2nd Quant §3）

> **PM intuition is valid as a trading observation, but not stable enough for rule-level adoption.**

特别 short-premium gate：例外规则放行更多 trades → tail-risk 代价常大于近期直觉收益。

### Q069 wording adjusted（per 2nd Quant §4）

"This is not something more research effort can solve" 收紧为：
> **Within percentile-threshold, smoothing, slope-aware, MA-timing, and simple regime-stop frameworks, additional micro-optimization is unlikely to solve the issue. Future work should require a genuinely different framework, such as probabilistic / Bayesian / cross-asset risk modeling.**

不写 "永远不能研究"，保留 future Q070 / Bayesian / cross-asset 作为 future independent SPEC option。

### Future research reopen criteria (per 2nd Quant §6) — high bar

未来重启 IVP gate 研究必须满足以下条件**之一**：

1. **使用完全不同的信息集**: credit spreads, rates, breadth, vol surface, VVIX, macro/liquidity variables
2. **使用完全不同的建模形式**: probabilistic tail-risk score, Bayesian state model, calibrated loss-probability model
3. **有新的 live evidence**: repeated blocked entries with documented positive counterfactual PnL across enough samples
4. **账户 / strategy routing materially changes**: BPS NNB capital share becomes much larger, requiring revised risk-return calibration

**不应再测试** (已充分覆盖):
- IVP 55 → 60/65
- IVP hysteresis
- MA5/MA10 override
- simple VIX rising/falling confirmation
- smoothed IVP
- IVP slope filter

### Final consolidated status

| 项 | 状态 |
|---|---|
| `BPS_NNB_IVP_UPPER = 55` | **UNCHANGED (final, 2nd Quant approved)** |
| `LOOKBACK_DAYS = 252` | UNCHANGED |
| selector.py inline comment | ✅ ADDED 2026-05-13 |
| Q063 / Q067 / Q068 / Q069 | ALL CLOSED |
| Future Q070+ IVP research | Open under high-bar conditions only |
| Engine research-mode flags (Q068 P7) | KEEP, default disabled |

**Status: APPROVED CLOSURE. All four IVP-gate research lines closed.**
