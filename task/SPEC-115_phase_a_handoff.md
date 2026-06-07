# SPEC-115 Phase A Developer Handoff

**SPEC**: [task/SPEC-115_phase_a.md](SPEC-115_phase_a.md)
**Predecessor (deployed)**: SPEC-114 `fe6b6f7`
**Date issued**: 2026-06-07
**Estimated effort**: 1-1.5 days
**Status**: pre-implementation. PM ratified all decisions (outline §4 Q-1~Q-4 + 6/7 cash-binding).

---

## TL;DR — What you're doing

Promote Q041 T2 GOOGL + AMZN CSP to paper trade lane. Three threads:

1. **Extend SPEC-111** cash governance to cover CSP cash collateral (rename `DEBIT_STRATEGIES` → `CASH_OCCUPYING_STRATEGIES`, generic `cash_need_usd` field, backward-compat for BCD)
2. **Drop paper-bypass** in `sleeve_governance.py:1095` — paper trade now走 SPEC-111 cap (PM 拍板)
3. **Wire T2** into selector + catalog + dashboard + Telegram + paper log

**预期 production behavior** (PM 已知情): T2 GOOGL ($36.6k cash need) + AMZN ($25.2k) **>** SPEC-111 cap ($22.2k). Daily signal job 多数日 emit `blocked` events not `open`. **0 fire in first week is success, not failure** — verifies cash-bound boundary.

---

## Files to change

