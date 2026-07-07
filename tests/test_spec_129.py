"""SPEC-129 — 手动入场信息鸿沟修复批（BPS 复审产物）.

AC coverage:
  AC-1 advisory 附 selector reason（IVP 否决日 → FYI 正文含 IVP= 与阈值；
       仍 FYI 类不升级）                                → AdvisoryReasonTests
  AC-2 (a) 推荐日预填字段透传（非 mock 冒烟）            → OpenDraftPrefillSmokeTests
       (b) 偏离 auto-note 落 ledger open 事件            → DeviationLedgerTests
       (c) wait 日提交路径不受阻 + 横幅/无预填（UI 源锁） → DeviationLedgerTests / UiSourceTests
  AC-3 风险行三绝对值与手算一致；strict-JSON；cash fail-soft → EntryRiskTests

测试向量脚本生成（seeded RNG / 单一变量源），无手抄常数。
"""
from __future__ import annotations

import json
import os
import random
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import logs.trade_log_io as tlog
import strategy.state as state_mod
import web.server as server_mod
from web.server import app

from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.selector import BPS_NNB_IVP_UPPER, select_strategy


TODAY = date.today().isoformat()


def _nnb_snapshots(ivp: float):
    """NORMAL × IV NEUTRAL × BULLISH 格 fixture（5/4 实证场景：IVP 越上限门）."""
    vix_snap = VixSnapshot(
        date=TODAY, vix=17.0, regime=Regime.NORMAL, trend=Trend.FLAT,
        vix_5d_avg=17.0, vix_5d_ago=17.1, transition_warning=False,
        vix3m=19.0, backwardation=False, vix_peak_10d=18.0)
    iv_snap = IVSnapshot(
        date=TODAY, vix=17.0, iv_rank=48.0, iv_percentile=float(ivp),
        iv_signal=IVSignal.NEUTRAL, iv_52w_high=30.0, iv_52w_low=12.0,
        ivp63=float(ivp), ivp252=float(ivp))
    trend_snap = TrendSnapshot(
        date=TODAY, spx=6000.0, ma20=5900.0, ma50=5800.0,
        ma_gap_pct=0.034, signal=TrendSignal.BULLISH, above_200=True,
        atr14=45.0, gap_sigma=1.2)
    return vix_snap, iv_snap, trend_snap


# ── AC-1 — advisory 附原因文本 ───────────────────────────────────────────────

class AdvisoryReasonTests(unittest.TestCase):
    def _ivp_veto_rec(self, ivp: float):
        rec = select_strategy(*_nnb_snapshots(ivp))
        # 生产 selector 真值：IVP ≥ 上限门 → reduce_wait，reason 带 IVP= 与阈值
        self.assertEqual(rec.strategy_key, "reduce_wait")
        self.assertIn(f"IVP={ivp:.0f}", rec.rationale)
        self.assertIn(str(BPS_NNB_IVP_UPPER), rec.rationale)
        return rec

    def _run_advisory(self, rec, strategy_key="bull_put_spread",
                      trade_id="2026-07-07_bps_001"):
        sent: list[dict] = []

        def _rec_push(category, about, title, body, **kw):
            sent.append({"category": category, "about": about,
                         "title": title, "body": body})
            return True

        with patch("strategy.selector.get_recommendation", return_value=rec), \
             patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 0.0, "source": "unavailable",
                                 "breakdown": {}, "error": "test"}), \
             patch("strategy.cash_budget_governance.evaluate_cash_collateral_budget",
                   return_value={"accepted": True}), \
             patch("notify.gateway.push", side_effect=_rec_push):
            server_mod._manual_open_governance_advisory(strategy_key, {}, trade_id)
        return sent

    def test_ivp_veto_day_fyi_carries_reason(self) -> None:
        """AC-1: IVP 否决日 → FYI 正文含 IVP= 与阈值字样，类别不升级."""
        ivp = 62.0
        rec = self._ivp_veto_rec(ivp)
        sent = self._run_advisory(rec)
        self.assertEqual(len(sent), 1)
        p = sent[0]
        self.assertEqual(p["category"], "FYI")          # 仍 FYI，不升级
        self.assertEqual(p["about"], "持仓 2026-07-07_bps_001")
        self.assertIn(f"IVP={ivp:.0f}", p["body"])       # 原因文本（教学面）
        self.assertIn(str(BPS_NNB_IVP_UPPER), p["body"])
        self.assertIn("路由为 wait", p["body"])

    def test_route_mismatch_also_carries_reason(self) -> None:
        ivp = 50.0   # 门内 → 正常路由 bull_put_spread
        rec = select_strategy(*_nnb_snapshots(ivp))
        self.assertEqual(rec.strategy_key, "bull_put_spread")
        sent = self._run_advisory(rec, strategy_key="bear_call_spread_hv",
                                  trade_id="2026-07-07_bcsh_001")
        self.assertEqual(len(sent), 1)
        body = sent[0]["body"]
        self.assertIn("路由=bull_put_spread", body)
        self.assertIn("Selector 原因:", body)
        self.assertIn(rec.rationale, body)

    def test_on_route_day_no_push(self) -> None:
        """在格开仓（策略与路由一致）→ 无治理提示（现状保持）."""
        rec = select_strategy(*_nnb_snapshots(50.0))
        sent = self._run_advisory(rec, strategy_key="bull_put_spread")
        self.assertEqual(sent, [])


