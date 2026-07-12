# SPEC-141: 统一状态面（S1）+ State Map 页（S2a）

## 目标

实现 `doc/unified_state_redesign_2026-07-13.md` 的 S1+S2a：把散落在 5 个模块的市场状态收拢为**一个状态面模块**（shadow 语义，零路由变更），并新增 **State Map 页 = 四层架构的活版**（Layer 0 veto 灯 / Layer 1 双轴+事件灯 / Layer 2 三引擎 / Layer 3 双池）+ Portfolio home 顶部 hero 条。

审批链：PM 2026-07-13 mockup v2 方向确认 +"开始"；三条评审意见（QA 硬要求 / badge 语义统一 / 引擎卡信息密度保留）已转写为 AC-8/9/10。

## 策略/信号逻辑

**无任何路由/参数/风险语义变更**。状态面是纯只读聚合层（shadow）：selector、executor、governance 一行不改、不 import 它。

## 接口定义

### F1 — 状态面模块 `strategy/state_surface.py`

`compute_state_surface() -> dict`，全部复用现役信号，不重新实现任何算法：

| 字段 | 来源（复用） |
|---|---|
| `vol_axis`: {state: CALM/NORMAL/HIGH/EXTREME, vix, dist_next} | signals/vix_regime 阈值（15/22/35） |
| `structure_axis`: {state: TREND_UP/RANGE/TREND_DOWN/MIXED, episode_day, band_lo, band_hi} | RANGE = SPEC-094.4 因果分段分类器（in-episode-now，尾窗同 094.4）；非 RANGE 时按 trend 信号方向，NEUTRAL 非 episode → MIXED |
| `trend_signal` | signals/trend（hero 单列，与 structure 轴并存——6 月实况：RANGE 与 BULLISH 共存） |
| `events`: dip{active, ddath, dist_pp, type_if_now} · aftermath{active, peak10d} · backwardation · second_leg | q042 snapshot ddATH · 094.4 分型 · selector is_aftermath · vix3m · governance second_leg |
| `veto`: extreme_ok · second_leg_ok · caps_ok · cash_floor_ok | governance runtime + cash_budget |
| `ammo`: {liquid, in_flight_debit, reserve_need($78.6k=12.5%×NLV 现算), ready} | cash_budget_governance + q042 sizing |
| `today`: selector 推荐摘要 + 资源类型（吃 BP/吃 cash） | /api/recommendation 同源 |

失败语义：任一子源失败 → 该字段 `{status:"n/a"}`，不抛不假造（fail-soft，逐字段）。

### F2 — API 与日志

`GET /api/state-surface` 现算返回；`data/state_surface.jsonl` 日志一天一行——挂进 `scripts/daily_snapshot.py` 既有 16:50 job（幂等：当日已有则跳过）。**首跑回填**：用日线缓存回算过去 90 TD 的 (vol_state, structure_state) 简版填时间轴（回填行打 `backfill:true`）。

### F3 — State Map 页 `/state-map`

按 mockup v2（Artifact `state-map-v2-live-layers`）实现四层活版 + 90 天时间轴 + 触发预演（复用 094.4 分型/sizing helper，fail-soft n/a）。**布局即架构**：Layer 0→3 纵向层框、层内容与 mockup 一致。nav 全页入口。

### F4 — Portfolio home hero 条

顶部**纯新增**一条（一行摘要 + 点击进 /state-map）。**Open Position 与 Portfolio Snapshot 两个 section 的 DOM 一个节点不动**（PM 不动锚点）。`/portfolio_old` 本期不需要（本期对 home 只有 additive hero；S2b 重组时才建）。

## 边界条件与约束（含 PM 评审三条）

