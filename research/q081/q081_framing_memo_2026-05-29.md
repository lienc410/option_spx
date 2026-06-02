# Q081 Framing — Debit-策略现金机会成本 + LOW_VOL × BULL 路由审计

**Date**: 2026-05-29
**Owner**: Quant Researcher
**Status**: FRAMING — pending PM ratification before P0 kickoff
**Trigger**: 2nd quant pre-framing memo 2026-05-29（PM 转发，原文存 `task/q081_framing_2nd_quant_input_2026-05-29.md`）；PM 初始问题为"低 VIX 下 BCD vs BPS 的资源效率"
**Approval**: PM 2026-06-01 拍板（a. 框架同意 / b. cash-bound PM 直接确认 / c. hurdle = QQQ rolling / d. G-review 1+2 同一位 2nd quant）

---

## Thesis recentering (post-G-review 1, 2026-06-01)

P1 + P2 数据安静改变了研究重心。原始 framing 假设挤占 (BCD 吃光 QQQ 现金) 是核心风险；P1 实测 0 crowd-out → 挤占在历史上从未发生（sequential ladder 自然避免）。研究空间收窄为：

1. **单笔 cash efficiency**（BCD per-trade vs 现金留 QQQ 的纯 ROE 比较，与挤占无关）— P3 主战场
2. **定性 routing audit**（IVP≥67→BPS 是否结构上正确，per cash-bound 推论）— P3 半页定性论证
3. **Single-trade cash sizing**（在 $37k cash baseline 下，单笔 BCD worst-case cash draw 是否在 slack 内）— **P5 主 verdict**

**降权**：BCD 尾部 CI 精度（n=21 已够，因 verdict 收窄）。

**升权**：sizing recommendation（从 P5 附属建议升级为主 actionable）。原因：worst BCD = 8.8% of $37k cash baseline，在 cash-bound 账户里是真冲击；defer 会让 Q081 close 时无 actionable 产出。

参见 2nd quant G1 reply (`task/q081_p2_g1_2nd_quant_review_2026-06-01_Review.md`) 跨 Q 收尾段，Q078 thesis pivot 先例同构。

---

## 0. 问题归纳（PM 备忘 § 1 → § 4 的 quant-format 复述）

当前 SPEC-104 sleeve governance 按 **BP utilization** 设 cap。但若账户实际是 **cash-bound 而非 BP-bound**（闲置现金在 QQQ/SGOV 滚动以避免现金 drag），则：

- **BCD（debit 策略）**：占瓶颈资源（现金），几乎不占富余资源（BP）
- **BPS（credit 策略）**：占富余资源（BP），几乎不占瓶颈资源（现金）

LOW_VOL × BULL 矩阵当前路由 → BCD。如果上述前提成立，路由方向**与资源画像反向**：消耗稀缺资源、闲置富余资源。SPEC-104 cap 没有约束到 BCD 的真正瓶颈，可能允许 debit 仓 stack 直至吃光 QQQ 现金管理预算。

---

## 1. Phase 结构（带 kill gate + G-review node）

每 phase 输出独立 memo + 数据文件，PM/Quant 检查 kill gate 后再决定是否 continue。

### **P0** — Cash-bound 前提验证（**最重要、最容易 kill**）

**问题**：账户历史窗口（建议过去 12 个月）内是否真 cash-bound？具体定义：
- "cash-bound" = （可用现金 ÷ NLV）持续 < 20% 且 (BP 利用率 ÷ BP cap) < 70%
- 或更严格：QQQ/SGOV 持仓占 NLV > 30%，证明闲置现金已在主动管理

**数据源**：
- `data/daily_snapshot.jsonl`（NLV）
- Schwab API：当前账户 cash + positions（历史快照见 §6 数据缺口）
- E-Trade：同上
- 若历史每日 cash 利用率无快照，则取 PM 提供的描述 + 当前一次性快照作 anchor

**输出**：`research/q081/q081_p0_cash_bound.{py,csv,md}`

**Kill gate**:
- 若 cash utilization 与 BP utilization 同步高（双 bound）或 BP utilization 反而更紧 → **整个 Q081 作废**，归档为"前提不成立，BCD 占现金不是真成本"。PM §5 第三条已 explicit 允许此 verdict。
- 若 cash 持续宽松、BP 也宽松 → Q081 退化为只关心 left-tail（仍有价值，但 cash hurdle 论点弱化）

**G-review 0**：PM 看 P0 verdict（kill or continue）。

---

### **P1** — BCD 历史 cash deployment 时间线 + crowd-out 事件识别

**前提**：P0 通过。

**问题**：低 VIX 历史窗口里，BCD 在场期间是否曾出现"BCD 现金占用 > 可分配现金"（即 BCD 实际**挤占**了 QQQ/SGOV 配置）？

**数据源**：
- 3y backtest 已知 21 BCD trades（`data/backtest_trades_3y_2026-04-29.csv`），每笔 entry debit / exit pnl / hold days 都有
- 同期 NLV + free-cash 估算（用 PM 给的当前 cash ratio 反推历史，或 PM 直接提供）

