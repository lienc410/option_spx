# HC ↔ MC 双环境同步协议 v3

## 1. 环境定义与权威域

| 环境 | 权威域 | 说明 |
|------|--------|------|
| **HC** | 源代码、回测执行、最终知识镜像 | Claude 所在环境；代码和回测数字以HC为准；**项目完成时HC持有完整、正确的全部知识** |
| **MC** | 策略决策、参数拍板、研究方向 | 独立研究环境；参数值和SPEC APPROVED/REJECTED 以MC（PM）为准 |

**根本原则**：数字和代码 → HC权威；决策和研究方向 → MC权威。冲突时按此原则解决，不拖延。

**最终目标**：项目完成时，HC 持有：
- 完整策略逻辑（含信号/入场/出场/overlay/shock）
- 所有有效参数的最终值
- 完整研究结论和实验摘要
- 当前推荐生产配置及理由
- 所有已知局限性和未解决问题

---

## 2. Master Documents 体系

HC 必须持续维护以下 master 文件（不可只靠 delta 积累）：

| 文件 | 路径 | 内容 | 由谁负责维护 |
|------|------|------|-------------|
| 参数主表 | `sync/PARAM_MASTER.md` | 所有有效参数、最终值、来源SPEC | HC（MC同步后更新）|
| 开放问题 | `sync/open_questions.md` | 未解决问题、阻塞项、待验证假设 | 双端都可更新 |
| 同步日志 | `sync/SYNC_LOG.md` | 每次同步记录、冲突标注、镜像健康度 | HC |

HC 的 `doc/` 目录承担以下角色（利用现有文件，不新建）：

| 角色 | 对应现有文件 |
|------|------------|
| strategy_master | `doc/strategy_status_YYYY-MM-DD.md`（最新版）|
| experiment_registry | `doc/research_notes.md` + delta 文件 |
| implementation_status | `task/` 目录下所有 SPEC 文件 |
| production_recommended_config | `sync/PARAM_MASTER.md` 最末节 |

---

## 3. 信息流约束

```
HC ──────(MD / 小数据 / 小源文件)──────► MC

HC ◄──(iPhone扫描 → 粘贴 → HC清洗 → 整合入 master docs)── MC
```

| 方向 | 可传内容 | 不可传内容 |
|------|----------|-----------|
| HC → MC | MD文件、小数据(<1MB)、小源文件(<200行)、OCR清洗版、review notes | — |
| MC → HC | OCR扫描的MD文件（间接）| 原始数据、详细时间序列、完整codebase |

---

## 4. 同步节拍（6天周期）

```
Day 1-3（MC工作期）  →  Day 3末：MC产出"MC Handoff包"（scan-friendly格式）
Day 4-6（HC工作期）  →  Day 4初：HC消化并整合入 master docs
                     →  Day 6末：HC产出"HC Return包"给下周MC
```

**强制规则**：切换工作环境前，必须完成当前环境的同步包。不允许跨周期积压 delta。

**Weekly Mirror Check**（每周一次）：HC 评估 master docs 健康度，写入 SYNC_LOG：
- 🟢 Green：与MC实质同步，可用
- 🟡 Yellow：有已知小滞后，仍可用
- 🔴 Red：实质过期，不可信赖

---

## 5. MC → HC：Handoff 包

### 5.1 MC端写扫描包（scan-friendly格式）

**文件命名**：MC端本地 `mc_handoff_YYYYMMDD.md`

**OCR友好规范**（强制）：
- 每行 ≤ 45个中文字符
- **禁止 Markdown 表格**，改用标签+缩进列表
- 数字单独占行，前后有标签
- 禁用特殊符号：`→ ← ≥ ≤ × ÷ ±`，改用文字
- 每段用`【标签】`明确分区
- 每个参数变更单独写四行：参数名/旧值/新值/原因

**MC Handoff 模板**：

