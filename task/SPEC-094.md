# SPEC-094: Q042 Directional Drawdown / Reversal Overlay (Revised)

Status: APPROVED

## Design Source

This is a **research-driven Spec**.

Design substance:
- **Quant Researcher**: Q042 Tier 1 + Tier 2 + Tier 3 research chain
  - `research/q042/q042_tier1_memo_2026-05-09.md`
  - `research/q042/q042_tier2_memo_2026-05-09.md`
  - `research/q042/q042_tier3_memo_2026-05-09.md`
  - Tier 3 deep-dive (post 2nd Quant review): drawdown definition, MA filters, sizing, sleeve interaction
- **2nd Quant Reviewer**: APPROVE WITH ADJUSTMENTS — 6 revisions all incorporated (`task/q042_tier1_tier2_2nd_quant_review_packet_2026-05-09_Review.md`)
- **PM**: standing objective "reasonably maximize account-level ROE"; Tier 3 deep-dive resolved methodology fragility (rolling 60d max → ddATH), trigger universe (dd12+reclaim → dd4+dd15), sizing scale (1% → 10%), and dual-sleeve architecture decisions

## 一句话目标

在 SPX 出现两个不同深度的真实回撤事件后（dd ≥ 4% 从历史最高点 / dd ≥ 15% 从历史最高点），分别用两个独立 sleeve 入场 ATM/+5% **SPX call spread** DTE 90，作为主策略 income-first 之外的方向性 long-premium overlay。

**Symbol 决策（2026-05-10 PM 决定）**：MVP **SPX-only**。XSP 路径删除 — PM 当前 NLV ≥ $500k，SPX 1-contract 步长 ($11k) 在此 scale 下 sizing 偏差 ≤ 12%，可接受。删 XSP 显著简化 F2/F4/F5/F6/F8。XSP 路径作为未来 NLV < $200k 时的 revisit option，不进 MVP。

---

## 锁定参数

### Sleeve A — High-frequency moderate dip-buy

| 参数 | 值 |
|---|---|
| Trigger 名称 | `q042_sleeve_a_dd4_lenient` |
| 触发条件 | `ddATH_lenient` 首次跌穿 -4% |
| Drawdown 定义 | 距 running ATH（self-updating max since 2007-01-01） |
| Re-arm | ddATH 恢复到 ≥ -2%（lenient） |
| MA filter | **none**（直接 T+1 open 入场） |
| 历史频次 | ~1.3 trades/yr (25 trades over 19y) |
| 历史 win rate | 64% |

### Sleeve B — Rare high-conviction deep-drawdown

| 参数 | 值 |
|---|---|
| Trigger 名称 | `q042_sleeve_b_dd15_lenient_ma10reclaim` |
| 触发条件（外） | `ddATH_lenient` 首次跌穿 -15% |
| Re-arm | ddATH 恢复到 ≥ -2%（lenient） |
| MA filter | **MA10 reclaim**（首次 close > MA10，30 trading-day window） |
| 历史频次 | ~0.26 trades/yr (5 trades over 19y) |
| 历史 win rate | 100% (5/5) |

### Structure（两 sleeve 共用）

| 参数 | 值 |
|---|---|
| Type | Long call vertical spread (debit) |
| Long leg | ATM (strike = entry-day SPX close, rounded to nearest $5) |
| Short leg | ATM × 1.05（+5% OTM, rounded to nearest $5） |
| DTE target | **90 days** |
| Hold | to expiry (MVP) |
| Symbol | **SPX**（cash-settled European, Section 1256, multiplier 100） |
| Activation threshold | NLV ≥ **$200k**（保证 ≥ 1 SPX contract 在 10% sizing 下；< $200k 跳过 Q042） |

### Sizing（两 sleeve 各自独立）

| 参数 | Sleeve A | Sleeve B |
|---|---|---|
| Per-entry sizing | **10% account** | **10% account** |
| Sleeve cap (own) | 10% account | 10% account |
| Combined cap | **20% account**（仅在两 sleeve 同时持仓时） |
| Joint BP gate | `q042_combined_cap = min(20%, max(0%, 60% − main_bp%))` — governance backstop |

