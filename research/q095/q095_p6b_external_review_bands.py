"""Q095 P6b — 外审（ChatGPT via PM, 2026-07-13）触发的逐笔分带检验。

外审条件表主张：预期 30d 大涨 → call vertical；预期企稳微涨 → BPS。
本脚本按实际 30d 前向收益分带复算 P6 逐笔数据（HAIRCUT 现实端），并检验
"BPS 赢组"是否存在入场日可观测的判别特征（事前可判性 = 条件表可执行性）。
结论：分带方向逐带成立（外审对 payoff 结构的刻画正确）；但条件变量 =
前向收益本身，入场日可观测特征（VIX/debit/铺垫型分层）均不能识别 BPS 赢组
——条件表是正确的地图，没有可用的罗盘。详见 findings 外审吸收节。
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

df = pd.read_csv(ROOT / 'research/q095/q095_p6_bps_sub.csv')
h = df[df.pricing == 'HAIRCUT'].copy()

spx = pd.read_pickle(ROOT / 'data/market_cache/yahoo__GSPC__max__1d.pkl')
idx = pd.to_datetime(spx.index)
spx.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
c = spx['Close']


def fwd(sig, td=21):
    i = c.index.searchsorted(pd.Timestamp(sig))
    j = min(i + 1 + td, len(c) - 1)
    return c.iloc[j] / c.iloc[i + 1] - 1


h['fwd30'] = [fwd(s) for s in h.signal]
h['bps_wins'] = h.bps_pnl > h.cs_pnl
h.to_csv(ROOT / 'research/q095/q095_p6b_bands.csv', index=False)

for lo, hi, lbl in [(None, 0, '<0%'), (0, .02, '0-2%'), (.02, .04, '2-4%'), (.04, None, '>4%')]:
    g = h[((h.fwd30 >= lo) if lo is not None else (h.fwd30 < hi))
          & ((h.fwd30 < hi) if hi is not None else (h.fwd30 >= lo))]
    print(f"{lbl:6s} n={len(g):2d} BPS赢{g.bps_wins.sum():2d} "
          f"CS ${g.cs_pnl.sum()/1000:+8.1f}k BPS ${g.bps_pnl.sum()/1000:+8.1f}k")
w, l = h[h.bps_wins], h[~h.bps_wins]
print(f"ex-ante 分离度: VIX {w.vix.median():.1f} vs {l.vix.median():.1f} | "
      f"BPS赢组 stratum {w.stratum.value_counts().to_dict()}")
