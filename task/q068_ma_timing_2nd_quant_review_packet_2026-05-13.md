# Q068 MA-Timing Override — 2nd Quant Review Packet

- **Date**: 2026-05-13
- **Prepared by**: Quant Researcher
- **Audience**: 2nd Quant Reviewer
- **Topic**: BPS NNB IVP > 55 gate 是否应加 MA-based timing override 捕捉低波环境短线 dip-entry？
- **Stage**: Post-research, pre-decision; PM 已收到 Quant 初步建议（**A. 维持 V0 baseline**），但 PM 的 recent example 与 19yr backtest 之间存在矛盾，请求独立 review

---

## 1. Review Request

PM hypothesis (2026-05-13)：
> 现在的 IVP > 55 gate 在低波环境下漏掉 SPX 靠近 MA10 的短线 dip-entry。SPX 小跌 → VIX 小升 → IVP 跨越 55 → gate block；SPX 反弹 → IVP 回落 → gate allow → 追高入场。对 30DTE / 持有 ~9 天的 BPS，这种 timing drag 显著耗损 PnL。

2nd Quant 2026-05-13 给出 narrow override 设计：
```
Override IVP > 55 block if:
    VIX < 20
    AND SPX close > MA50
    AND SPX close within [-1.0%, +0.5%] of MA(5 or 10)
    AND SPX 5d return > -2%
```
明确要求：**不可重新放行 Q063 已挡掉的 2026-02-25 坏 trade**。

Q068 实施 Round 1（粗设计 6 变体）+ Round 2（2nd quant narrow override 3 变体）+ recent specific date drill。

**核心 review 问题**：
> 19yr backtest 显示能精准捕捉 PM recent intuition 的变体 (P6B MA5) 是 full sample 最差 (-$16,567)。可否解读为 "regime-conditional alpha"，paper trade 6 个月，还是应直接拒绝？是否 19yr backtest 是判断这个 regime-specific signal 的正确工具？

详细问题见 §7。

---

## 2. Current Production Gate

[strategy/selector.py:1170-1175](../strategy/selector.py)：BPS NORMAL+NEUTRAL+BULLISH path 入场前判断 `IVP_252 ≥ 55` 即 block（路径转 reduce_wait）。
- `BPS_NNB_IVP_UPPER = 55`
- `LOOKBACK_DAYS = 252`（IVP 计算窗口）
- 已经过 Q063 Phase 4 + Phase 5 验证为 19yr empirical local optimum

Q067 后续量化 jitter 特征：
- daily flip 7.37% historical / 11.5% recent
- 61% flips 5 TD 内反转
- IVP [50,65] band 集中在 17-18 VIX (rank-jump artifact)

---

## 3. Method

### Round 1 (粗设计)

[research/q068/q068_ma_timing_variants.py](../research/q068/q068_ma_timing_variants.py) 6 变体：

| 变体 | 设计 |
|---|---|
| V0 baseline | block if IVP ≥ 55 |
| V4a tight 5dMA | + 必须 SPX ≤ 5dMA |
| V4b tight 10dMA | + 必须 SPX ≤ 10dMA |
| V5a relax 10dMA+1% | block 取消 if SPX ≤ MA10 × 1.005 |
| V5b relax 5dMA | block 取消 if SPX ≤ MA5 |
| V5c relax 10dMA | block 取消 if SPX ≤ MA10 |

### Round 2 (2nd quant narrow override)

[research/q068/q068_phase6_narrow_override.py](../research/q068/q068_phase6_narrow_override.py) 3 变体，所有都要求：
```
VIX < 20  AND  SPX > MA50  AND  SPX in [MA × 0.99, MA × 1.005]  AND  SPX_5d_ret > -2%
```

| 变体 | MA 列 |
|---|---|
| P6A_narrow_MA10 | MA10 only |
| P6B_narrow_MA5 | MA5 only |
| P6C_narrow_MA5or10 | MA5 OR MA10 任一满足 |

Engine: 复用 Q063 Phase 5 框架 patch `select_strategy`，仅对 BPS NORMAL+NEUTRAL+BULLISH path 应用 gate。账户 $150k。19yr 2007-2026。

### Recent-date drill

