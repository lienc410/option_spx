"""SPEC-132.1 — Structure Map v2 蜡烛图叠加.

AC coverage:
  ohlc[] 与 runtime 缓存一致性                → ChartPayloadTests
  叠加物数值与 API 同一 response 同源         → ChartPayloadTests（s2 同函数、
                                               s4 线段外推 == row.s4_line、簇同源）
  零 CDN/外域请求（模板静态扫描 + vendor 在位）→ NoCdnTests
  badge 文案回归（132 三红线继承）             → test_spec_132.BadgeAuditTests（沿用）
                                               + UiWiringTests 图表元素扩展
  shadow 缺行 fail-soft（stale 照常渲染旧图）  → StaleFailSoftTests
  双主题渲染 wiring（theme token 桥 + 重绘）   → UiWiringTests

向量脚本生成（确定性 S4 构造 + seeded 随机游走）。
"""
from __future__ import annotations

import importlib
import json
import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import strategy.structure_map as sm
from tests.test_spec_132 import synth_chain, synth_ohlc

q090 = importlib.import_module("research.q090.q090_e1_fact_layer")
ROOT = Path(__file__).resolve().parents[1]
SPX_HTML = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")


def synth_ohlc_with_s4(n: int = 320) -> pd.DataFrame:
    """确定性 S4 构造：三个严格递减的孤立 swing high（LOOK 窗内），
    其余 bar 平坦 —— 锚点/线值可独立手算。"""
    close = np.full(n, 100.0)
    high = np.full(n, 100.0)
    low = np.full(n, 99.0)
    vol = np.full(n, 1e9)
    for i, h in ((220, 120.0), (260, 115.0), (300, 110.0)):
        high[i] = h
    idx = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"open": close, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


class _TmpPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self._orig = {k: getattr(sm, k) for k in
                      ("OHLC_CACHE", "RESEARCH_OHLC_CACHE", "SHADOW_PATH", "CHAIN_DIR")}
        sm.OHLC_CACHE = t / "runtime.json"
        sm.RESEARCH_OHLC_CACHE = t / "research.json"
        sm.SHADOW_PATH = t / "shadow.jsonl"
        sm.CHAIN_DIR = t / "chains"

    def tearDown(self) -> None:
        for k, v in self._orig.items():
            setattr(sm, k, v)

    def _seed(self, df: pd.DataFrame) -> None:
        hist = [{"date": d.date().isoformat(), "open": float(r.open),
                 "high": float(r.high), "low": float(r.low),
                 "close": float(r.close), "volume": float(r.volume)}
                for d, r in df.iterrows()]
        sm.RESEARCH_OHLC_CACHE.write_text(json.dumps({"history": hist}))


