# SPEC-111 — Debit-Strategy Cash-Budget Cap + Concurrent-Utilization Alert

**Type**: governance / risk management
**Date**: 2026-06-01
**Status**: **DEPLOYED at cap=60% (commit 6f133fc, 2026-06-02)** — Q082 G2 ratified cap=50%; **PM elected Option C** (operational live-test) 2026-06-02: keep deployed cap=60% for 30-60 day live test, patch to 50% only if data trigger fires (see Live-Test Tripwire below).
**Cross-reference**: `research/q082/q082_p10_verdict_revised_2026-06-02.md` Verdict Z — research-ratified at 50%; operational config at 60% pending live-test outcome.

### Live-Test Tripwire (PM Option C, valid 2026-06-02 → 2026-08-01)

Decision tree for cap parameter at 60-day review (≈ **2026-08-01**):

| Observed condition during live test | Action |
|---|---|
| Σ debit utilization stays < 50% throughout window | Cap=60% sufficient; Q082 Z analysis archived as "research-ratified but operationally unnecessary"; no SPEC-111 patch |
| Σ debit utilization touches 50% but never >55% | Marginal; default to KEEPING cap=60% but note in Q082 close that data slightly favors Z |
| Σ debit utilization exceeds 55% even once | Trigger SPEC-111.1 patch: cap 60%→50%, BCD max_debit $22k→$18.5k. Backtest cache refresh required |
| 75% concurrent alert fires | Immediate ad-hoc review (do NOT wait for 60-day window); likely indicates structural issue requiring tighter cap regardless |

**Where data lives**: `data/cash_budget_decisions.jsonl` (per-decision row) + Portfolio Snapshot "Debit cash budget" field.
**Owner**: Quant Researcher (draft) → PM ratify → Developer implementation
**Source**: Q081 P5 Verdict A (research/q081/q081_p5_verdict_2026-06-01.md), G-review 2 ratified 2026-06-01 (Q2 RATIFY-65→60, Q3 RATIFY-60, Q4 CHALLENGE-add alert)
**Parent**: SPEC-104 (Sleeve Governance, BP-based caps) — additive, no breaking change

---

## 0. TL;DR

Add a **cash-side governance layer** to sleeve_governance, parallel to (not replacing) the existing BP-side caps. Closes a structural gap identified in Q081: SPEC-104 caps by BP utilization, but in a cash-bound account the binding constraint for debit strategies (BCD; future debit strategies) is **cash**, not BP.

**Two rules**:

| Rule | Trigger | Action |
|---|---|---|
| **Hard cap** | `Σ debit_open ≥ 50% × current_liquid_cash` | **BLOCK** new debit-strategy open; degrade to reduce_wait |
| **Concurrent alert** | `Σ debit_open ≥ 75% × current_liquid_cash` | **NOTIFY** (Telegram); allow trade |
| **Cash floor** | `current_liquid_cash < $30,000` | **BLOCK** all new debit-strategy opens |

**Cap parameter history**: PM initial approval 60% (2026-06-01). Refined to **50%** by Q082 G2 final re-ratify (2026-06-02) after 26y BCD synth reconstruction confirmed DOWN-stratum drag is reliably -19 to -22pp (block-bootstrap CI tight) and Y MA-cross gate is refuted (filters only 6.2% of DOWN). Cap is the only operational lever — tightened from 60% → 50%.

**Denominator**: real-time combined liquid cash across brokers, NOT static dollar amount, NOT % NLV.

---

## 1. Background

### 1.1 Q081 finding (research/q081/q081_p1_memo.md + q081_p5_verdict_2026-06-01.md)

Steady-state liquid cash = **3.0% of NLV** ($37k of $1.24M). Combined BP utilization = 13.7%; BP headroom = 56%. **Cash is the scarce resource, BP is abundant**.

SPEC-104 caps by BP utilization — does not bite a BCD stack until cash is depleted. Per Q081 P1, a single BCD consumes 66% of available cash. Two concurrent BCDs would exhaust all liquid cash, forcing QQQ liquidation. P1 historical found 0 concurrent BCDs (sequential ladder discipline), but nothing in code enforces that — pure behavioral.

### 1.2 Why 60% (G-review 2 Q3 RATIFY-60)

