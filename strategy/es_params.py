"""
Single source of truth for /ES Short Put production parameters.

All layers — backtest (research/strategies/ES_puts/backtest.py),
live selector, alert bot (notify/telegram_bot.py), and web server —
should import from here. Never hardcode these values elsewhere.

Alignment rule: when any parameter changes, update this file only.
The change propagates to backtest, bot, and server automatically.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EsShortPutParams:
    # ── Entry ──────────────────────────────────────────────────────────────
    entry_dte:      int   = 45    # target DTE at open
    target_delta:   float = 0.20  # short put delta (absolute value)

    # ── Sizing — production rule: 1 contract, single slot ──────────────────
    n_contracts:    int   = 1     # fixed 1-contract cap (SPEC-061 single-slot rule)

    # ── Exit rules ─────────────────────────────────────────────────────────
    stop_mult:      float = 10.0  # stop when mark ≥ N× entry premium
    #   SPEC-121 (Q087 A3, PM ratified 2026-07-05): canonical stop = 10×,
    #   one number across monitor / backtest / display. 26y backtest is
    #   bit-identical to the old research 15× (zero triggers either way);
    #   10× is the disaster fail-safe (abnormal mark / gap scenarios).
    #   Bot trigger: ratio = mark/entry ≥ 10.0 (SPEC-086, telegram_bot.py);
    #   the 2× WARNING is fixed and independent (early intelligence layer).

    profit_target:  float = 0.10  # close when mark ≤ N× entry premium (= 90% profit captured)
    gamma_dte:      int   = 5     # force-close if DTE ≤ this at daily check

    # ── Risk / account ─────────────────────────────────────────────────────
    bp_limit_fraction: float = 0.20  # max combined /ES margin as fraction of NLV


# Module-level default — mirrors the pattern in strategy/selector.py
DEFAULT_ES_PARAMS = EsShortPutParams()
