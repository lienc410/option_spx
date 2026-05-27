# SPEC-107: Intraday Recommendation Governance

Status: APPROVED (PM 2026-05-26) — awaiting Developer implementation (F1-F7)

## Design Source

This is a **research-driven Spec**.

Design substance:
- **Quant Researcher**: Q076 Intraday Recommendation Replay chain (P1-P3)
  - `research/intraday/q076_findings_2026-05-26.md` — P1 diagnostic (21-day jitter window, 15 hourly flips, IVP=55 hard-threshold root cause)
  - `research/intraday/q076_p2_findings_2026-05-26.md` — P2 6-variant mitigation replay (A2a + B chosen)
  - `research/intraday/q076_p3_findings_2026-05-26.md` — P3 robustness on 12-month sample (flips -54%, ≤3h -92%, EOD 93.2%)
- **2nd Quant Reviewer**: 4 rounds, all PASS/PASS-with-revisions, all incorporated
  - `task/q076_phase2_2nd_quant_review_2026-05-26.md` — P2 review (recommend 4-variant test)
  - `task/q076_phase2_2nd_quant_review_2026-05-26_Verdict.md` — PM verdict accepting A2a + B
  - P3 review (Quant accepted in full, esp. AC8 regression test addition)
  - `task/SPEC-107_2nd_quant_review_packet_2026-05-26_Review.md` — R4 round-1: SPEC-107 review (R1-R7 incorporated)
  - `task/SPEC-107_2nd_quant_review_packet_round2_2026-05-26_Review.md` — R4 round-2: implementation verification (E1-E7 micro-edits incorporated below)
- **PM**: 2026-05-26 verdict — "Q076 = execution governance only. Low-IVP semantics = separate research. 两个轨道，两个边界，不混."

---

## 一句话目标

把 `/api/recommendation` 的 intraday hourly output 从 "actionable 交易指令" 降级为 **state observation with scheduled actionable decisions**：默认每小时 UI 显示当前 state，但只在 **10:30 + 15:30 ET** 这两个 scheduled bar 把 recommendation 作为 actionable；同时在 selector 层叠加 **IVP hysteresis state machine**（per position）抑制 IVP=55 边界处的小时级抖动。Hard exits（SPEC-103 R5/R6 daemon、EXTREME_VOL、stop-loss、manual override）**bypass** scheduled-eval gate，保持即时。

**不改**：selector 内部策略 semantics（包括 low-IVP "Reduce/Wait" 在持仓时是否强制 close 的决定 —— 另开独立研究）。

---

## Scope

### A. A2a Hysteresis State Machine

Per-position state machine, applied as a wrap on top of selector recommendation：

**Entry band**（WAIT → BPS only when inside）:
- IVP ∈ [42, 53]
- AND selector baseline recommends Bull Put Spread with `position_action ∈ {"OPEN", "HOLD"}`

**Hold band**（BPS → BPS while inside）:
- IVP ∈ [35, 57]

**Close trigger**（BPS → WAIT when outside hold band）:
- IVP > 57 ALWAYS triggers close (upper-bound close, never gated)
- IVP < 35 triggers close **only when `hysteresis_lower_force_close=True`** (default — see R6 below)

**Override 优先级**: see new §F **Priority Order**.

**实施位置**：建议在 `strategy/sleeve_governance.py` 内新增 `intraday_governance.py` 模块或同文件下的 helper class，与 SPEC-103 governance 解耦。

**Configurable parameters**（不要硬编码；ENV / config file 可调）：
- `INTRADAY_HYS_ENTRY_LOW = 42.0`
- `INTRADAY_HYS_ENTRY_HIGH = 53.0`
- `INTRADAY_HYS_HOLD_LOW = 35.0`
- `INTRADAY_HYS_HOLD_HIGH = 57.0`
- `INTRADAY_HYS_LOWER_FORCE_CLOSE = True` ← **R6 future-compat flag**
  - Default `True`: matches current A2a production semantics (IVP < 35 forces close)
  - Setting `False` requires Q077 approval / separate SPEC; upper-bound (>57) close remains active regardless

**State persistence (R7 + E5)**：
- Hysteresis state MUST persist across process restart
- State key MUST include account / underlying / strategy / position id
- If no active position exists → state resets to WAIT
- Implementation: write state to `data/intraday_governance_state.json` **atomic write** on each transition (write to `.tmp` then `os.replace`)
- **State file corruption fail-safe (E5)**: if state file unreadable or schema-mismatch → fail safe to **raw selector / WAIT**, NOT stale BPS hold. Emit Telegram alert + log entry on corruption-detected fallback.

