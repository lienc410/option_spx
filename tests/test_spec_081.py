import unittest

from research.q041.download_massive import map_underlying, parse_occ_ticker, safe_filename


class Spec081Tests(unittest.TestCase):
    def test_parse_occ_ticker_basic(self):
        parsed = parse_occ_ticker("O:AAPL220520C00120000")
        self.assertEqual(parsed["underlying_raw"], "AAPL")
        self.assertEqual(parsed["expiry"], "2022-05-20")
        self.assertEqual(parsed["option_type"], "C")
        self.assertEqual(parsed["strike"], 120.0)

    def test_parse_occ_ticker_invalid(self):
        self.assertIsNone(parse_occ_ticker("bad"))
        self.assertIsNone(parse_occ_ticker("O:AAPL220520X00120000"))

    def test_symbol_mapping(self):
        self.assertEqual(map_underlying("BRKB", "2024-01-01"), "BRK/B")
        self.assertEqual(map_underlying("SPXW", "2024-01-01"), "SPX")
        self.assertEqual(map_underlying("FB", "2022-06-08"), "META")
        self.assertEqual(map_underlying("FB", "2022-06-09"), "FB")

    def test_safe_filename(self):
        self.assertEqual(safe_filename("BRK/B"), "BRK_B")
        self.assertEqual(safe_filename("/ES"), "ES")


if __name__ == "__main__":
    unittest.main()
