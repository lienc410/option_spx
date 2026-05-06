from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "q041_paper_ledger.py"


class Spec083Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.ledger = Path(self.tmpdir.name) / "q041_paper_trades.jsonl"
        self.config = Path(self.tmpdir.name) / "q041_paper_trade_config.json"
        self.review_dir = Path(self.tmpdir.name) / "review"
        self.env = os.environ.copy()
        self.env["Q041_PAPER_LEDGER_FILE"] = str(self.ledger)
        self.env["Q041_PAPER_CONFIG_FILE"] = str(self.config)
        self.env["Q041_PAPER_REVIEW_DIR"] = str(self.review_dir)

    def _run(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(ROOT),
            env=self.env,
            text=True,
            capture_output=True,
        )
        if ok and proc.returncode != 0:
            self.fail(f"CLI failed: {' '.join(args)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
        if not ok and proc.returncode == 0:
            self.fail(f"CLI unexpectedly succeeded: {' '.join(args)}\nstdout={proc.stdout}")
        return proc

    def _rows(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in self.ledger.read_text().splitlines() if line.strip()]

    def _write_config(self, total_bp: float = 500000.0) -> None:
        self.config.write_text(json.dumps({"account_total_bp": total_bp}))

    def test_ac2_add_csp_writes_full_open_record(self) -> None:
        proc = self._run(
            "add-csp",
            "--symbol", "SPX",
            "--tier", "tier1",
            "--entry-date", "2026-05-16",
            "--expiry", "2026-06-19",
            "--act-dte", "34",
            "--s-entry", "7230",
            "--iv-entry", "14.5",
            "--vix-entry", "17.2",
            "--net-prem", "31.33",
            "--bp-reserved", "694000",
            "--contracts", "1",
            "--strike", "6940",
            "--pct-otm", "4.2",
            "--delta-actual", "0.20",
            "--notes", "tier1 open",
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["record_id"], "20260516-SPX-01")
        self.assertEqual(payload["status"], "open")
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        required = {
            "record_id", "status", "tier", "strategy_type", "symbol", "entry_date", "expiry", "act_dte",
            "S_entry", "iv_entry", "vix_entry", "net_prem", "bp_reserved", "contracts", "S_exit",
            "settle_cost", "pnl", "hit", "close_date", "flags", "notes", "strike", "pct_otm", "delta_actual",
        }
        self.assertTrue(required.issubset(set(row.keys())))
        self.assertEqual(row["strategy_type"], "csp")
        self.assertEqual(row["pnl"], None)

    def test_ac3_close_updates_open_record(self) -> None:
        self.test_ac2_add_csp_writes_full_open_record()
        proc = self._run(
            "close",
            "--record-id", "20260516-SPX-01",
            "--s-exit", "7250",
            "--pnl", "31.33",
            "--hit", "false",
            "--close-date", "2026-06-19",
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "closed")
        self.assertEqual(payload["pnl"], 31.33)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "closed")
        self.assertEqual(rows[0]["close_date"], "2026-06-19")
        self.assertFalse(rows[0]["hit"])

    def test_ac4_add_ic_and_reject_vix_gate_fail(self) -> None:
        proc = self._run(
            "add-ic",
            "--symbol", "COST",
            "--tier", "tier3",
            "--entry-date", "2026-05-20",
            "--expiry", "2026-05-29",
            "--act-dte", "9",
            "--s-entry", "1012",
            "--iv-entry", "24.1",
            "--vix-entry", "18.0",
            "--net-prem", "4.25",
            "--bp-reserved", "4200",
            "--contracts", "1",
            "--k-put-short", "980",
            "--k-put-long", "960",
            "--k-call-short", "1040",
            "--k-call-long", "1060",
            "--event-name", "COST-2026Q2",
            "--earnings-date", "2026-05-23",
            "--implied-move-pct", "4.2",
            "--vix-gate-passed", "true",
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["strategy_type"], "earnings_ic")
        self.assertTrue(payload["vix_gate_passed"])
        self.assertEqual(payload["record_id"], "20260520-COST-01")

        bad = self._run(
            "add-ic",
            "--symbol", "JPM",
            "--tier", "tier3",
            "--entry-date", "2026-05-21",
            "--expiry", "2026-05-30",
            "--act-dte", "9",
            "--s-entry", "312",
            "--iv-entry", "26.1",
            "--vix-entry", "13.0",
            "--net-prem", "2.1",
            "--bp-reserved", "2000",
            "--contracts", "1",
            "--k-put-short", "300",
            "--k-put-long", "290",
            "--k-call-short", "324",
            "--k-call-long", "334",
            "--event-name", "JPM-2026Q2",
            "--earnings-date", "2026-05-24",
            "--implied-move-pct", "6.3",
            "--vix-gate-passed", "false",
            ok=False,
        )
        self.assertIn("cannot create an open record", bad.stderr)
        rows = self._rows()
        self.assertEqual(len(rows), 1)

    def test_ac5_budget_within_limits(self) -> None:
        self._write_config(500000)
        self._run(
            "add-csp", "--symbol", "SPX", "--tier", "tier1", "--entry-date", "2026-05-16", "--expiry", "2026-06-19",
            "--act-dte", "34", "--s-entry", "7230", "--iv-entry", "14.5", "--vix-entry", "17.2", "--net-prem", "31.33",
            "--bp-reserved", "95000", "--contracts", "1", "--strike", "6940", "--pct-otm", "4.2", "--delta-actual", "0.20",
        )
        self._run(
            "add-csp", "--symbol", "GOOGL", "--tier", "tier2", "--entry-date", "2026-05-16", "--expiry", "2026-06-06",
            "--act-dte", "21", "--s-entry", "385.69", "--iv-entry", "22.0", "--vix-entry", "17.2", "--net-prem", "3.15",
            "--bp-reserved", "70000", "--contracts", "1", "--strike", "366", "--pct-otm", "5.1", "--delta-actual", "0.20",
        )
        proc = self._run("budget")
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["tier1_bp_pct"], 19.0)
        self.assertEqual(payload["tier2_bp_pct"], 14.0)
        self.assertTrue(payload["within_limits"])

    def test_ac6_budget_reports_violations(self) -> None:
        self._write_config(500000)
        self._run(
            "add-csp", "--symbol", "SPX", "--tier", "tier1", "--entry-date", "2026-05-16", "--expiry", "2026-06-19",
            "--act-dte", "34", "--s-entry", "7230", "--iv-entry", "14.5", "--vix-entry", "17.2", "--net-prem", "31.33",
            "--bp-reserved", "105000", "--contracts", "1", "--strike", "6940", "--pct-otm", "4.2", "--delta-actual", "0.20",
        )
        proc = self._run("budget")
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["within_limits"])
        self.assertTrue(any("tier1 exceeds 20%" in item for item in payload["violations"]))

    def test_ac7_and_ac8_exports(self) -> None:
        self._run(
            "add-csp", "--symbol", "SPX", "--tier", "tier1", "--entry-date", "2026-05-16", "--expiry", "2026-06-19",
            "--act-dte", "34", "--s-entry", "7230", "--iv-entry", "14.5", "--vix-entry", "17.2", "--net-prem", "31.33",
            "--bp-reserved", "694000", "--contracts", "1", "--strike", "6940", "--pct-otm", "4.2", "--delta-actual", "0.20",
        )
        self._run(
            "add-ic", "--symbol", "COST", "--tier", "tier3", "--entry-date", "2026-05-20", "--expiry", "2026-05-29",
            "--act-dte", "9", "--s-entry", "1012", "--iv-entry", "24.1", "--vix-entry", "18.0", "--net-prem", "4.25",
            "--bp-reserved", "4200", "--contracts", "1", "--k-put-short", "980", "--k-put-long", "960", "--k-call-short", "1040",
            "--k-call-long", "1060", "--event-name", "COST-2026Q2", "--earnings-date", "2026-05-23", "--implied-move-pct", "4.2",
            "--vix-gate-passed", "true",
        )
        csp_path = Path(self._run("export-csp", "--month", "2026-05").stdout.strip())
        ic_path = Path(self._run("export-ic", "--symbol", "COST", "--year", "2026").stdout.strip())
        self.assertTrue(csp_path.exists())
        self.assertTrue(ic_path.exists())
        with csp_path.open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertIn("delta_actual", rows[0])
        with ic_path.open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertIn("event_name", rows[0])
        self.assertIn("vix_gate_passed", rows[0])

    def test_ac9_status_output_contains_required_sections(self) -> None:
        self._write_config(500000)
        self._run(
            "add-csp", "--symbol", "SPX", "--tier", "tier1", "--entry-date", "2026-05-16", "--expiry", "2026-05-22",
            "--act-dte", "6", "--s-entry", "7230", "--iv-entry", "14.5", "--vix-entry", "17.2", "--net-prem", "31.33",
            "--bp-reserved", "95000", "--contracts", "1", "--strike", "6940", "--pct-otm", "4.2", "--delta-actual", "0.20",
        )
        self._run(
            "add-ic", "--symbol", "COST", "--tier", "tier3", "--entry-date", "2026-05-20", "--expiry", "2026-05-29",
            "--act-dte", "9", "--s-entry", "1012", "--iv-entry", "24.1", "--vix-entry", "18.0", "--net-prem", "4.25",
            "--bp-reserved", "4200", "--contracts", "1", "--k-put-short", "980", "--k-put-long", "960", "--k-call-short", "1040",
            "--k-call-long", "1060", "--event-name", "COST-2026Q2", "--earnings-date", "2026-05-23", "--implied-move-pct", "4.2",
            "--vix-gate-passed", "true",
        )
        proc = self._run("status", "--today", "2026-05-16")
        text = proc.stdout
        self.assertIn("Open Positions", text)
        self.assertIn("Recent Entries", text)
        self.assertIn("BP Usage:", text)
        self.assertIn("Next Review Item", text)
        self.assertIn("20260516-SPX-01", text)
        self.assertIn("- csp: 20260516-SPX-01", text)


if __name__ == "__main__":
    unittest.main()
