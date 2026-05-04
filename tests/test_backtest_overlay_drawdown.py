import unittest
from pathlib import Path


class BacktestOverlayDrawdownTemplateTests(unittest.TestCase):
    def test_backtest_template_exposes_drawdown_overlay(self):
        template = (Path(__file__).resolve().parents[1] / "web" / "templates" / "backtest.html").read_text(encoding="utf-8")
        self.assertIn("setSpxOverlay('dd'", template)
        self.assertIn(">Drawdown</button>", template)
        self.assertIn("label: 'Drawdown'", template)
        self.assertIn("(_spxOverlay === 'pnl' || _spxOverlay === 'dd')", template)


if __name__ == "__main__":
    unittest.main(verbosity=2)