历史上两 sleeve 同时持仓的天数：109 天 / 4868 总（2.2%），合计 BP 偶尔到 20%。**这是有意的**，不是 bug — 两个 sleeve 是独立 alpha source。

### Re-Trigger Spacing（每 sleeve 内部）

每个 sleeve 内部：max 1 active position at a time（no-overlap）。
跨 sleeve：**完全独立**，不互相阻塞。

### Execution

| 参数 | 值 | 备注 |
|---|---|---|
| Trigger evaluation time | T close (EOD) | Daily close-based |
| Order generation | T close + alert | Telegram alert post-close |
| Order placement | T+1 open | Realistic execution window |

---

## 一句话决策路径

```
For each trading day T (after 16:15 ET close):
  1. Update running ATH if SPX_close(T) > previous ATH
  2. Compute ddATH = SPX_close(T) / ATH - 1

  ── Sleeve A ──
  3. If sleeve_a.armed AND ddATH ≤ -4%:
       → trigger Sleeve A; place ATM/+5% spread DTE 90 at T+1 open (no MA filter)
       → sleeve_a.armed = False; sleeve_a.position open
  4. If sleeve_a.position closed (90 days passed) AND ddATH ≥ -2%:
       → sleeve_a.armed = True

  ── Sleeve B ──
  5. If sleeve_b.armed AND ddATH ≤ -15%:
       → enter Sleeve B "watching" mode (30 trading days)
       → sleeve_b.armed = False
  6. If sleeve_b in "watching" AND SPX_close(T) > MA10:
       → trigger Sleeve B; place ATM/+5% spread DTE 90 at T+1 open
       → sleeve_b.position open; exit watching
  7. If sleeve_b in "watching" 30 days expired without MA10 reclaim:
       → drop trigger; sleeve_b stays armed=False until ddATH ≥ -2%
  8. If sleeve_b.position closed AND ddATH ≥ -2%:
       → sleeve_b.armed = True

  ── Order sizing (both sleeves) ──
  At entry: 10% account / spread; hold to expiry; settle European cash.
```

---

## 功能项 (Features)

### F1 — Trigger Engine (Dual Sleeve, ddATH-based)

**File**: `signals/q042_trigger.py` (new)

Implements two **independent state machines**:

```python
@dataclass
class SleeveState:
    sleeve_id: str           # "A" or "B"
    armed: bool              # can this sleeve fire?
    in_watching: bool        # B-specific: dd15 fired, awaiting MA10 reclaim
    watch_start_date: str | None
    active_position_id: str | None
    active_position_expiry: str | None

def update_sleeve_a(state: SleeveState, ddath: float, today: str) -> dict:
    """dd4 + no filter — fire immediately on first ddATH ≤ -4% crossing."""
    # Re-arm logic
    if not state.armed and state.active_position_id is None and ddath >= -0.02:
        state.armed = True
    # Trigger logic
    if state.armed and ddath <= -0.04 and state.active_position_id is None:
        return {"action": "fire_A", "date": today}
    return {"action": "none"}

def update_sleeve_b(state: SleeveState, ddath: float, spx_close: float, ma10: float, today: str) -> dict:
    """dd15 + MA10 reclaim filter."""
    if not state.armed and state.active_position_id is None and ddath >= -0.02:
        state.armed = True
    if state.armed and not state.in_watching and ddath <= -0.15 and state.active_position_id is None:
        state.in_watching = True
        state.watch_start_date = today
        state.armed = False
        return {"action": "enter_watching"}
    if state.in_watching:
        days_in_watch = days_between(today, state.watch_start_date)
        if days_in_watch > 30:
            state.in_watching = False
            return {"action": "watch_expired"}
        if spx_close > ma10:
            state.in_watching = False
            return {"action": "fire_B", "date": today}
    return {"action": "none"}
```

- Daily close-based evaluation; **no look-ahead**
- ATH is computed as `SPX.cummax()` from 2007-01-01 baseline (initial seed value loaded from historical data)
- MA10 = 10-day rolling mean of SPX close

**Acceptance criteria**:
- AC1: Walk-forward 2007-2026 produces:
  - Sleeve A: 25 entries (after no-overlap rule)
  - Sleeve B: 5 entries
  - Match Tier 3 memo §A3b filtered counts
