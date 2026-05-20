# Q074.1 — IVP > 55 Gate Forensic

**Date**: 2026-05-18
**Author**: Quant Researcher
**Trigger**: PM observation that IVP > 55 block concentrates in low-VIX slow-bull years (2007/2018/2024/2026)
**Status**: Sub-investigation (NOT a P0/P5 cycle). Findings inform whether SPEC-105 gate refinement is warranted.

---

## 0. TL;DR

**PM intuition was half right, half reversed**:

| Year | Block% | Blocked-day actual fwd 10d stress | Verdict |
|---|---|---|---|
| 2007 | 72.7% | 25.0% (passed: 23.8% → +1.2pp lift) | **真 FP**: 几乎纯过度保守 |
| 2017 | 12.0% | 0% (passed: 0% → 0pp lift) | **真 FP**: 完美 false positive year |
| 2018 | 66.7% | 17.4% (passed: 14.0% → +3.5pp lift) | **真 FP**: block 很多但用处少 |
| **2024** | **39.6%** | **60.7% (passed: 13.3% → +47.4pp lift)** | **正确预测**: 不是 false positive |
| **2025** | **30.1%** | **49.1% (passed: 10.6% → +38.5pp lift)** | **正确预测** |
| **2026** | **57.6%** | **30.3% (passed: 0% → +30.3pp lift)** | **正确预测** |

→ 2007/2017/2018 是真 false positive 大户；2024/2025/2026 看起来 block 多，但**那些 block 实实在在地预测了 forward stress**。PM "近期 block 一半交易日"的感受真实，但**block 之后确实出 stress**——不是过度保守。

**全样本上 IVP > 55 仍是高质量信号**：
- Blocked 日 P(stress 10d) = 35.2% vs Passed 日 17.7% → +17.5pp lift
- 这个信号本身是健康的，问题集中在 2007/2017/2018 三年

**最优 candidate refinement**：Gate B = `IVP_252 < 55 OR VIX < 16`
- 全样本 pass rate 79.0% → 90.4% (+11.4pp)
- 新增的 416 天 P(stress 10d) = 20.7% (vs 当前 baseline 17.7% → +3pp marginal risk)
- 2007: 27% → 74% pass | 2018: 33% → 94% pass (恢复 FP 年份)
- 2024: 60% → 76% | 2025: 70% → 73% (微改善——这两年 VIX 不够低)
- 2026: 42% → 42% (无改善——2026 VIX 平均 17.9，escape valve 不触发)

**IVP_63（短窗口）反而 worse**：pass rate 72.6%（更严格），因为短窗口在 VIX 横盘时和 IVP_252 行为接近，但在 VIX 上升时更慢响应。

---

## 1. Per-Year Block Distribution

完整 26y 样本 (n=3643 normal days，IVP_252 + IVP_63 都可用)：

```
Total IVP_252 >= 55: 764 days (21.0% of normal days)
                              = 10.1% of total trading days

按年度展开：
  2007: 72.7%  ←  PM-flagged 高 block
  2018: 66.7%  ←  PM-flagged
  2026: 57.6%  ←  PM-flagged
  2015: 48.6%  ←
  2024: 39.6%  ←  PM-flagged
  2014: 37.4%
  2020: 34.9%
  2025: 30.1%
  2013: 19.7%
  2006: 18.4%
  2017: 12.0%
  2019: 13.7%
  ... 其他年份 < 10%

2008/2009/2010/2023: 0% (要么本身 stress，要么 VIX 高位下行 IVP 自然低)
```

---

## 2. The Critical Discovery — Block IS predictive in 2024-2026

| Year | Blocked days | Blocked P(stress 10d) | Passed P(stress 10d) | Lift |
|---|---|---|---|---|
| 2007 | 112 | **25.0%** | 23.8% | +1.2pp ← FP 年 |
| 2017 | 30 | **0.0%** | 0.0% | 0pp ← 完美 FP 年 |
| 2018 | 86 | **17.4%** | 14.0% | +3.5pp ← FP 年 |
| 2024 | 84 | **60.7%** | 13.3% | **+47.4pp** ← 真信号 |
| 2025 | 53 | **49.1%** | 10.6% | **+38.5pp** ← 真信号 |
| 2026 | 38 | **30.3%** | 0.0% | **+30.3pp** ← 真信号 |

**为什么 2024-26 信号真实，2007/2017/2018 是 FP？**

假设（待 P2 ROE 复盘确认）：
- **2024-26**: 慢牛 + 后期估值高 + 真有 mini-stress 出现（每个季度几次 -4% pullback）。IVP > 55 实际抓住 pre-pullback 时刻。
- **2007**: 长达半年的"前 VIX 静止期" → IVP 持续高但 stress 在 8 月才爆发，前端 block 半年大部分是无效保护。
- **2017**: 历史最低 VIX 年，IVP > 55 触发但市场根本没 stress。
- **2018**: 1 月底 Volpocalypse 前两个月 IVP 慢爬，但触发后市场反而横盘到 2 月初才崩。Forward 10d 窗口没抓住。

