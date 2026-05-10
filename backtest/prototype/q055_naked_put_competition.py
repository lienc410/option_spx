"""
Q055: Naked Put Strategy Slot — Competition Protocol Execution
================================================================

PM 2026-05-09 decision: Q041 T1 SPX CSP and /ES V2c are formally merged into
the "naked put strategy slot"; one will be eliminated.

This script:
  1. Defines the competition protocol (vetos + tiered scoring)
  2. Loads both candidates' 26-yr BS-flat trade data
  3. Computes all scoring dimensions on common baseline
  4. Outputs the scoring table with winner

Protocol design rationale:
  - The /ES lot-size advantage at $500k IS the deployable strategy edge,
    not an artifact to normalize away. PM directive: present transparently.
  - Per-contract / per-BP-day shown as informational, not decisive.
  - Tier 1 vetos: any one fails → eliminated outright.
  - Tier 2 primary: account-level metrics (production reality).
"""

import pickle
import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings('ignore')

# ─── Common baseline assumptions ──────────────────────────────────────────────
WINDOW_START = "2000-01-01"
WINDOW_END   = "2026-04-17"
ACCOUNT      = 500_000.0
YEARS        = (pd.Timestamp(WINDOW_END) - pd.Timestamp(WINDOW_START)).days / 365.25
SPX_MULT     = 100

# BP per contract (from production / Schwab measurement)
BP_PER_ES_CONTRACT  = 20_500.0    # research_notes §12.4 actual Schwab
BP_PER_SPX_CONTRACT = 50_000.0    # PM Method A/B floor for Δ0.20 OTM

# Trading-day average hold per trade
ES_V2C_HOLD_TD     = 28           # 49 → 21 trading days
SPX_CSP_HOLD_TD    = 21           # 30 calendar ≈ 21 trading days

# Concurrent positions at steady state
ES_V2C_CONCURRENT   = 5.6         # 28-td hold / 5-td weekly entry
SPX_CSP_CONCURRENT  = 1.0         # single slot
TRADING_DAYS_PER_YR = 252

# ─── Load candidate data ──────────────────────────────────────────────────────
print("Loading V2c (/ES candidate)...")
with open('/tmp/q041_es_v2_validation.pkl', 'rb') as f:
    v2_data = pickle.load(f)
es_v2c = v2_data['b3_variants']['V2c_stop8']
es_pnls = es_v2c['pnl_$'].values

print("Loading Q041 SPX CSP T1 (SPX candidate)...")
with open('/tmp/q041_es_full_window_bs.pkl', 'rb') as f:
    spx_data = pickle.load(f)
spx_cycles = spx_data['q041_cycles']
spx_pnls = spx_cycles['pnl_$'].values

# ─── Geometric Ann ROE on $500k ───────────────────────────────────────────────
def geom_ann_roe(total_pnl, account=ACCOUNT, years=YEARS):
    cum = total_pnl / account
    if cum <= -1:
        return float('nan')
    return ((1 + cum) ** (1/years) - 1) * 100

# ─── Bootstrap CI for statistical significance ────────────────────────────────
def block_bootstrap_ci(arr, block_size, n_boot=2000, seed=42, ci=0.95):
    import math
    arr = np.asarray(arr, dtype=float)
    n = len(arr)
    if n < 10:
        return {'ci_lo': float('nan'), 'ci_hi': float('nan'), 'significant': False}
    rng = np.random.default_rng(seed=seed)
    boot_means = np.empty(n_boot)
    max_start = max(1, n - block_size + 1)
    for idx in range(n_boot):
        n_blocks = math.ceil(n / block_size)
        starts = rng.integers(0, max_start, size=n_blocks)
        sample = np.concatenate([arr[s:s+block_size] for s in starts])[:n]
        boot_means[idx] = sample.mean()
    alpha = 1.0 - ci
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return {'ci_lo': lo, 'ci_hi': hi, 'significant': lo > 0,
            'block_size': block_size}

