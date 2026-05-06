from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import research.q041.collect_massive_snapshot as mod
from research.q041.collect_massive_snapshot import (
    _normalize_frame,
    _with_api_key,
    massive_underlying_symbol,
    run,
    safe_filename,
)


class MassiveSnapshotHelpersTest(unittest.TestCase):
    def test_safe_filename_and_api_symbol_mapping(self) -> None:
        self.assertEqual(safe_filename("BRK/B"), "BRK_B")
        self.assertEqual(massive_underlying_symbol("BRK/B"), "BRK.B")
        self.assertEqual(massive_underlying_symbol("SPX"), "SPX")

    def test_with_api_key_preserves_existing_query_and_injects_key(self) -> None:
        url = "https://api.massive.com/v3/snapshot/options/AAPL?cursor=abc&limit=250"
        out = _with_api_key(url, "secret")
        self.assertIn("cursor=abc", out)
        self.assertIn("limit=250", out)
        self.assertIn("apiKey=secret", out)

    def test_normalize_frame_flattens_core_snapshot_fields(self) -> None:
        frame = _normalize_frame(
            "AAPL",
            "2026-05-04",
            [
                {
                    "break_even_price": 277.175,
                    "day": {
                        "open": 78.64,
                        "high": 78.64,
                        "low": 76.62,
                        "close": 76.89,
                        "volume": 21,
                        "vwap": 77.0562,
                        "change": -3.31,
                        "change_percent": -4.13,
                        "previous_close": 80.2,
                        "last_updated": 1777867200000000000,
                    },
                    "details": {
                        "contract_type": "call",
                        "exercise_style": "american",
                        "expiration_date": "2026-05-04",
                        "shares_per_contract": 100,
                        "strike_price": 200,
                        "ticker": "O:AAPL260504C00200000",
                    },
                    "greeks": {
                        "delta": 0.42,
                        "gamma": 0.013,
                        "theta": -0.08,
                        "vega": 0.12,
                        "rho": 0.01,
                    },
                    "implied_volatility": 20,
                    "last_trade": {
                        "sip_timestamp": 1777920107986252583,
                        "price": 76.89,
                        "size": 2,
                        "exchange": 300,
                        "timeframe": "DELAYED",
                    },
                    "open_interest": 1,
                    "underlying_asset": {
                        "change_to_break_even": 0.645,
                        "last_updated": 1777939197246835419,
                        "price": 276.53,
                        "ticker": "AAPL",
                        "timeframe": "DELAYED",
                    },
                }
            ],
        )
        self.assertEqual(len(frame), 1)
        row = frame.iloc[0].to_dict()
        self.assertEqual(row["snapshot_date"], "2026-05-04")
        self.assertEqual(row["occ_ticker"], "O:AAPL260504C00200000")
        self.assertEqual(row["contract_type"], "call")
        self.assertEqual(row["strike_price"], 200)
        self.assertEqual(row["open_interest"], 1)
        self.assertEqual(row["delta"], 0.42)
        self.assertEqual(row["underlying_ticker"], "AAPL")
        self.assertIn("2026-05-04T", row["day_last_updated_et"])

    def test_existing_parquet_reuse_marks_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            day_dir = data_root / "2026-05-04"
            day_dir.mkdir(parents=True)
            pd.DataFrame([{"snapshot_date": "2026-05-04", "symbol": "AAPL", "occ_ticker": "O:AAPL260504C00200000"}]).to_parquet(
                day_dir / "AAPL.parquet",
                index=False,
            )
            with patch.object(mod, "DATA_ROOT", data_root), patch.object(mod, "_ensure_api_key", return_value="x"):
                rc = run(snapshot_day=date(2026, 5, 4), symbols=["AAPL"], force=False, verbose=False)
            self.assertEqual(rc, 0)
            # smoke structure check via raw json to preserve null
            import json
            payload = json.loads((day_dir / "_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["ok"], 1)
            self.assertEqual(payload["errors"], 0)
            self.assertEqual(payload["results"][0]["symbol"], "AAPL")
            self.assertIsNone(payload["results"][0]["pages"])
            self.assertTrue(payload["results"][0]["reused"])


if __name__ == "__main__":
    unittest.main()