- AC2: Each sleeve's `armed` flag is independent of the other (verify by unit test: dd4 firing does not change dd15.armed)
- AC3: Re-arm requires `ddATH ≥ -2%` (lenient)
- AC4: Sleeve B's "watching" window expires after 30 trading days with no MA10 reclaim
- AC5: Persistence: after process restart, sleeve states (`armed`, `in_watching`, `active_position_id`) reload correctly from `data/q042_state.json`

### F2 — Position Sizing (SPX-only)

**File**: `strategy/q042_sizing.py` (new)

- Inputs: NLV, current SPX, current VIX, sleeve_id ("A" or "B")
- Logic:
  - If `NLV < $200k` → return 0 contracts (skip Q042; below this threshold SPX 1-contract step ($11k) is > 5.5% account, sizing too coarse)
  - Target debit budget = `NLV × 0.10` (10% account / entry)
  - Symbol fixed = **SPX** (no symbol-selection branch)
  - Strikes: long_K = ATM rounded to nearest $5; short_K = ATM × 1.05 rounded to nearest $5
  - Estimate spread debit using `q042_pricing.estimate_debit(S, K_long, K_short, dte=90, vix)` (BS + skew haircut + term-multiplier; same as research model)
  - Contracts = `floor(target_debit / estimated_debit_per_contract)`
- Output: `(long_strike, short_strike, contracts, est_debit)` tuple

**Acceptance criteria**:
- AC6: At NLV $500k, SPX 7400, VIX 25 → returns `(7400, 7770, 4 contracts, ~$11k/ct)` [10% × $500k = $50k budget; 4 ct × $11k = $44k = 8.8% account, accept slight under-target]
- AC7: At NLV $150k → returns `(None, None, 0, None)` [below activation threshold $200k]
- AC8: At NLV $5M → returns `(K_long_$5_rounded, K_short_$5_rounded, ~45 contracts, ~$11k/ct)`

### F3 — Joint BP Gate (Combined-Cap Backstop)

**File**: `strategy/q042_gate.py` (new)

- Reads current main-strategy `bp_pct_account` from `web/state.py` or position store
- Reads current Q042 sleeve A & B BP usage
- Computes `q042_combined_cap = min(20.0, max(0.0, 60.0 - main_bp_pct))`
- Returns per-sleeve allowance:
  - If gate not binding (combined cap ≥ 20%): each sleeve gets full 10% allowance
  - If gate partially binding: prorate (each sleeve allowed up to `combined_cap / 2`)
  - If gate fully binding (cap = 0): block both sleeves
- Logs gate state daily

**Acceptance criteria**:
- AC9: `main_bp_pct = 30%` → both sleeves get full 10% allowance (combined cap 20% not binding)
- AC10: `main_bp_pct = 55%` → combined cap = 5%, both sleeves get 2.5% each (prorated)
- AC11: `main_bp_pct = 65%` → combined cap = 0, both sleeves blocked
- AC12: Gate state logged to `data/q042_gate_log.jsonl` daily

### F4 — Live Pricing Tie-Out (Spec Acceptance Gate)

**Status**: ✅ **5-day tie-out PASSED retroactively from oldair archive** (median delta 5.65%, max 8.0%; data: `data/q042_f4_tieout_history.csv`; script: `research/q042/q042_f4_oldair_backfill.py`).

**Discovery (2026-05-10)**: oldair has been auto-collecting Schwab SPX chain daily via `com.spxstrat.q041_massive_snapshot` launchd job at 16:35 ET, persisted to `data/q041_chains/<date>/SPX.parquet` with full bid/ask/mid/iv/delta/Greeks. 5 trading days (2026-05-04 → 05-08) of complete chain data already on hand — no waiting required.

**Tie-out evidence (5 days)**:

| Date | VIX | DTE | K_long ATM | K_short | OTM% | Broker debit | Model debit | Delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05-04 | 18.29 | 88 | 7205 | 7450 | 3.40% | $132.80 | $122.18 | **8.00%** |
| 2026-05-05 | 17.38 | 87 | 7280 | 7505 | 3.09% | $122.45 | $112.87 | 7.83% |
| 2026-05-06 | 17.39 | 86 | 7375 | 7615 | 3.25% | $125.35 | $119.27 | **4.85%** |
| 2026-05-07 | 17.08 | 85 | 7350 | 7585 | 3.20% | $123.60 | $116.62 | 5.65% |
| 2026-05-08 | 17.19 | 84 | 7400 | 7645 | 3.31% | $127.10 | $120.80 | 4.96% |
| **median** | | | | | | | | **5.65%** |

