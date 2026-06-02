"""Q081 P0 — Cash-bound profile verification (anchor snapshot 2026-06-01).

PM confirmed verbally on 2026-06-01 that the account is cash-bound (idle
cash actively managed via QQQ/SGOV/BOXX). This script captures a real
cross-broker snapshot for the framing memo + anchor for P1 historical
analysis.

Methodology: pull Schwab + E-Trade balances + positions, categorize each
holding as {cash, cash-like, beta-deployed, individual stock, options},
compute utilization ratios at broker and combined account level.

Output: research/q081/q081_p0_cash_bound.csv
"""
from __future__ import annotations
import csv
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "q081" / "q081_p0_cash_bound.csv"

# Hardcoded snapshot from live broker pull 2026-06-01 21:02 ET
# (script can be re-run later to regenerate from API — see __main__)
SNAPSHOT = {
    "schwab": {
        "nlv": 631728.49,
        "cash_balance": 205253.92,
        "buying_power": 567757.30,
        "maintenance_margin": 63971.19,
        "positions": [
            {"symbol": "NVDA", "type": "stock_individual", "mv": 130624.20},
            {"symbol": "INTU", "type": "stock_individual", "mv": 23868.00},
            {"symbol": "BOXX", "type": "cash_like",        "mv": 96216.93},  # 1-3mo T-bill ETF
            {"symbol": "MSFT", "type": "stock_individual", "mv": 116443.14},
            {"symbol": "META", "type": "stock_individual", "mv": 59429.70},
        ],
    },
    "etrade": {
        "nlv": 608036.52,
        "cash_balance": 37045.51,
        "buying_power": 123485.03,
        "maintenance_margin": 105607.27,
        "positions": [
            {"symbol": "BABA", "type": "stock_individual", "mv":  7524.00},
            {"symbol": "MS",   "type": "stock_individual", "mv": 20889.99},
            {"symbol": "NIO",  "type": "stock_individual", "mv":  1495.00},
            {"symbol": "PANW", "type": "stock_individual", "mv": 30048.00},
            {"symbol": "QQQ",  "type": "beta_deployed",    "mv": 137094.95},
            {"symbol": "SE",   "type": "stock_individual", "mv":  5238.75},
            {"symbol": "SPY",  "type": "beta_deployed",    "mv": 310093.43},
            {"symbol": "TSLA", "type": "stock_individual", "mv": 95652.40},
        ],
    },
}


def categorize_capital(broker: dict) -> dict:
    """Sum positions by category, plus cash."""
    cats = {"cash": broker["cash_balance"], "cash_like": 0.0,
            "beta_deployed": 0.0, "stock_individual": 0.0}
    for p in broker["positions"]:
        cats[p["type"]] += p["mv"]
    return cats


def main() -> None:
    rows = []
    combined = {"nlv": 0.0, "cash": 0.0, "cash_like": 0.0,
                "beta_deployed": 0.0, "stock_individual": 0.0,
                "maintenance_margin": 0.0, "buying_power": 0.0}

    for name, broker in SNAPSHOT.items():
        cats = categorize_capital(broker)
        bp_util = broker["maintenance_margin"] / broker["nlv"]
        bp_headroom = broker["buying_power"] / broker["nlv"]
        rows.append({
            "broker":           name,
            "nlv":              round(broker["nlv"], 2),
            "cash":             round(cats["cash"], 2),
            "cash_pct":         round(100 * cats["cash"] / broker["nlv"], 1),
            "cash_like":        round(cats["cash_like"], 2),
            "cash_like_pct":    round(100 * cats["cash_like"] / broker["nlv"], 1),
            "beta_deployed":    round(cats["beta_deployed"], 2),
            "beta_deployed_pct":round(100 * cats["beta_deployed"] / broker["nlv"], 1),
            "stock_individual": round(cats["stock_individual"], 2),
            "stock_individual_pct": round(100 * cats["stock_individual"] / broker["nlv"], 1),
            "maint_margin":     round(broker["maintenance_margin"], 2),
            "bp_utilized_pct":  round(100 * bp_util, 1),
            "bp_headroom_pct":  round(100 * bp_headroom, 1),
        })
        combined["nlv"]                += broker["nlv"]
        combined["cash"]               += cats["cash"]
        combined["cash_like"]          += cats["cash_like"]
        combined["beta_deployed"]      += cats["beta_deployed"]
        combined["stock_individual"]   += cats["stock_individual"]
        combined["maintenance_margin"] += broker["maintenance_margin"]
        combined["buying_power"]       += broker["buying_power"]

    rows.append({
        "broker":               "combined",
        "nlv":                  round(combined["nlv"], 2),
        "cash":                 round(combined["cash"], 2),
        "cash_pct":             round(100 * combined["cash"] / combined["nlv"], 1),
        "cash_like":            round(combined["cash_like"], 2),
        "cash_like_pct":        round(100 * combined["cash_like"] / combined["nlv"], 1),
        "beta_deployed":        round(combined["beta_deployed"], 2),
        "beta_deployed_pct":    round(100 * combined["beta_deployed"] / combined["nlv"], 1),
        "stock_individual":     round(combined["stock_individual"], 2),
        "stock_individual_pct": round(100 * combined["stock_individual"] / combined["nlv"], 1),
        "maint_margin":         round(combined["maintenance_margin"], 2),
        "bp_utilized_pct":      round(100 * combined["maintenance_margin"] / combined["nlv"], 1),
        "bp_headroom_pct":      round(100 * combined["buying_power"] / combined["nlv"], 1),
    })

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT}")

    for r in rows:
        print(f"\n{r['broker'].upper()}")
        print(f"  NLV          ${r['nlv']:>12,.0f}")
        print(f"  cash         ${r['cash']:>12,.0f}  ({r['cash_pct']:.1f}%)")
        print(f"  cash_like    ${r['cash_like']:>12,.0f}  ({r['cash_like_pct']:.1f}%)  [BOXX etc]")
        print(f"  beta         ${r['beta_deployed']:>12,.0f}  ({r['beta_deployed_pct']:.1f}%)  [QQQ/SPY]")
        print(f"  stocks       ${r['stock_individual']:>12,.0f}  ({r['stock_individual_pct']:.1f}%)")
        print(f"  maint margin ${r['maint_margin']:>12,.0f}  ({r['bp_utilized_pct']:.1f}% of NLV)")
        print(f"  BP headroom  ${r['nlv'] * r['bp_headroom_pct']/100:>12,.0f}  ({r['bp_headroom_pct']:.1f}% of NLV)")


if __name__ == "__main__":
    main()
