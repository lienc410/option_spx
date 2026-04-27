# Q021 Phase 4 — Aftermath First-Entry Sizing Curve

- 日期：2026-04-26
- Author: Quant Researcher
- Phase 1: `doc/q021_phase1_attribution_2026-04-25.md`
- Phase 2: `doc/q021_phase2_full_engine_2026-04-25.md`
- Phase 3 (含 V_D 补测): `doc/q021_phase3_half_size_2026-04-25.md`
- 2nd Quant Round 1 CHALLENGE: `tests/q021_2nd_quant_handoff_2026-04-25.md`
- 2nd Quant Round 2 CHALLENGE (V_D): `task/q021_2nd_quant_review_handoff_2.md`
- Prototype: `backtest/prototype/q021_phase4_sizing_curve.py`
- 标准指标包永久规则: `~/.claude/projects/.../memory/feedback_strategy_metrics_pack.md`（Phase 4 触发的 PM standing rule）

---

## TL;DR

**所有 sizing-up 变体都验证为 leverage drag，没有 smart-edge。**

2nd Quant Round 2 的核心怀疑被 6 变体数据严格证实：

| 关键判别 | 数值 | 结论 |
|---|---|---|
| V_A baseline PnL/BP-day | **+$4.85** | smart-rule 必须超过这个数 |
| V_G marginal $/BPd | +$3.83 | < baseline → leverage |
| V_D marginal $/BPd | +$3.37 | < baseline → leverage |
| V_J marginal $/BPd | +$2.98 | < baseline → leverage |
| V_E marginal $/BPd | +$2.70 | < baseline → leverage |

**V_D 多挣的 +$27,823 是用 +$8,260 BP-days 换来的，每多 1 BP-day 只挣 $3.37 — 比 baseline 资本效率低 30%。** 把 V_J（限制重叠 leverage）和 V_E（半 size）放进来后看到 sizing curve 是一条递减曲线，不是 step function — 没有任何风险集中方式让 marginal $/BPd 回到 baseline 之上。

**Phase 4 推荐**：

1. **关闭 V_D / V_E / V_J 候选**，回到 1st Quant 原始推荐 **(a) 保留 SPEC-066 close Q021**
2. **V_G 作为 future spec 候选保留但不晋升**：disaster-cap 是最干净的 sizing 变体（disaster +$176 / marginal $3.83），但仍未能跨过 baseline
3. **V_H split-entry 不构成独立选项**：本质是 V_A 减一笔，PnL -$1,874，无统计意义

---

## 1. Phase 4 触发与设计

### 1.1 Phase 3 V_D 数据看似强

- 全样本 PnL +$431,673（V_A +6.9%）
- Sharpe 0.45 vs 0.42
- MaxDD -$9,749 vs -$10,323
- 2026-03 双峰 case 翻倍

但 2nd Quant (`task/q021_2nd_quant_review_handoff_2.md`) 指出：

> **V_D 是 leverage effect，不是 smarter rule。**
> 
> 增量资本效率 = (PnL_D − PnL_A) / (BPdays_D − BPdays_A) ≈ $3.37/BP-day，比 V_A baseline $4.85 低 30%。这意味着 V_D 多挣 PnL 的代价是更低质量的边际美元。
> 
> 必须做 sizing-curve 对照：1× / 1.5× / 2×、有/无重叠限制、有/无 disaster gate。如果 sizing 曲线整段都在 baseline 之下，V_D 不是 promote 候选。

### 1.2 PM 决策（2026-04-25）

1. **永久 standing rule**: 所有未来 strategy/spec 比较必须包含完整指标包（marginal $/BP-day、worst trade、disaster window、max BP%、concurrent 2× 天数、CVaR 5%、IC_HV decomposition）。已存为 memory（`feedback_strategy_metrics_pack.md`）。
2. **Phase 4 scope**: 选 6 变体（option 2）— V_A / V_D / V_E / V_J / V_H / V_G。
3. **不做 9×4 cluster sweep** — 2nd Quant 明确建议先回答 sizing 问题。

### 1.3 6 变体规则

