"""SPEC-128 — native Partnership Book engine acceptance tests.

AC map:
  1/2/7  parity vs xlsx oracle + §9 anchors + XIRR对拍 — via the migration
         gate re-run (skipUnless the PII workbook exists on this machine)
  3      recon checks: green on migrated data; injected bad rows flip the
         matching check red (negative tests)
  4      write flows: POST→recompute→readable; void rolls back; closed
         period → 409; files are append-only
  5      fallback: no data/book/ → legacy chain intact
  6      PII: data/book/ gitignored, no ledger jsonl tracked
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import web.book_engine as be

XLSX = REPO / "research" / "book_management" / "Partnership_Shares_v3.5.xlsx"
MIGRATED = REPO / "data" / "book" / ".migrated"


def _mini_book(tmp: Path) -> Path:
    """Synthetic two-period pool for hermetic engine tests."""
    (tmp / "config.json").write_text(json.dumps({
        "sw_partners": ["A", "B"], "et_partners": ["A"],
        "members": [{"display": "A", "sw": "A", "et": "A"},
                    {"display": "B", "sw": "B", "et": None}],
        "partner_display": {}, "subaccounts": ["SUB-1"],
        "et_merge": {"cost_basis": {"A": 100.0},
                     "roi_convention": {"A": "value_vs_cost_basis"}},
        "guarantees": [],
    }))
    snaps = [
        {"id": "s1", "event": "snapshot", "date": "2025-01-31", "total": 1000.0,
         "note": "", "closed": True},
        {"id": "s2", "event": "snapshot", "date": "2025-02-28", "total": 1150.0,
         "note": "", "closed": False},
    ]
    flows = [
        {"id": "f1", "event": "flow", "snapshot_date": "2025-01-31",
         "partner": "A", "from": "bank", "to": "pool", "amount": 600.0,
         "counts": "Yes", "type": "Contribution", "note": ""},
        {"id": "f2", "event": "flow", "snapshot_date": "2025-01-31",
         "partner": "B", "from": "bank", "to": "pool", "amount": 400.0,
         "counts": "Yes", "type": "Contribution", "note": ""},
        {"id": "f3", "event": "flow", "snapshot_date": None,
         "partner": "", "from": "bank", "to": "SUB-1", "amount": 50.0,
         "counts": "No", "type": "", "note": "transit in"},
    ]
    (tmp / "sw_snapshots.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in snaps))
    (tmp / "sw_cashledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in flows))
    (tmp / "et_snapshots.jsonl").write_text(json.dumps(
        {"id": "e1", "event": "snapshot", "date": "2025-02-28", "total": 120.0,
         "note": "", "closed": False}) + "\n")
    (tmp / "et_cashledger.jsonl").write_text(json.dumps(
        {"id": "ef1", "event": "flow", "snapshot_date": "2025-02-28",
         "partner": "A", "from": "x", "to": "pool", "amount": 100.0,
         "counts": "Yes", "type": "Contribution", "note": ""}) + "\n")
    (tmp / "cxz_etrade.jsonl").write_text("")
    (tmp / "lien_etrade.jsonl").write_text("")
    return tmp


class TestEngineMath(unittest.TestCase):
    def setUp(self):
        self.dir = _mini_book(Path(tempfile.mkdtemp()))

    def test_backsolved_pnl_and_opening_share_allocation(self):
        b = be.compute_book(self.dir, force=True)
        # period 1: 1000 total = 600+400 flows, pnl 0; period 2: +150 pnl on
        # opening shares 60/40
        a = next(m for m in b["members"] if m["name"] == "A")
        bb = next(m for m in b["members"] if m["name"] == "B")
        self.assertAlmostEqual(a["schwab_value"], 600 + 90, places=6)
        self.assertAlmostEqual(bb["schwab_value"], 400 + 60, places=6)
        self.assertAlmostEqual(b["total"]["schwab_value"], 1150.0)
        # ET pool: A contributed 100, value 120, cost basis 100 → roi 20%
        et = b["etrade_pool"][0]
        self.assertAlmostEqual(et["current_value"], 120.0)
        self.assertAlmostEqual(et["return_on_invested"], 0.20, places=6)
        # NAV/unit: SW period2 return 15% → 115
        self.assertAlmostEqual(b["nav_unit"]["sw"], 115.0, places=6)

    def test_recon_green_and_subaccount_pending(self):
        b = be.compute_book(self.dir, force=True)
        self.assertTrue(b["recon_all_green"], b["recon_checks"])
        self.assertAlmostEqual(b["subaccounts"]["SUB-1"], 50.0)

    def test_injected_bad_rows_flip_checks_red(self):
        # (a) distribution larger than balance → negative balance check fires
        with (self.dir / "sw_cashledger.jsonl").open("a") as f:
            f.write(json.dumps({"id": "bad1", "event": "flow",
                                "snapshot_date": "2025-02-28", "partner": "B",
                                "from": "pool", "to": "bank", "amount": 9999.0,
                                "counts": "Yes", "type": "Distribution",
                                "note": ""}) + "\n")
        b = be.compute_book(self.dir, force=True)
        self.assertFalse(b["recon_all_green"])
        fired = {c["name"] for c in b["recon_checks"] if not c["ok"]}
        self.assertIn("no_negative_balances", fired)

    def test_void_rolls_back(self):
        with (self.dir / "sw_cashledger.jsonl").open("a") as f:
            f.write(json.dumps({"id": "bad1", "event": "flow",
                                "snapshot_date": "2025-02-28", "partner": "B",
                                "from": "pool", "to": "bank", "amount": 9999.0,
                                "counts": "Yes", "type": "Distribution",
                                "note": ""}) + "\n")
        self.assertFalse(be.compute_book(self.dir, force=True)["recon_all_green"])
        be.record_void("sw_flows", "bad1", "input error", data_dir=self.dir)
        b = be.compute_book(self.dir, force=True)
        self.assertTrue(b["recon_all_green"])
        self.assertAlmostEqual(b["total"]["schwab_value"], 1150.0)

    def test_closed_period_write_raises(self):
        with self.assertRaises(be.ClosedPeriodError):
            be.record_flow("sw", {"snapshot_date": "2025-01-31", "partner": "A",
                                  "amount": 1.0, "counts": "Yes",
                                  "type": "Contribution"}, data_dir=self.dir)
        with self.assertRaises(be.ClosedPeriodError):
            be.record_snapshot("sw", "2025-01-31", 999.0, data_dir=self.dir)

    def test_append_only(self):
        before = (self.dir / "sw_cashledger.jsonl").read_text()
        be.record_flow("sw", {"snapshot_date": "2025-02-28", "partner": "A",
                              "amount": 10.0, "counts": "Yes",
                              "type": "Contribution"}, data_dir=self.dir)
        after = (self.dir / "sw_cashledger.jsonl").read_text()
        self.assertTrue(after.startswith(before))   # strictly appended

    def test_flow_validation(self):
        with self.assertRaises(ValueError):
            be.record_flow("sw", {"snapshot_date": "2025-02-28", "partner": "A",
                                  "amount": 1.0, "counts": "Maybe",
                                  "type": "Contribution"}, data_dir=self.dir)
        with self.assertRaises(ValueError):
            be.record_flow("xx", {"snapshot_date": "2025-02-28", "partner": "A",
                                  "amount": 1.0, "counts": "Yes",
                                  "type": "Contribution"}, data_dir=self.dir)


class TestXirr(unittest.TestCase):
    def test_known_value(self):
        from datetime import date
        # Excel XIRR([-1000, 1150], [2025-01-01, 2026-01-01]) = 0.15
        flows = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1150.0)]
        self.assertAlmostEqual(be._xirr(flows), 0.15, places=4)

    def test_undefined(self):
        from datetime import date
        self.assertIsNone(be._xirr([(date(2025, 1, 1), -1.0)]))


@unittest.skipUnless(XLSX.exists(), "PII workbook only on the dev machine")
class TestMigrationParity(unittest.TestCase):
    """AC-1/2/7: the full gate — extraction + field parity + anchors + recon."""

    def test_migration_gate_passes(self):
        res = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "book_migrate_from_xlsx.py")],
            capture_output=True, text=True, timeout=300)
        self.assertEqual(res.returncode, 0, res.stdout[-2000:] + res.stderr[-500:])
        self.assertIn("parity: ALL FIELDS MATCH", res.stdout)
        self.assertIn("-> OK", res.stdout)
        self.assertTrue(MIGRATED.exists())


class TestApiAndFallback(unittest.TestCase):
    def test_native_first_read(self):
        from web.server import app
        tmp = _mini_book(Path(tempfile.mkdtemp()))
        with patch.object(be, "DATA_DIR", tmp):
            d = app.test_client().get("/api/partnership/book").get_json()
        self.assertEqual(d["source"], "native")
        self.assertIn("recon_checks", d)

    def test_fallback_to_legacy_when_unmigrated(self):
        from web.server import app
        empty = Path(tempfile.mkdtemp())
        with patch.object(be, "DATA_DIR", empty), \
             patch("web.partnership_book.read_book",
                   return_value={"available": True, "source": "google_drive"}):
            d = app.test_client().get("/api/partnership/book").get_json()
        self.assertEqual(d["source"], "google_drive")

    def test_write_endpoints_roundtrip(self):
        from web.server import app
        tmp = _mini_book(Path(tempfile.mkdtemp()))
        client = app.test_client()
        with patch.object(be, "DATA_DIR", tmp):
            r = client.post("/api/partnership/book/snapshot",
                            json={"pool": "sw", "date": "2025-03-31",
                                  "total": 1200.0, "note": "t"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["recon_all_green"])
            d = client.get("/api/partnership/book").get_json()
            self.assertAlmostEqual(d["total"]["schwab_value"], 1200.0)
            # closed period → 409
            r = client.post("/api/partnership/book/snapshot",
                            json={"pool": "sw", "date": "2025-01-31",
                                  "total": 1.0})
            self.assertEqual(r.status_code, 409)
            # bad payload → 400
            r = client.post("/api/partnership/book/flow",
                            json={"pool": "sw", "snapshot_date": "2025-03-31",
                                  "partner": "A", "amount": 5.0,
                                  "counts": "Maybe", "type": "Contribution"})
            self.assertEqual(r.status_code, 400)


class TestPii(unittest.TestCase):
    def test_book_dir_gitignored(self):
        res = subprocess.run(["git", "check-ignore", "data/book/config.json"],
                             capture_output=True, text=True, cwd=REPO)
        self.assertEqual(res.returncode, 0, "data/book/ must be gitignored")

    def test_no_ledger_files_tracked(self):
        res = subprocess.run(["git", "ls-files", "data/book/"],
                             capture_output=True, text=True, cwd=REPO)
        self.assertEqual(res.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
