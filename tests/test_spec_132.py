"""SPEC-132 — 市场结构地图：可视化 + shadow 证据流共管道.

AC coverage:
  flag 计算与 q090_e1 同函数 import + 样本日 bit-identical → BitIdenticalTests
  badge 文案与 Q090 verdict 对齐（内容审计）              → BadgeAuditTests
  JSONL strict-JSON                                       → ShadowRowTests
  链快照缺失 fail-soft（stale 日期）                       → ShadowRowTests
  心跳注册（SPEC-117 registry）+ plist                     → OpsWiringTests
  winner 切点与 q090 封账 CSV 锁定                         → WinnerParamsLockTests
  墙聚合/S3 边界 + n 进度计数                              → WallsAndProgressTests

测试向量脚本生成（seeded RNG 合成 OHLC/chain；真实 battery 缓存做 bit-identical）。
"""
from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import strategy.structure_map as sm

q090 = importlib.import_module("research.q090.q090_e1_fact_layer")

ROOT = Path(__file__).resolve().parents[1]


def synth_ohlc(n: int = 320, seed: int = 132) -> pd.DataFrame:
    """合成 OHLCV（随机游走 + 波动，量含 20d 结构）。"""
    rng = np.random.default_rng(seed)
    close = 6000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    spread = np.abs(rng.normal(0, 0.006, n)) + 0.002
    high = close * (1 + spread)
    low = close * (1 - spread)
    open_ = low + (high - low) * rng.uniform(0.2, 0.8, n)
    vol = rng.uniform(3e9, 6e9, n)
    idx = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


class BitIdenticalTests(unittest.TestCase):
    """flag 谓词（生产 compute_flags 用的 cluster_flag_at / trendline_state_at）
    与 q090 series 构造逐日一致——先在合成数据上全窗口断言，再在真实 battery
    缓存尾窗上断言（同一数据、同款函数、零旁路）。"""

    def _assert_predicate_matches_series(self, df: pd.DataFrame, sample_last: int) -> None:
        hi = df["high"].to_numpy(); lo = df["low"].to_numpy(); cl = df["close"].to_numpy()
        swing_hi, swing_lo = q090.find_swing_pivots(hi, lo)
        hi_idx = np.where(swing_hi)[0]; lo_idx = np.where(swing_lo)[0]
        n = len(cl)
        series = {
            "s1r": q090.cluster_flag(hi_idx, hi, cl, df.index, side="r", **sm.S1R_PARAMS),
            "s1s": q090.cluster_flag(lo_idx, lo, cl, df.index, side="s", **sm.S1S_PARAMS),
            "s4": q090.trendline_flag(hi_idx, hi, cl, df.index,
                                      sm.S4_PARAMS["n_highs"], sm.S4_PARAMS["prox"]),
        }
        for t in range(n - sample_last, n):
            flags = sm.compute_flags(df, t=t)
            self.assertEqual(flags["s1r_flag"], bool(series["s1r"].iloc[t]), f"s1r@{t}")
            self.assertEqual(flags["s1s_flag"], bool(series["s1s"].iloc[t]), f"s1s@{t}")
            self.assertEqual(flags["s4_flag"], bool(series["s4"].iloc[t]), f"s4@{t}")
            vr = q090.volume_ratio(df["volume"]).iloc[t]
            if flags["vol_ratio"] is not None:
                self.assertAlmostEqual(flags["vol_ratio"], float(vr), places=3)

    def test_synthetic_full_window(self) -> None:
        df = synth_ohlc()
        self._assert_predicate_matches_series(df, sample_last=60)

    def test_real_battery_cache_sample_days(self) -> None:
        """样本日 bit-identical（AC 措辞）：真实 q085/q090 数据文件尾窗。"""
        cache = ROOT / "data" / "q085_spx_ohlc_cache.json"
        d = json.loads(cache.read_text())
        df = pd.DataFrame(d["history"][-420:])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        self._assert_predicate_matches_series(df, sample_last=15)


class WinnerParamsLockTests(unittest.TestCase):
    def test_params_match_q090_sealed_winner_tags(self) -> None:
        """生产切点必须与 q090 封账 confirmation CSV 的 winner tag 逐项一致。"""
        conf = pd.read_csv(ROOT / "research" / "q090" / "q090_e1_confirmation.csv")
        tags = dict(conf[["family", "signal"]].drop_duplicates().values)

        def parse(tag: str) -> dict:
            parts = tag.split("_")   # e.g. S1r_b3_t3_p10
            return {"band": int(parts[1][1:]) / 1e3,
                    "touches": int(parts[2][1:]),
                    "prox": int(parts[3][1:]) / 1e3}

        s1r = parse(tags["S1r"])
        self.assertEqual(sm.S1R_PARAMS, s1r)
        s1s = parse(tags["S1s"])
        self.assertEqual(sm.S1S_PARAMS, s1s)
        s4_parts = tags["S4"].split("_")   # S4_n3_p10
        self.assertEqual(sm.S4_PARAMS["n_highs"], int(s4_parts[1][1:]))
        self.assertEqual(sm.S4_PARAMS["prox"], int(s4_parts[2][1:]) / 1e3)


