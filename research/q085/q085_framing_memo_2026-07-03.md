# Q085 Framing Memo — 方向性主账本的技术信号 overlay（大规模研究线）

**日期**: 2026-07-03
**PM 批准**: 2026-07-03（"同意是个大规模的研究。同意进入下一步。"）
**性质**: 主策略级研究线。涉及可交易日 68.4% 的多头敞口，规模对标 Q078/Q083，不是 Q084 式快线。

---

## 1. 研究动机（P0 前提检验已完成）

**账本是方向性的**：26 年可交易日中 68.4% 路由到带杠杆多头结构（BCD 1,747 + BPS/BPS_HV 387 = 2,134/3,119），中性 29%，做空 2.6%。而方向输入只有一个三档 ATR 趋势信号——**2/3 的敞口，最低的方向分辨率**。

**Anti-timing 前提已实证**（2026-07-03，NORMAL×BULLISH 格，69 个 IVP-超上限被挡窗口）：
- 被挡窗口最低点 → 下一次放行入场：SPX 中位已涨 +2.97%，p75 +9.54%，max +42.6%；等待中位 123td
- 但 17/69 窗口等待更优（下次入场更低）；且被挡日 fwd-31td 左尾显著更肥（p5 -12.6% vs 放行日 -8.8%）——门有真实尾部保护，净值未知
- **机制修正**：被挡日 VIX 中位 17.3 ≈ 放行日 17.2，权利金并不更富；被挡的代价是价位，不是 vol

## 2. 硬纪律（全程有效，来自 house 档案）

1. **多重检验控制**：全部检验先于数据锁定（本 memo §4-5 即预注册清单）；事实层用 Benjamini-Hochberg FDR **q=0.10** 全 battery（~43 信号 × 2 strata ≈ 86 tests）校正。清单之外临时起意的指标/切点一律无效（per `feedback_stratum_cutpoint_overfit`）。**追加生存条件（2026-07-03 修订）**：幸存信号必须在样本前后两半（Tier 1: 2000-2012 / 2013-2026；Tier 2/3: 自身跨度对半）**效应符号一致**，防单一时代拟合。
2. **事实先于 PnL**（per `feedback_circular_metric_validation`）：条件分布事实不显著的信号不得进入 PnL 模拟。
3. **双标准**（per `feedback_decision_type_governs_significance_standard`）：信号有无信息量 = Alpha 标准（vs 零显著，FDR 后）；槽位是否采纳 = Execution 标准（vs 现状显著优）。
4. **Q082 P9 默认反驳在案**：任何"信号做否决门保护 forward window"的用法承担举证责任；strike 放置与离场管理不在该裁决覆盖范围（当年未测）。
5. 其余照旧：2008 型 Layer-1 筛查、悲观 skew bracket 前置、今日尺度绝对值、exit-day unsmoothed 记账、boundary 类槽位 freq AND ROE 双门槛、kill verdict 外审。
6. **频率边界**：全部信号在**日频收盘**数据上定义（含日频 OHLC）。不引入日内信号——SPEC-030 已结案（日内提前触发率 0%）。

## 3. 数据需求（P1 前置，2026-07-03 已核实可得区间）

- SPX 日频 **OHLC**：✅ 已落盘 `data/q085_spx_ohlc_cache.json`（6,814 行，1999-06 起含 200DMA 预热）
- Tier 2 跨资产（yfinance 已核实）：^VIX3M 2006+ / ^VVIX 2007+ / XLU 1998+ / RSP 2003+ / HYG 2007+ / TLT·IEF 2002+ / DXY 全史 / GLD 2004+ / **^SKEW 1990+ 全史**
- Tier 3 承诺采集：FOMC 会议日历 2000-2026（公开）；CFTC COT ES 净投机（免费 CSV）；AAII 情绪（免费）
- 量价族用 SPY 成交量代理，代理有效性单独标注（per `feedback_proxy_validity_must_match_conclusion`）

## 4. 预注册指标族（**2026-07-03 修订版**——PM 指令：完备性自查，不得以工作量裁剪）

**完备性确认方法**：对照三个来源系统枚举——(a) 学术异象文献的信号族分类（trend/momentum、reversal、seasonality、vol premium、positioning/sentiment、cross-asset）；(b) CTA/practitioner 标准工具箱；(c) 对冲基金系统化常用且在本项目数据预算内可得者。排除项仅允许两种理由：数据不可得（注明采购路径）或 house 已有结案裁决（SPEC-030 日内）。**工作量不是合法排除理由。** PM 可随时提名补充，提名信号在 P1 运行前并入预注册附录。

**Tier 1 = 26y 全史可算；Tier 2 = 自身可得史 ≥15y；Tier 3 = 需数据采集（已承诺采集项标注）。**