| Variant | 规则 | 含义 |
|---|---|---|
| **V_A SPEC-066** | cap=2 / cluster；正常 size | 当前生产 baseline |
| **V_D 2× first** | cap=1 / cluster；首笔 2× | Phase 3 PM 直觉 |
| **V_E 1.5× first** | cap=1 / cluster；首笔 1.5× | sizing 曲线中间点 |
| **V_J 2× no overlap** | cap=1 / cluster；首笔 2×，但若已有 IC_HV 持仓则降回 1× | 限制 distinct cluster 重叠 leverage |
| **V_H split entry** | cap=2 / cluster；同 cluster 第 2 笔仅在 VIX 未反弹时入场（split-entry gate） | 2nd Quant 提的 1×+1× 替代 |
| **V_G 2× disaster cap** | V_D 规则；但当日 VIX ≥ 30 → 降回 1× | 加 disaster size cap |

注：V_G `DISASTER_VIX_THRESHOLD` 起始定为 35，回测发现 aftermath 首笔 VIX 从未达 35（threshold inert），降至 30 后开始触发。详见 `q021_phase4_sizing_curve.py` 注释。

---

## 2. 系统层结果

### 2.1 全样本

| Variant | n | Total PnL | Sharpe | MaxDD | Δ vs V_A |
|---|---:|---:|---:|---:|---:|
| **V_A** | 400 | **+403,850** | **+0.42** | **-10,323** | — |
| V_D | 394 | +431,673 | +0.45 | -9,749 | +27,823 |
| V_E | 394 | +414,173 | +0.43 | -10,036 | +10,323 |
| V_J | 394 | +414,394 | +0.43 | -9,749 | +10,544 |
| V_H | 399 | +401,976 | +0.42 | -10,323 | -1,874 |
| V_G | 394 | +418,372 | +0.43 | -9,749 | +14,522 |

PnL 排序：V_D > V_G > V_J ≈ V_E > V_A > V_H。

### 2.2 Recent slice 2018+

| Variant | n | Total PnL | Sharpe | MaxDD | Δ vs V_A |
|---|---:|---:|---:|---:|---:|
| V_A | 146 | +164,958 | +0.49 | -9,405 | — |
| V_D | 140 | +172,116 | +0.52 | -9,392 | +7,158 |
| V_E | 140 | +165,885 | +0.50 | -9,392 | +927 |
| V_J | 140 | +169,425 | +0.51 | -9,392 | +4,467 |
| V_H | 145 | +163,055 | +0.48 | -9,405 | -1,903 |
| V_G | 140 | +170,756 | +0.51 | -9,392 | +5,798 |

近期切片排序与全样本一致；V_E 在近期 slice 几乎完全失去 alpha（+$927）。

---

## 3. 标准指标包 — 全样本（核心证据）

| Variant | PnL/BPd | Marginal $/BPd | Worst | IC_HV CVaR5% | MaxBP% | #2× ovl days |
|---|---:|---:|---:|---:|---:|---:|
| **V_A** | **+4.85** | — | -8,564 | **-2,383** | **14.0%** | 0 |
| V_D | +4.72 | **+3.37** | -8,564 | -2,580 | 42.0% | **27** |
| V_E | +4.76 | +2.70 | -8,564 | -2,580 | 31.5% | 27 |
| V_J | +4.78 | +2.98 | -8,564 | -2,580 | 28.0% | 0 |
| V_H | +4.84 | +24.34 (n/a) | -8,564 | -2,383 | 14.0% | 0 |
| V_G | +4.81 | +3.83 | -8,564 | -2,580 | 35.0% | 5 |

**关键观察**：

1. **没有 doubler 跨过 baseline**。V_A PnL/BPd = $4.85；所有 doubler 的 marginal $/BPd 都低于此（V_G $3.83 最高，V_E $2.70 最低）。这是 sizing curve 形状的**直接证据**：每加 1 BP-day 都不如 V_A 现有规则赚得多。

2. **V_H marginal $/BPd 看似 +$24.34 是退化**。V_H IC_HV PnL 比 V_A 少 $1,874，BP-days 也少 ~77。两个负数相除得正数，但语义上 V_H = V_A − 1 trade，没新信号；本指标不适用。

3. **CVaR 5% 整齐分两组**：V_A / V_H = -$2,383，所有 doubler = -$2,580。这是因为 doubler 删掉了 V_A 的同 cluster 第 2 笔（往往是中等亏损），底部 5% 全是 disaster 单笔，size 翻倍直接体现在 CVaR。**所有 sizing 变体的 IC_HV tail 一致变差**（且变差幅度相同）。

