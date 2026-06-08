"""SPEC-115 Phase B — AC-7/8/9: T+1 IC close PnL logic."""
import unittest

from strategy.q041_t3_selector import compute_ic_close_pnl


def _entry():
    return {
        "K_short_put": 931, "K_long_put": 890,
        "K_short_call": 1013, "K_long_call": 1054,
        "net_credit_usd": 1420.0,
        "max_loss_usd": 2680.0,
    }


class TestICCloseLogic(unittest.TestCase):
    def test_ac7_neither_breached_full_credit(self):
        r = compute_ic_close_pnl(_entry(), s_exit=1000.0)
        self.assertIsNone(r["breached"])
        self.assertTrue(r["strikes_held"])
        self.assertAlmostEqual(r["paper_pnl_usd"], 1420.0)

    def test_ac8_short_put_breached(self):
        # s_exit 920 < K_put 931 → loss = min(2680, (931-920)*100=1100) = 1100
        # PnL = 1420 - 1100 = 320
        r = compute_ic_close_pnl(_entry(), s_exit=920.0)
        self.assertEqual(r["breached"], "put")
        self.assertFalse(r["strikes_held"])
        self.assertAlmostEqual(r["paper_pnl_usd"], 320.0)

    def test_ac9_short_call_breached(self):
        # s_exit 1025 > K_call 1013 → loss = min(2680, (1025-1013)*100=1200) = 1200
        # PnL = 1420 - 1200 = 220
        r = compute_ic_close_pnl(_entry(), s_exit=1025.0)
        self.assertEqual(r["breached"], "call")
        self.assertAlmostEqual(r["paper_pnl_usd"], 220.0)

    def test_deep_breach_capped_at_max_loss(self):
        # s_exit far below → loss capped at max_loss 2680 → PnL = 1420 - 2680 = -1260
        r = compute_ic_close_pnl(_entry(), s_exit=800.0)
        self.assertEqual(r["breached"], "put")
        self.assertAlmostEqual(r["paper_pnl_usd"], 1420.0 - 2680.0)

    def test_at_strike_boundary_held(self):
        # s_exit exactly at K_short_put → not < K_put → held
        r = compute_ic_close_pnl(_entry(), s_exit=931.0)
        self.assertIsNone(r["breached"])
        self.assertAlmostEqual(r["paper_pnl_usd"], 1420.0)


if __name__ == "__main__":
    unittest.main()