class ChartPayloadTests(_TmpPaths):
    def test_ohlc_matches_runtime_cache_tail(self) -> None:
        """AC: ohlc[] 与 runtime 缓存一致（近 120td，逐 bar 逐字段）。"""
        df = synth_ohlc()
        self._seed(df)
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            chart = sm.chart_payload(None)
        cache = json.loads(sm.OHLC_CACHE.read_text())["history"][-sm.CHART_LOOKBACK_TD:]
        self.assertEqual(len(chart["ohlc"]), sm.CHART_LOOKBACK_TD)
        for bar, src in zip(chart["ohlc"], cache):
            self.assertEqual(bar["time"], src["date"])
            for f in ("open", "high", "low", "close"):
                self.assertAlmostEqual(bar[f], round(src[f], 2), places=2)
        # volume 序列同源同长
        self.assertEqual([v["time"] for v in chart["volume"]],
                         [b["date"] for b in cache])

    def test_s2_coloring_same_function_as_q090(self) -> None:
        """AC 同源：volume[].s2 == q090.s2_flag（winner d2_v85，同一函数）。"""
        df = synth_ohlc()
        self._seed(df)
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            chart = sm.chart_payload(None)
        expected = q090.s2_flag(df["close"], df["volume"], **sm.S2_PARAMS)
        tail = expected.iloc[-sm.CHART_LOOKBACK_TD:]
        self.assertEqual([v["s2"] for v in chart["volume"]],
                         [bool(x) for x in tail])
        self.assertGreater(sum(v["s2"] for v in chart["volume"]), 0,
                           "向量应含至少一个 S2 日（否则测试无信息量）")
        # winner 切点与封账 CSV tag 锁定（S2_d2_v85）
        conf = pd.read_csv(ROOT / "research/q090/q090_e1_confirmation.csv")
        tag = dict(conf[["family", "signal"]].drop_duplicates().values)["S2"]
        _, d_tag, v_tag = tag.split("_")
        self.assertEqual(sm.S2_PARAMS["consecutive"], int(d_tag[1:]))
        self.assertEqual(sm.S2_PARAMS["threshold"], int(v_tag[1:]) / 100)

    def test_s4_segment_extrapolates_to_row_line_value(self) -> None:
        """AC 同源：s4_line_points 外推终点 == row.s4_line（同一 response 自洽）；
        锚点 == row.s4_anchors（trendline_anchors_at 同款选取）。"""
        df = synth_ohlc_with_s4()
        self._seed(df)
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            sm._ensure_runtime_ohlc()
            row = sm.build_daily_row(df.index[-1].date().isoformat())
            chart = sm.chart_payload(row)
        # 独立手算：spikes (220,120) (260,115) (300,110)；线过后两点
        slope = (110.0 - 115.0) / (300 - 260)
        exp_line = 110.0 + slope * (len(df) - 1 - 300)
        self.assertIsNotNone(row["s4_line"])
        self.assertAlmostEqual(row["s4_line"], round(exp_line, 2), places=2)
        self.assertEqual([a["bar_index"] for a in row["s4_anchors"]], [220, 260, 300])
        pts = chart["s4_line_points"]
        self.assertGreaterEqual(len(pts), 2)
        self.assertAlmostEqual(pts[-1]["value"], row["s4_line"], delta=0.5)
        self.assertEqual(pts[-1]["time"], df.index[-1].date().isoformat())

    def test_clusters_in_row_from_clusters_at(self) -> None:
        """row.s1r/s1s_clusters 与 q090.clusters_at 同源（最近 3 个，格式化）。"""
        df = synth_ohlc()
        self._seed(df)
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            sm._ensure_runtime_ohlc()
            flags = sm.compute_flags(sm.load_ohlc())
        hi = df["high"].to_numpy(); lo = df["low"].to_numpy()
        swing_hi, swing_lo = q090.find_swing_pivots(hi, lo)
        t = len(df) - 1
        raw = q090.clusters_at(t, np.where(swing_hi)[0], hi,
                               sm.S1R_PARAMS["band"], sm.S1R_PARAMS["touches"])
        exp_levels = sorted(round(c["level"], 2) for c in raw)
        got_levels = sorted(c["level"] for c in flags["s1r_clusters"])
        for lvl in got_levels:
            self.assertIn(lvl, exp_levels)
        self.assertLessEqual(len(flags["s1r_clusters"]), 3)

    def test_api_response_carries_chart_and_is_strict_json(self) -> None:
        df = synth_ohlc()
        self._seed(df)
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            sm._ensure_runtime_ohlc()
            spot = float(sm.load_ohlc()["close"].iloc[-1])
            p = sm.CHAIN_DIR / date.today().isoformat()
            p.mkdir(parents=True)
            synth_chain(spot, [("CALL", spot * 1.01, 5000, 30),
                               ("PUT", spot * 0.99, 4000, 30)]).to_parquet(p / "SPX.parquet")
            sm.append_shadow(sm.build_daily_row(date.today().isoformat()))
            from web.server import app
            res = app.test_client().get("/api/structure-map")
        self.assertEqual(res.status_code, 200)
        raw = res.get_data(as_text=True)
        json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(
            AssertionError(f"non-finite literal: {s}")))
        d = res.get_json()
        self.assertIsNotNone(d["chart"])
        self.assertEqual(len(d["chart"]["ohlc"]), sm.CHART_LOOKBACK_TD)