4. **V_J 的 #2× ovl days = 0** 证实其规则 (no overlapping 2× clusters) 起作用，但 PnL 仅 +$10,544 — 与 V_E（+$10,323，无 overlap 限制）几乎相同。**说明 V_D 多出的 ~$17K 几乎全部来自 distinct-cluster 同时 2× 持仓的 leverage。**

5. **V_G 是最可控的 doubler**：MaxBP 35% > V_J 28% < V_D 42%；marginal $3.83 > V_D $3.37；disaster +$176 > V_A +$302 但 > V_D -$748。

---

## 4. IC_HV vs 非 IC_HV 拆解

| Variant | IC_HV n | IC_HV PnL | nonIC_HV n | nonIC_HV PnL | Σ check |
|---|---:|---:|---:|---:|---:|
| V_A | 107 | +71,169 | 293 | +332,681 | +403,850 |
| V_D | 101 | +98,992 | 293 | **+332,681** | +431,673 (IC+27,823, non+0) |
| V_E | 101 | +81,492 | 293 | **+332,681** | +414,173 (IC+10,323, non+0) |
| V_J | 101 | +81,713 | 293 | **+332,681** | +414,394 (IC+10,544, non+0) |
| V_H | 106 | +69,295 | 293 | **+332,681** | +401,976 (IC-1,874, non+0) |
| V_G | 101 | +85,691 | 293 | **+332,681** | +418,372 (IC+14,522, non+0) |

**6 个变体非 IC_HV PnL 严格相等 ($332,681)**。这是 Phase 3 § 2.3 的延续 — IC_HV cap/size 改动**完全不影响**其他策略。Q021 整个争论封闭在 IC_HV 子策略内，无 portfolio crowding 风险。

---

## 5. 2026-03 双峰 case（PM 直觉来源）

| Variant | Trade 1 | Trade 2 | Net |
|---|---|---|---:|
| V_A | 03-09 (0.23) +$580 | 03-10 (0.24, same cluster) +$604 | **+$1,184** |
| V_D | 03-09 (**0.46, 2×**) +$1,161 | 03-16 (**0.52, 2× distinct**) +$1,428 | **+$2,589** |
| V_E | 03-09 (0.35, 1.5×) +$871 | 03-16 (0.39, 1.5× distinct) +$1,071 | +$1,942 |
| V_J | 03-09 (0.46, 2×) +$1,161 | 03-16 (**0.26, 1× downgraded**) +$714 | +$1,875 |
| V_H | 03-09 (0.23) +$580 | 03-10 (0.24) +$604 | +$1,184 |
| V_G | 03-09 (0.46, 2×) +$1,161 | 03-16 (0.52, 2× distinct) +$1,428 | +$2,589 |

V_J 在 PM case 上较 V_D 少赚 $714（即 distinct cluster 第 2 笔被降回 1×）。这正是 V_J 多挣 $10K 与 V_D 多挣 $28K 之间 $18K 差距的缩影。

---

## 6. Disaster windows

| Variant | n | W/L | Net | 单点细节 |
|---|---:|---|---:|---|
| **V_A** | 5 | 3W/2L | **+$302** | COVID 2×$-1,657 = $-3,314；Tariff 3×$+1,959 = $+5,877 |
| V_D | 4 | 2W/2L | -$748 | COVID 2×$-3,314 = $-6,628；Tariff 2×$+2,566 = $+5,132 |
| V_E | 4 | 2W/2L | -$561 | COVID 2×$-2,485；Tariff 2×$+1,924 |
| V_J | 4 | 2W/2L | -$99 | COVID 2×$-2,665；Tariff 2×$+2,566 |
| V_H | 5 | 3W/2L | +$302 | 与 V_A 相同 |
| **V_G** | 4 | 2W/2L | **+$176** | COVID 2×$-1,657 = $-3,314（disaster cap 触发，降回 1×）；Tariff 2×$+1,833 |

**V_G 是唯一在 disaster 窗口净值接近 V_A 的 doubler**：disaster cap 在 COVID 触发，单笔损失保持 V_A 水平 $-1,657（不像 V_D 翻倍至 $-3,314）。这印证 V_G 设计意图。

但即便如此，V_G marginal $/BPd 仍只有 $3.83，依然低于 baseline。

---

## 7. Cluster coverage