### B. Scheduled Actionable Evaluation

Default actionable cadence：**10:30 ET 和 15:30 ET**（two bars per trading day）。

**Outside scheduled bars**：UI 显示 current state observation，但不 emit actionable signal（无 Telegram, 无 banner, 无 order-staging）。

**Scheduled bars**：emit actionable signal（带 hysteresis state machine 输出）。

**Configurable**：
- `INTRADAY_SCHED_BARS_ET = ["10:30", "15:30"]`

**Timezone & Market Calendar (R7 + E6 + E7)**：
- Scheduled times are **America/New_York** (handles DST automatically)
- Actionable bars are the nearest available aligned bar at 10:30 and 15:30 ET
- **Calendar source (E6)**: MUST use NYSE trading calendar via `pandas_market_calendars` NYSE calendar OR existing project market-calendar utility. **Hand-written holiday lists are not acceptable** (drift risk).
- **Half-days / market holidays**: do NOT generate false scheduled decisions
  - Market holiday: 当日 0 sched decisions
  - **Early-close rule (E7, generalized)**: on early-close days, last scheduled actionable time MUST be at least **30 minutes before market close**. Default rule: 13:00 ET close → last actionable at 12:30 ET; for other close times, choose the closest aligned bar ≥ 30 min before close
  - 15:30 sched eval is skipped on any day where market closes before 16:00 ET

### C. Bypass List (R2 — 7 classes)

下列情况 **immediate actionable**, 不受 §A 状态机或 §B sched-eval 限制：

1. **Manual PM override** — governance CLI / web 触发的 immediate decision
2. **Broker / system stop-loss** — trade-level stop_loss 触发（broker-pushed margin call、liquidation 等系统级强平）
3. **Profit-taking / lifecycle exit** — 包括 roll / 51% profit target / DTE 21 close / expiration management
4. **SPEC-103 daemon hard rules** — R5 stress episode SPX cap reduce / R6 second-leg short-vol absolute block（已独立于 selector recommendation 运行 ✓）
5. **EXTREME_VOL / EXTREME_VIX** — VIX ≥ EXTREME_VIX (currently 40)，selector emit `Reduce / Wait` with EXTREME_VOL rationale
6. **Selector verdict explicitly marked `hard_exit=True`** — 包括 trend 突变如果 selector / governance 元数据上明示为 hard_exit；**普通 trend 翻转 NOT bypass** unless metadata flag set
   - **`hard_exit=True` discipline (E1)**: MUST be set only for immediate-risk exits (trade-level stop, regime-shock detection, data-integrity emergency). MUST NOT be set for ordinary strategy preference changes (e.g., selector switching from BPS to IC due to IVP normal fluctuation). Discipline enforced via code review at selector / governance code path level.
7. **Emergency data-quality / stale-data failsafe** — VIX feed stale > N min, Schwab quote unavailable, NLV / position read failure 等数据不可信场景

**显式 NOT bypass**:
- Trend BULLISH↔BEARISH 翻转（除非 selector / governance 元数据明示 `hard_exit=True`）
- DD Overlay armed state 变化 (daily evaluator, not emergency)
- Aftermath gate open/close (permission signal, not emergency)
- 任何 strategy-level signal change without `hard_exit` flag

**Bypass type enum** (for decision log R5):
```
{manual_override, broker_stop_loss, lifecycle_exit, spec_103_r5,
 spec_103_r6, extreme_vol, selector_hard_exit, stale_data_failsafe, null}
```

**Bypass list 实施**：在 actionable-decision pipeline 入口检查 bypass 条件；如任一条件成立，跳过 hysteresis state machine 和 sched-eval gate，直接 propagate selector / daemon 决策。

### D. Frontend Semantic Downgrade

#### Hourly recommendation card (every 1h bar)

**Outside scheduled bars**:
- 上方 label： `📊 State Observation · auto-evaluated at 10:30 / 15:30 ET`
- 内容：当前 state（BPS / Wait / Hold / 其他），current VIX / IVP / regime
- **无** "Open Now" / "Close Now" / "Action Required" 类型 actionable CTA
- Next actionable decision time 倒计时

**Scheduled bars (10:30, 15:30)**:
- 上方 label： `⚡ Actionable Decision`
- 标准 actionable CTA（与现行 production UI 一致）
- Banner 高亮（橙色或绿色，per existing convention）

#### Bypass events