| Cap | Single BCD ($24k) fits? | Concurrent (2nd at typical sizing)? | Liquid cash slack | Headroom for future debit strategies |
|---|---|---|---|---|
| 50% | ❌ (must shrink BCD) | ❌ | $18.5k | ample |
| **60% (selected)** | ✅ (boundary, 65% of $37k = $24.05k) | ❌ | $14.8k | **modest reserve** |
| 65% | ✅ | ❌ | $13.0k | minimal |
| 100% | ✅ | ❌ | $0 | none |

60% rationale (per G-review 2):
- Marginal slack cost of 65%→60% is small (~$1,850 cash)
- Cash-bound account: slack has high option value for unexpected needs
- 60% is structural pre-reservation for future debit strategies (not dependent on remembering to re-audit)
- Allows 1 BCD at current backtest-validated sizing (debit $23,864 < $22,228 = 60% × $37,046)

**Note on boundary**: at the steady-state baseline $37,046, 60% = $22,227. Median BCD debit ($23,864) is **slightly over** this — meaning current BCD sizing would need to shrink ~7% to fit under 60% cap. This is the explicit trade-off PM accepts for the slack reserve.

### 1.3 Why concurrent alert at 75% (G-review 2 Q4 add)

The cap alone caps **single new entry**, not cumulative state. If matrix design evolves to allow concurrent debit positions (e.g., BCD on SPX + BCD on NDX), two positions each at 40% would sum to 80% — but neither single-trade open would trip the 60% cap.

The 75% concurrent alert is the **forward false-negative monitor** (per memory `feedback_kill_gate_external_read`). It notifies PM that the aggregate is approaching cap, before a future open is silently rejected.

Alert ≠ block: PM can see the state and decide manually.

### 1.4 Why % liquid cash, NOT % NLV (G-review 2 Q2)

In a cash-bound account ($37k liquid of $1.24M NLV), a 5%-NLV cap = $62k > full liquid pool — **the cap is effectively nonexistent**. The denominator must be the scarce resource the cap protects.

---

## 2. Scope

### 2.1 Strategies governed

All **debit** strategies (entry premium is paid out, not received):

| Strategy key | Class | Today's regime cells |
|---|---|---|
| `bull_call_diagonal` | debit | LOW_VOL × BULL × IVP_{LOW, MID} |
| (future) | debit | TBD |

**Strategies NOT governed by this cap** (their entry credit MORE cash, not less):

| Strategy key | Class |
|---|---|
| `bull_put_spread`, `bull_put_spread_hv` | credit |
| `bear_call_spread_hv` | credit |
| `iron_condor`, `iron_condor_hv` | credit |
| `reduce_wait` | n/a |

Detection: a strategy is "debit" if its catalog descriptor's net entry cash flow is **negative** (PM pays). Implemented as a hardcoded set in code; extensible.

### 2.2 New runtime state

`Σ debit_open` = sum of `entry_premium_paid_usd` for all currently-open positions of strategies in DEBIT_STRATEGIES set. Read from existing `data/positions.json` + `data/positions.jsonl` event log.

`current_liquid_cash` = realtime read at open-decision time:
- Schwab `cash_balance` (from `schwab.client.get_account_balances()`)
- + Schwab BOXX market value (or any holding flagged as `cash_like`) — from positions endpoint
- + E-Trade `cash_balance`
- + E-Trade any cash-like positions (currently none, but extensible)

Cash-like detection: hardcoded symbol set `{"BOXX", "SGOV", "SHV", "USFR", "BIL"}` (1-3mo T-bill ETFs). Configurable in code.

### 2.3 New SPEC interactions

| Existing rule | Interaction with SPEC-111 |
|---|---|
| SPEC-104 BP caps | Both rules apply; whichever is tighter wins |
| SPEC-058/060 IVP gates | Apply before SPEC-111 (selector → governance pipeline) |
| SPEC-103 stop-loss daemon | Unchanged; SPEC-111 is open-time gate only |
| SPEC-107 intraday governance | Unchanged; SPEC-111 is account-level, SPEC-107 is per-position |
| Manual override | Existing override mechanism applies; PM can bypass cap if needed |

---

## 3. Implementation

### 3.1 New module: `strategy/cash_budget_governance.py`

Defines:

