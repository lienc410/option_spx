# Q088 T1 — Shadow 模式军团清单（2026-07-06）

**发现**: selector/governance 中六个特性以 shadow/disabled 模式常驻，多数自上线后无回访记录——"裸注记死信"模式的特性级版本（shadow = 无追踪的搁置决策）。

| 特性 | 模式 | 来源 | 生产真值 | 处置建议 |
|---|---|---|---|---|
| **SPEC-079 comfort filter** | shadow（无生产覆盖） | Q038, 3da1f5f 有意停靠 | **从未拦截过实盘**；74MB shadow 日志被回测重放污染（尾行 2018 日期） | **正式退役**（A4 已证 26y 零保护价值 + 生产本就不拦 → shadow→disabled 为零行为变更；日志污染修复交 dev） |
| bcd_stop_tightening | shadow | Q038 同批 | 同批停靠，无回访 | DEFERRED 评估（shadow 日志有无信号量） |
| overlay_mode（SPEC-026 VIX Accel） | **disabled** | 停用时间待考 | 完全关闭，但 memory/文档仍列为"已完成模块" | 确认退役 + 文档对齐 |
| overlay_f（SPEC-075/076） | shadow | 458231e "roll to shadow" | 无回访 | DEFERRED 评估 |
| shock_mode（shock engine） | shadow | — | 疑似设计即 advisory | 确认意图后标注（可能是合法常驻 shadow） |
| booster（Q074/SPEC-105/105-v2） | shadow（env 默认） | 修订 2 次后停靠 | 日志仅 19KB | DEFERRED 评估（Q074 验收标准考古） |

**模式教训（入 METHODOLOGY 候选）**: shadow 上线必须带"评估期限 + 判定标准"，否则 shadow = 永久坟场。六个特性全部进 DEFERRED.md 追踪。

## A4 更正（第三类叙事修正）

A4 memo 称 filter "2024 年还真实拦截 6 次"——**假设性拦截**（反事实口径），生产 shadow 模式从未拦过。A4 的 DEFER-CLOSED 处置反而简化：**退役提案**（无行为变更）可直接走快批，不必等 BCD anchor——它拦的对象本来就不存在。
