# Q087 Program Charter — Fable 时代全系统优化迭代（2026-07-05）

**PM 指令**: "在 Fable 模型下，把所有的工作流/项目方案/代码全部优化迭代一遍。"
**性质**: 程序（program），非单一研究课题。原 Q087（自适应审计）并入为 Track A。
**不动产**: 实盘策略照常运行；SPEC-116 paper 观察不受干扰；任何生产行为变更走既有 SPEC+guard 流程。禁止 big-bang 重写。

## 0. 三条设计原则

1. **先审计后重写**：每个域先做清单+分诊（影响 × 风险 × 现状证据），按边际经济价值排序改造，不为美观重写（per `feedback_economic_optimality_over_simplicity`——工程量不是约束，但价值排序是纪律）。
2. **Guard 分级**：行为中性重构 → bit-identical 断言（SPEC-116 AC-6 模式）；行为变更 → paper-first / 分时代证据 + 外审；参数变更 → Track A 审计流程 + PM ratify。
3. **Fable 红利显式化**：外审已从"奢侈品"变成"每个 verdict 的例行程序"（subagent 常驻）；大规模 battery、真实数据校准、全量代码审计都已可行——工作流按这个能力水位重设，而不是沿用旧的人力假设。

## 1. 五条 Track 与分工

| Track | 内容 | 主责 | 审 | 产出物 |
|---|---|---|---|---|
| **A 策略参数自适应审计**（原 Q087） | 每个 gate/参数过"时代镜头"：IVP 双门窗宽、HV 0.5x 折扣、SPEC-079 filter、BPS NNB 窄带（43-55）、spell throttle、IC delta 档位；全部历史 kill 档案分时代复查（Q084 calendar 首个）；FOMC-cycle 线索评估 | Quant | 外审 agent 每 verdict | 逐参数 verdict + 改动走 SPEC |
| **B 回测/定价基础设施**（并入 Q086） | BS-flat@VIX 定价偏差全面审计（真实链校准回灌）；**统一定价库**（生产 pricer 与研究侧 ≥3 份 BS 复制品去重）；engine 接链校准钩子；策略指标包标准化实现 | Quant 设计 + Dev 实现 | 外审方法学 | 校准报告 + 共享库 SPEC |
| **C 生产代码健康** | 全代码审计：server.py（~4.5k 行）分拆、测试覆盖地图、已知潜伏 bug 清册（如 Greeks 跨券商乘数错配）、重复/死代码、类型与错误处理 | Dev | Quant 抽查行为等价 | 分诊清册 + 重构 SPEC 序列（全部 bit-identical guard） |
| **D 数据与运维** | launchd 任务清单（现 ~10 个）统一心跳/失败告警；数据文件谱系（caches/ledgers/chains）与保留策略；oldair 部署健康检查脚本化；token/auth 故障分类自动化（沿用三类故障档案） | Dev | — | 运维清册 + 监控 SPEC |
| **E 工作流编纂** | 把散在 memory 的方法学沉淀为版本化 `METHODOLOGY.md`（流程规则，非参数镜像——数值仍以代码为真值）；research→G-review→外审→SPEC→handoff→verify 的模板化；**agent 分工架构文档**（Quant 主会话 / 常驻外审 subagent / Dev / Planner 的接口约定：task/ 交接、packet 规范、verdict 等级）；PM 决策权矩阵（什么必须 ratify、什么自主） | Quant | PM ratify | METHODOLOGY.md + 模板集 |

## 2. 推进结构

**Phase 0 — 全域清单与分诊（先行，1-2 个工作会话）**
- Quant 出：A 域参数清单（含时代敏感性初判）、历史 verdict 方法学版本标注表
- Dev 出：C 域代码清册（模块/LOC/覆盖率/已知 bug/重复度）、D 域任务与数据谱系
- 汇总为**统一分诊板**（影响 × 风险 × 工作量三轴打分）→ **PM checkpoint #1：ratify 优先级排序**

**Phase 1+ — 按分诊板并行推进**
- A、B 由 Quant 串行主导（同一时间一个 active 审计对象，防质量稀释）；C、D 由 Dev 并行消化（bit-identical 类不需要排队等 PM）
- E 随程序持续沉淀，每次流程改进即时入档
- 节奏：每完成一个审计对象/重构包 → 例行外审 → 该项 verdict 入 program board（Planner 侧归档）
- **PM checkpoint 节律**：Phase 0 后一次（定优先级）；此后每完成一个"行为变更类" SPEC 前一次（ratify）；程序级复盘每 ~2 周一次

**默认优先序建议（待 PM checkpoint #1 确认）**：Phase 0 → A（直接兑现自适应哲学，已有明确嫌疑清单）→ B（决定所有研究结论的可信度）→ C（风险清除）→ D（韧性）→ E（贯穿）。

## 3. 角色边界（延续现行 + 显式化）

- **PM**: 优先级、风险姿态、行为变更 ratify、资金决策
- **Quant（本会话）**: A/B/E 主责、全部 SPEC 起草、Phase 0 分诊板、program 状态汇报
- **Dev**: C/D 主责、全部生产代码实施、部署与首日验证回报
- **外审 subagent（常驻）**: 每个 kill/adopt verdict、方法学变更、分诊板抽查
- **Planner**: program board 维护、归档、跨会话状态锚点
