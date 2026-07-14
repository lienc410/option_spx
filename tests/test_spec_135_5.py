"""SPEC-135.5 — Lane D「Sleeve 决策引擎泳道」.

AC coverage:
  数据同源静态断言（装配层零旁路重推公式/阈值）     → SameSourceStaticTests
  联动线与 gate log 最新行逐字段一致               → LinkageVerbatimTests
  7/11 快照固定测试用例（双 sleeve armed +
    main_bp 15.8% 联动线；冻结向量回归锁）          → Fixture711Tests
  badge 词表合规（DESIGN.md Action State +
    Signal-outcome states）                        → VocabularyTests
  人话铁律 §0（label_human/三件套/术语英文保留）    → Fixture711Tests / UiAuditTests
  首页摘要行与 /spx 行同 copy 源（共享整卡单渲染）  → UiAuditTests
  API 装配（当日 lane_d / 历史未存档 / strict-JSON）→ ApiAssemblyTests
  引擎级 fail-soft（数据源全挂不炸泳道）            → FailSoftTests
  ES Ladder 行与首页卡同 copy 源（status_human）    → StatusHumanTests

测试向量：tests/fixtures/spec135_5_lane_d_vectors.json（脚本生成——
scripts/gen_spec135_5_vectors.py；gate 行由 q042_gate.compute_gate 产出，
公式唯一真值；expected_lane_d 为冻结回归锁，重生成须在 commit 注明）。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads(
    (ROOT / "tests" / "fixtures" / "spec135_5_lane_d_vectors.json")
    .read_text(encoding="utf-8"),
    parse_constant=lambda s: (_ for _ in ()).throw(AssertionError(s)))

# DESIGN.md badge 词表（Action State + Signal-outcome states）
LEGAL_BADGE_WORDS = {
    "OPEN", "HOLD", "CLOSE", "NO ENTRY", "WARNING", "BLOCKED", "REVIEW",
    "SIGNAL", "ARMED", "WATCHING", "WAITING", "SKIPPED", "CHANGED",
    "CONFIRMED", "TIMEOUT", "CALM", "READ ONLY", "DEFERRED",
}


def _lane_d_with(inputs: dict, tmp_path: Path, *, gate_rows=None,
                 q042_state=None, aftermath=None, market=None, hvladder=None):
    """与 scripts/gen_spec135_5_vectors.py 同一 patch 面灌 lane_d_sleeves。"""
    import strategy.q042_gate as qg
    import strategy.sleeve_governance as sg
    import web.server  # noqa: F401

    gate_log = tmp_path / "gate_log.jsonl"
    rows = gate_rows if gate_rows is not None else inputs["gate_log_rows"]
    gate_log.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                        encoding="utf-8")
    from strategy.decision_trace import lane_d_sleeves
    with patch("web.server.q042_state_payload",
               return_value=q042_state or inputs["q042_state"]), \
         patch.object(qg, "GATE_LOG", gate_log), \
         patch("web.server.aftermath_state_payload",
               return_value=aftermath or inputs["aftermath_state"]), \
         patch.object(sg, "_latest_market_stress",
                      return_value=market or inputs["market_stress"]), \
         patch.object(sg, "booster_mode", return_value="shadow"), \
         patch.object(sg, "ladder_mode", return_value="shadow"), \
         patch("web.server.hvladder_live_payload",
               return_value=hvladder or inputs["hvladder_live"]):
        return lane_d_sleeves()


class SameSourceStaticTests(unittest.TestCase):
    """AC: 数据全同源既有 API/生产函数——静态断言零旁路重推。"""

    @classmethod
    def setUpClass(cls) -> None:
        src = (ROOT / "strategy" / "decision_trace.py").read_text(encoding="utf-8")
        i = src.find("SPEC-135.5 — Lane D")
        assert i > -1
        cls.lane_d_src = src[i:]
        cls.server_src = (ROOT / "web" / "server.py").read_text(encoding="utf-8")

    def test_lane_d_reads_only_production_sources(self) -> None:
        # 四台引擎 + 联动线的数据源符号必须全部出现（同一组装点/生产函数）
        for symbol in ("q042_state_payload", "read_latest_gate_row",
                       "aftermath_state_payload", "_latest_market_stress",
                       "booster_signal_conditions", "active_spx_cap",
                       "hvladder_live_payload", "status_human"):
            self.assertIn(symbol, self.lane_d_src, symbol)

    def test_lane_d_never_rederives_formulas(self) -> None:
        # 禁旁路重推：联合门公式/触发阈值/状态机阈值的字面量不得在装配层出现
        for forbidden in ("min(", "max(", "compute_gate(", "12.5", "= 60",
                          "0.04", "0.15", ">= 28", ">= 22", "* (1 -"):
            self.assertNotIn(forbidden, self.lane_d_src, forbidden)
        # 阈值只能经 import 的生产常数进来
        for const in ("_DD4_THRESHOLD", "_DD15_THRESHOLD", "_REARM_THRESHOLD",
                      "_MAIN_BP_BUDGET"):
            self.assertIn(const, self.lane_d_src, const)

    def test_api_routes_share_the_same_payload_builders(self) -> None:
        # /api 路由体 = 同一 payload 函数（Lane D 与 API 字面同源的机械保证）
        for call in ("return jsonify(q042_state_payload())",
                     "return jsonify(aftermath_state_payload())",
                     "return jsonify(hvladder_live_payload())"):
            self.assertIn(call, self.server_src, call)

    def test_gate_log_reader_lives_with_writer(self) -> None:
        qg = (ROOT / "strategy" / "q042_gate.py").read_text(encoding="utf-8")
        self.assertIn("def read_latest_gate_row", qg)
        self.assertIn("def log_gate", qg)          # 读写同居（同一 GATE_LOG）


class LinkageVerbatimTests(unittest.TestCase):
    """AC: 联动线数值与 gate log 最新行逐字段一致。"""

    def _linkage(self, lane_d: dict) -> dict:
        return next(n for n in lane_d["engines"]
                    if n["check"] == "dd_overlay_main_linkage")

    def test_linkage_inputs_verbatim_from_latest_gate_row(self) -> None:
        import tempfile
        inputs = VECTORS["inputs"]
        row = inputs["gate_log_rows"][1]           # 最新 gate 状态行（7/11）
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(inputs, Path(tmp))
        link = self._linkage(lane_d)
        for k in ("date", "main_bp_pct", "q042_combined_cap",
                  "sleeve_a_allowance", "sleeve_b_allowance", "gate_binding"):
            self.assertEqual(link["inputs"][k], row[k], k)
        self.assertEqual(link["inputs"]["src"], row["bp_source"]["source"])
        self.assertEqual(link["inputs"]["src_timestamp"],
                         row["bp_source"]["timestamp"])
        # 主行数字与档位（15.8 / 60 / 12.5）都来自该行
        for token in ("15.8", "60", "12.5"):
            self.assertIn(token, link["label_human"])
        self.assertEqual(link["outcome"], "pass")          # 未压缩 ≠ 红/琥珀
        self.assertIn("未压缩", link["label_human"])

    def test_reader_skips_blocked_fire_and_takes_latest(self) -> None:
        # 向量里最后一行是 blocked_fire——read_latest_gate_row 必须跳过它
        import tempfile
        import strategy.q042_gate as qg
        inputs = VECTORS["inputs"]
        with tempfile.TemporaryDirectory() as tmp:
            gate_log = Path(tmp) / "g.jsonl"
            gate_log.write_text(
                "\n".join(json.dumps(r) for r in inputs["gate_log_rows"]) + "\n",
                encoding="utf-8")
            with patch.object(qg, "GATE_LOG", gate_log):
                row = qg.read_latest_gate_row()
        self.assertEqual(row["date"], "2026-07-11")
        self.assertNotIn("blocked_fire", row)
        self.assertEqual(row["main_bp_pct"], 15.8)

    def test_linkage_squeezed_zero_and_failclosed_wording(self) -> None:
        import tempfile
        inputs = VECTORS["inputs"]
        cases = [
            (inputs["gate_row_squeezed"], "advisory", "压缩"),
            (inputs["gate_row_zero"], "veto", "归零"),
            (inputs["gate_row_failclosed"], "advisory", "fail-closed"),
        ]
        for row, outcome, token in cases:
            with tempfile.TemporaryDirectory() as tmp:
                lane_d = _lane_d_with(inputs, Path(tmp), gate_rows=[row])
            link = self._linkage(lane_d)
            self.assertEqual(link["outcome"], outcome, row)
            self.assertIn(token, link["label_human"], row)

    def test_linkage_missing_log_fail_soft(self) -> None:
        import tempfile
        inputs = VECTORS["inputs"]
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(inputs, Path(tmp), gate_rows=[])
        link = self._linkage(lane_d)
        self.assertEqual(link["outcome"], "info")
        self.assertIn("尚无记录", link["label_human"])


class Fixture711Tests(unittest.TestCase):
    """AC: 7/11 快照固定测试用例（双 sleeve armed + main_bp 15.8% 联动线）。"""

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile
        cls._tmp = tempfile.TemporaryDirectory()
        cls.lane_d = _lane_d_with(VECTORS["inputs"], Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_frozen_vector_regression_lock(self) -> None:
        """全量输出 == 冻结向量（文案/结构变更必须有意识重生成）。"""
        self.assertEqual(self.lane_d, VECTORS["expected_lane_d"])

    def test_four_engines_plus_linkage(self) -> None:
        checks = [n["check"] for n in self.lane_d["engines"]]
        self.assertEqual(checks, ["dd_overlay", "dd_overlay_main_linkage",
                                  "aftermath_window", "sleeve_stress_machine",
                                  "es_ladder"])
        for n in self.lane_d["engines"]:
            self.assertEqual(n["stage"], "sleeve")
            self.assertIn(n["kind"], ("verdict", "evidence"))

    def test_dd_overlay_double_armed_copy(self) -> None:
        dd = self.lane_d["engines"][0]
        self.assertEqual(dd["badge"]["word"], "ARMED")
        self.assertIn("双 sleeve 待命中", dd["label_human"])
        self.assertIn("-0.9%", dd["label_human"])          # 回撤读数
        self.assertIn("3.1pp", dd["label_human"])          # 距 A 触发线（-0.9 → -4）
        # hover 三件套：检查数据 / 实际值 vs 阈值 / code_ref
        self.assertTrue(dd["inputs"])
        self.assertIn("-4", dd["detail"])
        self.assertIn("-15", dd["detail"])
        self.assertTrue(dd["code_ref"])

    def test_settled_backfill_position_does_not_render_hold(self) -> None:
        """2026-07-11 生产实锤回归锁：payload 的 active_position 携带已结算
        历史仓（is_active=False，grandfather 补录）时，DD Overlay 必须仍按
        armed 渲染 ARMED，而非 HOLD（HOLD=有活仓，词表语义）。"""
        import copy
        import tempfile
        vec = copy.deepcopy(VECTORS["inputs"])
        vec["q042_state"]["sleeve_a"]["active_position"] = {
            "trade_id": "A-2026-03-12", "is_active": False,
            "days_to_expiry": 0, "contracts": 1,
            "long_strike": 6675, "short_strike": 7005,
            "expiry_date": "2026-06-11", "current_pnl": 16329.0,
        }
        with tempfile.TemporaryDirectory() as td:
            lane_d = _lane_d_with(vec, Path(td))
        dd = lane_d["engines"][0]
        self.assertEqual(dd["badge"]["word"], "ARMED")
        self.assertIn("待命中", dd["label_human"])

    def test_node_schema_135_1_contract_plus_lane_d_fields(self) -> None:
        from tests.test_spec_135_1 import BASE_FIELDS
        for n in self.lane_d["engines"]:
            self.assertEqual(set(n.keys()) - {"badge"},
                             BASE_FIELDS | {"kind", "stage", "summary"},
                             n["check"])

    def test_summary_line_from_same_nodes(self) -> None:
        # 摘要行 = 各引擎 summary 字段拼接（同一函数吐出，无第二 copy 源）
        expected = " · ".join(n["summary"] for n in self.lane_d["engines"]
                              if n.get("summary"))
        self.assertEqual(self.lane_d["summary_line"], expected)
        self.assertIn("DD Overlay ARMED×2", self.lane_d["summary_line"])

    def test_semantics_says_real_decisions(self) -> None:
        self.assertIn("真实决策", self.lane_d["semantics"])
        self.assertIn("只描述", self.lane_d["semantics"])

    def test_options_terms_stay_english(self) -> None:
        """§0 术语铁律：期权/策略术语保留英文。"""
        blob = json.dumps(self.lane_d, ensure_ascii=False)
        for term in ("DD Overlay", "Aftermath", "VIX", "MA10",
                     "booster", "slots"):
            self.assertIn(term, blob)
        # 挂仓态的 "put spread" 术语在 EngineStateVariantTests 覆盖

    def test_strict_json(self) -> None:
        raw = json.dumps(self.lane_d, ensure_ascii=False, allow_nan=False)
        json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(
            AssertionError(s)))


class EngineStateVariantTests(unittest.TestCase):
    """DD Overlay/Aftermath/压力机的状态机分支（badge 与文案随真值走）。"""

    def _dd(self, q042_state: dict) -> dict:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(VECTORS["inputs"], Path(tmp),
                                  q042_state=q042_state)
        return lane_d["engines"][0]

    def test_dd_position_open_shows_position_and_expiry(self) -> None:
        st = json.loads(json.dumps(VECTORS["inputs"]["q042_state"]))
        st["sleeve_a"]["armed"] = False
        st["sleeve_a"]["active_position"] = {
            "trade_id": "q042_a_001", "entry_date": "2026-07-02",
            "long_strike": 7300.0, "short_strike": 7100.0, "contracts": 2,
            "expiry_date": "2026-08-21", "days_to_expiry": 41,
            "is_active": True, "current_pnl": 350.0}
        dd = self._dd(st)
        self.assertEqual(dd["badge"]["word"], "HOLD")
        self.assertIn("已挂仓", dd["label_human"])
        self.assertIn("2026-08-21", dd["label_human"])     # 到期
        self.assertIn("41", dd["label_human"])             # 剩余天数
        self.assertIn("put spread", dd["label_human"])
        self.assertEqual(dd["inputs"]["positions"], ["q042_a_001"])

    def test_dd_watching_state(self) -> None:
        st = json.loads(json.dumps(VECTORS["inputs"]["q042_state"]))
        st["sleeve_a"]["armed"] = False
        st["sleeve_b"]["armed"] = False
        st["sleeve_b"]["in_watching"] = True
        st["sleeve_b"]["watch_start_date"] = "2026-07-08"
        dd = self._dd(st)
        self.assertEqual(dd["badge"]["word"], "WATCHING")
        self.assertIn("MA10", dd["label_human"])
        self.assertIn("2026-07-08", dd["label_human"])

    def test_dd_ath_degraded_f7_advisory(self) -> None:
        """F7 语义：ATH degraded 显式标注 + 琥珀档 + 不给假回撤读数。"""
        st = json.loads(json.dumps(VECTORS["inputs"]["q042_state"]))
        st["ath_degraded"] = True
        st["ddath_pct"] = 0.0
        dd = self._dd(st)
        self.assertEqual(dd["outcome"], "advisory")
        self.assertIn("ATH 基准缺失", dd["label_human"])
        self.assertNotIn("还差", dd["label_human"])        # 距离读数不给
        self.assertIn("不可用", dd["detail"])

    def test_aftermath_active_signal(self) -> None:
        import tempfile
        am = dict(VECTORS["inputs"]["aftermath_state"])
        am.update({"active": True, "vix": 27.1, "vix_peak_10d": 32.4,
                   "off_peak_pct": 16.4, "reason": None, "regime": "HIGH_VOL"})
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(VECTORS["inputs"], Path(tmp), aftermath=am)
        n = next(x for x in lane_d["engines"] if x["check"] == "aftermath_window")
        self.assertEqual(n["badge"]["word"], "SIGNAL")
        self.assertIn("已激活", n["label_human"])
        self.assertIn("32.4", n["label_human"])

    def test_stress_machine_warning_when_stressed(self) -> None:
        import tempfile
        mk = dict(VECTORS["inputs"]["market_stress"])
        mk.update({"vix": 25.5, "stress_episode_active": True,
                   "vix_5d_change": 4.2, "ivp252": 78.0})
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(VECTORS["inputs"], Path(tmp), market=mk)
        n = next(x for x in lane_d["engines"]
                 if x["check"] == "sleeve_stress_machine")
        self.assertEqual(n["badge"]["word"], "WARNING")
        self.assertEqual(n["outcome"], "advisory")
        self.assertIn("stress episode", n["label_human"])
        self.assertIn("50%", n["label_human"])             # cap 压档（生产函数吐出）
        # warm-up 条件逐条在 detail（hover 三件套第 2 件）
        self.assertIn("ddATH>-4%", n["detail"])
        self.assertIn("VIX<22", n["detail"])


class VocabularyTests(unittest.TestCase):
    """AC: badge 词全部来自 DESIGN.md 词表（Action State + Signal-outcome）。"""

    def test_all_badges_in_legal_vocabulary(self) -> None:
        for n in VECTORS["expected_lane_d"]["engines"]:
            if "badge" in n:
                self.assertIn(n["badge"]["word"], LEGAL_BADGE_WORDS, n["check"])

    def test_code_emits_only_legal_badge_words(self) -> None:
        src = (ROOT / "strategy" / "decision_trace.py").read_text(encoding="utf-8")
        i = src.find("SPEC-135.5 — Lane D")
        words = set(re.findall(r'badge_word\s*=\s*"([^"]+)"', src[i:]))
        words |= set(re.findall(r'badge_word, badge_label = "([^"]+)"', src[i:]))
        self.assertTrue(words)
        for w in words:
            self.assertIn(w, LEGAL_BADGE_WORDS, w)
        # server.py（ES Ladder status_human）同样只吐词表词
        ssrc = (ROOT / "web" / "server.py").read_text(encoding="utf-8")
        j = ssrc.find("def hvladder_live_payload")
        swords = re.findall(r'badge_word, badge_label = "([^"]+)"',
                            ssrc[j:j + 4000])
        self.assertTrue(swords)
        for w in swords:
            self.assertIn(w, LEGAL_BADGE_WORDS, w)


class ApiAssemblyTests(unittest.TestCase):
    def test_today_payload_has_lane_d(self) -> None:
        import strategy.selector as sel
        from tests.test_spec_129 import _nnb_snapshots
        from web.server import app
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        with patch("strategy.selector.get_recommendation", return_value=rec), \
             patch("strategy.decision_trace.lane_d_sleeves",
                   return_value=VECTORS["expected_lane_d"]):
            res = app.test_client().get("/api/decision-trace")
        self.assertEqual(res.status_code, 200)
        d = res.get_json()
        self.assertIn("lane_d", d)
        self.assertEqual([n["check"] for n in d["lane_d"]["engines"]],
                         [n["check"] for n in
                          VECTORS["expected_lane_d"]["engines"]])
        raw = res.get_data(as_text=True)
        for bad in ("NaN", "Infinity"):
            self.assertNotIn(bad, raw)

    def test_historical_lane_d_honest_note(self) -> None:
        from web.server import app
        res = app.test_client().get("/api/decision-trace?date=2026-07-01")
        d = res.get_json()
        self.assertEqual(d["lane_d"]["engines"], [])
        self.assertIn("未存档", d["lane_d"]["note"])
        self.assertIsNone(d["lane_d"]["summary_line"])


class FailSoftTests(unittest.TestCase):
    def test_all_sources_down_still_five_rows_no_raise(self) -> None:
        import strategy.q042_gate as qg
        import strategy.sleeve_governance as sg
        from strategy.decision_trace import lane_d_sleeves
        boom = RuntimeError("source down")
        with patch("web.server.q042_state_payload", side_effect=boom), \
             patch.object(qg, "read_latest_gate_row", side_effect=boom), \
             patch("web.server.aftermath_state_payload", side_effect=boom), \
             patch.object(sg, "_latest_market_stress", side_effect=boom), \
             patch("web.server.hvladder_live_payload", side_effect=boom):
            lane_d = lane_d_sleeves()
        self.assertEqual(len(lane_d["engines"]), 5)
        for n in lane_d["engines"]:
            self.assertEqual(n["outcome"], "info")         # 不拦、不红
            self.assertIn("不可用", n["label_human"])

    def test_market_unavailable_is_honest_not_optimistic(self) -> None:
        import tempfile
        mk = {"status": "unavailable", "reason": "missing SPX cache"}
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(VECTORS["inputs"], Path(tmp), market=mk)
        n = next(x for x in lane_d["engines"]
                 if x["check"] == "sleeve_stress_machine")
        self.assertIn("市场读数不可用", n["label_human"])
        self.assertIn("fail-closed", n["label_human"])
        self.assertNotIn("badge", n)                       # 不装 CALM


class StatusHumanTests(unittest.TestCase):
    """AC: ES Ladder 行与首页卡同 copy 源——status_human 唯一组装点。"""

    def _payload(self, *, vix=15.0, slots=0):
        import web.server as ws
        with patch.object(ws, "_load_hvlad_paper_trades", return_value=[]), \
             patch.object(ws, "_hvlad_active_slots", return_value=slots), \
             patch.object(ws, "_hvlad_cadence_status", return_value=(True, 7)), \
             patch.object(ws, "_hvlad_vix_context",
                          return_value={"vix_current": vix, "vix_5td_avg": vix,
                                        "ok": True, "stale": False,
                                        "source": "test", "error": None,
                                        "latest_close_date": "2026-07-11",
                                        "quote_time": None}), \
             patch.object(ws, "_hvlad_trend_status",
                          return_value={"warmed": True, "trend_ok": True,
                                        "ok": True, "error": None}):
            return ws.hvladder_live_payload()

    def test_blocked_state_words(self) -> None:
        p = self._payload(vix=15.0, slots=0)
        sh = p["status_human"]
        self.assertEqual(sh["slots_text"], "slots 0/5")
        self.assertEqual(sh["blockers_human"], ["VIX"])
        self.assertEqual(sh["state_text"], "blocked: VIX")
        self.assertEqual(sh["badge_word"], "NO ENTRY")

    def test_signal_live_words(self) -> None:
        p = self._payload(vix=25.0, slots=0)
        sh = p["status_human"]
        self.assertTrue(p["signal_live"])
        self.assertEqual(sh["state_text"], "SIGNAL LIVE")
        self.assertEqual(sh["badge_word"], "SIGNAL")

    def test_hold_slots_words(self) -> None:
        p = self._payload(vix=15.0, slots=2)
        sh = p["status_human"]
        self.assertEqual(sh["badge_word"], "HOLD")
        self.assertEqual(sh["badge_label"], "HOLD 2/5")

    def test_home_card_consumes_status_human_not_local_map(self) -> None:
        home = (ROOT / "web" / "templates" / "portfolio_home.html").read_text(encoding="utf-8")
        self.assertIn("status_human", home)
        self.assertNotIn("blockMap", home)                 # 本地词表已删
        self.assertNotIn("vix_ok: 'VIX'", home)
        self.assertNotIn("label: 'SIGNAL'", home)          # badge 词不再前端组装
        self.assertNotIn("label: `HOLD ${", home)


class UiAuditTests(unittest.TestCase):
    """渲染面：第四泳道 + 折叠态摘要行；前端零引擎清单/零 copy 硬编码；
    首页摘要行与 /spx 同 copy 源 = 共享整卡单渲染（0d5991f 架构）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tr = (ROOT / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "static" / "theme.css").read_text(encoding="utf-8")
        cls.spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        cls.home = (ROOT / "web" / "templates" / "portfolio_home.html").read_text(encoding="utf-8")

    def test_fourth_lane_in_shared_card(self) -> None:
        self.assertIn("Lane D · 决策引擎状态（真实决策——区别于 Lane C 只描述）",
                      self.tr)
        self.assertIn("${traceLaneDHtml(d.lane_d)}", self.tr)

    def test_summary_strip_same_copy_source_both_pages(self) -> None:
        # 摘要行渲染在共享 cardHtml 的 <summary> 内（折叠态常显）——两页
        # 字节级同一（同 copy 源的机械保证：首页与 /spx 均只挂共享整卡）
        self.assertIn("${traceLaneDSummaryHtml(d.lane_d)}", self.tr)
        self.assertIn("决策引擎状态", self.tr)
        for tpl in (self.spx, self.home):
            self.assertIn("TraceRender.loadCard('decision-trace')", tpl)
            self.assertNotIn("laneDSummaryHtml(", tpl)     # 页面不自渲染第二份

    def test_frontend_zero_engine_copy(self) -> None:
        # 引擎行文案只活在后端装配层——前端与模板零 copy 硬编码
        for token in ("待命中", "余波窗口", "与主策略的联动", "压力状态机",
                      "已挂仓"):
            for src in (self.tr, self.spx, self.home):
                self.assertNotIn(token, src, token)

    def test_badge_word_to_class_map_only_styling(self) -> None:
        self.assertIn("TRACE_BADGE_CLS", self.tr)
        m = re.search(r"TRACE_BADGE_CLS = \{([^}]+)\}", self.tr)
        words = set(re.findall(r"'([^']+)':\s*'tb-", m.group(1)))
        for w in words:
            self.assertIn(w, LEGAL_BADGE_WORDS, w)

    def test_hover_triple_on_lane_d_rows(self) -> None:
        i = self.tr.find("function traceLaneDNodeHtml")
        block = self.tr[i:i + 1600]
        for token in ("检查数据", "实际值 vs 阈值", "代码溯源", "trace-triple"):
            self.assertIn(token, block)

    def test_lane_d_css_in_theme_no_text_muted(self) -> None:
        i = self.css.find("SPEC-135.5")
        self.assertGreater(i, -1)
        block = self.css[i:i + 2200]
        for cls in (".trace-sleeve-summary", ".t-badge", ".trace-laned-link"):
            self.assertIn(cls, block)
        rules_only = re.sub(r"^.*?\*/", "", block, count=1, flags=re.S)
        rules_only = re.sub(r"/\*.*?\*/", "", rules_only, flags=re.S)
        self.assertNotIn("--text-muted", rules_only)       # 可读内容禁用
        # 双主题：全走 CSS vars，零裸 hex
        self.assertNotIn("#", rules_only)

    def test_asset_versions_bumped(self) -> None:
        # SPEC-141.1：theme.css/trace_render.js 内容变更（trace :target 高亮 +
        # 节点稳定 id）→ 版本键随内容全站同步（DESIGN.md Decisions Log 2026-07-11）
        # theme.css 版本键当前 = pools1（2026-07-13 PoolsRender 共享样式；棘轮字面量）
        for tpl in (self.spx, self.home):
            self.assertIn("theme.css') }}?v=pools1", tpl)
            self.assertIn("trace_render.js') }}?v=spec141_1", tpl)


if __name__ == "__main__":
    unittest.main()