---

## 3. Alternative Gate Comparison

5 个候选 gate 在全样本表现：

| Gate | Pass rate | Passed P(stress 10d) | Added vs current marginal stress |
|---|---|---|---|
| **A: IVP_252 < 55 (current)** | 79.0% | 17.7% | — |
| **B: IVP_252 < 55 OR VIX < 16** | 90.4% | 18.1% | **+3.0pp on 416 added days** |
| C: IVP_252 < 55 OR VIX < 18 | 95.3% | 19.2% | +9.0pp on 593 added days |
| D: IVP_63 < 55 (shorter) | **72.6%** ← 反而更严 | 16.4% | — |
| E: IVP_63 < 55 OR VIX < 16 | 88.3% | 17.0% | +6.2pp on 507 added days |

**判断**：
- **Gate B** 是最干净的 refinement——pass rate +11.4pp，新增天的 stress 风险只 +3pp，几乎免费的"释放低 VIX 真静"
- Gate C 走太远——+9pp 边际 stress 风险，破坏 booster 保护性
- Gate D（IVP_63）**反而更严**，因为短窗口在 VIX 横盘期对自己的最近表现更敏感，不解决问题
- Gate E 比 B 稍差

**对慢牛年的恢复效果**：

| Year | Current pass | Gate B pass | 改善 |
|---|---|---|---|
| 2007 | 27.3% | 74.0% | **+46.7pp** |
| 2017 | 88.0% | 99.6% | +11.6pp |
| 2018 | 33.3% | 93.8% | **+60.5pp** |
| 2024 | 60.4% | 76.4% | +16.0pp |
| 2025 | 69.9% | 72.7% | +2.8pp |
| 2026 | 42.4% | 42.4% | **0pp** (VIX 2026 平均 17.9，escape valve 几乎不触发) |

→ Gate B 在 **PM 真正觉得过度保守的 2007/2018** 上修正最显著。2026 不动是好事——2026 的 block 是 real signal（30% 真出 stress）。

---

## 4. Caveats

1. **2025/2026 样本极少**（53 + 38 天），blocked-stress lift +38/+30pp 有统计噪音。即使 noise σ 翻倍仍显著。
2. 本 forensic 只看 P(stress 10d/20d)，**没看 ROE 影响**。Gate B 让 booster 多激活 11pp of days × ~$3k/day avg → 估算 +$10-15k/年 额外 ROE（vs 当前 booster 总 +$22k/年）。需要 P2-style sweep 才能确认。
3. **2007 是 1 年的极端 FP 年**，单独贡献 ~112 blocked days 中 ~80 是 FP——Gate B 改善的主要来源。如果剔除 2007，Gate B 的好处缩水一半。
4. 没考虑 Gate B 和 booster 其他 6 个条件的 AND 组合效应。可能其他条件已经 filter 掉相当多 VIX<16 IVP>55 的天。

---

## 5. Recommendation

**不立即修改 SPEC-105**。SPEC-105 已 Stage 1 shadow 中，先按当前 B4 定义跑实盘 evidence。

**但记录 Gate B 为后续优化候选**。如果 Stage 1-2 paper/shadow 期看到：
- Booster 激活率显著低于回测预期（< 25% of normal days）
- 在 VIX < 16 的极低波动期 booster 频繁被 IVP block

→ 触发 Q074.2 follow-up：用 Gate B 跑 P2 ROE sweep（不重新 P0），如果 +0.05-0.10pp 净 ROE 且 V2/V3 仍 pass，可作为 SPEC-105 v2 修订。

**也不需要 G2 2nd Quant review**。这是 SPEC-105 内的 micro-refinement，不影响 architecture。等真有 live evidence 触发再走流程。

---

## 6. 给 PM 的一句话

> 你的直觉"block 集中在低 VIX 拉锯年"是对的。但**只有 2007/2017/2018 是真的 false positive**——2024/2025/2026 看起来 block 多，但那些 block 之后**实实在在地出 stress**（10d 内 30-60%），booster 没保护错。如果担心 2007/2018 模式重演，Gate B（加 VIX<16 escape valve）能恢复 47-60pp pass rate，边际 stress 风险只 +3pp。但**不必现在改 SPEC-105**——Stage 1 shadow 还没跑完，先看 live evidence。

---

## 7. Files

- `q074_1_ivp_gate_forensic.py` — script
- `q074_1_ivp_per_year.csv` — yearly breakdown table
- `q074_1_blocked_stress_breakdown.csv` — slow-bull vs other subgroup
- `q074_1_alt_gates_comparison.csv` — 5 gates full-sample stress
- `q074_1_slow_bull_gate_pass.csv` — pass rate by year for each gate
- `q074_1_added_pass_days_stress.csv` — marginal stress on newly-passed days
