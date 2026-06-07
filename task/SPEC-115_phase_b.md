# SPEC-115 Phase B — Q041 T3 COST + JPM Earnings IC Paper Trade Promote

**Type**: strategy promote / event-driven paper trade / cash collateral extension
**Date**: 2026-06-07
**Status**: **RATIFIED** by PM 2026-06-07 (skip phase A 1-week obs, 直接起 phase B)
**Cross-reference**: [task/SPEC-115_outline.md](SPEC-115_outline.md), [task/SPEC-115_phase_a.md](SPEC-115_phase_a.md) (ship `446037e`)
**Predecessors (deployed)**: SPEC-114 `fe6b6f7`, SPEC-115 phase A `446037e`
**Owner**: Quant Researcher (this draft) → Developer (impl)

---

## 0. TL;DR

Promote Q041 Tier 3 **COST earnings IC T-3 1.0×** + **JPM earnings IC T-3 1.0×** to event-driven paper trade lane. 共四件事：

1. **Earnings calendar** 数据源：yfinance `Ticker.calendar` + stale guard (返回历史日期则跳过 + alert)
2. **T-3 trigger + entry filter**: NYSE-trading-day countdown to earnings; `VIX ≥ 15` gate; JPM optional `IMR ≥ 33%` (best-effort, skip if data missing)
3. **IC structure**: ATM short straddle wings + 1.0× implied-move long protection (4 legs); `cash_need = max_loss × 100 × n` 入 SPEC-111 `CASH_OCCUPYING_STRATEGIES`
4. **T+1 auto close**: 财报次日强制 close (paper) → 记录 realized_move + 击穿与否 + PnL

**预期产出**:
- 每名每季 1 IC fire, ≈ 8 events/yr (COST 4 + JPM 4 quarters)
- 单 contract cash collateral: COST ≈ $4.2k / JPM ≈ $2k —— **远低于** SPEC-111 cap $10,151 (当前 $16,918 liquid × 60%); 即使 floor $30k 当前 violated 也允许 paper open (governance 显示 floor warning 但接受 paper 标记)
- 与 Phase A 不同：**Phase B paper trade 会 fire**，PM 看到真实 IC 进出

---

## 1. Background

### 1.1 5/5 packet T3 spec

Per [doc/q041_execution_prep_packet_2026-05-05.md](../doc/q041_execution_prep_packet_2026-05-05.md) §4：

| 参数 | COST IC | JPM IC |
|---|---|---|
| 入场 | T-3（财报日前第 3 个交易日） | T-3 |
| 结构 | Iron Condor (双边 credit spread) | Iron Condor |
| 宽度 | 1.0× ATM straddle 隐含移动 | 1.0× |
| Entry filter | `VIX ≥ 15` | `VIX ≥ 15` + optional `IMR ≥ 33%` |
| DTE 选择 | 找最近"财报后"到期日（DTE 1-14 天，覆盖财报日） | 同 |
| 出场 | T+1 (财报次日) auto close | 同 |
| 每名每季 | 1 contract | 1 contract |

### 1.2 5/5 packet T3 evidence

Per [doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md](../doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md):
- COST 4y backtest: **N=15**, win rate ~67%, 单事件经济性可接受
- JPM 4y backtest: **N=9**, win rate ~67%, 但样本极小
- VIX ≥ 15 是 weak-loss regime gate (Phase 2 P2-2 finding)
- COVID-era earnings 未在样本内（4y window 起 2022-05 之后）

### 1.3 Cash collateral 估算（per 5/5 packet §4.3）

| | COST | JPM |
|---|---:|---:|
| Spot ~ | $972 (Schwab 2026-06-05 chain) | ~$312 (5/5 estimate) |
| Expected implied_move | ~4.2% | ~6.3% |
| Spread width (1.0×) | ≈ $42 | ≈ $20 |
| **Max loss per contract (= cash collateral proxy)** | **$4,200** | **$2,000** |
| vs SPEC-111 cap ($10,151 at current liquid $16,918) | ✅ fits | ✅ fits |
| vs SPEC-111 floor ($30,000) | ⚠️ liquid already below | ⚠️ same |

**SPEC-111 floor 警告**: 当前 liquid $16,918 < $30k floor。Per `evaluate_cash_collateral_budget`, paper trade candidate 触发 floor block。**这是个设计决定点 (§2.5 below).**

### 1.4 Phase A 与 Phase B 互动

