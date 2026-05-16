# SPEC-103: Global Sleeve Stress Governance

Status: DONE (Developer implementation 2026-05-15) — implementation review pending

## Design Source

This is a **research-driven Spec**.

Design substance:
- **Quant Researcher**: Q072 Sleeve Global Evaluation full chain (P1-P4)
  - `research/q072/q072_research_brief_2026-05-15.md`
  - `research/q072/q072_p1_findings_2026-05-15.md` — episode detection & capital stack
  - `research/q072/q072_p2_findings_2026-05-15.md` — entry profile & HV background
  - `research/q072/q072_p3_findings_2026-05-15.md` — path / co-loss / scenario decomp
  - `research/q072/q072_p4a_findings_2026-05-15.md` — SPX pool ablation
  - `research/q072/q072_p4c_consolidated_findings_2026-05-15.md` — 5-allocator simulation
  - `research/q072/q072_final_memo_2026-05-15.md` — final memo (verdict + recommendation)
- **2nd Quant Reviewer**: 2 rounds PASS WITH REVISIONS — all incorporated
  - `task/q072_sleeve_global_eval_design_review_2026-05-15_Review.md`
  - `task/q072_priority_scoring_2nd_quant_review_packet_2026-05-15_Review.md`
  - Final closure verdict: **APPROVE — close Q072 with "Augmented Default Cap" recommendation. Do not promote priority allocator. Do not use static per-sleeve caps. Open a SPEC only for R5/R6 governance rules**
- **PM**: 2026-05-15 final verdict APPROVE; standing objective "reasonably maximize account-level ROE under explicit risk guardrails"

---

## 一句话目标

实施 portfolio-level sleeve stress governance：normal regime 保持默认 caps；stress episode 期间适度收紧 SPX cap；second-leg state 下硬停新增 short-vol 入场。**不实施 priority allocator**（Q072 P4C.4 实证 ≡ FCFS），**不实施 static per-sleeve cap**（Q072 P4C.4 实证 destroys winners without protecting tail）。

---

## 6 条 Governance Rules

### Normal Regime — R1-R4 hard caps

| Rule | Cap | 适用对象 |
|---|---|---|
| **R1** | SPX PM pool BP cap = **70% NLV** | SPX 账户内所有持仓总和 |
| **R2** | /ES SPAN cap = **80% NLV** | /ES 账户内 HV Ladder SPAN 总和 |
| **R3** | Combined economic cap = **60% combined NLV** | SPX BP + /ES SPAN 合计 |
| **R4** | Max short-vol exposure = **50% combined NLV** | 所有短 vega/gamma sleeve（BPS_HV / IC_HV / Bear Call HV / HV Ladder）合计 |

19y backtest 中 R1-R4 几乎不 bind（< 5 days each）。设这些 cap 主要是给极端 NLV 增长场景留 safety margin。

### Stress Episode Throttle — R5

```
当 stress_episode_active == True:
    SPX PM pool cap → 60% NLV (down from 70%)
```

**Stress episode 定义**（沿用 Q072 P1 tight 口径）：
```
stress_flag = (VIX ≥ 22)
              OR (SPX dd_20d ≤ -4%)
              OR (SPX dd_60d ≤ -4%)
              OR (DD Overlay sleeve active)
              OR (Aftermath permission active)

stress_episode_active = stress_flag has been True within last 3 trading days
```

### Second-Leg Hard Stop — R6

```
当 second_leg_active == True:
    Block all NEW short-vol entries (see scope below)
    Allow: long-gamma entries, risk-reducing exits, rolls
```

**Second-leg state 定义**（Q072 P4C.0 实现）：
```
second_leg_active = (SPX 从 60d 高点回撤 ≥ 8%)
                    AND (过去 30 个交易日内有 ≥ 2% 中段反弹)
                    AND (VIX ≥ 25)
                    AND (days since current stress_episode start > 14)
```

19y 历史仅 fire 26 天（0.5% of trading days），全部集中在 2008-09 和 2022。

### R6 Scope — short-vol entries 范围

**必须 block**（new entries only）:
- HV Ladder 新 slot
- BPS_HV (Aftermath-permission-gated) 新入场
- IC_HV 新入场
- Bear Call HV 新入场
- 任何 main strategy 中的 short-vol 性质入场