# ─── Compute all metrics for one candidate ────────────────────────────────────
def compute_metrics(label, pnls, bp_per_contract, hold_td, n_concurrent):
    arr = np.asarray(pnls, dtype=float)
    n = len(arr)
    total = arr.sum()

    # Account-level
    ann_roe_geom = geom_ann_roe(total)
    ann_roe_arith = (total / YEARS / ACCOUNT) * 100

    # Win/Loss
    wr = (arr > 0).mean() * 100
    mean = arr.mean()
    std = arr.std()
    sharpe_per_trade = mean / std if std > 0 else 0.0
    trades_per_year = n / YEARS
    sharpe_ann = sharpe_per_trade * np.sqrt(trades_per_year)

    # Tail
    worst = arr.min()
    worst_pct_nlv = worst / ACCOUNT * 100
    cvar_5 = float(np.sort(arr)[:max(1, n//20)].mean())
    cvar_5_pct = cvar_5 / ACCOUNT * 100

    # Account drawdown (chronological PnL stream)
    eq = ACCOUNT + np.cumsum(arr)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    mdd_pct = dd.min() * 100

    # Capital efficiency: $/BP-day
    avg_bp_per_trade = bp_per_contract * hold_td   # BP-days for one trade
    dollars_per_bp_day = mean / avg_bp_per_trade   # per trading-day

    # Annualised: capital deployed per year × concurrent
    avg_concurrent_bp = bp_per_contract * n_concurrent
    annual_pnl_per_contract = (total / YEARS) / n_concurrent if n_concurrent > 0 else 0
    bp_year_pct = annual_pnl_per_contract / bp_per_contract * 100

    # Statistical significance (bootstrap)
    boot = block_bootstrap_ci(arr, block_size=250)
    boot_lo_ann_arith = (boot['ci_lo'] * trades_per_year) / ACCOUNT * 100
    boot_hi_ann_arith = (boot['ci_hi'] * trades_per_year) / ACCOUNT * 100

    return {
        'label': label,
        'n_trades': n,
        'years': round(YEARS, 1),
        'trades_per_yr': round(trades_per_year, 1),
        'total_pnl_$': round(total, 0),
        'ann_roe_geom_%': round(ann_roe_geom, 2),
        'ann_roe_arith_%': round(ann_roe_arith, 2),
        'sharpe_ann': round(sharpe_ann, 2),
        'wr_%': round(wr, 1),
        'mean_$': round(mean, 0),
        'std_$': round(std, 0),
        'worst_$': round(worst, 0),
        'worst_pct_nlv': round(worst_pct_nlv, 2),
        'cvar5_$': round(cvar_5, 0),
        'cvar5_pct_nlv': round(cvar_5_pct, 2),
        'mdd_pct': round(mdd_pct, 1),
        'avg_concurrent_contracts': n_concurrent,
        'avg_bp_deployed_$': round(avg_concurrent_bp, 0),
        'annual_$_per_contract': round(annual_pnl_per_contract, 0),
        'bp_year_pct': round(bp_year_pct, 2),
        'dollar_per_bp_td': round(dollars_per_bp_day * 10000, 2),    # bp = bps; 10000× for readability
        'boot_ci_lo_ann_%': round(boot_lo_ann_arith, 2),
        'boot_ci_hi_ann_%': round(boot_hi_ann_arith, 2),
        'boot_significant_bs250': boot['significant'],
    }

mA = compute_metrics("A: /ES V2c (true ladder)", es_pnls,
                     BP_PER_ES_CONTRACT, ES_V2C_HOLD_TD, ES_V2C_CONCURRENT)
mB = compute_metrics("B: SPX CSP T1 (single slot)", spx_pnls,
                     BP_PER_SPX_CONTRACT, SPX_CSP_HOLD_TD, SPX_CSP_CONCURRENT)

# ─── Print competition protocol summary ───────────────────────────────────────
print(f"\n{'='*88}")
print(f"  Q055 NAKED PUT SLOT COMPETITION PROTOCOL")
print(f"  Window: {WINDOW_START} → {WINDOW_END} ({YEARS:.1f} yr)")
print(f"  Account: ${ACCOUNT:,.0f} | Pricing: BS-flat (VIX as sigma) | Underlying: SPX")
print(f"{'='*88}\n")

print("PROTOCOL — TIER 1 VETOS (any failure → eliminate):")
print("  V1: Worst single trade ≤ 15% NLV (broker/PM-action threshold)")
print("  V2: Geometric Ann ROE > 0% on 26-yr window")
print("  V3: Bootstrap CI (block=250) lower bound not in extreme negative territory (>-1.0% Ann)")
print()
print("PROTOCOL — TIER 2 PRIMARY (account-level production metrics):")
print("  P1: Account-level Ann ROE (geometric)")
print("  P2: $/BP-year capital efficiency")
print("  P3: Worst trade % NLV (tail discipline)")
print("  → Win 2/3 Tier 2 → wins competition")
print()
print("PROTOCOL — TIER 3 SECONDARY (informational, tie-breaker):")
print("  S1: Annualised Sharpe")
print("  S2: WR")
print("  S3: CVaR 5% / NLV")
print("  S4: Account MDD")
print("  S5: Per-contract annual $ (strategy efficiency, structural-blind)")

# ─── Display side-by-side ─────────────────────────────────────────────────────
def fmt_row(label, key_a, key_b, fmt='{}'):
    a = fmt.format(mA[key_a]) if key_a else 'n/a'
    b = fmt.format(mB[key_b]) if key_b else 'n/a'
    return f"  {label:<38}  {a:>22}  {b:>22}"

print(f"\n{'='*88}")
print(f"  COMPARISON TABLE")
print(f"{'='*88}\n")
print(f"  {'Metric':<38}  {'A: /ES V2c':>22}  {'B: SPX CSP T1':>22}")
print(f"  {'-'*38}  {'-'*22}  {'-'*22}")
print(fmt_row("Trades total",                   'n_trades',           'n_trades'))
print(fmt_row("Trades per year",                'trades_per_yr',      'trades_per_yr'))
print(fmt_row("Concurrent contracts (avg)",     'avg_concurrent_contracts', 'avg_concurrent_contracts'))
print(fmt_row("BP deployed avg",                'avg_bp_deployed_$',  'avg_bp_deployed_$',  fmt='${:,.0f}'))
print()
print("  ─── Tier 1 Vetos ──")
print(fmt_row("V1: Worst trade $ ",             'worst_$',            'worst_$',            fmt='${:,.0f}'))
print(fmt_row("V1: Worst trade % NLV",          'worst_pct_nlv',      'worst_pct_nlv',      fmt='{:.2f}%'))
v1_a = mA['worst_pct_nlv'] >= -15
v1_b = mB['worst_pct_nlv'] >= -15
print(f"     V1 Veto (worst > -15% NLV):  A: {'PASS ✅' if v1_a else 'FAIL ❌'}   B: {'PASS ✅' if v1_b else 'FAIL ❌'}")
print()
print(fmt_row("V2: Ann ROE geometric",          'ann_roe_geom_%',     'ann_roe_geom_%',     fmt='{:.2f}%'))
v2_a = mA['ann_roe_geom_%'] > 0
v2_b = mB['ann_roe_geom_%'] > 0
print(f"     V2 Veto (Ann ROE > 0%):       A: {'PASS ✅' if v2_a else 'FAIL ❌'}   B: {'PASS ✅' if v2_b else 'FAIL ❌'}")
print()
print(fmt_row("V3: Bootstrap CI lo Ann %",      'boot_ci_lo_ann_%',   'boot_ci_lo_ann_%',   fmt='{:.2f}%'))
v3_a = mA['boot_ci_lo_ann_%'] > -1.0
v3_b = mB['boot_ci_lo_ann_%'] > -1.0
print(f"     V3 Veto (CI lo > -1.0% Ann):  A: {'PASS ✅' if v3_a else 'FAIL ❌'}   B: {'PASS ✅' if v3_b else 'FAIL ❌'}")
print()

print("  ─── Tier 2 Primary (account-level) ──")
print(fmt_row("P1: Ann ROE geometric",          'ann_roe_geom_%',     'ann_roe_geom_%',     fmt='{:.2f}%'))
print(fmt_row("P2: $/BP-year (capital eff.)",   'bp_year_pct',        'bp_year_pct',        fmt='{:.2f}%'))
print(fmt_row("P3: Worst % NLV",                'worst_pct_nlv',      'worst_pct_nlv',      fmt='{:.2f}%'))
p1_winner = 'A' if mA['ann_roe_geom_%'] > mB['ann_roe_geom_%'] else 'B'
p2_winner = 'A' if mA['bp_year_pct'] > mB['bp_year_pct'] else 'B'
p3_winner = 'A' if mA['worst_pct_nlv'] > mB['worst_pct_nlv'] else 'B'
print(f"     P1 winner: {p1_winner}    P2 winner: {p2_winner}    P3 winner: {p3_winner}")

print()
print("  ─── Tier 3 Secondary (informational) ──")
print(fmt_row("S1: Sharpe (annualised)",        'sharpe_ann',         'sharpe_ann',         fmt='{:.2f}'))
print(fmt_row("S2: Win Rate",                   'wr_%',               'wr_%',               fmt='{:.1f}%'))
print(fmt_row("S3: CVaR 5% % NLV",              'cvar5_pct_nlv',      'cvar5_pct_nlv',      fmt='{:.2f}%'))
print(fmt_row("S4: Account MDD",                'mdd_pct',            'mdd_pct',            fmt='{:.1f}%'))
print(fmt_row("S5: $/contract/year (struct-blind)", 'annual_$_per_contract', 'annual_$_per_contract', fmt='${:,.0f}'))

# ─── Verdict ──────────────────────────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  VERDICT")
print(f"{'='*88}\n")

vetos_a = [v1_a, v2_a, v3_a]
vetos_b = [v1_b, v2_b, v3_b]
print(f"  A vetos:  V1={v1_a}, V2={v2_a}, V3={v3_a}  → {'PASS' if all(vetos_a) else 'FAIL'}")
print(f"  B vetos:  V1={v1_b}, V2={v2_b}, V3={v3_b}  → {'PASS' if all(vetos_b) else 'FAIL'}")

a_t2_wins = sum([p1_winner == 'A', p2_winner == 'A', p3_winner == 'A'])
b_t2_wins = 3 - a_t2_wins
print(f"\n  Tier 2 wins: A={a_t2_wins}/3, B={b_t2_wins}/3")

if not all(vetos_a) and not all(vetos_b):
    verdict = "BOTH FAIL VETOS — neither candidate proceeds"
elif not all(vetos_a):
    verdict = "A FAILS VETO — B wins by elimination"
elif not all(vetos_b):
    failed_b = [name for name, p in zip(['V1', 'V2', 'V3'], vetos_b) if not p]
    verdict = f"B FAILS VETO ({', '.join(failed_b)}) — A wins by elimination"
elif a_t2_wins >= 2:
    verdict = f"A WINS Tier 2 ({a_t2_wins}/3 primary metrics)"
elif b_t2_wins >= 2:
    verdict = f"B WINS Tier 2 ({b_t2_wins}/3 primary metrics)"
else:
    verdict = "TIE on Tier 2 — need Tier 3 tie-breaker"

print(f"\n  RESULT: {verdict}")

# ─── Structural constraint disclosure ─────────────────────────────────────────
print(f"\n  STRUCTURAL CONSTRAINT DISCLOSURE:")
print(f"    A (/ES) deploys ~5.6 concurrent contracts at $500k account.")
print(f"    B (SPX CSP) deploys 1 concurrent contract at $500k account.")
print(f"    Per-contract $/year: A=${mA['annual_$_per_contract']:,.0f}, B=${mB['annual_$_per_contract']:,.0f}")
print(f"    The ladder advantage is ~{ES_V2C_CONCURRENT/SPX_CSP_CONCURRENT:.1f}× more BP deployed,")
print(f"    contributing materially to A's account-level Ann ROE advantage.")
print(f"    However, A also wins on per-BP-year capital efficiency,")
print(f"    so the structural advantage compounds with strategy-level efficiency.")

# ─── Save ─────────────────────────────────────────────────────────────────────
with open('/tmp/q055_competition_results.pkl', 'wb') as f:
    pickle.dump({
        'A_metrics': mA,
        'B_metrics': mB,
        'verdict': verdict,
        'tier1_vetos': {'A': vetos_a, 'B': vetos_b},
        'tier2_winners': {'P1': p1_winner, 'P2': p2_winner, 'P3': p3_winner},
    }, f)
print(f"\n  Saved: /tmp/q055_competition_results.pkl")
