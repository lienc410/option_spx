# SPEC-115 Phase A — Q041 T2 GOOGL + AMZN CSP Paper Trade Promote

**Type**: strategy promote / paper trade lane / SPEC-111 extension
**Date**: 2026-06-07
**Status**: **RATIFIED** by PM 2026-06-06 (Q-1 串行) + 2026-06-07 (cash-binding: paper 走严格双 cap)
**Cross-reference**: [task/SPEC-115_outline.md](SPEC-115_outline.md), [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md)
**Predecessor**: SPEC-114 (chain sanity + retry, ship 2026-06-07 `fe6b6f7`)
**Parent**: `strategy/sleeve_governance.py` + `strategy/cash_budget_governance.py` (SPEC-111 extend) + `strategy/catalog.py`
**Owner**: Quant Researcher (this draft) → Developer (impl)

---

## 0. TL;DR

Promote Q041 Tier 2 **GOOGL CSP Δ0.20 DTE21** + **AMZN CSP Δ0.25 DTE21** to paper trade lane. 共三件事：

1. **Extend SPEC-111** cash governance to cover CSP cash collateral（K × 100）。当前 SPEC-111 只 gate debit；CSP 是 credit 但仍占用 cash 担保金，**对 cash-bound 账户同样稀缺**。
2. **Paper trade 严格走双 cap** —— SPEC-104 BP-side AND SPEC-111 cash-side。Paper 不再 bypass cash gate（去掉 `sleeve_governance.py:1095` 的 `not is_paper` 条件）。
3. **Wire T2 candidate** 入 selector + governance + Telegram + dashboard。

**预期 daily signal 行为**（PM 已知情接受）：T2 GOOGL CSP cash 需求 K × 100 ≈ $36,600，AMZN ≈ $25,200，**均 > SPEC-111 cap $22,200**。Phase A 多数日 governance reason = `cash_collateral: would exceed 60% liquid`，fire 频率取决于 GOOGL/AMZN 价格回撤（GOOGL K < $222 / AMZN K < $222 单 contract 才能进 cap）。**Phase A 1 周观察期 0 paper fire 不视作失败，视作 verify cash-bound 边界。**

---

## 1. Background

### 1.1 Phase A scope

Per 2026-06-06 AskUserQuestion: "T2 + T3 全动"。Phase A 是串行的第一段，单独 ship Tier 2：

| Candidate | Spec (5/5 packet §3) | Backtest |
|---|---|---|
| T2 GOOGL CSP | Δ ≈ 0.20, DTE ≈ 21, close > $0.10 | 198 trades, win 84.3%, total +$7,729 |
| T2 AMZN CSP | Δ ≈ 0.25, DTE ≈ 21, close > $0.10 | 188 trades, win 84.0%, total +$5,090 |

Backtest cache: [`data/q041_backtest_cache.json`](../data/q041_backtest_cache.json) (key `2022-05-06__1778260502`).

### 1.2 Cash-binding constraint (PM 已知情)

Per [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md) §… + Q081 cash-bound framework:

| | GOOGL CSP | AMZN CSP |
|---|---:|---:|
| K (~5-6% OTM at current prices) | $366 | $252 |
| Cash collateral per 1 contract (K × 100) | **$36,600** | **$25,200** |
| vs SPEC-111 cap (60% × $37k liquid = $22,200) | ❌ exceeds | ❌ exceeds |

PM 2026-06-07 拍板: paper trade 也走严格双 cap (不 bypass)。Phase A 的 production value 是 verify cash-bound boundary 而非 demo fire 频率。

### 1.3 SPEC-111 当前 gap

