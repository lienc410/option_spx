"""SPEC-116 — Q085 S2-BPS daily paper job (16:50 ET, after 16:30 chain snapshot).

Order per handoff:
  A. skew measurement (unconditional)         → data/q085_skew_monitor.jsonl
  C. manage open paper positions (daily)      → close events in ledger
  B. signal check + paper open (signal days)  → open event + Telegram
  D. degradation note (after any close)       → WARNING Telegram (informational)
  E. overlap tracking is recorded on open events (main BPS sleeve presence)

Missing chain snapshot → Telegram `missing_chain` and skip (never silently).
Non-signal days are Telegram-silent (skew row still written).
Strict-JSON discipline: every numeric field asserted finite before dumps
(per feedback_nan_json_browser_vs_python).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from strategy.q085_s2bps_signal import signal_day  # noqa: E402
# SPEC-126: all sends go through the gateway (category/about contract)
from notify.gateway import escape as _gw_escape  # noqa: E402
from notify.gateway import push as _gw_push  # noqa: E402


def _telegram_send(msg: str, *, category: str = "FYI", about: str = "系统状态") -> bool:
    # plain-text body → whole-body escape at the boundary (H-4)
    return _gw_push(category, about, "", _gw_escape(msg), dedupe_key=None)

log = logging.getLogger("q085_s2bps")
ET = ZoneInfo("America/New_York")

CHAIN_DIR = ROOT / "data" / "q041_chains"
SKEW_OUT = ROOT / "data" / "q085_skew_monitor.jsonl"
LEDGER = ROOT / "data" / "q085_paper_log.jsonl"

STOP_X = 3.0        # paper stop: cost_mid >= 3 x credit_mid
EXIT_DTE = 21       # paper expiry rule
DEGRADE_TRAIL_N = 10
DEGRADE_CUM_USD = -5000.0

_MAIN_BPS_KEYS = {"bull_put_spread", "bull_put_spread_hv"}


# ── strict-JSON helpers ────────────────────────────────────────────────────────

def _assert_finite(row: dict, ctx: str) -> None:
    for k, v in row.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"q085 {ctx}: non-finite field {k}={v}")


def _append_jsonl(path: Path, row: dict, ctx: str) -> None:
    _assert_finite(row, ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ── chain access ───────────────────────────────────────────────────────────────

def _load_side(date_str: str, side: str):
    import pandas as pd
    p = CHAIN_DIR / date_str / "SPX.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    rows = df[(df.option_type.str.upper() == side) & df.iv.notna() & (df.iv > 1)]
    return rows if len(rows) else None


def load_today_chain(date_str: str):
    """SPX puts with usable IV from the day's 16:30 snapshot; None if missing."""
    return _load_side(date_str, "PUT")


def load_today_calls(date_str: str):
    """SPEC-119: call side, feeds the skew-monitor extension only; None if missing."""
    return _load_side(date_str, "CALL")


# ── A. skew measurement ────────────────────────────────────────────────────────

# SPEC-119 extension legs: call |delta| targets (BCD re-evaluation needs the
# ITM 0.70 long leg and the OTM 0.30/0.16/0.08 short candidates) and the
# 80-100 DTE far bucket for both sides. Field names must match
# pricing.calibration._LEG_FIELDS.
_PUT_LEGS = (("atm", 0.50), ("d30", 0.30), ("d15", 0.15))
_CALL_LEGS = (("c70", 0.70), ("c30", 0.30), ("c16", 0.16), ("c08", 0.08))
_FAR_DTE = (80, 100)
# Extension legs only record when the chain actually reaches the target delta;
# the far bucket is strike-limited (|Δ| ~0.33-0.67 at 90 DTE as of 2026-07),
# without this guard c08/c16/d15 far legs would snap to the boundary row and
# get recorded under the wrong delta label — poisoning calibration curves.
_LEG_DELTA_TOL = 0.05
# Mid-implied IV solver conventions. AC-3 finding (2026-07-05): the vendor
# `iv` column runs 1-2.5vp BELOW the vol that reproduces the chain's own mid
# under our pricer — offsets built from vendor iv can NOT price real credits.
# Calibration therefore consumes the *_moff fields (solved from mid through
# pricing.core under the conventions below); vendor *_off fields are kept for
# continuity/diagnostics only.
_MIV_R = 0.045
_MIV_CONV = "r045_q0_act365"


