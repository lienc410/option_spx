"""SPEC-115 Phase A — AC-5/6: q041_paper_telegram daily job + paper log.

AC-5: paper_log writes `blocked` events when cash gate rejects
AC-6: paper_log writes `open` events when K × 100 ≤ cap (mock low strike)
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import notify.q041_paper_telegram as job
import strategy.q041_selector as sel
import strategy.cash_budget_governance as cbg
import strategy.sleeve_governance as sg


def _mock_cash(total, source="live"):
    return {"total": total, "source": source, "breakdown": {}, "error": None}


def _mock_open(total):
    return {"total": total, "positions": []}


class TestPaperLog(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.chain_root = self.tmp / "chains"
        self.paper_log = self.tmp / "q041_paper_log.jsonl"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_chain(self, symbol: str, date_str: str, strike: float, delta: float, dte: int = 21):
        day_dir = self.chain_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        fname = symbol.replace("/", "_") + ".parquet"
        df = pd.DataFrame([{
            "option_type": "PUT", "delta": -abs(delta), "dte": dte,
            "strike": strike, "mid": 5.00,
        }])
        df.to_parquet(day_dir / fname, index=False)

    def _read_log_events(self):
        if not self.paper_log.exists():
            return []
        return [json.loads(l) for l in self.paper_log.read_text().splitlines() if l.strip()]

    # SPEC-138 F1 行为判定：夹具原来只 mock 了现金函数，没给治理 NLV basis。
    # 生产 evaluate_candidate 先解析 basis（live NLV），测试环境读不到 → 返回 R0
    # "basis_unavailable" 失败关闭（SPEC-118.2 有意行为：宁可 fail-closed 也不用
    # 虚构 $200k 账户算 cap）。所以两笔都因 R0 被拦——test_ac5 恰好期望 blocked
    # 就"蒙对"了（但拦的原因是 R0 不是 cash-cap R111），test_ac6 期望 open 就暴
    # 露了缺口。修法：补 basis mock（模拟生产 live NLV 可用），让 cash-collateral
    # cap 成为真正被测的门。非 code bug，非削弱——反而让两笔都测到正确的门。
    _BASIS = (500_000.0, False)

    def test_ac5_blocked_event_written(self):
        # GOOGL strike 366 → cash_need 36600 > cap → blocked（R111 cash-cap）
        self._write_chain("GOOGL", "2026-06-05", strike=366.0, delta=0.20)
        self._write_chain("AMZN", "2026-06-05", strike=252.0, delta=0.25)
        with patch.object(sel, "CHAIN_ROOT", self.chain_root), \
             patch.object(job, "PAPER_LOG", self.paper_log), \
             patch.object(sg, "_resolve_basis", return_value=self._BASIS), \
             patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            results = job.run("2026-06-05", force=True, dry_run=False)

        self.assertEqual(len(results), 2)
        events = self._read_log_events()
        self.assertEqual(len(events), 2)
        for ev in events:
            self.assertEqual(ev["event"], "blocked")
            self.assertFalse(ev["governance_decision"]["accepted"])
            # 现在确实是 cash-cap 拦的（R111），不再是 basis-unavailable R0
            self.assertEqual(ev["governance_decision"]["rule"], "R111")

    def test_ac6_open_event_when_under_cap(self):
        # Low strike $50 → cash_need $5,000 < cap → paper open
        self._write_chain("GOOGL", "2026-06-05", strike=50.0, delta=0.20)
        self._write_chain("AMZN", "2026-06-05", strike=50.0, delta=0.25)
        with patch.object(sel, "CHAIN_ROOT", self.chain_root), \
             patch.object(job, "PAPER_LOG", self.paper_log), \
             patch.object(sg, "_resolve_basis", return_value=self._BASIS), \
             patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            results = job.run("2026-06-05", force=True, dry_run=False)

        events = self._read_log_events()
        self.assertEqual(len(events), 2)
        for ev in events:
            self.assertEqual(ev["event"], "open")
            self.assertTrue(ev["governance_decision"]["accepted"])

    def test_dry_run_does_not_write(self):
        self._write_chain("GOOGL", "2026-06-05", strike=366.0, delta=0.20)
        self._write_chain("AMZN", "2026-06-05", strike=252.0, delta=0.25)
        with patch.object(sel, "CHAIN_ROOT", self.chain_root), \
             patch.object(job, "PAPER_LOG", self.paper_log), \
             patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            job.run("2026-06-05", force=True, dry_run=True)
        self.assertFalse(self.paper_log.exists())

    def test_non_trading_day_skips(self):
        with patch.object(job, "PAPER_LOG", self.paper_log):
            results = job.run("2026-05-25", force=False, dry_run=False)  # Memorial Day
        self.assertEqual(results, [])
        self.assertFalse(self.paper_log.exists())

    def test_telegram_format_blocked(self):
        results = [{
            "underlying": "GOOGL",
            "candidate": {"underlying": "GOOGL", "delta": 0.20, "dte": 21,
                          "short_strike": 366.0, "close": 4.50, "cash_need_usd": 36_600.0},
            "decision": {"accepted": False, "reason": "cash_collateral: post-entry cash $36,600 ..."},
        }]
        msg = job._format_telegram("2026-06-05", results)
        self.assertIn("📋 CSP 纸面信号", msg)  # SPEC-136：主文案零内部代号
        self.assertIn("GOOGL", msg)
        self.assertIn("blocked", msg)
        self.assertIn("36,600", msg)

    def test_telegram_format_no_candidate(self):
        results = [{"underlying": "AMZN", "candidate": None, "decision": None}]
        msg = job._format_telegram("2026-06-05", results)
        self.assertIn("no chain candidate", msg)


if __name__ == "__main__":
    unittest.main()
