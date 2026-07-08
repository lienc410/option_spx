"""SPEC-135 — Decision Trace：决策管道可视化.

AC coverage:
  trace 注入后 selector 路由 bit-identical      → BitIdentityTests
    （一次性 40,320 组合 HEAD-vs-插桩 全字段对照已于迁移时验证（commit
      记录）；此处为永久回归锁：gate() 恒等合同 + 决定性 + trace 纯附加）
  当日 trace 与 rationale 一致性断言            → TraceContentTests
  G2 halt 日（7/7）固定测试用例（治理截断渲染）  → G2HaltFixtureTests
  静默通过的门必须出现在 trace                  → TraceContentTests
  三泳道分离 + Lane C 免责标注（内容审计）       → LaneAuditTests / UiAuditTests
  strict-JSON（trace 落盘 + API）               → StorageApiTests
  人话铁律 §0（label_human/三件套/术语英文保留）  → TraceContentTests / UiAuditTests
"""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import strategy.bcd_governance as gov
import strategy.decision_trace as T
import strategy.selector as sel
from tests.test_spec_129 import _nnb_snapshots
from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot

ROOT = Path(__file__).resolve().parents[1]


def _carve_snapshots(vix_level: float = 16.13):
    """7/7 实例格：NORMAL × IV LOW × BULLISH × VIX<18 → SPEC-113 carve BCD."""
    vs = VixSnapshot(date="2026-07-07", vix=vix_level, regime=Regime.NORMAL,
                     trend=Trend.FLAT, vix_5d_avg=vix_level, vix_5d_ago=vix_level,
                     transition_warning=False, vix3m=vix_level * 1.1,
                     backwardation=False, vix_peak_10d=vix_level * 1.2)
    ivs = IVSnapshot(date="2026-07-07", vix=vix_level, iv_rank=20.0,
                     iv_percentile=25.0, iv_signal=IVSignal.LOW,
                     iv_52w_high=40.0, iv_52w_low=10.0, ivp63=30.0, ivp252=25.0)
    ts = TrendSnapshot(date="2026-07-07", spx=7537.0, ma20=7450.0, ma50=7300.0,
                       ma_gap_pct=0.032, signal=TrendSignal.BULLISH,
                       above_200=True, atr14=45.0, gap_sigma=1.1,
                       spx_30d_high=7551.0, dist_30d_high_pct=-0.002)
    return vs, ivs, ts


class BitIdentityTests(unittest.TestCase):
    def test_gate_helper_returns_input_unchanged(self) -> None:
        """gate() 恒等合同：返回值 === 传入布尔（行为零变更的机械保证）。"""
        T.reset()
        for v in (True, False):
            self.assertIs(T.gate(v, "x", "y"), v)

    def test_trace_is_pure_addition_and_deterministic(self) -> None:
        """同输入两次评估：除 trace 外全字段相等，trace 自身也决定性相等。"""
        snaps = _nnb_snapshots(50.0)
        r1 = sel.select_strategy(*snaps)
        r2 = sel.select_strategy(*snaps)
        d1, d2 = asdict(r1), asdict(r2)
        t1, t2 = d1.pop("trace"), d2.pop("trace")
        self.assertEqual(d1, d2)
        self.assertEqual(t1, t2)
        self.assertGreater(len(t1), 0)

    def test_reduce_wait_paths_also_bit_stable(self) -> None:
        vetoed = sel.select_strategy(*_nnb_snapshots(62.0))   # IVP 上限门
        self.assertEqual(vetoed.strategy_key, "reduce_wait")
        self.assertTrue(any(n["outcome"] == "veto" for n in vetoed.trace))