[research/q068/q068_drill_2026_dates.py](../research/q068/q068_drill_2026_dates.py) 检查 2026-05-04 至 2026-05-13 每日数据 + 2026-02-25 hard check。

---

## 4. Findings

### 4.1 Round 1 (粗设计)

| 变体 | bps_n | Δ avg/trade | Δ total | Δ worst | Δ ann/yr | 决策 |
|---|---|---|---|---|---|---|
| V0 baseline | 38 | — | — | — | — | ref |
| V4a tight 5dMA | 19 | **+$879** | -$19,962 | $0 | -$1,989 | ⚠ |
| V4b tight 10dMA | 10 | **+$2,572** | -$28,310 | +$5,806 | -$2,161 | ⚠ |
| V5a relax 10dMA+1% | 47 | -$775 | -$19,056 | -$6,334 | -$1,155 | ❌ |
| V5b relax 5dMA | 45 | -$598 | -$13,403 | -$6,334 | -$863 | ❌ |
| **V5c relax 10dMA** | **43** | **+$41** | **+$11,411** | **$0** | **+$552** | ✅ |

观察：
- V4 tightening 提升 per-trade alpha 显著（PM 时机假设在 per-trade 层成立），但 trade count 减半 → 总 alpha 负
- V5c (exact MA10 bypass, **无 buffer**, **无 guardrails**) 是唯一干净 +alpha 变体
- V5a/V5b 加 buffer 或换 MA5 反而 re-admit worst trade -$15,713

### 4.2 Round 2 (narrow override per 2nd quant)

| 变体 | Full bps_n | Full total | Full worst | OOS total | Recent 2y total |
|---|---|---|---|---|---|
| V0 baseline | 38 | $73,327 | -$9,379 | $46,636 | $23,648 |
| P6A_MA10 | 44 (+6) | **$76,050 (+$2,723)** | -$15,713 (worse) | $46,473 (-$163) | $34,047 (+$10,399) |
| P6B_MA5 | 47 (+9) | $56,760 (-$16,567) | -$15,119 (worse) | $43,518 (-$3,118) | $33,556 (+$9,908) |
| P6C_MA5or10 | 48 (+10) | $62,391 (-$10,936) | -$15,119 (worse) | $49,149 (+$2,513) | $33,556 (+$9,908) |

### 4.3 Go 条件矩阵 (per 2nd Quant 2026-05-13 design)

| Go 条件 | P6A MA10 | P6B MA5 | P6C MA5/10 |
|---|---|---|---|
| Full sample PnL > 0 | ✅ +$2,723 | ❌ -$16,567 | ❌ -$10,936 |
| OOS 2018-2026 > 0 | ❌ -$163 | ❌ -$3,118 | ✅ +$2,513 |
| Recent 2024-2026 > 0 | ✅ +$10,399 | ✅ +$9,908 | ✅ +$9,908 |
| Worst trade 不显著差 | ❌ -$6,334 | ❌ -$5,740 | ❌ -$5,740 |
| **2026-02-25 blocked** | ✅ | ✅ | ✅ |
| **5 条全 PASS?** | **No** | **No** | **No** |

---

## 5. Recent-Date Drill — 重要修正 (corrected)

Quant 起初 drill 错日期为 2025（误读 PM message）。PM 澄清后正确日期为 **2026**：

| Date | SPX | VIX | IVP | Baseline | MA5_dip | MA10_dip | P6A | P6B | P6C |
|---|---|---|---|---|---|---|---|---|---|
| **2026-05-04** | **7201** | 18.3 | **62.3** | **BLK** | **Y** | N | — | **Y** | **Y** |
| 2026-05-05 | 7259 | 17.4 | 50.8 | OK | N | N | — | — | — |
| 2026-05-06 | 7365 | 17.4 | 51.6 | OK | N | N | — | — | — |
| **2026-05-07** | 7337 | 17.1 | **45.6** | **OK (allow!)** | N | N | — | — | — |
| 2026-05-08 | 7399 | 17.2 | 47.6 | OK | N | N | — | — | — |
| 2026-05-11 | 7413 | 18.4 | 65.1 | BLK | N | N | — | — | — |
| **2026-05-12** | **7401** | 18.0 | **60.3** | **BLK** | **Y** | N | — | **Y** | **Y** |
| 2026-05-13 (today) | 7444 | 17.9 | 59.1 | BLK | N | N | — | — | — |

