"""Q095 P2 — 模式切换赛跑:事实层(预注册 2026-07-11,PM 当日 ratify)。

严格按 q095_p2_framing_memo 执行,不加变体:
  真值:day t ∈ chop ⟺ |S_{t+20} − S_t| < 1 × ATR14_t(后视定义,仅作 ground truth)
  分类器(4 个锁死,切点=全样本中位数,事实层惯例,K3 反事实需 walk-forward 另议):
    C1 ER20        = |S_t−S_{t-20}| / Σ|ΔS|(20d)          — 低于中位 → chop
    C2 RangeATR    = (20d High−Low) / ATR14                — 低于中位 → chop
    C3 |MA20 斜率| = |MA20_t − MA20_{t-5}| / (5·ATR14)     — 低于中位 → chop
    C4 ADX14(Wilder)                                       — 低于中位 → chop
  三分布:转换频率+detection lag / dwell time / flip-rate
  杀标:K1 日翻转率>8% 或 5TD 回翻率>50%;K2 median(dwell)−median(lag)<5TD

窗口:2000-01-01 →(26y,与引擎时代一致)。Output: q095_p2_race.csv + 摘要。
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

K1_FLIP = 0.08
K1_REV5 = 0.50
K2_MIN_WINDOW = 5


def load_ohlc() -> pd.DataFrame:
    df = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[["Open", "High", "Low", "Close"]].dropna()
    return df.loc["1999-01-01":]      # warmup 前置一年


def atr14(df: pd.DataFrame) -> pd.Series:
    tr = pd.concat([
        df.High - df.Low,
        (df.High - df.Close.shift()).abs(),
        (df.Low - df.Close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()


def adx14(df: pd.DataFrame) -> pd.Series:
    up = df.High.diff()
    dn = -df.Low.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr = atr14(df)
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/14, adjust=False).mean()


def segments(mask: pd.Series) -> list[tuple[int, int]]:
    """True-run [start_idx, end_idx] inclusive, positional."""
    out, start = [], None
    vals = mask.values
    for i, v in enumerate(vals):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1)); start = None
    if start is not None:
        out.append((start, len(vals) - 1))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_ohlc()
    a = atr14(df)
    c = df.Close

    # ── 真值(后视):前向 20d 净位移 < 1×ATR ───────────────────────────────
    fwd = (c.shift(-20) - c).abs()
    truth_chop = (fwd < a).rename("truth")

    # ── 分类器(仅用过去数据)──────────────────────────────────────────────
    er20 = (c - c.shift(20)).abs() / c.diff().abs().rolling(20).sum()
    rng = (df.High.rolling(20).max() - df.Low.rolling(20).min()) / a
    ma20 = c.rolling(20).mean()
    slope = (ma20 - ma20.shift(5)).abs() / (5 * a)
    adx = adx14(df)

    frame = pd.DataFrame({"truth": truth_chop, "C1_ER20": er20, "C2_RangeATR": rng,
                          "C3_MA20slope": slope, "C4_ADX": adx}).loc["2000-01-01":].dropna()

    truth_segs = segments(frame["truth"])
    dwell = pd.Series([e - s + 1 for s, e in truth_segs])
    n_days = len(frame)
    print(f"样本 {n_days} TD ({frame.index[0].date()}→{frame.index[-1].date()}) | "
          f"真值 chop 日占比 {frame.truth.mean()*100:.1f}% | 转换(trend→chop)次数 {len(truth_segs)} "
          f"(~{len(truth_segs)/(n_days/252):.1f}/yr) | dwell median {dwell.median():.0f} TD "
          f"(p25 {dwell.quantile(.25):.0f} / p75 {dwell.quantile(.75):.0f})")

    rows = []
    for name in ("C1_ER20", "C2_RangeATR", "C3_MA20slope", "C4_ADX"):
        sig_chop = (frame[name] < frame[name].median())
        flips = (sig_chop != sig_chop.shift()).iloc[1:]
        flip_rate = flips.mean()
        # 5TD 回翻率:每次翻转后 5TD 内又翻回
        flip_idx = np.where(flips.values)[0] + 1
        rev5 = 0
        for i in flip_idx:
            seg_end = min(i + 5, len(sig_chop) - 1)
            if (sig_chop.iloc[i + 1:seg_end + 1] != sig_chop.iloc[i]).any():
                rev5 += 1
        rev5_rate = rev5 / max(len(flip_idx), 1)

        lags, misses = [], 0
        for s, e in truth_segs:
            det = None
            for i in range(s, e + 1):
                if sig_chop.iloc[i]:
                    det = i - s
                    break
            if det is None:
                misses += 1
            else:
                lags.append(det)
        lag_med = float(np.median(lags)) if lags else float("nan")
        window = float(dwell.median()) - lag_med if lags else float("nan")
        k1 = "DEAD" if (flip_rate > K1_FLIP or rev5_rate > K1_REV5) else "pass"
        k2 = "DEAD" if (not lags or window < K2_MIN_WINDOW) else "pass"
        rows.append({
            "classifier": name, "flip_rate_pct": round(flip_rate * 100, 2),
            "rev5_rate_pct": round(rev5_rate * 100, 1),
            "lag_median_td": lag_med, "miss_rate_pct": round(misses / len(truth_segs) * 100, 1),
            "dwell_median_td": float(dwell.median()),
            "race_window_td": round(window, 1) if window == window else None,
            "K1": k1, "K2": k2,
            "verdict": "SURVIVES" if (k1 == "pass" and k2 == "pass") else "DEAD",
        })
        r = rows[-1]
        print(f"{name:>14s} | flip {r['flip_rate_pct']:>5.2f}%/d rev5 {r['rev5_rate_pct']:>5.1f}% → K1 {k1:>4s}"
              f" | lag med {lag_med:>4.0f} TD miss {r['miss_rate_pct']:>4.1f}% window {r['race_window_td']} → K2 {k2:>4s}"
              f" | {r['verdict']}")

    pd.DataFrame(rows).to_csv(OUT / "q095_p2_race.csv", index=False)
    print(f"\nwrote {OUT/'q095_p2_race.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