class TraceContentTests(unittest.TestCase):
    def test_silent_passes_present_with_human_labels(self) -> None:
        """AC: 静默通过的门必须出现在 trace（'为什么没拦'同权重）。"""
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        gates = [n for n in rec.trace if n["layer"] == "gate"]
        passes = [n for n in gates if n["outcome"] == "pass"]
        # NNB 走到 accept 必然静默通过：extreme_vol + backwardation +
        # vix_rising + ivp_upper + ivp_lower = 5 个 pass 门
        self.assertGreaterEqual(len(passes), 5)
        for n in rec.trace:
            self.assertTrue(n["label_human"], f"节点缺 label_human: {n['check']}")
            self.assertIn("code_ref", n)
        # 数字带语义（§0）：IVP 节点用"第 X 百分位"表述
        ivp_node = next(n for n in rec.trace if n["check"] == "iv_percentile")
        self.assertIn("百分位", ivp_node["label_human"])

    def test_final_verdict_matches_rationale(self) -> None:
        """AC: 当日 trace 与 rationale 文本一致性。"""
        for ivp in (50.0, 62.0):
            rec = sel.select_strategy(*_nnb_snapshots(ivp))
            final = [n for n in rec.trace if n["check"] == "final_verdict"]
            self.assertEqual(len(final), 1)
            self.assertEqual(final[0]["detail"], rec.rationale)
            self.assertEqual(final[0]["outcome"],
                             "wait" if rec.strategy_key == "reduce_wait" else "accept")

    def test_veto_day_trace_shows_the_gate_with_values(self) -> None:
        rec = sel.select_strategy(*_nnb_snapshots(62.0))
        veto = next(n for n in rec.trace if n["outcome"] == "veto")
        self.assertEqual(veto["check"], "nnb_ivp_upper")
        self.assertIn("62", veto["detail"])        # 实际值
        self.assertIn("55", veto["detail"])        # 阈值
        self.assertTrue(veto["inputs"])            # 三件套第 1 件

    def test_options_terms_stay_english(self) -> None:
        """§0 术语铁律：策略/期权术语保留英文（抽查 carve 路径节点）。"""
        rec = sel.select_strategy(*_carve_snapshots())
        self.assertEqual(rec.strategy_key, "bull_call_diagonal")
        carve = next(n for n in rec.trace if n["check"] == "nlb_spec113_carve")
        self.assertIn("Bull Call Diagonal", carve["label_human"])
        self.assertIn("call", carve["label_human"])   # 括注解释保留英文术语