- Phase A T2 GOOGL/AMZN: daily rolling，cash_need per contract 远超 cap → 多数日 blocked
- Phase B T3 COST/JPM: event-driven (8 events/yr)，cash_need 在 cap 内 → 可 fire
- 共享 `q041_paper_log.jsonl` + SPEC-111 `CASH_OCCUPYING_STRATEGIES` set
- Phase B `cash_need_usd` 字段语义和 Phase A 一致 (paper governance 用同一 cap math)

---

## 2. Specification

### 2.1 Earnings calendar data source

**Primary**: yfinance `Ticker.calendar` (PM ratify 2026-06-06 Q-3 = yfinance)

```python
import yfinance as yf
def get_next_earnings_date(symbol: str) -> date | None:
    """Returns next upcoming earnings date for symbol, or None if missing/stale."""
    t = yf.Ticker(symbol)
    cal = t.calendar
    if not cal or "Earnings Date" not in cal:
        return None
    dates = cal["Earnings Date"]
    if not dates:
        return None
    next_date = dates[0] if isinstance(dates, list) else dates
    if next_date < date.today():
        return None  # stale (yfinance sometimes returns last past date)
    return next_date
```

**Stale guard**: 如果 yfinance 返回历史日期（earnings 已发布但 yfinance 没刷），`get_next_earnings_date` 返回 `None` → Phase B skip 当 cycle。

**Refresh cadence**: daily 16:30 ET via launchd (after `q041_collect`)。yfinance no-cache，每天最新 call。

**Cache file**: `data/q041_earnings_calendar.json` 存最新 next-earnings-date 每 symbol，便于 dashboard 显示。

**Dev dependency**: yfinance >= 0.2.0，`pip install lxml` (for HTML parsing in yfinance internals — current venv 缺)。

**Fallback**: 如果 yfinance fail (network / parse error), 写 `data/q041_earnings_alert.jsonl` 一条 + Telegram alert. PM 可手动 override cache file。

### 2.2 T-3 trigger + entry filter

**T-3 算法** (per 5/5 packet §4.2):
- T 0 = earnings date (from yfinance)
- T-3 = 3 NYSE trading days before T 0 (skip weekends + holidays)
- Use existing `_US_HOLIDAYS_2026` set from `daily_chain_sanity.py` for holiday calendar

**Daily check** (each trading day 16:50 ET, after Phase A T2 push):
```
for sym in ["COST", "JPM"]:
    earn_date = get_next_earnings_date(sym)
    if not earn_date: continue
    days_to = trading_days_until(earn_date)
    if days_to == 3:  # exactly T-3
        # Trigger Phase B IC entry flow
        ...
```

**Entry filter**:
1. `VIX ≥ 15` (read from existing VIX snapshot, same as SPX selector)
2. JPM optional `IMR ≥ 33%`: 
   - IMR = current implied_move 在过去 8 个 COST/JPM earnings 周期中的 percentile rank
   - Compute: for each historical earnings_date in past 4y, compute implied_move on T-3 (via Schwab IV at that date if available; else skip)
   - **Phase B v1 simplification**: 如果历史 IMR 数据缺失（< 4 个 historical IMR），**skip IMR check** (best-effort, per 5/5 packet "可选 / 次要"). 写 paper log 标 `imr_check: skipped`.

### 2.3 IC selector — ATM + 1.0× implied move

**New file**: `strategy/q041_t3_selector.py`