```
# MC Handoff YYYY-MM-DD

上次同步日期 YYYY-MM-DD
本次MC工作期 YYYY-MM-DD 到 YYYY-MM-DD

【本期摘要】
主要完成内容（不超过3条）
第一条 xxx
第二条 xxx

【当前状态快照】
当前推荐生产配置 EXP-full，overlay_mode=active
当前最高优先阻塞 xxx

【参数变更】
（每个变更单独四行）

参数名 overlay_mode
旧值 disabled
新值 active
来源SPEC SPEC-026，原因 EXP-full验证通过

参数名 bearish_persistence_days
旧值 3
新值 1
来源SPEC SPEC-020，原因 RS-020-2驳回persistence filter

【SPEC决策】

SPEC编号 SPEC-XXX
新状态 APPROVED
PM决策日期 YYYY-MM-DD
备注 一句话

【研究发现】

发现编号 F001
内容 ATR标准化后假BULLISH减少约18%
依据 4路ablation
相关SPEC SPEC-020

【策略逻辑变更】

变更项 趋势翻转触发条件
旧逻辑 单日BEARISH即触发
新逻辑 xxx

【开放问题更新】

问题编号 Q001
状态 已解决
结论 xxx

问题编号 Q002
状态 新增
内容 xxx

【Master Doc 影响清单】
（每项 yes/no，yes的才需要HC更新）

PARAM_MASTER需要更新 yes
open_questions需要更新 yes
strategy_status需要更新 no
experiment_registry需要更新 no

【HC指令】
（对本周期HC Claude的具体任务）

指令1 实现SPEC-020 ATR-normalized entry gate
指令2 将overlay_mode默认值改为active

【不要推断的项目】
（HC不应自行解读，必须等MC确认）

项目1 xxx

【下周MC计划】

计划1 Vol Persistence Model前置研究
```

### 5.2 HC清洗OCR

收到用户粘贴的OCR原文后，**分三层输出**，不混在一起：

**层1 — 清洗版（Cleaned）**
- 修正OCR错误：`0/O`、`1/l/I`、`5/S` 混淆
- 恢复标签结构和列表缩进
- 无法确认的字符标 `[OCR?原文]`，不擅自推断
- 保存至 `sync/mc_to_hc/mc_clean_YYYYMMDD.md`

**层2 — 不确定项汇总（Uncertainty Flags）**

在清洗版文件尾附：

```markdown
## Uncertainty Flags

| 项目 | 原始OCR文本 | HC读取值 | 置信度 | 需MC确认 |
|------|------------|---------|--------|---------|
| overlay_mode新值 | "actlve" | active | 高 | 建议确认 |
| 某参数数值 | "0.O25" | 0.025 | 中 | 需MC确认 |
```

**数字交叉校验**（最高优先级）：对照 `sync/PARAM_MASTER.md` 中的"当前值"核对每个参数的旧值是否匹配。若旧值不匹配，标 `[OCR?核对旧值]`，不采用新值。

**层3 — Review Notes（可选，仅当MC handoff请求时）**
- 逻辑评论、风险评估、文档质量意见
- 存至 `sync/mc_to_hc/mc_review_YYYYMMDD.md`（与清洗版分开）

### 5.3 HC整合

清洗确认后，HC Claude 按 Master Doc 影响清单执行：

1. **更新 `sync/PARAM_MASTER.md`**：写入参数变更，递增MC版本号
2. **更新 `doc/strategy_status_YYYYMMDD.md`**（最新版）：写入策略逻辑变更和研究发现
3. **更新 `sync/open_questions.md`**：关闭已解决问题，添加新问题
4. **更新 SPEC 状态**：`task/SPEC-XXX.md` 写入 APPROVED/REJECTED
5. **执行HC指令**：按 MC 指令列表逐项实施
6. **更新 SYNC_LOG + Mirror健康度评级**

---

## 6. HC → MC：Return 包

**文件**：`sync/hc_to_mc/hc_return_YYYYMMDD.md`

