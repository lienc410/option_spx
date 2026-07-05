# Q087 P0 — 历史 verdict 方法学版本标注表（2026-07-05）

**用途**: 标注每个支撑现行行为的研究结论用的是哪一代方法学，据此排定"用新协议重审"的优先级。新协议基线 = studentized 推断 / 真实链校准+成本 / 分时代呈现 / vs-现状基准（2026-07-04 后为默认）。

| Verdict | 支撑的现行行为 | 定价 | 推断 | 时代呈现 | 基准 | 重审优先级 |
|---|---|---|---|---|---|---|
| **原始 26y 矩阵回测**（Sharpe 1.43，SPEC-010~023 时代） | **整个 CANONICAL_MATRIX 路由** | engine BS（sigma 来源需核） | 无显著性框架 | 全样本聚合 | 无 | **P1 — 全系统的地基**；Track B 定价审计首个对象 |
| Q082（BCD 137 笔 + SPEC-111 校准） | BCD 全部格 + 现金 cap 参数 | **BS-flat@VIX synth**（已知高估 credit 类；BCD 为 debit 结构方向需单独定量） | raw | 聚合 | vs QQQ | **P1** — Track B 校准回灌首批 |
| Q083/SPEC-113（carve） | NORMAL×LOW×BULL×VIX<18 → BCD 实盘路由 | BS-flat + skew bracket（bracket 锚也是 VIX-flat） | raw | P16 补了 lockout 分时代 | vs 无 | **P2** — 有 bracket 缓冲但锚偏 |
| Q084（calendar kill） | NORMAL×LOW×NEUTRAL 维持 wait | BS-flat | raw | **全样本聚合**（PM 已点名复查） | vs 零 | **P2** — 分时代复查即可，工作量小 |
| Q071（ES HV Ladder promote） | **实盘 /ES 策略全部参数** | 需核（futures options 定价来源） | raw | 校准期偏 2020+ 高波动时代 | — | **P1** — 实盘资金 + 校准时代单一 |
| Q075（Layer-N 替代 kill） | 维持现状（cash 终点） | 混合 | raw | 聚合 | 实现成本排序已纠 | P3 |
| Q078（anchored cadence/portfolio） | sleeve caps 数值来源 | engine | raw | 聚合 | — | P2（与 caps 审计联动） |
| Q080（Sharpe smoothing） | 报告口径规则 | — | — | — | — | 无需重审（方法学本身） |
| Q081（cash-bound 框架） | $37k 基线/机会成本 10% | — | — | 点时估计（现金已 $61k） | — | P3 — 基线数字随 8/1 SPEC-111 复审一起刷新 |
| Q085（F3/S2-BPS） | SPEC-116 paper sleeve | **新协议原生** | studentized | 分时代 | vs 现状 | 无需重审（新基线的定义者） |

## 重审执行规则

1. P1 三项（矩阵地基 / Q082 / Q071）先走 **Track B 定价校准**（同一把尺子重估），再进 Track A 时代镜头——顺序不能反，否则时代结论建立在偏定价上。
2. 重审≠推翻默认：目标是"每个实盘行为背后至少有一个新协议口径的数字"；结论不变最好，变了走 SPEC。
3. 每项重审 verdict 照常外审。