```python
DEBIT_STRATEGIES = {"bull_call_diagonal"}  # extensible
CASH_LIKE_SYMBOLS = {"BOXX", "SGOV", "SHV", "USFR", "BIL"}

CAP_PCT = 0.60  # hard cap: Σ debit / liquid ≤ 60%
ALERT_PCT = 0.75  # concurrent alert threshold
CASH_FLOOR_USD = 30_000.0  # hard floor on liquid cash

def get_current_liquid_cash() -> dict:
    """Returns {'total': float, 'breakdown': {broker: {raw_cash, cash_like}}}."""
    ...

def get_open_debit_total_usd() -> dict:
    """Returns {'total': float, 'positions': [{trade_id, strategy, debit, ...}, ...]}."""
    ...

def evaluate_debit_cash_budget(candidate: dict) -> dict:
    """Returns:
      {
        "accepted": bool,
        "reason": str (if rejected),
        "alert": bool (if 75% threshold crossed but accepted),
        "stats": {
            "current_liquid_cash": float,
            "currently_open_debit": float,
            "candidate_debit": float,
            "post_entry_total_debit": float,
            "post_entry_utilization_pct": float,
            "cap_pct": float,
            "alert_pct": float,
            "cash_floor_usd": float,
        }
      }
    """
    ...
```

### 3.2 Integration in `strategy/sleeve_governance.py`

In `evaluate_candidate`, after existing BP cap checks and before final acceptance:

```python
if candidate.get("strategy_key") in DEBIT_STRATEGIES and not paper_trade:
    cash_decision = evaluate_debit_cash_budget(candidate)
    if not cash_decision["accepted"]:
        return GovernanceDecision(
            accepted=False,
            reason=f"debit_cash_budget: {cash_decision['reason']}",
            sleeve=...,
            cash_budget_state=cash_decision["stats"],
        )
    if cash_decision["alert"]:
        maybe_alert_concurrent_debit(cash_decision["stats"])
```

### 3.3 Telegram alert

New notification template in `notify/event_push.py` or similar:

```
⚠ Debit cash-utilization at <X>% liquid (cap at 60%, alert at 75%)
Currently open debit: $<sum>
Candidate just approved: $<this_trade>
Combined: $<total> of $<liquid> liquid cash
Strategies open: <list>
```

### 3.4 Frontend display

In `/portfolio_home` Portfolio Snapshot card, add new row:

```
Debit cash budget:  $<sum> / $<liquid>  (X% — cap 60%, alert 75%)
```

Color logic:
- `< 50%`: green (`--green`)
- `50-74%`: gold (`--gold`)
- `≥ 75%`: orange (`--orange`)
- `≥ 60% (would block)`: red (`--red`)

Per memory `feedback_text_muted_banned`: use `--text-2` (NOT `--text-muted`) for label/numbers.

### 3.5 Logging

New file: `data/cash_budget_decisions.jsonl` — one row per decision (accept/reject/alert):

```json
{
  "ts": "2026-06-02T10:30:00Z",
  "candidate_strategy": "bull_call_diagonal",
  "candidate_debit_usd": 23864.00,
  "currently_open_debit": 0.00,
  "current_liquid_cash": 37046.00,
  "decision": "accept",
  "alert_threshold_crossed": false,
  "stats": {...}
}
```

---

## 4. Acceptance Criteria

### AC1 — Unit tests for evaluator

`tests/test_spec_111.py`:

- AC1.1: Single BCD at $22k debit with $37k liquid → accept, no alert (60% boundary)
- AC1.2: Single BCD at $24k debit with $37k liquid → **block** (>60%)
- AC1.3: Σ open $18k + new $10k = $28k, $37k liquid (76%) → accept new $10k (under 60%? wait $10k/$37k=27%; total $28k/$37k=76% > 60%) → block due to TOTAL exceeding cap, even though candidate alone < cap
- AC1.4: Σ open $20k + new $5k = $25k, $37k liquid (68%) → accept (under 60% × 37k = $22.2k? no, 68% > 60%) → **block**
- AC1.5: Σ open $15k + new $5k = $20k, $37k liquid (54%) → accept, no alert
- AC1.6: Σ open $19k + new $9k = $28k, $37k liquid (76%) → accept, **alert** (cross 75%)
- AC1.7: Liquid cash $25k (< $30k floor) → block regardless of cap math
- AC1.8: Strategy not in DEBIT_STRATEGIES → bypass SPEC-111 entirely

### AC2 — Integration smoke test (per memory `feedback_spec_integration_test`)

Real broker pull (Schwab + E-Trade) on test fixture must return non-zero `current_liquid_cash` and correctly identify BOXX as `cash_like`. Failure if `cash_like` is mis-classified or broker fields are misread (defends against E-Trade field-name changes per recent `marginBalance` bug).

