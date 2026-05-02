# SPEC-077: profit_target Default Lift to 0.60 + stop_mult Wiring Verification

Status: DONE (2026-05-02; AC3 全样本未达 — PM 选项 (2) 操作性 MC 对齐，量级差距调查 deferred 至 SPEC-080 wire debit-side `params.stop_mult` 之后)

## 目标

**What**：将 HC `StrategyParams.profit_target` 默认值从 `0.50` 提升到 `0.60`；同时核查 / 锁定 `stop_mult` 在 backtest engine 内的 wire-through 路径，使 HC 与 MC 的 production 默认配置对齐。

**Why**：
- MC `SPEC-077 DONE` 的 production config 是 `profit_target=0.60` + `stop_mult` engine wired through。HC 当前默认仍是 `profit_target=0.50`（[strategy/selector.py:68](strategy/selector.py#L68)）
- `Q037 Phase 2A` 实证支持 `0.60`：全样本 ann ROE `+0.91 ~ +1.03pp` vs `0.50`，sharpe / drawdown 同向改善
- HC 3y backtest tieout 残余差异最大单项预计落在此处（assessment §3.5 Cause A，估约 50%）
- `stop_mult` 在 HC `backtest/engine.py:880` credit 侧已读 `params.stop_mult`，但 debit 侧 line 882 仍硬编 `-0.50`。该硬编码的修复属于 SPEC-080 的 BCD 范围，不在本 spec 内动；本 spec 仅 (a) 调 default、(b) 加 unit test 锁定 credit-side wiring 不被回退、(c) 显式标注 debit-side 由 SPEC-080 处理
- 详见 `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md` §3.5 / §9

---

## 核心原则

- **只动 default 值 + 加 test，不动 engine 行为**：default lift 是 config change；wiring verification 是 governance test
- **不在本 spec 内改 debit-side 硬编码**：那是 SPEC-080 的 BCD 范围，本 spec 显式 punt
- **toggle 不引入**：`profit_target` 历来就是 `StrategyParams` 字段，可由 PM / 研究脚本覆盖；不需要新 toggle

---

## 功能定义

### F1 — `profit_target` 默认值 0.50 → 0.60

**[strategy/selector.py:68](strategy/selector.py#L68)**：

当前：
```python
profit_target:      float = 0.50   # close at this fraction of max credit
```

修改后：
```python
profit_target:      float = 0.60   # close at this fraction of max credit (SPEC-077; Q037 Phase 2A 实证)
```

### F2 — 添加 unit test 锁定 `params.stop_mult` 被 engine credit 侧读取

**新增 [tests/test_engine_stop_wiring.py](tests/test_engine_stop_wiring.py)**：

测试至少包含两条 case：
1. **credit trade**：构造一个已开仓的 credit position，设置 `params.stop_mult = 1.5`，喂入触发 `pnl_ratio = -1.6` 的市场快照，断言 `exit_reason == "stop_loss"`；将 `stop_mult = 3.0` 时同一快照断言 **不** 触发 stop
2. **debit trade**：构造一个 debit position，断言 `pnl_ratio = -0.50` 触发 stop（验证 line 882 硬编码当前行为）；同时在测试 docstring 内引用 SPEC-080 说明该硬编码将由 SPEC-080 替换

测试位置：`tests/`（与现有 unit test 同目录）。如 fixtures 不便构造完整 position，可直接调用 engine 内的 `_current_value` + 手写 `Position` dataclass。

### F3 — Production config baseline 文件更新

**[doc/baseline_2026-04-24/](doc/baseline_2026-04-24/)** 或后续 baseline 目录：

- 在 baseline run script 内显式写 `profit_target=0.60`（或在 baseline 文档里说明已切换默认，旧 baseline 用 `profit_target=0.50` 保留为历史对照）
- baseline metrics 重生成：trade count / total_pnl / max_drawdown / sharpe 全部更新
- 旧 baseline 不删除，作为 "default lift before/after" 的对照

### F4 — `RESEARCH_LOG.md` / `PROJECT_STATUS.md` 索引更新

- `RESEARCH_LOG.md`：新增条目 "SPEC-077 default lift 0.50→0.60"，引用 `Q037 Phase 2A` 数据 + assessment §3.5 / §9
- `PROJECT_STATUS.md`：在 backtest config 节标注当前 `profit_target=0.60`（当前可能还停留在 0.50 描述）

---

## In Scope

| 项目 | 说明 |
|---|---|
| F1 default 调整 | selector.py 一行 |
| F2 unit test | credit-side wiring + debit-side current behavior |
| F3 baseline 更新 | 重跑 baseline；保留旧版作对照 |
| F4 索引更新 | RESEARCH_LOG / PROJECT_STATUS |

## Out of Scope

| 项目 | 理由 |
|---|---|
| debit 侧 line 882 硬编码 `-0.50` 替换 | SPEC-080 BCD 范围 |
| `stop_mult` 默认值改动 | 默认 `2.0` 与 MC 一致，无需调 |
| `profit_target` 0.65 候选研究 | `Q037` deferred 项，等 4-8 周 live `0.60` 观察期 |
| `min_hold_days` 调整 | 与本 spec 无关 |
| dashboard ann ROE 表述更新 | SPEC-078 处理 |
| BCD comfort filter | SPEC-079 / 080 处理 |

---

## 边界条件与约束

- **回归口径**：本 spec **预期** 改变 trade outcome（profit_target 改了），所以不能要求 baseline byte-identical。验证 acceptance 应是 "ann ROE / sharpe / max_dd 改善方向与 Q037 Phase 2A 一致"
- **tieout #2 影响**：本 spec 落地后才能跑 tieout #2；tieout #2 残余差异中 Cause A 部分应消解
- **production toggle**：无新 toggle；现有 `production_config` 如果显式 override `profit_target=0.50` 必须同步改到 `0.60`，否则 default lift 会被覆盖回退

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| `Q037 Phase 2A` 数据 | `task/q037_phase2a_*.md`（如已存在）或 MC handoff 引用 | F1 实证依据 |
| 旧 baseline (`profit_target=0.50`) | `doc/baseline_2026-04-24/` | 对照 |
| 新 baseline (`profit_target=0.60`) | F3 重新生成 | 落地基线 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | [strategy/selector.py:68](strategy/selector.py#L68) `profit_target` 默认值为 `0.60` | grep 实测 |
| AC2 | `tests/test_engine_stop_wiring.py` 存在且 PASS（credit + debit 两 case） | `pytest tests/test_engine_stop_wiring.py` |
| AC3 | 新 baseline 与 `Q037 Phase 2A` 数据方向一致（ann ROE 改善 ≥ +0.5pp 全样本，sharpe 不退化） | 数据比对 |
| AC4 | `RESEARCH_LOG.md` / `PROJECT_STATUS.md` 已更新 `profit_target=0.60` | 文档审查 |
| AC5 | `production_config`（如有）`profit_target` 字段同步到 `0.60` | grep 实测 |
| AC6 | 测试 docstring 内显式引用 SPEC-080 处理 debit-side 硬编码 | 代码审查 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-01 | Quant 起草；F1/F2 范围确认；engine credit-side wiring 已实测在 line 880 | DRAFT |
| 2026-05-02 | PM 审批 → APPROVED；进入实施 | APPROVED |
| 2026-05-02 | F1 落地 [strategy/selector.py:68](strategy/selector.py#L68) `profit_target=0.60`；production_config 同步 [web/server.py:1272/1309](web/server.py#L1272) | APPROVED |
| 2026-05-02 | F2 落地 [tests/test_engine_stop_wiring.py](tests/test_engine_stop_wiring.py) — 5 testcases PASS（credit-side `params.stop_mult` 引用锁定 + debit-side `-0.50` 当前行为锁定，docstring 引用 SPEC-080） | APPROVED |
| 2026-05-02 | F3 baseline rerun 完成 [doc/baseline_2026-05-02/](doc/baseline_2026-05-02/)。3.3y 窗口结果方向 **混合**：max DD 改善 +$958（与 Q037 一致），但 realized PnL -$13,276 / Sharpe -0.29（与 Q037 不一致；2 winners 仍 open 未实现）。AC3 全样本验证仍依赖 Q037 Phase 2A，**等 PM AC3 裁定**后再关 DONE | APPROVED |
| 2026-05-02 | F4 RESEARCH_LOG / PROJECT_STATUS 已更新；R-20260502-01 录入 | APPROVED |
| 2026-05-02 | **AC3 全样本 HC rerun 完成** (`doc/baseline_2026-05-02/run_ac3_fullsample.py`，start=`2007-01-01`，period=`19.32y`)。结果：Δ ann_roe = `+0.0856pp` (PT=0.50→0.60)，远低于 Q037 Phase 2A 报道的 `+0.91~+1.03pp` 区间，也未达到 SPEC-077 AC3 阈值 `≥+0.5pp`。Δ sharpe = `0.00`（非退化 ✓），Δ max_dd = `-$850`。**AC3 FAIL**。HC ↔ MC 在该实验上的 ~10× 量级差距怀疑落在 (a) 复利口径（HC 用 fixed `$100k` baseline，可能 MC compound）；(b) debit-side hardcoded `-0.50` stop（line 882，待 SPEC-080 wire）影响 BCD 与 PT 互动；(c) SPEC-054 / SPEC-056c 永久分歧带来的 trade-mix 差异。需要 PM 选择路径：(1) 暂停 SPEC-077 DONE，先开 quant 调查 HC↔MC 量级差距；(2) 接受 SPEC-077 操作性 MC 对齐（rule lift + wiring）但显式 acknowledge AC3 全样本未达，闭 DONE；(3) revert 默认到 `0.50` | APPROVED — AC3 BLOCKED |
| 2026-05-02 | **PM 选项 (2) — 操作性 MC 对齐 + AC3 全样本未达 acknowledged → DONE**。F1 / F2 / F3 / F4 / F5 全部交付；AC1 / AC2 / AC4 / AC5 / AC6 PASS；**AC3 documented FAIL**（`+0.0856pp` < `+0.5pp` 阈值，未进 Q037 band `+0.91~+1.03pp`）。HC↔MC 量级差距调查 deferred：理由是 SPEC-080 wire debit-side `params.stop_mult` 后再 rerun 才能区分 (a) 复利 / (b) debit-stop 硬编 / (c) SPEC-054 永久分歧三因素。本 spec 闭 DONE 不阻塞 tieout #2；量级差距由 future spec（暂记 SPEC-080-followup 或 Q040）跟踪 | DONE |
