# Q066 Aftermath vs Q042 Co-firing — 2nd Quant Review Packet

- **Date**: 2026-05-12
- **Prepared by**: Quant Researcher
- **Audience**: 2nd Quant Reviewer
- **Topic**: 是否两个 addon（SPEC-064 Aftermath broken-wing IC vs Q042 Drawdown Overlay）功能重复？应合并 / 竞争 / 保留双 addon？
- **Stage**: Post-research，pre-decision; 1st Quant 结论 "不应合并 / 不应竞争"，PM 在采取任何操作前要求独立 review

---

## 1. Review Request

PM 提出问题："两个 addon 是否都在做'抄底'（post-decline entry），是否功能重复？是否应合并或淘汰一个？"

1st Quant 给出两层论证：
1. **理论层（[doc/addon_greek_orthogonality_2026-05-12.md](../doc/addon_greek_orthogonality_2026-05-12.md)）**：两者 Greek 全部反向（vega/gamma/delta/theta），信号空间不同（VIX 结构 vs SPX ddATH），执行路径独立
2. **实证层（Q066，本 packet）**：19yr (2007-2026) 真实数据 day-level 重叠 0.9%，Q042-A 事件级 74% 与 aftermath 异步

**Verdict**: 两个 addon empirically + theoretically 正交，**不应合并 / 不应竞争**。

我们请求独立 review 以下问题：

> Q066 实证方法是否成立？Day-level 0.9% / 事件级 74-86% 异步的结论是否足够支持 "保持双 addon" 决策？是否漏掉某种结构性失败模式或风险叠加场景？

**我们不在请教**：
- 是否调整任一 addon 的触发参数（不在 scope）
- Q042 / SPEC-064 各自 standalone 表现（已有独立 review）

**我们在请教**：
- Co-firing 量化方法是否 fair？是否漏掉 portfolio 层风险？
- N=5 Q042-B / N=35 Q042-A 是否足以下结论？
- "正交"结论是否过度依赖 ±5 TD 窗口的选择？
- 没做 PnL correlation 是否是关键漏洞？
- Greek 正交论证在 short-vol(aftermath) + long-vol(Q042) 同时持仓的实际净 PnL 是否真的 "partial hedge"？

详细问题见 §7。

---

## 2. Background — 两个 Addon 的实际机制

### 2.1 SPEC-064 Aftermath broken-wing IC

[strategy/selector.py:295](../strategy/selector.py) `is_aftermath()`:

```python
AFTERMATH_PEAK_VIX_10D_MIN = 28.0
AFTERMATH_OFF_PEAK_PCT     = 0.10
EXTREME_VIX                = 40.0
```

满足 (peak 10TD VIX ≥ 28) AND (current VIX ≤ peak × 0.90) AND (current VIX < 40) →
触发 V3-A broken-wing IC（卖出 put + call 各一对，short vol bet）。

频率：2007-2026 共 **518 fire days / 90 windows**。

### 2.2 Q042 Dual-Sleeve Drawdown Overlay

[signals/q042_trigger.py](../signals/q042_trigger.py):

```python
_DD4_THRESHOLD   = -0.04   # Sleeve A trigger (ddATH ≤ -4%)
_DD15_THRESHOLD  = -0.15   # Sleeve B outer trigger
_REARM_THRESHOLD = -0.02   # ddATH ≥ -2% to re-arm
_WATCH_DAYS      = 30      # Sleeve B watching window
_MA10_WINDOW     = 10      # Sleeve B inner trigger (close > MA10)
```

- **Sleeve A**：首次穿越 `ddATH ≤ -4%` → 触发 30-DTE long call spread → re-arm 需 `ddATH ≥ -2%`
- **Sleeve B**：首次穿越 `ddATH ≤ -15%` → 进入 watching → 30TD 内首次 `close > MA10` → 触发 90-DTE long call spread

频率：2007-2026 Sleeve A **35 triggers**，Sleeve B **5 triggers**。

