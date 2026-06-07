# SPEC-115 Phase B Developer Handoff

**SPEC**: [task/SPEC-115_phase_b.md](SPEC-115_phase_b.md)
**Predecessors (deployed)**: SPEC-114 `fe6b6f7`, SPEC-115 phase A `446037e`
**Date issued**: 2026-06-07
**Estimated effort**: 1.5-2 days (more than Phase A — event-driven + earnings data source)
**Status**: pre-implementation. PM ratified 2026-06-07 (skip A obs week, 直接起 B).

---

## TL;DR — What you're doing

Event-driven Q041 T3 IC paper trade for COST + JPM earnings:

1. **earnings calendar** via yfinance `Ticker.calendar` + stale guard
2. **T-3 trigger**: 3 NYSE trading days before earn_date; daily check 16:55 ET
3. **IC selector**: ATM straddle wings + 1.0× implied move width (4 legs); `cash_need_usd = max_loss × 100`
4. **VIX ≥ 15 gate** + optional JPM IMR ≥ 33% (v1 skip if data unavailable)
5. **T+1 auto close**: simulated using next-day chain; PnL = net_credit or max_loss capped

Cash collateral: COST ≈ $4.2k / JPM ≈ $2k 单 contract → 远低于 SPEC-111 cap，**但当前 floor $30k 仍拦** (liquid $16,918)。

---

## Files to change

