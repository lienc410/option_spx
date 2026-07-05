# SPEC-123 — BCD 家族治理落地包（PM 2026-07-05 ratify D1/D2 + 手动单边界）

**性质**: 纯增量为主（监测/提示/断言），一处 selector 端 advisory 前置门。来源 `task/q087_bcd_family_review_packet_2026-07-05.md` v3+终态。

## 1. BCD 降级状态机（D1，家族级：carve + 主格）

- 数据源：ledger（实现）+ 每日链快照标记（未实现，**mid 口径为主**，natural 并行记录）
- **Halt 条件（任一）**: 最近 6 笔实现和 < 0；过去 18 个月实现+标记和 < 0 且笔数 ≥3；单自然月标记回撤 ≥ $12k；**家族累计（实现+标记）< −$15k → 全停+PM 复审**
- Halt 行为：selector 对 BCD 格输出降级为 wait + Telegram 说明触发的门；恢复须 PM 显式复审 + fresh 报价对照
- **运行特性写入代码注释与推送文案**：P(6 笔和<0 | 边际为真) ≈ 39-48%/窗口——halt = 例行复核事件，文案不得用告警语气
- **首批实现流水触发器**：任一 BCD 平仓落 ledger → Telegram 通知 PM+Quant"预注册复审触发"

## 2. D2 前置门（LOW_VOL 回归时）

- regime 进入 LOW_VOL 后：BCD 主格 selector 输出附 advisory 标记 "quote-gate: N/10 天"，shadow 记录该 regime 报价
- **≥10 交易日 且 CALIB 偏移复核 |Δ|≤1vp** → 解锁（推送告知）；解锁后首 5 笔 1 张锁定（advisory 提示，PM 手动执行自律）

## 3. SPEC-111 手动单提示（提示不拦）

- ledger 录入手动 open 时同步跑治理检查：超 cap / 破 floor / 所在格为 wait（含 SPEC-060 类死格）→ Telegram **知情提示**（如"本单在治理口径外：现金 $16.9k < $30k floor"），不阻断、不需确认

## 4. 代码级修复（外审揪出）

- **ledger ID 唯一性**：06-03 三笔 open 的 ID 前缀相同——核实 ID 生成逻辑，必要时加唯一后缀 + 对既有记录出迁移说明（correction 定位/归因分组正确性依赖它）
- **`_effective_iv_signal` 单一函数化断言**：任何研究/监测侧格分类必须 import 该生产函数（一天内三处独立错误的根因）；CI 断言无第二实现
- SPEC-120 遗留小项：compare CSV 缺行补齐、SPEC-113 后行为 cache 重生成、pricing convention tag 断言

## 5. SPEC-122 前向版并入本包

每日 BCD 信号日（生产 selector 判定）真实报价 shadow（v2 预注册标准照旧），落 `data/q087_bcd_quote_shadow.jsonl`，heartbeat 入表。

## AC 要点

状态机四门单测 + 触发集成测试（构造 halt 场景）；前置门 N/10 计数与解锁推送；手动单提示的三类触发（cap/floor/dead-cell）实测；ID 唯一性回归；断言批全绿；heartbeat 注册表更新。