def synth_chain(spot: float, walls: list[tuple[str, float, int, int]]) -> pd.DataFrame:
    """rows: (option_type, strike, oi, dte)."""
    rows = [{"option_type": ot, "strike": k, "open_interest": oi, "dte": dte}
            for ot, k, oi, dte in walls]
    return pd.DataFrame(rows)


class WallsAndProgressTests(unittest.TestCase):
    def test_top_walls_and_s3_boundary(self) -> None:
        spot = 7500.0
        chain = synth_chain(spot, [
            ("CALL", 7600, 9000, 30), ("CALL", 7550, 8000, 30),
            ("CALL", 7700, 7000, 30), ("CALL", 7800, 100, 30),
            ("CALL", 7900, 50000, 60),           # dte>45 → 排除
            ("PUT", 7400, 6000, 30), ("PUT", 7300, 5000, 30),
            ("PUT", 7200, 4000, 30), ("PUT", 7100, 10, 30),
        ])
        w = sm.top_walls(chain, spot)
        self.assertEqual([x["strike"] for x in w["calls"]], [7600, 7550, 7700])
        self.assertEqual([x["strike"] for x in w["puts"]], [7400, 7300, 7200])
        self.assertEqual(w["s3_top2"], [7600.0, 7550.0])
        self.assertFalse(w["s3_flag"])           # 最近 top2 墙 7550 距 0.67%
        # spot 贴近 top2 墙 < 0.5% → 触发；边界外 → 不触发
        self.assertTrue(sm.top_walls(chain, 7550 * (1 + 0.0049))["s3_flag"])
        self.assertFalse(sm.top_walls(chain, 7600 * (1 + 0.0051))["s3_flag"])

    def test_progress_counts(self) -> None:
        rows = ([{"date": f"d{i}", "s3_flag": True, "s1s_flag": False} for i in range(4)]
                + [{"date": f"e{i}", "s3_flag": False, "s1s_flag": True} for i in range(7)]
                + [{"date": "x", "chain_missing": True}])
        p = sm.progress(rows)
        self.assertEqual(p["days_logged"], 12)
        self.assertEqual(p["s3_n"], 4)
        self.assertEqual(p["s1s_n"], 7)
        self.assertEqual(p["s3_target"], 60)
        self.assertEqual(p["s1s_target"], 100)


class ShadowRowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self._orig = {k: getattr(sm, k) for k in
                      ("OHLC_CACHE", "RESEARCH_OHLC_CACHE", "SHADOW_PATH", "CHAIN_DIR")}
        sm.OHLC_CACHE = t / "ohlc_runtime.json"
        sm.RESEARCH_OHLC_CACHE = t / "ohlc_research.json"
        sm.SHADOW_PATH = t / "shadow.jsonl"
        sm.CHAIN_DIR = t / "chains"
        df = synth_ohlc()
        hist = [{"date": d.date().isoformat(), "open": float(r.open), "high": float(r.high),
                 "low": float(r.low), "close": float(r.close), "volume": float(r.volume)}
                for d, r in df.iterrows()]
        sm.RESEARCH_OHLC_CACHE.write_text(json.dumps({"history": hist}))
        self.today = date.today().isoformat()

    def tearDown(self) -> None:
        for k, v in self._orig.items():
            setattr(sm, k, v)

    def _write_chain(self, day: str, spot: float) -> None:
        p = sm.CHAIN_DIR / day
        p.mkdir(parents=True, exist_ok=True)
        synth_chain(spot, [("CALL", spot * 1.01, 5000, 30),
                           ("PUT", spot * 0.99, 4000, 30)]).to_parquet(p / "SPX.parquet")

    def test_row_is_strict_json_and_idempotent(self) -> None:
        with patch.object(sm, "refresh_ohlc_cache", return_value="2026-01-01"):
            sm._ensure_runtime_ohlc()
            spot = float(sm.load_ohlc()["close"].iloc[-1])
            self._write_chain(self.today, spot)
            row = sm.build_daily_row(self.today)
        # strict-JSON：NaN/Inf 字面量必须不存在
        text = json.dumps(row)
        def _bad(s):
            raise AssertionError(f"non-finite literal: {s}")
        json.loads(text, parse_constant=_bad)
        self.assertNotIn("chain_missing", row)
        self.assertEqual(row["chain_asof"], self.today)
        self.assertTrue(row["walls"]["calls"])
        # 幂等
        self.assertTrue(sm.append_shadow(row))
        self.assertFalse(sm.append_shadow(row))
        self.assertEqual(len(sm.read_shadow()), 1)

    def test_chain_missing_fails_soft_with_stale_date(self) -> None:
        stale_day = (date.today() - timedelta(days=3)).isoformat()
        with patch.object(sm, "refresh_ohlc_cache", return_value="2026-01-01"):
            sm._ensure_runtime_ohlc()
            spot = float(sm.load_ohlc()["close"].iloc[-1])
            self._write_chain(stale_day, spot)       # 只有旧链
            row = sm.build_daily_row(self.today)
        self.assertTrue(row["chain_missing"])
        self.assertEqual(row["chain_asof"], stale_day)   # 卡片显示 stale 日期
        self.assertNotIn("walls", row)
        self.assertNotIn("s3_flag", row)                 # 无链日不计 S3 n
        # flags（OHLC 侧）照常计算
        self.assertIn("s1r_flag", row)
        self.assertTrue(sm.append_shadow(row))           # 行照写（心跳新鲜度成立）

    def test_finite_assert_rejects_inf(self) -> None:
        with self.assertRaises(ValueError):
            sm._assert_finite({"x": float("inf")})

    def test_api_structure_map_serves_row_and_progress(self) -> None:
        with patch.object(sm, "refresh_ohlc_cache", return_value="2026-01-01"):
            sm._ensure_runtime_ohlc()
            spot = float(sm.load_ohlc()["close"].iloc[-1])
            self._write_chain(self.today, spot)
            sm.append_shadow(sm.build_daily_row(self.today))
        from web.server import app
        res = app.test_client().get("/api/structure-map")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["available"])
        self.assertFalse(data["stale"])
        self.assertIn("progress", data)
        for bad in ("NaN", "Infinity"):
            self.assertNotIn(bad, res.get_data(as_text=True))


