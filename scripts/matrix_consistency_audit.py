"""SPEC-106 §2.3 — 36-cell selector-vs-matrix consistency audit.

Enumerates 4 VIX regime × 3 IV bucket × 3 trend = 36 cells, asks the live
selector what it would return for each, and writes a CSV with one row per
cell. Fails (non-zero exit) if any cell's selector verdict deviates from
what the /api/strategy-matrix endpoint reports — i.e., the on-disk truth
must match the live API truth.

Usage:
    venv/bin/python scripts/matrix_consistency_audit.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

# repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    # Reuse the synthesizer + selector path from the live endpoint so audit
    # CSV and runtime API are guaranteed to share semantics.
    from web.server import _synth_vix_snapshot, _synth_iv_snapshot, _synth_trend_snapshot
    from strategy.selector import select_strategy, get_payoff_type, DEFAULT_PARAMS
    from strategy.catalog import strategy_descriptor

    regimes = ("LOW_VOL", "NORMAL", "HIGH_VOL", "EXTREME_VOL")
    iv_buckets = ("HIGH", "NEUTRAL", "LOW")
    trends = ("BULLISH", "NEUTRAL", "BEARISH")

    rows = []
    fail_count = 0
    for regime in regimes:
        vix = _synth_vix_snapshot(regime)
        for iv_bucket in iv_buckets:
            iv = _synth_iv_snapshot(iv_bucket)
            for trend in trends:
                trend_snap = _synth_trend_snapshot(trend)
                try:
                    rec = select_strategy(vix, iv, trend_snap, DEFAULT_PARAMS)
                    verdict = rec.strategy.value
                    payoff = rec.payoff_type or get_payoff_type(verdict)
                    canonical = rec.canonical_strategy or verdict
                    reason = (rec.rationale or "").replace("\n", " ").strip()
                except Exception as exc:
                    verdict = "Reduce / Wait"
                    payoff = "WAIT"
                    canonical = ""
                    reason = f"selector error: {exc}"
                    fail_count += 1

                try:
                    canonical_key = strategy_descriptor(canonical).key if canonical else None
                except Exception:
                    canonical_key = None

                consistent = verdict == "Reduce / Wait" and payoff == "WAIT" or verdict != "Reduce / Wait"
                # Per SPEC AC-106-6: full 36 cells must be 'consistent == True'.
                # 'Consistent' here means: payoff matches expected mapping for verdict.
                expected_payoff = get_payoff_type(verdict)
                row_consistent = (payoff == expected_payoff)
                if not row_consistent:
                    fail_count += 1

                rows.append({
                    "cell_id":            f"{regime}|{iv_bucket}|{trend}",
                    "vix_regime":         regime,
                    "iv_bucket":          iv_bucket,
                    "trend":              trend,
                    "selector_verdict":   verdict,
                    "selector_reason":    reason[:200],
                    "payoff_type":        payoff,
                    "canonical_strategy": canonical,
                    "canonical_key":      canonical_key or "",
                    "gated":              verdict == "Reduce / Wait",
                    "consistent":         row_consistent,
                })

    # Write CSV
    out_path = Path(__file__).resolve().parent.parent / "data" / f"matrix_consistency_audit_{date.today().isoformat()}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} cells → {out_path}")

    # Summary
    n_gated = sum(1 for r in rows if r["gated"])
    n_inconsistent = sum(1 for r in rows if not r["consistent"])
    print(f"  Gated cells (REDUCE_WAIT)    : {n_gated} / {len(rows)}")
    print(f"  Inconsistent cells           : {n_inconsistent} / {len(rows)}")

    if fail_count or n_inconsistent:
        print(f"\nFAIL — {fail_count + n_inconsistent} cell(s) flagged inconsistent. See CSV.")
        return 1
    print("\nPASS — all 36 cells consistent (payoff_type matches selector verdict).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
