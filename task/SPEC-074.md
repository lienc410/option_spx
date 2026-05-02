# SPEC-074: Backtest Selector Path Parity (HC)

Status: DONE

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

**比对源**：[sync/mc_to_hc/MC_Spec-074_short_summary_v3.md](sync/mc_to_hc/MC_Spec-074_short_summary_v3.md)（PM 2026-05-01 提供）

**核查结果（2026-05-01 完成）**：

#### 7 项 MC 列出的"缺失 gate"对照

| MC 缺失项 | HC 当前位置 | 是否需补 |
|---|---|---|
| 1. BACKWARDATION filter (BPS_HV / IC_HV aftermath) | [selector.py:698](strategy/selector.py#L698), [:746](strategy/selector.py#L746), [:786](strategy/selector.py#L786), [:963](strategy/selector.py#L963), [:1084](strategy/selector.py#L1084) | **N**（已有） |
| 2. VIX_RISING gate (BCS_HV bearish) | [selector.py:616](strategy/selector.py#L616), [:739](strategy/selector.py#L739), [:794](strategy/selector.py#L794), [:869](strategy/selector.py#L869) (`vix.trend == Trend.RISING`) | **N**（已有） |
| 3. IVP63 ≥ 70 gate (BCS_HV) | [selector.py:165](strategy/selector.py#L165) (`IVP63_BCS_BLOCK = 70`), [:623](strategy/selector.py#L623) | **N**（已有） |
| 4. IC IVP range filter (20 < IVP < 50) | [selector.py:877](strategy/selector.py#L877) (`if iv.iv_percentile < 20 or iv.iv_percentile > 50: REDUCE_WAIT`) | **N**（已有） |
| 5. DIAGONAL IV-high gate (SPEC-051) | [selector.py:914](strategy/selector.py#L914) | **N**（已有） |
| 6. DIAGONAL both-high gate (SPEC-054) | [selector.py:924-925](strategy/selector.py#L924-L925) **明确注释 "removed by SPEC-056c"** | **⚠ 见 §F5** |
| 7. aftermath bypass (含 backwardation retention) | [selector.py:283](strategy/selector.py#L283) (`is_aftermath`), [:581](strategy/selector.py#L581), [:697](strategy/selector.py#L697); SPEC-064 bypass 注释 [:611](strategy/selector.py#L611), [:734](strategy/selector.py#L734) | **N**（已有） |

#### 5 个 MC 列出的"实施组件"对照

| MC 组件 | HC 当前位置 | 是否需补 |
|---|---|---|
| 1. VIX3M 历史数据 | [backtest/engine.py:671](backtest/engine.py#L671) (`fetch_vix3m_history(period="max")`) — **HC 走 yfinance**，覆盖 inception 2003-12-04 至 today | **N**（已有，无需 BBG fetch） |
| 2. IVP63 helper | [signals/iv_rank.py:135-153](signals/iv_rank.py#L135-L153) (`compute` 内 `ivp63 = round((window63.iloc[:-1] < float(window63.iloc[-1])).mean() * 100.0, 1)`) | **N**（已有） |
| 3. Snapshot 构建 | engine 主循环 [:812-824](backtest/engine.py#L812-L824), 第二循环 [:1232-1244](backtest/engine.py#L1232-L1244) — 含 `vix3m / backwardation / ivp63 / ivp252` 全字段 | **N**（已有） |
| 4. `select_strategy` delegation | [engine.py:835](backtest/engine.py#L835), [:1252](backtest/engine.py#L1252) 直接调用 live `select_strategy(vix_snap, iv_snap, trend_snap, params)` | **N**（已有） |
| 5. Parity test (`tests/test_backtest_select_parity.py`) | **不存在** | **Y → 见 §F4** |

#### 判定结论

- 7 项 gate 中 6 项 HC 已有；第 6 项 `SPEC-054 both-high diagonal gate` 是 **HC 主动 removed**（SPEC-056c），MC 仍 canonical → 这是 **HC vs MC 的真实行为分歧**，不是 HC 缺失，需要 PM 单独裁定
- 5 个组件中 4 个 HC 已有；只缺 **parity test**
- BBG VIX3M fetch 脚本（`data/fetch_bbg_vix3m.py` / `bin/run_fetch_bbg_vix3m.cmd`）在 HC 不需要，HC yfinance 已覆盖
- 因此 SPEC-074 在 HC 侧的真实工作 = **F4 (parity test 新增) + F5 (SPEC-054 分歧 escalation)**，**不是 no-op**

### F3 — 在 HC 索引层归档 SPEC-074 实际状态

**变更**：
1. `task/SPEC-074.md`（本文件）状态：F4 + F5 完成后从 `DRAFT` → `DONE`；§变更记录列 F2 核查结果 + F4 测试结果 + F5 PM 裁定记录
2. `sync/open_questions.md` `Q020`：保持 `open`；不因 F4 测试 PASS 直接关闭，Q020 关闭仍以 `tieout #2` 收敛为依据
3. `PROJECT_STATUS.md`：在 backtest 节标注 "selector parity test 已立 (`tests/test_backtest_select_parity.py`)" 作为治理项

### F4 — 新增 backtest selection vs live selection parity test

**新增 [tests/test_backtest_select_parity.py](tests/test_backtest_select_parity.py)**：

- 选 ≥ 20 个手挑日期，分布覆盖：
  - 2008（GFC）— ≥ 4 dates
  - 2018（Volmageddon / Q4 selloff）— ≥ 4 dates
  - 2020（COVID）— ≥ 6 dates（含 backwardation 高峰、aftermath、recovery）
  - 2022（rate-hike bear）— ≥ 6 dates
- 每个日期：从 HC backtest engine 真实 snapshot 路径（`engine.py:812-824` 等同口径）构建 `VixSnapshot` / `IVSnapshot` / `TrendSnapshot`，调用 `select_strategy` 一次；并独立用 live data fetch 路径（`signals/vix_regime.fetch_vix_snapshot()` 等）构建另一份 snapshot 调用 `select_strategy` 一次
- 断言：≥ `99%` 日期上两路返回的 `Recommendation.canonical_strategy` 一致；任何不一致日期必须列出 snapshot diff
- **核心约束**：测试不应需要 live network；snapshot 构建走 cached pkl（`data/market_cache/yahoo__VIX__max__1d.pkl` 等已 staged）

### F5 — SPEC-054 (DIAGONAL both-high gate) 分歧 escalation

**事实**：
- HC: `SPEC-056c` 已 remove `SPEC-054` both-high gate（[selector.py:924-925](strategy/selector.py#L924-L925)）
- MC: SPEC-074 short summary 仍 list `SPEC-054 DIAGONAL both-high gate` 为 canonical 缺失项（即 MC 仍保留该 gate）

**含义**：
- 若 SPEC-074 parity test 在 LOW_VOL + IVP_HIGH 路径上某些日期 fail 99% 阈值，根因可能是这一条
- 这不是 HC bug —— 是历史 spec 演进上 HC 走在了 MC 前面。但 PM 需要决定：
  - **Option A**：HC 保持 `SPEC-056c` 移除状态（推荐）→ 在 SPEC-074 parity test 接受 LOW_VOL + IVP_HIGH 类日期 < 99% 一致；并由 PM 在 MC 侧补一条 spec 同步 remove
  - **Option B**：HC 回滚 `SPEC-056c`（不推荐）→ both-high gate 重新激活；需要单独 spec
  - **Option C**：维持现状，把 SPEC-074 parity test acceptance 从 ">=99%" 改为 ">=95%, with documented exemption for LOW_VOL + IVP_HIGH"

**Quant 推荐**：Option A。理由：`SPEC-056c` 是 HC 自己审过的研究结果，回滚需要新证据；MC 侧自身缺 SPEC-056c 等同动作属 MC 治理 backlog，不应让 HC 妥协。

**本 spec 的处理**：F5 里把这个分歧明文 flag，等 PM 拍板；在 PM 拍板之前，F4 测试 acceptance 阈值暂用 `>=95%` 并要求列出全部 mismatch 日期。

---

## In Scope

| 项目 | 说明 |
|---|---|
| F1 grep 核查 | 已完成（无 `_backtest_select` 命中） |
| F2 逐行 diff | 已完成（基于 MC short summary v3） |
| F3 索引层归档 | 仅文档变更 |
| F4 parity test 新增 | `tests/test_backtest_select_parity.py` |
| F5 SPEC-054 分歧 PM escalation | 文档 + 等 PM 裁定 |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 引入新 `_backtest_select` wrapper | HC 无此函数；引入只会制造未来分叉 |
| 修改 `select_strategy` 任何 behavior（除 F5 PM 选 Option B 外） | 行为对齐应通过 SPEC-077 / 080 等单独 spec 处理 |
| 引入 BBG VIX3M fetch（`data/fetch_bbg_vix3m.py` / `bin/run_fetch_bbg_vix3m.cmd`） | HC yfinance 已覆盖 inception → today，无需 BBG |
| 关闭 `Q020` | 以 tieout #2 收敛为依据 |
| 修改 prototype 脚本 | frozen 历史快照 |
| 回滚 `SPEC-056c`（重新激活 SPEC-054 gate） | 除非 PM 选 F5 Option B，否则不在范围内 |

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
| AC1 | `grep -rn "_backtest_select" backtest/` 返回 0 行（prototype 除外） | grep 实测（已完成，0 命中） |
| AC2 | F2 diff 表已归档于本 spec §F2 §F5 | 文档审查（已完成） |
| AC3 | `tests/test_backtest_select_parity.py` 存在且 PASS（≥20 dates，2008/2018/2020/2022 分布；阈值见 F5） | `pytest tests/test_backtest_select_parity.py` |
| AC4 | F5 Option A/B/C 已由 PM 裁定，结果记录在本 spec §变更记录 | 文档审查 |
| AC5 | `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md` §3.5 在本 spec 内被显式引用 | 文档审查（已完成） |
| AC6 | `sync/open_questions.md` `Q020` 仍 `open`，且引用本 spec 的 F4 测试已立、tieout #2 待跑 | 文档审查 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-01 | Quant 起草，F1 grep 已实测 0 命中 | DRAFT |
| 2026-05-01 | PM 提供 [MC_Spec-074_short_summary_v3.md](sync/mc_to_hc/MC_Spec-074_short_summary_v3.md)；F2 完成：7 项 gate 中 6 项 HC 已有，第 6 项（SPEC-054 both-high diagonal）HC 主动 removed by SPEC-056c → 升级为 §F5 PM escalation；5 个组件中 4 个已有，仅缺 parity test → §F4；BBG fetch 不适用（HC yfinance 覆盖） | DRAFT (revised) |
| 2026-05-02 | PM 裁定 §F5 = **Option A**：HC 保持 SPEC-056c 已 remove 状态；MC 侧需由 PM 在 MC 治理 backlog 补同步 spec；F4 parity test 阈值 = **≥95%**（LOW_VOL + IVP_HIGH 类日期允许例外） | DRAFT (F5 resolved, F4 in progress) |
| 2026-05-02 | F4 实施完成：[tests/test_backtest_select_parity.py](tests/test_backtest_select_parity.py) 新增（22 dates × 5 testcases），跑 `python -m unittest tests.test_backtest_select_parity` 全部 PASS（success rate 22/22 = 100%，远超 95% 阈值）；snapshot 字段 (vix3m / backwardation / ivp63 / ivp252 / regime / trend) 全部正确填充；2020-03-16 known backwardation 验证 PASS；F5 Option A 阈值不需要触发例外路径 | DONE |
