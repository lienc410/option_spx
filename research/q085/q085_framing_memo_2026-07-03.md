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

1. **多重检验控制**：全部检验先于数据锁定（本 memo §4-5 即预注册清单）；事实层用 Benjamini-Hochberg FDR **q=0.10** 全 battery 校正。清单之外临时起意的指标/切点一律无效（per `feedback_stratum_cutpoint_overfit`）。
2. **事实先于 PnL**（per `feedback_circular_metric_validation`）：条件分布事实不显著的信号不得进入 PnL 模拟。
3. **双标准**（per `feedback_decision_type_governs_significance_standard`）：信号有无信息量 = Alpha 标准（vs 零显著，FDR 后）；槽位是否采纳 = Execution 标准（vs 现状显著优）。
4. **Q082 P9 默认反驳在案**：任何"信号做否决门保护 forward window"的用法承担举证责任；strike 放置与离场管理不在该裁决覆盖范围（当年未测）。
5. 其余照旧：2008 型 Layer-1 筛查、悲观 skew bracket 前置、今日尺度绝对值、exit-day unsmoothed 记账、boundary 类槽位 freq AND ROE 双门槛、kill verdict 外审。
6. **频率边界**：全部信号在**日频收盘**数据上定义（含日频 OHLC）。不引入日内信号——SPEC-030 已结案（日内提前触发率 0%）。

## 3. 数据需求（P1 前置）

- SPX 日频 **OHLC**（现有 cache 只有 close；K 线形态、摆动低点、支撑位需要 O/H/L）：yfinance ^GSPC 2000-2026，落盘 `data/q085_spx_ohlc_cache.json`
- 量价族用 SPY 成交量为代理（SPX 指数无原生成交量），单独标注代理有效性风险（per `feedback_proxy_validity_must_match_conclusion`）

## 4. 预注册指标族（有限清单，含文献先验）

| 族 | 指标（精确定义） | 文献先验 |
|---|---|---|
| **F1 慢频趋势** | (a) close vs 200DMA 二值；(b) 12-1 月时序动量符号 | **高**（Faber 2007；MOP 2012）。但检验目标是**对现有 ATR 趋势信号的增量**，不是 standalone |
| **F2 价格结构** | (a) 63td/126td 滚动最低价距离（%）；(b) 摆动低点：局部 low 且左右各 5 bar 未破，取最近者为支撑位，算 close 距支撑 %；(c) dist_30d_high（已存在于 SPEC-079 特征） | **中**（择时弱；作为"跌到哪会停"的 strike 放置条件未被充分检验——本研究先验最高的用法） |
| **F3 均值回归** | (a) RSI(14) <30/>70 二值；(b) close 距 20DMA 的 ATR 倍数 | 低-中（日频指数上不稳定） |
| **F4 K 线形态** | 固定 3 个：看涨吞没、锤子线于 20td 低位、三日反转（低-低-高收） | **~零**（系统化文献无可复制记录）。作为对照组陪跑，预期死于事实层 |
| **F5 量价** | SPY 量 20td z-score；equity put/call ratio（如可得） | 低（指数层面被 IV 张成，Q085 前讨论已判冗余先验），一次性检验 |

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