class StaleFailSoftTests(_TmpPaths):
    def test_stale_row_still_serves_chart(self) -> None:
        """AC: shadow 缺当日行 → stale=true 且 chart 照常（旧图 + stale 标注）。"""
        df = synth_ohlc()
        self._seed(df)
        old_day = (date.today() - timedelta(days=4)).isoformat()
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            sm._ensure_runtime_ohlc()
            sm.append_shadow(sm.build_daily_row(old_day))
            from web.server import app
            res = app.test_client().get("/api/structure-map")
        d = res.get_json()
        self.assertTrue(d["available"])
        self.assertTrue(d["stale"])
        self.assertIsNotNone(d["chart"])
        self.assertEqual(len(d["chart"]["ohlc"]), sm.CHART_LOOKBACK_TD)

    def test_chart_failure_fails_soft_to_v1_card(self) -> None:
        df = synth_ohlc()
        self._seed(df)
        with patch.object(sm, "refresh_ohlc_cache", return_value="x"):
            sm._ensure_runtime_ohlc()
            sm.append_shadow(sm.build_daily_row(date.today().isoformat()))
        with patch.object(sm, "chart_payload", side_effect=RuntimeError("boom")):
            from web.server import app
            res = app.test_client().get("/api/structure-map")
        d = res.get_json()
        self.assertTrue(d["available"])       # v1 数字卡数据照常
        self.assertIsNone(d["chart"])


class NoCdnTests(unittest.TestCase):
    def test_chart_lib_vendored_with_apache_license(self) -> None:
        lib = ROOT / "web" / "static" / "lightweight-charts.standalone.production.js"
        self.assertTrue(lib.exists(), "图表库必须 vendor 到 web/static/")
        head = lib.read_text(encoding="utf-8")[:600]
        self.assertIn("Apache License 2.0", head)
        self.assertIn("Lightweight Charts", head)
        self.assertTrue((ROOT / "web" / "static" / "lightweight-charts.LICENSE").exists())

    def test_template_has_zero_external_script_srcs(self) -> None:
        """AC 零 CDN/外域：spx.html 所有 <script src> 一律走本地 static。"""
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', SPX_HTML)
        self.assertGreater(len(srcs), 0)
        for s in srcs:
            self.assertIn("url_for('static'", s,
                          f"external script src forbidden: {s}")
        for cdn in ("unpkg.com", "jsdelivr", "cdnjs", "skypack", "esm.sh",
                    "cdn.tradingview", "lightweight-charts@"):
            self.assertNotIn(cdn, SPX_HTML)


class UiWiringTests(unittest.TestCase):
    def test_chart_wiring_present(self) -> None:
        for token in ("structure-chart", "renderStructureChart",
                      "LightweightCharts", "addCandlestickSeries",
                      "addHistogramSeries", "createPriceLine",
                      "s4_line_points", "fitContent"):
            self.assertIn(token, SPX_HTML)

    def test_theme_reactive_dual_palette(self) -> None:
        """双主题：颜色经 theme.js 桥读 theme.css token；themechange 重绘；
        teal（SPEC 指定、系统无 token）持 light/dark 双值。"""
        for token in ("structureChartColors", "themeColor('--green')",
                      "themeRgba('--gold'", "addEventListener('themechange'",
                      "data-theme"):
            self.assertIn(token, SPX_HTML)
        self.assertIn("'#0F8A7C' : '#2FB8A6'", SPX_HTML)   # teal light/dark

    def test_badge_red_lines_inherited_around_chart(self) -> None:
        """132 三红线继承：badge 词汇表在 v2 卡里仍在（图例携带）。"""
        for token in ("前瞻收集中 n=", "Q090 无验证边际，仅描述", "无裁决 · 重开 n=",
                      "structure-stale"):
            self.assertIn(token, SPX_HTML)


if __name__ == "__main__":
    unittest.main()
