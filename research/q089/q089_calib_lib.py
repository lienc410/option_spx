"""Q089 shared machinery — CALIB-priced BCD single-cycle + campaign simulators.

Pricing: Q082 P6 primitives (BS, T=dte/365 ACT365) + SPEC-119 pricing lib
CALIB sigma. P6's calendar basis MATCHES the offset measurement convention
(r045_q0_act365) so offsets are used RAW — the x0.831 tconv correction applies
only to the 252-basis matrix engine (Q087 C4). Asserted below.

H-1 quarantine: production skew-monitor rows dated >= 2026-07-06 are excluded
(SPEC-122 integration field-crossing puts call values in put moff fields;
hotfix in flight). Re-widen after dev confirms the first clean row.

Friction: per-leg half-spread measured from the REAL 2026-07-06 chain
(script-measured medians, methodology "数据采集脚本化"):
  long leg  (CALL d.60-.80, 55-100 dte, deep ITM): 0.14-0.18% of mid -> 0.2%
  short leg (CALL d.25-.35 entry / 18-24 dte exit): 0.76-1.05%       -> 1.0%
Buy at mid*(1+f), sell at mid*(1-f). Single calm-day measurement; spreads
widen in stress, and wider friction penalizes the higher-frequency incumbent
arm more, so calm-day friction is CONSERVATIVE for the incumbent side of the
head-to-head. (v1 of this lib used a flat 1.6%/leg — ~10x too heavy on the
long leg; superseded by measurement.)
"""
from __future__ import annotations
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "q082"))

from q082_p6_bcd_synth_reconstruction import (  # noqa: E402
    call_price, find_strike_for_delta, load_spx_history, load_vix_history,
    SHORT_DTE, LONG_DTE, SHORT_DELTA_TARGET, LONG_DELTA_TARGET, ROLL_AT_DTE)
from pricing.calibration import load_offsets_merged, CONV_ACT365  # noqa: E402
from pricing.sigma import SigmaMode, sigma_for  # noqa: E402

LONG_FRICTION = 0.002   # measured 2026-07-06 chain, deep-ITM call
SHORT_FRICTION = 0.010  # measured 2026-07-06 chain, OTM call
H1_QUARANTINE_FROM = "2026-07-06"

OFFSET_SOURCES = [
    ROOT / "data" / "q085_skew_monitor.jsonl",
    Path.home() / "backups/oldair/data/q085_skew_monitor.jsonl",
    ROOT / "research" / "q087" / "q087_moff_backfill.jsonl",
]


def build_offsets(scratch: Path) -> dict:
    """Merged offsets with H-1 polluted rows filtered out before merging."""
    filtered = []
    for src in OFFSET_SOURCES:
        if not src.exists():
            continue
        rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
        kept = [r for r in rows if str(r.get("date", "")) < H1_QUARANTINE_FROM]
        p = scratch / f"h1q_{src.parent.name}_{src.name}"
        p.write_text("\n".join(json.dumps(r) for r in kept))
        print(f"offsets source {src}: {len(rows)} rows, {len(rows)-len(kept)} H-1-quarantined")
        filtered.append(p)
    offsets, stats = load_offsets_merged(filtered)
    assert getattr(offsets, "convention", None) == CONV_ACT365, \
        "P6 prices at T=dte/365; offsets must stay in ACT365 convention (NO tconv scaling)"
    print(f"merged calibration days: {stats['days_total']} (no-moff skipped: {stats['days_no_moff']})")
    return offsets


def leg_sigma(offsets, vix_level: float, option_type: str, abs_delta: float, dte: int) -> float:
    return sigma_for(SigmaMode.CALIB, vix=vix_level, option_type=option_type,
                     abs_delta=abs_delta, dte=dte, offsets=offsets)


class Leg:
    """One call leg; smile lookup keeps the ENTRY abs-delta bucket, dte bucket
    follows current maturity (same treatment both arms -> relative robust)."""

    def __init__(self, offsets, entry_iso: str, S: float, vix: float,
                 dte: int, target_delta: float):
        self.offsets = offsets
        self.abs_delta = target_delta
        self.entry_iso = entry_iso
        self.dte0 = dte
        sig = leg_sigma(offsets, vix, "CALL", target_delta, dte)
        self.K = round(find_strike_for_delta(S, dte, sig, target_delta) / 5) * 5
        self.entry_prem = call_price(S, self.K, dte, sig)

    def mark(self, S: float, vix: float, dte_remaining: int) -> float:
        if dte_remaining <= 0:
            return max(S - self.K, 0.0)
        sig = leg_sigma(self.offsets, vix, "CALL", self.abs_delta, dte_remaining)
        return call_price(S, self.K, dte_remaining, sig)


def _walk(entry_iso: str, spx: dict, vix: dict, max_days: int):
    """Yield (delta_days, iso, S, vix_level) on trading days after entry."""
    d0 = date.fromisoformat(entry_iso)
    S, v = spx[entry_iso], vix[entry_iso]
    for dd in range(1, max_days + 1):
        iso = (d0 + timedelta(days=dd)).isoformat()
        if iso in spx:
            S = spx[iso]
        if iso in vix:
            v = vix[iso]
        if iso in spx:
            yield dd, iso, S, v


