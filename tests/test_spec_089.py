import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import notify.telegram_bot as bot_mod
import strategy.state as state_mod
from etrade import auth as etrade_auth
from etrade import client as etrade_client
from web.server import app


class _FakeOAuth:
    def __init__(self, *_args):
        self.resource_owner_key = "req-token"
        self.session = SimpleNamespace(
            _client=SimpleNamespace(
                client=SimpleNamespace(
                    resource_owner_secret="req-secret",
                )
            )
        )

    def get_request_token(self):
        return "https://example.com/auth?oauth_token=req-token"

    def get_access_token(self, verifier):
        return {
            "oauth_token": f"acc-{verifier}",
            "oauth_token_secret": "acc-secret",
        }

    def renew_access_token(self):
        return {
            "oauth_token": "renewed-token",
            "oauth_token_secret": "renewed-secret",
        }


class _FakeAccounts:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_accounts(self):
        return {
            "AccountListResponse": {
                "Accounts": {
                    "Account": [{"accountIdKey": "acct-key-1"}]
                }
            }
        }

    def get_account_balance(self, _account_id):
        return {
            "BalanceResponse": {
                "Computed": {
                    "cashAvailableForWithdrawal": "18000",
                    "marginBalance": "11000",
                    "marginBuyingPower": "90000",
                    "RealTimeValues": {"netMv": "250000"},
                    "PortfolioMargin": {"totalMarginRqmts": "42000"},
                },
            }
        }

    def get_account_portfolio(self, _account_id, resp_format="xml"):
        return {
            "PortfolioResponse": {
                "AccountPortfolio": [{
                    "Position": [
                        {
                            "Product": {"symbol": "SPY", "securityType": "EQ"},
                            "quantity": 100,
                            "marketValue": 51234,
                            "totalGain": 1234,
                        },
                        {
                            "Product": {"symbol": "TLT", "securityType": "EQ"},
                            "quantity": 25,
                            "marketValue": 2400,
                            "totalGain": -50,
                        },
                    ]
                }]
            }
        }


