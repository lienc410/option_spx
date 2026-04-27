# Q036 Phase 5 — Overlay-F Confirmation

- 日期：2026-04-26
- Author: Quant Researcher
- 上游：`doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- Prototype: `backtest/prototype/q036_phase5_overlay_f_confirmation.py`

---

## TL;DR

`Overlay-F_sglt2` 经过一轮更窄的 confirmation 之后，结论是：

1. **不是纯粹由单一年份或单一 trigger case 支撑的假阳性。**
2. uplift 在年度上是“稀疏但分散”的，不是只集中在 `2026-03` 这类个案。
3. overlay fires 全部发生在 `HIGH_VOL`，且主要集中在 `VIX 25-30` 区间。
4. 触发时的 pre-existing short-gamma 结构很干净：只发生在 `0` 或 `1`，没有任何 `>=2`。
5. **recent-era (`2018+`) 仍为正，但 uplift 比全样本更薄。**

因此：

> `Overlay-F` 仍是当前 `Q036` 最值得保留的 lead candidate，但证据强度更像“可继续验证的窄候选”，还不是可以自然推进到 DRAFT overlay spec 的级别。

---

## 1. Top-Line Confirmation

| Metric | Baseline | Overlay-F | Delta |
|---|---:|---:|---:|
| Total PnL | `+$403,850` | `+$412,855` | `+$9,005` |
| Annualized ROE | `8.675%` | `8.748%` | `+0.074pp` |
| MaxDD | `-10,323` | `-9,749` | 改善 |
| CVaR 5% | `-4,309` | `-4,382` | 恶化 `-74` |

这与 Phase 4 的结论一致：

- 回报是正增量
- drawdown 没有恶化
- 但 tail CVaR 仍然略差

---

## 2. Yearly Attribution

### 逐年 delta

| Year | Delta |
|---|---:|
| 2000 | `+700` |
| 2001 | `0` |
| 2002 | `-828` |
| 2003 | `0` |
| 2004 | `0` |
| 2005 | `0` |
| 2006 | `0` |
| 2007 | `+1,172` |
| 2008 | `+1,826` |
| 2009 | `0` |
| 2010 | `+1,066` |
| 2011 | `+113` |
| 2012 | `0` |
| 2013 | `0` |
| 2014 | `0` |
| 2015 | `+589` |
| 2016 | `-26` |
| 2017 | `0` |
| 2018 | `-17` |
| 2019 | `+888` |
| 2020 | `-11` |
| 2021 | `+802` |
| 2022 | `+1,896` |
| 2023 | `0` |
| 2024 | `+146` |
| 2025 | `0` |
| 2026 | `+691` |

### 结构解读

- positive delta years: `11 / 27`
- negative delta years: `4 / 27`
- zero years: `12 / 27`

这说明 uplift 的形态不是“每年都稳定多赚一点”，而是：

> 只有在部分适合的 aftermath / HIGH_VOL 环境里才工作，其余年份基本与 baseline 相同。

这本身并不坏，因为 overlay 本来就是一个条件触发的 capital-allocation sleeve。真正重要的是：

- **坏年份不多**
- **负向年份幅度小**
- **正向年份分布跨越多个时期**

Top 5 absolute delta years：

| Year | Delta | Share of absolute yearly delta |
|---|---:|---:|
| 2022 | `+1,896` | `17.6%` |
| 2008 | `+1,826` | `17.0%` |
| 2007 | `+1,172` | `10.9%` |
| 2010 | `+1,066` | `9.9%` |
| 2019 | `+888` | `8.2%` |

没有单一年份占据绝对主导。最大的 `2022 + 2008` 也只是合计约 `34.6%` 的 absolute delta，而不是 `70%+` 那种高度集中。

---

## 3. Overlay Fire Distribution

### Fire 总体

- overlay fire count: `23`
- mean pre-existing short-gamma count: `0.61`
- fires with pre-existing `SG >= 2`: `0 / 23`
- mean idle BP at fire: `80.5%`

### Fires by regime

| Regime | Count |
|---|---:|
| `HIGH_VOL` | `23` |

### Fires by VIX bucket

| Bucket | Count |
|---|---:|
| `20-25` | `5` |
| `25-30` | `18` |

### Fires by pre-existing short-gamma count

| SG count | Count |
|---|---:|
| `0` | `9` |
| `1` | `14` |

### 解释

这组分布非常干净：

1. overlay 真正发生的地方全部是 `HIGH_VOL`
2. 几乎都在 `VIX 25-30`，也就是 disaster cap 之前、但 volatility 已经足够高的窗口
3. 触发时只允许已有 `0` 或 `1` 个 short-gamma posture，从未在 `>=2` 环境继续加码

这说明 `Overlay-F` 的 guardrail 语义是 coherent 的，不是看起来干净、实际上偷偷在危险环境加杠杆。

---

## 4. Recent Slice (`2018+`)

| Metric | Baseline | Overlay-F | Delta |
|---|---:|---:|---:|
| Total PnL | `+$164,958` | `+$169,353` | `+$4,395` |
| Annualized ROE | `5.544%` | `5.583%` | `+0.040pp` |
| Marginal $/BP-day | — | `+7.3007` | — |
| MaxDD | `-9,405` | `-9,392` | 基本持平 |

### 解释

recent-era 结果仍支持 `Overlay-F`，但语义要更精确：

- **方向仍为正**
- **unit economics 仍然很好**
- 但 **annualized ROE uplift 比全样本更薄**，只剩 `+0.040pp`

这意味着：

> `Overlay-F` 并没有在 recent era 失效，但也没有变成一个更强、更明显的现代 edge。

---

## 5. Quant Judgment

### 5.1 目前已确认的内容

`Overlay-F` 现在可以比较有把握地说：

- 它不是由单一年份主导
- 它不是由单个 PM case 人工撑起来
- 它的 fire 分布与 design intent 一致
- 它没有在 pre-existing `SG >= 2` 的环境继续叠仓
- 它在 recent era 仍为正

### 5.2 仍未被证明的内容

但同样需要明确：

- uplift 依然不大
- recent-era uplift 更薄，而不是更强
- 这更像一个“治理良好、经济上可正”的小 overlay，而不是高确信度的大级别改进

---

## 6. Recommendation

- **Topic**: `Q036` Phase 5 — Overlay-F confirmation
- **Findings**:
  - `Overlay-F` 的 uplift 不是单一年份集中
  - fire 分布集中在 `HIGH_VOL`, mostly `VIX 25-30`
  - pre-existing short-gamma guard 按预期工作，`SG>=2` fires 为 `0`
  - recent era 仍为正，但 uplift 更薄
- **Risks / Counterarguments**:
  - 如果 PM 需要的是“足够大、足够清晰”的 ROE 提升，这组证据仍不够强
  - 如果 PM 接受“小但治理干净的 overlay”，则 `F` 已是当前最合理候选
- **Confidence**: medium-high
- **Next Tests**:
  - 若继续，只应做最后一层 very narrow confirmation 或 stop
  - 不应再横向扩更多新候选
- **Recommendation**: **continue research, but close to decision point**

更具体地说：

> `Q036` 现在已经接近一个 PM judgment 问题，而不是“还差很多技术研究”的问题。技术上最合理的 lead candidate 已经是 `Overlay-F_sglt2`，后续若再研究，应该只做极少量最终确认，然后准备让 PM 决定是收口还是进入更正式讨论。