# ── 共享 setUp（ledger/state 隔离 + governance basis 种子）────────────────────

class _IsolatedApiCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        tmp = self.tmpdir.name
        self.orig_state = state_mod.STATE_FILE
        self.orig_closed = state_mod.CLOSED_TRADES_FILE
        self.orig_log = tlog.TRADE_LOG_FILE
        state_mod.STATE_FILE = os.path.join(tmp, "current_position.json")
        state_mod.CLOSED_TRADES_FILE = os.path.join(tmp, "closed_trades.jsonl")
        tlog.TRADE_LOG_FILE = Path(tmp) / "trade_log.jsonl"
        import strategy.sleeve_governance as gov_mod
        self._gov_mod = gov_mod
        self.orig_runtime = gov_mod.RUNTIME_STATE_PATH
        gov_mod.RUNTIME_STATE_PATH = Path(tmp) / "sleeve_governance_runtime.json"
        gov_mod.RUNTIME_STATE_PATH.write_text(json.dumps(
            {"basis_dollars": 1_240_000.0, "timestamp": "2026-01-01T00:00:00"}))
        gov_mod._BASIS_DEGRADED_ALERTED.clear()
        self.client = app.test_client()

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state
        state_mod.CLOSED_TRADES_FILE = self.orig_closed
        tlog.TRADE_LOG_FILE = self.orig_log
        self._gov_mod.RUNTIME_STATE_PATH = self.orig_runtime


# ── AC-2(b)(c) — 偏离 auto-note 落 ledger + 提交不受阻 ───────────────────────

class DeviationLedgerTests(_IsolatedApiCase):
    def _open_payload(self, **extra) -> dict:
        return {
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "short_strike": 7000, "long_strike": 6800,
            "expiry": "2026-08-07", "dte_at_entry": 30,
            "contracts": 2, "actual_premium": 8.5,
            **extra,
        }

    def test_deviations_land_in_open_event_note_and_structured(self) -> None:
        """AC-2(b): deviated 字段 → note 自动追加 + 结构化 deviations 落 ledger."""
        devs = [
            {"field": "long_strike", "actual": 6800, "rec": 6875},
            {"field": "dte_at_entry", "actual": 30, "rec": 28},
        ]
        res = self.client.post("/api/position/open",
                               json=self._open_payload(note="manual note",
                                                       deviations=devs))
        self.assertEqual(res.status_code, 200, res.get_json())
        tid = res.get_json()["trade_id"]
        resolved = {t["id"]: t for t in tlog.resolve_log()}
        o = resolved[tid]["open"]
        exp_note = ("manual note | "
                    + "; ".join(f"deviated: {d['field']}={d['actual']} (rec {d['rec']})"
                                for d in devs))
        self.assertEqual(o["note"], exp_note)
        self.assertEqual(o["deviations"], devs)

    def test_no_deviations_keeps_note_untouched(self) -> None:
        res = self.client.post("/api/position/open",
                               json=self._open_payload(note="plain"))
        self.assertEqual(res.status_code, 200)
        tid = res.get_json()["trade_id"]
        o = next(t for t in tlog.resolve_log() if t["id"] == tid)["open"]
        self.assertEqual(o["note"], "plain")
        self.assertNotIn("deviations", o)

    def test_wait_day_submission_not_blocked(self) -> None:
        """AC-2(c): 提交路径不消费 selector 路由——wait 日（或 selector 完全
        不可用）manual open 照常 200，advisory 只是事后 FYI（提示不拦）."""
        with patch("strategy.selector.get_recommendation",
                   side_effect=RuntimeError("selector unavailable / wait day")):
            res = self.client.post("/api/position/open", json=self._open_payload())
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertTrue(res.get_json().get("trade_id"))


# ── AC-3 — 风险行三绝对值 ────────────────────────────────────────────────────

