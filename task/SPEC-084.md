# SPEC-084: Q045 Joint `bp_target` Lift for Account-Level ROE

Status: DONE

## 目标

将 `Q045` Tier 3 已完成的联合研究结论收敛成一个**窄范围、可实施、可回归验证**的参数类 Spec：

- `bp_target_normal: 0.10 -> 0.15`
- `bp_target_low_vol: 0.10 -> 0.15`
- `bp_target_high_vol: 0.07 -> 0.14`

并同步更新 live recommendation 中 `_size_rule()` 的展示文案，使其与新的账户风险口径一致。

本 Spec 的定位是：

- **参数默认值提升**
- **风险披露同步**
- **最小实现面**

本 Spec **不是**：

- ceiling 改造 Spec
- Overlay-F 改造 Spec
- Q041 paper-trading 扩展 Spec
- 新策略 / 新路由 / 新 runtime 能力的 productization Spec

---

## 背景

`Q045` Tier 3 已完成，且 PM 已决定进入 DRAFT Spec 阶段。

核心研究结论（见 `task/q045_pm_decision_packet_2026-05-06.md`）：

- `Q036 / Q044 / SPEC-077` 的 piecemeal 优化被重新统一为**单一联合参数提升**
- 联合最优 `J3`：
  - `bp_target_normal = 0.15`
  - `bp_target_low_vol = 0.15`
  - `bp_target_high_vol = 0.14`
- `19` 年样本（`2007-01-01 -> 2026-05-06`）结果：
  - `AnnROE: 11.94% -> 17.41%`（`+5.48pp`）
  - `Sharpe: 1.78 -> 1.83`
  - `Peak BP: 30% -> 43%`
  - `Worst trade: -5.64% acct -> -8.82% acct`
- NORMAL / HIGH_VOL 两条提升路径**完全可加**：
  - interaction = `0.000pp`
- `Q044`（BPS-only）已被 supersede
- `Q036 Overlay-F` 的基础价值被 partial supersede，但 shadow 观察仍可保留

这意味着：

- 不需要 ceiling 改动
- 不需要新增策略
- 不需要复杂的 regime-specific runtime machinery
- 只需收口成一个小的参数提升 Spec

---

## 核心原则

- **只改默认参数，不改策略矩阵**
- **不改 ceiling**
- **不引入新 toggle**
- **研究结论必须以风险披露方式落地**
- **回归验证必须证明旧参数路径可复现 baseline**
- **不把 Q036 / Q041 / `/ES` 等其他 open branch 一起带进本 Spec**

---

## In Scope

1. 修改 `StrategyParams` 中三个 `bp_target` 默认值
2. 修改 `_size_rule()` 展示文案，使 normal / high-vol 风险口径与新参数一致
3. 增加针对 `bp_target` 默认值与展示文本的测试
4. 增加一组最小回归验证要求，确认：
   - baseline 旧参数可被 override 重现
   - 新默认值路径在关键参数层已切换
5. 在 Spec 文本中记录强制风险披露

---

## Out of Scope

- `bp_ceiling_normal` / `bp_ceiling_high_vol` 任何调整
- `Q036 Overlay-F` shadow / active / decommission 决策
- `Q044` fallback 重新研究
- `Q041` paper-trading route / dashboard / ledger 变更
- broker integration 扩展
- bot / alert / runtime service 改造
- 新的策略路由、候选扫描、mark-to-market engine
- 任何新的 variant sweep / Tier 4 研究

---

## 功能定义

### F1 — `StrategyParams` 默认值提升

在 `strategy/selector.py` 的 `StrategyParams` 中修改：

```python
- bp_target_low_vol:  float = 0.10
+ bp_target_low_vol:  float = 0.15

- bp_target_normal:   float = 0.10
+ bp_target_normal:   float = 0.15

- bp_target_high_vol: float = 0.07
+ bp_target_high_vol: float = 0.14
```

要求：

- 仅修改默认值
- 不新增新字段
- 不修改 ceiling 相关参数

### F2 — `_size_rule()` 展示文案同步

**修改位置：`strategy/selector.py` 第 322–323 行，`_size_rule()` 函数**。

该函数为唯一入口，`web/server.py` 的 `_bp_target_fraction_for_strategy()` 直接读取 `DEFAULT_PARAMS`，会自动继承 F1 的参数变更，**无需修改 `web/server.py`**。

```python
- "Full size — risk ≤ 3% of account (signals agree + VIX flat/falling)"
- "Half size — risk ≤ 1.5% of account (VIX rising or signals mixed)"
+ "Full size — risk ≤ 4.5% of account (signals agree + VIX flat/falling)"
+ "Half size — risk ≤ 2.25% of account (VIX rising or signals mixed)"
```

说明：

- 这是**展示/解释口径同步**，不要求引入新的 sizing engine
- `bp_target_high_vol` 从 `0.07` 升至 `0.14`（2x），但 HIGH_VOL 使用同一 `_size_rule()` 函数；升级后 `bp_target_high_vol (0.14) ≈ bp_target_normal (0.15)`，使用统一的 `4.5%` 口径可接受
- `web/templates/margin.html` 中有静态示例文案（"6.0% of account"），这是旧的举例数字，不在本 Spec 修改范围内

### F3 — 风险披露要求

本 Spec 实施后，相关说明 / handoff / review 必须明确记录以下风险披露：