| 族 | 信号（预注册精确定义，n=43） | Tier | 文献先验 |
|---|---|---|---|
| **F1 慢频趋势/动量** (8) | 200DMA 上下；50/200 金叉状态；TSMOM 12-1m/3m/6m 符号；Donchian 55td 突破；ADX(14)>25；MACD(12,26,9) 柱符号 | 1 | **高**（Faber 07；MOP 12）。检验对现有 ATR 信号的**增量** |
| **F2 价格结构** (6) | 距 63td/126td 滚动低点 %；摆动支撑距离（局部 low 左右 5 bar 未破）；距 252td 高点 %（George-Hwang 04）；前月高/低突破；隔夜 gap 方向×幅度 | 1 | **中**；strike 放置用途 = 全研究最高先验 |
| **F3 短线均值回归** (6) | RSI(2)（Connors）；RSI(14)；IBS=(C-L)/(H-L)（指数上有记录）；Bollinger %B(20,2)；连续下跌天数 ≥3；5td 收益 z-score | 1 | 低-中；RSI(2)/IBS 在指数日频有可复制记录 |
| **F4 K 线形态（对照组）** (3) | 看涨吞没；20td 低位锤子；三日反转 | 1 | **~零**，陪跑校准假发现率 |
| **F5 波动率结构** (6) | **VRP 代理 = VIX − RV21**（卖权利金最核心的文献信号）；ATR(14) 百分位；VIX 5td Δ；SKEW 指数水平/Δ（1990+ 全史）；VIX/VIX3M 比（2006+）；VVIX 百分位（2007+） | 1/2 | **高**（VRP 文献充分）；与现有 IVR/IVP 门的**增量**是检验目标 |
| **F6 跨资产 risk-on/off** (6) | XLU/SPY 63td 相对强度（1999+）；RSP/SPY 63td（2003+，兼作广度代理）；TLT 21td 动量（2002+）；HYG/IEF 63td（2007+）；DXY 63td 动量（全史）；GLD 63td 动量（2004+） | 1/2 | 中（defensive rotation / credit 有记录） |
| **F7 日历/事件** (5) | 月末月初窗口（turn-of-month，有记录）；OpEx 周；FOMC 前 24h drift（Lucca-Moench 15，需 FOMC 日历——公开可得，承诺采集）；月份 dummy、星期 dummy（对照） | 1/3 | turn-of-month 与 FOMC drift 有记录 |
| **F8 持仓/情绪** (3) | CFTC COT ES 净投机头寸百分位（2006+，免费 CSV，**承诺采集**）；AAII bull-bear spread（1987+，免费，**承诺采集**）；CBOE equity P/C ratio（可得性 P1 核实） | 3 | 中-低（慢频反向指标有记录） |
| **F9 市场内部广度** (0 active) | %>200DMA、A-D line 等需付费源（Norgate 级）。当前用 RSP/SPY（F6）代理；**若 P1 幸存信号提示广度维度有价值，向 PM 提数据采购**——这是数据约束，非工作量裁剪 | 3 | 中 |

**明示排除项（理由留档）**：日内/盘中信号（SPEC-030 结案，日内提前触发率 0%）；GEX/期权流（Schwab 链数据 2026 起，历史不足以检验）；付费广度数据（F9，采购路径已注明，条件性开启）。

## 5. 决策槽位（信号只对具体槽位负责）

| 槽位 | 问题 | 采纳标准（Execution 层） |
|---|---|---|
| **S1 strike 放置** | BPS 短腿放在结构支撑下方 vs 固定 delta：等权利金比较下 breach 率/PnL 是否改善 | 悲观 bracket 下今日尺度净 ≥$2,000/yr 且 breach 率不升 |
| **S2 被挡窗口入场** | Arm A：IVP 上限外 0.5x 规模入场净值（boundary → freq AND ROE 双门槛）；Arm B：窗口内条件选日（先事实层，尾部无改善即斩） | 同上 + 双门槛 |
| **S3 放行窗口择日** | 合格窗口内信号选日 vs 全取 | 净 ≥$2,000/yr |
| **S4 BCD 技术离场** | 方向性离场 overlay vs 机械 21 DTE（+0.4 delta 持仓的方向管理） | 净 ≥$2,000/yr 且 worst-trade/CVaR 不恶化 |
| **S5 规模调节** | 信号驱动 0.5x/1x | 净 ≥$2,000/yr |

**优先序**（PM 认可的先验排序）：S1 → S2 → F1 增量检验（廉价，随 P1 出）→ S4 → S3/S5。

## 6. 流水线

- **P1 事实层（本研究最大单体）**：OHLC 数据准备 → 全指标族 × 相关 strata 的条件 fwd-31td 收益/尾部分布 vs 无条件，KS + 分位差，BH-FDR q=0.10 → 幸存者表。**全 battery 一次跑完再看结果**，不逐个窥探。
- **P2+ 槽位层**：仅幸存信号进入对应槽位的反事实 PnL（复用 Q082/Q084 sim 基建 + BPS synth）；每槽位独立 verdict，可部分采纳。
- **G-review**：事实层完成后一次 packet；任何采纳提案前一次；kill 需外审。
- **采纳路径**：任何采纳 = selector/catalog 代码改动 → SPEC + dev handoff，研究侧不碰生产代码。

## 7. 预注册 kill gates（研究线级）

- **K1**：事实层后零幸存信号（FDR q=0.10）→ 研究线 DOCUMENT 收尾（"技术 overlay 无信息量"本身是有价值的档案，防未来重提）
- **K2**：幸存信号存在但全部槽位 Execution 层不过 → DOCUMENT，信号记录为"有信息量但不可变现"
- **K3**：任何单槽位悲观 bracket 净 <$2,000/yr → 该槽位关闭，不因"其他槽位过了"豁免

---

## 修订日志

- **2026-07-03（PM 指令）**：§4 指标族由 5 族 ~14 信号扩充为 9 族 43 信号（Tier 1/2/3 按已核实数据可得性分层）；§2 追加 IS/OOS 符号一致性生存条件；§3 更新已核实数据区间与承诺采集项。PM 指令原文要点："不要因为怕工作量大而放弃扫描其他可能的信号"——与 `feedback_research_thoroughness` 一致，排除项仅限数据不可得或 house 结案裁决。
- **2026-07-03**：Delta 对冲问题当日评估完毕，DOCUMENT 留档不立项（见 `q085_delta_hedge_assessment_2026-07-03.md`）：账本 52/48 方向/carry 分割，carry 半边 90% 胜率真实存在，但对冲版每占用美元回报降为 1/3-1/4 且运营不兼容；方向依赖的削减走结构路由 + S5 规模条件化。
