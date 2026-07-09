# 全局审阅 · 素材集（滚动更新，2026-07-08 凌晨开始）

## F1 — 基线测试失败分诊（16+1 个，长期无人认领）

全部为"系统进化甩下测试"型债务。**清偿规则：先按 SPEC 确认生产行为是有意的，再改测试对齐——禁止为了变绿而削弱断言**；每项引用行为出处。

| 家族 | 数量 | 根因 | 处置 |
|---|---|---|---|
| spec_086 / spec_089 | 7+3 | SPEC-126 网关迁移后，测试仍 mock 旧传输 `bot.send_message`（await_count=0）——生产行为正确 | 测试改断言 `gateway.push`（126 契约） |
| q041_paper_log | 6 | 测试夹具期望 open，生产写 blocked——某后加治理门（疑 cash 预算/cap）拦截了夹具场景 | **先查明是哪个门、是否有意**（若门误伤 paper 流需修码），再定测试 |
| spec_057 | 7 | `_FORCED_LEGS` 不认识 `q041_t2_googl_csp` 等 sleeve keys —— **真实小代码缺口**（force_strategy 枚举滞后于 sleeve 注册） | 补 legs 映射或显式排除非 SPX keys（selector.py:587） |
| spec_093 | 1 | 模板文案漂移（"Geometric from equity curve" 已不在页面） | 断言对齐现文案（并确认现文案正确） |
| spec_101 / 017_015 / state_and_api | ~3 | 详单见 tool-results 存档 bpcw2hxpy.txt，模式类同 | 同规则逐项 |
| spec_087×2 / spec_125×1 (nav) | 3 | 并行会话 b171de8 nav rename 与测试期望不一致（提交级二分已证） | **另一 lane 裁决**（rename 补全 or 测试更新） |

→ 处置载体：SPEC-138 测试债清偿批（全局审阅后与其它 findings 合批）。

## F2 — 已知未了（并入收尾）

- 遗留 direct senders ×3（SPEC-137 #1）、duplicate-id（#2）、Short Leg Fill（#3）、teal token（#4）
- Google Fonts 外域预加载（可选项，收尾轮定夺）
- Lane B 历史回放（short_leg_actions 落盘一行改动，"待需求"——收尾轮问 PM 或按 cheap 默认做）
- 26y stats 缓存 nightly 依赖 yfinance 盘中半日 bar 守卫（132 已加）——审阅时验证 nightly 全链

## F3 — 缺轨污染头条（P1，7/8 凌晨生产实况抓获）

E-Trade token 过期 → combined NLV 少一轨 → 首页头条渲染 **"NLV $628,607 −$625,433 (−49.87%) · MTD −49.9% · YTD −50.4%"**——把数据中断显示成账户腰斩。fail-soft 横幅存在但头条数学不感知轨道构成。修法：轨道缺席时同口径基线对比或标注"口径不齐（E-Trade 缺席）"并抑制红色百分比。

## F4 — 门在降级分母上开火（P1，同一事件暴露）

现金池分母随缺轨从 $152k 变 $105k → cash budget 72.7%>60% **红门触发**、RESOURCE WATERLINE 显示"已满 $-13,352"、敞口池占比 33.5%→42%。**数据中断被翻译成了治理裁决**。修法：现金/敞口类计算携带轨道构成标记——缺轨时降级为"数据降级中"advisory 语气或用 last-known-good + staleness 标注，禁出硬 verdict。（语义诚实红旗的数据版）

## F5 — 推送 HTML 转义 bug（P2）— **已修复 01307e7**

7/7 有 1 条推送 HTML parse 失败降级纯文本（H-4 兜底正常工作）。**另一会话 7/7 晚已独立抓获并修复**：gateway boundary 改为 whole-body escape（notify/gateway.py:56），根因是 H-4 只转义了 gate detail 片段、背景行的裸 `<0` 再次打死 parse。无需再动。

## F6 — 风格面（P3，有界行动）

- 裸 `except Exception` 165 处：多为有意 fail-soft 风格；**有界审计**仅限 ledger 写入与资金流路径的吞异常
- 生产路径 print() 30 处：多在脚本 main 段，低优
- `_ES_BP_PER_CONTRACT` 硬编码已带 freshness 机制（as_of+age 警告）——Q088 A5 遗留项降级为可接受

## F7 — A2 前端字符串审计（好消息）

非在飞页面（es/backtest/q041/margin/performance/journal/q042）抽查：SPEC 引用绝大多数已按 DESIGN.md 规则作 .spec-ref 后缀/出处行使用，7/6 前端 review 的模式保持住了。人话化残债集中于推送线（=SPEC-136 范围，另一会话在飞）。A2 无需独立批次。

## 全局审阅结论（2026-07-08 凌晨完成，Opus）

grep 面/单源/launchd/A2 全部走完：
- **TODO/FIXME/HACK 生产路径 = 0**（干净）
- **裸 except 165、print 30** — 绝大多数有意 fail-soft/脚本 main，仅 ledger+资金流路径值得有界审计（F6）
- **launchd 27/27 green（07-07 17:30）**；唯一历史违规是 signal_settling 路径问题（早已修）
- **_ES_BP_PER_CONTRACT 硬编码带 freshness 机制**（as_of+age 警告）——可接受
- **A2 前端合规**（F7）：非在飞页面 SPEC 引用已按 DESIGN.md 降级，无需独立批

**净新增待办 → SPEC-138 收尾批**（待 SPEC-136 完全落定 + 与另一会话协调后编）：
1. F1 测试债（16 失败：网关迁移 mock 过时×10 / q041 治理拦截查因×6 / **forced-legs 真缺口 selector.py:587×7** / 文案漂移×1 / nav×3 归另一 lane）
2. F3 缺轨污染头条（P1，NLV 头条数学需感知轨道构成）
3. F4 门在降级分母开火（P1，现金/敞口计算携带轨道标记，缺轨降 advisory）
4. F6 有界裸 except 审计（仅 ledger/资金流）

**协调风险实录**：本轮出现 26 文件混提交（c99e234 裹入另一会话 SPEC-136 + 我的 findings 文档）——共享工作树多会话并发的典型事故，无数据丢失但提交边界被污染。SPEC-137/138 派 dev 前须与在飞会话协调工作树占用，或用 worktree 隔离。
