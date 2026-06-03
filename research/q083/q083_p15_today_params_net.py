"""Q083 P15 — Net settlement at PM's TODAY parameters (not 26y摊薄 median debit).

Per G-review P14 reply: my P14 packet reported "4-5% ratio" + "net +$2,834/yr"
using historical $7,101 median debit. PM today faces SPX 5000+ / SPEC-111 cap
$22,200/BCD / $37k liquid cash base. The ratio holds, but absolute numbers are
3.13x — and the ratio is the wrong lens for a cash-bound account anyway.

Recompute at today's params + check cash-floor worst case.
"""

# PM today (Q081 P0)
LIQUID_CASH = 37_000
SPEC_111_CAP_PCT = 0.60
PER_TRADE_DEBIT = LIQUID_CASH * SPEC_111_CAP_PCT  # $22,200
CASH_FLOOR = 30_000

# Historical (P14)
HIST_MEDIAN_DEBIT = 7_101
HIST_PRE_PNL_YR = 5_037
HIST_POST_PNL_YR = 8_003
HIST_PRE_OPP_QQQ = 322
HIST_POST_OPP_QQQ = 455
HIST_PRE_OPP_SGOV = 161
HIST_POST_OPP_SGOV = 227
PRE_COVERAGE = 0.355
POST_COVERAGE = 0.464

SCALE = PER_TRADE_DEBIT / HIST_MEDIAN_DEBIT  # 3.13x

print(f"PM today: liquid ${LIQUID_CASH:,} | SPEC-111 cap ${PER_TRADE_DEBIT:,.0f}/BCD"
      f" | floor ${CASH_FLOOR:,}")
print(f"Scale vs 26y historical median debit: {SCALE:.2f}x\n")

# Today's params scaling
pre_pnl = HIST_PRE_PNL_YR * SCALE
post_pnl = HIST_POST_PNL_YR * SCALE
pre_opp_qqq = HIST_PRE_OPP_QQQ * SCALE
post_opp_qqq = HIST_POST_OPP_QQQ * SCALE
pre_opp_sgov = HIST_PRE_OPP_SGOV * SCALE
post_opp_sgov = HIST_POST_OPP_SGOV * SCALE

print(f"{'@ QQQ 10%/yr':<35} {'Pre':>12} {'Post':>12} {'Δ':>12}")
print(f"{'BCD PnL':<35} ${pre_pnl:>10,.0f} ${post_pnl:>10,.0f} ${post_pnl-pre_pnl:>+11,.0f}")
print(f"{'Opp cost':<35} ${pre_opp_qqq:>10,.0f} ${post_opp_qqq:>10,.0f} ${post_opp_qqq-pre_opp_qqq:>+11,.0f}")
net_d_qqq = (post_pnl - post_opp_qqq) - (pre_pnl - pre_opp_qqq)
print(f"{'Net Δ':<35} {'':>12} {'':>12} ${net_d_qqq:>+11,.0f}")
print(f"{'Δ opp / Δ PnL':<35} {'':>12} {'':>12} {(post_opp_qqq-pre_opp_qqq)/(post_pnl-pre_pnl)*100:>11.1f}%")
print()

print(f"{'@ SGOV 5%/yr':<35} {'Pre':>12} {'Post':>12} {'Δ':>12}")
print(f"{'BCD PnL':<35} ${pre_pnl:>10,.0f} ${post_pnl:>10,.0f} ${post_pnl-pre_pnl:>+11,.0f}")
print(f"{'Opp cost':<35} ${pre_opp_sgov:>10,.0f} ${post_opp_sgov:>10,.0f} ${post_opp_sgov-pre_opp_sgov:>+11,.0f}")
net_d_sgov = (post_pnl - post_opp_sgov) - (pre_pnl - pre_opp_sgov)
print(f"{'Net Δ':<35} {'':>12} {'':>12} ${net_d_sgov:>+11,.0f}")

print(f"\nCash floor worst-case:")
post_open = LIQUID_CASH - PER_TRADE_DEBIT
print(f"  Cash after 1 BCD open: ${LIQUID_CASH:,} - ${PER_TRADE_DEBIT:,.0f} = ${post_open:,.0f}")
print(f"  vs floor ${CASH_FLOOR:,}: {'BELOW by' if post_open < CASH_FLOOR else 'above by'} ${abs(post_open - CASH_FLOOR):,}")
print(f"  Trading days/yr below floor (252×coverage):")
print(f"    Pre-SPEC-113:  {PRE_COVERAGE*252:.0f} days/yr")
print(f"    Post-SPEC-113: {POST_COVERAGE*252:.0f} days/yr")
print(f"    Δ: +{(POST_COVERAGE-PRE_COVERAGE)*252:.0f} days/yr")
print(f"\n  Risk character: SPEC-111 floor blocks NEW opens, not in-flight. Sequential")
print(f"  ladder already enforces max concurrent BCD=1, so floor's marginal value is in")
print(f"  catching OTHER debit strategies (e.g. SPY held alongside SPX BCD). SPEC-113")
print(f"  does NOT introduce new cash-floor risk; it scales below-floor duration +30%.")