def _mid_implied_iv(rows, spx: float, *, is_call: bool) -> float | None:
    """Mean mid-implied IV (vol points) over rows, each solved with its own
    strike/mid/dte through pricing.core (T=dte/365, r=_MIV_R, q=0)."""
    from pricing import core as _core
    if "mid" not in rows.columns or "strike" not in rows.columns:
        return None
    vals = []
    for _, rr in rows.iterrows():
        mid = float(rr.mid)
        if not math.isfinite(mid) or mid <= 0:
            continue
        iv = _core.implied_vol(mid, spx, float(rr.strike), float(rr.dte) / 365.0,
                               _MIV_R, is_call=is_call)
        if iv is not None:
            vals.append(iv * 100.0)
    return sum(vals) / len(vals) if vals else None


def parity_spot(puts, calls, *, r: float = _MIV_R) -> float | None:
    """SPX spot implied by put-call parity on the day's OWN chain snapshot.

    H-1 root cause (2026-07-06): the 16:50 job priced the 16:30 chain with the
    yahoo EOD cache, which (a) refreshes on an 18h TTL so it is ALWAYS the
    morning state (= previous close) by 16:50, and (b) went two sessions stale
    across the July-4 gap — spot was off by −56 pts and every near-bucket put
    miv solved ~2.5vp low (calls symmetric high). The chain is self-consistent:
    S = C_mid − P_mid + K·e^{−rT} at the ATM-most strikes. Averaged over up to
    3 strikes nearest put |Δ|=0.50 on the expiry nearest 30 DTE."""
    if puts is None or calls is None or not len(puts) or not len(calls):
        return None
    p = puts[(puts.dte >= 25) & (puts.dte <= 35)]
    if not len(p):
        p = puts
    best_dte = min(p.dte.unique(), key=lambda d: abs(int(d) - 30))
    pe = p[p.dte == best_dte].assign(ad=lambda x: x.delta.abs())
    ce = calls[calls.dte == best_dte]
    vals = []
    for _, pr in pe.iloc[(pe.ad - 0.50).abs().argsort()[:3]].iterrows():
        cr = ce[ce.strike == pr.strike]
        if cr.empty:
            continue
        T = float(pr.dte) / 365.0
        s = float(cr.iloc[0].mid) - float(pr.mid) + float(pr.strike) * math.exp(-r * T)
        if math.isfinite(s) and s > 0:
            vals.append(s)
    return sum(vals) / len(vals) if vals else None


def resolve_pricing_spot(puts, calls, yahoo_spot: float | None) -> tuple[float | None, str]:
    """(spot, source) for pricing the day's chain. Chain parity is primary —
    correct by construction, no cache dependency; yahoo EOD is fallback only.
    Logs loudly when the two diverge >0.1% (that is the H-1 failure mode)."""
    par = None
    try:
        par = parity_spot(puts, calls)
    except Exception:
        log.exception("q085: parity spot failed")
    if par is not None:
        if yahoo_spot and abs(par - yahoo_spot) / par > 0.001:
            log.warning("q085: yahoo spot %.2f diverges from chain parity %.2f "
                        "(>0.1%%) — stale cache suspected, using parity",
                        yahoo_spot, par)
        return par, "chain_parity"
    return yahoo_spot, "yahoo_eod"


