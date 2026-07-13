"""SPEC-144 — Aftermath 页面可读性重构 + 展示层事实修正 acceptance tests.

AC map（task/SPEC-144.md §AC）:
  AC-1 单源：模板零阈值/腿参数硬编码（静态扫描）；payload 新字段各有测试；
       v3a_legs / sizing_note 与 selector 真值断言相等（防漂移）
                                              → SingleSourceTemplateTests /
                                                PayloadNewFieldsTests /
                                                AntiDriftTests
  AC-2 [35,40) reason 修正回归：VIX=37 → active=False 且 reason 指向
       extreme（不再误报 off-peak 不足）        → ReasonRegressionTests
  AC-3 三条件 checklist 逐条今日值+判定；ACTIVE / 非 ACTIVE 两态渲染
       （payload 断言 + 模板绑定断言——页面为 JS 渲染，遵循 SPEC-141
       AC-3 的模板静态断言先例）                → ChecklistTests
  AC-4 staging：active+读数三态显示正确（复用 SPEC-143 fixtures）；
       inactive 时 payload staging=null（只显静态规则）；评估失败
       fail-soft null 不破 payload              → StagingPayloadTests
  AC-5 --text-muted 扫描：两模板 muted 仅存于 .empty-msg 占位符规则
                                              → MutedScanTests
  AC-6 additive only：既有字段全保留、reason 字段语义不变、strict JSON
                                              → AdditiveContractTests
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from signals.iv_rank import IVSignal
from signals.trend import TrendSignal
from signals.vix_regime import Regime, Trend
from strategy.selector import (DEFAULT_PARAMS, AFTERMATH_LOOKBACK_DAYS,
                               AFTERMATH_OFF_PEAK_PCT,
                               AFTERMATH_PEAK_VIX_10D_MIN, StrategyName,
                               hv_size_rule, is_aftermath, select_strategy,
                               v3a_legs)
from tests.test_spec_064 import make_iv, make_trend, make_vix

TPL = REPO / "web" / "templates"
DASHBOARD = (TPL / "aftermath.html").read_text(encoding="utf-8")
BACKTEST = (TPL / "aftermath_backtest.html").read_text(encoding="utf-8")


def _payload(vix_snap, staging="off"):
    """构造 payload：get_current_snapshot 打桩；staging 默认打桩为 None
    （'off'），传 dict/None 则按值打桩，传 'real' 走真实现（调用方自行密闭）。"""
    import web.server as ws
    patches = [patch("signals.vix_regime.get_current_snapshot",
                     return_value=vix_snap)]
    if staging != "real":
        patches.append(patch.object(
            ws, "_aftermath_staging_snapshot",
            return_value=(None if staging == "off" else staging)))
    with patches[0]:
        if len(patches) > 1:
            with patches[1]:
                return ws.aftermath_state_payload()
        return ws.aftermath_state_payload()


def _active_snap(vix=27.0, peak=32.0):
    return make_vix(vix=vix, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                    vix_peak_10d=peak)


# ── AC-1 — 模板零硬编码（阈值/腿参数全 API 渲染） ────────────────────────────

class SingleSourceTemplateTests(unittest.TestCase):
    """AC-1 静态扫描：<style> 外零 28/35/40/45/0.90/delta 数字。"""

    BANNED = [r"\b28(\.0)?\b", r"\b35(\.0)?\b", r"\b40(\.0)?\b", r"\b45\b",
              r"0\.90", r"δ\s*0\.\d", r"\b0\.12\b", r"\b0\.04\b",
              r"\b0\.08\b", r"\b0\.16\b"]

    @staticmethod
    def _markup(src: str) -> str:
        return re.sub(r"<style>.*?</style>", "", src, flags=re.S)

    def test_dashboard_zero_hardcoded_thresholds_or_legs(self) -> None:
        body = self._markup(DASHBOARD)
        for tok in self.BANNED:
            self.assertIsNone(re.search(tok, body), tok)

    def test_dashboard_renders_from_api_fields(self) -> None:
        for field in ("conditions", "v3a_legs", "exit_rule_text", "exit_human",
                      "sizing_note", "staging_rule", "reason_human",
                      "label_human", "actual_text"):
            self.assertIn(field, DASHBOARD, field)
        self.assertIn("/api/aftermath/state", DASHBOARD)

    def test_backtest_discipline_dehardcoded(self) -> None:
        # 旧硬编码字面（含镜像行号）必须清零
        for stale in ("vix_peak_10d ≥ 28", "off_peak ≥ 10%", "vix &lt; 40",
                      "vix ≥ 40", "= 28.0", "= 0.10", "(line 295)",
                      "(line 178)", "60% credit profit target",
                      "BP target <code>14%", "HIGH_VOL <code>50%",
                      "DTE ≤ 21</code>"):
            self.assertNotIn(stale, BACKTEST, stale)
        # 改为 API 渲染锚点
        for anchor in ("disc-cond-peak", "disc-cond-offpeak",
                       "disc-cond-extreme", "disc-exit-human",
                       "disc-exit-rule", "disc-size", "disc-bp-target",
                       "disc-bp-ceiling", "fillDiscipline"):
            self.assertIn(anchor, BACKTEST, anchor)

    def test_no_line_number_mirrors_anywhere(self) -> None:
        for src, name in ((DASHBOARD, "aftermath.html"),
                          (BACKTEST, "aftermath_backtest.html")):
            self.assertIsNone(re.search(r"lines?\s*~?\d{2,}", src), name)


class PayloadNewFieldsTests(unittest.TestCase):
    """AC-1 payload 新字段逐个（真值 import，非复制数字）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.p = _payload(_active_snap())

    def test_thresholds_from_production_constants(self) -> None:
        self.assertEqual(self.p["threshold_peak_min"], AFTERMATH_PEAK_VIX_10D_MIN)
        self.assertEqual(self.p["threshold_off_peak_pct"], AFTERMATH_OFF_PEAK_PCT * 100)
        self.assertEqual(self.p["threshold_vix_max"], DEFAULT_PARAMS.extreme_vix)
        self.assertEqual(self.p["lookback_days"], AFTERMATH_LOOKBACK_DAYS)

    def test_v3a_legs_field_shape(self) -> None:
        legs = self.p["v3a_legs"]
        self.assertEqual(len(legs), 4)
        for leg in legs:
            self.assertEqual(set(leg), {"action", "option", "dte", "delta", "note"})
        self.assertEqual(self.p["strategy_key"], "iron_condor_hv")

    def test_exit_rule_text_verbatim_from_catalog(self) -> None:
        from strategy.catalog import strategy_descriptor
        self.assertEqual(self.p["exit_rule_text"],
                         strategy_descriptor("iron_condor_hv").roll_rule_text)

    def test_exit_human_numbers_from_params(self) -> None:
        self.assertIn(f"{int(DEFAULT_PARAMS.profit_target*100)}%", self.p["exit_human"])
        self.assertIn(str(DEFAULT_PARAMS.min_hold_days), self.p["exit_human"])
        self.assertIn(f"{DEFAULT_PARAMS.stop_mult:g}×", self.p["exit_human"])

    def test_sizing_note_and_sizing_dict(self) -> None:
        self.assertEqual(self.p["sizing_note"], hv_size_rule(DEFAULT_PARAMS))
        s = self.p["sizing"]
        self.assertEqual(s["high_vol_size"], DEFAULT_PARAMS.high_vol_size)
        self.assertEqual(s["bp_target_high_vol"], DEFAULT_PARAMS.bp_target_high_vol)
        self.assertEqual(s["bp_ceiling_high_vol"], DEFAULT_PARAMS.bp_ceiling_high_vol)
        self.assertEqual(s["profit_target"], DEFAULT_PARAMS.profit_target)
        self.assertEqual(s["min_hold_days"], DEFAULT_PARAMS.min_hold_days)
        self.assertEqual(s["stop_mult"], DEFAULT_PARAMS.stop_mult)

    def test_staging_rule_constants_from_module(self) -> None:
        import strategy.aftermath_staging as ams
        self.assertEqual(self.p["staging_rule"]["factor"], ams.Q101_STAGING_FACTOR)
        self.assertEqual(self.p["staging_rule"]["recheck_mult"],
                         ams.Q101_SLOPE_RECHECK_MULT)


