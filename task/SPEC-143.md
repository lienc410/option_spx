# SPEC-143 — Aftermath 首笔 0.5× staging（Q101 裁决 3 实施）

来源: research/q101/q101_e1_memo.md §6（外审 CONFIRMED + PM 授权裁决）。**Live 推荐层 only，禁止触碰任何回测路径。**

## 行为

Aftermath 通道（V3-A broken-wing 推荐）在生成开仓推荐时分三态：

1. **窗口首笔且窗口内无 skew 实测** → 推荐张数 = max(1, floor(标准张数 × 0.5))；卡片与 Lane A trace 节点注明"Q101 staging：本窗口 skew 未实测，首笔 0.5×，实测落地后恢复"（advisory ⚠ 档，非 veto）
2. **窗口内已有 skew 读数且 put 斜率倍数 s < 1.5** → 标准张数；trace 节点注明 s 值与"skew 实测通过"
3. **s ≥ 1.5** → 维持 0.5× + advisory 注明"Q101 预承诺复判触发，通道处置待 Quant 重跑判定网格"

定义（常量进代码，注释指向 Q101，不建 mirror 文档）：
- 窗口首笔 = 当前 is_aftermath 连续区间内尚无本策略已开仓位
- 窗口内 skew 读数 = data/q085_skew_monitor.jsonl 存在 date ≥ 窗口起始日的行
- s = (d15_moff − atm_moff) / 4.52vp（分母 = Q101 calm 中位基线：1.78 − (−2.74)；出处 research/q101/）
- monitor 数据缺失/字段缺 → 视同无读数（态 1，危害向保守）

## 约束

- **回测隔离**：staging 门只在 live 推荐上下文生效（有 skew monitor 状态可读时）；Q041/ES/SPX 三套回测磁盘缓存输出必须逐字节不变——AC 含 backtest/output/matrix_audit.csv 前后 diff 为空
- 推送宪法：advisory 档 → 不新增推送，digest/web 走既有 trace 单源（strategy/decision_trace.py label 函数，勿在模板重复文案）
- 文案人话（DESIGN.md 词表）；主题 theme.css 规则不适用（无新模板预期）

## AC

1. 三态单测（fixtures 合成 monitor 行）：无读数→0.5×+advisory；s=1.0→全量；s=1.8→0.5×+复判 advisory；monitor 文件缺失→态 1
2. 张数下限：标准张数=1 时 staging 仍 ≥1
3. 信号翻译对齐（feedback_signal_translation_alignment_ac）：用 2026-05 以来真实 monitor 数据回放 staging 门——期内无 aftermath 窗口 → 断言门从未激活（已知阴性校准）；另以 Q101 SKEW2 合成日验证 s≥1.5 分支（已知阳性校准）
4. 回测隔离 AC（上述 diff 为空 + 全量测试零新增失败）
5. trace 节点走 decision_trace.py 单源，verbatim-equality 断言样式同 SPEC-140

## 交付

worktree 隔离；推分支 `spec-143` 不碰 main 不部署；回报 commits + AC 逐条；SPEC 与现实冲突不静默改。
