# Q088 T2 开篇 — 逐格证据强度表（2026-07-06）

**用途**: T2 Q2.4（修补 vs 重构）的判定地基——每个实盘格的当前路由到底靠什么证据撑着。
**口径注记（重要）**: ① CALIB 列为 pre-tconv 严苛口径（compare CSV 未按 365/252 修正重建）——**评级是下界**，tconv 后 C 格普遍上移（主 BCD 格 $5.4k→$26.8k）；正式评级等例行 tconv 重跑（已排）。② NORMAL|LOW|BULLISH 行为日 574 天 = 重生成缓存用**现行代码**回放历史（carve 的历史足迹），其 CALIB 应看 carve 单列行（tconv +$9.4k）而非全格行。

## 评级分布（19 个行为格）

| 级 | 定义 | 格数 | 构成 |
|---|---|---|---|
| **B 校准稳健** | CALIB>0 且 PESS≈≥0 | **10** | IC/HV 特许经营权全部主力格——框架的骨架无恙 |
| **C 薄边际** | CALIB>0、PESS<0 | 4 | 主 BCD 格（tconv 后趋 B-）、NNB BPS（唯一有实现流水的格）、NORMAL|HIGH|BEARISH IC、HIGH_VOL|NEUTRAL|NEUTRAL |
| **D 校准为负** | CALIB≤0 | 5 | 全部小 n 或已知项（LOW_VOL|NEUTRAL|BULLISH BCD、NORMAL|NEUTRAL|NEUTRAL IC、HIGH_VOL|LOW 两小格、NORMAL|LOW|BULLISH 全格行——carve 子集除外） |

## T2 最重要的一个事实

**整个矩阵 26 年验证 vs 实盘实现流水 = 5 笔**（全在 NNB BPS 一格）。证据金字塔极度模型侧重：live 证据覆盖 19 格中的 2 格（NNB 已实现 + carve 未实现持仓）。含义：
1. "框架 vs 补丁"的判定在未来数年内主要仍靠模型证据——**shadow/paper 证据流（skew monitor、S2-BPS、BCD shadow）是唯一能系统性升级证据等级的机制**，其价值高于任何新回测
2. 框架焦虑应按证据等级分层：B 格（10 个骨架格）无需动；C/D 格的处置全部已在既有轨道上（BCD 家族复审、Q088 T2 清单、DEFERRED）
3. **T2 定量部分维持条件挂起是正确的**——在证据等级普遍为"模型"的现状下重构框架 = 用一个模型换另一个模型

## 下一步（T2 定性余项）

信号维度取舍（Q2.1：IVR/IVP 合成问题）与格粒度 vs 数据分辨率（Q2.2：19 格中 8 格行为日 <100）的分析随 tconv 重跑后一并出，不阻塞任何在跑事项。