任何 bypass list 事件触发：
- 红色 banner: `🚨 Hard Exit · {rule}` (SPEC-103 R6 / EXTREME_VOL / stop-loss / manual)
- 即时 actionable，不等 sched bar
- Telegram alert 立刻发

#### State Observation 与 Actionable 视觉区分

通过颜色 + label + interaction 三层区分：
- Observation: 灰底 / 灰文 / 不可点击 CTA
- Actionable: 高亮底色 / 强对比文字 / 可点击 / Telegram alert
- Hard exit: 红色高亮 / immediate Telegram

具体颜色 token 留给 frontend dev 按 `DESIGN.md` 选定。

### E. Decision Log

每次 governance 决策（不论是否 actionable）写入 `data/intraday_governance_log.jsonl`：

```json
{
  "timestamp": "2026-05-26T15:30:00-04:00",
  "bar_hm": "15:30",
  "is_scheduled_bar": true,
  "is_bypass_event": false,
  "bypass_reason": null,
  "vix": 16.94,
  "ivp252": 45.8,
  "regime": "NORMAL",
  "selector_baseline_strategy": "Bull Put Spread",
  "selector_baseline_position_action": "HOLD",
  "selector_baseline_rationale": "NORMAL + IV NEUTRAL + BULLISH ...",
  "hysteresis_state_prev": "Bull Put Spread",
  "hysteresis_state_new": "Bull Put Spread",
  "governed_strategy": "Bull Put Spread",
  "governed_position_action": "HOLD",
  "actionable": true,
  "override_baseline": false,
  "last_actionable_decision_at": "2026-05-26T10:30:00-04:00",
  "next_actionable_decision_at": "2026-05-27T10:30:00-04:00",
  "final_priority_layer": 5,
  "final_priority_name": "spec_107_scheduled_actionable",
  "bypass_type": null
}
```

字段含义：
- `is_scheduled_bar`: 是否在 §B sched bars 列表内
- `is_bypass_event`: 是否触发 §C bypass list
- `bypass_reason`: enum {`spec_103_r5`, `spec_103_r6`, `extreme_vol`, `stop_loss`, `manual_override`, null}
- `hysteresis_state_prev/new`: §A state machine 前后
- `governed_strategy/position_action`: 最终发给 UI / order pipeline 的决策
- `actionable`: UI 是否显示 actionable banner
- `override_baseline`: governed 决策 ≠ baseline 时为 True (审计用)

Decision log 用于：
1. Post-deploy retrospective（"governance 在过去 30 天 override 了多少次 baseline？"）
2. Bypass list 触发频率监控
3. AC7 backtest replay verification（重跑 12mo 数据 vs P3 数字）

### F. Priority Order (R1 — explicit hard-coded layering)

**Hard-risk layer always overrides intraday governance.**
**SPEC-107 may delay soft selector churn.**
**SPEC-107 may never delay hard-risk exits.**

Priority stack（按高到低，每个 candidate decision 按此顺序检查）：

| Priority | `final_priority_name` (E3) | Layer description | Source |
|---|---|---|---|
| 1 | `manual_override` | Manual PM override | governance manage CLI / web |
| 2 | `broker_stop_loss_or_lifecycle` | Broker/system stop-loss + lifecycle exits | trade lifecycle (stop / roll / profit-take / expiration) |
| 3 | `spec_103_hard_risk_daemon` | SPEC-103 hard-risk daemon | R5 stress episode / R6 second-leg block |
| 4 | `extreme_vol` | EXTREME_VOL / EXTREME_VIX | selector hard exit at VIX ≥ 40 |
| 5 | `spec_107_scheduled_actionable` | SPEC-107 scheduled actionable decision | sched bar 10:30 / 15:30 ET |
| 6 | `spec_107_hysteresis` | SPEC-107 hysteresis state | A2a state machine |
| 7 | `raw_selector` | Raw selector recommendation | passthrough when neither schedule nor hysteresis applies |

**Implementation rule**: 每个 candidate evaluation 按 1→7 顺序检查。第一个 returns non-None 的 layer **wins**。
- Layers 1-4 (priorities 1-4) 通过 §C bypass list 实现 → return immediate actionable
- Layer 5 (scheduled) 仅在 sched bar 触发 → return actionable signal
- Layer 6 (hysteresis) 维护 internal state → return state-machine output
- Layer 7 (raw) 在所有上层都 None 时 fallback