### 2.3 表层相似 vs 实际差异

| 维度 | Aftermath | Q042 |
|---|---|---|
| 信号空间 | VIX 结构 | SPX 价格 |
| 入场结构 | Broken-wing IC | Long call spread |
| Greeks 方向 | **short vega + short gamma + 微 short delta + long theta** | **long delta + long gamma + long vega + short theta** |
| 赚什么钱 | IV elevated 但开始 mean-revert + 价格在 short wings 之间 | SPX 反弹 → call spread max payoff |
| 失败模式 | IV 维持 / VIX 反弹 ≥ 40 / 价格穿出 short wings | SPX 进一步深跌 / 横盘到 expiry |
| BP 占用 | 主 sleeve | Combined cap ≤ 20% NLV（[q042_gate.py](../strategy/q042_gate.py)）|
| 执行 | [selector.py](../strategy/selector.py) 自动 | Telegram → 手动 |

---

## 3. Method（Q066）

[research/q066/q066_cofiring.py](../research/q066/q066_cofiring.py) 完整复现两个 addon 的生产触发逻辑：

- 数据：yfinance ^VIX + ^GSPC 2007-01-03 → 2026-05-12, **4870 trading days**
- Aftermath flag：每日按生产参数计算
- Q042 state machine：完整 armed / in_watching / re-arm 状态机；mock 30/90 TD hold（生产用 `active_position_expiry` 跟踪，但 trigger 计数应等价）
- 三种重叠度量：
  - **Day-level overlap**：same-day both 触发
  - **Event-level ±5 TD**：Q042 触发后 ±5 TD 内是否有 aftermath 日
  - **Aftermath window 视角**：每个 aftermath window ±5 TD 内是否有 Q042 触发

---

## 4. Findings

### 4.1 触发频率（19 年）

| Addon | 触发日数 | 年化频率 |
|---|---|---|
| Aftermath | 518 | ~27 / yr |
| Q042-A trigger | 35 | ~1.8 / yr |
| Q042-B watching | 32 | ~1.7 / yr |
| Q042-B trigger | **5** | ~0.26 / yr |

### 4.2 Day-level confusion matrix

|  | Q042 (A or B) = YES | Q042 = NO | 行总 |
|---|---|---|---|
| Aftermath = YES | **5** | 513 | 518 |
| Aftermath = NO | 35 | 4317 | 4352 |

- Same-day overlap rate = 5 / (5+513+35) = **0.9%**
- 99.1% 的"任一触发"日子只有一个 addon 触发

### 4.3 Event-level co-firing（±5 TD window）

**Q042-A 视角**（35 events）：
- 9 / 35 (**26%**) co-fire with Aftermath ±5 TD
- **26 / 35 (74%) 是 vol-quiet drawdown**（aftermath 完全不会触发）

代表 vol-quiet 事件：2013-06-20 / 2013-08-27 / 2014-01-29 / 2014-10-09 / 2014-12-15 / 2015-01-30 / 2015-11-13 / 2015-12-31 / 2016-05-19 / 2018-10-10 / 2019-05-13 / 2019-08-05 / 2019-10-02 / 2024-04-17 / 2024-07-24 / 2025-01-10 / 2025-02-27 / 2025-11-20 等——VIX 在 16-26 区间，SPX 缓慢 -4% 回撤，aftermath gate 不触发但 Q042 capture 上升 convexity。

**Q042-B 视角**（5 events）：

| 日期 | ddath_% | VIX | 距最近 aftermath |
|---|---|---|---|
| 2008-01-28 | -13.49% | 27.78 | 0 TD |
| 2018-12-31 | -14.46% | 25.42 | 0 TD |
| 2020-03-25 | -26.89% | 63.95 | 13 TD（aftermath 被 VIX≥40 拦截）|
| 2022-05-17 | -14.75% | 26.10 | 0 TD |
| 2025-04-09 | -11.19% | 33.62 | 0 TD |