| 2026-02-25 (Q063 known bad trade) | 6946 | 17.9 | 57.1 | BLK | N | N | — | — | — |

### 关键观察

1. **2026-05-07 实际未被 baseline block** (IVP=45.6 < 55)。**PM 此处 example 不成立**——这天 strategy 可以入场，gate 没拦。或许 PM 误记日期
2. **2026-05-04 是真正"被挡的 dip"**：IVP=62.3 → BLK；SPX 7201 vs MA5 7183 (+0.25%) → **P6B/P6C 救**
3. **2026-05-12 也确实被挡**：IVP=60.3 → BLK；SPX 7401 vs MA5 7383 (+0.24%) → **P6B/P6C 救**
4. **2026-02-25 hard check** ✅ PASS：SPX 6946 vs MA10 6878 (+0.99%) 超出 +0.5% 上界 → 所有 override 不触发

### Critical Tension

**P6B/P6C 能精准捕捉 PM 的 recent intuition** (2026-05-04 + 2026-05-12)，但 **P6B 在 19yr full sample 最差 (-$16,567)，P6C 也 -$10,936**。

唯一 full sample PASS 的 P6A (MA10) **不能 capture PM 的 examples**（5/4 SPX 高于 MA10 +0.62%，5/12 高于 MA10 +1.45% 均超 +0.5% 上界）。

**这是 Q068 的核心 dilemma**：
- 能匹配 PM 直觉的设计 → 19yr fail
- 19yr 接近 PASS 的设计 → 不能匹配 PM 直觉

---

## 6. Three Interpretive Paths

| Path | 含义 | 操作 |
|---|---|---|
| **A. PM 直觉是 noise** | 2026-05-04/12 是 random 好运气；19yr backtest 是 ground truth | 维持 V0，关闭 Q068 |
| **B. PM 直觉对，但仅在当前低波 regime 有效** | MA5 信号是 regime-conditional alpha；历史多 regime 平均掩盖了 regime-specific signal | Paper trade P6C 6 个月观察 |
| **C. 当前低波 regime 是"new normal"** | 整个 IVP gate 在 VIX clustering 14-18 时代需要重新校准 | 重新设计 gate，深度研究 (高工程量) |

**Quant 当前 preliminary 推荐**：A（维持 V0）；但承认 B 是合理 alternative，C 不可主动启动。

---

## 7. Specific Review Questions

请 reviewer 在以下问题上发表独立意见：

### Q7.1 — 19yr backtest 是否是判断 regime-conditional signal 的正确工具？

如果 MA5 override 在低波年份 (1992-96 / 2013-18 / 2024-26) work，在 bear regime (2008 / 2020 / 2022) 不 work，**19yr 平均** 给出的 fail verdict 是否过度惩罚了"针对低波 regime 的工具"？换言之：是否应该按 regime conditional 评估？

如果应该 regime-conditional：怎么定义 regime？VIX < 20 长期 stationary？或 IVP cluster density？这本身是新研究。

### Q7.2 — P6B/P6C 19yr fail 是否 acceptable risk

P6C (MA5 OR 10) 是 Go 条件矩阵最接近全 PASS 的：
- Full sample -$10,936
- OOS +$2,513
- Recent 2y +$9,908
- Worst trade -$5,740 worse

是否可以接受 full sample -$10,936 over 19 年（约 -$575/yr）换 recent 2y +$9,908 / 2yr (+$4,954/yr) 净收益 ~$4,400/yr？这是 ~3% Ann ROE swing on $150k 账户。

Reviewer 视角：full sample -$10,936 是否 reasonable insurance cost？还是 worst trade -$5,740 恶化已经超出 risk tolerance？

### Q7.3 — Worst trade 恶化的具体溯源

所有 override 变体都让 worst trade 从 -$9,379 恶化到 -$15,119 ~ -$15,713。**未单独 drill 具体哪一笔 trade**。

Reviewer 建议：
- 是否要求 Quant 先溯源该笔 trade 入场日期 + reasons before 任何 production change?
- 如果该笔 trade 是 2014/2015 一次性事件 → 可能 acceptable
- 如果是 systematic pattern → 应否决

