"""SPEC-094.8 — BPS fallback 触发日现场校验（三态 + 冻结）AC 测试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production.q042_executor as ex                        # noqa: E402
from tests.test_spec_094_4 import (                          # noqa: E402
    _episode_closes, _prime_fire_a, _trigger_bodies, _ammo_rows,
    q042_env,                                                # noqa: F401
)


# ── AC-1 三态分类纯函数（边界含警戒线本身） ──────────────────────────────────

def test_ac1_classification_bands():
    assert ex._classify_fallback_err(0.0) == "PASS"
    assert ex._classify_fallback_err(-10.0) == "PASS"
    assert ex._classify_fallback_err(10.1) == "WARNING"
    assert ex._classify_fallback_err(-15.0) == "WARNING"
    assert ex._classify_fallback_err(15.1) == "FREEZE"
    assert ex._classify_fallback_err(-45.5) == "FREEZE"      # P6c FLAT 实测量级


def _run_with_check(q042_env, monkeypatch, check):
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)
    if callable(check):
        monkeypatch.setattr(ex, "_fallback_onsite_check", check)
    else:
        monkeypatch.setattr(ex, "_fallback_onsite_check", lambda **k: check)
    ex.run_eod_evaluation(dry_run=False)
    return _trigger_bodies(q042_env)[0], _ammo_rows(q042_env)[0]["ammo_advisory"]


# ── AC-2 PASS / WARNING → 原分支保留 + 校验标注 ──────────────────────────────

def test_ac2_pass_keeps_fallback_with_tag(q042_env, monkeypatch):
    body, adv = _run_with_check(q042_env, monkeypatch,
                                {"state": "PASS", "err_pct": 3.2,
                                 "real_credit": 20.0, "calib_credit": 20.6})
    assert "可用 BPS fallback" in body
    assert "现场校验 PASS：credit 误差 +3.2%" in body
    assert adv["branch"] == "bps_fallback"
    assert adv["fallback_check"]["state"] == "PASS"


def test_ac2_warning_keeps_fallback(q042_env, monkeypatch):
    body, adv = _run_with_check(q042_env, monkeypatch,
                                {"state": "WARNING", "err_pct": -12.4,
                                 "real_credit": 20.0, "calib_credit": 17.5})
    assert "可用 BPS fallback" in body and "WARNING" in body
    assert adv["branch"] == "bps_fallback"


# ── AC-3 FREEZE / UNVERIFIABLE → 降级空仓，零现场裁量 ────────────────────────

def test_ac3_freeze_downgrades_to_stand_aside(q042_env, monkeypatch):
    body, adv = _run_with_check(q042_env, monkeypatch,
                                {"state": "FREEZE", "err_pct": 26.1,
                                 "real_credit": 20.0, "calib_credit": 25.2})
    assert "BPS fallback 已冻结" in body
    assert "credit 误差 +26.1% 超 ±15% 容差" in body
    assert "按空仓分支执行" in body and "SELL PUT" not in body
    assert adv["branch"] == "bps_fallback_frozen"


def test_ac3_unverifiable_freezes(q042_env, monkeypatch):
    def _boom(**k):
        raise ValueError("chain unavailable")
    body, adv = _run_with_check(q042_env, monkeypatch, _boom)
    assert "BPS fallback 已冻结（现场无法校验" in body
    assert adv["branch"] == "bps_fallback_frozen"
    assert adv["fallback_check"]["state"] == "UNVERIFIABLE"


# ── AC-4 三态记录落盘（监控管道） ────────────────────────────────────────────

def test_ac4_check_log_appended(q042_env, monkeypatch, tmp_path):
    _run_with_check(q042_env, monkeypatch,
                    {"state": "WARNING", "err_pct": 13.0,
                     "real_credit": 20.0, "calib_credit": 22.6})
    log = tmp_path / "q042_fallback_check_log.jsonl"
    rows = [json.loads(l) for l in log.read_text().splitlines() if l]
    assert len(rows) == 1
    assert rows[0]["state"] == "WARNING" and rows[0]["err_pct"] == 13.0
    assert rows[0]["date"] == "2026-07-08"


# ── AC-5 充足现金分支不做校验（只在 fallback 分支评估时跑） ──────────────────

def test_ac5_sufficient_cash_no_check(q042_env, monkeypatch, tmp_path):
    calls = []
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes())   # liquid 412k 充足
    monkeypatch.setattr(ex, "_fallback_onsite_check",
                        lambda **k: calls.append(1) or {"state": "PASS", "err_pct": 0})
    ex.run_eod_evaluation(dry_run=False)
    assert calls == []
    assert not (tmp_path / "q042_fallback_check_log.jsonl").exists()


# ── AC-6 preview（Trigger Rehearsal 预演）：零真实链、零日志、附规则说明 ──────

def test_ac6_preview_skips_check_and_log(q042_env, monkeypatch, tmp_path):
    calls = []
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)
    monkeypatch.setattr(ex, "_fallback_onsite_check",
                        lambda **k: calls.append(1) or {"state": "PASS", "err_pct": 0})
    line, payload = ex._ammo_advisory(
        sleeve_id="A", signal_date="2026-07-08", nlv=500_000.0,
        spx_close=950.0, vix=20.0, contracts=5, est_debit=3_000.0,
        closes=_episode_closes(), preview=True)
    assert calls == []
    assert "可用 BPS fallback" in line and "触发日将现场校验" in line
    assert payload["fallback_check"]["state"] == "PREVIEW"
    assert not (tmp_path / "q042_fallback_check_log.jsonl").exists()