**输出**：`research/q081/q081_p1_bcd_cash_timeline.{py,csv,md}`
- 时间序列图：BCD cash usage / NLV vs 同期 BP utilization / cap
- crowd-out 事件清单：每次 BCD 现金占用 > X% NLV 的日期

**Continue → P2**

---

### **P2** — BCD cash-ROE 分布（左尾 p05/p01，**不是均值**）

**这是整个研究的 anchor**，per PM §2 方法学要求。

**问题**：低 VIX BCD 实际 cash-ROE（PnL ÷ debit ÷ hold days × 365）的分布形态？尤其左尾。

**计算**：
- 对 21 BCD trade 计算单笔 cash-ROE annualized
- 报告 mean / median / **p05 / p01** / std / worst
- 区分 LOW_VOL × LOW_IVP vs LOW_VOL × HIGH_IVP 子样本（n 小但仍报）

**输出**：`research/q081/q081_p2_bcd_cash_roe_dist.{py,csv,md}`

**G-review 1**：左尾方法学（**必做**，per memory `feedback_kill_gate_external_read`）
- 21 个样本算 p05 是否有意义？bootstrap?
- 是否需要合成更多 BCD 历史（用 1y q041 chain 数据回填，触及 q079 已 build 的工具链）

---

### **P3** — QQQ hurdle benchmark + thesis recentering + qualitative routing audit

**Updated scope per G-review 1**：

**§A — Thesis recentering（半页开头）**：显式记录 P1 后挤占问题已 non-issue，verdict 收窄为 single-trade cash efficiency + qualitative routing + sizing。

**§B — Per-trade matched-window comparison**：
- 21 笔 BCD 每笔取同 hold window 的 QQQ period return
- 比较 period-ROE 分布（**不年化**）
- 报 BCD 与 QQQ 同窗口的 p05 / median / mean 差

**§C — Direction bias control panel**（G1 Q1 补强）：
- 21 个 hold window 的 SPX / QQQ same-window return 分布
- 若窗口 systematically 偏上行 → BCD 跑赢 QQQ 必须打折读

**§D — Qualitative IVP≥67 → BPS routing audit**（G1 Q3 重新表述）：
- 半页结构性论证：cash-bound 账户 + premium 充裕（IVP≥67）→ credit (BPS, 不占现金) 对 debit (BCD, 占现金) 有 structural advantage，与 ROI 谁高无关
- 不需 IVP_HIGH 反事实合成；用 cash-bound 推论 ratify 矩阵 routing

**§E — Sizing prep**：worst-case single-trade cash draw distribution，喂 P5 cap 标定

**输出**：`research/q081/q081_p3_{qqq_hurdle.py, window_bias.csv, hurdle_benchmark.csv, memo.md}`

**Decision logic（更新）**:
- BCD p05 period-ROE > QQQ p05 same-window（直接比较，无 hurdle 加成）→ BCD 在 cash 维度跑赢
- 反之 → BCD 没跑赢，倾向 cash-hurdle gate
- 但即便 BCD 跑赢，仍需在 P5 上 sizing cap，因为单笔 worst-case = 8.8% liquid cash 是独立风险

---

### **P4** — BPS-in-LOW_IVP 独立验证（PM 直觉 B 复核）

**Always run，不被 P3 kill**。这条是 PM 主动要求我 challenge 他自己的劝阻。

**问题**：低 IVP 子样本里 BPS 的 ROE-on-BP 真的差到不值得开吗？哪怕 BP 是"免费"的？

**数据源**：
- 3y backtest 14 BPS trade 全部在 NORMAL VIX（15-18）。LOW_IVP 子样本可能 n=0 或极少
- 需要 counterfactual：把 BCD 实际 trade 日强行换成 BPS（同 underlying + 同 entry date，按 BPS HV2 / HV3 selector 参数算 strike），看模拟 PnL

**输出**：`research/q081/q081_p4_bps_low_ivp_counterfactual.{py,csv,md}`

**Decision logic**:
- 若发现某 IVP 子区间 BPS ROE-on-BP > QQQ hurdle 后 → 收回 PM 自己的劝阻，矩阵可能有 BPS 入场窗口
- 若 BPS 全 IVP 子区间 ROE-on-BP 都低于 hurdle → 确认 PM 直觉 B，BPS 不进 LOW_VOL

---

### **P5** — Verdict + SPEC 推荐

汇总 P0-P4 → 三选一：

| 路径 | 触发条件 | 后续工作 |
|---|---|---|
| **A. 维持现状** | P0 kill / BCD p05 显著跑赢 + 无 crowd-out | 归档 Q081 closed |
| **B. SPEC: debit cash budget cap** | BCD 跑赢 + 历史出现 crowd-out 事件 | 起 SPEC-XXX：sleeve 之上加 `cash_budget_pct` 全局 cap |
| **C. SPEC: BCD cash-hurdle gate** | BCD p05 不显著高于 QQQ hurdle | 起 SPEC-XXX：selector 在路由 BCD 前 check expected cash-ROE > rolling QQQ hurdle，否则降级 reduce_wait |
| **不出现路径**：把 BPS 加进 LOW_VOL 矩阵（PM §3 直觉 B 已 self-vetoed，P4 只是 sanity-check） | | |

