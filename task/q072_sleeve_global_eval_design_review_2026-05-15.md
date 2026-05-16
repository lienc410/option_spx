# Q072 — Sleeve Global Evaluation Design Review
## Drawdown Overlay × Aftermath × HV Ladder — BP 竞争与组合尾部测试方案

**Date**: 2026-05-15
**Prepared by**: Quant Researcher
**Audience**: 2nd Quant Reviewer
**Stage**: Pre-research design review — 在开跑 P1 之前验证评估框架是否完整
**Reviewer response**: `task/q072_sleeve_global_eval_design_review_2026-05-15_Review.md`

---

## 0. TL;DR

主策略之外的三个 sleeve（Drawdown Overlay / Aftermath / HV Ladder）都在 high vol 或市场承压时触发。PM 提问：它们之间是否会争抢 BP、Greek 是否同向叠加 tail、入场后回撤画像是否被低估？

本文档请 2nd Quant 评估**研究设计本身**是否完整：是否抓住了 sleeve 全局组合的关键风险维度，P1–P4 的顺序是否合理，判断锚点是否过松/过紧。**不评估具体参数，不要求跑数据。**

---

## 1. 三个 Sleeve 的当前状态

| Sleeve | 来源 | 入场触发 | Greek 方向 | 状态 |
|---|---|---|---|---|
| **Drawdown Overlay** | Q042 / SPEC-094(.1) | dd4 lenient（Sleeve A）/ dd15+MA10 reclaim（Sleeve B），ATM/+5% call vertical DTE 90 | **Long delta / long gamma**（crash reversal）| Paper trading active on old Air，10%/sleeve，组合 cap 20% |
| **Aftermath** | SPEC-064（permission label）| VIX peak_10d ≥ 28 且 off-peak ≥ 10%，feed BPS HV | **Short vega / short gamma**（HIGH_VOL）| Production，Q070 刚结论维持 threshold=28 |
| **HV Ladder** | Q071 / ES High-Vol Sell Put Ladder | HIGH_VOL regime（VIX ≥ 22）+ trend_ok，/ES rolling ladder DTE 49→21，STOP_MULT=15 | **Short delta / short vega**（persistent HV）| Research 阶段，promote 决策待定（Q071 closure 2026-05-14）|

**关键观察**：三者的 Greek 方向**并不同向**——Drawdown Overlay 是 long gamma/long delta 的反向押注，Aftermath/HV Ladder 是 short vega 的卖方收敛。这意味着 "sleeve 是同一笔风险换三个名字" 的简单假设**未必成立**，但 entry 时间窗很可能高度重合（都集中在 stress 期）。

---

## 2. 核心研究问题

| 问题 | 想验证什么 |
|---|---|
| Q-A | 三个 sleeve 的**入场触发是否在时间上同步**？同步是巧合还是结构性？|
| Q-B | 三个 sleeve **同时在场**时，组合 BP 占用是否会挤压主策略入场窗？|
| Q-C | sleeve 之间 daily P&L 相关性如何？stress 日是分散还是放大组合 drawdown？|
| Q-D | 加入 sleeve pack 相对 main-only 的 **marginal $/BP-day 与尾部代价**是否值得？|

---

## 3. 提议的研究范围（P1–P4）

### P1 — Co-activation Map（同时在场图谱）

**数据**：`research/q064/q064_p1_daily_flags.csv` + Q042 dd4/dd15 触发日志 + Q071 V2f trade list

**方法**：
- 19y 每日打标签：`{main_active, dd_overlay_active, aftermath_active, hv_ladder_active}`（按 entry→exit 区间填充）
- 共激活矩阵 3×3（sleeve 两两）+ main × sleeve 矩阵
- BP 占用堆叠时间序列（按策略分层）

**关键产出**：
- `P(≥2 sleeves active | any sleeve active)`
- `P(main_active | sleeve_active)` —— 测主策略是否在 sleeve 触发时常常已经在场
- 4-way co-occurrence table（16 states × 占比）

**判断锚点**：
- 若 sleeve 两两共激活率 < 20%：天然分散，P3 ablation 可简化
- 若 > 50%：sleeve 实质重叠，必须做 P3 + P4

### P2 — Entry 特征画像

对每个 sleeve 入场打标签：VIX 水平 / VIX 10d slope / SPX 距 20d high 的回撤幅度 / IVP_252 / 距上一次 sleeve 入场的间隔天数。

**产出**：3 个 sleeve 的 entry 特征分布对比（密度叠加）。

**判断锚点**：
- 分布几乎重合 → sleeve 是同一信号的三个名字
- 分布错位（例：DD 抓回撤幅度、Aftermath 抓 VIX peak-and-fall、HV Ladder 抓持续高 VIX）→ 互补窗口

### P3 — Co-loss & Drawdown 测试

**对每笔 sleeve trade**：
- MAE（max adverse excursion）、5d / 10d / exit 时的 mark-to-market 曲线
- entry 当日 portfolio Greek 暴露（vega/gamma/delta）& BP 占用

**Co-loss 测试**（参照 Q066 §6）：
- 标记"灾难窗口"= 任一 sleeve 单日 P&L 在历史 worst 5% 的天
- 在这些日子里查另外两个 sleeve 同步 P&L、main 同步 P&L
- 4×4 daily P&L 相关矩阵（main + 3 sleeves）
- CVaR 5%（组合层 vs 单 sleeve 层）