### Q7.4 — Paper trading 是否合适的 next step

Path B（paper trade P6C 6 个月）是 light-weight 验证 regime-conditional 假设的方式。Reviewer 是否同意：
- 这是 reasonable risk-management step（不动 production，但 systematic 验证）？
- 还是过度 commit 资源 to 一个 19yr fail 的设计？
- Paper trading 6 个月 N 太小（预期 ~5-10 trades），不足以下 statistical conclusion？

### Q7.5 — Q068 与 Q063 / Q067 的关系

Q063 Phase 5 否决了 multi-factor relax；Q067 Phase 2 证明 hysteresis 也 fail。Q068 narrow override 是第三轮尝试改进 gate。

**Reviewer 视角**：
- 三轮研究一致显示 "tested space 内无 strict-dominance 变体" 是否构成 strong evidence "hard 55 gate is local optimum"？
- 还是说 tested space 太狭窄，应当 explore 更远（如非 threshold-based signal）？
- 当前 PM 应该接受 hard 55 是 final 答案 (在当前研究框架下)？

### Q7.6 — Final recommendation

Reviewer 推荐：
- **A. 接受 Q068 verdict，维持 V0**
- **B. Paper trade P6C 6 个月 → regime-conditional 验证**
- **C. 要求 worst-trade 溯源后再决定**
- **D. 启动 Q069 regime-conditional research**
- **E. 其他**

---

## 8. Caveats / Quant 自暴露的弱点

1. **Quant 起初 drill 错 2025 dates**，被 PM 修正为 2026。可能还有其他认知误差未被发现
2. **Worst trade 恶化未溯源**：知道 -$9,379 → -$15,713 但未识别具体 trade
3. **engine 内其他 filter** 影响 override 候选日转化率（440 候选 → +6 trades）；未 drill 具体哪些 override 候选被 engine 其他 logic 否决
4. **PM hypothesis 的 specific evidence 部分不成立**（5/7 baseline 已允许）；但 generic hypothesis（低波 timing drag）仍可能 valid
5. **19yr 样本对 regime-conditional signal 的统计效力有限**
6. **Q068 没在 Round 2 中重测 V5c**（Round 1 唯一干净 +alpha 变体，但缺 guardrails）。V5c 在 2026-05-04 / 5/12 都不触发（SPX > MA10），所以也不能救 PM 例子。但 Round 1 数据下 +$11k 是真的

---

## 9. Outputs / 可验证文件