```python
def select_t3_earnings_ic(strategy_key: str, asof_date: str, earn_date: date) -> dict | None:
    """Build T-3 IC candidate.

    Returns:
      {
        "strategy_key": str,
        "underlying": str,
        "asof_date": str,
        "earn_date": str,
        "vix_entry": float,
        "spot": float,
        "atm_strike": float,
        "implied_move_pct": float,  # straddle / spot
        "implied_move_usd": float,  # = implied_move_pct * spot
        "spread_width_usd": float,  # = implied_move_usd * 1.0
        "K_short_put": float,       # ATM
        "K_long_put": float,        # ATM - spread_width
        "K_short_call": float,      # ATM
        "K_long_call": float,       # ATM + spread_width
        "expiry": str,              # post-earnings nearest expiry, DTE 1-14
        "dte": int,
        "net_credit_usd": float,    # sum of (short_close - long_close) × 100
        "max_loss_usd": float,      # = (spread_width_usd - net_credit_per_share) × 100
        "cash_need_usd": float,     # = max_loss_usd (for SPEC-111 gate)
        "imr_rank_pct": float | None,  # JPM only; None if skipped
        "paper_trade": True,
      }
      or None if any step fails.
    """
    # 1. Read Schwab chain
    # 2. Find spot (from _underlying.parquet)
    # 3. Find earliest expiry with DTE ∈ [1, 14] covering earn_date
    #    Use earn_date < expiry < earn_date + 14d
    # 4. Find ATM (strike closest to spot)
    # 5. Compute straddle = ATM_call.close + ATM_put.close
    # 6. implied_move = straddle / spot
    # 7. width = implied_move × spot × 1.0
    # 8. Find K_long_put ≈ ATM - width, K_long_call ≈ ATM + width
    #    (closest available strikes; record actual K used)
    # 9. Read close prices for 4 legs:
    #    K_short_put.close (sell)
    #    K_long_put.close (buy)
    #    K_short_call.close (sell)
    #    K_long_call.close (buy)
    # 10. net_credit = sum(short.close) - sum(long.close)
    # 11. max_loss = (width - net_credit) × 100  per contract
    # 12. Return candidate dict
    ...
```

### 2.4 catalog T3 StrategyDescriptors

```python
"q041_t3_cost_earnings_ic": StrategyDescriptor(
    key="q041_t3_cost_earnings_ic",
    name="Q041 T3 COST Earnings IC",
    emoji="📅",
    direction="neutral",
    underlying="COST",
    trade_type="Credit — Iron Condor (Earnings Paper)",
    dte_text="1-14 DTE (post-earnings nearest)",
    delta_text="ATM straddle wings, 1.0× implied move width",
    when_text=(
        "T-3 trading days before COST earnings; VIX ≥ 15 gate. "
        "Q041 paper-trade lane (observe-only → cautious paper per PM 2026-06-06)."
    ),
    risk_text=(
        "Max loss = width × 100 ≈ $4,200; 单事件击穿风险 (S_exit < K_put OR > K_call). "
        "N=15 backtest, 4y window missing COVID/2019-2021. SPEC-111 cap binds."
    ),
    detail_roll_text="No roll. T+1 (earnings 次日) auto close.",
    max_risk_text="(spread_width - net_credit) × 100 per contract.",
    target_return_text="Full credit at T+1 if both strikes hold.",
    roll_rule_text="None — paper observation lane.",
    short_gamma=True,
    short_vega=True,
    delta_sign="neut",
    manual_entry_allowed=False,
),

"q041_t3_jpm_earnings_ic": StrategyDescriptor(
    key="q041_t3_jpm_earnings_ic",
    name="Q041 T3 JPM Earnings IC",
    emoji="📅",
    direction="neutral",
    underlying="JPM",
    trade_type="Credit — Iron Condor (Earnings Paper)",
    dte_text="1-14 DTE (post-earnings nearest)",
    delta_text="ATM straddle wings, 1.0× implied move width",
    when_text=(
        "T-3 trading days before JPM earnings; VIX ≥ 15 gate. "
        "Optional IMR ≥ 33% filter (skip if historical data missing)."
    ),
    risk_text=(
        "Max loss = width × 100 ≈ $2,000; N=9 backtest (very small sample). "
        "4y window missing COVID/2019-2021. SPEC-111 cap binds."
    ),
    detail_roll_text="No roll. T+1 auto close.",
    max_risk_text="(spread_width - net_credit) × 100 per contract.",
    target_return_text="Full credit at T+1 if both strikes hold.",
    roll_rule_text="None — paper observation lane.",
    short_gamma=True,
    short_vega=True,
    delta_sign="neut",
    manual_entry_allowed=False,
),
```

### 2.5 SPEC-111 extension for IC cash collateral

Add 2 keys to `CASH_OCCUPYING_STRATEGIES` in `strategy/cash_budget_governance.py`:

```python
CASH_OCCUPYING_STRATEGIES = frozenset({
    "bull_call_diagonal",        # SPEC-113
    "q041_t2_googl_csp",         # SPEC-115 phase A
    "q041_t2_amzn_csp",          # SPEC-115 phase A
    "q041_t3_cost_earnings_ic",  # SPEC-115 phase B (NEW)
    "q041_t3_jpm_earnings_ic",   # SPEC-115 phase B (NEW)
})
```