def measure_skew(puts, vix: float, date_str: str, calls=None, spx: float | None = None,
                 spx_source: str | None = None) -> dict:
    """25-35 DTE |delta| IV legs (mean of 3 nearest rows) + offsets vs VIX.

    Near-bucket put legs are the original SPEC-116 fields and stay REQUIRED
    (raise on failure). The SPEC-119 extension buckets — call legs and the
    80-100 DTE far bucket — are fail-soft per bucket: a chain snapshot with
    no far expiry (or no call side) just omits those fields for the day.

    When `spx` (spot) is given, every recorded leg also gets *_miv / *_moff:
    mid-implied IV solved through pricing.core (see _MIV_CONV) — the fields
    pricing.calibration actually consumes. Vendor iv fields stay for
    continuity but are NOT pricing-grade (AC-3 finding).
    """
    p = puts[(puts.dte >= 25) & (puts.dte <= 35)].assign(ad=lambda x: x.delta.abs())
    if len(p) < 3:
        raise ValueError(f"q085 skew: only {len(p)} puts in 25-35 DTE window")

    def leg(chain, target: float) -> float:
        return float(chain.iloc[(chain.ad - target).abs().argsort()[:3]].iv.mean())

    row = {
        "date": date_str,
        "vix": round(float(vix), 2),
        "atm_iv": round(leg(p, 0.50), 2),
        "d30_iv": round(leg(p, 0.30), 2),
        "d15_iv": round(leg(p, 0.15), 2),
    }
    row["atm_off"] = round(row["atm_iv"] - row["vix"], 2)
    row["d30_off"] = round(row["d30_iv"] - row["vix"], 2)
    row["d15_off"] = round(row["d15_iv"] - row["vix"], 2)

    def miv_fields(chain, target: float, name: str, suffix: str, is_call: bool) -> None:
        if spx is None or spx <= 0:
            return
        rows3 = chain.iloc[(chain.ad - target).abs().argsort()[:3]]
        miv = _mid_implied_iv(rows3, spx, is_call=is_call)
        if miv is None or not math.isfinite(miv):
            return
        row[f"{name}_miv{suffix}"] = round(miv, 2)
        row[f"{name}_moff{suffix}"] = round(miv - row["vix"], 2)

    for name, target in _PUT_LEGS:
        miv_fields(p, target, name, "", is_call=False)

    for chain, legs, suffix, is_call in (
        (puts, _PUT_LEGS, "_far", False),
        (calls, _CALL_LEGS, "", True),
        (calls, _CALL_LEGS, "_far", True),
    ):
        lo, hi = _FAR_DTE if suffix == "_far" else (25, 35)
        if chain is None or not len(chain):
            continue
        b = chain[(chain.dte >= lo) & (chain.dte <= hi)]
        if len(b) < 3:
            log.info("q085 skew: bucket %s-%s DTE unavailable (%d rows) — skipping", lo, hi, len(b))
            continue
        b = b.assign(ad=lambda x: x.delta.abs())
        for name, target in legs:
            if float((b.ad - target).abs().min()) > _LEG_DELTA_TOL:
                continue  # chain doesn't reach this delta — skip, don't mislabel
            iv = leg(b, target)
            if not math.isfinite(iv):
                continue
            row[f"{name}_iv{suffix}"] = round(iv, 2)
            row[f"{name}_off{suffix}"] = round(iv - row["vix"], 2)
            miv_fields(b, target, name, suffix, is_call=is_call)

    if spx is not None and spx > 0 and any(k.endswith("_miv") or "_miv_" in k for k in row):
        row["spx"] = round(float(spx), 2)
        row["miv_conv"] = _MIV_CONV
        if spx_source:
            row["spx_source"] = spx_source

    _append_jsonl(SKEW_OUT, row, "skew")
    return row


# ── leg picking (shared by open + manage) ─────────────────────────────────────

def _pick_expiry(puts):
    """Expiry whose dte is nearest 30."""
    dtes = puts.dte.unique()
    best = min(dtes, key=lambda d: abs(int(d) - 30))
    return puts[puts.dte == best]

def _nearest_delta_row(chain, target: float):
    c = chain.assign(ad=lambda x: x.delta.abs())
    return c.iloc[(c.ad - target).abs().argsort()].iloc[0]

