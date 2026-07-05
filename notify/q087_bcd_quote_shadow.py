"""SPEC-122 — BCD real-quote shadow recording (Q087 SPEC-120 §2 arbitration).

PURE RECORDING: no routing / gate / execution change anywhere. On every BCD
signal day (production selector routes bull_call_diagonal — the LOW_VOL×BULLISH
lane or the SPEC-113 carve lane, post SPEC-079 filter), construct the real BCD
quote from the day's SPX chain snapshot:

  long leg : expiry nearest 90 DTE, call with |delta| nearest 0.70
  short leg: expiry nearest 45 DTE, call with |delta| nearest 0.30

and record bid/ask/mid, vendor iv, mid-implied iv per leg, debit in both mid
and natural (buy long at ask / sell short at bid) terms, plus the three model
debits (FLAT / CALIB / PESS via the pricing library, same conventions as its
ACT/365 native basis) — every row carries its own model-vs-real error.

Hooked into the SPEC-116 16:50 job (notify.q085_s2bps_paper.run). Telegram
SILENT by design. Non-signal days write nothing to the shadow file (AC-4);
the run marker below is touched on every run so the heartbeat can assert the
job is alive without false-alarming on quiet days (AC-5).

v2 pre-registration (task/SPEC-122.md): >=8 signal days by 2026-09-30;
verdict = median relative error of real NATURAL debit vs FLAT and CALIB_tconv.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHADOW_OUT = ROOT / "data" / "q087_bcd_quote_shadow.jsonl"
RUN_MARKER = ROOT / "data" / ".q087_bcd_shadow_ran"
BACKFILL = ROOT / "research" / "q087" / "q087_moff_backfill.jsonl"

LONG_DTE_TARGET, LONG_DELTA_TARGET = 90, 0.70
SHORT_DTE_TARGET, SHORT_DELTA_TARGET = 45, 0.30
PESS_BRACKET_VP = 1.0   # same bracket as SPEC-120 (short -1vp / long +1vp)
MIV_R = 0.045           # pricing-library native conventions (T=dte/365, q=0)

log = logging.getLogger("q087_bcd_shadow")


def _pick_leg(calls, dte_target: int, delta_target: float):
    """Row from the call chain: expiry nearest dte_target, then |delta|
    nearest delta_target within that expiry."""
    dtes = calls.dte.unique()
    if not len(dtes):
        return None
    best_dte = min(dtes, key=lambda d: abs(int(d) - dte_target))
    e = calls[calls.dte == best_dte].assign(ad=lambda x: x.delta.abs())
    if not len(e):
        return None
    return e.iloc[(e.ad - delta_target).abs().argsort()].iloc[0]


def _leg_fields(row, spx: float, prefix: str) -> dict:
    from pricing import core
    T = float(row.dte) / 365.0
    mid = float(row.mid)
    miv = core.implied_vol(mid, spx, float(row.strike), T, MIV_R, is_call=True)
    out = {
        f"{prefix}_expiry": str(row.expiry),
        f"{prefix}_dte": int(row.dte),
        f"{prefix}_strike": float(row.strike),
        f"{prefix}_delta": round(float(row.delta), 4),
        f"{prefix}_bid": float(row.bid),
        f"{prefix}_ask": float(row.ask),
        f"{prefix}_mid": mid,
        f"{prefix}_vendor_iv": round(float(row.iv), 2),
    }
    if miv is not None and math.isfinite(miv):
        out[f"{prefix}_miv"] = round(miv * 100.0, 2)
    return out


def _model_debits(long_row, short_row, spx: float, vix: float) -> dict:
    """FLAT / CALIB / PESS debit for the SAME two contracts, priced through
    the pricing library at its native conventions (T=dte/365, r=MIV_R, q=0 —
    matching the offsets' ACT/365 measurement basis, no conversion needed).
    CALIB/PESS key each leg's sigma by the leg's chain |delta|."""
    from pricing import core
    from pricing.calibration import InsufficientCalibration, load_offsets_merged
    from pricing.sigma import SigmaMode, sigma_for

    def px(row, sigma):
        return core.call_price(spx, float(row.strike), float(row.dte) / 365.0,
                               sigma, MIV_R, q=0.0)

    out: dict = {}
    flat = vix / 100.0
    out["model_flat_debit"] = round(px(long_row, flat) - px(short_row, flat), 4)

    try:
        offsets, _stats = load_offsets_merged(
            [ROOT / "data" / "q085_skew_monitor.jsonl", BACKFILL])
    except InsufficientCalibration as exc:
        out["calib_error"] = str(exc)
        return out

    def sig(row, mode, adverse_sign=None):
        kw = dict(vix=vix, option_type="CALL", abs_delta=abs(float(row.delta)),
                  dte=int(row.dte), offsets=offsets)
        if mode is SigmaMode.CALIB:
            return sigma_for(SigmaMode.CALIB, **kw)
        return sigma_for(SigmaMode.PESS, adverse_sign=adverse_sign,
                         bracket_vp=PESS_BRACKET_VP, **kw)

    out["model_calib_debit"] = round(
        px(long_row, sig(long_row, SigmaMode.CALIB))
        - px(short_row, sig(short_row, SigmaMode.CALIB)), 4)
    # PESS: adverse for a debit structure = pay more for the long (+1vp),
    # receive less on the short (-1vp) — same static bracket as SPEC-120.
    out["model_pess_debit"] = round(
        px(long_row, sig(long_row, SigmaMode.PESS, adverse_sign=+1))
        - px(short_row, sig(short_row, SigmaMode.PESS, adverse_sign=-1)), 4)
    out["offsets_convention"] = getattr(offsets, "convention", None)
    return out


def run(today: str, rec, calls, spx: float | None, vix: float,
        *, dry_run: bool = False) -> dict | None:
    """Called from notify.q085_s2bps_paper.run with the SAME production
    recommendation object (AC-1: signal-day determination reuses the selector
    output — never recomputed here) and the already-loaded call chain.

    Returns the written row on BCD signal days, None otherwise."""
    RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    RUN_MARKER.touch()  # heartbeat: job alive daily, incl. non-signal days

    strategy_key = getattr(rec, "strategy_key", None) if rec is not None else None
    regime = getattr(getattr(rec, "vix_snapshot", None), "regime", None) if rec is not None else None
    regime = getattr(regime, "value", str(regime)) if regime is not None else None

    # SPEC-123 §2 (D2 quote-gate): while in LOW_VOL, record quotes EVERY day —
    # the gate needs >=10 LOW_VOL quote days before the first main-cell trade,
    # including days when D1 halt or gates keep the selector on wait.
    is_signal = strategy_key == "bull_call_diagonal"
    if not is_signal and regime != "LOW_VOL":
        return None  # AC-4: non-signal day — zero shadow writes, zero pushes

    from notify.q085_s2bps_paper import _append_jsonl

    if is_signal:
        lane = "LOW_VOL|BULLISH" if regime == "LOW_VOL" else "SPEC-113_carve"
    else:
        lane = "lowvol_quote_gate"

    row: dict = {"date": today, "lane": lane, "regime": regime,
                 "vix": round(float(vix), 2)}
    if spx is not None and spx > 0:
        row["spx"] = round(float(spx), 2)

    if calls is None or not len(calls) or spx is None or spx <= 0:
        # A lost sample still counts toward the >=8 gate ledger — record the
        # signal day with the reason instead of silently dropping it.
        row["error"] = "missing_chain" if calls is None or not len(calls) else "missing_spx"
        _append_jsonl(SHADOW_OUT, row, "bcd_shadow")
        log.warning("q087 bcd shadow: signal day %s but %s", today, row["error"])
        return row

    long_row = _pick_leg(calls, LONG_DTE_TARGET, LONG_DELTA_TARGET)
    short_row = _pick_leg(calls, SHORT_DTE_TARGET, SHORT_DELTA_TARGET)
    if long_row is None or short_row is None:
        row["error"] = "leg_unavailable"
        _append_jsonl(SHADOW_OUT, row, "bcd_shadow")
        return row

    row.update(_leg_fields(long_row, spx, "long"))
    row.update(_leg_fields(short_row, spx, "short"))
    row["debit_mid"] = round(float(long_row.mid) - float(short_row.mid), 4)
    row["debit_natural"] = round(float(long_row.ask) - float(short_row.bid), 4)
    row.update(_model_debits(long_row, short_row, spx, vix))

    _append_jsonl(SHADOW_OUT, row, "bcd_shadow")
    log.info("q087 bcd shadow: recorded %s lane=%s debit_mid=%.2f", today, lane,
             row["debit_mid"])
    return row
