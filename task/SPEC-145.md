# SPEC-145 — Regime Playbook 面板（/state-map）

## 目标

PM 2026-07-13 三场景操作问答（箱体内 / 上破真假与第一动作 / 下破第一动作）
ratify 后要求进前端。选址 /state-map：手册按状态索引，L1 实时显示当前状态
→ 面板高亮当前场景卡；点位表与 DIP gauge 互补。

## 接口定义

**F1 单真值源模块** `strategy/regime_playbook.py`：三场景准则（每条强制
provenance 标签）+ `compute_levels(ath, band_lo, band_hi)` 当日点位
（A 触发线 / 箱体上下死亡线（带宽恒等式反解）/ 弱上破警觉带 / B 阶梯四档）。
**纪律**：点位零静态数字；基率行 import 自 `state_flip_notify`（SPEC-142
同一常量，禁复制）；参数 import 自各真值源（trigger/executor/sizing）。
展示层定位——不进 push 管道（F2 禁令管推送，不管 PM 自 ratify 的手册面板）。
**F2 端点** `/api/regime-playbook`：fail-soft 恒 200；`active_scenario` 由
structure_state 映射（RANGE→range / TREND_UP→up_break / TREND_DOWN→down_break /
MIXED→null）；ath_degraded → levels null 不给假数。
**F3 面板**：/state-map 折叠 frame（rehearsal 同款交互），三卡 grid + 点位
strip；当前场景卡 NOW 徽章 + 高亮并默认展开；语言/字体遵 DESIGN.md
（标签 EN / 叙事 CN / 数字 mono）。

## 验收标准

| AC# | 描述 | 结果 |
|---|---|---|
| AC-145-1 | 点位数学 golden（2026-07-13 实值：A 7305.39 / 箱亡 7631.49/7238.57 / 阶梯四档）+ degraded 不给假数 + 无箱体只给触发线 | ✅ 2 tests |
| AC-145-2 | 基率行与 SPEC-142 推送逐字符同源（import 断言）；每条准则有 provenance | ✅ 2 tests |
| AC-145-3 | active_scenario 四态映射 + 注入式 payload 组装 | ✅ 5 tests (param) |
| AC-145-4 | 老 Air 部署：/api/regime-playbook 返回 active=range、页面 PLAYBOOK 面板渲染、IN BOX 卡 NOW 高亮 | ✅ live 实测（as_of 2026-07-13, A 7305.39, 阶梯四档, a_first=true, 页面 9 处渲染） |

## Handoff Contract

What changes：`strategy/regime_playbook.py`（新）、`web/server.py`（+端点）、
`web/templates/state_map.html`（+面板）、`tests/test_spec_145.py`。
Invariants：决策路径零 diff（纯展示层）；SPEC-142 推送文案未动。
Rollback：摘面板 + 端点两段即回，模块无消费方。

---
Status: DEPLOYED 2026-07-13 (old Air verified)