**G-review 2**：P5 verdict 必须外审（per `feedback_kill_gate_external_read`）—— kill verdict 或 SPEC 推荐二者都需要 2nd quant review packet。

---

## 2. 决策门槛细化（待 G-review 1 ratify）

PM §5 给的硬阈值要 quant 落地：

- "BCD 显著跑赢" = p05_BCD - p05_QQQ > 2× bootstrap_se（per memory `feedback_noise_threshold` 已 calibrate 到 4σ 但那是 strategy-comparison level；这里 debit-vs-beta 方差结构不同，先用 2σ on p05，G-review 1 重新校）
- "historical crowd-out" = 任一历史日，BCD cash usage > 当日 available cash（PM 提供 cash 上限即可定义）
- "QQQ hurdle" = rolling 90-day QQQ annualized return（不用历史均值，因为 BCD 决策是 forward-looking）

---

## 3. Out of scope（Q081 不做）

- 改 LOW_VOL × NEUTRAL → IC 这一格（IC 是 limited-debit，cash 占用居中，单独 study）
- 改 HIGH_VOL 区域（BPS_hv / BCS_hv / IC_hv 都是 credit，cash 论点不适用）
- 改 EXTREME_VOL（Layer-1 frozen）
- **PM intuition B 之外的"把 BPS 加进 LOW_VOL"**（P4 只验证 PM 自己的劝阻，不主动 expand）
- 改 SPEC-058/060 IVP gate（Q079 的领域，独立）
- 换底层标的（不研究 NDX / RUT 替代 SPX）

---

## 4. Files

```
research/q081/
├── q081_framing_memo_2026-05-29.md          ← this file
├── q081_p0_cash_bound.{py,csv,md}            ← P0 数据脚本 + 输出 + verdict
├── q081_p1_bcd_cash_timeline.{py,csv,md}    ← P1
├── q081_p2_bcd_cash_roe_dist.{py,csv,md}    ← P2
├── q081_p3_hurdle_benchmark.{py,csv,md}     ← P3
├── q081_p4_bps_low_ivp_counterfactual.{py,csv,md}  ← P4
└── q081_p5_verdict_2026-MM-DD.md             ← P5

task/
└── q081_framing_2nd_quant_review_packet_2026-MM-DD.md   ← G-review 0 packet (P0 + framing)
```

---

## 5. PM 输入需要

以下信息 quant 这边没有现成的，请 PM 提供或授权我从 broker 拉：

1. **当前账户 cash ratio 快照**：Schwab + E-Trade 的现金、QQQ 持仓、SGOV 持仓、option positions 各占 NLV 比例（一次性，今天的数）
2. **历史回顾**（粗估即可）：过去 6-12 个月 BP utilization 大致区间（例如"BP 一直 < 50% cap"还是"经常碰 cap"）
3. **现金管理 hurdle 选哪个**：QQQ rolling return / 固定 SGOV 4.8% / 加权 mix？PM 给一个默认值，G-review 1 可以微调

---

## 6. 数据缺口 / 风险

- **N 太小**：3y 21 BCD trades，p05 / p01 估计 bootstrap 残差大。若 G-review 1 判定不足，需扩展到 q041 chain history 反推合成 BCD trade（多花 2-3 天）
- **历史 cash 利用率快照缺失**：daily_snapshot 只有 NLV，没单独记 cash。需要 PM 描述大致情形 + 用当前快照 anchor 倒推
- **PM intuition A 与 B 都可能错**：P0 / P4 都允许推翻 PM 的判断；quant 这边不偏袒 PM 直觉

---

## 7. 时序估计

| Phase | 工时 | Calendar 估计（依 G-review 等待） |
|---|---|---|
| P0 | 0.5 day | 2026-05-30 - 2026-05-31 |
| G-review 0 | PM 1 day | 2026-06-01 - 2026-06-02 |
| P1 | 1 day | 2026-06-02 |
| P2 | 1 day | 2026-06-03 |
| G-review 1 | 2nd quant 2-3 day | 2026-06-04 - 2026-06-06 |
| P3 | 1 day | 2026-06-07 |
| P4 | 1.5 day | 2026-06-08 - 2026-06-09 |
| P5 + G-review 2 | 2 day | 2026-06-10 - 2026-06-11 |
| 总 | **~8 working days** | 落地 SPEC 顺延 |

---

## 8. PM ratification

待回复事项：
1. 框架同意？特别 P0 kill criterion（账户不 cash-bound → 作废）—— 你能接受这个 verdict 吗？
2. § 5 PM 输入：当前 cash ratio 快照 / 历史 BP 利用率描述 / hurdle 选项，请提供
3. § 7 时序：8 个工作日可以接受？若 PM 要更快可压缩 P4
4. G-review 1 (P2 左尾方法学) 和 G-review 2 (P5 verdict) 选哪位 2nd quant reviewer？

回复 OK 即开始 P0。