**Important — IC max_loss as cash_need**:
- IC 不是 CSP（没有 K × 100 担保），cash_need 实际是 broker margin requirement for credit spread
- 在 PM 账户里，IC 的 BP requirement ≈ max_loss × 100 (per 5/5 packet §4.3, "max BP per contract ≈ $4,200 spread max loss")
- 因此 `cash_need_usd = max_loss_usd` 是 conservative approximation

**Cash floor 处理**:
- 当前 liquid $16,918 < $30k floor → 任何 cash_occupying 都被 floor block
- Phase A T2 已经接受这个行为 (paper signal 显示 cash_floor blocked)
- Phase B T3 cash_need 实际很小 ($2k-$4k), 应该 fire 但 floor 拦

**设计决定 (内嵌, 不再问 PM)**:
- Paper trade 走严格 floor (per PM 2026-06-07 拍板 "paper 走严格双 cap")
- 即 T3 IC paper signal **当前 liquid < floor 时也 blocked**
- Paper log 写 blocked event，显示 reason `cash_floor: liquid ${X} < $30,000 floor`
- 这与 PM 6/7 决定一致：paper trade is production-readiness verifier，not toy

**Implication for PM**: 当前 cash state 下 Phase B T3 也不会 fire。只有 PM cash 池回升 > $30k floor 时 T3 才能 fire。这是 cash-bound boundary 的进一步 verify。

### 2.6 Paper log + Telegram (event-driven, 与 Phase A 区别)

Phase A 是 daily push (每个交易日 16:50 都 emit T2 signal)。Phase B 是 **event-driven**:
- T-3 day: full IC candidate evaluation + open/blocked event push
- T-2/T-1 days: silent (no push)
- T 0 day (earnings): silent (paper hold)
- T+1 day: auto-close (simulated using next-day Schwab chain) + close event push with realized_move 计算

```
📅 Q041 T3 Paper Signal: COST T-3 (earn_date 2026-05-28)
  Spot: $972.35  VIX: 16.4 ✅ (≥15)
  ATM straddle: $41.08 (IV-implied move: 4.22%)
  Spread width: $41 (=ATM_call + ATM_put × 1.0)
  K_short_put: 972  K_long_put: 931  K_short_call: 972  K_long_call: 1013
  Net credit: $14.20 per share = $1,420 per contract
  Max loss: ($41 - $14.20) × 100 = $2,680 per contract
  Cash need (SPEC-111 gate): $2,680
  Decision: ❌ blocked — cash_floor: liquid $16,918 < $30,000 floor
            (would fit cap $10,151 otherwise)
```

T+1 close push:
```
📅 Q041 T3 Paper Close: COST T+1 (earn 2026-05-28)
  Realized move (T 0 close to T+1 close): +$28.50 (2.93%)
  Implied move (entry): $41.08 (4.22%)
  S_exit: $1,000.85  ∈ [K_put 931, K_call 1013] ✅ both strikes held
  Paper PnL: +$1,420 (full credit captured)
```

### 2.7 T+1 auto close

After earnings (T 0), T+1 calendar/trading day:
- Read Schwab chain on T+1
- Compute realized_move = (T+1_close - T 0_close) / T 0_close
- Determine 击穿: S_exit < K_short_put OR S_exit > K_short_call
- Paper PnL:
  - If neither strike breached: PnL = net_credit (full)
  - If short put breached (S_exit < K_put_short): PnL = net_credit - min(max_loss, (K_put_short - S_exit) × 100)
  - If short call breached: 同 symmetric
- Write `close` event to paper_log + Telegram push

### 2.8 launchd plist

Single new job: `com.spxstrat.q041_t3_earnings_check.plist`
- 16:55 ET Mon-Fri (after Phase A T2 push 16:50)
- Runs `python -m notify.q041_t3_earnings_check`
- Module logic:
  - For each T3 symbol: check `days_to_earnings`
  - If `days_to == 3`: trigger IC entry flow
  - If `days_to == -1` (i.e., yesterday was earnings): trigger T+1 close flow
  - All other days: silent

`com.spxstrat.q041_earnings_calendar_refresh.plist` (optional separate):
- 09:00 ET daily, refresh yfinance calendar cache
- Or fold into 16:55 main job (simpler)

---

## 3. Acceptance Criteria

### AC-1 — yfinance earnings calendar
`get_next_earnings_date("COST")` returns a `date` ≥ today; `get_next_earnings_date("JPM")` 同。If yfinance returns stale historical date, function returns `None`.