def _quote_for_strikes(puts, expiry: str, ks: float, kl: float):
    """Rows for exact expiry+strikes; (short_row, long_row) or None."""
    e = puts[puts.expiry == expiry]
    s = e[e.strike == ks]
    l = e[e.strike == kl]
    if s.empty or l.empty:
        return None
    return s.iloc[0], l.iloc[0]


# ── B. paper open ──────────────────────────────────────────────────────────────

def _main_bps_overlap() -> bool:
    """External-review C7: is the main BPS sleeve holding a position today?"""
    try:
        from strategy.state import read_all_positions
        for pos in (read_all_positions() or {}).get("positions", []):
            if str(pos.get("status") or "open").lower() not in {"", "open"}:
                continue
            if str(pos.get("strategy_key") or "") in _MAIN_BPS_KEYS:
                return True
    except Exception:
        log.warning("q085: main-sleeve overlap check failed", exc_info=True)
    return False


def build_paper_bps(puts, date_str: str, *, vix: float, sig: dict) -> dict:
    """Construct the paper BPS open event from today's chain (signal days only)."""
    e = _pick_expiry(puts)
    short = _nearest_delta_row(e, 0.30)
    long_ = _nearest_delta_row(e, 0.15)
    credit_mid = float(short.mid) - float(long_.mid)
    credit_natural = float(short.bid) - float(long_.ask)
    row = {
        "event": "open",
        "date": date_str,
        "expiry": str(short.expiry),
        "dte": int(short.dte),
        "k_short": float(short.strike),
        "k_long": float(long_.strike),
        "short_bid": float(short.bid), "short_ask": float(short.ask), "short_mid": float(short.mid),
        "long_bid": float(long_.bid), "long_ask": float(long_.ask), "long_mid": float(long_.mid),
        "short_iv": round(float(short.iv), 2), "long_iv": round(float(long_.iv), 2),
        "credit_mid": round(credit_mid, 2),
        "credit_natural": round(credit_natural, 2),
        "entry_spx": float(short.close),
        "entry_vix": round(float(vix), 2),
        "rsi2": sig.get("rsi2"), "down3": sig.get("down3"),
        "overlap_main_bps": _main_bps_overlap(),
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
    }
    _append_jsonl(LEDGER, row, "open")
    return row


# ── C. paper management ────────────────────────────────────────────────────────

def _open_positions(ledger: list[dict]) -> list[dict]:
    closed = {(r.get("open_date"), r.get("expiry"), r.get("k_short"), r.get("k_long"))
              for r in ledger if r.get("event") == "close"}
    out = []
    for r in ledger:
        if r.get("event") != "open":
            continue
        if (r.get("date"), r.get("expiry"), r.get("k_short"), r.get("k_long")) in closed:
            continue
        out.append(r)
    return out


def _vix_max_between(start_date: str, end_date: str) -> float | None:
    """Peak VIX over the holding window, from the daily skew monitor file."""
    vals = [r["vix"] for r in _read_jsonl(SKEW_OUT)
            if start_date <= r.get("date", "") <= end_date and isinstance(r.get("vix"), (int, float))]
    return round(max(vals), 2) if vals else None


def manage_open_positions(puts, today: str) -> list[dict]:
    """Re-mark all open paper positions off today's chain; close on stop/expiry rule."""
    ledger = _read_jsonl(LEDGER)
    closes: list[dict] = []
    for pos in _open_positions(ledger):
        q = _quote_for_strikes(puts, pos["expiry"], pos["k_short"], pos["k_long"])
        if q is None:
            log.warning("q085 manage: no quotes today for %s %s/%s — skip",
                        pos["expiry"], pos["k_short"], pos["k_long"])
            continue
        s, l = q
        cost_mid = float(s.mid) - float(l.mid)          # buy back short, sell long
        cost_natural = float(s.ask) - float(l.bid)
        dte_now = int(s.dte)
        spx_close = float(s.close)

        reason = None
        if cost_mid >= STOP_X * pos["credit_mid"] and pos["credit_mid"] > 0:
            reason = "stop"
        elif dte_now <= EXIT_DTE:
            reason = "expiry_rule"
        if reason is None:
            continue

        hold_days = (date.fromisoformat(today) - date.fromisoformat(pos["date"])).days
        row = {
            "event": "close",
            "date": today,
            "open_date": pos["date"],
            "expiry": pos["expiry"],
            "k_short": pos["k_short"], "k_long": pos["k_long"],
            "cost_mid": round(cost_mid, 2),
            "cost_natural": round(cost_natural, 2),
            "pnl_mid": round((pos["credit_mid"] - cost_mid) * 100.0, 2),
            "pnl_natural": round((pos["credit_natural"] - cost_natural) * 100.0, 2),
            "hold_days": hold_days,
            "dte_at_close": dte_now,
            "vix_max_during": _vix_max_between(pos["date"], today),
            "breach": bool(spx_close < pos["k_short"]),
            "reason": reason,
            "ts": datetime.now(ET).isoformat(timespec="seconds"),
        }
        _append_jsonl(LEDGER, row, "close")
        closes.append(row)
    return closes


