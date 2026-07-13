"""SPEC-094.6 — 运行时 state 防覆写 AC 测试（AC-94.6-1..2；3/4=old Air 运维核查，5=回归）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production.q042_executor as ex                        # noqa: E402  (fixture 依赖)

from tests.test_spec_094_2 import (                          # noqa: E402
    _default_state, _healthy_runtime, _patch_market, _write_json,
    q042_env,                                                # noqa: F401  (pytest fixture)
)

RUNTIME_STATE = ("data/q042_state.json", "data/closed_trades.jsonl",
                 "data/capital_flows.jsonl")


# ── AC-94.6-1 三个运行时文件不再被 git 追踪 ──────────────────────────────────

def test_ac1_runtime_files_untracked_and_ignored():
    tracked = subprocess.run(["git", "ls-files", *RUNTIME_STATE],
                             capture_output=True, text=True, cwd=ROOT).stdout.strip()
    assert tracked == "", f"still tracked: {tracked}"
    ignored = subprocess.run(["git", "check-ignore", *RUNTIME_STATE],
                             capture_output=True, text=True, cwd=ROOT).stdout.splitlines()
    assert len(ignored) == len(RUNTIME_STATE)


# ── AC-94.6-2 ATH 归零 tripwire：告警一条 + dry-run 静默 ─────────────────────

def _run_with_zero_ath(q042_env, monkeypatch, *, dry_run: bool):
    _write_json(q042_env["runtime"], _healthy_runtime())
    _write_json(q042_env["state_file"], _default_state(ath_running_max=0.0))
    _patch_market(monkeypatch, spx_close=7500.0, today_str="2026-07-13")
    ex.run_eod_evaluation(dry_run=dry_run)
    return [p for p in q042_env["pushes"] if "ATH 为 0" in p["title"]]


def test_ac2_zero_ath_fires_action_alert(q042_env, monkeypatch):
    alerts = _run_with_zero_ath(q042_env, monkeypatch, dry_run=False)
    assert len(alerts) == 1
    (a,) = alerts
    assert a["category"] == "ACTION"
    assert a["dedupe_key"] == "q042_ath_reset_2026-07-13"
    assert "重锚" in a["body"]
    # 重锚本身仍执行（max(0, close)），状态照常落盘
    import json
    st = json.loads(q042_env["state_file"].read_text())
    assert st["ath_running_max"] == 7500.0


def test_ac2_dry_run_silent(q042_env, monkeypatch):
    assert _run_with_zero_ath(q042_env, monkeypatch, dry_run=True) == []


def test_ac2_healthy_ath_no_alert(q042_env, monkeypatch):
    _write_json(q042_env["runtime"], _healthy_runtime())
    _write_json(q042_env["state_file"], _default_state(ath_running_max=7609.78))
    _patch_market(monkeypatch, spx_close=7500.0, today_str="2026-07-13")
    ex.run_eod_evaluation(dry_run=False)
    assert [p for p in q042_env["pushes"] if "ATH 为 0" in p["title"]] == []
