# Handoff → DD Overlay 页 UI 审阅：2026-07 研究轮的事实层更新

**From**: Quant Researcher（2026-07-12）
**To**: UI 工程师（DD Overlay `/q042` 页审阅会话）
**背景**: 2026-07-07 协同审计 + Q093 P1/P2 刚结束，页面上有若干"研究已翻案但显示层还是旧叙事"的点。你今天 `3d20f75` 那批（put-spread 错标 / 共用结构块 / 结算仓冒充活仓 / MA10 Loading）**已收到，不在本页重复**。以下是研究侧新增的四组事实 + 显示层含义。
**原则**: 结构参数（strike/DTE/sizing）以代码为真值，本页不镜像（`feedback_no_param_mirror_docs`）；本页只固化研究 verdict 类事实。

---

## 1. F3 联合闸门：从死值变活，历史日志不能当真数据画

- 审计实锤：部署至今 gate log **44/44 行 `main_bp_pct=0.0`** 是 dead gate（读了一个生产端从来没人写的字段），不是"主策略真的零占用"。SPEC-094.2 修复后 `log_gate` 新增 `bp_source` 字段（`strategy/q042_gate.py:96`）区分真 0 / 死 0。
- **显示层含义**：任何基于 `data/q042_gate_log.jsonl`（old Air）历史行的图表/统计，修复日之前的行必须排除或标注 "pre-fix dead-gate"；不要画成"闸门历史上从未 binding"的叙事。`bp_source` 缺失 = 旧行。
- AC-8 形式核查在下一交易日（true-zero ≠ dead-zero 判据），核查前别给闸门数据下"已验证"文案。
- Lane D swimlane（SPEC-135.5）是这个闸门第一个展示面；`/api/q042/state` 与 Lane D 共用同一组装点（`web/server.py:2219`），改显示时保持单源，别在前端另拼。

## 2. Paper 账本：不再是空表，但有一条 phantom 要过滤

- grandfather 仓已补录并用修活的结算链结算：**`A-2026-03-12-002`，exit_pnl +$16,329**（6/11 到期，双腿深 ITM）。这是 2026-11-10 6mo 评审的第 1 个样本（n=1）。
- 首版补录 **`-001` 是 phantom**（fill_debit 单位错误，作废留痕）——账本渲染必须按 status 过滤 phantom，否则仓位表多一条假记录。
- 数据文件在 old Air（本机 repo 无 `data/q042_paper_trades.jsonl`），本地开发注意 fail-soft。

## 3. 告警与现金上下文：有告警文案面就会看到新行

- SPEC-094.2 F5b（Q093 P1 R-a）：每条 Q042 触发告警现在附一行 `Liquid cash $X · 在场 debit 合计 $Y`（`production/q042_executor.py:114 _cash_context_line`）。若页面展示告警历史/预览，按此格式预期。
- 配套运营规则（Q093 P1 R-b）：**池水位 ≥$150k 三方自洽；<$100k 时 Q042 触发日需卖资产或跳过**。这是 PM 人工规则、**没有自动闸门**——页面若展示 liquid pool 水位，措辞不能暗示系统会自动拦截。

## 4. 文案红线：对冲叙事作废 + 三个不能再引用的数字

研究定性已改：Q042 与 aftermath 是「**两个独立 alpha，共享尾部**」（dip 同场、常态双赢、尾部同亏但不放大，Q093 P2 §5）。

| 红线 | 正确表述 |
|---|---|
| ❌ "hedge / 对冲主策略 / crash hedge"（home regime matrix 那处你已修，全站同族措辞都算） | "独立 overlay" / "bullish reversal 结构" |
| ❌ 重叠率 "0.9%" / "low-overlap"（Q066 数字已被 Q093 P2 作废） | post-2020 同口径 **4.63%**（宽口径 9.2%），"重叠常态化但联合尾部无放大" |
| ❌ 暗示存在 aftermath×Q042 联合 cap | 预注册判定 **NO-GO**（joint/单边 worst = 1.07–1.12 < 1.5×），维持双 addon |
| ❌ 把 Q042 说成受 SPEC-111 现金治理覆盖 | 有意隔离（Q093 P1：naive 纳入 19y −$281k），治理 = F5b 告警可见性 + 池水位规则 |

## 真值源（需要出处时读这些，不要读本页转述）

- 审计全文：`doc/q042_aftermath_synergy_audit_2026-07-07.md`（含 grandfather 勘误终审）
- 现金层 verdict：`research/q093/q093_p1_findings_2026-07-07.md`
- 重叠/co-fire verdict：`research/q093/q093_p2_findings_2026-07-08.md`
- 修复包：`task/SPEC-094.2.md`（AC-8 待核）；闸门代码 `strategy/q042_gate.py`