### AC3 — Frontend smoke test

Hit `/api/portfolio_home` after opening a BCD; verify response contains:
- `debit_cash_budget_pct` field
- `debit_cash_budget_status` ∈ {green, gold, orange, red}
- The visual element renders without breaking layout (manual test)

### AC4 — Telegram alert smoke

With `debit_cash_budget_pct` between 75 and 60% (alert zone): trigger a BCD open, verify Telegram notification fires.

### AC5 — Manual override path

Existing manual override (SPEC-104 override mechanism) bypasses SPEC-111. Confirmed via test fixture that override=True allows trade despite cap violation, AND override is logged.

### AC6 — Backtest non-regression

Re-run the 3y backtest with SPEC-111 active. The 21 historical BCD trades should ALL be admitted (their median debit $23.9k vs $22.2k cap requires sizing tweak — see AC7).

### AC7 — Backtest sizing adjustment

Backtest BCD sizing must be **reduced by ~7%** to comply with new cap (target $22k debit instead of $24k). Update relevant params in `backtest/engine.py` or per-strategy sizing in `strategy/catalog.py`. Verify backtest stats cache regeneration (per memory `feedback_backtest_cache_refresh`).

### AC8 — Q081 trail closure

Once SPEC-111 lands, update `research/q081/q081_p5_verdict_2026-06-01.md` to mark Verdict A as IMPLEMENTED, link to SPEC-111 commit hash.

---

## 5. Out of scope

- Routing change in matrix (BCD remains in LOW_VOL × BULL cells per PM Verdict B-1)
- Multi-regime BCD validation (Q082 follow-up research)
- Sizing optimization for BCD beyond minimum compliance with new cap
- Cash-like symbol whitelist expansion beyond initial 5 tickers
- Per-strategy debit cap (single global cap suffices for now)
- Real-time recalculation during market hours (open-decision time read is sufficient)

---

## 6. Risk

- **R1 — Cap blocks current BCD entries at backtest sizing**: AC7 addresses this. BCD sizing reduces ~7%, expected PnL impact is proportional (~$120/trade reduction).
- **R2 — Broker API failures during cap evaluation**: must fail SAFE (block on failure to read liquid cash, NOT fail-open). Implementation must catch + reject + log.
- **R3 — BOXX/cash-like position symbol changes**: hardcoded list. If PM moves to a different T-bill ETF, code update required. Documented in §3.1.
- **R4 — Alert noise**: 75% alert fires per debit-strategy open when threshold crossed. Could rate-limit (e.g., max 1 alert per 24h per strategy). Defer to ops feedback.

---

## 7. Deployment plan

```bash
# 1. Dev implements + tests on local
git checkout -b spec-111
# ... implementation ...
pytest tests/test_spec_111.py -v
pytest tests/test_spec_*.py  # full regression
git commit -m "feat(governance): SPEC-111 debit cash-budget cap + concurrent alert"
git push

# 2. Deploy to old Air
ssh oldair 'cd ~/SPX_strat && git pull origin main && launchctl kickstart -k gui/$(id -u)/com.spxstrat.web'

# 3. Backtest cache refresh (per memory feedback_backtest_cache_refresh)
ssh oldair '~/SPX_strat/venv/bin/python -m backtest.refresh_caches --strategies bull_call_diagonal'

# 4. Smoke test live
curl 'http://oldair.local:5050/api/portfolio_home' | jq '.debit_cash_budget_pct'

# 5. Q081 trail closure
# update research/q081/q081_p5_verdict_2026-06-01.md with commit hash
```

---

## 8. Estimated effort

| Task | Hours |
|---|---|
| `cash_budget_governance.py` module | 3 |
| `sleeve_governance.py` integration | 1 |
| Unit tests (8 ACs) | 2 |
| Frontend display | 2 |
| Telegram alert | 1 |
| Backtest sizing adjustment + cache refresh | 1.5 |
| Manual testing + smoke | 1 |
| **Total** | **~11.5 hours** (~1.5 dev days) |

---

## 9. PM ratification needed

- §1.2 calibration: cap = 60%, alert = 75%, floor = $30k — accept?
- §2.1 strategies governed: BCD only for now, future debit strategies inherit — accept?
- §3.4 frontend display location: Portfolio Snapshot card — OK or prefer different surface?
- §AC7 backtest BCD sizing reduce ~7% (debit $24k → $22k) — accept impact on per-trade PnL (~$120 reduction)?