# ── D. degradation note ────────────────────────────────────────────────────────

def degradation_note() -> dict | None:
    """Trailing-10 and cumulative pnl_mid; WARNING (no halt) if either trips."""
    pnls = [r["pnl_mid"] for r in _read_jsonl(LEDGER)
            if r.get("event") == "close" and isinstance(r.get("pnl_mid"), (int, float))]
    if not pnls:
        return None
    trail = sum(pnls[-DEGRADE_TRAIL_N:])
    cum = sum(pnls)
    trip_trail = trail < 0
    trip_cum = cum <= DEGRADE_CUM_USD
    if not (trip_trail or trip_cum):
        return None
    return {"trailing10_pnl_mid": round(trail, 2), "cum_pnl_mid": round(cum, 2),
            "trip_trailing": trip_trail, "trip_cum": trip_cum}


# ── main ───────────────────────────────────────────────────────────────────────

def run(today: str | None = None, *, dry_run: bool = False) -> dict:
    today = today or datetime.now(ET).date().isoformat()
    summary: dict = {"date": today, "skew": None, "closes": [], "open": None, "signal": None}

    puts = load_today_chain(today)
    if puts is None:
        msg = f"[S2-BPS PAPER] {today} missing_chain — skew/管理跳过（SPEC-114 sanity 会另行报警）"
        log.warning(msg)
        if not dry_run:
            _telegram_send(msg, category="ACTION")
        summary["missing_chain"] = True
        return summary

    # regime / strategy_key / VIX from the SAME pipeline as the bot's daily push
    from strategy.selector import get_recommendation
    rec = get_recommendation(use_intraday=False)
    vix = float(rec.vix_snapshot.vix)
    regime = getattr(rec.vix_snapshot.regime, "value", str(rec.vix_snapshot.regime))
    strategy_key = getattr(rec, "strategy_key", None)

    # SPX spot for mid-implied IV legs (SPEC-119); the same series is reused
    # by the signal check below. Fail-soft: skew still records vendor fields.
    from signals.trend import fetch_spx_history
    closes_series: list[float] = []
    try:
        closes_series = fetch_spx_history(period="2y")["close"].dropna().tolist()
    except Exception:
        log.exception("q085: SPX history fetch failed — miv legs skipped today")
    spx_spot = closes_series[-1] if closes_series else None

    calls = load_today_calls(today)

    # H-1: spot for chain pricing comes from the chain itself (put-call
    # parity); the yahoo EOD close is fallback only — by 16:50 the 18h-TTL
    # cache still holds the morning state (= previous close), and holiday
    # gaps made it 2 sessions stale on 2026-07-06 (−56 pts → every near-put
    # miv ~2.5vp low). spx_source is recorded on the row.
    spx_spot, spx_source = resolve_pricing_spot(puts, calls, spx_spot)
    summary["spx_source"] = spx_source

    # A. skew (unconditional; calls fail-soft — extension buckets only, SPEC-119)
    try:
        summary["skew"] = measure_skew(puts, vix, today, calls=calls, spx=spx_spot,
                                       spx_source=spx_source)
    except Exception as exc:
        log.exception("q085 skew measurement failed")
        summary["skew_error"] = str(exc)
        if not dry_run:
            _telegram_send(f"[S2-BPS PAPER] {today} skew 测量失败: {exc}", category="ACTION")

    # A2. SPEC-122 BCD real-quote shadow (pure recording, Telegram silent;
    # reuses the SAME production rec — AC-1 forbids recomputing the signal).
    # Fail-soft: a shadow error must never break the paper job.
    try:
        from notify.q087_bcd_quote_shadow import run as bcd_shadow_run
        summary["bcd_shadow"] = bcd_shadow_run(today, rec, calls, spx_spot, vix,
                                               dry_run=dry_run)
    except Exception as exc:
        log.exception("q087 bcd shadow failed")
        summary["bcd_shadow_error"] = str(exc)

    # A3. SPEC-123 BCD governance daily driver: chain marks for open BCD
    # positions, D1 gate evaluation (halt = routine review event), D2
    # quote-gate unlock check. Fail-soft like the shadow.
    try:
        from strategy.bcd_governance import daily_update as bcd_gov_update
        summary["bcd_governance"] = bcd_gov_update(today, calls=calls,
                                                   regime=regime, dry_run=dry_run)
    except Exception as exc:
        log.exception("q087 bcd governance failed")
        summary["bcd_governance_error"] = str(exc)

    # C. manage open positions
    closes = manage_open_positions(puts, today)
    summary["closes"] = closes
    for c in closes:
        stop_tag = " STOP" if c["reason"] == "stop" else ""
        if not dry_run:
            _telegram_send(
                f"[S2-BPS PAPER] 平仓 · {c['open_date']} 仓位 · "
                f"PnL mid ${c['pnl_mid']:,.0f} / natural ${c['pnl_natural']:,.0f} · "
                f"hold {c['hold_days']}d{stop_tag}"
            )

    # B. signal check + paper open (closes_series fetched above; if that fetch
    # failed, retry here so a transient error can't silently skip signal days)
    if not closes_series:
        closes_series = fetch_spx_history(period="2y")["close"].dropna().tolist()
    sig = signal_day(closes_series, vix, regime, strategy_key)
    summary["signal"] = sig
    if sig["signal"]:
        opened = build_paper_bps(puts, today, vix=vix, sig=sig)
        summary["open"] = opened
        if not dry_run:
            _telegram_send(
                f"[S2-BPS PAPER] 信号日 · SPX {opened['entry_spx']:,.0f} · VIX {vix:.1f} · "
                f"{opened['dte']}DTE {opened['k_short']:,.0f}/{opened['k_long']:,.0f} "
                f"credit mid ${opened['credit_mid']:.2f} / natural ${opened['credit_natural']:.2f}"
            )

    # D. degradation note (after closes)
    if closes:
        note = degradation_note()
        if note:
            summary["degradation"] = note
            if not dry_run:
                _telegram_send(
                    f"[S2-BPS PAPER] ⚠ WARNING 降级注记 · trailing10 ${note['trailing10_pnl_mid']:,.0f} · "
                    f"cum ${note['cum_pnl_mid']:,.0f}（paper 阶段仅记录，不停机）"
                )
    return summary


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # H-1 second layer: the 16:50 job must see TODAY's closes, not the 18h-TTL
    # morning cache — vix (moff baseline) and the selector rec (signal-day
    # determination!) both read these caches. Force one fresh pull per run;
    # yahoo failure still falls back to the stale cache inside
    # data.market_cache (fail-soft preserved). Entry-point only: tests and
    # importers are unaffected.
    import os
    os.environ.setdefault("SPX_REFRESH_YF_CACHE", "1")
    p = argparse.ArgumentParser(description="SPEC-116 Q085 S2-BPS daily paper job")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default today ET)")
    p.add_argument("--dry-run", action="store_true", help="no Telegram, still writes files")
    args = p.parse_args(argv)
    summary = run(args.date, dry_run=args.dry_run)
    print(json.dumps(summary, default=str, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
