"""SPEC-148 — IC 四腿 schema 扩展（手动开仓链路）acceptance tests.

AC map:
  AC-1 exposure 公式 — IC 不对称翼取 max 翼宽；无 put 对回落 call 翼（向后兼容）
  AC-2 draft 集成 — IC 合成推荐 → payload 四 strike 齐 + legs 4 条
  AC-3 提交 roundtrip — put 对落 state + ledger open 事件；BPS 不带值
  AC-4 UI 源锁 — ic-only 区块 / put 输入 / 槽位映射 / 偏离字段存在性
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from strategy.exposure import estimate_bp_per_contract, order_max_loss_usd


class TestAC1MaxLossFormula(unittest.TestCase):
    def test_ic_asymmetric_wings_take_max(self):
        # call 翼 6300/6350 (宽 50)，put 翼 5900/5800 (宽 100)，credit 12
        # → per-contract = (100 − 12) × 100 = 8800
        v = estimate_bp_per_contract("iron_condor", 6300, 6350, 12.0, 5900, 5800)
        self.assertEqual(v, 8800.0)

    def test_ic_symmetric_wings_unchanged(self):
        v = estimate_bp_per_contract("iron_condor", 6300, 6350, 12.0, 5900, 5850)
        self.assertEqual(v, (50 - 12) * 100.0)

    def test_ic_without_put_pair_falls_back_to_call_width(self):
        # 旧记录（无 put 字段）向后兼容：只按 call 翼宽算
        v = estimate_bp_per_contract("iron_condor", 6300, 6350, 12.0)
        self.assertEqual(v, (50 - 12) * 100.0)

    def test_non_ic_ignores_put_params(self):
        base = estimate_bp_per_contract("bull_put_spread", 7000, 6800, 8.5)
        self.assertEqual(base, (200 - 8.5) * 100.0)

    def test_order_max_loss_passthrough(self):
        v = order_max_loss_usd("iron_condor", 6300, 6350, 12.0, 2, 5900, 5800)
        self.assertEqual(v, 8800.0 * 2)

    def test_family_exposure_reads_put_fields(self):
        import strategy.exposure as expo
        pos = {"positions": [{
            "trade_id": "t1", "account": "schwab", "strategy_key": "iron_condor",
            "short_strike": 6300, "long_strike": 6350,
            "short_put_strike": 5900, "long_put_strike": 5800,
            "actual_premium": 12.0, "contracts": 1,
        }]}
        with patch("strategy.state.read_all_positions", return_value=pos):
            fam = expo.family_open_exposure("iron_condor")
        self.assertEqual(fam["family_open_max_loss_usd"], 8800.0)


def _ic_rec():
    from signals.iv_rank import IVSignal
    from signals.trend import TrendSignal
    from signals.vix_regime import Regime, Trend
    from strategy.selector import select_strategy
    from tests.test_strategy_unification import make_iv, make_trend, make_vix
    return select_strategy(
        make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
        make_iv(signal=IVSignal.NEUTRAL, iv_rank=50.0, iv_percentile=50.0, vix=13.0),
        make_trend(signal=TrendSignal.NEUTRAL),
    )


import logs.trade_log_io as tlog          # noqa: E402
import strategy.state as state_mod        # noqa: E402
from web.server import app                # noqa: E402


class _IsolatedApiCase(unittest.TestCase):
    """ledger/state 隔离 + governance basis 种子（同 test_spec_129 fixture）。"""

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


class TestAC2DraftFourStrikes(_IsolatedApiCase):
    def test_ic_draft_carries_four_strikes(self):
        rec = _ic_rec()
        self.assertEqual(rec.strategy_key, "iron_condor")
        with patch("strategy.selector.get_recommendation", return_value=rec), \
             patch("schwab.auth.is_configured", return_value=False):
            res = self.client.get("/api/position/open-draft")
        self.assertEqual(res.status_code, 200, res.get_json())
        draft = res.get_json()
        for f in ("short_strike", "long_strike", "short_put_strike", "long_put_strike"):
            self.assertIsNotNone(draft.get(f), f)
            self.assertGreater(float(draft[f]), 0, f)
        self.assertEqual(len(draft["legs"]), 4)
        # call 侧约定：short/long_strike = CALL 腿；put 对低于 call 对（IC 结构）
        self.assertLess(float(draft["short_put_strike"]), float(draft["short_strike"]))
        self.assertLess(float(draft["long_put_strike"]), float(draft["short_put_strike"]))

    def test_non_ic_draft_put_fields_none(self):
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        rec = select_strategy(
            make_vix(vix=18.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=40.0, iv_percentile=40.0, vix=18.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        if rec.strategy_key == "reduce_wait" or not rec.legs:
            self.skipTest(f"combo routed to {rec.strategy_key} — not a prefill day")
        with patch("strategy.selector.get_recommendation", return_value=rec), \
             patch("schwab.auth.is_configured", return_value=False):
            draft = self.client.get("/api/position/open-draft").get_json()
        self.assertIsNone(draft.get("short_put_strike"))
        self.assertIsNone(draft.get("long_put_strike"))


class TestAC3OpenRoundtrip(_IsolatedApiCase):
    def _open(self, **extra):
        payload = {
            "strategy_key": "iron_condor",
            "underlying": "SPX",
            "short_strike": 6300, "long_strike": 6350,
            "short_put_strike": 5900, "long_put_strike": 5800,
            "expiry": "2026-09-11", "dte_at_entry": 45,
            "contracts": 1, "actual_premium": 12.0,
            **extra,
        }
        return self.client.post("/api/position/open", json=payload)

    def test_put_pair_lands_in_ledger_and_state(self):
        res = self._open()
        self.assertEqual(res.status_code, 200, res.get_json())
        # ledger open 事件
        events = [json.loads(l) for l in tlog.TRADE_LOG_FILE.read_text().splitlines()]
        ev = next(e for e in events if e["event"] == "open")
        self.assertEqual(ev["short_put_strike"], 5900)
        self.assertEqual(ev["long_put_strike"], 5800)
        sides = [l["side"] for l in ev["legs"]]
        self.assertIn("short_put", sides)
        self.assertIn("long_put", sides)
        # state 持仓
        pos = (state_mod.read_all_positions() or {}).get("positions") or []
        self.assertEqual(pos[0].get("short_put_strike"), 5900)
        self.assertEqual(pos[0].get("long_put_strike"), 5800)

    def test_bps_open_writes_no_put_values(self):
        res = self._open(strategy_key="bull_put_spread",
                         short_strike=7000, long_strike=6800,
                         short_put_strike=None, long_put_strike=None,
                         actual_premium=8.5, dte_at_entry=30, expiry="2026-08-27")
        self.assertEqual(res.status_code, 200, res.get_json())
        events = [json.loads(l) for l in tlog.TRADE_LOG_FILE.read_text().splitlines()]
        ev = next(e for e in events if e["event"] == "open")
        self.assertIsNone(ev.get("short_put_strike"))
        self.assertIsNone(ev.get("long_put_strike"))
        self.assertEqual([l["side"] for l in ev["legs"]], ["short", "long"])

    def test_entry_risk_uses_put_pair(self):
        res = self.client.get(
            "/api/position/entry-risk?strategy_key=iron_condor"
            "&short_strike=6300&long_strike=6350&premium=12"
            "&contracts=1&short_put_strike=5900&long_put_strike=5800")
        data = res.get_json()
        self.assertEqual(data["order_max_loss_usd"], 8800.0)


class TestAC4UiSourceLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (REPO / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def test_ic_form_block_wired(self):
        for token in ("open-short-put-strike", "open-long-put-strike",
                      "updateIcLegVisibility", "ic-only",
                      "scan-short-put-wrap", "scan-long-put-wrap",
                      "short_put_leg", "long_put_leg", "SCAN_SLOT_INPUTS"):
            self.assertIn(token, self.spx, token)

    def test_deviation_fields_cover_put_wings(self):
        self.assertIn("{ field: 'short_put_strike', id: 'open-short-put-strike', numeric: true }", self.spx)
        self.assertIn("{ field: 'long_put_strike', id: 'open-long-put-strike', numeric: true }", self.spx)

    def test_submit_payload_carries_put_pair(self):
        self.assertIn("short_put_strike: isIcKey(strategyKey)", self.spx)


if __name__ == "__main__":
    unittest.main()
