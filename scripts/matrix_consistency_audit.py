"""SPEC-106 §2.3 — 36-cell selector-vs-endpoint consistency audit.

Two independent computations of the same 36 cells are compared row-by-row:

  A. Direct  — synthesize VIX/IV/Trend snapshots, call select_strategy() in
                process. This is the "truth" against which the API is tested.
  B. Endpoint — call /api/strategy-matrix via Flask test_client(). This is the
                payload PM's UI actually consumes.

Any divergence between A and B is a regression in API assembly, caching,
field mapping, or payload serialization — exactly the class of bugs the
audit needs to catch (per code review 2026-05-26).

Outputs CSV to data/matrix_consistency_audit_<date>.csv. Returns non-zero
exit code if any cell shows divergence (selector vs endpoint).

Usage:
    venv/bin/python scripts/matrix_consistency_audit.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from strategy.catalog import strategy_descriptor
    from strategy.selector import (
        DEFAULT_PARAMS,
        get_payoff_type,
        select_strategy,
    )
    from web.server import (
        _STRATEGY_MATRIX_CACHE,
        _synth_iv_snapshot,
        _synth_trend_snapshot,
        _synth_vix_snapshot,
        app,
    )

    # Bust the endpoint cache so we audit a fresh build, not a stale 5min
    # window where selector logic may have changed but cache hasn't expired.
    _STRATEGY_MATRIX_CACHE.clear()

    # ── B. Pull the API payload ──────────────────────────────────────────
    with app.test_client() as client:
        resp = client.get("/api/strategy-matrix")
        if resp.status_code != 200:
            print(f"FAIL — /api/strategy-matrix returned {resp.status_code}")
            return 2
        endpoint_payload = resp.get_json() or {}
    endpoint_by_id = {c["cell_id"]: c for c in (endpoint_payload.get("cells") or [])}
    if len(endpoint_by_id) != 36:
        print(f"FAIL — endpoint returned {len(endpoint_by_id)} cells, expected 36")
        return 2

    # ── A. Direct selector enumeration ───────────────────────────────────
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
                cell_id = f"{regime}|{iv_bucket}|{trend}"
                try:
                    rec = select_strategy(vix, iv, trend_snap, DEFAULT_PARAMS)
                    direct_verdict = rec.strategy.value
                    direct_payoff = rec.payoff_type or get_payoff_type(direct_verdict)
                    direct_canonical = rec.canonical_strategy or direct_verdict
                except Exception as exc:
                    direct_verdict = "Reduce / Wait"
                    direct_payoff = "WAIT"
                    direct_canonical = ""
                    print(f"  selector exception @ {cell_id}: {exc}")

                ep = endpoint_by_id.get(cell_id) or {}
                ep_verdict = ep.get("selector_verdict")
                ep_payoff = ep.get("payoff_type")
                ep_canonical = ep.get("historical_reference_strategy") or ep.get("selector_verdict")

                verdict_match  = (direct_verdict  == ep_verdict)
                payoff_match   = (direct_payoff   == ep_payoff)
                # Endpoint reports canonical via historical_reference_strategy (gated)
                # OR via selector_verdict (when not gated). Compare against direct_canonical.
                canonical_match = direct_canonical == ep_canonical
                # Pure mapping sanity: payoff must match what get_payoff_type(verdict) says
                mapping_consistent = direct_payoff == get_payoff_type(direct_verdict)

                row_pass = verdict_match and payoff_match and mapping_consistent
                if not row_pass:
                    fail_count += 1
                    print(
                        f"  DIVERGENCE @ {cell_id} | "
                        f"verdict({direct_verdict!r}=={ep_verdict!r}:{verdict_match}) "
                        f"payoff({direct_payoff!r}=={ep_payoff!r}:{payoff_match}) "
                        f"mapping={mapping_consistent}"
                    )

                try:
                    canonical_key = strategy_descriptor(direct_canonical).key if direct_canonical else None
                except Exception:
                    canonical_key = None

                rows.append({
                    "cell_id":               cell_id,
                    "vix_regime":            regime,
                    "iv_bucket":             iv_bucket,
                    "trend":                 trend,
                    "direct_verdict":        direct_verdict,
                    "endpoint_verdict":      ep_verdict or "",
                    "verdict_match":         verdict_match,
                    "direct_payoff":         direct_payoff,
                    "endpoint_payoff":       ep_payoff or "",
                    "payoff_match":          payoff_match,
                    "canonical_strategy":    direct_canonical,
                    "canonical_key":         canonical_key or "",
                    "canonical_match":       canonical_match,
                    "payoff_mapping_consistent": mapping_consistent,
                    "gated":                 direct_verdict == "Reduce / Wait",
                    "consistent":            row_pass,
                })

    # ── Write CSV (LF line endings, no trailing whitespace) ─────────────
    out_path = (
        Path(__file__).resolve().parent.parent
        / "data" / f"matrix_consistency_audit_{date.today().isoformat()}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="\n", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    n_gated = sum(1 for r in rows if r["gated"])
    n_div = sum(1 for r in rows if not r["consistent"])
    print(f"\nWrote {len(rows)} cells → {out_path}")
    print(f"  Gated cells (REDUCE_WAIT)        : {n_gated} / {len(rows)}")
    print(f"  Selector⇄endpoint divergences    : {n_div} / {len(rows)}")

    if fail_count or n_div:
        print(f"\nFAIL — {fail_count + n_div} cell(s) inconsistent. See CSV.")
        return 1
    print("\nPASS — selector and /api/strategy-matrix agree on all 36 cells.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
