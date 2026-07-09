# SPEC-138 — 收尾批：测试债清偿 + 缺轨污染修复（全局审阅 2026-07-08 产物）

**来源**: task/GLOBAL_REVIEW_findings_2026-07-08.md（F1/F3/F4/F6）。清偿铁律：**先按 SPEC 证明生产行为是有意的，再改测试对齐——禁止为变绿削弱断言**；每项引用行为出处 file:line。

## 1. F3 缺轨污染头条（P1）

**症状**（7/8 凌晨生产实况）：E-Trade token 过期 → combined NLV 少一轨 → 首页头条 `NLV −$625,433 (−49.87%) · MTD −49.9% · YTD −50.4%`，把数据中断显示为账户腰斩。
**修法**：`web/portfolio_surface.py` 头条 delta/MTD/YTD 计算感知轨道构成——当 open 轨道数 < 昨日基线轨道数时，(a) 用同口径基线（仅 available 轨道 vs 该轨道昨值）或 (b) 抑制百分比并标注"口径不齐（E-Trade 缺席，仅显示 Schwab）"。禁用跨口径相减出巨额假跌。
**AC**：缺轨 fixture → 头条不出 >20% 假跌 + 出现口径标注；全轨 fixture → 数值与现状 bit-identical（零行为变更）。

## 2. F4 门在降级分母上开火（P1）

**症状**：现金池分母随缺轨 $152k→$105k → cash budget 72.7%>60% 红门触发、RESOURCE WATERLINE "已满 −$13,352"、敞口占比 33.5%→42%——**数据中断被翻译成治理裁决**。
**修法**：`cash_budget_governance` / `exposure` / capacity 的现金与敞口计算携带 `rail_complete` 标记（来源 = liquid_cash 的 source/轨道数）。缺轨时：门降级为 advisory 语气（"数据降级中，治理判定暂挂"）或用 last-known-good 现金 + staleness 标注，**禁出硬 veto/红门**。decision_trace 资金层同步（135.3 的 advisory 档位复用）。
**AC**：缺轨 fixture → cash/exposure 门不出红 verdict + 显 staleness；全轨 → 与现状 bit-identical；trace 资金节点缺轨时 outcome ∈ {advisory, info} 非 veto。

## 3. F1 测试债清偿（16 失败，分族处置）

| 族 | 处置 | 铁律检查 |
|---|---|---|
| spec_086×7 + spec_089×3 | 测试改断言 `notify.gateway.push`（SPEC-126 契约），弃 mock 旧 `bot.send_message` | 先确认生产走 gateway（已知 True） |
| **spec_057×7** | **真缺口**：`_FORCED_LEGS`（selector.py:587）不认 sleeve keys（q041_t2_googl_csp 等）→ 补 legs 映射或显式排除非 SPX force keys（附行为判定：force_strategy 是否本应支持 sleeve？若否则测试改期望 ValueError） | 这是码 bug 不是测试债，先定行为 |
| q041_paper_log×6 | **先查因**：夹具期望 open、生产写 blocked——哪个门拦的？若治理门误伤 paper 流 = 码 bug（修码）；若有意 = 测试改期望 | 禁默认改测试 |
| spec_093×1 | 文案漂移，断言对齐现文案（并确认现文案正确） | |
| spec_087×2 + spec_125×1 (nav) | **不动**——归 b171de8 所在 lane，本批跳过并注明 | |

## 4. F6 有界裸 except 审计

仅审 **ledger 写入路径**（logs/trade_log_io.py）与**资金流路径**（cash_budget/exposure）的 `except Exception:` 是否吞掉了应当上报的错误；其余 155 处有意 fail-soft 不动。发现吞错即改为 log+re-raise 或窄化异常类型。

## 交付约束（PM 2026-07-08，共享工作树协调）

- **worktree 隔离**实施；**推分支 `spec-138`，不直接提交 main、不自行部署 oldair**——Quant 合并验收后统一部署（另一 Opus 会话同期在飞，避免部署竞争）
- 每项独立 commit；全量 pytest 目标：16 失败中除 nav×3 外全清，零新增
- 回报：commit hashes + AC 逐条 + 每个测试族的"行为判定"（有意/码 bug）结论
