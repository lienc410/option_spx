"""Q087 A3 — executable runner: HV Ladder stop-convention comparison.

Reproduces the A3 verdict table (15x / 3x / 5x, promoted config
run_phase2_hvlad(mode="filtered"), only V2F_STOP_MULT varied).
External review verified: no state leakage across monkey-patched runs;
n=147 vs 149 is real mechanism (stops free ladder slots earlier).
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import research.strategies.ES_puts.backtest as ES

def stats(res, label):
    p = np.array([t.pnl for t in res.trades])
    stops = sum(1 for t in res.trades if "stop" in t.exit_reason.lower())
    k = max(1, int(0.10 * len(p)))
    recent = [t.pnl for t in res.trades if t.entry_date >= "2024-01-01"]
    print(f"{label:<9} n={len(p):>3} stops={stops:>3} win={100*(p>0).mean():.0f}% "
          f"mean=${p.mean():,.0f} worst=${p.min():,.0f} CVaR10=${np.sort(p)[:k].mean():,.0f} "
          f"total=${p.sum():,.0f} 2024+={len(recent)}x${np.mean(recent) if recent else float('nan'):,.0f}")

if __name__ == "__main__":
    for stop in (15.0, 10.0, 5.0, 3.0):
        ES.V2F_STOP_MULT = stop
        stats(ES.run_phase2_hvlad(mode="filtered"), f"stop {stop}x")