def simulate_cycle(offsets, entry_iso: str, spx: dict, vix: dict) -> dict | None:
    """P6-equivalent single cycle (exit at short 21 DTE), CALIB legs + friction."""
    if entry_iso not in spx or entry_iso not in vix or vix[entry_iso] <= 0:
        return None
    S0, v0 = spx[entry_iso], vix[entry_iso]
    lng = Leg(offsets, entry_iso, S0, v0, LONG_DTE, LONG_DELTA_TARGET)
    sht = Leg(offsets, entry_iso, S0, v0, SHORT_DTE, SHORT_DELTA_TARGET)
    debit = lng.entry_prem - sht.entry_prem
    if debit <= 0:
        return None
    fl, fs = LONG_FRICTION, SHORT_FRICTION
    cash = -lng.entry_prem * (1 + fl) + sht.entry_prem * (1 - fs)
    for dd, iso, S, v in _walk(entry_iso, spx, vix, 50):
        if SHORT_DTE - dd <= ROLL_AT_DTE:
            cash += lng.mark(S, v, LONG_DTE - dd) * (1 - fl)
            cash -= sht.mark(S, v, SHORT_DTE - dd) * (1 + fs)
            return {"entry_date": entry_iso, "exit_date": iso, "hold_days": dd,
                    "entry_debit": round(debit, 2), "pnl_usd": round(cash * 100, 2)}
    return None


def simulate_campaign(offsets, entry_iso: str, spx: dict, vix: dict,
                      resell_rule: str, cap_td: int = 5) -> dict | None:
    """E4 campaign: long held to LONG-21 DTE; short bought back on collapse
    (mark <= 15% of its entry prem) or short 21 DTE; re-sell timing per rule:
      immediate  — new short same day
      wait5      — 5 trading days after buyback, then sell regardless
      retrace50  — S >= trough + 0.5*(campaign_peak - trough), cap cap_td
      prev_high  — S >= campaign peak, cap cap_td
      prev_high_lit — literal unbounded (diagnostic only, never re-sells if
                      the high never returns)
    New short: 45 DTE (or long remaining), delta 0.30, only while long DTE>=35.
    """
    if entry_iso not in spx or entry_iso not in vix or vix[entry_iso] <= 0:
        return None
    S0, v0 = spx[entry_iso], vix[entry_iso]
    lng = Leg(offsets, entry_iso, S0, v0, LONG_DTE, LONG_DELTA_TARGET)
    sht = Leg(offsets, entry_iso, S0, v0, SHORT_DTE, SHORT_DELTA_TARGET)
    if lng.entry_prem - sht.entry_prem <= 0:
        return None
    fl, fs = LONG_FRICTION, SHORT_FRICTION
    cash = -lng.entry_prem * (1 + fl) + sht.entry_prem * (1 - fs)
    short_open, short_entry_dd = True, 0
    short_income = sht.entry_prem * (1 - fs)
    peak, trough = S0, S0
    wait_since, naked_days, n_cycles = None, 0, 1
    exit_iso = None
    for dd, iso, S, v in _walk(entry_iso, spx, vix, LONG_DTE + 7):
        peak = max(peak, S)
        long_dte = LONG_DTE - dd
        if long_dte <= ROLL_AT_DTE:  # campaign end
            cash += lng.mark(S, v, long_dte) * (1 - fl)
            if short_open:
                m = sht.mark(S, v, sht.dte0 - (dd - short_entry_dd))
                cash -= m * (1 + fs)
            exit_iso = iso
            break
        if short_open:
            sdte = sht.dte0 - (dd - short_entry_dd)
            m = sht.mark(S, v, sdte)
            if m <= 0.15 * sht.entry_prem or sdte <= ROLL_AT_DTE:
                cash -= m * (1 + fs)
                short_open = False
                trough, wait_since = S, dd
        if not short_open:  # same-day fall-through so 'immediate' rolls on the buyback day
            if long_dte < 35:
                naked_days += 1
                continue
            waited = dd - wait_since
            go = {"immediate": True,
                  "wait5": waited >= 5,
                  "retrace50": S >= trough + 0.5 * (peak - trough) or waited >= cap_td,
                  "prev_high": S >= peak or waited >= cap_td,
                  "prev_high_lit": S >= peak}[resell_rule]
            if go:
                sht = Leg(offsets, iso, S, v, min(SHORT_DTE, long_dte), SHORT_DELTA_TARGET)
                if lng.entry_prem > 0 and sht.entry_prem > 0:
                    cash += sht.entry_prem * (1 - fs)
                    short_income += sht.entry_prem * (1 - fs)
                    short_open, short_entry_dd = True, dd
                    n_cycles += 1
                    trough = S
            if not short_open:
                naked_days += 1
    if exit_iso is None:
        return None
    return {"entry_date": entry_iso, "exit_date": exit_iso, "rule": resell_rule,
            "cap_td": cap_td, "n_cycles": n_cycles, "naked_days": naked_days,
            "short_income": round(short_income, 2), "pnl_usd": round(cash * 100, 2)}
