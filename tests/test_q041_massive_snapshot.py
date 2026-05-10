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
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp_path = Path(self.tmpdir.name)
        self.orig_data_root = mod.DATA_ROOT
        self.orig_integrity_audit = mod.INTEGRITY_AUDIT_PATH
        self.orig_integrity_alert_state = mod.INTEGRITY_ALERT_STATE_PATH
        mod.DATA_ROOT = self.tmp_path / "data"
        mod.INTEGRITY_AUDIT_PATH = self.tmp_path / "q041_massive_snapshot_integrity.jsonl"
        mod.INTEGRITY_ALERT_STATE_PATH = self.tmp_path / "q041_massive_snapshot_integrity_alerts.jsonl"

    def tearDown(self) -> None:
        mod.DATA_ROOT = self.orig_data_root
        mod.INTEGRITY_AUDIT_PATH = self.orig_integrity_audit
        mod.INTEGRITY_ALERT_STATE_PATH = self.orig_integrity_alert_state

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
        for d in ("2026-05-04", "2026-05-01", "2026-04-30", "2026-04-29", "2026-04-28"):
            day_dir = mod.DATA_ROOT / d
            day_dir.mkdir(parents=True)
            (day_dir / "_summary.json").write_text("{}", encoding="utf-8")
            pd.DataFrame([{"snapshot_date": d, "symbol": "SPX", "occ_ticker": f"O:SPX{d.replace('-', '')}C05000000"}]).to_parquet(
                day_dir / "SPX.parquet",
                index=False,
            )
        day_dir = mod.DATA_ROOT / "2026-05-04"
        pd.DataFrame([{"snapshot_date": "2026-05-04", "symbol": "AAPL", "occ_ticker": "O:AAPL260504C00200000"}]).to_parquet(
            day_dir / "AAPL.parquet",
            index=False,
        )
        with patch.object(mod, "_ensure_api_key", return_value="x"):
            rc = run(snapshot_day=date(2026, 5, 4), symbols=["AAPL"], force=False, verbose=False, send_telegram=False)
        self.assertEqual(rc, 0)
        import json
        payload = json.loads((day_dir / "_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["ok"], 1)
        self.assertEqual(payload["errors"], 0)
        self.assertEqual(payload["results"][0]["symbol"], "AAPL")
        self.assertIsNone(payload["results"][0]["pages"])
        self.assertTrue(payload["results"][0]["reused"])
        integrity = [json.loads(line) for line in mod.INTEGRITY_AUDIT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(integrity[-1]["status"], "ok")
        self.assertEqual(integrity[-1]["missing_days"], [])

    def test_integrity_warning_records_missing_recent_trading_day(self) -> None:
        for d in ("2026-05-08", "2026-05-07", "2026-05-05", "2026-05-04"):
            day_dir = mod.DATA_ROOT / d
            day_dir.mkdir(parents=True)
            (day_dir / "_summary.json").write_text("{}", encoding="utf-8")
            pd.DataFrame([{"snapshot_date": d, "symbol": "SPX", "occ_ticker": f"O:SPX{d.replace('-', '')}C05000000"}]).to_parquet(
                day_dir / "SPX.parquet",
                index=False,
            )
        day_dir = mod.DATA_ROOT / "2026-05-08"
        pd.DataFrame([{"snapshot_date": "2026-05-08", "symbol": "AAPL", "occ_ticker": "O:AAPL260508C00200000"}]).to_parquet(
            day_dir / "AAPL.parquet",
            index=False,
        )
        sent: list[str] = []
        with patch.object(mod, "_ensure_api_key", return_value="x"), patch.object(mod, "_send_telegram_message", side_effect=lambda text, _log: sent.append(text) or True):
            rc = run(snapshot_day=date(2026, 5, 8), symbols=["AAPL"], force=False, verbose=False, send_telegram=True)
        self.assertEqual(rc, 0)
        self.assertEqual(len(sent), 1)
        self.assertIn("Q041 Massive snapshot integrity warning 2026-05-08", sent[0])
        self.assertIn("2026-05-06", sent[0])
        import json
        integrity = [json.loads(line) for line in mod.INTEGRITY_AUDIT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(integrity[-1]["status"], "warning")
        self.assertEqual(integrity[-1]["missing_days"], ["2026-05-06"])


if __name__ == "__main__":
    unittest.main()