- 4 / 5 (**80%**) co-fire with Aftermath ±5 TD
- 但 N=5 难下统计学 conclusion
- 2020-03-25 这例 aftermath 被 VIX≥40 EXTREME 拦截（[Q065](../research/q065/q065_memo_2026-05-12.md) 保护机制正确工作）

**Aftermath windows 视角**（90 windows）：
- 13 / 90 (**14%**) ±5 TD 配对 Q042-A
- 6 / 90 (**7%**) ±5 TD 配对 Q042-B
- **86-93% aftermath windows 是 vol-only 事件**，SPX 无 -4% 回撤

### 4.4 同时触发的典型事件

5 个 day-level overlap + 同期 ±5 TD：
- 2007-12-04（A）
- 2008-01-28（B）
- 2015-08-20（A，VIX 19）
- 2018-02-05 Volmageddon（A，VIX 37）
- 2018-12-31（B）
- 2020-02-24（A）
- 2020-09-04 / 2020-10-21（A，post-COVID rolling ATH 反复 -4%）
- 2021-03-04 / 2021-12-01（A）
- 2022-05-17（B）
- 2025-04-09（B，tariff）
- 2026-03-12（A）

共性：VIX up→down 与 SPX down→up 同时发生。Greek 角度看是 **vega 反向 + delta 反向 partial hedge**（详 [addon_greek_orthogonality](../doc/addon_greek_orthogonality_2026-05-12.md) §3）。

---

## 5. Verdict（1st Quant 给出，请 reviewer 检验）

**两个 addon empirically 正交，不应合并 / 不应竞争**。

| 论据 | 数据支持 |
|---|---|
| Day-level 几乎零同步 | 0.9% overlap |
| Q042-A 74% 是 aftermath 不能 capture 的 vol-quiet drawdown | 26/35 events |
| Aftermath 86% 是 Q042 不能 capture 的 vol-only event | 77/90 windows |
| Greek 全反向 | 理论 + 同时持仓事件的 Greek 净额 |
| BP 冲突已机制化处理 | [q042_gate.py](../strategy/q042_gate.py) joint cap ≤ 20% |

---

## 6. Caveats / Open Questions

1. **未量化触发日 PnL correlation**。若两个 addon 在 co-fire 日都 LOSS 且 correlation > 0.7，仍可能存在 portfolio 层尾部叠加。Q066 仅看触发频率不看 PnL —— 这是已知漏洞，但补做需要真实期权回测 backtest（heavy），未启动
2. **Q042-B N=5 小样本**。80% co-fire rate 置信区间宽（5 个事件中 4 个同步可能是偶然）；如果未来 B 触发样本增加到 N=15+，需重新评估
3. **±5 TD 窗口是分析师选择**。扩到 ±10 TD 会推高 co-fire 比例：
   - Q042-A ±10 TD co-fire 大致 ~35-40%（估算）
   - 但语义转为"事件 cluster 关联性"而非"信号冗余"
   - 1st Quant 选 ±5 TD 是为对齐 Q042 sleeve A 30 DTE 期权的快速 PnL 窗口；reviewer 可挑战此选择
4. **Q042 state machine mock simplified**。研究脚本用固定 30/90 TD hold；生产用 `active_position_expiry` 跟踪。Trigger 计数应近似（Sleeve A 35 / Sleeve B 5 与历史预期匹配）但具体日期可能偏移 1-2 TD
5. **Greek 反向是否真的 hedge？** 理论上 short vega（aftermath）+ long vega（Q042）净 vega 缓和；但 IC 的 vega 在 short wings 附近 vs call spread 的 vega 在 ATM/上 wing 的形态不同，不是 unit-vega-for-unit-vega 对冲。同样 gamma profile 形态差异显著。**这是 1st Quant 论证的弱点之一**

---

## 7. Specific Review Questions

