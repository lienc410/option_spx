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

## 待续

135.4 落地后：前端字符串批 A2 审计、全仓 grep 面（TODO/FIXME/裸 except/print 遗留）、模块间单源审计、oldair launchd 面板健康、DESIGN.md 与实现一致性抽查。
