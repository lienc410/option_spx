# 全站人话化审计 Charter（PM 发起 2026-07-07 晚）

**任务**: 前端全部页面 + 推送全部文案，一次完整审核，非人类语言（SPEC 编号、内部代号、无语义数字、密码式缩写）全部改人话版。Decision Trace（SPEC-135 §0）的人话铁律升格为**全站文案风格契约**。

## 风格契约（源自 SPEC-135 v3，PM 确认）

1. 主文案不预设读者知道任何 SPEC 编号/内部代号/研究 Q 号；代号降级为悬停角标（溯源用）
2. 数字必须带语义（分位数说"偏贵/偏便宜"、计数说"已 X 天/需 Y 天"、比例说清分子分母）
3. **期权/策略术语保留英文**（Bull Call Diagonal、BPS、delta、DTE、IV、call/put），首次出现中文括注
4. 细节走 hover/点击展开三件套 `{检查数据, 实际值 vs 阈值, code_ref}`，不堆在主文案
5. 人话标签与逻辑定义**同居代码**（label_human 字段），禁独立词汇表文档（反镜像）

## 方法

- **Quant（我）**: 逐页/逐推送 catalog 所有用户可见字符串 → 改写表（原文 | 人话版 | hover 内容 | code_ref | 所在文件:行）→ findings CSV + SPEC-136 handoff
- **Dev**: 按改写表实施 + label_human 字段化改造
- 判定基准：给"聪明但从没读过我们 SPEC 的期权交易者"看得懂

## 批次

- **批 A（先做）**: 推送全量（晨报/digest/ACTION/ALERT/FYI/治理提示——PM 最高频触点）+ portfolio_home + /spx 决策相关区块 + SPEC-129 表单文案
- **批 B**: 回测页家族（backtest/es/q041/q042/aftermath/hvladder/portfolio_backtest）+ performance/margin/journal
- Structure Map 卡与 Decision Trace 天生合规（135 §0 约束下实施），作为风格参照物

## 边界

不改任何数字口径/逻辑（纯文案层）；口径问题单独立项（如 131 v2 分母修正）；research/ 与 task/ 内部文档不在范围（工作语言）。