- [research/q068/q068_memo_2026-05-13.md](../research/q068/q068_memo_2026-05-13.md) — 完整 memo
- [research/q068/q068_ma_timing_variants.py](../research/q068/q068_ma_timing_variants.py) — Round 1
- [research/q068/q068_ma_timing_results.csv](../research/q068/q068_ma_timing_results.csv)
- [research/q068/q068_phase6_narrow_override.py](../research/q068/q068_phase6_narrow_override.py) — Round 2 (2nd quant design)
- [research/q068/q068_phase6_results.csv](../research/q068/q068_phase6_results.csv)
- [research/q068/q068_drill_2026_dates.py](../research/q068/q068_drill_2026_dates.py) — Corrected drill
- [research/q067/q067_memo_2026-05-13.md](../research/q067/q067_memo_2026-05-13.md) — Q067 jitter 量化
- [research/q067/q067_phase2_memo_2026-05-13.md](../research/q067/q067_phase2_memo_2026-05-13.md) — Q067 Phase 2 hysteresis FAIL
- [task/q063_phase4_closure_memo_2026-05-11.md](q063_phase4_closure_memo_2026-05-11.md) — Q063 closure + 2026-02-25 来源
- [strategy/selector.py:175](../strategy/selector.py#L175) `BPS_NNB_IVP_UPPER = 55`
- RESEARCH_LOG R-20260513-01 / R-20260513-02 / R-20260513-03

---

## 10. 期望 review 形式

参照 [q066_cofiring_2nd_quant_review_packet_2026-05-12_Review.md](q066_cofiring_2nd_quant_review_packet_2026-05-12_Review.md) 体例：

1. **Top-line verdict**: PASS / REVISE / FAIL / WAIT-FOR-MORE-EVIDENCE
2. **逐 Q7.1 ~ Q7.6 回复**
3. **若推荐 Paper trade**：明确 success criteria + 终止条件
4. **若推荐 hard reject**：说明哪部分 evidence 是决定性的

回复文件命名：`q068_ma_timing_2nd_quant_review_packet_2026-05-13_Review.md`，放本 task/ 目录。

---

---

## 11. Supplement — Phase 7 Regime Stops (added 2026-05-13 after PM follow-up)

PM 追问：上面 Q068 是否有止损？若加 "VIX continues rising" 或 "SPX < MA10" 止损，结果如何？

### Method

Added research-mode flags to `StrategyParams`（默认 disabled，不影响生产）：

```python
regime_stop_vix_rise:        float = 0.0    # exit if vix > entry_vix × (1 + N)
regime_stop_below_ma10:      bool  = False  # exit if SPX_close < SPX_10dMA
regime_stop_min_hold_days:   int   = 1
regime_stop_bps_only:        bool  = True   # only apply to BPS strategies
```

Engine.py exit loop 增加 2 行检查（在 P&L stops 之后、roll_21dte 之前）。

Test matrix: 4 entry variants × 4 stop configs = 16 cells:
- **Entry**: V0_baseline / P6A_MA10 / P6B_MA5 / P6C_MA5or10
- **Stop**: S0 no_stop / S1 VIX+20% / S2 SPX<MA10 / S3 both

### Phase 7 Findings

| Entry × Stop | Full total | Full worst | Δ tot vs V0×S0 | Δ worst | Recent 2y total | Decision |
|---|---|---|---|---|---|---|
| **V0 × S0 (production)** | **$73,327** | **-$9,379** | ref | ref | $23,648 | ✅ Current |
| V0 × S1 | $50,323 | -$6,785 | -$23k | +$2.6k | $20,109 | ⚠ stops 损害 alpha |
| V0 × S2 | $33,262 | -$4,519 | -$40k | +$4.9k | $14,713 | ❌ S2 太激进 |
| V0 × S3 | $33,262 | -$4,519 | -$40k | +$4.9k | $14,713 | ❌ S2 主导 |
| P6A × S0 | $76,050 | -$15,713 | +$2.7k | -$6.3k | $34,047 | ⚠ worst 恶化 |
| **P6A × S1** | **$52,739** | **-$8,944** | -$20.6k | **+$0.4k ≈ baseline** | **$32,215 (+$8.5k)** | ⭐ 最优 candidate |
| P6A × S2 | $31,054 | -$4,519 | -$42k | +$4.9k | $20,198 | ❌ |
| P6B × S1 | $43,811 | -$8,944 | -$29.5k | +$0.4k | $30,721 | ⚠ |
| P6C × S1 | $49,442 | -$8,944 | -$23.9k | +$0.4k | $30,721 | ⚠ |

(其他配置详 [research/q068/q068_phase7_regime_stops_results.csv](../research/q068/q068_phase7_regime_stops_results.csv))

### Key Mechanism: Exit Reason Distribution

| Config | roll_21dte (natural) | regime_below_ma10 | regime_vix_rise | stop_loss (P&L) |
|---|---|---|---|---|
| V0 × S0 | 36/38 | 0 | 0 | 0 |
| V0 × S2 | 12/42 | **28** | 0 | 0 |
| V0 × S1 | 25/38 | 0 | **11** | 0 |
| P6A × S1 | 27/44 | 0 | **14** | 0 |
| P6A × S2 | 12/53 | **38** | 0 | 0 |

**S2 (SPX<MA10) 触发太频繁**（28-41 次）→ cut 73% 的 trade 在自然成熟前 → 损害 winners
**S1 (VIX+20%) 更选择性**（11-16 次）→ 真正针对 distress trade

### Phase 7 Verdict

- ❌ **加 stops 到 V0 baseline**：-$23k 到 -$40k full sample，stops 不是 free insurance
- ❌ **S2 (SPX<MA10) 对所有 entry 都太激进**：fires 30+ 次，cut winners
- ⚠ **P6A × S1 是唯一"有意义"组合**：worst trade 恢复 baseline (-$8,944 vs -$9,379, Δ+$435)，recent 2y +$8.5k，但 full sample -$1,084/yr (-0.7% Ann ROE) 保险成本
- 没有 strictly dominant 组合

### PM 直觉部分验证

- ✅ Stops **确实救了** P6 override 系列的 worst trade（-$15,713 → -$8,944 ≈ baseline）
- ❌ Stops **不是免费**：对 baseline V0，每救 $1 worst trade 损失 $8-9 winner alpha
- ✅ 对 P6 override，每救 $1 worst trade 损失 $3-4 winner alpha（仍负但温和）

### Updated Path Analysis

| Path | 含义 | Phase 7 数据更新后视角 |
|---|---|---|
| **A. 维持 V0** | 不动 production | ✅ 仍是最稳健 — 任何 stops 加上去都损害 alpha |
| **B. P6A × S1 paper trade** | Override + VIX-rise stop 组合，付 $1k/yr 保险 | 🟡 比 Phase 6 单独 P6 更有 defensible argument（worst 不恶化）|
| **C. 接受 worst trade 恶化 (Phase 6 P6A 无 stops)** | $2,723 full sample + -$6,334 worst | ❌ 更不划算 |

### Updated Recommendation

| 排序 | 选项 | 推荐度 |
|---|---|---|
| 1 | **A. 维持 V0 baseline，关闭 Q068** | ✅ 最稳健，three-phase research 一致结论 |
| 2 | **B. P6A × S1 paper trade 6 个月** | 🟡 比 Phase 6 单独 P6 更有 defensible argument（worst preserve），但 full sample insurance cost $1k/yr |
| 3 | C. Phase 6 P6A 单独（无 stops）| ❌ worst trade 恶化是 dealbreaker |
| 4 | D. 启动 Q069 regime-conditional 研究 | 🟡 高工程量，不主动启动 |

### Phase 7 加入后给 Reviewer 的额外问题

**Q7.7 (NEW)**: P6A × S1 数据下：
- full sample -$1,084/yr insurance cost
- worst trade preserve (Δ +$435 ≈ 0)
- recent 2y +$4.3k/yr improvement
- 是否值得 paper trade？或还是 alpha 净损失（recent gain 是 noise）？

**Q7.8 (NEW)**: S2 (SPX<MA10) 对所有 entry 都触发 28-41 次 → 是否 stop threshold 设计本身有问题（如改 MA10 × 0.99 / 跌穿 5 天而非单日 / 加 confirmation）？还是 MA10 cross 本身就是 noise signal？

### Phase 7 Outputs

- [research/q068/q068_phase7_regime_stops.py](../research/q068/q068_phase7_regime_stops.py)
- [research/q068/q068_phase7_regime_stops_results.csv](../research/q068/q068_phase7_regime_stops_results.csv)
- Engine modifications: [strategy/selector.py](../strategy/selector.py) `regime_stop_*` fields；[backtest/engine.py](../backtest/engine.py) exit loop 增加 regime stop 检查（默认 disabled）

---

## 附：关键数字回顾（一目了然）

```
Q068 核心矛盾（含 Phase 7 update）：

  Phase 6: 能精准捕捉 PM recent intuition (5/4 + 5/12) 的 → P6B / P6C (MA5)
           在 19yr full sample 表现 → P6B FAIL -$16,567 / P6C -$10,936
  
  Phase 6: 唯一 19yr Full PASS 的 → P6A (MA10)
           能 capture PM examples 的能力 → NO (SPX 离 MA10 太远)
  
  Phase 6 Recent 2y improvement → +$9,908 ~ +$10,399 (all variants)
  Phase 6 Worst trade 恶化 → -$5,740 ~ -$6,334 (all variants)
  Phase 6 2026-02-25 hard check → ✅ ALL PASS

  Phase 7 新增 regime stops:
    V0 + S1/S2: stops alone 损害 alpha -$23k to -$40k
    P6A + S1 (VIX+20% stop): 唯一 "有意义" 组合
      Worst -$8,944 ≈ baseline (Δ +$435) ✅
      Recent 2y +$8.5k ✅
      Full sample -$20.6k (-$1,084/yr insurance) ⚠

  19yr empirical local optimum (Q063+Q067 confirmed) → hard 55 gate, no stops
```