**Mandatory unit test** (in AC3):
> Given SPEC-107 layer 6 hysteresis says "OPEN/HOLD BPS" AND SPEC-103 R6 (layer 3) says "BLOCK/CLOSE",
> final action MUST be "BLOCK/CLOSE" (layer 3 wins).

---

## Acceptance Criteria

### AC1 — A2a hysteresis state machine
- 在 `strategy/sleeve_governance.py` 或新模块实施 entry/hold band state machine
- 参数 (`INTRADAY_HYS_*`) configurable via module constants 或 ENV
- Per-position state（不同账户/不同 sleeve 各自跟踪）
- **State persistence (R7)**: state 跨 process restart 必须 persist
  - State key MUST include account / underlying / strategy / position id
  - 如无 active position → state resets to WAIT
  - 实施：`data/intraday_governance_state.json` atomic write on each transition
- Unit tests: 覆盖 entry band / hold band / 上沿 close / 下沿 close / 跨 hold band 切换 / process restart 后 state 恢复

### AC2 — Scheduled actionable cadence
- Default `INTRADAY_SCHED_BARS_ET = ["10:30", "15:30"]`
- 实现在 actionable-decision pipeline；non-sched bars 不 emit Telegram, 不 emit actionable UI banner
- Configurable via module constant
- **Timezone (R7)**: scheduled times are America/New_York (DST automatic)
- **Half-days / market holidays (R7)**: do NOT generate false scheduled decisions
  - 早收市日 (e.g., 13:00 close): 15:30 sched eval 自动 skip; 最后 actionable check 落在 12:30
  - Market holiday: 当日 0 sched decisions
- Unit tests: 覆盖 regular trading day / half-day / market holiday / DST transition

### AC3 — Bypass list enforced + priority order (R1+R2)
- 在 actionable-decision pipeline 入口按 §F priority stack 顺序检查
- 任一上层 bypass 成立 → 跳过 hysteresis + sched-eval gate，直接 return that layer's decision
- §C 7 类 bypass 全部实现：
  1. Manual PM override
  2. Broker/system stop-loss + lifecycle exits
  3. SPEC-103 daemon R5/R6
  4. EXTREME_VOL / EXTREME_VIX
  5. selector `hard_exit=True` metadata
  6. Stale-data failsafe
  7. (Layer 1 contains manual; layer 2 contains stop-loss + lifecycle; etc. — see §F table)
- **Trend BULLISH↔BEARISH 翻转 NOT bypass** unless metadata `hard_exit=True`
- **DD Overlay armed state change NOT bypass**
- Unit tests 覆盖 7 类 bypass 各自独立触发的场景
- **Mandatory priority test (R1)**:
  > Given SPEC-107 layer 6 hysteresis emits "OPEN/HOLD BPS" AND SPEC-103 R6 emits "BLOCK/CLOSE",
  > final action MUST equal "BLOCK/CLOSE" (layer 3 wins).
- Integration: 与 SPEC-103 governance daemon 路径解耦验证

### AC4 — Frontend State Observation label
- Hourly recommendation card 在 non-sched bars 显示 `📊 State Observation · auto-evaluated at 10:30 / 15:30 ET`
- 无 actionable CTA buttons 在 non-sched bars
- 倒计时显示 next actionable time

### AC5 — Actionable banner only on scheduled bars or bypass events
- `⚡ Actionable Decision` banner 仅在 10:30 / 15:30 ET 或 bypass event 出现
- `🚨 Hard Exit` banner 仅在 bypass event 出现（红色高亮）
- 任何 actionable banner 同步触发 Telegram alert

### AC6 — Decision log with full fields (R5 + E2 + E3)
- `data/intraday_governance_log.jsonl` 每次决策一行
- 字段集合见 §E + 以下 5 个新增字段（必须从 day-1 就写入，避免 JSONL schema drift）:
  - `last_actionable_decision_at` — last sched-bar or bypass actionable decision timestamp
  - `next_actionable_decision_at` — **normally non-null** (E2)
    - During market hours: next scheduled actionable bar today if remaining
    - After 15:30 ET: next trading day's 10:30 ET (from NYSE calendar)
    - On market holiday: next valid trading day's 10:30 ET
    - For bypass event: still populate next scheduled decision (bypass itself is immediate; next sched continues)
    - **Null ONLY** when calendar utility fails — MUST emit `stale_data_failsafe` log entry simultaneously
  - `final_priority_layer` — int 1-7, which §F layer won
  - `final_priority_name` — readable string (E3): `"manual_override"`, `"broker_stop_loss_or_lifecycle"`, `"spec_103_hard_risk_daemon"`, `"extreme_vol"`, `"spec_107_scheduled_actionable"`, `"spec_107_hysteresis"`, `"raw_selector"`
  - `bypass_type` — enum per §C bypass_type values, or null