**NOT 在 R6 block 范围**（允许通过）:
- Drawdown Overlay long-call-spread 入场（long delta / long gamma）
- 任何 risk-reducing exit / 平仓
- 任何 roll 操作（DTE rolling / strike rolling，本质上是 risk-neutral 或减仓）
- main strategy 中的 long-vol / long-gamma 入场

---

## Acceptance Criteria

### AC1 — Portfolio state tracker daemon
- 每日（或近实时）计算 portfolio BP per pool（SPX PM / /ES SPAN / combined）+ short-vol exposure
- 数据源：Schwab API 持仓 + ETrade API 持仓（已有 SPEC-089/090）
- 输出：`data/sleeve_governance_state.jsonl`（daily append）

### AC2 — Stress episode flag computation
- 实现 §R5 定义的 stress_episode_active boolean
- 数据源：VIX 实时（已有 SPEC-091 sidecar）+ SPX OHLC（已有）+ DD Overlay armed state（SPEC-094 已有）+ Aftermath flag（selector.py 已有）
- Backtest 验证：在 19y 历史上重算 stress_episode_active 序列，与 Q072 P1 输出 `q072_p1_daily_flags.csv.episode_id_tight` 100% 一致

### AC3 — Second-leg state flag computation
- 实现 §R6 定义的 second_leg_active boolean
- 数据源：SPX 60d rolling max + 30d rolling bounce detection + VIX + episode counter
- Backtest 验证：19y 历史重算与 Q072 P4C.0 输出 `q072_p4c0_portfolio_state.csv.second_leg` 一致（容差 ≤ 2 days，因实时实施可能 lag）

### AC4 — Entry decision gate
- 在 production entry decision 处插入 governance check（before order send）
- 决策树：
  ```
  1. 通过 R1-R4 (hard caps)? → no = REJECT log
  2. stress_episode_active == True AND 入场后 SPX BP > R5 cap? → REJECT log
  3. second_leg_active == True AND new entry is short-vol? → REJECT log
  4. 全部通过 → ACCEPT, send order
  ```
- 入场决策日志写 `data/sleeve_governance_decisions.jsonl`

### AC5 — Blocked-candidate logging
每个 blocked candidate 记录：
- timestamp
- sleeve / strategy / direction
- rule triggered (R1-R6)
- requested BP
- counterfactual scenario: 5d / 10d / 20d forward SPX return + estimated P&L if entered
- estimated BP saved
- subsequent reality: did similar entry fire later under different governance state?

### AC6 — Telegram alert on R6 fire
- 当 second_leg_active 从 False → True 转换时，Telegram 告警
- 当 R6 实际 block 任一 candidate 时，Telegram 告警（含 sleeve 与 counterfactual）
- 当 second_leg_active 从 True → False 转换（退出 second-leg）时，Telegram 告警

### AC7 — Web dashboard panel
Portfolio Command Center 加 governance 面板：
- 当前 stress_episode_active / second_leg_active 状态
- 当前 BP per pool vs cap（visual gauge）
- 当前 short-vol exposure vs R4 cap
- 最近 30 日 blocked candidates 列表
- 最近 90 日 stress_episode / second_leg 触发次数与时长

### AC8 — Backtest replay smoke test
- 用 SPEC-103 实现替换 Q072 P4C.4 simulator 内的 eligibility filter
- 重跑 19y baseline + DD + HV Ladder candidates
- 与 Q072 P4C.4 `priority allocator default cap` 结果 100% 数值一致（n_entered 872, total P&L $742k, max DD -$175k）
- 若不一致，说明 SPEC-103 实现 drift 自 Q072 spec，必须修正

### AC9 — Override mechanism (manual)
- PM CLI 命令 `manage_governance.py --pause --rule R6 --duration 1d`：暂停某条 rule 一段时间
- 所有 manual override 记录到 `data/sleeve_governance_overrides.jsonl`
- 默认无 override（rules 始终 active）

---

## 不在范围内

- **Priority allocator** — Q072 P4C.4 实证 19y 中 ≡ FCFS，不实施
- **Static per-sleeve caps** — Q072 P4C.4 实证 destroys $102k P&L 无 max DD 改善，不实施
- **HV Ladder 自身参数调整** — Q071 final lock 决定（SPEC-101 主导）
- **Aftermath threshold 调整** — Q070 已结论维持 28
- **DD Overlay sleeve 调整** — SPEC-094 已锁定
- **Backtest engine 大改** — SPEC-103 只在 entry decision 层 hook，不改 strategy engine

