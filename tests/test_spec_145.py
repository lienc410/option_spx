"""SPEC-145 — Regime Playbook AC 测试（单真值源 / 点位数学 / 场景映射 / fail-soft）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy.regime_playbook import (              # noqa: E402
    build_payload, compute_levels, scenarios,
)
from strategy.state_flip_notify import (            # noqa: E402
    _DOWN_BREAK_LINE, _UP_BREAK_LINE,
)


# ── AC-1 点位数学（golden：2026-07-13 实值） ─────────────────────────────────

def test_ac1_levels_golden():
    lv = compute_levels(7609.78, 7259.22, 7609.78)
    assert lv["a_trigger"] == pytest.approx(7305.39, abs=0.01)
    assert lv["box_up_death"] == pytest.approx(7631.49, abs=0.05)
    assert lv["box_down_death"] == pytest.approx(7238.57, abs=0.05)
    assert lv["weak_poke_hi"] == pytest.approx(7685.88, abs=0.05)
    assert lv["a_fires_before_box_death"] is True   # 7305.39 > 7238.57
    rungs = {r["rung_pct"]: r for r in lv["b_rungs"]}
    assert rungs[-15.0]["level"] == pytest.approx(6468.31, abs=0.01)
    assert rungs[-15.0]["instrument"] == "SPREAD"
    assert rungs[-25.0]["instrument"] == "XSP_LEAP" and rungs[-25.0]["dte"] == 730
    assert rungs[-45.0]["level"] == pytest.approx(4185.38, abs=0.01)


def test_ac1_degraded_ath_no_fake_levels():
    assert compute_levels(0.0, 7000.0, 7300.0) is None
    lv = compute_levels(7609.78, None, None)        # 无箱体（TREND 期）→ 只给触发线
    assert lv["a_trigger"] > 0 and "box_up_death" not in lv


# ── AC-2 基率文案单真值源（与 SPEC-142 推送逐字符同源） ──────────────────────

def test_ac2_base_rate_lines_identical_to_142():
    all_lines = [l["line"] for sc in scenarios() for l in sc["lines"]]
    assert _UP_BREAK_LINE in all_lines              # import 同一常量，非复制
    assert _DOWN_BREAK_LINE in all_lines


def test_ac2_every_line_has_provenance():
    for sc in scenarios():
        for l in sc["lines"]:
            assert l.get("ref"), f"missing provenance: {l['line'][:30]}"


# ── AC-3 场景映射 + payload 组装（注入式，无磁盘依赖） ────────────────────────

def _row(structure, lo=7259.22, hi=7609.78):
    return {"date": "2026-07-13", "structure_state": structure,
            "surface": {"structure_axis": {"band_lo": lo, "band_hi": hi}}}


def _state(ath=7609.78):
    return {"ath_running_max": ath}


@pytest.mark.parametrize("structure,expected", [
    ("RANGE", "range"), ("TREND_UP", "up_break"),
    ("TREND_DOWN", "down_break"), ("MIXED", None),
])
def test_ac3_active_scenario_mapping(structure, expected):
    p = build_payload(state=_state(), surface_row=_row(structure))
    assert p["active_scenario"] == expected
    assert len(p["scenarios"]) == 3
    assert p["levels"]["a_trigger"] == pytest.approx(7305.39, abs=0.01)


def test_ac3_degraded_flag():
    p = build_payload(state=_state(ath=0.0), surface_row=_row("RANGE"))
    assert p["ath_degraded"] is True and p["levels"] is None
