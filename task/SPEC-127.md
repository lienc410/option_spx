# SPEC-127 — Diagonal Roll 登记与 Campaign 记账（PM 2026-07-06 需求）

**背景**: PM 确认 diagonal 标准打法含 roll（短腿到期前平旧开新，长腿持续持有），但 (a) 前端无 roll 登记入口；(b) 记账模型未定义——整个交易的 performance 该按阶段还是按大组合显示。H-5（21-DTE 动作缺失）修复后动作引擎也需要 ROLL 选项。

## 1. 记账模型（Quant 设计定稿）：Campaign 双层模型

**Campaign（战役）= 长腿的生命周期**。开仓创建 `campaign_id`；每次 roll = 一个 cycle；长腿平掉/到期则 campaign 结束。

**双层显示**：
- **Cycle 层（阶段）**：每行一个短腿周期——短腿 K/expiry、开仓 credit、平仓 cost、该 cycle 实现额、持有天数。第 0 行 = 初始建仓（debit）
- **Campaign 层（英雄指标）**：
  - **Adjusted Basis（调整后成本）** = 初始 debit − 累计短腿净收入——"长腿的成本已被 roll 收回多少"，diagonal 交易者的核心直觉量，**卡片主指标**
  - Campaign Net = 全部现金流 Σ + 未平 legs 现值；Campaign ROI = Net / 初始 debit
  - 状态徽章：cycles 数、长腿剩余 DTE、当前短腿 DTE

**Performance 页口径**：campaign 为统计单元（一个 campaign = 一笔 trade），点开下钻 cycle 层。**降级门（SPEC-123）记账衔接**：mark 类门天然兼容（家族求和不关心分组）；"最近 6 笔实现"的计数单位 = **cycle 实现事件**（每次 roll 的短腿平仓是一个真实决策点）——写入 123 状态机注释防歧义。

## 2. Ledger 扩展（衔接 H-3 的 open_id/strikes 补齐）

- open 事件新增 `campaign_id`（默认=自身 id）；`roll` 事件（schema 已有此类型，从未使用）：原子记录 {closed_short: K/exp/price, new_short: K/exp/price, campaign_id}
- 长短腿分离记录（根治单一 expiry 字段问题——H-5 根因）：open 事件记 `legs: [{side, K, expiry}]`

## 3. UI

- 持仓卡加 **Roll 按钮** → 表单（平旧短腿价格 + 新短腿 K/expiry/价格）一次提交
- Campaign 卡片按 §1 双层渲染；平仓下拉词表加 `roll`（与 manual/discretionary 一起补）

## 4. 动作引擎（衔接 H-5）

短腿 ≤21 DTE 时推送 ACTION：**"CLOSE 或 ROLL"** 双选项（带当前链上建议新短腿：45DTE |Δ|0.30——shadow 已在算同款腿）；roll 后 21-DTE 时钟按新短腿重置。

## 4b. 止损锚定（2026-07-06 补充，PM 实仓暴露的设计参数）

Debit 结构 −50% 止损在 roll 后锚什么：
- **定稿：锚 Adjusted Basis**——止损线 = 结构现值 ≤ 0.5 × adjusted basis。含义：campaign 层最大追加损失恒为"剩余真实敞口"的一半；已入袋的 roll 收入不参与止损计算（银行里的钱不该被拿来垫亏损空间的分母）
- 弃案（锚原始 debit）：roll 收入越多止损越松相对于剩余敞口，campaign 总损上限漂移，与"风险跟真实敞口走"直觉相悖
- 引擎侧：`pnl_ratio` 分母从 entry debit 换成 campaign adjusted basis（仅 diagonal/roll 场景；无 roll 时两者恒等，回归零行为变更）
- 属参数语义变更 → 随本 SPEC 整体走 PM ratify

## 5. AC 要点

roll 原子性（部分失败回滚）；campaign 聚合数学的单测（含多 cycle + 部分平仓）；adjusted basis 与逐 cycle 加总恒等断言；止损锚定单测（零 roll 时新旧口径 bit-identical + 有 roll 时按 adjusted basis 触发）；performance 页 campaign 口径回归；H-5 的 21-DTE 测试扩展 ROLL 分支；ledger 迁移（既有 5 笔 BCD 回填 campaign_id 与 legs——PM 的 6/3 双仓即首个 campaign）。

## 过渡期 workaround（SPEC-127 落地前，给 PM）

现在就想 roll 的话：券商端正常操作，ledger 里登记为 close（旧短腿，note 写 "roll leg"）+ open（新短腿，note 写 "roll from <id>"）——数据不丢，127 落地后迁移脚本可归组。