1. **Badge 语义统一（PM 2026-07-13）**：引擎徽章只有两个词——`ON`（今日被路由/可入场）/ `STANDBY`（今日未被路由）。Q042 的 armed/disarmed 是**行内字段**（`Trigger armed: yes/no`）不是徽章；veto 灯用点色不用词。禁止 ARMED/ACTIVE/READY 等第三词做徽章。
2. **量表刻度一致性（PM 指出的 mockup bug）**：所有 BP 条共用**绝对 0-100% 刻度**（同值必同长），cap 以金色刻度线标注在各自位置（80%/50%）；cash 条同理（0→liquid 满格，弹药线绝对位置）。禁止"利用率相对 cap"的变长条。
3. **文字不重叠**：刻度线标签（cap 80% 等）须防碰撞（错位/上下交替或 tooltip 化）；1280/900/mobile 三宽度无重叠（AC-9 视觉核查项）。
4. **引擎卡信息密度（PM 要求保留）**：每张引擎卡 = **静态身份块**（payoff 物理 · 吃什么资源 · 结构清单 · 接管条件 · 同引擎兄弟：/ES HV Ladder demoted、Q078 ladder shadow）+ **live 状态行**。静态文案以 `doc/unified_state_redesign_2026-07-13.md` §4 矩阵为准。
5. DESIGN.md 全套：link theme.css 禁内联 :root；三字体自托管；全数字 mono；语言规则（English chrome/badges，中文 rationale，DOM 单语）；spec-ref 降级后缀；`--text-muted` 禁内容、关键阅读内容用 `--text`（PM 可读性要求）。
6. dark/light 双主题经 theme.css tokens 自动成立。

## 不在范围内

S2b（资源卡重组/矩阵活化/governance 卡瘦身）；S4（selector 读状态面）；`/portfolio_old`（随 S2b）；任何路由/参数变更。

## Prototype
（无——全部复用已验证代码路径）

## Review
- 结论：N/A（实施后 Quant fidelity review + browse QA 补）

## 验收标准

| AC# | 描述 | 验证 |
|---|---|---|
| AC-141-1 | `/api/state-surface` 全字段返回且与源 API 交叉一致（episode_day 对分类器、ddath 对 q042 state、caps 对 governance、liquid 对 cash_budget） | pytest 交叉断言 |
| AC-141-2 | 日志幂等一天一行；首跑回填 90 TD（backfill 标记） | pytest |
| AC-141-3 | 子源注入失败 → 对应字段 n/a，API 200，页面显示 n/a 不空白 | pytest 注入 |
| AC-141-4 | **shadow invariant**：`strategy/selector.py`、`production/*`、`strategy/sleeve_governance.py` 零 diff 且无 state_surface import | grep + git diff 断言 |
| AC-141-5 | 页面徽章词汇 ∈ {ON, STANDBY}；Q042 armed 为行内字段 | pytest 模板断言 + 视觉 |
| AC-141-6 | **量表刻度**：渲染宽度 = 绝对值/满刻度（同值同长，单测断言计算函数）；cap 刻度线位置正确 | pytest + 视觉 |
| AC-141-7 | hero 条纯新增：portfolio home 的 Open Position / Portfolio Snapshot section DOM 与改动前逐字节一致（模板 diff 限定 hero 块） | git diff 范围断言 |
| AC-141-8 | 触发预演：episode 型/突发型/现金不足三例正文正确（复用 094.4 helper，非重写） | pytest |
| AC-141-9 | **browse QA（PM 硬要求）**：部署后 1280/900/390 三宽度截图核查——无文字重叠、同值条同长、双主题正常、全数字 mono | Quant 用 browse 工具截图核查并附 review |
| AC-141-10 | 094.2/094.3/094.4 全部测试继续绿 | pytest |

## Handoff Contract

1. **What changes**：新增 `strategy/state_surface.py`、`web/templates/state_map.html`；`web/server.py`（+2 路由）；`scripts/daily_snapshot.py`（+日志 hook）；`web/templates/portfolio_home.html`（仅顶部 hero 块 additive）；nav 入口。
2. **Invariants**：selector/executor/governance 零 diff（AC-4）；Open Position / Portfolio Snapshot DOM（AC-7）；全部既有 API 字段；094.x 测试全绿。
3. **Acceptance checks**：AC-141-1..10（关键 = 4/6/7/9）。
4. **Out of scope**：见上节。
5. **Failure / rollback**：新页/新 API 独立，故障即摘 nav 入口 + 路由返 404，零策略影响；hero 块单 commit 可独立 revert。

---
Status: APPROVED（PM 2026-07-13 "开始" + 三条评审意见已转写 AC；本 spec 为忠实转写）