- Append-only，daily 轮转或按 size 轮转

### AC7 — 12mo backtest replay matches P3 numbers (tightened per R3)
- 用 SPEC-107 实施替换 P3 simulator 内的 governance 逻辑
- 重跑 12mo aligned data (`spx_vix_1h_aligned_12mo.pkl`)
- 与 `q076_p3_metrics_overall.csv` 的 A2a+B 行比对：
  - `intraday_flips` = 93 ± 5
  - `episodes_le_3h` ≤ 4 ← **tightened from "3 ± 1"**
  - `eod_agreement_pct` ≥ **92%** ← **tightened from ≥90%**; P3 actual 93.2%, leaves 1.2pp slack
  - `round_trips` = 18 ± 2
- 若任一指标超 tolerance → SPEC 实施 drift 自研究结论，必须修正

### AC8 — HIGH_VOL / STRESS regime regression test (strengthened per R4 — two-layer)

**AC8a — Real replay regression (using P3 12mo subset)**:
- HIGH_VOL bars (VIX 22-30, n=203): governed_strategy 与 baseline_strategy 一致 (defer to selector)
- STRESS bars (VIX ≥ 30, n=10): 同上
- **0 BPS episodes generated by hysteresis** in these regimes

**AC8b — Synthetic / fuzz architectural invariant test**:
Construct synthetic inputs:
```
VIX regime = HIGH_VOL or STRESS (e.g., VIX 23, 27, 32)
IVP values around boundaries: 33, 35, 37, 42, 45, 50, 53, 57, 60
prior governance state = "Bull Put Spread"
raw selector verdict = non-BPS (Iron Condor / Iron Condor HV / Bear Call HV / Reduce / Wait)
```

**Assert (architecture invariant)**:
> SPEC-107 hysteresis MUST NOT convert a non-BPS selector verdict into "Bull Put Spread hold/open"
> in HIGH_VOL or STRESS regime, regardless of IVP value or prior governance state.

- 用途：锁定 P3 关键 invariant；防止未来调整 hysteresis band 时意外破坏；测试架构 invariant 而非仅历史样本

### AC9 — Forward-compat config flag (R6 + E4)
- `INTRADAY_HYS_LOWER_FORCE_CLOSE` config flag default `True`
- When `True`: IVP < 35 forces BPS close (current A2a production semantics)
- When `False`: IVP < 35 does NOT force close existing BPS; remains entry-only filter (future Q077 semantics)
- Upper-bound (IVP > 57) close **always active**, never gated by this flag
- SPEC-107 ships with default `True`
- **Changing this flag in production requires Q077 approval / separate SPEC** — write this constraint into config file comment + module docstring
- **Runtime observability (E4)**: if `INTRADAY_HYS_LOWER_FORCE_CLOSE` is observed to differ from the SPEC default `True` at module init or config reload, MUST:
  1. Emit Telegram alert with message identifying the override
  2. Write a `flag_override_detected` event to decision log
- Unit tests: 覆盖 `True` 和 `False` 两种行为 + flag-change alert path

---

## 不在范围内

- **Trade lifecycle operations** — SPEC-107 governs recommendation/actionability only. **Does NOT govern** profit-taking, stop-loss, roll, expiration management, manual close. Lifecycle ops bypass SPEC-107 via §C class 2/3.
- **Low-IVP semantics review** — IVP < 40 / 35 时是只 entry block 还是强制 close existing BPS？是 strategy semantics 问题，**另开 Q077 研究**，不进 SPEC-107. SPEC-107 通过 AC9 `INTRADAY_HYS_LOWER_FORCE_CLOSE` config flag 提供 future-compat hook.
- **Selector strategy logic 改动** — selector 决定推什么策略的 logic 不动；SPEC-107 只在外层 wrap governance
- **Daily backtest / strategy backtest** — A2a/B governance 只影响 intraday execution decision，不改动 daily backtest 结果（daily backtest 本身只在 EOD 评估）
- **/ES recommendation** — 当前 scope SPX 主策略 recommendation；/ES 有独立的 HV Ladder governance, 不在本 SPEC
- **SPEC-103 governance daemon 改动** — SPEC-103 R1-R6 与 SPEC-107 解耦运行；SPEC-103 通过 bypass list 处理；SPEC-103 daemon 本身不动
- **Hysteresis band sensitivity test** — Q7 deferred per 2nd Quant; bands configurable via config file; live shadow review at 1-3 mo post-deploy will inform calibration (Deferred 3)
- **Override 历史 audit UI** — 暂不做；decision log 文件足够；后续 SPEC 可补 UI