class Spec089Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()

        self.orig_state_file = state_mod.STATE_FILE
        state_mod.STATE_FILE = str(Path(self.tmpdir.name) / "current_position.json")

        self.orig_token_file = etrade_auth.TOKEN_FILE
        self.orig_alert_file = etrade_auth.ALERT_STATE_FILE
        etrade_auth.TOKEN_FILE = Path(self.tmpdir.name) / "etrade_token.json"
        etrade_auth.ALERT_STATE_FILE = Path(self.tmpdir.name) / "etrade_alert_state.json"
        etrade_client._CACHE.clear()

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state_file
        etrade_auth.TOKEN_FILE = self.orig_token_file
        etrade_auth.ALERT_STATE_FILE = self.orig_alert_file

    def test_ac1_auth_flow_persists_and_reloadable(self) -> None:
        fake = SimpleNamespace(ETradeOAuth=_FakeOAuth)
        with patch.object(etrade_auth, "consumer_key", return_value="key"), \
             patch.object(etrade_auth, "consumer_secret", return_value="secret"), \
             patch.object(etrade_auth, "_oauth1_session_class", return_value=lambda *args, **kwargs: SimpleNamespace()), \
             patch.object(etrade_auth, "_load_pyetrade", return_value=fake):
            request_payload = etrade_auth.request_token()
            self.assertEqual(request_payload["request_oauth_token"], "req-token")
            access_payload = etrade_auth.get_access_token("verifier-123")

        persisted = etrade_auth.load_token()
        self.assertEqual(persisted["oauth_token"], "acc-verifier-123")
        self.assertEqual(access_payload["oauth_token_secret"], "acc-secret")
        with patch.object(etrade_auth, "consumer_key", return_value="key"), \
             patch.object(etrade_auth, "consumer_secret", return_value="secret"):
            self.assertTrue(etrade_auth.is_token_valid())

    def test_ac2_client_returns_data_and_fail_soft_when_token_invalid(self) -> None:
        etrade_auth.save_token({
            "oauth_token": "token",
            "oauth_token_secret": "secret",
            "expires_at": "2099-01-01T00:00:00-05:00",
        })
        fake = SimpleNamespace(ETradeAccounts=_FakeAccounts)
        with patch.object(etrade_client, "is_configured", return_value=True), \
             patch.object(etrade_client, "_load_pyetrade", return_value=fake), \
             patch.object(etrade_client, "consumer_key", return_value="key"), \
             patch.object(etrade_client, "consumer_secret", return_value="secret"), \
             patch.object(etrade_client, "is_token_valid", return_value=True):
            balances = etrade_client.get_account_balances()
            positions = etrade_client.get_account_positions()

        self.assertEqual(balances["maintenance_margin"], 42000)
        self.assertEqual(len(positions["positions"]), 2)
        self.assertFalse(balances["stale"])
        self.assertFalse(positions["stale"])

        with patch.object(etrade_client, "is_configured", return_value=True), \
             patch.object(etrade_client, "is_token_valid", return_value=False):
            soft = etrade_client.get_account_balances()
        self.assertTrue(soft["stale"])
        self.assertFalse(soft["authenticated"])

    def test_ac3_routes_return_json_and_auth_redirects(self) -> None:
        with patch("etrade.client.get_account_balances", return_value={
            "configured": True,
            "authenticated": True,
            "maintenance_margin": 1000,
            "net_liquidation": 10000,
            "stale": False,
        }), patch("etrade.client.get_account_positions", return_value={
            "configured": True,
            "authenticated": True,
            "positions": [{"symbol": "SPY"}],
            "stale": False,
        }):
            bal_res = self.client.get("/api/etrade/balances")
            pos_res = self.client.get("/api/etrade/positions")
        self.assertEqual(bal_res.status_code, 200)
        self.assertEqual(pos_res.status_code, 200)
        self.assertEqual(bal_res.get_json()["maintenance_margin"], 1000)
        self.assertEqual(pos_res.get_json()["positions"][0]["symbol"], "SPY")

        with patch("etrade.auth.request_token", return_value={"authorize_url": "https://example.com/auth"}):
            start_res = self.client.get("/etrade/auth")
        self.assertEqual(start_res.status_code, 302)
        self.assertEqual(start_res.location, "https://example.com/auth")

        with patch("etrade.auth.get_access_token", return_value={"oauth_token": "ok"}):
            cb_res = self.client.get("/etrade/auth?oauth_verifier=abc123")
        self.assertEqual(cb_res.status_code, 302)
        self.assertTrue(cb_res.location.endswith("/"))

    def test_ac4_and_ac5_token_renew_fail_soft_and_single_alert_per_invalid_period(self) -> None:
        bot = AsyncMock()
        etrade_auth.save_alert_state({"invalid": True, "reason": "token_invalid", "alert_sent": False, "updated_at": None})

        import asyncio

        with patch("etrade.auth.renew_access_token", return_value={"ok": False, "reason": "expired"}), \
             patch("etrade.auth.is_token_valid", return_value=False):
            asyncio.run(bot_mod.scheduled_etrade_token_renewal(bot, "chat"))
            asyncio.run(bot_mod.scheduled_etrade_token_renewal(bot, "chat"))

        self.assertEqual(bot.send_message.await_count, 1)

        with patch("etrade.auth.is_token_valid", return_value=True):
            asyncio.run(bot_mod._maybe_send_etrade_token_alert(bot, "chat"))
        self.assertFalse(etrade_auth.ALERT_STATE_FILE.exists())

    def test_ac6_portfolio_home_and_summary_fail_soft_when_etrade_unavailable(self) -> None:
        with patch("web.portfolio_surface._etrade_margin_data", return_value=None), \
             patch("web.portfolio_surface._schwab_margin_data", return_value={"nlv": 400000.0, "maintenance_margin": 80000.0}):
            summary_res = self.client.get("/api/portfolio/summary")
        self.assertEqual(summary_res.status_code, 200)
        summary = summary_res.get_json()
        self.assertEqual(summary["rails"]["etrade_pm"]["status"], "unavailable")
        self.assertIsNone(summary["bp_usage_by_bucket"]["etrade_maintenance_bp_pct"])

        home_res = self.client.get("/")
        text = home_res.get_data(as_text=True)
        self.assertIn("E-Trade PM Account", text)
        self.assertIn("Read-only balances + positions", text)

    def test_ac6_combined_bp_uses_schwab_plus_etrade(self) -> None:
        with patch("web.portfolio_surface._etrade_margin_data", return_value={
            "nlv": 200000.0,
            "maintenance_margin": 30000.0,
            "balances": {"net_liquidation": 200000.0, "maintenance_margin": 30000.0},
        }), patch("web.portfolio_surface._schwab_margin_data", return_value={
            "nlv": 400000.0,
            "maintenance_margin": 80000.0,
        }):
            res = self.client.get("/api/portfolio/summary")
        data = res.get_json()
        self.assertEqual(data["bp_basis"], 600000.0)
        self.assertEqual(data["bp_usage_by_bucket"]["etrade_maintenance_bp_pct"], 5.0)
        self.assertEqual(data["account_breakdown"]["combined_maintenance_margin"], 110000.0)

    def test_maintenance_margin_field_mapping_invariants(self) -> None:
        """SPEC-107 followup 2026-05-27 — guard against silent field drift.

        ETrade `totalMarginRqmts` is the authoritative maintenance margin
        requirement. Historically the fallback chain also accepted
        `maintenanceCall` (a $ call amount, normally 0) and `marginBalance`
        (the outstanding margin LOAN balance — not a requirement). If
        ETrade's response changes shape, falling back to loan balance would
        misreport BP usage by 100%+. This test pins the contract:

          - totalMarginRqmts wins if present
          - totalHouseRequirement wins if only it is present
          - both absent → maintenance_margin is None (no fake fallback)
          - marginBalance / maintenanceCall must NEVER substitute for
            maintenance_margin
        """
        normalize = etrade_client._normalize_balance_payload

        # Case 1: totalMarginRqmts wins
        n = normalize({"BalanceResponse": {"Computed": {
            "PortfolioMargin": {
                "totalMarginRqmts": "141833.06",
                "totalHouseRequirement": "120000.00",
            },
            "marginBalance": "22792.52",
        }}})
        self.assertAlmostEqual(n["maintenance_margin"], 141833.06, places=2)

        # Case 2: totalHouseRequirement is fallback when totalMarginRqmts absent
        n = normalize({"BalanceResponse": {"Computed": {
            "PortfolioMargin": {"totalHouseRequirement": "99999.00"},
            "marginBalance": "22792.52",
        }}})
        self.assertAlmostEqual(n["maintenance_margin"], 99999.00, places=2)

        # Case 3: both requirement fields absent → None, NOT marginBalance
        n = normalize({"BalanceResponse": {"Computed": {
            "PortfolioMargin": {},
            "marginBalance": "22792.52",
            "maintenanceCall": "5000.00",
        }}})
        self.assertIsNone(
            n["maintenance_margin"],
            "must NOT fall back to marginBalance or maintenanceCall — those "
            "are loan balance / call amount, not maintenance requirement",
        )

        # Case 4: defensive — empty payload also returns None, no crash
        n = normalize({"BalanceResponse": {"Computed": {}}})
        self.assertIsNone(n["maintenance_margin"])

    def test_per_account_bp_sums_all_positions_not_just_first(self) -> None:
        """Regression for 2026-05-27 bug: an account holding multiple
        concurrent BPS spreads (e.g. ETrade with 2× 7300/7000 + 1× 7200/6950)
        was previously under-reported because `next()` only captured the
        first state record. _sum_spx_bp_usage must aggregate all entries.
        """
        from web.portfolio_surface import _sum_spx_bp_usage

        # Live state at time of fix (2026-05-27 production):
        etrade_positions = [
            {
                "strategy_key": "bull_put_spread",
                "account": "etrade",
                "short_strike": 7300,
                "long_strike": 7000,
                "contracts": 2,
            },
            {
                "strategy_key": "bull_put_spread",
                "account": "etrade",
                "short_strike": 7200,
                "long_strike": 6950,
                "contracts": 1,
            },
        ]
        basis = 909_000.0  # combined NLV approx

        result = _sum_spx_bp_usage(etrade_positions, basis)

        # Spread 1: 300 width × 2 ct × $100 = $60,000
        # Spread 2: 250 width × 1 ct × $100 = $25,000
        # Total: $85,000
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["bp_usage_dollars"], 85_000.0)
        self.assertEqual(result["n_positions"], 2)

        # Schwab side same logic, larger size
        schwab_positions = [
            {"strategy_key": "bull_put_spread", "account": "schwab",
             "short_strike": 7300, "long_strike": 7000, "contracts": 4},
            {"strategy_key": "bull_put_spread", "account": "schwab",
             "short_strike": 7200, "long_strike": 6950, "contracts": 1},
        ]
        result = _sum_spx_bp_usage(schwab_positions, basis)
        # 300 × 4 × 100 = $120,000 + 250 × 1 × 100 = $25,000 = $145,000
        self.assertEqual(result["bp_usage_dollars"], 145_000.0)
        self.assertEqual(result["n_positions"], 2)

        # Empty / None → status none
        self.assertEqual(_sum_spx_bp_usage([], basis)["status"], "none")
        self.assertEqual(_sum_spx_bp_usage(None, basis)["status"], "none")

        # Insufficient-data record alone → insufficient_data, NOT $0 disguise
        result = _sum_spx_bp_usage(
            [{"strategy_key": "bull_put_spread", "account": "etrade"}],  # no strikes
            basis,
        )
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["bp_usage_dollars"])

    def test_ac7_etrade_module_does_not_call_market_data_apis(self) -> None:
        source = Path("etrade/client.py").read_text() + "\n" + Path("etrade/auth.py").read_text()
        for forbidden in ("get_quote", "get_option_chain", "quotes", "chains", "marketdata"):
            self.assertNotIn(forbidden, source)

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_ac8_recommendation_shape_unchanged(self, mock_get_recommendation, _mock_hours) -> None:
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy
        from tests.test_strategy_unification import make_iv, make_trend, make_vix

        mock_get_recommendation.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )

        res = self.client.get("/api/recommendation")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("etrade", json.dumps(data).lower())


if __name__ == "__main__":
    unittest.main()