| Variant | #after_trades | #clusters_hit | #multi | avg/hit |
|---|---:|---:|---:|---:|
| V_A | 60 | 41 | 18 | 1.46 |
| V_D / V_E / V_J / V_G | 56 | 53 | 3 | 1.06 |
| V_H | 59 | 41 | 17 | 1.44 |

所有 cap=1 doubler 覆盖更多 cluster (53 vs 41) 但每 cluster 只 1 笔；V_A/V_H 集中在 41 cluster 但 18 个有 2 笔。**信号选择的 trade-off**：cap=1 + boosted size 可换 cluster 广度，但代价是丢同 cluster 第 2 笔（$13,249 在 V_A 中 → V_C/V_D 全部丢失）。

---

## 8. Sizing 曲线观察（Phase 4 核心定量发现）

把 4 个 doubler（V_E/V_J/V_D/V_G）按 IC_HV PnL 排序：

| Variant | Multiplier | overlap allowed | IC_HV PnL | ΔvsV_A | BP-days Δ | Marginal $/BPd |
|---|---:|---|---:|---:|---:|---:|
| V_E | 1.5× | yes | +81,492 | +10,323 | +3,825 | **+2.70** |
| V_J | 2× | no | +81,713 | +10,544 | +3,535 | +2.98 |
| V_D | 2× | yes | +98,992 | +27,823 | +8,259 | +3.37 |
| V_G | 2× + disaster cap | yes | +85,691 | +14,522 | +3,786 | **+3.83** |

观察：
- **V_E 与 V_J PnL 几乎相等** ($81.5K / $81.7K) — 1.5× 全允许重叠 ≈ 2× 禁止重叠。这两个数据点限定了 "single concentrated 2× position" 的 ceiling。
- **V_D = V_J + overlap leverage**: V_D 比 V_J 多挣 $17,279 (= +27,823 − +10,544)，对应 +4,724 BP-days，单价 $3.66/BPd。也就是说**重叠 2× 仓位贡献的边际 $/BPd 仍低于 baseline**。
- **V_G = V_D − disaster days**: V_G 比 V_D 少挣 $13,301，少用 4,473 BP-days，但 disaster window 由 −$748 → +$176（+$924 的 tail saving）。**disaster cap 用 BP 效率换 tail safety**。

整条 sizing curve 的 marginal $/BPd 曲线：

```
multiplier = 1×              baseline V_A           4.85
multiplier = 1.5× (V_E)                            2.70
multiplier = 2× no overlap (V_J)                   2.98
multiplier = 2× w overlap (V_D)                    3.37
multiplier = 2× w disaster cap (V_G)               3.83
                                                   ────
                                                   全部 < baseline
```

**结论**：sizing curve 在 [1×, 2×] 区间没有任何点击穿 V_A baseline。V_D 看似优于 V_A 是因为它在 2× 段最高（$3.37），但仍比 V_A 1× 段低 30%。

---

## 9. 直接回应 2nd Quant 7 项 push-back

| 2nd Quant 提议 | Phase 4 验证 |
|---|---|
| V_E 1.5× | 测试。PnL +$10K（线性预测 +$14K，亚线性），marginal $2.70（最差） |
| V_F 条件 2× | 未测（filter 候选未实现，PM scope 未含） |
| V_G disaster cap | 测试。最干净的 doubler，marginal $3.83，disaster +$176 |
| V_H split entry | 测试。本质是 V_A − 1 trade，无 alpha |
| V_I total IC_HV BP cap | 未测（与 V_J no-overlap 大致同向，被 V_J 替代） |
| V_J no overlap | 测试。证实 V_D 17K 增量主要来自 overlap leverage |
| V_K recent-era only | 已含 §2 recent slice |
| 标准指标包必备 | **PM 已立永久 rule** |

7 项中 5 项被 Phase 4 6 变体覆盖（V_E/V_G/V_H/V_J + recent slice）。V_F 条件 2× 与 V_I total cap 未单独做 — V_J 已基本覆盖 V_I 思路。**核心问题（"sizing 曲线哪段有 smart edge"）已答**：没有。

---

## 10. 推荐决策（V_D 否决，回到 V_A）

### 10.1 第一推荐 — **(a) 保留 SPEC-066，close Q021**（与 Phase 3 §4 第一推荐一致）

理由更新（vs Phase 3 V_D 测试时）：

