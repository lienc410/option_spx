"""One-shot data corrections for the 2026-07-06 watch-day hotfixes (H-1/H-3).

Run ON OLDAIR after deploying the code fixes. Idempotent-ish: refuses to run
twice (checks correction markers). Everything gets a .bak-h1 backup first.

  H-1: recompute the 7/6 skew-monitor row with chain-parity spot (+ true VIX
       close 15.57) — the recorded row was solved against the stale 7/2 yahoo
       close (−56 pts; near-put miv ~2.5vp low, calls symmetric high).
       Then re-derive the 7/6 BCD shadow row's miv/model fields.
  H-3: fix the two 2026-06-05_bcd_* close rows (debit sign slip: recorded
       −85,100, truth +2,900/contract), append correction events to the
       trade log, and clear the FALSE D1 halt those dirty rows triggered
       (G2+G4 fired on −175,460 garbage; corrected family cum ≈ +540).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MONITOR = ROOT / "data" / "q085_skew_monitor.jsonl"
SHADOW = ROOT / "data" / "q087_bcd_quote_shadow.jsonl"
CLOSED = ROOT / "data" / "closed_trades.jsonl"
DATE = "2026-07-06"
TRUE_VIX = 15.57          # yahoo 7/6 close, fetched fresh (matches quant hand calc)
NOTE_H1 = "H-1 correction 2026-07-06: recomputed with chain-parity spot (stale yahoo 7/2 close polluted miv/moff)"
NOTE_H3 = "H-3 correction 2026-07-06: debit close sign slip (entered +440 received as cost); truth +2,900/contract"


def _backup(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak-h1")
    if not b.exists():
        shutil.copy2(p, b)


def _rewrite_jsonl(p: Path, transform) -> int:
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    changed = 0
    out = []
    for r in rows:
        nr = transform(r)
        if nr is not None and nr != r:
            changed += 1
            out.append(nr)
        else:
            out.append(r if nr is None else nr)
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in out))
    return changed


def fix_monitor() -> dict:
    import notify.q085_s2bps_paper as q
    puts = q.load_today_chain(DATE)
    calls = q.load_today_calls(DATE)
    assert puts is not None and calls is not None, "7/6 chain missing"
    spot = q.parity_spot(puts, calls)
    assert spot and 7500 < spot < 7580, f"parity spot suspicious: {spot}"
    orig = q.SKEW_OUT
    q.SKEW_OUT = Path(tempfile.mkdtemp()) / "skew.jsonl"
    try:
        row = q.measure_skew(puts, TRUE_VIX, DATE, calls=calls, spx=spot,
                             spx_source="chain_parity")
    finally:
        q.SKEW_OUT = orig
    row["correction_note"] = NOTE_H1

    _backup(MONITOR)
    n = _rewrite_jsonl(MONITOR, lambda r: row if r.get("date") == DATE else None)
    assert n == 1, f"expected to replace exactly 1 monitor row, replaced {n}"
    print(f"[H-1] monitor row replaced: spx={row['spx']} vix={row['vix']} "
          f"d30_moff={row['d30_moff']} (expect ~-0.8±0.5) "
          f"c30_moff={row.get('c30_moff')} atm_moff={row['atm_moff']}")
    return row


def fix_shadow(spot: float) -> None:
    from pricing import core
    from pricing.calibration import load_offsets_merged
    from pricing.sigma import SigmaMode, sigma_for
    offsets, _ = load_offsets_merged([MONITOR,
                                      ROOT / "research/q087/q087_moff_backfill.jsonl"])

    def transform(r):
        if r.get("date") != DATE or "long_mid" in r and r.get("correction_note"):
            return None
        if "long_mid" not in r:
            return None
        nr = dict(r)
        nr["spx"], nr["vix"] = round(spot, 2), TRUE_VIX

        def px(strike, dte, sigma):
            return core.call_price(spot, strike, dte / 365.0, sigma, 0.045, q=0.0)

        for prefix in ("long", "short"):
            miv = core.implied_vol(r[f"{prefix}_mid"], spot, r[f"{prefix}_strike"],
                                   r[f"{prefix}_dte"] / 365.0, 0.045, is_call=True)
            if miv is not None:
                nr[f"{prefix}_miv"] = round(miv * 100.0, 2)
        flat = TRUE_VIX / 100.0
        nr["model_flat_debit"] = round(
            px(r["long_strike"], r["long_dte"], flat)
            - px(r["short_strike"], r["short_dte"], flat), 4)

        def sig(prefix, mode, adverse=None):
            kw = dict(vix=TRUE_VIX, option_type="CALL",
                      abs_delta=abs(r[f"{prefix}_delta"]),
                      dte=int(r[f"{prefix}_dte"]), offsets=offsets)
            if mode is SigmaMode.CALIB:
                return sigma_for(SigmaMode.CALIB, **kw)
            return sigma_for(SigmaMode.PESS, adverse_sign=adverse, bracket_vp=1.0, **kw)

        nr["model_calib_debit"] = round(
            px(r["long_strike"], r["long_dte"], sig("long", SigmaMode.CALIB))
            - px(r["short_strike"], r["short_dte"], sig("short", SigmaMode.CALIB)), 4)
        nr["model_pess_debit"] = round(
            px(r["long_strike"], r["long_dte"], sig("long", SigmaMode.PESS, +1))
            - px(r["short_strike"], r["short_dte"], sig("short", SigmaMode.PESS, -1)), 4)
        nr["correction_note"] = NOTE_H1
        return nr

    _backup(SHADOW)
    n = _rewrite_jsonl(SHADOW, transform)
    print(f"[H-1] shadow rows corrected: {n}")


def fix_closes() -> None:
    def transform(r):
        if r.get("trade_id") in ("2026-06-05_bcd_001", "2026-06-05_bcd_002") \
                and r.get("realized_pnl") == -85100.0:
            nr = dict(r)
            nr["exit_debit_per_share"] = -440.0
            nr["realized_pnl"] = 2900.0
            nr["close_reason"] = "discretionary"
            nr["correction_note"] = NOTE_H3
            return nr
        return None

    _backup(CLOSED)
    n = _rewrite_jsonl(CLOSED, transform)
    print(f"[H-3] closed_trades rows corrected: {n} (expect 2)")

    from logs.trade_log_io import append_event, load_log
    existing = {(r.get("id"), r.get("note")) for r in load_log()
                if r.get("event") == "correction"}
    ts = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    for tid in ("2026-06-05_bcd_001", "2026-06-05_bcd_002"):
        if (tid, NOTE_H3) in existing:
            print(f"[H-3] correction already logged for {tid}")
            continue
        append_event({"id": tid, "event": "correction", "timestamp": ts,
                      "target_event": "close",
                      "fields": {"exit_premium": -440.0, "actual_pnl": 2900.0,
                                 "exit_reason": "discretionary"},
                      "note": NOTE_H3})
        print(f"[H-3] correction event appended for {tid}")


def clear_false_halt() -> None:
    import strategy.bcd_governance as gov
    halt = gov.is_halted()
    if not halt:
        print("[gov] no halt present")
        return
    gov.pm_clear("2026-07-06 假 halt：H-3 close 事件 PnL 符号错误（−85,100×2 脏数据）"
                 "触发 G2+G4；ledger correction 后真实 realized +2,900×2，四门无一触发。"
                 "数据更正记录，非复审豁免。")
    fired = gov.evaluate_gates(DATE)
    print(f"[gov] halt cleared; re-evaluation fires: {fired or 'NONE'}")
    assert fired == [], f"gates still firing after correction: {fired}"


if __name__ == "__main__":
    row = fix_monitor()
    fix_shadow(row["spx"])
    fix_closes()
    clear_false_halt()
    print("all corrections applied")
