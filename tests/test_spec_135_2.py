"""SPEC-135.2 — 账户级容量线合图（Q091 定稿 $238k 进代码）.

AC coverage:
  常数单一来源（238 容量字面量仅 capacity.py）      → SingleSourceTests
  used_defined_risk 与 SPEC-129 家族机制同源一致    → SameTruthTests
  7/7 生产向量 76,600/238,000 = 32.2%              → SameTruthTests
  Lane A ④ 容量行（人话 + trace 纯附加 135.1 合同）  → LaneATests
  表单风险区同条（entry-risk 端点 + UI）            → EntryRiskTests / UiAuditTests
  display-only（零门逻辑耦合）                      → SingleSourceTests
  strict-JSON                                      → EntryRiskTests
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.capacity as cap
import strategy.state as state_mod

ROOT = Path(__file__).resolve().parents[1]


class SingleSourceTests(unittest.TestCase):
    def test_capacity_literal_only_in_capacity_py(self) -> None:
        """AC: 全仓生产代码中 238k 容量字面量仅 capacity.py 一处。"""
        pat = re.compile(r"238[_,]?000")
        offenders = []
        for d in ("strategy", "web", "notify", "production", "scripts", "logs"):
            for p in (ROOT / d).rglob("*.py"):
                if p.name == "capacity.py":
                    continue
                if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                    offenders.append(str(p))
        for p in (ROOT / "web" / "templates").glob("*.html"):
            if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(str(p))
        self.assertEqual(offenders, [], "容量字面量出现在 capacity.py 之外")
        self.assertEqual(cap.CRASH_DEPLOYABLE_DR_USD, 238_000.0)
        # 派生自洽：excess − buffer ≈ deployable（Q091 取整口径）
        self.assertAlmostEqual(cap.Q091_CRASH_EXCESS_USD - cap.CRASH_BUFFER_USD,
                               cap.CRASH_DEPLOYABLE_DR_USD, delta=1_000)

    def test_provenance_and_ratify_path_documented(self) -> None:
        src = (ROOT / "strategy" / "capacity.py").read_text(encoding="utf-8")
        for token in ("Q091 P0 RATIFIED", "SPEC-111 §4-B", "PM ratify",
                      "q091_p0_memo"):
            self.assertIn(token, src)

    def test_display_only_no_gate_coupling(self) -> None:
        """display-only：selector/治理不 import capacity。"""
        import inspect
        import strategy.bcd_governance as gov
        import strategy.selector as sel
        for mod in (sel, gov):
            self.assertNotIn("strategy.capacity", inspect.getsource(mod))
        # capacity 自身不做任何 veto/block 判定
        src = (ROOT / "strategy" / "capacity.py").read_text(encoding="utf-8")
        for token in ("blocked", "reject", "veto"):
            self.assertNotIn(token, src.lower())


class SameTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig_state = state_mod.STATE_FILE
        state_mod.STATE_FILE = os.path.join(self.tmp.name, "pos.json")

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self._orig_state

    def _seed_77_book(self) -> None:
        """7/7 实账：6/3 双仓 BCD（debit $383 ×1 各一），used = $76,600。"""
        for tid, acct in (("2026-06-03_bcd_001", "schwab"), ("2026-06-03_bcd_002", "etrade")):
            state_mod.write_state("Bull Call Diagonal", "SPX",
                                  strategy_key="bull_call_diagonal", account=acct,
                                  trade_id=tid, short_strike=7750, long_strike=7300,
                                  expiry="2026-07-17", long_expiry="2026-08-31",
                                  contracts=1, actual_premium=-383.0)

    def test_77_production_vector(self) -> None:
        """AC: 76,600 / 238,000 = 32.2%（7/7 生产向量）。"""
        self._seed_77_book()
        out = cap.used_defined_risk()
        self.assertAlmostEqual(out["used_usd"], 76_600.0, places=2)
        self.assertEqual(out["capacity_usd"], 238_000.0)
        self.assertAlmostEqual(out["pct"], round(76_600 / 238_000 * 100, 1))
        self.assertAlmostEqual(out["pct"], 32.2, places=1)
        self.assertEqual(len(out["positions"]), 2)

    def test_same_truth_as_spec129_family_mechanism(self) -> None:
        """AC 同源：used == Σ 各家族 family_open_exposure（同一 exposure 函数），
        且 capacity.py 源码零本地 max-loss 公式（禁旁路重推）。"""
        self._seed_77_book()
        # 加一笔跨家族 credit spread
        state_mod.write_state("Bull Put Spread", "SPX", strategy_key="bull_put_spread",
                              account="schwab", trade_id="X1", short_strike=7300,
                              long_strike=7100, expiry="2026-08-07",
                              contracts=2, actual_premium=8.5)
        # 上面 write_state 不同策略会重建 state——重新 seed 到同一 state
        raw = state_mod._load_raw()
        if len(raw.get("positions", [])) < 3:   # 不同策略触发了 fresh state
            self._seed_77_book()
            raw = state_mod._load_raw()
            raw["positions"].append({
                "trade_id": "X1", "account": "schwab",
                "strategy_key": "bull_put_spread", "short_strike": 7300,
                "long_strike": 7100, "expiry": "2026-08-07",
                "contracts": 2, "actual_premium": 8.5})
            state_mod._save(raw)
        from strategy.exposure import family_open_exposure
        fam_sum = (family_open_exposure("bull_call_diagonal")["family_open_max_loss_usd"]
                   + family_open_exposure("bull_put_spread")["family_open_max_loss_usd"])
        out = cap.used_defined_risk()
        self.assertAlmostEqual(out["used_usd"], fam_sum, places=2)
        # 独立手算：2×383×100 + (200−8.5)×100×2
        self.assertAlmostEqual(out["used_usd"],
                               2 * 383 * 100 + (200 - 8.5) * 100 * 2, places=2)
        src = (ROOT / "strategy" / "capacity.py").read_text(encoding="utf-8")
        self.assertIn("from strategy.exposure import order_max_loss_usd", src)
        # 禁旁路重推：capacity.py 不得含本地 max-loss 公式实现痕迹
        # （公式实现变量唯一住 exposure.py；docstring 的公式说明不算实现）
        for token in ("short_k", "long_k", "premium_val", "abs(_num", "- premium"):
            self.assertNotIn(token, src)

    def test_fail_soft_empty_book(self) -> None:
        out = cap.used_defined_risk()
        self.assertEqual(out["used_usd"], 0.0)
        self.assertEqual(out["pct"], 0.0)


class LaneATests(unittest.TestCase):
    def test_funding_trace_carries_capacity_line(self) -> None:
        """Lane A ④ 容量行：人话文案 + hover 三件套 + 135.1 字段合同。"""
        from strategy.decision_trace import funding_trace
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 152_346.01, "source": "live",
                                 "breakdown": {}, "error": None}), \
             patch("strategy.cash_budget_governance.get_open_cash_collateral_total_usd",
                   return_value={"total": 76_600.0}), \
             patch("strategy.exposure.evaluate_exposure_degrade",
                   return_value={"degraded": False, "pct_of_pool": 10.0,
                                 "family_open_max_loss_usd": 0.0,
                                 "threshold_pct": 30.0, "note": None}), \
             patch("strategy.capacity.used_defined_risk",
                   return_value={"used_usd": 76_600.0, "capacity_usd": 238_000.0,
                                 "buffer_usd": 100_000.0, "pct": 32.2,
                                 "positions": [{"trade_id": "A"}, {"trade_id": "B"}]}):
            nodes = funding_trace("bull_call_diagonal")
        capn = next(n for n in nodes if n["check"] == "account_dr_capacity")
        # 人话铁律：spec 指定句式（已用/可部署/崩盘日安全垫）
        self.assertIn("账户级 defined-risk：已用 $76,600 / 可部署 $238,000（32%）",
                      capn["label_human"])
        self.assertIn("崩盘日安全垫 $100,000 已预留", capn["label_human"])
        self.assertEqual(capn["code_ref"], "Q091")
        self.assertIn("display-only", capn["detail"])
        self.assertTrue(capn["inputs"])
        # 135.1 纯附加合同：字段集 = 基础 8 + kind/stage
        from tests.test_spec_135_1 import BASE_FIELDS
        self.assertEqual(set(capn.keys()), BASE_FIELDS | {"kind", "stage"})
        self.assertEqual(capn["kind"], "evidence")
        self.assertEqual(capn["stage"], "capital")

    def test_capacity_line_fail_soft(self) -> None:
        from strategy.decision_trace import funding_trace
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   side_effect=RuntimeError("down")), \
             patch("strategy.exposure.evaluate_exposure_degrade",
                   side_effect=RuntimeError("down")), \
             patch("strategy.capacity.used_defined_risk",
                   side_effect=RuntimeError("down")):
            nodes = funding_trace("bull_put_spread")
        capn = next(n for n in nodes if n["check"] == "account_dr_capacity")
        self.assertEqual(capn["outcome"], "info")     # 不拦


class EntryRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig_state = state_mod.STATE_FILE
        state_mod.STATE_FILE = os.path.join(self.tmp.name, "pos.json")
        for tid, acct in (("2026-06-03_bcd_001", "schwab"), ("2026-06-03_bcd_002", "etrade")):
            state_mod.write_state("Bull Call Diagonal", "SPX",
                                  strategy_key="bull_call_diagonal", account=acct,
                                  trade_id=tid, short_strike=7750, long_strike=7300,
                                  expiry="2026-07-17", long_expiry="2026-08-31",
                                  contracts=1, actual_premium=-383.0)

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self._orig_state

    def test_entry_risk_carries_account_dr_with_post_entry(self) -> None:
        from web.server import app
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 152_346.01, "source": "live",
                                 "breakdown": {}, "error": None}):
            res = app.test_client().get(
                "/api/position/entry-risk?strategy_key=bull_call_diagonal"
                "&short_strike=7700&long_strike=7200&premium=-400&contracts=1")
        self.assertEqual(res.status_code, 200)
        raw = res.get_data(as_text=True)
        json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(AssertionError(s)))
        adr = res.get_json()["account_dr"]
        self.assertAlmostEqual(adr["used_usd"], 76_600.0, places=2)
        self.assertEqual(adr["capacity_usd"], 238_000.0)
        self.assertAlmostEqual(adr["pct"], 32.2, places=1)
        # 本单成交后：76,600 + 40,000 = 116,600 → 49.0%
        self.assertAlmostEqual(adr["post_entry_used_usd"], 116_600.0, places=2)
        self.assertAlmostEqual(adr["post_entry_pct"],
                               round(116_600 / 238_000 * 100, 1), places=1)

    def test_capacity_failure_fails_soft(self) -> None:
        from web.server import app
        with patch("strategy.capacity.used_defined_risk",
                   side_effect=RuntimeError("boom")), \
             patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 100_000.0, "source": "live",
                                 "breakdown": {}, "error": None}):
            res = app.test_client().get(
                "/api/position/entry-risk?strategy_key=bull_put_spread"
                "&short_strike=7000&long_strike=6900&premium=8&contracts=1")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.get_json()["account_dr"])   # 其余字段照常


class UiAuditTests(unittest.TestCase):
    def test_form_capacity_line_wired(self) -> None:
        spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        for token in ("account_dr", "账户级 defined-risk（本单成交后）",
                      "崩盘日安全垫", "可部署"):
            self.assertIn(token, spx)
        # 单一来源：模板零容量字面量（数值全部来自 API）
        self.assertNotIn("238", spx.replace("spec132_1", "").replace("v=spec", ""))


if __name__ == "__main__":
    unittest.main()