1. **Phase 4 sizing curve 全段低于 baseline**：V_D 的 PnL +6.9% 是用 +9.9% BP-days 换的，每多 1 BP-day 的边际收益 < V_A 自身平均 1 BP-day 收益的 70%
2. **Tail risk 一致变差**：所有 cap=1+booster 变体 IC_HV CVaR 5% 同步下沉到 -$2,580，**这是结构性代价**，不是 V_D 的特殊问题
3. **2nd Quant 的核心怀疑被精确验证**：V_J 与 V_E 隔离出 leverage 与 first-entry concentration 的贡献，结果显示 leverage 段贡献最大但 marginal $/BPd 还是低
4. **V_H 否定 split-entry**：1×+1× 不是 V_A 与 V_D 之间的 sweet spot — split entry 反而少 1 trade

### 10.2 V_G 是 future spec 候选（不晋升）

如果 PM **未来** 想做 size-up policy（不在 Q021 范围）：

- V_G 是最干净的版本（marginal $3.83，disaster +$176，MaxBP 35%）
- 但即便如此 marginal $/BPd 仍 < baseline，**无 smart edge 证据**
- 暂存为 future research note（如有 IV / regime / earnings 等额外 filter，再回来评估）

### 10.3 关闭 Q021 的具体动作

1. `sync/open_questions.md` Q021 状态改 `closed`，链接 Phase 1+2+3+4 四 doc
2. `task/SPEC-066.md` 加 changelog：`2026-04-26 Quant Phase 4 sizing-curve 6 变体复审：所有 sizing-up 变体（V_D/V_E/V_J/V_G）marginal $/BP-day 均低于 V_A baseline $4.85，无 smart edge；保留 SPEC-066 不改动`
3. `RESEARCH_LOG.md` 加 R-20260426-XX 引用 Phase 4
4. 不开 SPEC-067 DRAFT
5. 不阻塞 Q029 / Q032 下游

### 10.4 如 PM 仍想保留 V_D 选项

可选的次优路径：

- **V_G 路径**: 写 `task/SPEC-067-DRAFT.md` 对 V_G 做 pilot study（需先解决 BP ceiling parity + Live SizeTier 一致性，归入 Q029 work）
- **不推荐**: 直接上 V_D / V_J（leverage 信号未通过 marginal test）

---

## 11. 输出物

- `backtest/prototype/q021_phase4_sizing_curve.py` — 6 变体 + 标准指标包 prototype
- `doc/q021_phase4_sizing_curve_2026-04-26.md` — 本文
- 标准指标包 memory: `~/.claude/projects/.../memory/feedback_strategy_metrics_pack.md`
- Phase 1-3 doc 与 1st/2nd Quant review packet 引用见标题区

---

## 12. 边界与未做

| 边界 | 原因 |
|---|---|
| V_F 条件 2× (quality filter) 未测 | PM scope 未含；filter 候选不在 q021 prototype 范围 |
| V_I total IC_HV BP cap 未单独测 | V_J no-overlap 已基本覆盖（限制 distinct cluster 重叠 = 限制 total BP）|
| Cluster threshold sensitivity 未做 | 2nd Quant 明确建议先答 sizing 问题；Phase 4 6 变体已显示 sizing 全段失败，cluster sweep 优先级更低 |
| BP ceiling parity / Live SizeTier 检查 | 不属 Q021；归入 Q029 / SPEC-072 |
| Sortino / Calmar 等扩展 metric | 标准指标包已含 CVaR / MaxDD / Worst trade，扩展 metric 不会改变 marginal $/BPd 的判别 |

---

## 13. 总结

**Phase 4 6 变体 sizing-curve study 的最终发现**：

> aftermath 第一笔 sizing-up 在 1× 之上没有 smart-edge 区段。所有 V_D/V_E/V_J/V_G 看似优于 V_A 的 PnL 都是 leverage drag — 边际美元的资本效率比 V_A baseline 低 19%-44%。

V_A SPEC-066 是 Phase 1-4 全部测试中唯一通过 marginal $/BP-day 检验的方案。**Q021 应 close，不开 SPEC-067**。

Phase 4 的最大持久价值不在于结果本身，而在于 **PM 立的标准指标包 standing rule** — 这个规则会让未来所有 strategy/spec 比较都包含 marginal $/BP-day 等指标，避免再次出现 "看似优于 baseline 实则 leverage drag" 的判定误差。
