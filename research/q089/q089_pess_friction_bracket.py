"""Q089 — PESS friction bracket (quantifying the caveat, not assuming it).

Caveat under test: measured friction is from ONE calm LOW_VOL day; stress
spreads are wider, and wider friction penalizes the higher-transaction-count
incumbent arms. Bracket: double both leg frictions (0.2%->0.4%, 1.0%->2.0%)
and rerun E2 (selected window wait3) and E4 (full rule table via module
import). If verdicts hold at 2x, the caveat is closed quantitatively.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import q089_calib_lib as L

L.LONG_FRICTION *= 2   # 0.4%
L.SHORT_FRICTION *= 2  # 2.0%
print(f"BRACKET frictions: long={L.LONG_FRICTION:.3f} short={L.SHORT_FRICTION:.3f}\n")

import q089_e2_entry_timing as E2  # noqa: E402  (top-level loads only)

inc = E2.run_incumbent()
ch3 = E2.run_challenger(3)
for tag, lo, hi in (("select<2013", "2000", "2013"), ("confirm>=2013", "2013", "2100"),
                    ("full", "2000", "2100")):
    di = inc[(inc.entry_date >= lo) & (inc.entry_date < hi)].pnl_usd.sum()
    dc = ch3[(ch3.entry_date >= lo) & (ch3.entry_date < hi)].pnl_usd.sum()
    print(f"E2@2x wait3 {tag}: dTotal={dc - di:+,.0f} (inc {di:+,.0f} n={len(inc)}, ch {dc:+,.0f} n={len(ch3)})")
lo95, hi95 = E2.boot_delta_total(inc, ch3)
print(f"E2@2x bootstrap 95% CI dTotal: [{lo95:+,.0f}, {hi95:+,.0f}]\n")

print("== E4 @2x friction (full table from module run) ==")
csv = Path(__file__).parent / "q089_e4_results.csv"
base = csv.read_bytes()  # e4 module overwrites this file; preserve base case
import q089_e4_resell_timing  # noqa: E402,F401  (executes and prints)
(Path(__file__).parent / "q089_e4_results_2x.csv").write_bytes(csv.read_bytes())
csv.write_bytes(base)