class BadgeAuditTests(unittest.TestCase):
    """Badge 文案与 Q090 verdict 对齐（SPEC-132 强制词汇表，内容审计项）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def test_badge_vocabulary_present(self) -> None:
        # 墙 = OPEN（前瞻收集中 n/60）；簇/线/量 = Q090 无验证边际，仅描述；
        # S1s 额外携带 无裁决 + 重开 n/100
        for token in ("前瞻收集中 n=", "Q090 无验证边际，仅描述", "无裁决 · 重开 n="):
            self.assertIn(token, self.spx)

    def test_walls_first_class_and_footnotes_muted(self) -> None:
        # 墙一等公民（walls-grid 主区）；簇/线/量走 footnote 区
        for token in ("walls-grid", "structure-footnotes", "Call Walls", "Put Walls"):
            self.assertIn(token, self.spx)

    def test_no_text_muted_in_structure_block(self) -> None:
        i = self.spx.find(".structure-card")
        j = self.spx.find(".structure-fn strong")
        block = self.spx[i:j + 200]
        self.assertNotIn("--text-muted", block)

    def test_no_push_no_engine_coupling(self) -> None:
        """边界：structure map 不进 gateway 推送、不进 selector。"""
        import inspect
        for mod_name in ("strategy.structure_map", "production.q090_structure_shadow"):
            src = inspect.getsource(importlib.import_module(mod_name))
            for token in ("from notify", "import notify", "gw_push", "apush(",
                          "event_push"):
                self.assertNotIn(token, src, f"{mod_name} 不得触推送通道")
        import strategy.selector as sel
        self.assertNotIn("structure_map", inspect.getsource(sel))


class OpsWiringTests(unittest.TestCase):
    def test_heartbeat_registry_has_job_with_freshness(self) -> None:
        reg = json.loads((ROOT / "ops" / "heartbeat_registry.json").read_text())
        entry = next((j for j in reg["jobs"]
                      if j["label"] == "com.spxstrat.q090_structure"), None)
        self.assertIsNotNone(entry, "SPEC-117: new job must be registered")
        self.assertEqual(entry["freshness"]["path"], "data/q090_structure_shadow.jsonl")
        self.assertEqual(entry["freshness"]["rule"], "trading_day")

    def test_plist_tracked_and_runs_job_without_push_env(self) -> None:
        import plistlib
        p = ROOT / "com.spxstrat.q090_structure.plist"
        self.assertTrue(p.exists())
        d = plistlib.loads(p.read_bytes())
        self.assertIn("production.q090_structure_shadow", d["ProgramArguments"])
        # SPEC-132 边界：本 job 零推送 → 不授予 SPX_PUSH_ENABLE
        self.assertNotIn("SPX_PUSH_ENABLE", d.get("EnvironmentVariables", {}))


if __name__ == "__main__":
    unittest.main()
