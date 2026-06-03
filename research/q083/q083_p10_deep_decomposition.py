"""Q083 P10 — Deep decomposition of "几乎不能开仓" using cache values.

Step 1: 26y NORMAL × BULL days, decompose ALL routings.
Step 2: For each blocking pattern (iv_signal=LOW, IVP-out-of-band, both),
        characterize the days — absolute VIX level, IVR/IVP values, what
        the SPX did after.
Step 3: Identify which blocking patterns COULD safely be relaxed.

Key insight from G2: PM's current pain is iv_signal=LOW × IVP<40.
Both gates block. Neither one alone would unblock. To meaningfully
help PM, we need to address BOTH layers OR design a new path.

Critical constraint: don't reproduce Q081 P4's vega-tail failure mode
(BPS in absolute-low-IV regime → vol expansion catastrophe).
"""
from __future__ import annotations
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
OUT_DIR = ROOT / "research" / "q083"


def main():
    rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "date":     r["date"],
                    "vix":      float(r["vix"]),
                    "ivr":      float(r["ivr"]),
                    "ivp":      float(r["ivp"]),
                    "ivp63":    float(r["ivp63"]) if r["ivp63"] else None,
                    "iv_signal": r["iv_signal"],
                    "regime":   r["regime"],
                    "trend":    r["trend"],
                    "strategy_key": r["strategy_key"],
                    "spx":      float(r["spx"]) if r["spx"] else None,
                })
            except (ValueError, TypeError):
                continue
    rows.sort(key=lambda r: r["date"])

    universe = [r for r in rows if r["regime"] == "NORMAL" and r["trend"] == "BULLISH"]
    n = len(universe)
    print(f"NORMAL × BULL universe: {n} days (2000-2026)\n")

    # 1. Decompose by gate failure
    print("=" * 80)
    print("1. ROOT-CAUSE DECOMPOSITION (which gate fires)")
    print("=" * 80)

    def gate_result(r):
        sig = r["iv_signal"]
        ivp = r["ivp"]
        if sig == "LOW":
            return "iv_signal_LOW_blocks_cell"
        # iv_signal NEUTRAL or HIGH
        if sig == "NEUTRAL":
            if ivp < 43: return "ivp_below_NNB_lower"
            if ivp > 55: return "ivp_above_NNB_upper"
            return "passes_gate"
        # HIGH
        if ivp < 40 or ivp > 70:
            return "ivp_out_of_HIGH_band"
        return "passes_gate"

    counts = defaultdict(int)
    for r in universe:
        counts[gate_result(r)] += 1

    print(f"{'reason':<35} {'count':>6} {'%':>7}")
    for reason, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {reason:<33} {c:>6} {100*c/n:>6.1f}%")

    # 2. iv_signal LOW universe characterization
    print("\n" + "=" * 80)
    print("2. iv_signal=LOW (matrix routes reduce_wait) — characterization")
    print("=" * 80)
    iv_low = [r for r in universe if r["iv_signal"] == "LOW"]
    print(f"n = {len(iv_low)}")
    vix_levels = [r["vix"] for r in iv_low]
    print(f"VIX distribution (absolute level):")
    print(f"  min={min(vix_levels):.2f}, max={max(vix_levels):.2f}")
    print(f"  median={median(vix_levels):.2f}, mean={mean(vix_levels):.2f}")
    for lo, hi in [(13,15), (15,16), (16,17), (17,18), (18,19), (19,20), (20,21), (21,22)]:
        sub = [v for v in vix_levels if lo <= v < hi]
        if sub:
            print(f"  VIX [{lo},{hi}): {len(sub)} days  ({100*len(sub)/len(iv_low):.1f}%)")

    ivr_levels = [r["ivr"] for r in iv_low]
    print(f"IVR distribution (% of 52w range):")
    print(f"  min={min(ivr_levels):.1f}, max={max(ivr_levels):.1f}, median={median(ivr_levels):.1f}")

    ivp_levels = [r["ivp"] for r in iv_low]
    print(f"IVP distribution:")
    print(f"  min={min(ivp_levels):.1f}, max={max(ivp_levels):.1f}, median={median(ivp_levels):.1f}")

    # 3. The "interesting" subset: VIX >= 15 AND iv_signal=LOW
    print("\n" + "=" * 80)
    print("3. 'INTERESTING' SUBSET: VIX >= 15 + iv_signal=LOW")
    print("=" * 80)
    print("These are days where ABSOLUTE VIX is moderate (15+) but IVR is low.")
    print("They differ from 'LOW_VOL × LOW IVR' (VIX<15) cases where Q081 P4")
    print("vega-tail asymmetry argument applies.\n")

    interesting = [r for r in iv_low if r["vix"] >= 15]
    print(f"n = {len(interesting)}  ({100*len(interesting)/len(iv_low):.1f}% of iv_low days)")
    print(f"VIX distribution in this subset:")
    for lo, hi in [(15,16), (16,17), (17,18), (18,19), (19,20), (20,21), (21,22)]:
        sub = [r for r in interesting if lo <= r["vix"] < hi]
        if sub:
            print(f"  [{lo},{hi}): {len(sub)} days")

    # 4. Forward outcome for this subset — what did SPX do next 21 days?
    print("\n" + "=" * 80)
    print("4. FORWARD 21D SPX RETURN for 'interesting' subset")
    print("=" * 80)
    print("Tests: did opening BPS here historically face vol expansion / SPX drop?")

    # Need date-indexed SPX for forward returns
    spx_by_date = {r["date"]: r["spx"] for r in rows if r["spx"] is not None}
    spx_dates = sorted(spx_by_date.keys())

    fwd_returns = []
    fwd_max_drops = []
    fwd_vix_rises = []
    vix_by_date = {r["date"]: r["vix"] for r in rows}
    for r in interesting:
        entry_iso = r["date"]
        entry_spx = r["spx"]
        if entry_spx is None:
            continue
        entry_vix = r["vix"]
        # Find SPX 21 trading days forward
        try:
            idx = spx_dates.index(entry_iso)
            if idx + 21 >= len(spx_dates):
                continue
            fwd_iso = spx_dates[idx + 21]
            fwd_spx = spx_by_date[fwd_iso]
            ret = (fwd_spx - entry_spx) / entry_spx
            # Max drawdown over 21 days
            window_spx = [spx_by_date[spx_dates[idx+i]] for i in range(1, 22) if spx_dates[idx+i] in spx_by_date]
            window_vix = [vix_by_date.get(spx_dates[idx+i]) for i in range(1, 22)]
            window_vix = [v for v in window_vix if v is not None]
            if window_spx and window_vix:
                max_drop = (min(window_spx) - entry_spx) / entry_spx
                max_vix_rise = max(window_vix) - entry_vix
                fwd_returns.append(ret)
                fwd_max_drops.append(max_drop)
                fwd_vix_rises.append(max_vix_rise)
        except (ValueError, IndexError):
            continue

    if fwd_returns:
        print(f"n = {len(fwd_returns)}")
        print(f"\nForward 21d SPX return:")
        print(f"  mean: {mean(fwd_returns)*100:>+5.1f}%, median: {median(fwd_returns)*100:>+5.1f}%")
        print(f"  worst: {min(fwd_returns)*100:>+5.1f}%, best: {max(fwd_returns)*100:>+5.1f}%")
        up = sum(1 for r in fwd_returns if r > 0)
        print(f"  up windows: {up}/{len(fwd_returns)} = {100*up/len(fwd_returns):.1f}%")

        print(f"\nMax drawdown (worst intraday drop) over 21d window:")
        print(f"  median max-drop: {median(fwd_max_drops)*100:>+5.1f}%")
        big_drops = sum(1 for d in fwd_max_drops if d < -0.05)
        print(f"  days with max-drop > 5%: {big_drops}/{len(fwd_max_drops)} = {100*big_drops/len(fwd_max_drops):.1f}%")

        print(f"\nMax VIX rise over 21d window:")
        print(f"  median: +{median(fwd_vix_rises):.1f} vol points")
        big_rises = sum(1 for v in fwd_vix_rises if v >= 5)
        print(f"  days with VIX rise >= +5vp: {big_rises}/{len(fwd_vix_rises)} = {100*big_rises/len(fwd_vix_rises):.1f}%")

    # 5. Compare to LOW_VOL (Q081 P4's actual concern)
    print("\n" + "=" * 80)
    print("5. CONTRAST: LOW_VOL × BULL (Q081 P4's vega-tail case)")
    print("=" * 80)
    low_vol_bull = [r for r in rows if r["regime"] == "LOW_VOL" and r["trend"] == "BULLISH"]
    print(f"n = {len(low_vol_bull)} (this is what Q081 P4 was actually concerned about)")
    if low_vol_bull:
        vix_levels = [r["vix"] for r in low_vol_bull]
        print(f"VIX: median {median(vix_levels):.2f}, range [{min(vix_levels):.2f}, {max(vix_levels):.2f}]")
        # Forward outcomes for LOW_VOL
        lv_returns = []
        lv_drops = []
        lv_vix_rises = []
        for r in low_vol_bull:
            entry_iso = r["date"]
            entry_spx = r["spx"]
            entry_vix = r["vix"]
            if entry_spx is None:
                continue
            try:
                idx = spx_dates.index(entry_iso)
                if idx + 21 >= len(spx_dates):
                    continue
                window_spx = [spx_by_date[spx_dates[idx+i]] for i in range(1, 22) if spx_dates[idx+i] in spx_by_date]
                window_vix = [vix_by_date.get(spx_dates[idx+i]) for i in range(1, 22)]
                window_vix = [v for v in window_vix if v is not None]
                if window_spx and window_vix:
                    max_drop = (min(window_spx) - entry_spx) / entry_spx
                    fwd_ret = (window_spx[-1] - entry_spx) / entry_spx
                    max_vix_rise = max(window_vix) - entry_vix
                    lv_returns.append(fwd_ret)
                    lv_drops.append(max_drop)
                    lv_vix_rises.append(max_vix_rise)
            except (ValueError, IndexError):
                continue
        if lv_returns:
            print(f"  21d forward SPX: median {median(lv_returns)*100:+.1f}%, worst {min(lv_returns)*100:+.1f}%")
            print(f"  Max drawdown >5%: {sum(1 for d in lv_drops if d<-0.05)}/{len(lv_drops)} = "
                  f"{100*sum(1 for d in lv_drops if d<-0.05)/len(lv_drops):.1f}%")
            big_rises = sum(1 for v in lv_vix_rises if v >= 5)
            print(f"  Max VIX rise >= +5vp: {big_rises}/{len(lv_vix_rises)} = {100*big_rises/len(lv_vix_rises):.1f}%")

    print("\n" + "=" * 80)
    print("COMPARATIVE: vol-expansion risk by regime")
    print("=" * 80)
    print("If NORMAL × IV_LOW (VIX>=15) has SIMILAR vol-expansion risk as LOW_VOL,")
    print("then routing BPS to it would reproduce Q081 P4's problem.")
    print("If it has LESS risk, the matrix is over-conservative.")


if __name__ == "__main__":
    main()
