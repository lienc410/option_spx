# Q088 Track 1 — 修订史考古首份清单（2026-07-05）

**方法**: git log 逐文件修订计数 + 主题时间线提取 + 现状 grep 核实。修订最频文件：selector.py（20 次）、engine.py（20）、sleeve_governance.py（14）、ES backtest（10）。task/ 累计 212 个 SPEC。

## 金矿发现：2026-05-08 已有一次对齐审计，其"仅注记"项两个月后全部复发

Commit `1b1c080`（5/8）当时就发现并**仅注记**："annotate ES stop/BP inconsistencies for decision"。其中 ES 止损失配后来被 A3 当"新发现"重审（SPEC-121 才收敛）；**ES sizing 失配至今活着**（见下）。教训：**"注记待决"是死信机制**——没有追踪就等于没发现。

## 活失配（立即行动项）：ES 规模三层口径 → 立项 A5 对账审计

| 层 | 口径 | 现状 |
|---|---|---|
| P1 回测 | BP target 10%/仓 | 注记比较基准（已过时相位） |
| V2f 晋升回测 | 固定 5 槽 × 3 张 | 已验证口径 |
| **Live（server.py:5014）** | **单槽位 + NLV 20% BP 上限门** | 现行 |

方向初判：live 单槽位使实际并发**低于**已验证 V2f（保守方向），但 20% 上限与两个回测口径都不同源。A5 = 事实对账（live 实际下单张数惯例、三层风险等效换算）→ verdict（统一到何口径）→ 走流程。5/8 注记的"live 2× 回测"表述本身也不精确——这正是口径混乱的症状。

## 修订振荡指数表（初版，考古继续扩充）

| 话题 | 修订次数 | 时间线 | 现状 |
|---|---|---|---|
| **ES sizing 口径** | ≥2 + 注记搁置 | P1→V2f→live 三层分叉，5/8 注记 | **活失配 → A5** |
| 定价约定 | 3（本月） | BS-flat→vendor→moff→T-conv | 已收敛（119/120），断言待 dev |
| ES 止损 | ≥3 | bot 3×（086）→ V2f 15×（未调和）→ 10×（121） | 已收敛；5/8 已知未决前科 |
| IVP 门系列 | ≥4 | 048~055 → Q015 NNB → 049 撤销 → 105/105-v2 booster → Q083/A1 | A1 已审现状；模式=门叠门 |
| Aftermath 系列 | ≥5 | 064→066→071→075/076→118 边界修 | 边界已修；系列整体未复核 |
| Sleeve caps | ≥5 | 103→104→108→108.1→084 lift | Q078 时代校准；NLV=100k 已修 |
| BP/NLV 分母 | ≥4 | 103 修→48f0064→798aaaa→118 fallback | 收敛中 |
| Profit target | ≥2 | 50%→60%，曾 catalog/bot/frontend 三处不一致 | 已收敛；根因=多处镜像 |
| Matrix cell 补丁 | 多次 | 060/064/071/113 | Track 2 输入 |
| SPEC-111 边界 | 新 | 手动单绕过（BCD packet v2 发现） | 待 PM 定治理边界 |

## 三类根因 → 制度化修复方向

1. **多处镜像无单一真值**（profit target / stop / sizing）→ 单源化 + 一致性断言测试（121 的 EsShortPutParams 模式推广）
2. **层间约定无契约**（定价 day-count / offsets 口径）→ SPEC-119 convention-tag 断言模式推广
3. **"注记搁置"无追踪**（5/8 审计两项全部复发）→ 制度：**禁止裸注记**——搁置项必须入 `task/DEFERRED.md` 且 heartbeat 类周期性曝光，或当场开 SPEC

## 交 dev 的断言清单（v1）

pricing convention tag 断言（120 v2 已列）；profit-target catalog↔bot↔frontend 一致性测试；matrix 展示↔行为一致性测试（SPEC-060 案例通用化）；ES sizing 单源断言（待 A5 verdict）；SPEC-111 手动单边界提示（待 PM）；DEFERRED.md 机制。
