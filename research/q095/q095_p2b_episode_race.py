"""Q095 P2b — episode 级真值的模式切换赛跑(修正案,PM 2026-07-11 ratify)。

预注册(单值,不网格;post-null 二次定义,稳健性前置披露于 findings):
  真值 episode:Close 极差带 X=5% 内驻留 ≥ N=15 TD 的最大不重叠段
    (X 取整带宽,与 6 月 motivating case 4.7% 同量级;N=15 与 P2 findings
     §2 已用的 ≥15TD 口径一致)
  分类器:C1-C4 沿用 P2 登记(中位切点) + C5 trailing-band
    (trailing 15TD Close 极差 ≤5% —— episode 真值的实时直译,结构 lag ≥14TD)
  杀标:K0 episode 频率 < 0.5/yr → 关(价值上限不足)
        K1 flip >8%/d 或 5TD 回翻 >50%
        K2' median(episode 长度) − median(lag) < 5 TD
窗口 2000→。Output: q095_p2b_race.csv + q095_p2b_episodes.csv + 摘要。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "q095"

from research.q095.q095_p2_race_factlayer import load_ohlc, atr14, adx14  # noqa: E402

BAND = 0.05
MIN_LEN = 15
K0_FREQ = 0.5
K1_FLIP, K1_REV5, K2_MIN = 0.08, 0.50, 5


def find_episodes(close: pd.Series) -> list[tuple[int, int]]:
    """Maximal non-overlapping segments: range/mid ≤ BAND and length ≥ MIN_LEN."""
    vals = close.values
    n = len(vals)
    out = []
    s = 0
    while s < n - MIN_LEN:
        lo = hi = vals[s]
        e = s
        for j in range(s + 1, n):
            lo, hi = min(lo, vals[j]), max(hi, vals[j])
            if (hi - lo) / ((hi + lo) / 2) > BAND:
                break
            e = j
        if e - s + 1 >= MIN_LEN:
            out.append((s, e))
            s = e + 1
        else:
            s += 1
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_ohlc()
    a = atr14(df)
    c = df.Close
    frame = pd.DataFrame({
        "C1_ER20": (c - c.shift(20)).abs() / c.diff().abs().rolling(20).sum(),
        "C2_RangeATR": (df.High.rolling(20).max() - df.Low.rolling(20).min()) / a,
        "C3_MA20slope": (c.rolling(20).mean() - c.rolling(20).mean().shift(5)).abs() / (5 * a),
        "C5_TrailBand": (c.rolling(MIN_LEN).max() - c.rolling(MIN_LEN).min())
                        / c.rolling(MIN_LEN).mean(),
        "C4_ADX": adx14(df),
        "close": c,
    }).loc["2000-01-01":].dropna()

    eps = find_episodes(frame["close"])
    years = len(frame) / 252
    lengths = pd.Series([e - s + 1 for s, e in eps])
    freq = len(eps) / years
    print(f"样本 {len(frame)} TD | episodes(≤{BAND*100:.0f}% 带 ≥{MIN_LEN}TD): n={len(eps)} "
          f"({freq:.2f}/yr) | 长度 median {lengths.median():.0f} / p75 {lengths.quantile(.75):.0f} "
          f"/ max {lengths.max():.0f} TD")
    pd.DataFrame([{"start": frame.index[s].date(), "end": frame.index[e].date(),
                   "len_td": e - s + 1} for s, e in eps]).to_csv(
        OUT / "q095_p2b_episodes.csv", index=False)

    k0 = "DEAD" if freq < K0_FREQ else "pass"
    print(f"K0 频率杀标({K0_FREQ}/yr): {k0}")
    if k0 == "DEAD":
        print("→ P2b 死于 K0，分类器赛跑不再执行（预注册条款）")
        return 0

    rows = []
    for name, invert in (("C1_ER20", True), ("C2_RangeATR", True), ("C3_MA20slope", True),
                         ("C4_ADX", True), ("C5_TrailBand", None)):
        if name == "C5_TrailBand":
            sig = frame[name] <= BAND          # 直译真值,固有阈值,非中位切点
        else:
            sig = frame[name] < frame[name].median()
        flips = (sig != sig.shift()).iloc[1:]
        flip_rate = flips.mean()
        fi = np.where(flips.values)[0] + 1
        rev5 = sum(1 for i in fi
                   if (sig.iloc[i + 1:min(i + 6, len(sig))] != sig.iloc[i]).any())
        rev5_rate = rev5 / max(len(fi), 1)
        lags, misses = [], 0
        for s, e in eps:
            det = next((i - s for i in range(s, e + 1) if sig.iloc[i]), None)
            if det is None:
                misses += 1
            else:
                lags.append(det)
        lag_med = float(np.median(lags)) if lags else float("nan")
        window = float(lengths.median()) - lag_med if lags else float("nan")
        k1 = "DEAD" if (flip_rate > K1_FLIP or rev5_rate > K1_REV5) else "pass"
        k2 = "DEAD" if (not lags or window < K2_MIN) else "pass"
        rows.append(dict(classifier=name, flip_rate_pct=round(flip_rate * 100, 2),
                         rev5_rate_pct=round(rev5_rate * 100, 1), lag_median_td=lag_med,
                         miss_rate_pct=round(misses / len(eps) * 100, 1),
                         episode_median_td=float(lengths.median()),
                         race_window_td=round(window, 1) if window == window else None,
                         K1=k1, K2=k2,
                         verdict="SURVIVES" if k1 == k2 == "pass" else "DEAD"))
        r = rows[-1]
        print(f"{name:>13s} | flip {r['flip_rate_pct']:>5.2f}%/d rev5 {r['rev5_rate_pct']:>5.1f}% K1 {k1:>4s}"
              f" | lag {lag_med:>4.0f} miss {r['miss_rate_pct']:>4.1f}% window {r['race_window_td']}"
              f" K2 {k2:>4s} | {r['verdict']}")
    pd.DataFrame(rows).to_csv(OUT / "q095_p2b_race.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