[strategy/cash_budget_governance.py:29](../strategy/cash_budget_governance.py#L29):
```python
DEBIT_STRATEGIES: frozenset[str] = frozenset({"bull_call_diagonal"})
```

SPEC-111 当时 (2026-06-01) 只考虑 debit strategies (BCD); CSP 是 credit 入场所以未被 gate。但 **CSP cash collateral 同样占用 liquid cash**，对 cash-bound 账户构成同等约束。SPEC-115 必须 extend SPEC-111 覆盖 CSP。

[strategy/sleeve_governance.py:1095](../strategy/sleeve_governance.py#L1095):
```python
if sk in DEBIT_STRATEGIES and not is_paper:  # ← paper skips SPEC-111
    cash_decision = evaluate_debit_cash_budget(candidate)
```

去掉 `not is_paper` 是 PM 2026-06-07 拍板的直接含义。

---

## 2. Specification

### 2.1 SPEC-111 extension — `CASH_OCCUPYING_STRATEGIES`

Rename `DEBIT_STRATEGIES` 概念为 `CASH_OCCUPYING_STRATEGIES`（涵盖 debit + cash-secured collateral）。共享同一 cap（60% liquid, $30k floor, 75% alert）。

新增 candidate field `cash_need_usd`（generic）：
- 对 debit (BCD): `cash_need_usd = entry_debit_usd`（原 SPEC-111 字段）
- 对 CSP: `cash_need_usd = short_strike × 100 × contracts`

`cash_budget_governance.py` 改动:

```python
# Replace DEBIT_STRATEGIES with CASH_OCCUPYING_STRATEGIES
CASH_OCCUPYING_STRATEGIES: frozenset[str] = frozenset({
    "bull_call_diagonal",       # debit
    "q041_t2_googl_csp",        # CSP cash collateral (SPEC-115 phase A)
    "q041_t2_amzn_csp",         # CSP cash collateral
})

# Backward compat alias (sleeve_governance may still reference DEBIT_STRATEGIES)
DEBIT_STRATEGIES = CASH_OCCUPYING_STRATEGIES  # deprecation alias

def evaluate_cash_collateral_budget(candidate: dict) -> dict:
    """Rename evaluate_debit_cash_budget; same semantics, generic field name."""
    sk = candidate.get("strategy_key", "")
    if sk not in CASH_OCCUPYING_STRATEGIES:
        return {"accepted": True, "skip_reason": "not_cash_occupying"}

    # Compute candidate cash need:
    cash_need = candidate.get("cash_need_usd")
    if cash_need is None:
        # Backward compat for BCD: read entry_debit_usd
        cash_need = candidate.get("entry_debit_usd")
    if cash_need is None:
        return {"accepted": False, "reason": "missing cash_need_usd field", ...}

    # ... rest of logic unchanged from evaluate_debit_cash_budget
```

Open positions sum (existing `get_open_debit_total_usd`): 改为 generic. Iterate all positions whose `strategy_key in CASH_OCCUPYING_STRATEGIES`. Per-position cash usage:
- BCD: `entry_premium_paid_usd` (current behavior)
- CSP: `short_strike * 100 * contracts` (new)

### 2.2 sleeve_governance.py — paper 走 cash gate

[strategy/sleeve_governance.py:1095](../strategy/sleeve_governance.py#L1095) 改:

```python
# BEFORE:
if sk in DEBIT_STRATEGIES and not is_paper:
    cash_decision = evaluate_debit_cash_budget(candidate)

# AFTER:
if sk in CASH_OCCUPYING_STRATEGIES:
    cash_decision = evaluate_cash_collateral_budget(candidate)
```

Paper trade candidates 现在也走 SPEC-111 cap check。Block reason 在 decision log 写明 `paper_blocked: cash_collateral: <reason>`。

### 2.3 catalog.py — T2 StrategyDescriptor

新增 2 个 entries:

```python
"q041_t2_googl_csp": StrategyDescriptor(
    key="q041_t2_googl_csp",
    name="Q041 T2 GOOGL CSP",
    emoji="📋",
    direction="bull",
    underlying="GOOGL",
    trade_type="Credit — Cash-Secured Put (Paper)",
    dte_text="21 DTE (±3d)",
    delta_text="Short put δ0.20 (±5pp)",
    when_text="Daily EOD scan; Q041 sleeve paper-trade only. SPEC-111 cash cap binds.",
    risk_text=(
        "Assignment risk = K × 100 cash; single-name tail (5/5 packet: missing "
        "COVID/2019-2021 history); SPEC-111 cap blocks if K × 100 > 60% liquid."
    ),
    detail_roll_text="No roll in paper. Default exit: hold to expiry or assignment.",
    max_risk_text="K × 100 cash collateral (per contract).",
    target_return_text="Full credit at expiry (S_exit > K).",
    roll_rule_text="None (paper trade; PM observes assignment cases).",
    short_gamma=True,
    short_vega=False,
    delta_sign="pos",
    manual_entry_allowed=False,
),
"q041_t2_amzn_csp": StrategyDescriptor(
    key="q041_t2_amzn_csp",
    name="Q041 T2 AMZN CSP",
    # Same shape as GOOGL but Δ0.25 in delta_text, "AMZN" underlying
    ...
),
```

### 2.4 Selector — T2 daily entry signal

**New module**: `strategy/q041_selector.py`

```python
"""Q041 paper trade selector — Phase A: T2 GOOGL + AMZN CSP."""
from __future__ import annotations
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHAINS_ROOT = REPO_ROOT / "data" / "q041_chains"

# Per 5/5 execution prep packet §3
T2_PARAMS = {
    "q041_t2_googl_csp": {
        "underlying": "GOOGL",
        "delta_target": 0.20,
        "delta_tolerance_pp": 0.05,
        "dte_target": 21,
        "dte_tolerance_d": 3,
        "premium_floor_close": 0.10,
    },
    "q041_t2_amzn_csp": {
        "underlying": "AMZN",
        "delta_target": 0.25,
        "delta_tolerance_pp": 0.05,
        "dte_target": 21,
        "dte_tolerance_d": 3,
        "premium_floor_close": 0.10,
    },
}

def select_t2_csp(strategy_key: str, asof_date: str) -> dict | None:
    """Read same-day Schwab chain parquet, find PUT matching Δ-band + DTE-band.

    Returns:
      {
        "strategy_key": str,
        "underlying": str,
        "short_strike": float,    # K
        "expiry": str,             # YYYY-MM-DD
        "dte": int,
        "delta": float,            # actual at-entry
        "close": float,            # entry credit per share
        "cash_need_usd": float,    # K × 100 × 1 contract
        "asof_date": str,
      }
      or None if no candidate found.
    """
    params = T2_PARAMS[strategy_key]
    chain_path = CHAINS_ROOT / asof_date / f"{params['underlying']}.parquet"
    if not chain_path.exists():
        return None
    df = pd.read_parquet(chain_path)
    # filter PUT, delta-band, dte-band, close-floor
    puts = df[df["option_type"] == "PUT"].copy()
    puts = puts[
        (puts["delta"].abs() >= params["delta_target"] - params["delta_tolerance_pp"]) &
        (puts["delta"].abs() <= params["delta_target"] + params["delta_tolerance_pp"]) &
        (puts["dte"] >= params["dte_target"] - params["dte_tolerance_d"]) &
        (puts["dte"] <= params["dte_target"] + params["dte_tolerance_d"]) &
        (puts["close"] > params["premium_floor_close"])
    ]
    if puts.empty:
        return None
    # closest to delta target (then closest DTE)
    puts["delta_dist"] = (puts["delta"].abs() - params["delta_target"]).abs()
    puts["dte_dist"] = (puts["dte"] - params["dte_target"]).abs()
    puts = puts.sort_values(["delta_dist", "dte_dist"]).head(1)
    row = puts.iloc[0]
    return {
        "strategy_key": strategy_key,
        "underlying": params["underlying"],
        "short_strike": float(row["strike"]),
        "expiry": str(row["expiry"]),
        "dte": int(row["dte"]),
        "delta": float(row["delta"]),
        "close": float(row["close"]),
        "cash_need_usd": float(row["strike"]) * 100.0,
        "asof_date": asof_date,
        "paper_trade": True,
    }
```

### 2.5 Paper trade ledger

**New file**: `data/q041_paper_log.jsonl`（per `feedback_quant_review_location` 不放 doc/, 放 data/）

每个 event 一行 JSON:
```json
{"ts": "2026-06-08T16:50:00-04:00", "event": "open|close|expire|assign|blocked",
 "strategy_key": "q041_t2_googl_csp", "asof_date": "2026-06-08",
 "candidate": {...full candidate dict...},
 "governance_decision": {"accepted": false, "reason": "cash_collateral: ..."},
 "notes": "..."}
```

**Open**: 当 governance.accepted=True 时写 open event.
**Blocked**: 当 governance.accepted=False 时写 blocked event (记录尝试)。
**Close/Expire/Assign**: T-day 处理 (Phase A 简化: 21d 后日历到期自动写 expire 或 assign 视 SPX/GOOGL/AMZN close vs K)。

### 2.6 Telegram daily signal push

每日 16:50 ET (after `q041_chain_sanity` 16:45 完成), 跑新 launchd job `com.spxstrat.q041_t2_paper_signals.plist`:

1. Call `select_t2_csp("q041_t2_googl_csp", today)` → candidate dict
2. Call `evaluate_candidate(candidate)` → governance decision
3. Write to `data/q041_paper_log.jsonl`
4. Push Telegram message:

```
📋 Q041 T2 Paper Signal {date}
GOOGL CSP Δ0.20 DTE21:
  Found: K=$366 DTE=20 Δ=0.21 close=$3.45
  Cash need: $36,600
  Decision: ❌ blocked — cash_collateral: would exceed 60% liquid cap
            (current: $0 + candidate $36,600 = 99% of $22,200 cap)

AMZN CSP Δ0.25 DTE21:
  Found: K=$252 DTE=20 Δ=0.26 close=$2.18
  Cash need: $25,200
  Decision: ❌ blocked — cash_collateral: would exceed 60% liquid cap
```

Format follows existing Q041 alert style. Skip days with no candidate found → suppress message (avoid noise).

### 2.7 Dashboard wiring

[web/templates/q041.html:341-379](../web/templates/q041.html#L341-L379) 已有 T2 GOOGL + T2 AMZN candidate spec hardcoded in JS。改动:

- `/api/q041/overview` endpoint 加入 T2 paper signal 当日状态（candidate / governance decision / blocked reason）
- T2 candidate cards 显示:
  - 当日 candidate found (K / Δ / close / cash_need)
  - Governance decision (accepted / blocked + reason)
  - 累计统计: total signals / total blocked / total fired (paper)
- Banner 提示: "Phase A 期望多数日 blocked by SPEC-111 cap; 仅验证 cash-bound 边界"

### 2.8 launchd plist

`com.spxstrat.q041_t2_paper_signals.plist` — daily 16:50 ET Mon-Fri (after chain_sanity 16:45)。

---

## 3. Acceptance Criteria

### AC-1 — T2 candidate selection from same-day chain
Given `data/q041_chains/2026-06-05/GOOGL.parquet`, `select_t2_csp("q041_t2_googl_csp", "2026-06-05")` returns candidate dict with `delta ∈ [0.15, 0.25]`, `dte ∈ [18, 24]`, `close > 0.10`, `cash_need_usd = strike * 100`.

### AC-2 — SPEC-111 extension covers CSP
Given candidate `{"strategy_key": "q041_t2_googl_csp", "cash_need_usd": 36600, "paper_trade": True}`, `evaluate_cash_collateral_budget` returns `accepted=False`, `reason="cash_collateral: would exceed 60% liquid cap"`.

### AC-3 — Paper trade no longer bypasses cash gate
Given candidate `{"strategy_key": "q041_t2_googl_csp", "paper_trade": True, "cash_need_usd": 36600}`, `evaluate_candidate(candidate)` in `sleeve_governance.py` returns `accepted=False` with reason mentioning cash collateral. (Without SPEC-115 changes, this would return `accepted=True` because paper skipped cap.)

### AC-4 — BCD path backward compatible
Given candidate `{"strategy_key": "bull_call_diagonal", "entry_debit_usd": 5000, "paper_trade": False}`, governance decision unchanged from pre-SPEC-115 behavior (read `entry_debit_usd` field still works via fallback in `evaluate_cash_collateral_budget`).

### AC-5 — Paper log writes blocked events
After daily signal job runs, `data/q041_paper_log.jsonl` contains a `blocked` event per candidate per day (when governance rejects).

### AC-6 — Paper log writes open events when within cap
**Hypothetical test**: mock GOOGL chain with K=$200 (cash_need = $20,000 ≤ $22,200 cap). `evaluate_candidate` returns `accepted=True`. Paper log writes `open` event.

### AC-7 — Telegram daily signal format
Daily 16:50 ET job pushes Telegram message matching §2.6 format. Both candidates' decisions visible. Skip push if no candidate found for both.

### AC-8 — Dashboard T2 cards render decisions
`/api/q041/overview` returns T2 candidate + decision in JSON. q041.html T2 cards display K/Δ/close/cash_need + governance decision + cumulative count.

### AC-9 — Phase A observation criterion (NOT a tripwire — info only)
After 1 week post-deploy, count of `open` events in `q041_paper_log.jsonl`:
- 0 opens = expected (verifies cash-binding) — log "Phase A baseline observation 0 fires"
- 1-3 opens (GOOGL or AMZN price dropped) = unexpected but informative — Quant review
- ≥4 opens = unexpected pattern, investigate why cap stopped binding

---

## 4. Files to change

| File | Action |
|---|---|
| `strategy/cash_budget_governance.py` | EDIT — rename `DEBIT_STRATEGIES` → `CASH_OCCUPYING_STRATEGIES`; add `evaluate_cash_collateral_budget()`; generic `cash_need_usd` field; backward-compat alias |
| `strategy/sleeve_governance.py:1095` | EDIT — drop `and not is_paper` condition; rename call to `evaluate_cash_collateral_budget` |
| `strategy/catalog.py` | EDIT — add 2 `StrategyDescriptor` entries (`q041_t2_googl_csp`, `q041_t2_amzn_csp`) |
| `strategy/q041_selector.py` | NEW — `select_t2_csp()` per §2.4 |
| `data/q041_paper_log.jsonl` | NEW (runtime-created) |
| `notify/q041_paper_telegram.py` | NEW — daily signal push job per §2.6 |
| `web/server.py` `/api/q041/overview` | EDIT — return T2 candidate + decision |
| `web/templates/q041.html` | EDIT — wire T2 cards to API + banner |
| `~/Library/LaunchAgents/com.spxstrat.q041_t2_paper_signals.plist` | NEW — daily 16:50 ET (oldair deploy) |
| `tests/test_q041_t2_selector.py` | NEW — AC-1 |
| `tests/test_spec_115_cash_collateral.py` | NEW — AC-2/3/4 |
| `tests/test_q041_paper_log.py` | NEW — AC-5/6 |

---

## 5. Test plan

```bash
arch -arm64 venv/bin/python -m pytest tests/test_q041_t2_selector.py tests/test_spec_115_cash_collateral.py tests/test_q041_paper_log.py -v

# Existing regression must still pass:
arch -arm64 venv/bin/python -m pytest tests/test_spec_113_carve.py tests/test_spec_113_bit_identical.py tests/test_strategy_unification.py -v

# AC-5 replay on real data
arch -arm64 venv/bin/python -m notify.q041_paper_telegram --date 2026-06-05 --dry-run
# Expect: 2 candidates produced, both blocked by cash collateral cap

# Deploy plist + LaunchAgent
scp com.spxstrat.q041_t2_paper_signals.plist oldair:~/Library/LaunchAgents/
ssh oldair "launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_t2_paper_signals.plist"
```

---

## 6. Rollout

1. Dev: impl + 单测 → push
2. Dev: deploy oldair (git pull + plist load)
3. **Smoke check first 16:50 ET**: verify Telegram message format + paper_log.jsonl 写入
4. **PM first-week observation** (T+5 trading days):
   - 检查 Telegram daily push 是否如预期: 多数日 GOOGL/AMZN 都 blocked
   - 如果有意外 open event (GOOGL/AMZN 价格够低): PM 看 paper trade fire 是否合理
5. **T+30 retrospective** (与 SPEC-113 T+30 同 cadence; 是否合并 schedule 由 Quant 决定): paper log 统计 + 是否调 SPEC-111 cap/floor
6. **Backtest cache refresh**: 否，monitoring 层 + paper trade，未触发 backtest 重跑

---

## 7. Forward dependency

Phase B (T3 COST + JPM earnings IC) 起始条件:
- Phase A 已 ship + 1 周观察期完成
- PM 看 SPEC-115 Phase A 实际效果 (paper signal flow / governance decision visibility) 是否符合预期
- Phase B SPEC 起 (`task/SPEC-115_phase_b.md`) 时引用 Phase A 的 paper-trade infrastructure (Phase A 已 hardened)

---

## 8. Related

- [task/SPEC-111.md](SPEC-111.md) — cash budget governance (extended by this SPEC)
- [task/SPEC-113.md](SPEC-113.md) — BCD carve (current sole user of DEBIT_STRATEGIES set)
- [task/SPEC-114.md](SPEC-114.md) — chain sanity (predecessor, deployed `fe6b6f7`)
- [task/SPEC-115_outline.md](SPEC-115_outline.md) — phase plan
- [doc/q041_execution_prep_packet_2026-05-05.md](../doc/q041_execution_prep_packet_2026-05-05.md) — 5/5 T2 spec defaults
- [doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md](../doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md) — Phase 2 evidence
- `feedback_post_withdrawal_proposals_front_load_robustness`, `feedback_absolute_at_today_scale_not_historical_ratio` — relevant memory rules