请 reviewer 在以下问题上发表独立意见：

### Q7.1 — 方法论 fairness

±5 TD window 是否是合理的 "co-firing" 定义？±5 TD 之外的事件是否应被视为"独立机会"？如果改为 ±10 TD 是否会推翻"正交"结论？

### Q7.2 — Sample size adequacy

- Q042-A N=35 events 在 19yr 内是否足够 robust 量化 74% 异步？
- Q042-B N=5 是否任何结论都不可信？是否应明确标注 B 的 co-firing 比例为 "unrobust pending more data"？

### Q7.3 — 缺失的失败模式

是否存在一种场景下两个 addon 实际产生**叠加风险**（不是 partial hedge）？例如：
- 极端反向场景：aftermath IC 入场后 SPX 继续暴跌穿过 short put（loss）+ Q042 call spread 归零（loss）—— 两者同向 loss
- 这种场景历史上是否有先例？1st Quant 未单独列出，是否漏掉

### Q7.4 — Greek "partial hedge" 是否真实

1st Quant 论证 "vega 反向 → partial hedge"。但：
- IC short vega 集中在 short wings 附近 strike
- Call spread long vega 集中在 ATM 至上 wing
- 两者 vega curve 形态不同；net vega 在不同 SPX 路径下变化不均
- Reviewer 是否同意 "Greek 全反向" 的 quantitative magnitude 等价于 "portfolio 层风险缓和"？还是只是 symbol-level 反向而 magnitude 上仍可能同向暴露？

### Q7.5 — 未做 PnL correlation 是 fatal flaw 吗

1st Quant 承认未量化 co-fire 日 PnL correlation。Reviewer 认为：
- 这是必须先补的研究才能下"不合并"结论？
- 还是触发频率 + Greek 反向已足够支撑结论，PnL correlation 是 nice-to-have？

### Q7.6 — Reviewer 视角的最终建议

基于 1st Quant 提供的证据 + 自身判断，reviewer 应推荐：
- A. 接受 "保持双 addon" 结论，不需 PM 进一步操作
- B. 接受方向但要求补 PnL correlation 研究（Q067 启动）
- C. 拒绝结论，建议某种形式的合并 / 淘汰（请说明具体方案）
- D. 其他（请阐述）

---

## 8. Outputs / 可验证文件

- **Memo**: [research/q066/q066_memo_2026-05-12.md](../research/q066/q066_memo_2026-05-12.md)
- **Script**: [research/q066/q066_cofiring.py](../research/q066/q066_cofiring.py)（完整生产逻辑复现）
- **Daily flags CSV**: `research/q066/q066_daily_flags.csv` — 4870 行每日 flag
- **Event overlap CSV**: `research/q066/q066_event_overlap.csv` — 40 个 Q042 触发事件 + 距最近 aftermath 距离
- **理论论证**: [doc/addon_greek_orthogonality_2026-05-12.md](../doc/addon_greek_orthogonality_2026-05-12.md)
- **生产代码**: [strategy/selector.py:295](../strategy/selector.py)，[signals/q042_trigger.py](../signals/q042_trigger.py)，[strategy/q042_gate.py](../strategy/q042_gate.py)
- **RESEARCH_LOG**: R-20260512-02

---

## 9. 期望 review 形式

请按以下格式回复（参照 [q064_aftermath_2nd_quant_review_packet_2026-05-12_Review.md](q064_aftermath_2nd_quant_review_packet_2026-05-12_Review.md) 的体例）：

1. **Top-line verdict**: PASS / REVISE / FAIL
2. **逐 Q7.1 ~ Q7.6 回复**
3. **若 REVISE**：列出必须补的研究项（特别是 PnL correlation）
4. **若 FAIL**：说明 1st Quant 漏掉的关键证据 / 错误推理

回复文件命名：`q066_cofiring_2nd_quant_review_packet_2026-05-12_Review.md`，放本 task/ 目录。