| File | Action | 说明 |
|---|---|---|
| [strategy/cash_budget_governance.py](../strategy/cash_budget_governance.py) | EDIT | rename set + generic field + new function alias |
| [strategy/sleeve_governance.py:1095](../strategy/sleeve_governance.py#L1095) | EDIT | drop `and not is_paper` |
| [strategy/catalog.py](../strategy/catalog.py) | EDIT | add 2 T2 StrategyDescriptors |
| `strategy/q041_selector.py` | NEW | `select_t2_csp()` chain-reading + filter |
| `notify/q041_paper_telegram.py` | NEW | daily 16:50 ET signal job |
| `web/server.py` `/api/q041/overview` | EDIT | add T2 candidate/decision payload |
| `web/templates/q041.html:341-379` | EDIT | wire JS T2 cards to API; add Phase A banner |
| `tests/test_q041_t2_selector.py` | NEW | AC-1 |
| `tests/test_spec_115_cash_collateral.py` | NEW | AC-2/3/4 |
| `tests/test_q041_paper_log.py` | NEW | AC-5/6 |
| `~/Library/LaunchAgents/com.spxstrat.q041_t2_paper_signals.plist` | NEW (oldair) | daily 16:50 ET Mon-Fri |

---

## Code stubs

### 1. `strategy/cash_budget_governance.py` extend

```python
# At line 29 — replace
DEBIT_STRATEGIES: frozenset[str] = frozenset({"bull_call_diagonal"})

# With:
CASH_OCCUPYING_STRATEGIES: frozenset[str] = frozenset({
    "bull_call_diagonal",       # debit (SPEC-113)
    "q041_t2_googl_csp",        # CSP cash collateral (SPEC-115 phase A)
    "q041_t2_amzn_csp",         # CSP cash collateral
})

# Backward-compat alias (kept until any external import is migrated):
DEBIT_STRATEGIES = CASH_OCCUPYING_STRATEGIES
```

Add new function (next to `evaluate_debit_cash_budget`):

```python
def evaluate_cash_collateral_budget(candidate: dict) -> dict:
    """Generic cash-occupying-strategy gate. Handles both debit (BCD) and
    cash-secured collateral (CSP). Same cap math as SPEC-111.

    Reads candidate.cash_need_usd; falls back to candidate.entry_debit_usd
    for backward compat with BCD callers.
    """
    sk = str(candidate.get("strategy_key") or "")
    if sk not in CASH_OCCUPYING_STRATEGIES:
        return {"accepted": True, "stats": {}, "alert": False,
                "skip_reason": "not_cash_occupying"}

    cash_need = candidate.get("cash_need_usd")
    if cash_need is None:
        cash_need = candidate.get("entry_debit_usd")  # BCD backward compat
    if cash_need is None:
        return {"accepted": False, "reason": "missing cash_need_usd or entry_debit_usd",
                "stats": {}, "alert": False}

    # ... rest mirrors evaluate_debit_cash_budget, using `cash_need` in place
    # of debit_per_contract. Reason strings use "cash_collateral:" prefix
    # for CSP, "debit_cash_budget:" for BCD (sk == "bull_call_diagonal").
    prefix = "debit_cash_budget" if sk == "bull_call_diagonal" else "cash_collateral"
    # ...
```

**Keep `evaluate_debit_cash_budget` as alias** for any external caller (backward compat):
```python
def evaluate_debit_cash_budget(candidate: dict) -> dict:
    """Deprecated: use evaluate_cash_collateral_budget. Retained for callers."""
    return evaluate_cash_collateral_budget(candidate)
```

Also update `get_open_debit_total_usd` → `get_open_cash_collateral_total_usd`:
- BCD position: `entry_premium_paid_usd` (existing)
- CSP position: `short_strike * 100 * contracts` (new — read from position dict)

### 2. `strategy/sleeve_governance.py:1095` change

```python
# BEFORE (line 1088-1097):
is_paper = bool(candidate.get("paper_trade"))
try:
    from strategy.cash_budget_governance import (
        DEBIT_STRATEGIES,
        evaluate_debit_cash_budget,
        log_cash_budget_decision,
        maybe_alert_cash_budget,
    )
    if sk in DEBIT_STRATEGIES and not is_paper:
        cash_decision = evaluate_debit_cash_budget(candidate)

# AFTER:
try:
    from strategy.cash_budget_governance import (
        CASH_OCCUPYING_STRATEGIES,
        evaluate_cash_collateral_budget,
        log_cash_budget_decision,
        maybe_alert_cash_budget,
    )
    if sk in CASH_OCCUPYING_STRATEGIES:
        cash_decision = evaluate_cash_collateral_budget(candidate)
```

(Remove `is_paper` variable and the `and not is_paper` condition. `is_paper` may still be referenced elsewhere — grep before deleting.)

### 3. `strategy/catalog.py` T2 descriptors

```python
# Add to STRATEGIES_BY_KEY dict (between existing entries):

"q041_t2_googl_csp": StrategyDescriptor(
    key="q041_t2_googl_csp",
    name="Q041 T2 GOOGL CSP",
    emoji="📋",
    direction="bull",
    underlying="GOOGL",
    trade_type="Credit — Cash-Secured Put (Paper)",
    dte_text="21 DTE (±3d)",
    delta_text="Short put δ0.20 (±5pp)",
    when_text=(
        "Daily EOD scan; Q041 paper-trade lane only. SPEC-111 cash cap binds "
        "single GOOGL CSP ($36.6k) typically > $22.2k cap."
    ),
    risk_text=(
        "Assignment risk = K × 100 cash. Single-name tail (missing COVID/2019-2021 "
        "in 4y backtest, per 5/5 review packet). Paper trade verifies cash-bound boundary."
    ),
    detail_roll_text="No roll in paper. Default exit: hold to expiry or assignment.",
    max_risk_text="K × 100 cash collateral per contract (~$36.6k at K=$366).",
    target_return_text="Full credit at expiry (S_exit > K).",
    roll_rule_text="None — Phase A is observation lane.",
    short_gamma=True,
    short_vega=False,
    delta_sign="pos",
    manual_entry_allowed=False,
),

"q041_t2_amzn_csp": StrategyDescriptor(
    key="q041_t2_amzn_csp",
    name="Q041 T2 AMZN CSP",
    emoji="📋",
    direction="bull",
    underlying="AMZN",
    trade_type="Credit — Cash-Secured Put (Paper)",
    dte_text="21 DTE (±3d)",
    delta_text="Short put δ0.25 (±5pp)",
    when_text=(
        "Daily EOD scan; Q041 paper-trade lane only. SPEC-111 cash cap binds "
        "single AMZN CSP ($25.2k) typically > $22.2k cap."
    ),
    risk_text=(
        "Assignment risk = K × 100 cash. Single-name tail (missing COVID/2019-2021 "
        "in 4y backtest, per 5/5 review packet). Paper trade verifies cash-bound boundary."
    ),
    detail_roll_text="No roll in paper. Default exit: hold to expiry or assignment.",
    max_risk_text="K × 100 cash collateral per contract (~$25.2k at K=$252).",
    target_return_text="Full credit at expiry (S_exit > K).",
    roll_rule_text="None — Phase A is observation lane.",
    short_gamma=True,
    short_vega=False,
    delta_sign="pos",
    manual_entry_allowed=False,
),
```

### 4. `strategy/q041_selector.py` (NEW)

See SPEC §2.4. Key responsibilities:
- Read `data/q041_chains/<date>/<UNDERLYING>.parquet`
- Filter PUT, |Δ| ∈ [target ± 0.05], DTE ∈ [target ± 3], close > $0.10
- Sort by `(|delta - target|, |dte - target|)` ascending; take top-1
- Return candidate dict with `cash_need_usd = strike * 100 * 1`

If chain missing → return `None` (collector_alert.jsonl from SPEC-114 already logs missing).

### 5. `notify/q041_paper_telegram.py` (NEW)

```python
"""Q041 T2 paper signal daily job — SPEC-115 phase A.

Runs once per trading day (16:50 ET via launchd, after q041_chain_sanity 16:45).
For each T2 candidate strategy:
  1. select_t2_csp(strategy_key, today)
  2. evaluate_candidate(candidate)  # via sleeve_governance
  3. write event to data/q041_paper_log.jsonl
  4. include in Telegram daily push (one message, both candidates)
"""
from __future__ import annotations
import argparse, json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from strategy.q041_selector import select_t2_csp
from strategy.sleeve_governance import evaluate_candidate
from notify.telegram_bot import push_message  # verify actual fn name

ET = ZoneInfo("America/New_York")
REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_LOG = REPO_ROOT / "data" / "q041_paper_log.jsonl"
T2_STRATEGIES = ["q041_t2_googl_csp", "q041_t2_amzn_csp"]

def _emit_log(event_type: str, strategy_key: str, candidate, decision, asof_date: str):
    rec = {
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "event": event_type,
        "strategy_key": strategy_key,
        "asof_date": asof_date,
        "candidate": candidate,
        "governance_decision": decision,
    }
    with open(PAPER_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")

def _format_telegram(date_str: str, results: list[dict]) -> str:
    lines = [f"📋 Q041 T2 Paper Signal {date_str}"]
    for r in results:
        if r["candidate"] is None:
            lines.append(f"{r['underlying']} CSP: no chain candidate found (Δ/DTE/close out of band)")
            continue
        c = r["candidate"]
        lines.append(f"\n{c['underlying']} CSP Δ{c['delta']:.2f} DTE{c['dte']}:")
        lines.append(f"  K=${c['short_strike']:.0f}  close=${c['close']:.2f}  cash_need=${c['cash_need_usd']:,.0f}")
        d = r["decision"]
        if d.get("accepted"):
            lines.append(f"  Decision: ✅ PAPER OPEN")
        else:
            lines.append(f"  Decision: ❌ blocked — {d.get('reason', 'unknown')}")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asof = args.date or date.today().isoformat()
    results = []
    for sk in T2_STRATEGIES:
        candidate = select_t2_csp(sk, asof)
        if candidate is None:
            results.append({"underlying": "GOOGL" if "googl" in sk else "AMZN",
                            "candidate": None, "decision": None})
            continue
        decision = evaluate_candidate(candidate)
        event = "open" if decision.accepted else "blocked"
        if not args.dry_run:
            _emit_log(event, sk, candidate, decision.__dict__, asof)
        results.append({"underlying": candidate["underlying"],
                        "candidate": candidate, "decision": decision.__dict__})

    msg = _format_telegram(asof, results)
    if args.dry_run:
        print(msg)
    else:
        push_message(msg)

if __name__ == "__main__":
    main()
```

(Verify `notify.telegram_bot` push helper function name — `push_message` is placeholder.)

### 6. `web/server.py` `/api/q041/overview` extension

Search current `/api/q041/overview` endpoint. Add to its JSON payload:

```python
# In existing q041_overview handler:
from strategy.q041_selector import select_t2_csp
from strategy.sleeve_governance import evaluate_candidate

t2_state = {}
today = date.today().isoformat()
for sk in ["q041_t2_googl_csp", "q041_t2_amzn_csp"]:
    cand = select_t2_csp(sk, today)
    if cand is None:
        t2_state[sk] = {"status": "no_candidate", "reason": "chain or band missing"}
        continue
    dec = evaluate_candidate(cand)
    t2_state[sk] = {
        "status": "open" if dec.accepted else "blocked",
        "candidate": cand,
        "decision": {"accepted": dec.accepted, "reason": getattr(dec, "reason", None)},
    }

# add cumulative counts from paper_log
log_path = Path("data/q041_paper_log.jsonl")
counts = {"total_signals": 0, "blocked": 0, "opens": 0}
if log_path.exists():
    for line in log_path.read_text().splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        counts["total_signals"] += 1
        if rec["event"] == "blocked": counts["blocked"] += 1
        elif rec["event"] == "open": counts["opens"] += 1

return jsonify({
    **existing_payload,
    "t2_paper_state": t2_state,
    "t2_paper_counts": counts,
})
```

### 7. `web/templates/q041.html` T2 cards wiring

Line 341-379 已有 hardcoded T2 spec object. 改 `loadQ041Overview` JS function to:
- read `data.t2_paper_state.q041_t2_googl_csp` + `data.t2_paper_state.q041_t2_amzn_csp`
- render each in its existing card slot (line ~352 / ~361)
- Banner at top of Q041 page (visible only when Phase A active):

```html
<div class="phase-a-banner" style="background:var(--theme-lit-006);border:1px solid var(--border);padding:8px 12px;margin-bottom:10px;font-size:0.65rem;color:var(--text-2);border-radius:5px">
  <strong style="color:var(--text)">Phase A — T2 Paper Trade Observation</strong>
  · 期望多数日 governance-blocked (SPEC-111 cash cap binds GOOGL/AMZN 单 contract).
  · 0 fire in observation period verifies cash-bound boundary.
</div>
```

### 8. `com.spxstrat.q041_t2_paper_signals.plist` (NEW oldair)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.spxstrat.q041_t2_paper_signals</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/macbook/SPX_strat/venv/bin/python</string>
    <string>-m</string>
    <string>notify.q041_paper_telegram</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/macbook/SPX_strat</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>50</integer><key>Weekday</key><integer>1</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>50</integer><key>Weekday</key><integer>2</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>50</integer><key>Weekday</key><integer>3</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>50</integer><key>Weekday</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>50</integer><key>Weekday</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key>
  <string>/Users/macbook/SPX_strat/logs/q041_t2_paper_signals.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/macbook/SPX_strat/logs/q041_t2_paper_signals.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/Users/macbook/SPX_strat/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
```

---

## Test plan

```bash
# Unit tests (new)
arch -arm64 venv/bin/python -m pytest \
  tests/test_q041_t2_selector.py \
  tests/test_spec_115_cash_collateral.py \
  tests/test_q041_paper_log.py -v

# Regression (SPEC-113 / SPEC-111 / sleeve_governance)
arch -arm64 venv/bin/python -m pytest \
  tests/test_spec_113_carve.py \
  tests/test_spec_113_bit_identical.py \
  tests/test_strategy_unification.py \
  tests/ -k 'sleeve or cash_budget' -v

# Smoke test on real chain data (AC-2/3 manual replay)
arch -arm64 venv/bin/python -m notify.q041_paper_telegram --date 2026-06-05 --dry-run
# Expected: 2 candidates produced, both blocked by cash_collateral (K*100 > $22.2k)

# Mock-with-low-strike test (AC-6 manual)
# (Edit q041_chains/2026-06-05/GOOGL.parquet temp to set strike=$200 for a PUT row,
#  run dry-run again, expect accepted=True paper open event)

# Deploy
scp com.spxstrat.q041_t2_paper_signals.plist oldair:~/Library/LaunchAgents/
ssh oldair "launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_t2_paper_signals.plist"
ssh oldair "launchctl list | grep q041"
# Expect 3 jobs: q041_collect / q041_chain_sanity / q041_t2_paper_signals
```

---

## AC checklist

- [ ] AC-1 — `select_t2_csp` returns valid candidate from 6/5 chain
- [ ] AC-2 — `evaluate_cash_collateral_budget` blocks $36,600 GOOGL CSP
- [ ] AC-3 — paper_trade=True candidate now走 cash gate (sleeve_governance)
- [ ] AC-4 — BCD path unchanged (entry_debit_usd field still read)
- [ ] AC-5 — paper_log writes blocked events
- [ ] AC-6 — paper_log writes open events when K × 100 ≤ cap (mock test)
- [ ] AC-7 — Telegram daily message format matches §2.6
- [ ] AC-8 — q041.html T2 cards render API decisions
- [ ] AC-9 — first-week observation logged (informational)

---

## Deploy

```bash
# After all ACs green
git push origin main
ssh oldair "cd ~/SPX_strat && git pull"
scp com.spxstrat.q041_t2_paper_signals.plist oldair:~/Library/LaunchAgents/
ssh oldair "launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_t2_paper_signals.plist"
# Verify
ssh oldair "launchctl list | grep q041; tail -1 /Users/macbook/SPX_strat/data/q041_paper_log.jsonl 2>/dev/null"
```

Restart web service so `/api/q041/overview` picks up new fields:
```bash
ssh oldair "launchctl kickstart -k gui/$(id -u) com.spxstrat.web"
```

---

## Open questions for dev

1. `notify.telegram_bot` actual push function — verify name (placeholder `push_message`).
2. `web/server.py` 当前 `/api/q041/overview` 是否已有实际数据流 (5/5 packet 写过 T1 SPX CSP)？还是空 stub？
3. Backward-compat alias `DEBIT_STRATEGIES = CASH_OCCUPYING_STRATEGIES` 是否影响 SPEC-113 BCD tests？grep for any test importing `DEBIT_STRATEGIES` before renaming.

Ping Quant if any blocking ambiguity.

---

## Cross-references

- [task/SPEC-115_phase_a.md](SPEC-115_phase_a.md)
- [task/SPEC-115_outline.md](SPEC-115_outline.md)
- [task/SPEC-111.md](SPEC-111.md) — extended by this SPEC
- [task/SPEC-114.md](SPEC-114.md) — predecessor (ship `fe6b6f7`)
- [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md)
- [doc/q041_execution_prep_packet_2026-05-05.md](../doc/q041_execution_prep_packet_2026-05-05.md)
