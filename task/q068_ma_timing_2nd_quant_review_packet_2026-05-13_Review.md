# Q068 MA-Timing Override + Phase 7 Stops — 2nd Quant Review

## Top-line verdict

**PASS / KEEP V0 — 维持 current hard `IVP > 55` gate，不加 MA override，不加 regime stop，不进入 formal paper trade。**

Phase 7 补充测试后，结论反而更清楚：**当前 V0 baseline 仍是最稳健方案。** MA timing override 能解释部分 recent intuition，但不能形成可生产的稳定规则；regime stops 能修复部分 worst-trade 恶化，但代价是系统性损失 full-sample alpha。综合 Q063 / Q067 / Q068，`IVP > 55` hard gate 仍是当前 tested space 内的 empirical local optimum。

---

# Q7.1 — 19yr backtest 是否适合判断 regime-conditional signal？

**Verdict: Yes，仍然应作为 primary gate。**

如果一个信号要进入 production entry gate，它必须跨 regime 不产生明显伤害。Q068 的 MA override 如果只在 2024–2026 recent low-vol regime 有效，但在 19 年样本上恶化 total PnL 或 worst trade，那它还不能进入规则层。

这不是说 regime-conditional alpha 不存在，而是：

> **Q068 还没有定义出一个足够稳定、可回测、可治理的 regime 条件。**

现在的说法仍停留在：

```text
current low-vol clustered VIX regime may be different
```

这个不够。要成立，至少需要先定义：

```text
什么是 low-vol clustered regime？
如何在当时实时识别？
它是否在历史低波阶段也有效？
```

否则用 recent 2y 强行覆盖 full-sample 失败，容易变成 sample chasing。

---

# Q7.2 — P6B/P6C 19yr fail 是否 acceptable risk？

**Verdict: No.**

P6B / P6C 的问题不是只少赚一点，而是：

* full sample total PnL 下降；
* worst trade 从约 `-$9.4k` 恶化到约 `-$15k`；
* 能抓 PM recent examples 的 MA5 版本，长期表现最差；
* 唯一 full-sample 较好的 P6A MA10，又不能捕捉 PM 的 5/4 和 5/12 examples。

所以这个 tradeoff 不合格。

不能为了 recent 2y `+$9.9k`，接受一个在长期样本里明显放大 worst trade 的 entry override。尤其这个策略本身就是 short premium，entry gate 的第一职责是避免重新放行 bad trades，而不是最大化每一个小 dip 的参与率。

---

# Q7.3 — 是否需要 worst-trade 溯源后再决定？

**Verdict: 不需要作为决策 blocker。**

Worst-trade 溯源有学习价值，但不是当前决策必须项。当前 reject 已经有足够证据：

1. P6B / P6C full sample fail；
2. P6A 不满足 PM intended use-case；
3. all Phase 6 variants worsen worst trade；
4. Phase 7 stops 修复 worst trade 的同时损害 full-sample alpha；
5. 2026-05-07 这个 PM example 实际上 baseline 已允许。

如果要补，建议作为 archival appendix：

```text
Identify the P6 worst-trade date and classify whether it was a one-off or systematic failure.
```

但不应因此延迟关闭 Q068。

---

# Q7.4 — 是否适合 paper trade P6C 6 个月？

**Verdict: 不建议 formal paper trade。**

原因有三个。

第一，6 个月样本太小。预期只有几笔到十来笔，不能验证 regime-conditional alpha。

第二，P6C 是 full-sample fail，且 worst trade 更差。把它放进 formal paper trade，会给一个已失败规则过多治理权重。

第三，paper trade 容易产生心理锚定。如果未来 2–3 笔碰巧赚钱，会诱导提前 promotion；如果几笔亏损，又不能统计性否定。

更好的替代是：

> **shadow tag only，不作为 paper strategy。**

例如：

```text
If V0 blocks but P6C would allow, log:
blocked_by_IVP55_but_MA_dip_override_candidate = True
```

只记录，不推荐交易，不进 scoreboard，不设 6 个月 promotion 路径。

---

# Q7.5 — Q063 / Q067 / Q068 的关系

**Verdict: Strong evidence that hard 55 gate is local optimum within tested space.**

现在三轮证据是连续的：

* Q063：放宽 IVP gate / multi-factor relax 被 reject；
* Q067：hysteresis 不能修复 threshold jitter；
* Q068：MA dip override 能解释一部分 recent intuition，但长期和 tail 维度不合格；
* Phase 7：加 stops 不是 free insurance，V0 加 stop 直接损害 alpha。

所以我会把结论写成：

