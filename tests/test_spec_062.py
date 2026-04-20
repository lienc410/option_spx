from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backtest.research_views as research_views_mod
import web.server as server_mod
from backtest.engine import BacktestResult, Trade
from strategy.selector import StrategyName
from web.server import app


def make_trade(
    *,
    strategy: StrategyName,
    entry_date: str,
    exit_date: str,
    exit_pnl: float,
    exit_reason: str = "roll_21dte",
) -> Trade:
    return Trade(
        strategy=strategy,
        underlying="SPX",
        entry_date=entry_date,
        exit_date=exit_date,
        entry_spx=5000.0,
        exit_spx=5050.0,
        entry_vix=18.5,
        entry_credit=3.2,
        exit_pnl=exit_pnl,
        exit_reason=exit_reason,
        dte_at_entry=45,
        dte_at_exit=21,
        spread_width=50.0,
        option_premium=320.0,
        bp_per_contract=4680.0,
        contracts=1.0,
        total_bp=4680.0,
        bp_pct_account=3.12,
    )


class Spec062ResearchViewsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_build_research_views_emits_expected_keys_and_filtered_trades(self) -> None:
        baseline_trade = make_trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            entry_date="2026-01-05",
            exit_date="2026-01-18",
            exit_pnl=450.0,
        )
        open_trade = make_trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            entry_date="2026-01-20",
            exit_date="2026-02-28",
            exit_pnl=0.0,
            exit_reason="end_of_backtest",
        )
        q015_trade = make_trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            entry_date="2026-02-03",
            exit_date="2026-02-20",
            exit_pnl=225.0,
        )
        q015_out_of_band = make_trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            entry_date="2026-02-10",
            exit_date="2026-02-24",
            exit_pnl=200.0,
        )
        q016_trade = make_trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            entry_date="2026-03-02",
            exit_date="2026-03-18",
            exit_pnl=310.0,
        )
        q016_non_recovery = make_trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            entry_date="2026-03-11",
            exit_date="2026-03-27",
            exit_pnl=150.0,
        )
        spec064_trade = make_trade(
            strategy=StrategyName.IRON_CONDOR_HV,
            entry_date="2026-04-09",
            exit_date="2026-04-24",
            exit_pnl=2410.64,
        )
        spec064_disabled_overlap = make_trade(
            strategy=StrategyName.IRON_CONDOR_HV,
            entry_date="2026-04-24",
            exit_date="2026-05-29",
            exit_pnl=1855.14,
        )

        baseline_result = BacktestResult(
            trades=[baseline_trade, open_trade, q015_trade, q015_out_of_band, spec064_trade, spec064_disabled_overlap],
            metrics={},
            signals=[
                {"date": "2026-02-03", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "BULLISH", "ivp": 53.0},
                {"date": "2026-02-10", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "BULLISH", "ivp": 56.0},
                {"date": "2026-03-01", "regime": "HIGH_VOL", "iv_signal": "HIGH", "trend": "NEUTRAL"},
                {"date": "2026-03-02", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH"},
                {"date": "2026-03-03", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "NEUTRAL"},
                {"date": "2026-03-04", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "NEUTRAL"},
                {"date": "2026-03-05", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "NEUTRAL"},
                {"date": "2026-03-06", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "NEUTRAL"},
                {"date": "2026-03-07", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "NEUTRAL"},
                {"date": "2026-03-11", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH"},
            ],
        )
        ivp55_result = BacktestResult(
            trades=[baseline_trade, q015_out_of_band],
            metrics={},
            signals=[
                {"date": "2026-02-03", "ivp": 53.0},
                {"date": "2026-02-10", "ivp": 56.0},
            ],
        )
        dza_result = BacktestResult(
            trades=[baseline_trade, q016_trade, q016_non_recovery],
            metrics={},
            signals=[],
        )
        no_aftermath_result = BacktestResult(
            trades=[baseline_trade, spec064_disabled_overlap],
            metrics={},
            signals=[],
        )

        with (
            patch.object(research_views_mod, "run_backtest", return_value=baseline_result),
            patch.object(research_views_mod, "_run_with_bps_upper", return_value=ivp55_result),
            patch.object(research_views_mod, "_run_dead_zone_a_variant", return_value=dza_result),
            patch.object(research_views_mod, "_run_with_aftermath_disabled", return_value=no_aftermath_result),
            patch.object(research_views_mod, "_params_hash", return_value="abc123def0"),
        ):
            payload = research_views_mod.build_research_views()

        self.assertEqual(payload["params_hash"], "abc123def0")
        self.assertEqual(
            set(payload["views"].keys()),
            {"baseline", "q015_ivp55_marginal", "q016_dza_recovery_bps", "spec064_aftermath_ic_hv"},
        )

        baseline_trades = payload["views"]["baseline"]["trades"]
        self.assertEqual(len(baseline_trades), 5)
        self.assertEqual(
            {t["entry_date"] for t in baseline_trades},
            {"2026-01-05", "2026-02-03", "2026-02-10", "2026-04-09", "2026-04-24"},
        )
        self.assertTrue(all(t["source_view"] == "baseline" for t in baseline_trades))

        q015_trades = payload["views"]["q015_ivp55_marginal"]["trades"]
        self.assertEqual(len(q015_trades), 1)
        self.assertEqual(q015_trades[0]["entry_date"], "2026-02-03")
        self.assertEqual(q015_trades[0]["source_view"], "q015_ivp55_marginal")

        q016_trades = payload["views"]["q016_dza_recovery_bps"]["trades"]
        self.assertEqual(len(q016_trades), 1)
        self.assertEqual(q016_trades[0]["entry_date"], "2026-03-02")
        self.assertEqual(q016_trades[0]["source_view"], "q016_dza_recovery_bps")

        spec064_trades = payload["views"]["spec064_aftermath_ic_hv"]["trades"]
        self.assertEqual(len(spec064_trades), 1)
        self.assertEqual(spec064_trades[0]["entry_date"], "2026-04-09")
        self.assertEqual(spec064_trades[0]["strategy"], StrategyName.IRON_CONDOR_HV.value)
        self.assertEqual(spec064_trades[0]["source_view"], "spec064_aftermath_ic_hv")

    def test_generate_research_views_writes_json_file(self) -> None:
        output = Path(self.tmpdir.name) / "research_views.json"
        payload = {
            "generated_at": "2026-04-19T15:00:00",
            "params_hash": "abc123def0",
            "views": {
                "baseline": {"label": "Baseline (Production)", "description": "prod", "trades": []},
                "q015_ivp55_marginal": {"label": "Q015", "description": "ivp55", "trades": []},
                "q016_dza_recovery_bps": {"label": "Q016", "description": "dza", "trades": []},
                "spec064_aftermath_ic_hv": {"label": "SPEC-064", "description": "aftermath", "trades": []},
            },
        }
        with patch.object(research_views_mod, "build_research_views", return_value=payload):
            path = research_views_mod.generate_research_views(output)

        self.assertEqual(path, output)
        self.assertTrue(output.exists())
        self.assertEqual(json.loads(output.read_text()), payload)


class Spec062ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.orig_research_views_file = server_mod._RESEARCH_VIEWS_FILE
        self.client = app.test_client()

    def tearDown(self) -> None:
        server_mod._RESEARCH_VIEWS_FILE = self.orig_research_views_file

    def test_api_research_views_returns_empty_when_file_missing(self) -> None:
        server_mod._RESEARCH_VIEWS_FILE = Path(self.tmpdir.name) / "missing.json"
        res = self.client.get("/api/research/views")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.get_json(),
            {"empty": True, "message": "Run: python -m backtest.research_views generate"},
        )

    def test_api_research_views_returns_generated_payload(self) -> None:
        payload = {
            "generated_at": "2026-04-19T15:00:00",
            "params_hash": "abc123def0",
            "views": {
                "baseline": {"label": "Baseline (Production)", "description": "prod", "trades": []},
                "q015_ivp55_marginal": {"label": "Q015", "description": "ivp55", "trades": []},
                "q016_dza_recovery_bps": {"label": "Q016", "description": "dza", "trades": []},
                "spec064_aftermath_ic_hv": {"label": "SPEC-064", "description": "aftermath", "trades": []},
            },
        }
        target = Path(self.tmpdir.name) / "research_views.json"
        target.write_text(json.dumps(payload))
        server_mod._RESEARCH_VIEWS_FILE = target

        res = self.client.get("/api/research/views")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), payload)


if __name__ == "__main__":
    unittest.main()