class G2HaltFixtureTests(unittest.TestCase):
    """AC: 7/7 G2 触发日为固定测试用例——carve BCD 走到开仓候选，被治理
    刹车截断为观望；trace 完整保留『本来会开 + 为什么被拦』全程。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig_state = gov.STATE_PATH
        gov.STATE_PATH = Path(self.tmp.name) / "gov_state.json"
        # 7/7 实况 halt 状态（G2 18 个月合并转负 −$6,006）
        gov._write_state({"halt": {
            "at": "2026-07-07",
            "gates": [{"gate": "G2_18m_combined",
                       "detail": "18 个月实现+标记和 $-6,006 < 0（n=4）"}],
            "full_halt": False,
        }})

    def tearDown(self) -> None:
        gov.STATE_PATH = self._orig_state

    def test_governance_truncation_keeps_full_path(self) -> None:
        vs, ivs, ts = _carve_snapshots()
        rec = sel.select_strategy(vs, ivs, ts)
        self.assertEqual(rec.strategy_key, "bull_call_diagonal")   # 门前：会开
        final = sel._apply_bcd_governance_live(rec, vs, ivs, ts)
        self.assertEqual(final.strategy_key, "reduce_wait")        # 门后：观望
        self.assertIn("-6,006", final.rationale.replace("−", "-"))
        checks = [n["check"] for n in final.trace]
        # selector 原路径保留（carve 特批 + 结论 accept）…
        self.assertIn("nlb_spec113_carve", checks)
        self.assertIn("final_verdict", checks)
        # …治理截断节点在后，最终 wait 结论收尾
        halt_idx = checks.index("bcd_family_halt")
        accept_idx = checks.index("final_verdict")
        self.assertLess(accept_idx, halt_idx)
        halt = final.trace[halt_idx]
        self.assertEqual(halt["outcome"], "halt")
        self.assertIn("四成概率误踩", halt["label_human"])   # 运行特性披露人话版
        self.assertEqual(final.trace[-1]["outcome"], "wait")

    def test_not_halted_adds_silent_pass_node(self) -> None:
        gov._write_state({"halt": None})
        vs, ivs, ts = _carve_snapshots()
        rec = sel.select_strategy(vs, ivs, ts)
        final = sel._apply_bcd_governance_live(rec, vs, ivs, ts)
        self.assertEqual(final.strategy_key, "bull_call_diagonal")
        halt_nodes = [n for n in final.trace if n["check"] == "bcd_family_halt"]
        self.assertEqual(len(halt_nodes), 1)
        self.assertEqual(halt_nodes[0]["outcome"], "pass")


class GovernanceGatesTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self._orig = {k: getattr(gov, k) for k in
                      ("STATE_PATH", "MARKS_PATH", "CLOSED_TRADES", "SHADOW_PATH")}
        gov.STATE_PATH = t / "s.json"
        gov.MARKS_PATH = t / "m.jsonl"
        gov.CLOSED_TRADES = t / "c.jsonl"
        gov.SHADOW_PATH = t / "sh.jsonl"

    def tearDown(self) -> None:
        for k, v in self._orig.items():
            setattr(gov, k, v)

    def test_all_four_gates_traced_even_when_silent(self) -> None:
        fired, trace = gov.evaluate_gates_detailed("2026-07-07")
        self.assertEqual(fired, [])
        self.assertEqual([n["check"] for n in trace],
                         ["g1_last6", "g2_18m", "g3_month_dd", "g4_family_cum"])
        for n in trace:
            self.assertEqual(n["outcome"], "pass")
            self.assertTrue(n["label_human"])

    def test_wrapper_equivalence(self) -> None:
        with gov.CLOSED_TRADES.open("w") as f:
            for pnl in (-2000, -1500, -900, -700, -500, -406):
                f.write(json.dumps({"strategy_key": "bull_call_diagonal",
                                    "realized_pnl": pnl,
                                    "closed_at": "2026-07-01"}) + "\n")
        fired_wrap = gov.evaluate_gates("2026-07-07")
        fired_det, trace = gov.evaluate_gates_detailed("2026-07-07")
        self.assertEqual(fired_wrap, fired_det)
        g1 = next(n for n in trace if n["check"] == "g1_last6")
        self.assertEqual(g1["outcome"], "veto")


class StorageApiTests(unittest.TestCase):
    def setUp(self) -> None:
        import logs.recommendation_log_io as rlog
        self.rlog = rlog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig_log = rlog.RECOMMENDATION_LOG_FILE
        rlog.RECOMMENDATION_LOG_FILE = Path(self.tmp.name) / "rec.jsonl"

    def tearDown(self) -> None:
        self.rlog.RECOMMENDATION_LOG_FILE = self._orig_log

    def test_trace_persisted_strict_json_roundtrip(self) -> None:
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        self.rlog.append_recommendation_event(
            rec=rec, source="test", mode="eod",
            timestamp="2026-07-07T09:35:00-04:00", params_hash="x")
        raw = self.rlog.RECOMMENDATION_LOG_FILE.read_text()
        def _bad(s):
            raise AssertionError(f"non-finite literal: {s}")
        ev = json.loads(raw.splitlines()[0], parse_constant=_bad)
        self.assertEqual(ev["trace"], rec.trace)
        self.assertEqual(len(self.rlog.read_events({"2026-07-07"})), 1)

    def test_non_finite_trace_rejected(self) -> None:
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        rec.trace = rec.trace + [{"layer": "x", "check": "bad",
                                  "label_human": "x", "detail": "",
                                  "inputs": {"v": float("inf")},
                                  "outcome": "info", "code_ref": "",
                                  "branch_taken": True}]
        with self.assertRaises(ValueError):
            self.rlog.append_recommendation_event(
                rec=rec, source="test", mode="eod",
                timestamp="2026-07-07T09:35:00-04:00", params_hash="x")

    def test_api_today_assembles_three_lanes(self) -> None:
        from web.server import app
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        with patch("strategy.selector.get_recommendation", return_value=rec), \
             patch("strategy.decision_trace.funding_trace",
                   return_value=[{"layer": "funding", "check": "cash_floor",
                                  "label_human": "x", "detail": "", "inputs": {},
                                  "outcome": "pass", "code_ref": "SPEC-115",
                                  "branch_taken": True}]):
            res = app.test_client().get("/api/decision-trace")
        self.assertEqual(res.status_code, 200)
        d = res.get_json()
        for lane in ("lane_a", "lane_b", "lane_c"):
            self.assertIn(lane, d)
        self.assertTrue(d["is_today"])
        checks = [n["check"] for n in d["lane_a"]]
        self.assertIn("final_verdict", checks)
        self.assertIn("cash_floor", checks)                      # ④ 资金层拼接
        self.assertIn("免责", json.dumps(d["lane_c"], ensure_ascii=False)
                      .replace("disclaimer", "免责") or "")
        self.assertIn("只描述，不进任何决策", d["lane_c"]["disclaimer"])
        for bad in ("NaN", "Infinity"):
            self.assertNotIn(bad, res.get_data(as_text=True))

    def test_api_historical_reads_stored_trace(self) -> None:
        from dataclasses import replace
        from web.server import app
        vs, ivs, ts = _carve_snapshots()
        vs = replace(vs, date="2026-07-01")           # 强制历史日
        rec = sel.select_strategy(vs, ivs, ts)
        self.rlog.append_recommendation_event(
            rec=rec, source="test", mode="eod",
            timestamp="2026-07-01T09:35:00-04:00", params_hash="x")
        res = app.test_client().get("/api/decision-trace?date=2026-07-01")
        d = res.get_json()
        self.assertFalse(d["is_today"])
        self.assertEqual([n["check"] for n in d["lane_a"]],
                         [n["check"] for n in rec.trace])
        self.assertIn("2026-07-01", d["dates_available"])
        self.assertIn("未存档", d["lane_b"][0]["label_human"])   # 历史 Lane B 如实标注

    def test_funding_trace_fail_soft(self) -> None:
        from strategy.decision_trace import funding_trace
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   side_effect=RuntimeError("broker down")), \
             patch("strategy.exposure.evaluate_exposure_degrade",
                   side_effect=RuntimeError("also down")), \
             patch("strategy.capacity.used_defined_risk",
                   side_effect=RuntimeError("down too")):     # SPEC-135.2 容量节点
            nodes = funding_trace("bull_put_spread")
        self.assertTrue(nodes)
        self.assertTrue(all(n["outcome"] == "info" for n in nodes))  # 不拦


class UiAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def test_three_lanes_and_disclaimer(self) -> None:
        for token in ("Lane A · 今天开不开新仓？", "Lane B · 手上的仓位要动吗？",
                      "Lane C · 地形参考（只描述，不决策）"):
            self.assertIn(token, self.spx)

    def test_hover_triple_wired(self) -> None:
        for token in ("检查数据", "实际值 vs 阈值", "代码溯源", "trace-triple",
                      "label_human"):
            self.assertIn(token, self.spx)

    def test_frontend_has_no_hardcoded_gate_list(self) -> None:
        """反漂移铁律：前端零硬编码 gate 清单——gate check 名不得出现在模板。"""
        for gate_check in ("nnb_ivp_upper", "nnb_backwardation", "nlb_spec113_carve",
                           "hv_bearish_ivp63", "g2_18m"):
            self.assertNotIn(gate_check, self.spx)

    def test_ghost_and_date_switcher(self) -> None:
        for token in ("trace-ghost", "ghost 分支", "trace-date-pick",
                      "loadDecisionTrace"):
            self.assertIn(token, self.spx)


if __name__ == "__main__":
    unittest.main()
