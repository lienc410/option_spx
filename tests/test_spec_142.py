"""SPEC-142 — 状态转换 FYI 通知 AC 测试（AC-142-1..5；6 = 全套回归另跑）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy.state_flip_notify import (  # noqa: E402
    _BANNED, _assert_clean, notify_state_flips,
)

BANNED_SET = {"IC", "BPS", "BCD", "建议", "优先", "更适合", "适合做"}


def _row(date, structure, vol, *, backfill=False, surface=None):
    r = {"date": date, "backfill": backfill,
         "structure_state": structure, "vol_state": vol}
    if surface is not None:
        r["surface"] = surface
    return r


def _write_log(tmp_path, rows):
    p = tmp_path / "state_surface.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _surface_range(day=15, lo=7259.22, hi=7609.78, ammo_ok=True):
    ammo = ({"status": "ok", "liquid": 231_000.0, "reserve_need": 78_600.0,
             "ready": True} if ammo_ok else {"status": "n/a", "error": "boom"})
    return {"structure_axis": {"status": "ok", "state": "RANGE",
                               "episode_day": day, "band_lo": lo, "band_hi": hi},
            "vol_axis": {"status": "ok", "state": "NORMAL", "vix": 17.2},
            "trend_signal": {"status": "ok", "spx": 7500.0},
            "ammo": ammo}


def _surface_trend(spx=7650.0, vix=17.2, vol_state="NORMAL"):
    return {"structure_axis": {"status": "ok", "state": "TREND_UP",
                               "episode_day": None, "band_lo": None, "band_hi": None},
            "vol_axis": {"status": "ok", "state": vol_state, "vix": vix},
            "trend_signal": {"status": "ok", "spx": spx},
            "ammo": {"status": "ok", "liquid": 231_000.0,
                     "reserve_need": 78_600.0, "ready": True}}


class Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, category, about, title, body, *, dedupe_key=None, **kw):
        self.calls.append(dict(category=category, about=about, title=title,
                               body=body, dedupe_key=dedupe_key))
        return True


# ── AC-142-1 转换触发与模板字段 ────────────────────────────────────────────────

def test_ac1_trend_to_range_fires_with_band_and_ammo(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "TREND_UP", "NORMAL", surface=_surface_trend()),
        _row("2026-07-13", "RANGE", "NORMAL", surface=_surface_range()),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["status"] == "ok" and res["pushed"] == 1
    (c,) = cap.calls
    assert c["category"] == "FYI" and c["about"] == "系统状态"
    assert c["title"] == "结构轴翻转：TREND_UP → RANGE"
    assert "过去 15TD 困于 7,259.22–7,609.78" in c["body"]
    assert "4.7% 箱" in c["body"]
    assert "liquid $231,000 vs reserve $78,600 ✓" in c["body"]
    assert c["dedupe_key"] == "state_flip_structure_2026-07-13"


def test_ac1_range_to_trend_fires_with_break_direction(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "RANGE", "NORMAL", surface=_surface_range()),
        _row("2026-07-13", "TREND_UP", "NORMAL", surface=_surface_trend(spx=7650.0)),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["pushed"] == 1
    (c,) = cap.calls
    assert c["title"] == "结构轴翻转：RANGE → TREND_UP"
    assert "向上破箱 @ 7,650.00（原箱体 7,259.22–7,609.78）" in c["body"]
    assert "弱上破" in c["body"] and "5-10 个交易日" in c["body"]   # P3b 双面事实
    assert "3.3%" in c["body"]


def test_ac1_down_break_gets_down_line(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "RANGE", "NORMAL", surface=_surface_range()),
        _row("2026-07-13", "TREND_DOWN", "NORMAL",
             surface=_surface_trend(spx=7100.0)),
    ])
    cap = Capture()
    notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    (c,) = cap.calls
    assert "向下破箱 @ 7,100.00" in c["body"]
    assert "2026-03-13" in c["body"] and "14% vs 7%" in c["body"]


def test_ac1_vol_flip_fires_with_vix(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "RANGE", "NORMAL", surface=_surface_range()),
        _row("2026-07-13", "RANGE", "HIGH",
             surface=_surface_range() | {"vol_axis": {"status": "ok",
                                                      "state": "HIGH", "vix": 24.8}}),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["pushed"] == 1
    (c,) = cap.calls
    assert c["title"] == "Vol 轴翻转：NORMAL → HIGH（VIX 24.8）"
    assert c["dedupe_key"] == "state_flip_vol_2026-07-13"


def test_ac1_both_axes_flip_two_pushes(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "TREND_UP", "NORMAL", surface=_surface_trend()),
        _row("2026-07-13", "RANGE", "HIGH",
             surface=_surface_range() | {"vol_axis": {"status": "ok",
                                                      "state": "HIGH", "vix": 25.1}}),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["pushed"] == 2
    assert {c["dedupe_key"] for c in cap.calls} == {
        "state_flip_structure_2026-07-13", "state_flip_vol_2026-07-13"}


# ── AC-142-2 F2 负向断言 ──────────────────────────────────────────────────────

def test_ac2_no_banned_words_in_any_template(tmp_path):
    scenarios = [
        ([_row("2026-07-10", "TREND_UP", "NORMAL", surface=_surface_trend()),
          _row("2026-07-13", "RANGE", "HIGH", surface=_surface_range())]),
        ([_row("2026-07-10", "RANGE", "NORMAL", surface=_surface_range()),
          _row("2026-07-13", "TREND_DOWN", "CALM",
               surface=_surface_trend(spx=7100.0, vol_state="CALM", vix=12.0))]),
        ([_row("2026-07-10", "RANGE", "NORMAL",
               surface=_surface_range(ammo_ok=False)),
          _row("2026-07-13", "MIXED", "EXTREME",
               surface=_surface_trend(vol_state="EXTREME", vix=36.0))]),
    ]
    for rows in scenarios:
        cap = Capture()
        notify_state_flips(date="2026-07-13",
                           log_path=_write_log(tmp_path, rows), _push=cap)
        for c in cap.calls:
            text = c["title"] + "\n" + c["body"]
            for w in BANNED_SET:
                assert w not in text, f"banned {w!r} in {text!r}"


def test_ac2_guard_raises_loud_on_banned():
    with pytest.raises(ValueError, match="F2 violation"):
        _assert_clean("这个状态更适合做某结构")
    assert set(_BANNED) == BANNED_SET       # 守卫词表与 AC 词表同源不漂移


# ── AC-142-3 弹药行 n/a 不阻塞 ────────────────────────────────────────────────

def test_ac3_ammo_na_still_pushes(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "TREND_UP", "NORMAL", surface=_surface_trend()),
        _row("2026-07-13", "RANGE", "NORMAL",
             surface=_surface_range(ammo_ok=False)),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["pushed"] == 1
    assert "弹药检查：n/a" in cap.calls[0]["body"]


# ── AC-142-4 无变化 / backfill / n-a → 零推送 ─────────────────────────────────

def test_ac4_no_change_zero_push(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "RANGE", "NORMAL", surface=_surface_range()),
        _row("2026-07-13", "RANGE", "NORMAL", surface=_surface_range(day=17)),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["pushed"] == 0 and cap.calls == []


def test_ac4_backfill_today_zero_push(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "TREND_UP", "NORMAL", backfill=True),
        _row("2026-07-13", "RANGE", "NORMAL", backfill=True),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["status"] == "skipped" and cap.calls == []


def test_ac4_na_state_skips_axis_not_all(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", None, "NORMAL", backfill=True),
        _row("2026-07-13", "RANGE", "HIGH",
             surface=_surface_range() | {"vol_axis": {"status": "ok",
                                                      "state": "HIGH", "vix": 25.0}}),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["pushed"] == 1                       # 只有 vol 轴（structure 侧 n/a）
    assert cap.calls[0]["dedupe_key"] == "state_flip_vol_2026-07-13"


def test_ac4_stale_log_date_mismatch_skips(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-09", "TREND_UP", "NORMAL", surface=_surface_trend()),
        _row("2026-07-10", "RANGE", "NORMAL", surface=_surface_range()),
    ])
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    assert res["status"] == "skipped" and cap.calls == []


# ── AC-142-5 dedupe key / dry-run 零推送零落盘 ────────────────────────────────

def test_ac5_dry_run_builds_but_never_pushes(tmp_path):
    rows = [
        _row("2026-07-10", "TREND_UP", "NORMAL", surface=_surface_trend()),
        _row("2026-07-13", "RANGE", "HIGH", surface=_surface_range()),
    ]
    log = _write_log(tmp_path, rows)
    before = log.read_text(encoding="utf-8")
    cap = Capture()
    res = notify_state_flips(date="2026-07-13", log_path=log,
                             dry_run=True, _push=cap)
    assert cap.calls == [] and res["pushed"] == 0
    assert all(f.get("dry_run") for f in res["flips"] if "title" in f)
    titles = [f["title"] for f in res["flips"] if "title" in f]
    assert any("结构轴翻转" in t for t in titles)
    assert log.read_text(encoding="utf-8") == before      # 零落盘
    assert not (tmp_path / "notify_dedupe.json").exists()


def test_ac5_dedupe_key_per_axis_per_date(tmp_path):
    log = _write_log(tmp_path, [
        _row("2026-07-10", "RANGE", "CALM", surface=_surface_range()),
        _row("2026-07-13", "TREND_UP", "NORMAL", surface=_surface_trend()),
    ])
    cap = Capture()
    notify_state_flips(date="2026-07-13", log_path=log, _push=cap)
    keys = [c["dedupe_key"] for c in cap.calls]
    assert keys == ["state_flip_structure_2026-07-13", "state_flip_vol_2026-07-13"]
