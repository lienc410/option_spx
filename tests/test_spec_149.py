"""SPEC-149 — open-draft 自定义 DTE/δ 扫描参数 acceptance tests.

AC map:
  AC-1 覆盖生效 — dte/delta 传入后 priced legs 按新参数重算（含方向正确性）
  AC-2 方向专属优先 — short_dte/long_dte 覆盖通用 dte（diagonal 长短腿分离）
  AC-3 校验 — 越界/非法值 400 且带可读原因（不静默夹取）
  AC-4 向后兼容 — 不传参数时 payload 与旧行为逐字段一致，无 draft_overrides
  AC-5 偏离基线不被污染 — 自定义扫描不改写 REC_BASELINE（UI 源锁）
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from web.server import app, _apply_leg_overrides, _parse_draft_overrides  # noqa: E402


def _bps_rec():
    """LOW_VOL/NORMAL + BULLISH → bull_put_spread（短腿 δ0.30 / 30 DTE）。"""
    from signals.iv_rank import IVSignal
    from signals.trend import TrendSignal
    from signals.vix_regime import Regime, Trend
    from strategy.selector import select_strategy
    from tests.test_strategy_unification import make_iv, make_trend, make_vix
    return select_strategy(
        make_vix(vix=18.0, regime=Regime.NORMAL, trend=Trend.FLAT),
        make_iv(signal=IVSignal.NEUTRAL, iv_rank=50.0, iv_percentile=50.0, vix=18.0),
        make_trend(signal=TrendSignal.BULLISH),
    )


def _draft(**params):
    """schwab 未配置 → 走模型腿（密闭，不打实盘链）。"""
    rec = _bps_rec()
    if rec.strategy_key == "reduce_wait" or not rec.legs:
        raise unittest.SkipTest(f"combo routed to {rec.strategy_key}")
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    with patch("strategy.selector.get_recommendation", return_value=rec), \
         patch("schwab.auth.is_configured", return_value=False):
        res = app.test_client().get("/api/position/open-draft" + (f"?{qs}" if qs else ""))
    return res


class TestAC1OverridesApply(unittest.TestCase):
    def test_dte_override_propagates_to_all_legs(self):
        base = _draft().get_json()
        out = _draft(dte=45).get_json()
        self.assertTrue(all(l["dte"] == 45 for l in out["legs"]))
        self.assertEqual(out["dte_at_entry"], 45)
        # rec 原值仍单列（UI 标注"已改"用），且确实不同于覆盖值
        self.assertTrue(all(l["rec_dte"] != 45 for l in out["legs"]))
        self.assertNotEqual(out["expiry"], base["expiry"])

    def test_short_delta_override_moves_strike_toward_spot(self):
        base = _draft().get_json()
        out = _draft(short_delta=0.40).get_json()
        short_leg = next(l for l in out["legs"] if l["action"] == "SELL")
        self.assertAlmostEqual(abs(float(short_leg["delta"])), 0.40, places=6)
        # 短 PUT：|δ| 越大越贴近现价 → 行权价升高
        self.assertEqual(short_leg["option"], "PUT")
        self.assertGreater(out["short_strike"], base["short_strike"])
        # 长腿未指定 → 保持目录值
        long_leg = next(l for l in out["legs"] if l["action"] == "BUY")
        self.assertEqual(long_leg["delta"], long_leg["rec_delta"])

    def test_uniform_delta_applies_to_both_sides(self):
        out = _draft(delta=0.25).get_json()
        for l in out["legs"]:
            self.assertAlmostEqual(abs(float(l["delta"])), 0.25, places=6)

    def test_overrides_echoed_and_flagged_in_hint(self):
        out = _draft(dte=45, short_delta=0.40).get_json()
        self.assertEqual(out["draft_overrides"], {"dte": 45, "short_delta": 0.40})
        self.assertIn("自定义参数扫描", out["legs_hint"])

    def test_bp_preview_recomputed_from_overridden_strikes(self):
        base = _draft().get_json()
        out = _draft(short_delta=0.40).get_json()
        # 宽度变了 → 每张 BP（≈max loss）必须跟着变，不能沿用旧值
        self.assertNotEqual(out["bp_preview"]["bp_per_contract"],
                            base["bp_preview"]["bp_per_contract"])


class TestAC2PerSidePrecedence(unittest.TestCase):
    def test_side_specific_beats_uniform(self):
        out = _draft(dte=45, short_dte=30).get_json()
        short_leg = next(l for l in out["legs"] if l["action"] == "SELL")
        long_leg = next(l for l in out["legs"] if l["action"] == "BUY")
        self.assertEqual(short_leg["dte"], 30)   # 专属值赢
        self.assertEqual(long_leg["dte"], 45)    # 通用值兜底

    def test_helper_precedence_unit(self):
        class _Leg:
            action, dte, delta = "SELL", 30, 0.30
        ov = _parse_draft_overrides({"dte": "45", "short_dte": "21",
                                     "delta": "0.20", "short_delta": "0.35"})
        self.assertEqual(_apply_leg_overrides(_Leg(), ov), (21, 0.35))

        class _Long(_Leg):
            action, dte, delta = "BUY", 30, 0.15
        self.assertEqual(_apply_leg_overrides(_Long(), ov), (45, 0.20))

    def test_helper_defaults_to_catalog_when_absent(self):
        class _Leg:
            action, dte, delta = "SELL", 30, 0.30
        ov = _parse_draft_overrides({})
        self.assertFalse(ov["active"])
        self.assertEqual(_apply_leg_overrides(_Leg(), ov), (30, 0.30))


class TestAC3Validation(unittest.TestCase):
    def test_out_of_range_rejected_loudly(self):
        for params in ({"dte": 0}, {"dte": 400}, {"short_delta": 0},
                       {"long_delta": 1.5}, {"dte": "abc"}, {"short_delta": "x"}):
            res = _draft(**params)
            self.assertEqual(res.status_code, 400, params)
            self.assertIn("error", res.get_json())

    def test_boundary_values_accepted(self):
        self.assertEqual(_draft(dte=1).status_code, 200)
        self.assertEqual(_draft(dte=365).status_code, 200)
        self.assertEqual(_draft(short_delta=0.95).status_code, 200)

    def test_negative_delta_normalized_to_abs(self):
        out = _draft(short_delta=-0.40).get_json()
        short_leg = next(l for l in out["legs"] if l["action"] == "SELL")
        self.assertAlmostEqual(abs(float(short_leg["delta"])), 0.40, places=6)


class TestAC4BackwardCompat(unittest.TestCase):
    def test_no_params_leaves_payload_unchanged(self):
        out = _draft().get_json()
        self.assertNotIn("draft_overrides", out)
        self.assertNotIn("自定义参数扫描", out["legs_hint"])
        # 腿仍按目录参数（覆盖值 == rec 原值）
        for l in out["legs"]:
            self.assertEqual(l["dte"], l["rec_dte"])
            self.assertEqual(l["delta"], l["rec_delta"])

    def test_empty_string_params_are_ignored(self):
        """前端留空格子会发 ?dte=&short_delta= —— 必须等同未传。"""
        res = _draft(dte="", short_delta="", long_dte="")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("draft_overrides", res.get_json())


class TestAC5UiSourceLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (REPO / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def test_scan_param_inputs_and_actions_wired(self):
        for token in ("scan-dte", "scan-short-delta", "scan-long-delta",
                      "scan-short-dte", "scan-long-dte", "SCAN_PARAM_FIELDS",
                      "collectScanOverrides", "rescanOpenDraft",
                      "resetScanOverrides", ">Re-scan<", ">Reset<"):
            self.assertIn(token, self.spx, token)

    def test_buttons_are_english_chrome(self):
        """DESIGN.md 双语规则：按钮属 chrome → 英文（中文只走叙事/提示）。
        SPEC-125 D9 已有全站断言，这里对本区块再上一道本地锁。"""
        import re
        block = self.spx[self.spx.index('class="scan-params"'):]
        block = block[:block.index("</div>\n          <div class=\"modal-hint\"")]
        self.assertEqual(re.findall(r"<button[^>]*>[^<]*[一-鿿][^<]*</button>", block), [])

    def test_baseline_not_clobbered_by_custom_scan(self):
        """SPEC-129 偏离基线必须一直锚在当日推荐上（否则自定义腿变成自己的
        参照物，偏离永远记不到）。"""
        self.assertIn("if (!draft.draft_overrides) {", self.spx)

    def test_strategy_switch_clears_overrides(self):
        self.assertIn("clearScanOverrideInputs();", self.spx)


if __name__ == "__main__":
    unittest.main()