| File | Action | 说明 |
|---|---|---|
| `strategy/cash_budget_governance.py` | EDIT | +2 keys to `CASH_OCCUPYING_STRATEGIES` |
| `strategy/catalog.py` | EDIT | +2 T3 StrategyDescriptors |
| `strategy/q041_t3_selector.py` | NEW | `select_t3_earnings_ic()` |
| `strategy/q041_earnings_calendar.py` | NEW | `get_next_earnings_date()` + cache |
| `notify/q041_t3_earnings_check.py` | NEW | event-driven daily check (T-3 / T+1) |
| `web/server.py` `/api/q041/overview` | EDIT | +t3_paper_state + countdown |
| [web/templates/q041.html:370-379](../web/templates/q041.html#L370-L379) | EDIT | wire T3 cards |
| oldair: `com.spxstrat.q041_t3_earnings_check.plist` | NEW (deploy) | 16:55 ET Mon-Fri |
| `data/q041_earnings_calendar.json` | NEW (runtime) | cache |
| `tests/test_q041_earnings_calendar.py` | NEW | AC-1/2/13 |
| `tests/test_q041_t3_selector.py` | NEW | AC-4 |
| `tests/test_q041_t3_governance.py` | NEW | AC-3/5/6/10 |
| `tests/test_q041_t3_close_logic.py` | NEW | AC-7/8/9 |
| `tests/test_q041_t3_telegram.py` | NEW | AC-11/12 |
| `pyproject.toml` | EDIT | add `lxml` dep |

---

## Code stubs

### 1. `strategy/q041_earnings_calendar.py` (NEW)

```python
"""Q041 earnings calendar via yfinance — SPEC-115 phase B.

Caches next-earnings-date per T3 symbol. Stale guard rejects past dates.
"""
from __future__ import annotations
import json
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = REPO_ROOT / "data" / "q041_earnings_calendar.json"
ALERT_PATH = REPO_ROOT / "data" / "q041_earnings_alert.jsonl"
T3_SYMBOLS = ["COST", "JPM"]

def get_next_earnings_date(symbol: str) -> date | None:
    """Returns next upcoming earnings date for symbol, or None if missing/stale."""
    try:
        t = yf.Ticker(symbol)
        cal = t.calendar
    except Exception as e:
        log.warning(f"yfinance calendar fetch for {symbol} failed: {e}")
        _emit_alert(symbol, f"yfinance_error:{e}")
        return None
    if not cal or "Earnings Date" not in cal:
        return None
    dates = cal["Earnings Date"]
    if not dates:
        return None
    next_date = dates[0] if isinstance(dates, list) else dates
    # Stale guard
    if next_date < date.today():
        log.info(f"{symbol} yfinance returned stale date {next_date} < today; skipping")
        return None
    return next_date

def refresh_cache() -> dict:
    """Refresh cache for all T3 symbols, write to CACHE_PATH."""
    cache = {"refreshed_at": datetime.now(ET).isoformat(timespec="seconds")}
    for sym in T3_SYMBOLS:
        d = get_next_earnings_date(sym)
        cache[sym] = d.isoformat() if d else None
    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    return cache

def _emit_alert(symbol: str, reason: str) -> None:
    rec = {
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "symbol": symbol,
        "reason": reason,
    }
    with open(ALERT_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    try:
        from notify.telegram_bot import push_message  # verify actual name
        push_message(f"⚠ Q041 earnings calendar: {symbol} {reason}")
    except Exception:
        pass

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()
    if args.refresh:
        c = refresh_cache()
        print(json.dumps(c, indent=2))
```

### 2. `strategy/q041_t3_selector.py` (NEW)

```python
"""Q041 T3 earnings IC selector — SPEC-115 phase B.

T-3 entry IC: ATM short straddle wings + 1.0× implied move width.
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
CHAINS_ROOT = REPO_ROOT / "data" / "q041_chains"

T3_PARAMS = {
    "q041_t3_cost_earnings_ic": {"underlying": "COST"},
    "q041_t3_jpm_earnings_ic":  {"underlying": "JPM"},
}

def select_t3_earnings_ic(strategy_key: str, asof_date: str, earn_date: date,
                          vix_now: float) -> dict | None:
    """Build T-3 IC candidate per SPEC-115 phase B §2.3.

    Returns candidate dict or None on any failure.
    """
    if vix_now < 15.0:
        # VIX gate — gate handled by caller, but defensive here too
        return None
    params = T3_PARAMS[strategy_key]
    sym = params["underlying"]
    chain_path = CHAINS_ROOT / asof_date / f"{sym}.parquet"
    und_path = CHAINS_ROOT / asof_date / "_underlying.parquet"
    if not chain_path.exists() or not und_path.exists():
        return None
    df = pd.read_parquet(chain_path)
    und = pd.read_parquet(und_path)
    spot_row = und[und["symbol"] == sym]
    if spot_row.empty:
        return None
    spot = float(spot_row.iloc[0]["close"])

    # Step 3: find earliest expiry with DTE ∈ [1,14] covering earn_date
    df = df[(df["dte"] >= 1) & (df["dte"] <= 14)].copy()
    if df.empty:
        return None
    # earnings should fall inside expiry window
    df["expiry_date"] = pd.to_datetime(df["expiry"]).dt.date
    df = df[df["expiry_date"] >= earn_date]
    if df.empty:
        return None
    # earliest qualifying expiry
    target_expiry = df["expiry_date"].min()
    df = df[df["expiry_date"] == target_expiry]
    dte = int(df["dte"].iloc[0])

    # Step 4: find ATM strike
    df["strike_dist"] = (df["strike"] - spot).abs()
    atm_strike = float(df.sort_values("strike_dist").iloc[0]["strike"])

    # Step 5: ATM call.close + ATM put.close = straddle
    atm_call_row = df[(df["option_type"] == "CALL") & (df["strike"] == atm_strike)]
    atm_put_row  = df[(df["option_type"] == "PUT")  & (df["strike"] == atm_strike)]
    if atm_call_row.empty or atm_put_row.empty:
        return None
    atm_call_close = float(atm_call_row.iloc[0]["close"])
    atm_put_close  = float(atm_put_row.iloc[0]["close"])
    straddle = atm_call_close + atm_put_close
    implied_move_pct = straddle / spot
    implied_move_usd = straddle  # in dollar terms = call_close + put_close
    spread_width = implied_move_usd * 1.0  # 1.0× IV move

    # Step 6: find K_long_put, K_long_call (closest strikes at ±width)
    K_long_put_target  = atm_strike - spread_width
    K_long_call_target = atm_strike + spread_width
    df_puts  = df[df["option_type"] == "PUT"].copy()
    df_calls = df[df["option_type"] == "CALL"].copy()
    df_puts["dist"]  = (df_puts["strike"]  - K_long_put_target).abs()
    df_calls["dist"] = (df_calls["strike"] - K_long_call_target).abs()
    K_long_put  = float(df_puts.sort_values("dist").iloc[0]["strike"])
    K_long_call = float(df_calls.sort_values("dist").iloc[0]["strike"])

    # Step 7: 4 legs prices
    def _close(opt_type, strike):
        r = df[(df["option_type"] == opt_type) & (df["strike"] == strike)]
        return float(r.iloc[0]["close"]) if not r.empty else None
    p_short_put  = atm_put_close
    p_long_put   = _close("PUT",  K_long_put)
    p_short_call = atm_call_close
    p_long_call  = _close("CALL", K_long_call)
    if None in (p_long_put, p_long_call):
        return None

    # Step 8: net_credit + max_loss
    net_credit_per_share = (p_short_put + p_short_call) - (p_long_put + p_long_call)
    if net_credit_per_share <= 0:
        return None  # not a credit spread; skip
    net_credit_usd = net_credit_per_share * 100
    max_loss_per_share = max(atm_strike - K_long_put, K_long_call - atm_strike) - net_credit_per_share
    max_loss_usd = max_loss_per_share * 100

    return {
        "strategy_key": strategy_key,
        "underlying": sym,
        "asof_date": asof_date,
        "earn_date": earn_date.isoformat(),
        "vix_entry": vix_now,
        "spot": spot,
        "atm_strike": atm_strike,
        "implied_move_pct": implied_move_pct,
        "implied_move_usd": implied_move_usd,
        "spread_width_usd": spread_width,
        "K_short_put": atm_strike,
        "K_long_put": K_long_put,
        "K_short_call": atm_strike,
        "K_long_call": K_long_call,
        "expiry": target_expiry.isoformat(),
        "dte": dte,
        "net_credit_usd": net_credit_usd,
        "max_loss_usd": max_loss_usd,
        "cash_need_usd": max_loss_usd,
        "imr_rank_pct": None,  # v1 skip
        "paper_trade": True,
    }
```

### 3. `strategy/cash_budget_governance.py` extend (small)

```python
CASH_OCCUPYING_STRATEGIES: frozenset[str] = frozenset({
    "bull_call_diagonal",
    "q041_t2_googl_csp",
    "q041_t2_amzn_csp",
    "q041_t3_cost_earnings_ic",   # NEW
    "q041_t3_jpm_earnings_ic",    # NEW
})
```

No other changes — `evaluate_cash_collateral_budget` already reads `cash_need_usd` field generically.

### 4. `strategy/catalog.py` T3 descriptors

See SPEC §2.4. Two new `StrategyDescriptor` entries (`q041_t3_cost_earnings_ic`, `q041_t3_jpm_earnings_ic`).

### 5. `notify/q041_t3_earnings_check.py` (NEW)

```python
"""Q041 T3 earnings IC daily event check — SPEC-115 phase B.

Runs each trading day 16:55 ET. For each T3 symbol:
  - days_to == 3: trigger T-3 entry flow
  - days_to == -1: trigger T+1 close flow
  - else: silent
"""
from __future__ import annotations
import argparse, json, logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from strategy.q041_earnings_calendar import refresh_cache, T3_SYMBOLS
from strategy.q041_t3_selector import select_t3_earnings_ic
from strategy.sleeve_governance import evaluate_candidate

ET = ZoneInfo("America/New_York")
REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_LOG = REPO_ROOT / "data" / "q041_paper_log.jsonl"
CACHE = REPO_ROOT / "data" / "q041_earnings_calendar.json"
SK_BY_SYM = {"COST": "q041_t3_cost_earnings_ic", "JPM": "q041_t3_jpm_earnings_ic"}

_US_HOLIDAYS_2026 = {  # mirror from daily_chain_sanity.py
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}

def trading_days_until(target: date, today: date | None = None) -> int:
    """Count NYSE trading days from today (exclusive) to target (inclusive).
    Returns negative if target is in the past."""
    today = today or date.today()
    if target == today:
        return 0
    direction = 1 if target > today else -1
    count = 0
    d = today
    while d != target:
        d += timedelta(days=direction)
        iso = d.isoformat()
        # weekday: 0=Mon … 6=Sun
        if d.weekday() < 5 and iso not in _US_HOLIDAYS_2026:
            count += direction
    return count

def _get_current_vix() -> float | None:
    """Read VIX from existing snapshot source (reuse signals/ helper)."""
    from signals.vix_regime import latest_vix_snapshot  # adjust to actual fn
    snap = latest_vix_snapshot()
    return float(snap.vix) if snap else None

def _push_telegram(text: str) -> None:
    from notify.telegram_bot import push_message
    push_message(text)

def _emit_log(event_type: str, strategy_key: str, candidate, decision, **extra):
    rec = {
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "event": event_type,
        "strategy_key": strategy_key,
        "candidate": candidate,
        "governance_decision": decision,
        **extra,
    }
    with open(PAPER_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")

def _format_t_minus_3(cand, decision) -> str:
    ud = cand
    return (
        f"📅 Q041 T3 Paper Signal: {ud['underlying']} T-3 (earn_date {ud['earn_date']})\n"
        f"  Spot: ${ud['spot']:.2f}  VIX: {ud['vix_entry']:.1f} {'✅' if ud['vix_entry'] >= 15 else '❌'} (≥15)\n"
        f"  ATM straddle: ${ud['implied_move_usd']:.2f} (IV-implied move: {ud['implied_move_pct']*100:.2f}%)\n"
        f"  Spread width: ${ud['spread_width_usd']:.2f}\n"
        f"  K_short_put: {ud['K_short_put']:.0f}  K_long_put: {ud['K_long_put']:.0f}  "
        f"K_short_call: {ud['K_short_call']:.0f}  K_long_call: {ud['K_long_call']:.0f}\n"
        f"  Net credit: ${ud['net_credit_usd']:.0f}  Max loss: ${ud['max_loss_usd']:.0f}\n"
        f"  Cash need: ${ud['cash_need_usd']:.0f}\n"
        f"  Decision: {'✅ PAPER OPEN' if decision.get('accepted') else '❌ blocked — ' + str(decision.get('reason', 'unknown'))}"
    )

def _handle_t_minus_3(sym, earn_date, vix, args):
    sk = SK_BY_SYM[sym]
    if vix is None or vix < 15.0:
        _emit_log("blocked", sk, None,
                  {"accepted": False, "reason": f"vix_gate: {vix} < 15.0"},
                  asof=date.today().isoformat(), earn_date=earn_date.isoformat())
        if not args.dry_run:
            _push_telegram(f"📅 Q041 {sym} T-3 ({earn_date}): blocked — VIX {vix} < 15")
        return
    cand = select_t3_earnings_ic(sk, date.today().isoformat(), earn_date, vix)
    if cand is None:
        _emit_log("blocked", sk, None,
                  {"accepted": False, "reason": "no_candidate (chain/expiry/strike missing)"},
                  asof=date.today().isoformat(), earn_date=earn_date.isoformat())
        return
    dec = evaluate_candidate(cand)
    decision_dict = {"accepted": dec.accepted, "reason": getattr(dec, "reason", None)}
    event = "open" if dec.accepted else "blocked"
    _emit_log(event, sk, cand, decision_dict)
    msg = _format_t_minus_3(cand, decision_dict)
    if args.dry_run:
        print(msg)
    else:
        _push_telegram(msg)

def _handle_t_plus_1(sym, earn_date, args):
    # Look up most recent open for this sym from paper_log
    # Read T+1 spot from today's chain underlying
    # Compute PnL per AC-7/8/9
    # _emit_log("close", ...)
    # _push_telegram(close message)
    # ... (implementation details — see SPEC §2.7)
    pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-earn", default=None,
                        help="Override earnings for test: COST:YYYY-MM-DD,JPM:YYYY-MM-DD")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()

    # Refresh cache (or load existing)
    if args.mock_earn:
        cache = {}
        for kv in args.mock_earn.split(","):
            k, v = kv.split(":")
            cache[k] = v
    else:
        try:
            cache = refresh_cache()
        except Exception as e:
            log.error(f"calendar refresh failed: {e}")
            return

    vix = _get_current_vix()

    for sym in T3_SYMBOLS:
        earn_iso = cache.get(sym)
        if not earn_iso:
            continue
        earn_date = date.fromisoformat(earn_iso)
        days_to = trading_days_until(earn_date, today)
        if days_to == 3:
            _handle_t_minus_3(sym, earn_date, vix, args)
        elif days_to == -1:
            _handle_t_plus_1(sym, earn_date, args)
        # else: silent

if __name__ == "__main__":
    main()
```

### 6. `com.spxstrat.q041_t3_earnings_check.plist` (NEW oldair)

Same structure as Phase A plist but module = `notify.q041_t3_earnings_check` and time = 16:55 ET (after Phase A T2 16:50).

### 7. `/api/q041/overview` extension

Add to existing payload:

```python
# T3 paper state
t3_state = {}
cache_path = Path("data/q041_earnings_calendar.json")
if cache_path.exists():
    cache = json.loads(cache_path.read_text())
    for sym, sk in [("COST", "q041_t3_cost_earnings_ic"), ("JPM", "q041_t3_jpm_earnings_ic")]:
        earn_iso = cache.get(sym)
        if not earn_iso:
            t3_state[sk] = {"status": "no_earnings_date", "days_to": None}
            continue
        earn_date = date.fromisoformat(earn_iso)
        days_to = trading_days_until(earn_date)
        t3_state[sk] = {
            "status": "armed" if days_to >= 0 else "stale",
            "earn_date": earn_iso,
            "days_to": days_to,
        }
return jsonify({..., "t3_paper_state": t3_state, ...})
```

q041.html line 370-379 已有 T3 spec hardcoded — wire JS to read `t3_paper_state.q041_t3_cost_earnings_ic.days_to` + render countdown chip.

---

## Test plan

```bash
# Install lxml
ssh oldair "cd ~/SPX_strat && arch -arm64 venv/bin/pip install lxml"

# Unit tests
arch -arm64 venv/bin/python -m pytest \
  tests/test_q041_earnings_calendar.py \
  tests/test_q041_t3_selector.py \
  tests/test_q041_t3_governance.py \
  tests/test_q041_t3_close_logic.py \
  tests/test_q041_t3_telegram.py -v

# Regression
arch -arm64 venv/bin/python -m pytest tests/ -k 'spec_113 or spec_115 or sleeve_governance' -v

# Smoke: yfinance integration
arch -arm64 venv/bin/python -m strategy.q041_earnings_calendar --refresh
cat data/q041_earnings_calendar.json

# Smoke: T-3 trigger
arch -arm64 venv/bin/python -m notify.q041_t3_earnings_check \
  --date 2026-06-05 --dry-run \
  --mock-earn "COST:2026-06-08,JPM:2026-06-09"

# Deploy
git push
ssh oldair "cd ~/SPX_strat && git pull && launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_t3_earnings_check.plist"
ssh oldair "launchctl list | grep q041"
# Expect 4 jobs
```

---

## AC checklist

- [ ] AC-1 — yfinance calendar returns valid earn_date, stale guard works
- [ ] AC-2 — `trading_days_until` arithmetic correct
- [ ] AC-3 — VIX < 15 → blocked, reason `vix_gate`
- [ ] AC-4 — IC candidate construction returns 4 legs + max_loss
- [ ] AC-5 — SPEC-111 cash floor blocks IC (current state)
- [ ] AC-6 — Cash floor restored → IC accepted (mock test)
- [ ] AC-7 — T+1 close: neither breached → PnL = net_credit
- [ ] AC-8 — T+1 close: put breached → PnL formula
- [ ] AC-9 — T+1 close: call breached → PnL formula
- [ ] AC-10 — JPM IMR v1 skip writes `imr_check: skipped`
- [ ] AC-11 — Telegram T-3 message format
- [ ] AC-12 — Telegram T+1 close message
- [ ] AC-13 — Daily calendar refresh writes JSON cache

---

## Deploy

```bash
git push origin main
ssh oldair "cd ~/SPX_strat && git pull"
ssh oldair "arch -arm64 venv/bin/pip install lxml"
scp com.spxstrat.q041_t3_earnings_check.plist oldair:~/Library/LaunchAgents/
ssh oldair "launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_t3_earnings_check.plist"
ssh oldair "launchctl list | grep q041"
# Expect 4 jobs: collect / chain_sanity / t2_paper_signals / t3_earnings_check
```

Restart web for `/api/q041/overview` pickup:
```bash
ssh oldair "launchctl kickstart -k gui/$(id -u) com.spxstrat.web"
```

---

## Open questions for dev

1. **lxml install in venv**: verify `import lxml` works post-install on oldair venv.
2. **yfinance network reliability on oldair**: 第一天 deploy 后, monitor `q041_earnings_alert.jsonl` 是否有 yfinance fail records.
3. **VIX snapshot helper**: 实际 function name (`latest_vix_snapshot` 是 placeholder) — `signals/vix_regime.py` 看 actual API.
4. **JPM IMR**: 5/5 packet 写 "可选 / secondary"。Phase B v1 skip is intentional. If PM later wants v2 implementation, separate SPEC.
5. **T+1 close timing**: 实际 earnings 发布是盘后或盘前。T+1 close 应该用 T+1 收盘 chain。`q041_collect` 16:30 ET 拉 T+1 chain → `q041_t3_earnings_check` 16:55 ET 跑 T+1 close. 数据时序 OK.
6. **Earnings stale on COST (2026-05-28 已过去)**: yfinance 应该今天后会 refresh 到下一 fiscal Q earnings. 部署后 verify 一次.

---

## Cross-references

- [task/SPEC-115_phase_b.md](SPEC-115_phase_b.md) — full SPEC
- [task/SPEC-115_phase_a.md](SPEC-115_phase_a.md) — Phase A (deployed `446037e`)
- [task/SPEC-115_outline.md](SPEC-115_outline.md)
- [task/SPEC-111.md](SPEC-111.md) — extended again
- [doc/q041_execution_prep_packet_2026-05-05.md](../doc/q041_execution_prep_packet_2026-05-05.md) §4 — T3 IC spec defaults
