import unittest
from unittest.mock import patch


class Spec102HvLadderFrontendTests(unittest.TestCase):
    def test_pages_and_archive_tab_are_available(self):
        from web.server import app

        with app.test_client() as client:
            live = client.get("/hvladder")
            backtest = client.get("/hvladder_backtest")
            archive = client.get("/es-backtest")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(backtest.status_code, 200)
        self.assertEqual(archive.status_code, 200)
        self.assertIn(b"paper/shadow", live.data)
        self.assertIn(b"Crisis Windows", backtest.data)
        # SPEC-125 D8: "[archived]" wording removed — the strategy is active
        # (SPEC-061 single-lot); only the embedded TAB moved to dedicated pages
        self.assertIn("Stress Put Ladder → moved".encode(), archive.data)
        self.assertIn(b"/hvladder_backtest", archive.data)

    def test_hvladder_apis_shape(self):
        from web.server import app

        with app.test_client() as client:
            live = client.get("/api/hvladder/live").get_json()
            paper = client.get("/api/hvladder/paper_trades?limit=5").get_json()
            stats = client.get("/api/hvladder/stats").get_json()

        self.assertIn("vix_current", live)
        self.assertIn("vix_5td_avg", live)
        self.assertIn("gate_status", live)
        self.assertIn("signal_live", live)
        self.assertIn("trades", paper)
        self.assertIn("count", paper)
        self.assertIn("crisis_windows", stats)
        self.assertGreaterEqual(len(stats["crisis_windows"]), 3)

    def test_paper_trades_fail_soft_when_missing(self):
        from web.server import app

        with patch("web.server._load_hvlad_paper_trades", return_value=[]):
            with app.test_client() as client:
                payload = client.get("/api/hvladder/paper_trades").get_json()

        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["trades"], [])


if __name__ == "__main__":
    unittest.main()