class AntiDriftTests(unittest.TestCase):
    """AC-1 防漂移：payload 腿/仓位文本 == selector 实际推荐输出（逐字段）。"""

    def _aftermath_rec(self, trend):
        rec = select_strategy(_active_snap(), make_iv(signal=IVSignal.HIGH),
                              make_trend(trend), DEFAULT_PARAMS)
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertIn("aftermath", rec.rationale)
        return rec

    def test_payload_legs_equal_selector_recommendation_legs(self) -> None:
        p = _payload(_active_snap())
        for trend in (TrendSignal.BEARISH, TrendSignal.NEUTRAL):
            rec = self._aftermath_rec(trend)
            expected = [{"action": l.action, "option": l.option, "dte": l.dte,
                         "delta": l.delta, "note": l.note} for l in rec.legs]
            self.assertEqual(p["v3a_legs"], expected, trend)

    def test_payload_sizing_note_equal_selector_size_rule(self) -> None:
        p = _payload(_active_snap())
        for trend in (TrendSignal.BEARISH, TrendSignal.NEUTRAL):
            self.assertEqual(p["sizing_note"], self._aftermath_rec(trend).size_rule)

    def test_v3a_legs_helper_is_the_single_writer(self) -> None:
        """selector 内 V3-A 腿字面量只允许出现一次（v3a_legs 函数体）。"""
        src = (REPO / "strategy" / "selector.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("broken-wing tighter (V3-A)"), 1)
        self.assertEqual(src.count("legs=v3a_legs()"), 2)   # 两条 aftermath 分支


# ── AC-2 — [35,40) reason 修正回归 ───────────────────────────────────────────

class ReasonRegressionTests(unittest.TestCase):
    def test_vix_37_reports_extreme_not_offpeak(self) -> None:
        """VIX=37（peak 45，回落 17.8% ≥ 10%）：SPEC-118.1 后 active=False，
        修正前 reason 误报 insufficient_off_peak，修正后指向 extreme。"""
        snap = make_vix(vix=37.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                        vix_peak_10d=45.0)
        self.assertFalse(is_aftermath(snap))                 # 前提：真值不活跃
        p = _payload(snap)
        self.assertFalse(p["active"])
        self.assertTrue(p["reason"].startswith("vix_above_extreme"), p["reason"])
        self.assertNotIn("off_peak", p["reason"])
        self.assertIn(f"{DEFAULT_PARAMS.extreme_vix:.0f}", p["reason"])
        self.assertIn("极端线", p["reason_human"])

    def test_boundary_349_active_400_extreme(self) -> None:
        p = _payload(make_vix(vix=34.9, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                              vix_peak_10d=45.0))
        self.assertTrue(p["active"])
        self.assertIsNone(p["reason"])
        p = _payload(make_vix(vix=40.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                              vix_peak_10d=50.0))
        self.assertFalse(p["active"])
        self.assertTrue(p["reason"].startswith("vix_above_extreme"))

    def test_true_offpeak_case_still_reports_offpeak(self) -> None:
        # 回落只有 3.1%：reason 仍是 insufficient_off_peak（语义不变）
        p = _payload(make_vix(vix=31.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                              vix_peak_10d=32.0))
        self.assertFalse(p["active"])
        self.assertTrue(p["reason"].startswith("insufficient_off_peak"), p["reason"])
        self.assertIn("退潮", p["reason_human"])


# ── AC-3 — 三条件 checklist（payload 判定 + 模板绑定） ───────────────────────

class ChecklistTests(unittest.TestCase):
    def _conds(self, p):
        return {c["key"]: c for c in p["conditions"]}

    def test_active_state_all_conditions_met(self) -> None:
        p = _payload(_active_snap(vix=27.0, peak=32.0))
        self.assertTrue(p["active"])
        c = self._conds(p)
        self.assertEqual(set(c), {"peak", "off_peak", "below_extreme"})
        for key, cond in c.items():
            self.assertTrue(cond["met"], key)
            for f in ("label_human", "threshold", "actual", "actual_text"):
                self.assertIn(f, cond)
        self.assertEqual(c["peak"]["actual"], 32.0)
        self.assertIn("32.00", c["peak"]["actual_text"])
        self.assertAlmostEqual(c["off_peak"]["actual"], 15.62, places=2)
        self.assertEqual(c["below_extreme"]["actual"], 27.0)

    def test_inactive_state_failing_condition_marked(self) -> None:
        p = _payload(make_vix(vix=17.2, regime=Regime.NORMAL, trend=Trend.FLAT,
                              vix_peak_10d=17.2))
        self.assertFalse(p["active"])
        c = self._conds(p)
        self.assertFalse(c["peak"]["met"])                   # 无恐慌尖峰
        self.assertTrue(c["below_extreme"]["met"])
        self.assertIn("17.20", c["peak"]["actual_text"])

    def test_conditions_conjunction_equals_is_aftermath(self) -> None:
        """判定与 is_aftermath 真值逐快照一致（防装配层旁路重推漂移）。"""
        cases = [(27.0, 32.0), (37.0, 45.0), (34.9, 45.0), (17.2, 17.2),
                 (29.0, 30.0), (26.0, None)]
        for vix_v, peak in cases:
            snap = make_vix(vix=vix_v, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                            vix_peak_10d=peak)
            p = _payload(snap)
            met_all = all(c["met"] for c in p["conditions"])
            self.assertEqual(met_all, is_aftermath(snap), (vix_v, peak))
            self.assertEqual(p["active"], is_aftermath(snap), (vix_v, peak))

    def test_labels_carry_thresholds_from_constants(self) -> None:
        p = _payload(_active_snap())
        c = self._conds(p)
        self.assertIn(f"{AFTERMATH_PEAK_VIX_10D_MIN:.0f}", c["peak"]["label_human"])
        self.assertIn(f"{AFTERMATH_OFF_PEAK_PCT*100:.0f}%", c["off_peak"]["label_human"])
        self.assertIn(f"{DEFAULT_PARAMS.extreme_vix:.0f}",
                      c["below_extreme"]["label_human"])
        self.assertIn(str(AFTERMATH_LOOKBACK_DAYS), c["peak"]["label_human"])

    def test_template_renders_both_states_and_checklist(self) -> None:
        """模板绑定断言（JS 渲染页面的 DOM 断言先例：SPEC-141 AC-3）。"""
        # 两态 pill：SIGNAL / NO ENTRY（DESIGN.md 词表；WAIT 已废）
        self.assertIn("'SIGNAL' : 'NO ENTRY'", DASHBOARD)
        self.assertNotIn("'ACTIVE' : 'WAIT'", DASHBOARD)
        # 逐条渲染：label + 今日值 + ✓/✗ 判定，全部来自 conditions
        for token in ("d.conditions", "c.label_human", "c.actual_text",
                      "c.met ? '✓' : '✗'", "d.reason_human"):
            self.assertIn(token, DASHBOARD, token)
        # ACTIVE 后果注明（SPX 主推荐切换 + /spx 深链）
        self.assertIn('href="/spx"', DASHBOARD)
        self.assertIn("自动切到本结构", DASHBOARD)

    def test_five_question_order_in_template(self) -> None:
        markup = re.sub(r"<style>.*?</style>", "", DASHBOARD, flags=re.S)
        idx = [markup.index(f'card-title">{t}') for t in
               ("① 这是什么", "② 什么时候做", "③ 交易什么", "④ 多大仓位",
                "⑤ 什么时候退出", "Implementation Reference")]
        self.assertEqual(idx, sorted(idx))


# ── AC-4 — staging 三态 / inactive / fail-soft ───────────────────────────────

class StagingPayloadTests(unittest.TestCase):
    """复用 SPEC-143 fixtures（_window_vix_df / _skew_row / _StagingEnv）。"""

    def _real_staging_payload(self, monitor_rows):
        from tests.test_spec_143 import _StagingEnv, _window_vix_df
        vix_df, win_start = _window_vix_df()
        with tempfile.TemporaryDirectory() as tmp, \
                _StagingEnv(tmp, monitor_rows), \
                patch("signals.vix_regime.fetch_vix_history",
                      return_value=vix_df):
            return _payload(_active_snap(vix=28.0, peak=34.0),
                            staging="real"), win_start

    def test_three_states_render_through_payload(self) -> None:
        from strategy.decision_trace import q101_staging_label
        from tests.test_spec_143 import _skew_row, _window_vix_df
        _, win_start = _window_vix_df()
        cases = [(None, 1, 0.5), (1.0, 2, 1.0), (1.8, 3, 0.5)]
        for s, state, factor in cases:
            rows = None if s is None else [_skew_row(win_start, s)]
            p, _ = self._real_staging_payload(rows)
            st = p["staging"]
            self.assertIsNotNone(st, s)
            self.assertEqual(st["state"], state, s)
            self.assertEqual(st["factor"], factor, s)
            expected_label, expected_outcome = q101_staging_label(st)
            self.assertEqual(st["label_human"], expected_label)   # 逐字单源
            self.assertEqual(st["outcome"], expected_outcome)

    def test_inactive_payload_staging_null(self) -> None:
        p = _payload(make_vix(vix=17.2, regime=Regime.NORMAL, trend=Trend.FLAT,
                              vix_peak_10d=17.2), staging="real")
        self.assertIsNone(p["staging"])
        self.assertIn("staging_rule", p)                     # 静态规则仍在

    def test_evaluate_failure_fail_soft_null(self) -> None:
        with patch("strategy.aftermath_staging.evaluate_staging",
                   side_effect=RuntimeError("boom")):
            p = _payload(_active_snap(), staging="real")
        self.assertTrue(p["active"])
        self.assertIsNone(p["staging"])                      # 不破 payload

    def test_template_staging_bindings(self) -> None:
        # 实时三态整句 = API label_human（不许模板手写第二套三态文案——
        # tests/test_spec_143.py 另有全模板词面扫描）；inactive 只显静态规则
        for token in ("d.staging", "st.label_human", "staging_rule",
                      "d.active"):
            self.assertIn(token, DASHBOARD, token)
        self.assertIn("fail-soft", DASHBOARD)                # API 失败降级文案


# ── AC-5 — --text-muted 仅存占位符 ───────────────────────────────────────────

class MutedScanTests(unittest.TestCase):
    def test_muted_only_in_empty_msg_placeholder_rule(self) -> None:
        for src, name in ((DASHBOARD, "aftermath.html"),
                          (BACKTEST, "aftermath_backtest.html")):
            for i, line in enumerate(src.splitlines(), 1):
                if "--text-muted" not in line:
                    continue
                stripped = line.strip()
                if stripped.startswith(("/*", "*", "//")) or "占位" in line \
                        or "禁 --text-muted" in line:
                    continue                                  # 注释
                self.assertIn(".empty-msg", line,
                              f"{name}:{i}: {stripped[:90]}")

    def test_wait_pill_gone(self) -> None:
        self.assertNotIn("state-pill.wait", DASHBOARD)
        self.assertNotIn(">WAIT<", DASHBOARD)


# ── AC-6 — additive only（既有消费方零破坏） ─────────────────────────────────

class AdditiveContractTests(unittest.TestCase):
    LEGACY_FIELDS = {"active", "vix", "vix_peak_10d", "off_peak_pct",
                     "threshold_off_peak_pct", "threshold_peak_min",
                     "threshold_vix_max", "regime", "trend", "reason", "date"}

    def test_all_legacy_fields_present(self) -> None:
        p = _payload(_active_snap())
        self.assertTrue(self.LEGACY_FIELDS <= set(p), self.LEGACY_FIELDS - set(p))

    def test_reason_prefixes_unchanged(self) -> None:
        prefixes = {
            (17.2, 17.2): "peak_below_threshold",
            (31.0, 32.0): "insufficient_off_peak",
            (37.0, 45.0): "vix_above_extreme",
            (26.0, None): "no_peak_data",
        }
        for (v, peak), prefix in prefixes.items():
            p = _payload(make_vix(vix=v, regime=Regime.HIGH_VOL,
                                  trend=Trend.FLAT, vix_peak_10d=peak))
            self.assertTrue(p["reason"].startswith(prefix), (v, peak, p["reason"]))

    def test_api_route_strict_json(self) -> None:
        import web.server as ws
        snap = _active_snap()
        with patch("signals.vix_regime.get_current_snapshot", return_value=snap), \
             patch.object(ws, "_aftermath_staging_snapshot", return_value=None):
            res = ws.app.test_client().get("/api/aftermath/state")
        self.assertEqual(res.status_code, 200)
        raw = res.get_data(as_text=True)
        for bad in ("NaN", "Infinity"):
            self.assertNotIn(bad, raw)
        json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(
            AssertionError(s)))

    def test_both_pages_render_and_cache_buster_bumped(self) -> None:
        from web.server import app
        c = app.test_client()
        for route in ("/aftermath", "/aftermath/backtest"):
            self.assertEqual(c.get(route).status_code, 200, route)
        for src, name in ((DASHBOARD, "aftermath.html"),
                          (BACKTEST, "aftermath_backtest.html")):
            self.assertEqual(src.count("?v=spec144"), 3, name)
            self.assertNotIn("?v=spec108", src, name)
            self.assertNotIn("?v=spec141_1", src, name)
            self.assertIn("theme.css", src, name)            # 主题继续单源


if __name__ == "__main__":
    unittest.main()