- `Worst trade` 可能扩大至约 `-8.82%` account（full-sample）
- `Peak concurrent BP` 可能升至约 `43%`
- 仍位于 `HIGH_VOL ceiling 50%` 之内
- `Q036 Overlay-F` 不被本 Spec 自动关闭；仅视为 value-add 已被 partial supersede

说明：

- 本条要求至少体现在：
  - `SPEC-084.md` 本身
  - 实施 handoff
  - reviewer close-out summary

### F4 — 最小测试与回归

至少补以下验证：

1. **参数默认值测试**
   - `StrategyParams()` 默认实例应给出：
     - `bp_target_low_vol == 0.15`
     - `bp_target_normal == 0.15`
     - `bp_target_high_vol == 0.14`

2. **文案同步测试**
   - `_size_rule()` 或对应输出文本中应出现：
     - `4.5%`
     - `2.25%`

3. **Baseline override 回归**（行为输出验证）
   - 通过显式 `params=StrategyParams(bp_target_normal=0.10, bp_target_low_vol=0.10, bp_target_high_vol=0.07)` override 时：
     - 不报错
     - `bp_target_pct` 返回 `10.0`（而非 `15.0`），确认 override 路径有效
     - 可运行 `run_backtest(params=old_params)`，不 crash

4. **不改 ceiling 回归**
   - `StrategyParams().bp_ceiling_normal == 0.35`
   - `StrategyParams().bp_ceiling_high_vol == 0.50`

5. **现有测试修正（⚠️ Developer 必须处理）**
   - `tests/test_state_and_api.py:138` 当前断言 `bp_target_pct == 10.0`
   - F1 落地后此断言会失败，**必须在本 Spec 实施范围内更新为 `bp_target_pct == 15.0`**
   - `tests/test_spec_069.py:72` 和 `tests/test_overlay_f_gate.py:90` 使用显式 `bp_target=0.07` override，不受影响，无需修改

---

## 研究结论锚点（必须在 Spec 中保留）

以下不是重新研究，而是本 Spec 的设计依据，必须明确记录：

- `J3` 是联合最优：
  - `bp_target_normal = 0.15`
  - `bp_target_low_vol = 0.15`
  - `bp_target_high_vol = 0.14`
- `19` 年样本：
  - `AnnROE +5.48pp`
  - `Sharpe +0.05`
  - `Peak BP 43%`
- NORMAL / HIGH_VOL interaction = `0.000pp`
- `Q044` superseded
- `Q036` partial superseded（但不强制关闭）

---

## 边界条件

- 本 Spec 不得顺手调整任何 ceiling
- 本 Spec 不得顺手把 `Q036` 从 shadow 改成 active / disabled
- 本 Spec 不得把 `Q041` 的 paper-trading BP budget 一起改掉
- 若实施过程中发现 `_size_rule()` 文案实际同时承载了更深层逻辑，而非纯展示文案，应停止并报告，不自行扩展 Spec

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `StrategyParams` 默认值已改为 `0.15 / 0.15 / 0.14` | unit test / grep |
| AC2 | `_size_rule()` 或对应 recommendation 输出文案已从 `3% / 1.5%` 更新为 `4.5% / 2.25%` | unit test / snapshot |
| AC3 | 显式 override 回旧值时，`bp_target_pct` 返回 `10.0`（而非 `15.0`），且 `run_backtest` 不 crash | regression test |
| AC4 | `bp_ceiling_normal == 0.35` / `bp_ceiling_high_vol == 0.50` 默认值无变化 | unit test / grep |
| AC5 | `Q036` / `Q041` / 其他策略路由无直接代码范围扩展 | diff review |
| AC6 | 实施 handoff 明确写出 `Worst trade -8.82% acct` 与 `Peak BP 43%` 风险披露 | handoff review |
| AC7 | `tests/test_state_and_api.py:138` 断言已从 `10.0` 更新为 `15.0`，现有测试套件全部通过 | test run |

---

## 建议实施顺序

1. `F1` 参数默认值
2. `F2` `_size_rule()` 文案同步
3. `F4` 测试与 baseline override 回归
4. handoff 中补 `F3` 风险披露

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-07 | PM 决定 `Q045` 进入 DRAFT Spec；Planner 收口为单一联合参数提升 spec，范围限定为 `bp_target` 默认值 + `_size_rule()` 文案同步 + 风险披露，不带入 ceiling / Q036 / Q041 扩展 | DRAFT |
| 2026-05-07 | PM 审批通过；`SPEC-084` 进入标准 Developer 实施路径 | APPROVED |
| 2026-05-07 | Quant pre-implementation review：发现 3 处需修正。(1) F2 补充修改位置说明（`strategy/selector.py:322-323`，`web/server.py` 无需修改）；(2) F4/AC3 加强行为输出验证；(3) 新增 F4.5 + AC7：`tests/test_state_and_api.py:138` 断言 `bp_target_pct` 须从 `10.0` 更新为 `15.0`，否则测试套件会直接失败。研究结论正确，范围无变化 | APPROVED（review 修订完成）|
| 2026-05-07 | Developer implementation complete: `StrategyParams` defaults changed to `0.15 / 0.15 / 0.14`; `_size_rule()` display text changed to `4.5% / 2.25%`; focused SPEC-084 tests added; affected API draft assertion updated to `15.0`; handoff records `Worst trade -8.82% acct`, `Peak BP 43%`, no ceiling change, and no Q036/Q041 change | DONE |
