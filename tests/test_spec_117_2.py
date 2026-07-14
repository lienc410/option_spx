"""SPEC-117.2 — 每日绿线降噪 AC 测试（PM 2026-07-13：绿线并入 digest，反向心跳搬家）。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notify.telegram_bot import ET, _digest_health_bits          # noqa: E402

NOW = datetime(2026, 7, 14, 15, 55, tzinfo=ET)


def _hb(tmp_path, *, hours_ago=22.4, violations=0, total=29):
    p = tmp_path / "hb.json"
    ts = NOW - timedelta(hours=hours_ago)
    p.write_text(json.dumps({"ts": ts.isoformat(timespec="seconds"),
                             "total": total, "violations": violations}))
    return p


def _cs(tmp_path, *, alert=False, present=17, total=17, date="2026-07-14"):
    p = tmp_path / "cs.jsonl"
    p.write_text(json.dumps({"date": date, "alert_fired": alert,
                             "s1_present": present, "s1_total": total}) + "\n")
    return p


# ── AC-1 全绿：单行令牌，无升级 ──────────────────────────────────────────────

def test_ac1_green_tokens_no_escalation(tmp_path):
    bits, esc = _digest_health_bits(NOW, _hb(tmp_path), _cs(tmp_path))
    assert esc is False
    assert bits[0].startswith("ops 29/29 ✓")
    assert "链体检 17/17 ✓" in bits[1]


# ── AC-2 反向心跳：state 过期 >26h → 升 ACTION ───────────────────────────────

def test_ac2_stale_heartbeat_escalates(tmp_path):
    bits, esc = _digest_health_bits(NOW, _hb(tmp_path, hours_ago=30), _cs(tmp_path))
    assert esc is True
    assert "心跳过期" in bits[0]


def test_ac2_missing_state_flags_but_no_escalation(tmp_path):
    bits, esc = _digest_health_bits(NOW, tmp_path / "absent.json", _cs(tmp_path))
    assert esc is False                       # 首日部署宽限（文案已说明）
    assert "心跳状态缺失" in bits[0]


# ── AC-3 违规日：⚠ 令牌但不重复升级（独立 ACTION 已响） ───────────────────────

def test_ac3_violation_token_no_double_escalation(tmp_path):
    bits, esc = _digest_health_bits(NOW, _hb(tmp_path, violations=2), _cs(tmp_path))
    assert esc is False
    assert "⚠ ops 2 项违规" in bits[0]


def test_ac3_chain_alert_token(tmp_path):
    bits, _ = _digest_health_bits(NOW, _hb(tmp_path), _cs(tmp_path, alert=True, present=15))
    assert "链体检 15/17 ⚠" in bits[1]


# ── AC-4 心跳脚本：绿天写 state 不推送、违规日推 ACTION ───────────────────────

def test_ac4_heartbeat_green_writes_state_no_push(tmp_path, monkeypatch):
    import scripts.ops_heartbeat as hb
    calls = []
    import notify.gateway as gw
    monkeypatch.setattr(gw, "push", lambda *a, **k: calls.append(a) or True)
    monkeypatch.setattr(hb, "ROOT", tmp_path)
    (tmp_path / "logs").mkdir()
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"jobs": []}))          # 空清单 → 零违规绿路径
    monkeypatch.setattr(hb, "REGISTRY", reg)
    monkeypatch.setattr(hb, "_launchctl_state", lambda: {})
    monkeypatch.setattr(hb, "_deferred_digest", lambda now, path=None: None)
    violations = hb.run(NOW, dry_run=False)
    assert violations == []
    st = json.loads((tmp_path / "logs" / "ops_heartbeat_state.json").read_text())
    assert st["violations"] == 0
    assert calls == []                                # 绿天零推送（SPEC-117.2）


def test_ac4_heartbeat_violation_still_pushes_action(tmp_path, monkeypatch):
    import scripts.ops_heartbeat as hb
    calls = []
    import notify.gateway as gw
    monkeypatch.setattr(gw, "push", lambda *a, **k: calls.append(a) or True)
    monkeypatch.setattr(hb, "ROOT", tmp_path)
    (tmp_path / "logs").mkdir()
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"jobs": [{"label": "com.x.dead", "allow_exit": [0]}]}))
    monkeypatch.setattr(hb, "REGISTRY", reg)
    monkeypatch.setattr(hb, "_launchctl_state",
                        lambda: {"com.x.dead": {"exit": 1, "pid": None}})
    monkeypatch.setattr(hb, "_deferred_digest", lambda now, path=None: None)
    violations = hb.run(NOW, dry_run=False)
    assert violations
    assert calls and calls[0][0] == "ACTION"          # 红天照响
    st = json.loads((tmp_path / "logs" / "ops_heartbeat_state.json").read_text())
    assert st["violations"] == len(violations)