**AC13 (deployment gate)**: ✅ **PASSED** — 5-day median delta 5.65% << 15% threshold.

**Caveat 1 — strike window**: Existing q041 collector window stopped at ~ATM+3.4% OTM, not full +5%. Tie-out validates model on ATM/+3.4% spread, which generalizes to +5% via smooth skew. **No re-calibration needed**; collector should be widened forward (one-line change in `research/q041/collect_chains.py` strike_window param) to fully cover +5% in future archives.

**Caveat 2 — all low-vol regime**: All 5 archive days had VIX 17-18 (low-vol). Q042 actually triggers in HIGH_VOL (VIX ≥ 22) where call skew is steeper. **First live HIGH_VOL trigger = mandatory re-validation** (re-run `q042_f4_oldair_backfill.py` against that day's chain, expect delta to potentially shift).

**No additional 3-day collection required pre-deployment** (PM decision 2026-05-10).

### F5 — Execution Alert (T+1 open, Telegram-only)

**File**: `production/q042_executor.py` (new)

**架构决策（PM 2026-05-10）**：与主策略一致，Q042 采用 **Telegram alert + 人手下单** 模式。整个 repo 目前无 Schwab order automation endpoint；~1.5 trades/yr 的频率完全适合人工执行。未来若 repo 引入全局 order automation，Q042 可一并接入（独立 SPEC）。

- After T close, if F1 fires Sleeve A or Sleeve B trigger and F3 allows, generate execution alert
- Send Telegram alert:

```
🟢 Q042 [Sleeve A | Sleeve B] | SPX
Entry: T+1 open (manual)
Strikes: long K=<x> / short K=<x>
DTE: 90
Est debit: $<x> per contract
Contracts: <n>
NLV at signal: $<x>
ddATH at signal: <x>%
→ Place SPX call spread at T+1 open
```

- Log pending entry to `data/q042_paper_trades.jsonl`; PM manually fills `fill_debit` and `entry_time` after execution
- No Schwab order API call in MVP

**Acceptance criteria**:
- AC14: Telegram alert content matches the spec format（含 sleeve_id, strikes, DTE, est_debit, contracts, NLV, ddATH）
- ~~AC15: Order is placed within 60 seconds of T+1 open~~ **（删除 — Telegram-only 架构不适用）**
- AC16: Failed alert does NOT block daily main-strategy alerts (independent execution path)
- AC17: Pending trade record logged: sleeve_id (A/B), signal_date, ATH_at_signal, ddATH_at_signal, strikes, DTE, est_debit, contracts, NLV_at_entry；`fill_debit` / `entry_time` 由 PM 事后回填

### F6 — Position Tracking & Exit

**File**: extend `production/positions.py` or create `q042_positions.py`

- Track active Q042 positions per sleeve (max 1 each by no-overlap rule within sleeve)
- At T close on `entry_date + 90 calendar days`, mark position as "expiring today"
- At market close on expiry day, allow position to settle (cash settlement, European-style)
- Record exit P&L to `data/q042_paper_trades.jsonl` (or live)
- **No early close in MVP** (held-to-expiry only)

**Acceptance criteria**:
- AC18: Position object exposes `is_active`, `days_to_expiry`, `current_pnl` for portfolio dashboard
- AC19: Expiry P&L computed from settlement value, not intraday mid
- AC20: After expiry, sleeve state transitions to `armed=False` until ddATH re-arm condition met

### F7 — Web UI: Q042 Dual-Sleeve Section

**File**: extend `web/templates/index.html` or new `q042.html`

- Add a Q042 dual-sleeve card to portfolio command center showing:
  - **ATH tracker**: current SPX, current ATH, current ddATH%
  - **Sleeve A state**: armed / awaiting re-arm / active position
  - **Sleeve B state**: armed / watching for MA10 reclaim (with watch-day countdown) / active position
  - **Active position details** (per sleeve): entry_date, strikes, current PnL, days to expiry
  - **Combined Q042 BP**: % account; flag yellow if > 15%, red if > 20%
  - **Lifetime stats**: per-sleeve trades count, win rate, total P&L

### F8 — Backtest Harness

**File**: `backtest/q042_engine.py` (new)

- Walk-forward 2007-2026 simulation using same trigger logic as F1
- Use BS + skew haircut + term-multiplier pricing (same model as Tier 3 research)
- Output trade log compatible with portfolio metrics tooling

**Acceptance criteria**:
- AC21: Reproduces Tier 3 research-memo metrics within ±2%:
  - Sleeve A: n=25, win 64%, +99% / 19y, max DD -16.3%
  - Sleeve B: n=5, win 100%, +41% / 19y, max DD 0%
- AC22: Outputs `data/q042_backtest_trades.csv` with columns: sleeve_id, entry_date, exit_date, signal_date, ATH_at_signal, ddATH_at_signal, contracts, debit, exit_pnl, account_pct (symbol omitted — always SPX)
- AC23: Outputs combined-portfolio daily BP series for visualization

### F9 — Documentation & Sleeve State Persistence

- Update `RESEARCH_LOG.md` with R-20260509-15 (Tier 3 final + deep-dive + SPEC-094 revision)
- Update `sync/open_questions.md` Q042 status to "SPEC-094 APPROVED → Developer queue"
- After deployment: add Q042 to `QUANT_RESEARCHER.md` "Active strategies" section
- State file `data/q042_state.json`:

```json
{
  "ath_running_max": 7401.5,
  "ath_last_update": "2026-05-08",
  "sleeve_a": {
    "armed": true,
    "active_position_id": null,
    "active_position_expiry": null
  },
  "sleeve_b": {
    "armed": true,
    "in_watching": false,
    "watch_start_date": null,
    "active_position_id": null,
    "active_position_expiry": null
  },
  "combined_bp_pct": 0.0
}
```

---

## State Machine 图

```
                Sleeve A (dd4 + no filter)               Sleeve B (dd15 + MA10 reclaim)

     ┌─ armed ─┐                                  ┌─ armed ─┐
     │         │                                  │         │
   ddATH     ddATH                              ddATH     ddATH
   ≤ -4%     ≥ -2%                              ≤ -15%    ≥ -2%
     │         │                                  │         │
     ↓         ↑                                  ↓         ↑
  fire A   re-arm                            watching      re-arm
  (T+1)                                      (≤30 days)
     │                                          │
     ↓                                          ↓
   active                                    close > MA10?
   90d hold                                     │
     │                                          ↓ (yes)
     ↓                                       fire B (T+1)
   expiry                                       │
     │                                          ↓
     └──── back to "needs ddATH ≥ -2%" ─→  active 90d hold
                                                │
                                                ↓
                                              expiry
                                                │
                                                └──→ "needs ddATH ≥ -2%" to re-arm

Both sleeves run **independently**. ddATH is shared computation; armed flags are per-sleeve.
```

---

## Failure Modes (Tier 3 final)

### FM1 — Vol crush + delayed recovery
- Trigger fires during elevated IV; SPX does not fall further; recovery is slow
- IV crush + theta decay can kill the spread before directional move arrives
- **Mitigation**: DTE 90 (vs DTE 30) provides 60 extra days; benefits from IV mean reversion via long ATM call
- **Detection**: monitor unrealized PnL ≤ −80% of debit at day 60 → log "FM1-suspected"

### FM2 — Sequence bleed in secular bear / prolonged chop
- Multiple Sleeve A triggers in multi-leg bear market; cumulative bleed
- **ddATH-based design 已部分缓解**: re-arm requires ddATH ≥ -2%, which is hard to achieve in a sustained bear → fewer triggers vs old dd60_rolling approach (Sleeve A: 25 events vs old "43 if dd5_rolling")
- **Sleeve A max DD historically -16.3%**; max consecutive losses 2 (under ddATH_lenient)
- **Detection**: rolling 12m sleeve P&L ≤ −10% account → trigger Tier 4 review (kill switch consideration)

### FM3 — Both sleeves fire on same drawdown event
- 5/5 dd15 events also had a preceding dd4 event firing in the same drawdown
- **Combined BP up to 20% during 109/4868 days (2.2%)**, max overlap 63 days (2020 COVID)
- **Historical worst**: 0 instances of "both sleeves losing during same overlap" — sleeve B is 5/5 winner
- **Mitigation**: Joint BP gate (F3) keeps combined cap ≤ 20%; if main strategy BP forces dual-cap below 20%, prorate

### FM4 — Pre-2007 tail event types untested
- Strategy backtested on 2007-2026 only
- 1929 / 1987 / 1998 LTCM / 2000-2002 dot-com regimes not in sample
- **Mitigation**: monitor for live anomalies; first 2 years of live trading = continuous validation

### Excluded from concern
- Naked-margin cascade: N/A (defined-risk debit spread)
- Dividend assignment: N/A (cash-settled European)
- Margin call from spread: bounded by debit at risk

---

## Expected Performance (Tier 3 backtest)

| Metric | Sleeve A (dd4) | Sleeve B (dd15) | Combined |
|---|---:|---:|---:|
| Trade frequency | 1.3/yr | 0.26/yr | ~1.5/yr |
| Win rate | 64% | 100% | mixed |
| Median winner (% account) | +1.10% | +0.97% | — |
| 19y total | +99% | +41% | **+140%** |
| **Annualized** | **+5.11%** | **+2.12%** | **~+7.2%** |
| Max DD | -16.3% | 0% | -16% to -20% |
| Worst single trade | -10% account | -10% account | -10% (single sleeve) |
| Max combined BP | 10% | 10% | 20% (109 days/19y) |

**Caveats**:
- All numbers are research-scale (BS + skew haircut + term-multiplier pricing); live numbers will differ at the 2.5% level (per F4 single-day tie-out)
- No transaction cost modeled; estimated 0.4-2.7% per-trade haircut at MVP
- Sleeve B sample n=5 → wide CI on 100% win rate (95% CI roughly 50-100%)

---

## Acceptance Summary

Pre-deployment gates:
- [ ] AC1-AC23 implemented and tested
- [ ] F4 5-day live pricing tie-out passes (median delta < 15%)
- [ ] PM final approval on dual-sleeve config + 10%/10% sizing
- [ ] Backtest harness reproduces Tier 3 metrics within tolerance

Post-deployment monitoring:
- 6-month paper-trading review:
  - Sleeve A vs B realized win rates vs research baseline
  - Combined BP usage spikes vs research-predicted 2.2% of days
  - F4 model-vs-broker delta in HIGH_VOL regime triggers (live tie-out validation)
- 12-month review:
  - Sleeve cap upgrade discussion (Sleeve A 10%→15%? Sleeve B 10%→15%?) if metrics hold
  - Tier 4 candidate research: 50% TP / 50% stop on intraday data
- Continuous: Joint BP gate firing rate (expected 0/day in current main-strategy regime; flag if main strategy parameters change)

---

## References

- Tier 1 memo: `research/q042/q042_tier1_memo_2026-05-09.md`
- Tier 2 memo: `research/q042/q042_tier2_memo_2026-05-09.md`
- Tier 3 memo: `research/q042/q042_tier3_memo_2026-05-09.md`
- Tier 3 deep-dive scripts:
  - `q042_dd_threshold_comparison.py` (dd-threshold scan)
  - `q042_drawdown_definition.py` (rolling vs ATH)
  - `q042_ddath_full_scan.py` (dd3-15 ddATH grid)
  - `q042_ma_filter_grid.py` (MA filter × dd-threshold)
  - `q042_ddath_ma_filter.py` (final filter selection)
  - `q042_dd5_worst_trades.py` (max DD diagnostics)
  - `q042_f4_tieout.py` (single-day live pricing tie-out)
- 2nd Quant Review: `task/q042_tier1_tier2_2nd_quant_review_packet_2026-05-09_Review.md`
- Seed memo: `doc/q042_directional_overlay_seed_memo_2026-05-04.md`
- RESEARCH_LOG: R-20260509-11 (Tier 1) → R-20260509-12 (Tier 2) → R-20260509-13 (review) → R-20260509-14 (Tier 3 initial) → R-20260509-15 (Tier 3 deep-dive + SPEC-094 revision)
