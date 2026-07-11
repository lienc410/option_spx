# Q095 P5 Framing Memo — 供需/流动性信号家族（预注册，待 PM ratify）

**Date**: 2026-07-11 · **Status**: **RATIFIED（PM 2026-07-11）**；A 组待数据采集（breadth/PCR 无本地历史源，见执行注记），期限结构维度可先行；B 组挂 SPEC-132 无需启动动作

## 假设（PM 2026-07-11 补充）

账本本质是杠杆看多（P1：亏损侧近乎纯 delta），而标的涨跌由供需/流动性驱动——该层信号未系统挖掘。若有信息量，挂载点 = 敞口决定层（与 P2 分类器同槽位赛马），不另设 gate。

## 已有覆盖（不复议）

S2 缩量 null（Q090，PM 最强信念已被最干净否定）；S3 持仓墙 OPEN（SPEC-132 管道积累中，n≥60）；F3 短线超卖注册线索（Q085）。

## 数据可得性分层（决定验证路径）

**A 组（可回测，26y 免费）**：breadth（A/D line、新高新低）、SPX/CBOE put-call ratio、VIX 期限结构扩展维度（vix9d/vix/vix3m 曲率）。预注册 ≤6 个信号形态后**锁死**（防 Q090 的 18 组合选择算术，P(max|t|)≈30% 教训）；alpha 标准：studentized、BH-FDR q=0.10、era 分层、事实层（forward 分布差）先于 PnL。
**B 组（forward-only）**：GEX/dealer gamma、持仓墙动态。历史链数据采购已排除（CBOE DataShop 流程过重）；走 SPEC-132 证据流管道（与 S3 同池，自家 chain archive 2026-05 起），验证周期以月计，**不设短期交付预期**。

## 杀标（PM ratify 对象）

| # | 杀标 | 阈值 |
|---|---|---|
| K1 | A 组事实层 | 6 形态 FDR 后零幸存 → A 组 CLOSED-NULL（与 Q090 S2 同框归档） |
| K2 | 幸存信号槽位化 | 与 P2 幸存分类器 head-to-head 同框赛马（同一预注册窗口），敞口槽位只取一名；输者归档不叠加 | 
| K3 | B 组 | 仅当 SPEC-132 进度条达 n 门槛才开分析，本 memo 不预支结论 |

## 不在范围

0DTE 流量/MOC imbalance（数据不可得）；个股/板块 breadth 精细化（工程量与 SPX 单标的账本不匹配——此为数据成本判断非工作量畏惧，若 A 组粗粒度 breadth 幸存可升级）。