### AC-2 — T-3 trigger arithmetic
`trading_days_until(date(2026,7,14))` for asof_date 2026-07-09 (Thu) returns 3 (Fri=1, Mon=2, Tue=3 trading days). 

### AC-3 — VIX gate
Mock VIX = 14.5 + T-3 trigger: candidate evaluation skipped (gate not satisfied). Write `blocked` paper log event with reason `vix_gate: 14.5 < 15.0`.

### AC-4 — IC candidate construction
Given `data/q041_chains/2026-06-05/COST.parquet` + mocked yfinance earn_date = 2026-06-08 (so 6/5 = T-3): `select_t3_earnings_ic` returns dict with 4 strikes, net_credit > 0, max_loss > 0, cash_need_usd = max_loss_usd.

### AC-5 — SPEC-111 IC cash gate
Given candidate with `strategy_key="q041_t3_cost_earnings_ic"`, `cash_need_usd=2680`, current liquid `$16,918`: `evaluate_cash_collateral_budget` returns `accepted=False`, reason mentions `cash_floor`.

### AC-6 — Hypothetical fit case (cash floor restored)
Mock `get_current_liquid_cash` returns `$40,000`; IC cash_need_usd `$2,680`: `evaluate_cash_collateral_budget` returns `accepted=True`. Paper log writes `open` event.

### AC-7 — T+1 close logic — neither strike breached
Mock entry: K_put=931, K_call=1013, net_credit=$1,420, max_loss=$2,680. T+1 spot=$1,000: close logic returns PnL = +$1,420 (full credit), event `close` written.

### AC-8 — T+1 close logic — short put breached
Mock entry same; T+1 spot=$920 (< K_put 931): PnL = $1,420 - min($2,680, (931-920)*100) = $1,420 - $1,100 = +$320.

### AC-9 — T+1 close logic — short call breached
T+1 spot=$1,025 (> K_call 1013): PnL = $1,420 - min($2,680, (1025-1013)*100) = $1,420 - $1,200 = +$220.

### AC-10 — JPM IMR best-effort
Mock JPM candidate: IMR data unavailable. Paper log records `imr_check: skipped`, candidate proceeds (no block).

### AC-11 — Telegram T-3 message format
matches §2.6 template; T-2/T-1 days silent (no push).

### AC-12 — Telegram T+1 close message
Includes realized_move + 击穿 detection + paper PnL.

### AC-13 — Calendar refresh
Daily 09:00 ET (or 16:55 fold-in) yfinance call updates `data/q041_earnings_calendar.json`. If yfinance error, writes alert.

---

## 4. Files to change

| File | Action |
|---|---|
| `strategy/cash_budget_governance.py` | EDIT — add 2 T3 keys to `CASH_OCCUPYING_STRATEGIES` |
| `strategy/catalog.py` | EDIT — add 2 T3 StrategyDescriptors |
| `strategy/q041_t3_selector.py` | NEW — `select_t3_earnings_ic()` + IC construction |
| `strategy/q041_earnings_calendar.py` | NEW — `get_next_earnings_date()` + cache + stale guard |
| `notify/q041_t3_earnings_check.py` | NEW — event-driven daily check (T-3 / T+1 logic) |
| `web/server.py` `/api/q041/overview` | EDIT — add T3 paper signal state + next-earnings countdown |
| `web/templates/q041.html` | EDIT — wire T3 cards (line 370-379 已有 spec) + countdown chip |
| `~/Library/LaunchAgents/com.spxstrat.q041_t3_earnings_check.plist` | NEW (oldair) — 16:55 ET Mon-Fri |
| `data/q041_earnings_calendar.json` | NEW (runtime) |
| `tests/test_q041_earnings_calendar.py` | NEW — AC-1/2/13 |
| `tests/test_q041_t3_selector.py` | NEW — AC-4 |
| `tests/test_q041_t3_governance.py` | NEW — AC-3/5/6/10 |
| `tests/test_q041_t3_close_logic.py` | NEW — AC-7/8/9 |
| `tests/test_q041_t3_telegram.py` | NEW — AC-11/12 |
| `pyproject.toml` or `requirements.txt` | EDIT — add `lxml` for yfinance |

---

## 5. Test plan

