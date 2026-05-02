# SPEC-074: Backtest Selector Path Parity (HC No-Op Declaration)

Status: DRAFT (HC-side no-op pending PM confirmation)

## 目标

**What**：将 MC handoff 中 SPEC-074 的设计意图 —— "`_backtest_select` simplified fallback 矩阵被 delegate 到 live `select_strategy`" —— 在 HC 侧做正式 parity 核查并归档；如核查无差异，则在 HC 侧将 SPEC-074 显式判定为 **no-op declaration**（无代码变更，仅文档收口）。

**Why**：
- MC `SPEC-074 DONE` 是 MC-side 的修复，前提是 MC 自己曾经存在 `_backtest_select` 简化路径。HC 的实际状态需要独立核查后才能把 SPEC-074 视作 "已对齐"
- 直接核查（2026-05-01）显示：HC 的 `backtest/engine.py:835` 与 `:1252` 已经直接调用 `select_strategy(vix_snap, iv_snap, trend_snap, params)`，**没有 `_backtest_select` 函数存在**，没有 simplified matrix fallback
- HC `select_strategy` 已经包含 backwardation / VIX3M / IVP63 / IVR-IVP divergence 全分支
- 若不在 HC 侧把这条 "事实差异" 写明，未来 reproduction sprint 会被误读为 "HC 也修过 SPEC-074"，在 governance 上违反 "MC-side DONE ≠ HC-side DONE" 原则
- 详见 `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md` §3.5

---

## 核心原则

- **核查 → 声明**，不是 **修复 → 验证**：HC 侧不需要做任何代码变更，除非 §F2 比对发现 HC `select_strategy` 缺失 MC SPEC-074 引入的某个 live 分支
- **不重新启用 backtest fallback**：HC 既无 fallback，也不允许再引入；这是 reproduction sprint 之后维护期需要 lock-down 的状态
- **不跨入 SPEC-077 / 080 范围**：profit_target 默认值与 BCD debit stop 由那两条 spec 单独处理
- **保留 MC 编号连续性**：HC 跳过 SPEC-067 后已使用 SPEC-068..073；本条与 MC 对齐为 SPEC-074

---

## 功能定义

### F1 — 核查 HC 侧不存在 `_backtest_select` 简化路径

**核查对象**：
- [backtest/engine.py](backtest/engine.py)
- [backtest/](backtest/) 全目录

**核查命令**：
```bash
grep -rn "_backtest_select\|backtest_select\|simplified.*select\|fallback.*matrix" backtest/
```

**预期结果**：返回 0 个 production 命中（prototype 脚本可保留历史快照引用，不算）。

### F2 — 逐行 diff HC `select_strategy` vs MC SPEC-074 文本

**核查对象**：[strategy/selector.py:543](strategy/selector.py#L543) 起的 `select_strategy(vix, iv, trend, params)` 函数

**比对维度**（由 PM 在 spec 包中提供 MC 等价文件，或由 Quant 从 MC handoff `§SPEC-074 实现细节` 节选）：

| 分支 | HC 当前位置 | 是否需补 |
|---|---|---|
| `vix.backwardation` skip (HV neutral / HV bearish / Normal bullish) | selector.py:698 / 746 / 786 / 963 / 1084 | 待 diff |
| `IVP63_BCS_BLOCK >= 70` gate | selector.py:165, 623 | 待 diff |
| `vix.trend == Trend.RISING` skip | selector.py:616 | 待 diff |
| `IVR-IVP divergence` 处理 | selector.py:156 (常量) | 待 diff |
| `VIX3M term structure` 引用 | selector.py:255-257, 220 | 待 diff |
| 任何 MC SPEC-074 之后引入的 **新** 分支 | — | 待 PM 提供 |

**判定规则**：
- **若 HC 全部分支已存在** → SPEC-074 在 HC 侧 = no-op declaration，跳到 F3
- **若 HC 缺失 ≥1 分支** → 在本 spec 内补 F4 章节描述要补的分支，并写为 `IN-SCOPE patch`，不另开 spec

### F3 — 在 HC 索引层归档 SPEC-074 = no-op declaration

**变更**：
1. `task/SPEC-074.md`（本文件）状态从 `DRAFT` → `DONE (no-op)`，并在 §变更记录写明核查日期与 grep 结果
2. `sync/open_questions.md` `Q020`（如属同一根因）保持 `open`，并在备注引用本 spec 的 no-op 结论 —— **不**因 SPEC-074 DONE 而关闭 Q020；Q020 关闭仍以 `tieout #2` 收敛为依据
3. `PROJECT_STATUS.md` 不新增条目；no-op spec 不算 build-up

### F4 — （仅在 F2 发现缺失时启用）补齐 select_strategy 缺失分支

预留位。如 F2 比对未发现缺失，本节作废。

---

## In Scope

| 项目 | 说明 |
|---|---|
| F1 grep 核查 | 一行命令验证 |
| F2 逐行 diff | 需要 PM 提供 MC 等价文件或节选 |
| F3 索引层归档 | 仅文档变更 |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 引入新 `_backtest_select` wrapper | HC 无此函数；引入只会制造未来分叉 |
| 修改 `select_strategy` 任何 behavior（除 F4 缺失分支补齐外） | 行为对齐应通过 SPEC-077 / 080 等单独 spec 处理 |
| 关闭 `Q020` | 以 tieout #2 收敛为依据，不以 SPEC-074 DONE 为依据 |
| 修改 prototype 脚本 | frozen 历史快照 |

---

## 边界条件与约束

- **回归口径**：F1 / F2 / F3 全部 no-op 时，`run_baseline.py` 输出必须 byte-identical（trade_log / metrics / strikes 完全一致）
- **F4 触发时**：必须重跑 baseline 并将 diff 列入 §变更记录，且必须先重跑 `tieout #2` 才能 close
- **不进入产线 toggle**：本 spec 不引入任何 `params.*` 字段，不影响 production config

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| MC SPEC-074 文本 | PM 单独提供 | F2 比对源 |
| HC `select_strategy` | strategy/selector.py:543+ | F2 比对目标 |
| `doc/baseline_2026-04-24/` | 已生成 | F3 验证 byte-identical 的对照 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `grep -rn "_backtest_select" backtest/` 返回 0 行（prototype 路径除外） | grep 实测 |
| AC2 | F2 diff 列表归档于本 spec §变更记录 | 文档变更 |
| AC3 | 若 F2 无缺失，状态写为 `DONE (no-op)` 且 `sync/open_questions.md` Q020 仍 `open` | 文档审查 |
| AC4 | 若 F4 触发，必须先跑 tieout #2 并列出 trade-level diff | tieout 重跑 |
| AC5 | `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md` §3.5 / §9 在本 spec 内被显式引用 | 文档审查 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-01 | Quant 起草；F1 grep 已实测无命中；F2 待 PM 提供 MC 等价文件 | DRAFT |