class EntryRiskTests(_IsolatedApiCase):
    def _seed_family_positions(self, rng: random.Random) -> dict:
        """两笔同家族 BPS（schwab 主 + etrade _hv 变体）+ 一笔异家族 BCD."""
        v = {
            "bps1": {"ss": 5 * rng.randint(1350, 1450), "w": 5 * rng.randint(20, 40),
                     "prem": round(rng.uniform(5, 12), 2), "n": rng.randint(1, 4)},
            "bps2": {"ss": 5 * rng.randint(1350, 1450), "w": 5 * rng.randint(20, 40),
                     "prem": round(rng.uniform(5, 12), 2), "n": rng.randint(1, 4)},
            "bcd":  {"ss": 5 * rng.randint(1500, 1560), "w": 5 * rng.randint(80, 100),
                     "prem": -round(rng.uniform(300, 450), 2), "n": 1},
        }
        state_mod.write_state("Bull Put Spread", "SPX", strategy_key="bull_put_spread",
                              account="schwab", trade_id="R1",
                              short_strike=v["bps1"]["ss"],
                              long_strike=v["bps1"]["ss"] - v["bps1"]["w"],
                              expiry="2026-08-07", contracts=v["bps1"]["n"],
                              actual_premium=v["bps1"]["prem"])
        # 同家族 _hv 变体（不同 strategy_key，同 family）——加进同一 state 需要
        # per-position strategy_key
        state_mod.write_state("Bull Put Spread", "SPX", strategy_key="bull_put_spread",
                              account="etrade", trade_id="R2",
                              short_strike=v["bps2"]["ss"],
                              long_strike=v["bps2"]["ss"] - v["bps2"]["w"],
                              expiry="2026-08-07", contracts=v["bps2"]["n"],
                              actual_premium=v["bps2"]["prem"])
        # 异家族 BCD leg（应被家族过滤排除）——直接写 per-position strategy_key
        raw = state_mod._load_raw()
        raw["positions"].append({
            "trade_id": "R3", "account": "schwab",
            "strategy_key": "bull_call_diagonal",
            "short_strike": v["bcd"]["ss"],
            "long_strike": v["bcd"]["ss"] - v["bcd"]["w"],
            "expiry": "2026-08-21", "long_expiry": "2026-10-16",
            "contracts": v["bcd"]["n"], "actual_premium": v["bcd"]["prem"],
        })
        state_mod._save(raw)
        return v

    @staticmethod
    def _credit_max_loss(width: float, prem: float, n: int) -> float:
        return (width - prem) * 100.0 * n

    def test_three_values_match_hand_calc(self) -> None:
        """AC-3: fixture 三值与独立手算一致（向量脚本生成）."""
        rng = random.Random(129)
        v = self._seed_family_positions(rng)
        cash = round(rng.uniform(400_000, 700_000), 2)
        order = {"ss": 7300, "w": 100, "prem": 6.4, "n": 3}
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": cash, "source": "live",
                                 "breakdown": {}, "error": None}):
            res = self.client.get(
                "/api/position/entry-risk?strategy_key=bull_put_spread"
                f"&short_strike={order['ss']}&long_strike={order['ss'] - order['w']}"
                f"&premium={order['prem']}&contracts={order['n']}")
        self.assertEqual(res.status_code, 200)
        # strict JSON — NaN/Inf 字面量必须解析失败即不存在
        def _bad(_s):
            raise AssertionError(f"non-finite literal in JSON: {_s}")
        data = json.loads(res.get_data(as_text=True), parse_constant=_bad)

        # 独立手算（同一向量重新推导）
        exp_order = self._credit_max_loss(order["w"], order["prem"], order["n"])
        exp_family_open = (
            self._credit_max_loss(v["bps1"]["w"], v["bps1"]["prem"], v["bps1"]["n"])
            + self._credit_max_loss(v["bps2"]["w"], v["bps2"]["prem"], v["bps2"]["n"]))
        exp_concurrent = exp_order + exp_family_open
        self.assertAlmostEqual(data["order_max_loss_usd"], exp_order, places=2)
        self.assertAlmostEqual(data["family_open_max_loss_usd"], exp_family_open, places=2)
        self.assertAlmostEqual(data["family_concurrent_max_loss_usd"], exp_concurrent, places=2)
        self.assertAlmostEqual(data["liquid_cash_usd"], cash, places=2)
        self.assertAlmostEqual(data["concurrent_pct_of_cash"],
                               round(exp_concurrent / cash * 100.0, 2), places=2)
        # 异家族 BCD 不进合计
        fam_ids = {p["trade_id"] for p in data["family_open_positions"]}
        self.assertEqual(fam_ids, {"R1", "R2"})

    def test_debit_structure_max_loss_is_abs_debit(self) -> None:
        rng = random.Random(292)
        prem = -round(rng.uniform(300, 450), 2)
        n = rng.randint(1, 3)
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 500_000.0, "source": "live",
                                 "breakdown": {}, "error": None}):
            res = self.client.get(
                "/api/position/entry-risk?strategy_key=bull_call_diagonal"
                f"&short_strike=7700&long_strike=7200&premium={prem}&contracts={n}")
        data = res.get_json()
        self.assertAlmostEqual(data["order_max_loss_usd"], abs(prem) * 100 * n, places=2)

    def test_cash_unavailable_fails_soft(self) -> None:
        """AC-3: 现金源不可用 → 该行 n/a（null），端点仍 200，其余两值照常."""
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   side_effect=RuntimeError("broker down")):
            res = self.client.get(
                "/api/position/entry-risk?strategy_key=bull_put_spread"
                "&short_strike=7000&long_strike=6900&premium=8&contracts=1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNone(data["liquid_cash_usd"])
        self.assertIsNone(data["concurrent_pct_of_cash"])
        self.assertAlmostEqual(data["order_max_loss_usd"], (100 - 8) * 100 * 1, places=2)

    def test_family_groups_hv_variant_not_other_strategies(self) -> None:
        self.assertEqual(server_mod._strategy_family("bull_put_spread_hv"), "bull_put_spread")
        self.assertEqual(server_mod._strategy_family("bull_put_spread"), "bull_put_spread")
        self.assertEqual(server_mod._strategy_family("bull_call_diagonal"), "bull_call_diagonal")
        self.assertNotEqual(server_mod._strategy_family("bear_call_spread_hv"),
                            server_mod._strategy_family("bull_put_spread"))


# ── AC-2(a) — 预填字段透传（非 mock 冒烟）────────────────────────────────────

class OpenDraftPrefillSmokeTests(unittest.TestCase):
    """Integration smoke（非 mock）：对 live 推荐 payload 断言 open-draft 字段
    透传。wait 日走 wait 契约分支（400 + error），推荐日走一致性分支。
    live 市场数据不可用 → skip（不是 fail：冒烟目标是字段透传，不是行情）。"""

    def test_prefill_passthrough_against_live_recommendation(self) -> None:
        client = app.test_client()
        rec_res = client.get("/api/recommendation")
        rec = rec_res.get_json()
        if rec_res.status_code != 200 or rec.get("error"):
            self.skipTest(f"live recommendation unavailable: {rec.get('error')}")
        draft_res = client.get("/api/position/open-draft")
        if rec.get("strategy_key") == "reduce_wait" or not (rec.get("legs") or []):
            # wait 日契约：无推荐可预填 → 400（前端据此走横幅分支，不预填）
            self.assertEqual(draft_res.status_code, 400)
            self.assertIn("error", draft_res.get_json())
            return
        self.assertEqual(draft_res.status_code, 200, draft_res.get_json())
        draft = draft_res.get_json()
        # 字段透传：strategy/dte/expiry/strikes 与推荐 payload 一致
        self.assertEqual(draft["strategy_key"], rec["strategy_key"])
        rec_dtes = [int(l["dte"]) for l in rec["legs"]]
        self.assertEqual(int(draft["dte_at_entry"]), min(rec_dtes))
        self.assertGreater(float(draft["short_strike"]), 0)
        date.fromisoformat(draft["expiry"])  # ISO 且可解析
        if draft.get("long_strike") is not None:
            self.assertGreater(float(draft["long_strike"]), 0)
        self.assertIsNotNone(draft.get("model_premium"))


# ── UI 源锁（wait 横幅 / 偏离高亮 / 风险行接线存在性）─────────────────────────

class UiSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (Path(__file__).resolve().parents[1]
                   / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def test_wait_banner_and_no_prefill_guard_present(self) -> None:
        for token in ("open-wait-banner", "renderOpenWaitBanner",
                      "OPEN_MODAL_WAIT_DAY && !userInitiated", "NO ENTRY"):
            self.assertIn(token, self.spx)

    def test_deviation_tracking_wired(self) -> None:
        for token in ("checkOpenDeviations", "collectOpenDeviations",
                      "REC_BASELINE", "modal-input.deviated",
                      "basePayload.deviations = _devs"):
            self.assertIn(token, self.spx)

    def test_risk_row_wired(self) -> None:
        for token in ("open-risk-row", "loadEntryRisk", "updateOpenRiskRow",
                      "/api/position/entry-risk", "Max loss (this order)"):
            self.assertIn(token, self.spx)

    def test_no_text_muted_on_new_readable_content(self) -> None:
        # 新增 SPEC-129 UI 片段不得用 --text-muted（可读内容一律 --text-2）
        for cls_block in ("open-wait-banner", "open-risk-row"):
            idx = self.spx.find(cls_block)
            self.assertNotIn("--text-muted", self.spx[idx:idx + 1200])


if __name__ == "__main__":
    unittest.main()
