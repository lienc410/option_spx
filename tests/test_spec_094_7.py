"""SPEC-094.7 — Sleeve B 阶梯 AC 测试（AC-94.7-1..5；6=对齐脚本另验，7=全套回归）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production.q042_executor as ex                        # noqa: E402
import production.q042_positions as pos_mod                  # noqa: E402
from signals.q042_trigger import (                           # noqa: E402
    _B_RUNGS, _default_sleeve_b, _rung_key, migrate_sleeve_b,
    rung_breach_level, update_sleeve_b,
)
from strategy.q042_sizing import (                           # noqa: E402
    b_rung_structure, compute_leap_sizing,
)
from tests.test_spec_094_2 import (                          # noqa: E402
    _default_state, _healthy_runtime, _patch_market, _write_json,
    q042_env,                                                # noqa: F401
)

BANNED = ("IC", "BPS", "BCD", "建议", "优先", "更适合", "适合做")


# ── AC-94.7-1 阶梯状态机 ─────────────────────────────────────────────────────

def test_ac1_shallow_touch_fires_once_per_cycle():
    sb = _default_sleeve_b()
    acts = update_sleeve_b(sb, -0.155, "2026-01-05")
    assert [a["rung"] for a in acts] == [-0.15]
    assert update_sleeve_b(sb, -0.16, "2026-01-06") == []      # armed 已消耗
    update_sleeve_b(sb, -0.01, "2026-02-01")                   # re-arm 全档
    assert [a["rung"] for a in update_sleeve_b(sb, -0.151, "2026-03-01")] == [-0.15]


def test_ac1_gap_crossing_two_rungs_fires_both():
    sb = _default_sleeve_b()
    acts = update_sleeve_b(sb, -0.267, "2020-03-12")
    assert [a["rung"] for a in acts] == [-0.15, -0.25]
    assert all(a["action"] == "fire_B" for a in acts)


def test_ac1_rearm_position_agnostic_latch():
    """armed 复位与在场仓解耦：re-arm 后 rung 仍被在场仓挡；仓清后补发（闩锁）。"""
    sb = _default_sleeve_b()
    update_sleeve_b(sb, -0.26, "d1")                           # -15/-25 fire
    rs = sb["rungs"][_rung_key(-0.25)]
    rs["active_position_id"] = "B-25-d1"
    rs["active_position_expiry"] = "2099-01-01"
    update_sleeve_b(sb, -0.01, "d2")                           # re-arm 全档
    acts = update_sleeve_b(sb, -0.26, "d3")
    assert [a["rung"] for a in acts] == [-0.15]                # -25 被仓挡
    rs["active_position_id"] = None
    rs["active_position_expiry"] = None
    assert [a["rung"] for a in update_sleeve_b(sb, -0.26, "d4")] == [-0.25]


# ── AC-94.7-2 v1→v2 迁移 ─────────────────────────────────────────────────────

def test_ac2_v1_migration_maps_shallow_and_arms_deep():
    v1 = {"armed": False, "in_watching": True, "watch_start_date": "2026-01-01",
          "active_position_id": "B-2026-01-01", "active_position_expiry": "2026-04-01"}
    v2 = migrate_sleeve_b(v1)
    assert v2["schema"] == 2
    sh = v2["rungs"][_rung_key(-0.15)]
    assert sh["armed"] is False and sh["active_position_id"] == "B-2026-01-01"
    for r in (-0.25, -0.35, -0.45):
        assert v2["rungs"][_rung_key(r)]["armed"] is True
    assert migrate_sleeve_b(v2) is v2                          # 幂等


# ── AC-94.7-3 结构路由 ───────────────────────────────────────────────────────

def test_ac3_structure_routing():
    assert b_rung_structure(-0.15) == {"instrument": "SPREAD", "dte": 90, "symbol": "SPX"}
    for r in (-0.25, -0.35, -0.45):
        s = b_rung_structure(r)
        assert s["instrument"] == "XSP_LEAP" and s["dte"] == 730 and s["symbol"] == "XSP"
    k, none_short, cts, est = compute_leap_sizing(500_000, 7400.0, 30.0)
    assert none_short is None
    assert k == round(7400 * 0.85 / 10)                        # 629 (XSP $1 粒度)
    assert cts > 0 and est > 0
    assert compute_leap_sizing(150_000, 7400.0, 30.0) == (None, None, 0, None)


# ── AC-94.7-4 结算 instrument 分支 ───────────────────────────────────────────

def _leap_row(**over):
    r = {"trade_id": "B-25-2026-01-05", "sleeve_id": "B", "signal_date": "2026-01-05",
         "entry_target_date": "2026-01-06", "instrument": "XSP_LEAP", "symbol": "XSP",
         "rung": -0.25, "long_strike": 590, "dte": 730, "est_debit": 11_000.0,
         "fill_debit": None, "contracts": 2, "paper": True, "settled": False,
         "expiry": "2026-02-01"}
    r.update(over)
    return r


def test_ac4_settle_xsp_leap_intrinsic(q042_env):
    q042_env["paper_log"].write_text(json.dumps(_leap_row()) + "\n")
    # SPX 7100 → XSP 710；内在 = 710-590 = 120/share；debit 11000/ct = 110/share
    settled = pos_mod.settle_expired_positions(7100.0, today="2026-02-02", paper=True)
    assert settled == ["B"]
    row = json.loads(q042_env["paper_log"].read_text().splitlines()[0])
    assert row["settled"] is True
    assert row["exit_pnl"] == pytest.approx((120 - 110) * 100 * 2, abs=0.01)


def test_ac4_settle_leap_missing_short_strike_not_poisoned(q042_env):
    """守卫：LEAP 行无 short_strike 字段绝不能走 get(...,0) 默认（把标的当 short 赔付）。"""
    q042_env["paper_log"].write_text(json.dumps(_leap_row(est_debit=1_000.0)) + "\n")
    pos_mod.settle_expired_positions(7100.0, today="2026-02-02", paper=True)
    row = json.loads(q042_env["paper_log"].read_text().splitlines()[0])
    # 若中毒：short_payoff=7100 → exit_pnl 巨额负数
    assert row["exit_pnl"] == pytest.approx((120 - 10) * 100 * 2, abs=0.01)
    assert row["exit_pnl"] > 0


def test_ac4_settle_clears_matching_rung_only(q042_env):
    st = _default_state()
    st["sleeve_b"] = _default_sleeve_b()      # 094.2 helper 仍产 v1 → 升 v2
    sb = st["sleeve_b"]
    sb["rungs"][_rung_key(-0.25)].update(
        active_position_id="B-25-2026-01-05", active_position_expiry="2026-02-01")
    sb["rungs"][_rung_key(-0.35)].update(
        active_position_id="B-35-2026-01-08", active_position_expiry="2027-01-08")
    _write_json(q042_env["state_file"], st)
    q042_env["paper_log"].write_text(json.dumps(_leap_row()) + "\n")
    pos_mod.settle_expired_positions(7100.0, today="2026-02-02", paper=True)
    new = json.loads(q042_env["state_file"].read_text())
    assert new["sleeve_b"]["rungs"][_rung_key(-0.25)]["active_position_id"] is None
    assert new["sleeve_b"]["rungs"][_rung_key(-0.35)]["active_position_id"] == "B-35-2026-01-08"


# ── AC-94.7-5 rung 击穿 FYI（一生一次 + F2 + dry-run 静默）──────────────────

def _state_with_shallow_pos(ath=1000.0):
    st = _default_state(ath_running_max=ath,
                        sleeve_a={"armed": False, "active_position_id": None,
                                  "active_position_expiry": None})
    st["sleeve_b"] = _default_sleeve_b()      # 094.2 helper 仍产 v1 → 升 v2
    st["sleeve_b"]["rungs"][_rung_key(-0.15)].update(
        active_position_id="B-15-2026-07-01", active_position_expiry="2026-10-01")
    st["sleeve_b"]["rungs"][_rung_key(-0.15)]["armed"] = False
    return st


def test_ac5_breach_fyi_once(q042_env, monkeypatch):
    _write_json(q042_env["runtime"], _healthy_runtime())
    # ddath = 740/1000-1 = -26% ≤ 击穿线 -25%（-15 档持仓）→ FYI；-25 档同日 fire 被 cap0 拦截
    _write_json(q042_env["state_file"], _state_with_shallow_pos())
    _patch_market(monkeypatch, spx_close=740.0, today_str="2026-07-20")
    ex.run_eod_evaluation(dry_run=False)
    breach = [p for p in q042_env["pushes"] if "rung 击穿" in p["title"]]
    assert len(breach) == 1
    assert breach[0]["category"] == "FYI"
    assert breach[0]["dedupe_key"] == "q042_rungbreach_B-15-2026-07-01"
    text = breach[0]["title"] + breach[0]["body"]
    for w in BANNED:
        assert w not in text, w
    st = json.loads(q042_env["state_file"].read_text())
    assert "B-15-2026-07-01" in st["sleeve_b"]["breach_alerted"]
    # 第二天仍击穿 → 不再推
    q042_env["pushes"].clear()
    _patch_market(monkeypatch, spx_close=730.0, today_str="2026-07-21")
    ex.run_eod_evaluation(dry_run=False)
    assert [p for p in q042_env["pushes"] if "rung 击穿" in p["title"]] == []


def test_ac5_breach_dry_run_silent(q042_env, monkeypatch):
    _write_json(q042_env["runtime"], _healthy_runtime())
    _write_json(q042_env["state_file"], _state_with_shallow_pos())
    _patch_market(monkeypatch, spx_close=740.0, today_str="2026-07-20")
    ex.run_eod_evaluation(dry_run=True)
    assert [p for p in q042_env["pushes"] if "rung 击穿" in p["title"]] == []


# ── 补充：cap0 下 gap 日双档拦截（dedupe 不互吞）──────────────────────────────

def test_gap_day_two_rungs_two_blocked_fyi(q042_env, monkeypatch):
    _write_json(q042_env["runtime"], _healthy_runtime())
    _write_json(q042_env["state_file"], _default_state(
        ath_running_max=1300.0,
        sleeve_a={"armed": False, "active_position_id": None,
                  "active_position_expiry": None}))
    _patch_market(monkeypatch, spx_close=950.0, today_str="2026-07-20")  # dd -26.9%
    fired = ex.run_eod_evaluation(dry_run=False)
    assert fired == []                                         # cap 0 全拦
    blocked = [p for p in q042_env["pushes"] if "被拦截" in p["title"]]
    assert len(blocked) == 2
    assert {p["dedupe_key"] for p in blocked} == {
        "q042_blocked_B-15_2026-07-20", "q042_blocked_B-25_2026-07-20"}
    assert all(p["category"] == "FYI" for p in blocked)        # by-design → FYI