```bash
# Add lxml
arch -arm64 venv/bin/pip install lxml

# Unit tests
arch -arm64 venv/bin/python -m pytest tests/test_q041_earnings_calendar.py \
  tests/test_q041_t3_selector.py tests/test_q041_t3_governance.py \
  tests/test_q041_t3_close_logic.py tests/test_q041_t3_telegram.py -v

# Regression (Phase A + SPEC-113)
arch -arm64 venv/bin/python -m pytest tests/ -k 'spec_113 or spec_115 or sleeve_governance' -v

# Smoke test — yfinance integration
arch -arm64 venv/bin/python -m strategy.q041_earnings_calendar --refresh
cat data/q041_earnings_calendar.json
# Expect: {"COST": "2026-XX-XX", "JPM": "2026-07-14", "refreshed_at": "..."}

# AC-4 replay
arch -arm64 venv/bin/python -m notify.q041_t3_earnings_check --date 2026-06-05 --dry-run \
  --mock-earn "COST:2026-06-08,JPM:2026-06-09"
# Expect: both produce T-3 candidates (full IC structure printed), both blocked by cash_floor

# Deploy
scp com.spxstrat.q041_t3_earnings_check.plist oldair:~/Library/LaunchAgents/
ssh oldair "launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_t3_earnings_check.plist"
ssh oldair "launchctl list | grep q041"
# Expect 4 jobs: q041_collect / q041_chain_sanity / q041_t2_paper_signals / q041_t3_earnings_check
```

---

## 6. Rollout

1. Dev: impl + tests → push
2. Dev: deploy oldair (git pull + plist load + pip install lxml in oldair venv)
3. Smoke check 第一次 16:55 ET 跑：verify `q041_earnings_calendar.json` 写入 + 当前 days_to_earnings 显示
4. **Wait for first real T-3 trigger**:
   - JPM next earnings ~ 2026-07-14 → T-3 = 2026-07-09 (Thu)
   - COST next earnings TBD (yfinance may have stale data — verify after deploy)
5. T-3 event 时 PM 看 Telegram message format + dashboard 更新
6. T+1 close event 时 PM 看 close logic + paper PnL 正确性
7. 1 个完整 earnings cycle 后（约 1 季度 = 4 events）PM 复盘

---

## 7. Phase A + Phase B 共存

Phase A (T2) + Phase B (T3) **完全独立**:
- Phase A daily push (T2 GOOGL/AMZN), Phase B event-driven (T-3/T+1 only)
- 共用 `q041_paper_log.jsonl`（events tagged by strategy_key）
- 共用 SPEC-111 `CASH_OCCUPYING_STRATEGIES` set + cap math
- Dashboard q041.html 上 T2/T3 cards 并列显示
- Telegram daily push 通道不同（Phase A 每日, Phase B 仅 T-3/T+1）

---

## 8. Open dev questions

1. **lxml install on oldair venv**: `arch -arm64 venv/bin/pip install lxml`. Verify import works.
2. **yfinance `Ticker.calendar` 在 oldair 网络环境是否畅通**: 实测一次, 部分 ISP 可能限速 Yahoo。
3. **IMR history compute** (JPM optional): 是否在 Phase B v1 实现, 还是延期 Phase B v2? 建议 v1 skip (per 5/5 packet "可选"), 不阻塞 ship.
4. **earnings calendar 历史校验**: yfinance 偶尔返回 stale dates (例如 COST 显示 2026-05-28 已过). Dev impl `get_next_earnings_date` 中的 stale guard 是必须的, 不能依赖 yfinance 自动 refresh.
5. **`/api/q041/overview` T3 状态字段命名**: 推荐 `t3_paper_state` + `t3_paper_counts`, 与 Phase A `t2_*` 字段并列.

---

## 9. Related

- [task/SPEC-115_outline.md](SPEC-115_outline.md) — phase plan
- [task/SPEC-115_phase_a.md](SPEC-115_phase_a.md) — Phase A SPEC + ship
- [task/SPEC-111.md](SPEC-111.md) — cash budget (extended again here)
- [task/SPEC-113.md](SPEC-113.md) — BCD (current `CASH_OCCUPYING_STRATEGIES` 共用)
- [doc/q041_execution_prep_packet_2026-05-05.md](../doc/q041_execution_prep_packet_2026-05-05.md) §4 — T3 IC spec
- [doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md](../doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md) — Phase 2 evidence
- `feedback_post_withdrawal_proposals_front_load_robustness`, `feedback_absolute_at_today_scale_not_historical_ratio` — memory rules
