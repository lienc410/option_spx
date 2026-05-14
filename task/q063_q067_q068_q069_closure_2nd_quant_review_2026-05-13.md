# Q063/Q067/Q068/Q069 Closure Review — 2nd Quant

## Top-line verdict

**APPROVE — accept full closure. Keep `BPS_NNB_IVP_UPPER = 55` and `LOOKBACK_DAYS = 252` unchanged.**

我同意 closure memo 的最终判断：在已经测试过的空间里，hard `IVP > 55` gate 是当前 empirical local optimum。Q063、Q067、Q068、Q069 从不同角度尝试放宽、平滑、确认、加 hysteresis、加 MA timing、加 stops、加 slope-aware 逻辑，结果都没有产生 strict-dominance 变体。因此，现在应该停止围绕这个 gate 的微调研究，把 research effort 转向其它更高 ROI 的策略模块。

---

# 1. 对 Q063 主结论的评价

**PASS.**

Q063 的核心结论很强：PM 认为 `IVP < 55` gate 在低 VIX 环境下 false alarm，但 Phase 1–4 的证据反向支持 gate。尤其是 2024–2026 最近窗口里，被放宽规则重新放进来的 5 笔 entry 累计亏损 `-$13.7k`，说明 gate 不是错过机会，而是在过滤真实负 alpha entries。

最重要的机制解释是对的：

> VIX 绝对值低，不代表 IVP 相对位置低。
> VIX 15–17 + IVP 60–65 可能是 "complacency before mean reversion"，而不是安全卖 premium 的窗口。

这一点应保留在 strategy docs 中，因为它是之后所有关于 IVP/VIX 争论的基准解释。

---

# 2. 对 Q067 jitter / hysteresis 的评价

**PASS.**

Q067 很好地承认了一个真实问题：`IVP=55` 不是经济悬崖，而是 percentile rank 在 low-vol cluster 中的经验阈值。文件中记录的事实很重要：

* historical daily flip rate `7.37%`
* recent daily flip rate `11.5%`
* 61% 的 flips 在 5 个交易日内反转
* 126d / 252d / 504d 窗口之间有约 15% 的 disagreement

这证明 PM 对 jitter 的担心是合理的。

但 Q067 Phase 2 进一步证明，合理担心不等于有可用修复。Hysteresis、多窗口 confirmation、cross-window logic 都没有 strict dominance：有的损失 alpha，有的恶化 worst trade，有的甚至增加 flip rate。这个结果支持 "document limitation, do not change production logic"。

我建议在最终文档里强调这句话：

> **Jitter is real, but tested jitter fixes are worse than the original hard gate.**

这是 Q067 的核心价值。

---

# 3. 对 Q068 MA timing / regime stops 的评价

**PASS.**

Q068 对 PM 的交易直觉做了正确处理：没有直接否定直觉，而是把它拆成可测的 MA-timing override 与 regime stop。结果显示：

* 某些 MA5/MA10 变体能解释 2026-05-04 / 2026-05-12 这类 recent dip intuition；
* 但这些变体在长期样本或 worst-trade 风险上不过关；
* 加 stops 不是 free insurance，V0 + stops 直接损害 alpha；
* P6A × S1 虽能修复 worst trade，但 full-sample 要付出约 `$1k/yr` 的 insurance cost。

我同意 Q068 的 final interpretation：

> PM intuition is valid as a trading observation, but not stable enough for rule-level adoption.

这个 distinction 很重要。不是所有 trading intuition 都应该进入 selector rule。特别是 short-premium gate，一旦例外规则放行更多 trades，tail-risk 代价常常大于近期直觉收益。

---

# 4. 对 Q069 smoothed IVP / slope-aware 的评价

**PASS, with one wording adjustment.**

Q069 是很有价值的一刀，因为它测试了我们讨论过的 "smoothed IVP / regime detection / 非 threshold-based signal" 中最自然的一部分。结果：

* smoothing 类变体失败，因为 lag 会错过 risk ramp-up；
* slope-aware 类变体失败，因为会放行 "elevated but easing" 的 hard-guardrail bad trade；
* 两类失败模式互相冲突，说明软化 hard threshold 不容易同时保留保护力和减少 jitter。

我唯一建议是把这句话略微收紧：

> "This is not something more research effort can solve."

这句话方向上我理解，但措辞略绝对。更合适写成：

> **Within percentile-threshold, smoothing, slope-aware, MA-timing, and simple regime-stop frameworks, additional micro-optimization is unlikely to solve the issue. Future work should require a genuinely different framework, such as probabilistic / Bayesian / cross-asset risk modeling.**

因为文件自己也保留了 non-threshold Bayesian / ML / cross-asset 作为 future independent SPEC，而不是永远不能研究。

---

# 5. 是否应该保留 code 注释更新？

**Yes. Strongly recommend.**

我建议一定要给 `BPS_NNB_IVP_UPPER = 55` 加注释。这个 gate 很容易被未来 PM / developer / reviewer 误解为 "VIX 低时过度保守"。注释应记录三件事：

1. `IVP > 55` 是 empirical low-vol repricing filter，不是经济悬崖；
2. jitter / rank-jump 已被确认；
3. 放宽、hysteresis、MA override、smoothed IVP、slope-aware IVP 都已测试失败。

文件里建议的注释方向是对的，但可以加上 Q068/Q069 的 closure 简写。

建议注释版本：

```python
# BPS_NNB_IVP_UPPER = 55 is an empirical low-vol repricing filter, not a
# precise volatility cliff. Q063 confirmed that relaxing this gate re-admits
# negative-alpha BPS NNB entries, including recent 2024-2026 counterfactual
# losers. Q067 confirmed rank-jump / threshold jitter, but hysteresis and
# multi-window variants failed. Q068 MA-timing overrides and regime stops
# failed robustness / worst-trade tests. Q069 smoothed and slope-aware IVP
# variants also failed. Keep hard IVP_252 >= 55 block unless a future
# non-threshold framework is explicitly approved.
```

---

# 6. 是否应该允许 future Q070 / Bayesian / cross-asset？

**可以，但必须高门槛。**

我同意当前关闭所有 Q063/Q067/Q068/Q069。但我不会写成 "IVP gate 永远不能再研究"。未来如果重启，必须满足以下条件之一：

```text
1. 使用完全不同的信息集：
   credit spreads, rates, breadth, vol surface, VVIX, macro/liquidity variables

2. 使用完全不同的建模形式：
   probabilistic tail-risk score, Bayesian state model, calibrated loss-probability model

3. 有新的 live evidence：
   repeated blocked entries with documented positive counterfactual PnL across enough samples

4. 账户 / strategy routing materially changes:
   BPS NNB capital share becomes much larger, requiring revised risk-return calibration
```

但不应再测试：

```text
- IVP 55 → 60/65
- IVP hysteresis
- MA5/MA10 override
- simple VIX rising/falling confirmation
- smoothed IVP
- IVP slope filter
```

这些已经被充分覆盖。

---

# Final verdict

**APPROVE CLOSURE.**

正式表述：

> Q063, Q067, Q068, and Q069 collectively provide sufficient evidence that the current hard `IVP_252 >= 55` BPS NNB gate should remain unchanged. The gate is noisy and has known percentile-rank jitter, but every tested repair path either re-admits bad trades, worsens worst-trade risk, reduces long-run alpha, or fails hard-guardrail checks. Close all IVP-gate micro-optimization work. Future research should only reopen this area under a genuinely different probabilistic or cross-asset risk framework.

一句话：

> **接受 hard `IVP > 55` 是当前 tested space 的 final answer；不要再围绕这个 gate 做局部修补。**