> **Within the tested IVP-threshold / hysteresis / MA-timing / regime-stop family, current hard `IVP > 55` gate remains the best production rule.**

这不是说未来永远不能改。
但未来要重开，应该是一个真正不同的研究假设，而不是继续在 hard gate 周边加小修小补。

---

# Q7.6 — Final recommendation

**推荐 A：接受 Q068 verdict，维持 V0。**

具体：

```text
Keep:
- BPS_NNB_IVP_UPPER = 55

Do not add:
- MA5 override
- MA10 override
- MA5/10 combined override
- VIX+20% regime stop
- SPX<MA10 stop

Do not start:
- formal P6C paper trade
- Q069 regime-conditional research
```

可以保留：

```text
optional shadow logging tag for blocked-but-MA-dip cases
```

但这是 monitoring，不是 candidate strategy。

---

# Q7.7 — P6A × S1 是否值得 paper trade？

**Verdict: 不值得。**

P6A × S1 是 Phase 7 里"最有意义"的组合，但仍不够格。

它的优点：

* worst trade 恢复到接近 baseline；
* recent 2y 明显更好；
* VIX+20% stop 比 SPX<MA10 stop 更有选择性。

但问题更关键：

```text
V0 × S0 total: $73,327
P6A × S1 total: $52,739
difference: -$20.6k
```

这不是小成本。相当于 full sample 每年约 `-$1.1k` 的 insurance cost，而且 P6A 还不能捕捉 PM 最关心的 MA5 recent examples。它解决了 Phase 6 的 worst-trade 问题，但没有解决"长期 alpha 被侵蚀"的问题。

所以它更像是：

> **一个 recent-regime defensive variant，不是 production candidate。**

不建议 paper trade。最多 shadow log。

---

# Q7.8 — S2 `SPX < MA10` stop 是否值得改良？

**Verdict: No, not now.**

S2 的行为已经说明它太 noisy：

* 对 V0 触发 28 次；
* 对 P6A 触发 38 次；
* 大量 cut winners；
* full-sample alpha 损失很大。

当然可以设计更复杂版本，比如：

```text
SPX < MA10 × 0.99
or
SPX below MA10 for 3 consecutive days
or
MA10 break + VIX rising
```

但这会开启新的 micro-optimization tree。当前 Q068 已经证明，MA timing + stops 这个方向没有 clean edge。继续调 stop threshold，很容易变成 overfit。

所以不建议启动。

---

# 对 Phase 7 的独立解读

Phase 7 的最大价值是证明：

> **Stops are not free.**

尤其是：

* V0 加 S1/S2 都显著损害 alpha；
* SPX<MA10 stop 过度触发；
* VIX+20% stop 相对更合理，但仍然不是正期望保险；
* P6A × S1 只是把 worst trade 拉回 baseline，同时牺牲大量 full-sample PnL。

所以 PM 的直觉 "加止损能解决 override 的 tail 问题" 被部分验证，但也被定价了：

> 可以救 worst trade，但要付出太多 winner alpha。

---

# Final decision

## **Close Q068 under Path A**

正式表述：

> Q068 tested the PM hypothesis that the hard `IVP > 55` gate misses low-vol MA dip entries. The hypothesis is directionally plausible and the MA5 variants captured the 2026-05-04 / 2026-05-12 examples. However, those same variants fail full-sample robustness and worsen tail losses. Phase 7 confirms that regime stops are not free insurance: they can repair worst-trade deterioration but materially reduce long-run alpha. Therefore, no production change or formal paper trade is recommended. Keep V0 hard `IVP > 55` unchanged and close Q068.

---

# Suggested RESEARCH_LOG entry

```md
R-20260513 — Q068 MA-Timing Override Final Review

Decision:
Keep V0 hard IVP > 55 gate unchanged. Close Q068.

Evidence:
- MA5 / MA5or10 overrides capture recent 2026-05-04 and 2026-05-12 dip examples, but fail full-sample robustness.
- P6B full sample: -$16.6k vs baseline.
- P6C full sample: -$10.9k vs baseline.
- All Phase 6 overrides worsen worst trade from about -$9.4k to about -$15k.
- Phase 7 VIX+20% stop can repair worst trade for P6A but reduces full-sample PnL by about $20.6k.
- SPX<MA10 stop fires too often and cuts winners.

Interpretation:
The PM intuition is valid as a trading observation but not stable enough for rule-level adoption. Within the tested IVP / MA / hysteresis / regime-stop family, hard IVP > 55 remains the empirical local optimum.

Action:
No production change. No formal paper trade. Optional shadow tag only for future monitoring:
blocked_by_IVP55_but_MA_dip_override_candidate.
```