---

## Deferred validation（不阻塞 SPEC closure）

实施 SPEC-107 不依赖以下，但部署后 6 个月内做：

### Deferred 1: Live decision log retrospective
- 部署后 30 天：分析 `intraday_governance_log.jsonl`，统计：
  - Total actionable events
  - Override rate（governed ≠ baseline 的比例）
  - Bypass event 频率（4 类各多少次）
  - Sched bar vs non-sched bar decision 分布
- 若 override rate 远高于 P3 预测的 ~37% (= 1 - 0.63)，触发 review

### Deferred 2: Multi-regime live validation
- 部署后 6 个月覆盖至少一次 HIGH_VOL episode (VIX ≥ 22)
- 验证 governance 在 HIGH_VOL live 期不参与（AC8 live 验证）
- 若发现 HIGH_VOL 期 governance 异常 fire，开 review ticket

### Deferred 3: Hysteresis band sensitivity (P4)
- 不阻塞 SPEC closure；产品成熟后可做
- 测试 entry/hold bands 微调（±3pp）的 churn / EOD agreement 敏感度
- 用于未来 ENV-tuning 决策

### Deferred 4: Q077 low-IVP semantics research
- 独立轨道，与本 SPEC 并行
- 19y daily backtest 验证 low-IVP 强制 close 是否对 BPS_HV / BPS / Aftermath 有 net-positive
- 若研究结论支持改 selector semantics，单独开 SPEC（不修 SPEC-107）

---

## Implementation Plan (proposed)

| Phase | Scope | Owner |
|---|---|---|
| F1 | A2a hysteresis state machine module + unit tests (AC1, AC8 base) | Developer |
| F2 | Scheduled actionable cadence + bypass list enforcement (AC2, AC3) | Developer |
| F3 | Decision log JSONL append + log rotation (AC6) | Developer |
| F4 | Frontend State Observation label + Actionable banner UX (AC4, AC5) | Developer (frontend) |
| F5 | Backtest replay validation script (AC7) | Quant + Developer |
| F6 | HIGH_VOL/STRESS regression test (AC8) | Quant + Developer |
| F7 | Deploy old Air, smoke test, 30-day decision log review | Developer + PM |

---

## Confidence

**High** — based on:
- 21-day jitter window P2 + 12-month full sample P3 both PASS PM hard targets
- 3 rounds 2nd Quant review (P2 / verdict / P3) all PASS or PASS-with-revisions
- A2a + B in 12mo 跨 regimes 表现一致：HIGH_VOL/STRESS 自动 dormant，LOW_VOL 不误伤
- 49 non-BPS disagreement bars 100% 限于 non-sched bars → bypass list 设计完整覆盖此 caveat

**Caveats** (acknowledged in scope):
- 12mo sample 只含 2025-05 ~ 2026-05 一个"小型 bull-up + tariff shock + Nov-Dec selloff"周期；2008/2020 级 stress regime 缺样本。Deferred 2 在 live 收集。
- Hysteresis band (42-53 / 35-57) 是 PM 提议值，未做 sensitivity；P3 没看到不合理行为；Deferred 3 可补。

---

## Related Documents

```
research/intraday/q076_findings_2026-05-26.md            ← P1 diagnostic
research/intraday/q076_p2_findings_2026-05-26.md         ← P2 verdict
research/intraday/q076_p3_findings_2026-05-26.md         ← P3 robustness (12mo)
task/q076_phase2_2nd_quant_review_2026-05-26.md          ← 2nd Quant P2 review
task/q076_phase2_2nd_quant_review_2026-05-26_Verdict.md  ← PM verdict accepting A2a+B
data/market_cache/spx_vix_1h_aligned_12mo.pkl            ← P3 source data

SPEC-103 (Sleeve Stress Governance)                       ← R5/R6 hard rules, bypass list dependency
SPEC-064 (Aftermath BPS_HV permission gate)               ← Aftermath signal, NOT governed by SPEC-107
SPEC-091 (VIX settling sidecar)                           ← VIX data source for hysteresis
strategy/selector.py                                       ← baseline recommendation (NOT modified)
strategy/sleeve_governance.py                              ← potential host module for AC1
signals/iv_rank.py                                         ← IVP_252 calculation
```