---

## Deferred Validation（不阻塞 SPEC closure）

实施 SPEC-103 不依赖以下两项；它们是 SPEC-103 部署后 6 个月内的 robustness check：

### Deferred 1: P4B /ES pool ablation rerun (Q071 lock 后)
- 用 Q071 final HV Ladder config 替换 V2f filtered placeholder
- 重跑 Q072 P4B 部分
- 决定 R2 /ES SPAN cap 是否需要从 80% 调整

### Deferred 2: P4C.7 full synthetic stress test
- 重放 2008-09 + 2022 SPX/VIX path
- Inject 当前 sleeve pack (DD + HV + Aftermath) 假定 100% 部署
- 跑 SPEC-103 R1-R6 全套 + B_tight 对照
- 决定 R5 / R6 阈值是否需要在真实 stress path 中调紧

---

## Implementation Plan (proposed)

| Phase | Scope | Owner |
|---|---|---|
| F1 | Portfolio state tracker daemon (AC1) | Developer |
| F2 | Stress + second-leg flag computation + backtest validation (AC2, AC3, AC8) | Developer + Quant |
| F3 | Entry decision gate hook (AC4) | Developer |
| F4 | Logging + Telegram (AC5, AC6) | Developer |
| F5 | Web dashboard panel (AC7) | Developer |
| F6 | Manual override CLI (AC9) | Developer |
| F7 | 6-month post-deploy review + deferred validation | Quant |

---

## Confidence

**High** — based on 19y backtest data, 2 rounds 2nd Quant review PASS, simulator-validated decision rules.

**Caveat**: 19y data lacks "current full sleeve pack + true second-leg" sample (5/6 of 4-sleeve episodes are post-2020 V-shape; 2008/2022 had no DD/HV deployed). SPEC-103 R5/R6 calibration is based on extrapolation from this gap. Deferred validation items address this.

---

## Related Documents

```
research/q072/q072_final_memo_2026-05-15.md         ← driver memo
research/q072/q072_p4c_consolidated_findings_2026-05-15.md ← P4C evidence
research/q072/q072_p3_findings_2026-05-15.md        ← P3 evidence
RESEARCH_LOG.md R-20260515-01                       ← Q072 research log
sync/open_questions.md Q072                         ← open question (to be marked resolved upon SPEC-103 approval)
SPEC-094 (DD Overlay)                                ← sleeve A
SPEC-064 (Aftermath permission gate)                ← sleeve B (permission module)
SPEC-101 (HV Ladder / ES High-Vol Sell Put Ladder)   ← sleeve C (awaiting Q071 final lock)
SPEC-091 (VIX settling sidecar)                     ← dependency for stress flag
SPEC-089/090 (Schwab/ETrade position read)          ← dependency for portfolio state
```

---

## Developer Implementation Record (2026-05-15)

Implemented:
- `strategy/sleeve_governance.py` centralizes R1-R6 caps, stress / second-leg replay validation, entry decision evaluation, decision logs, state snapshots, Telegram alert helpers, override handling, and dashboard payload.
- `scripts/sleeve_governance_daemon.py` records one governance state snapshot per run for launchd scheduling.
- `scripts/manage_governance.py` supports `--pause --rule R6 --duration 1d` and writes `data/sleeve_governance_overrides.jsonl`.
- `/api/position/open` now runs a governance gate before production state writes; paper trades are not hard-blocked.
- `/api/sleeve-governance/state` exposes the read-only dashboard carrier.
- Portfolio Command Center includes a Sleeve Stress Governance panel.
- `tests/test_spec_103.py` covers AC2/AC3/AC4/AC5/AC6/AC7/AC8.

Validation:
- `arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py scripts/sleeve_governance_daemon.py scripts/manage_governance.py web/server.py` → PASS
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_103 -v` → 8/8 PASS
- Smoke API check: `/api/sleeve-governance/state`, `/api/portfolio/summary`, `/api/recommendation` → HTTP 200 JSON
- Adjacent regression: `tests.test_spec_085` → PASS as part of grouped run.

Known unrelated regression debt observed during adjacent run:
- `tests.test_spec_089` still fails 2 existing E-Trade assertions unrelated to SPEC-103 (`portfolio_home` static text and existing market quote helper source scan).