**判断锚点**：
- sleeve 间 daily P&L 相关 > 0.5 且 stress 期同号 → 加 sleeve 放大尾部
- DD Overlay 与短 vega sleeve 反向（预期）→ 可证伪/证实 Greek diversification 假说

### P4 — Marginal Value Ablation

**4 套回测**（19y baseline 框架）：

| 组合 | 含义 |
|------|------|
| A | Main only（baseline）|
| B_i | Main + 单 sleeve（×3）|
| C | Main + 全部 3 sleeves |
| D_i | Leave-one-out（×3）|

**指标包**（standard metrics pack）：total P&L、Sharpe、max DD、CVaR 5%、**marginal $/BP-day**、worst trade、worst 20d window、annualized return on average BP

**判断锚点**：
- `C − A ≈ Σ(B_i − A)` → sleeve 独立可加
- `C − A < Σ(B_i − A)` 显著 → 存在 cannibalization
- D_i 测试找出"裁掉损失最小的 sleeve"

---

## 4. 已识别风险（请 reviewer 补充）

1. **HV Ladder 是 /ES 期货账户**，与 SPX 主策略 + Drawdown Overlay + Aftermath 的 BP 池**物理不互通**。BP 竞争问题主要在 SPX 池内（main vs DD Overlay vs Aftermath-feed BPS HV）。这点会让 P1 的 BP 堆叠图需要按账户分层，不能简单加总。
2. **Drawdown Overlay paper trading 仅 5 天**（自 2026-05-10 部署，首次 SPEC-094.1 trigger 未发生）。P3 的 co-loss 测试只能依赖历史 backtest 重放，没有 live tape 校准。
3. **Aftermath 是 permission label 不是独立策略**——它的"trade"实际上是被它解锁的 BPS HV 入场。P1/P3 里要把"aftermath active"理解为"BPS HV 入场许可窗口"，而不是 standalone strategy P&L。这会影响 P4 ablation 设计：拿掉 aftermath 等同于禁用 BPS HV 路径。
4. **HV Ladder 尚未 promote**，目前是 backtest-only。P3/P4 把它当作"假设已部署"做并行回测是否合理？还是应该等 Q071 closure 后再启动 Q072？

---

## 5. Review Questions（2nd Quant 请明确回答）

**Q1 — 框架完整性**
Co-activation map（P1）+ entry 特征（P2）+ co-loss（P3）+ ablation（P4）是否覆盖了 "sleeve 全局评估" 的关键维度？有哪些维度被遗漏（如 sleeve-level Greek netting、margin call 触发链、roll period 重叠等）？

**Q2 — Greek 方向不同的处理**
Drawdown Overlay 是 long gamma，另两个是 short vega/gamma。这种 Greek 反向是否应在 P3 单独建模（例如分 "stress 加仓 vs stress 收敛" 两条 P&L 路径），还是只在 P4 ablation 层观察组合净效应即可？

**Q3 — Aftermath 的口径**
Aftermath 是 permission label，把它当作"独立 sleeve"参与 P4 ablation 会不会产生口径错误？是否应该把 P4 改为 "BPS HV (with/without aftermath gate)" 的对比，而把 Drawdown Overlay 和 HV Ladder 作为真正可加可减的 sleeve？

**Q4 — HV Ladder 时机**
HV Ladder 仍在 Q071 closure 阶段。Q072 应该：(a) 等 Q071 final memo 后再启动；(b) 立刻启动但用 V2f baseline 参数作占位；(c) Q072 P1+P2 先做（只看 entry 触发，不依赖 P&L），P3+P4 等 Q071 锁定后再做？

**Q5 — 判断阈值**
P1 共激活率 20%/50%、P3 daily P&L 相关 0.5、P4 `C − A < Σ(B_i − A)` 的显著性门槛——这些 hard thresholds 是否过松/过紧？建议怎么收紧？

**Q6 — 优先级与停研条件**
按当前优先级 P1 → P2 → P3 → P4 是否合理？什么早期信号会让你建议**停止 Q072**（例如 P1 显示共激活率 < 5%，说明 sleeve 时间上根本不冲突）？

---

## 6. 不在范围内

- 修改任何生产代码（Q072 全部在研究层）
- 重新评估单个 sleeve 自身参数（Drawdown Overlay sizing、Aftermath threshold、HV Ladder DTE 等都已各自 lock）
- Sleeve-level position cap 的实施 SPEC（若 Q072 结论需要，将另开 SPEC-xxx）
- /ES margin pool 与 SPX PM pool 的合并讨论（账户结构问题，不在研究范围）

---

## 7. 参考文件

```
task/SPEC-094.md / SPEC-094.1.md          ← Drawdown Overlay 双 sleeve 配置
task/SPEC-098.md                          ← Q042 独立 dashboard
strategy/selector.py:325                  ← is_aftermath() 实现
research/q070/q070_memo_2026-05-13.md     ← Aftermath threshold 维持 28 的结论
research/strategies/ES_puts/backtest.py   ← HV Ladder (V2f) 实现
task/q071_es_q041t1_integration_design_review_2026-05-14.md  ← HV Ladder 整合设计 review
research/q066/q066_memo_2026-05-12.md     ← Co-firing & co-loss 框架原型
research/q064/q064_p1_daily_flags.csv     ← 19y daily VIX/aftermath flags（P1 数据源）
```