```markdown
# HC Return Pack：YYYY-MM-DD

上次同步：YYYY-MM-DD
本次HC工作期：YYYY-MM-DD 到 YYYY-MM-DD

---

## § 1 OCR清洗输出

清洗文件：mc_clean_YYYYMMDD.md
OCR问题：X处（Y处已修正，Z处待确认）
不确定项：见 Uncertainty Flags 表（附件）

---

## § 2 SPEC状态变更

| SPEC | 状态 | 关键结论 |
|------|------|---------|
| SPEC-XXX | DONE | |

---

## § 3 回测结论

（关键数字，3-5条）

---

## § 4 参数主表更新摘要

本周期HC修改的参数：
（若无变更，写"无"）

| 参数 | 旧值 | 新值 | 原因 |
|------|------|------|------|

---

## § 5 Consolidation Suggestions

（HC建议MC更新的canonical文档，不代替MC决定）

建议更新 strategy_master：xxx
建议更新 experiment_registry：xxx

---

## § 6 开放问题更新

新增问题：
已关闭问题：

---

## § 7 需MC决策

1. 问题描述 — 选项A / 选项B — HC建议：A，理由：xxx

---

## § 8 下周HC计划

---

## § 9 Mirror 健康度

| Master Doc | 状态 | 备注 |
|------------|------|------|
| PARAM_MASTER | 🟢 | 与MC同步至YYYY-MM-DD |
| open_questions | 🟢 | |
| strategy_status | 🟡 | 待SPEC-020完成后更新 |
| SPEC状态汇总 | 🟢 | |

---

## § 10 附件

[列出附件文件名]
```

---

## 7. 冲突处理

| 冲突类型 | 处理规则 |
|---------|---------|
| 参数值冲突 | MC（PM决策）优先；HC更新PARAM_MASTER |
| SPEC APPROVED/REJECTED 冲突 | MC优先；HC不能自行 APPROVED |
| 代码实现冲突 | HC权威（HC持有源码）|
| 回测数字冲突 | HC权威；差异在 research_notes 中标注两套数字并说明原因 |
| 命名冲突 | MC canonical命名优先；HC更新mirror文档采用canonical名 |

冲突标注格式：SYNC_LOG 中标 `[CONFLICT]`，下一个HC Return包的§7请PM裁决。

---

## 8. 项目完成：Final Merge

### Step 1：HC发全量包（Final）
- 附件：完整 `PARAM_MASTER.md`、最新 `strategy_status`、`open_questions`
- 正文：所有SPEC状态汇总、源码模块清单（含最后修改日期）

### Step 2：MC扫描回传确认包（Final）
- 确认所有参数值是否与MC端记录一致
- 补充MC端有但HC端缺失的研究发现
- 对所有 open questions 给出最终答案

### Step 3：HC最终整合
- 将MC补充内容写入master docs
- git tag 标注 `FINAL`
- Mirror健康度全项 🟢

---

## 9. 小源文件同步标准（HC → MC）

满足全部条件才可附上源文件：

- 单文件 ≤ 200行
- 无新增外部依赖
- 不含密钥/配置
- 独立可读模块

适合：`signals/*.py`、`strategy/catalog.py`、`backtest/prototype/*.py`

不适合：`backtest/engine.py`、有复杂依赖链的模块

---

## 10. 目录结构

```
sync/
├── SYNC_LOG.md                     # 同步总日志 + Mirror健康度
├── PARAM_MASTER.md                 # 参数主表（双端锚点）
├── open_questions.md               # 开放问题追踪
├── hc_to_mc/
│   └── hc_return_YYYYMMDD.md
└── mc_to_hc/
    ├── mc_raw_YYYYMMDD.md          # OCR原文（用户粘贴）
    ├── mc_clean_YYYYMMDD.md        # HC清洗版（含Uncertainty Flags）
    └── mc_review_YYYYMMDD.md       # HC review notes（可选）
```

---

## 11. 参考案例

- Delta文档格式：`doc/clean_strategy_status_delta_2026-03-30_to_2026-04-02.md`
- OCR清洗参考：`doc/clean_research_notes_delta_2026-04-01.md`
- OAI版本参考：`doc/OAI_sync_protocol/`（HC_MC_SYNC_PROTOCOL / MC_HANDOFF_TEMPLATE / HC_RETURN_TEMPLATE）
