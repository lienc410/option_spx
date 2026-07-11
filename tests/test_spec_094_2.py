"""SPEC-094.2 — Q042 执行层完整性修复包 AC-94.2-1..9.

覆盖 F1（结算 wiring）/F2+B4（expiry 三级推导 + 事件过滤）/F3+B1（gate 数据源
fail-closed）/F4+B6（dry-run 语义）/F5+N2（blocked 告警 + 落盘）/F6+B2
（combined_bp_pct writer 单位契约）/F7（snapshot ATH degraded）。

密闭：AC-94.2-1 是非 mock integration smoke —— 真实结构的 sleeve_governance_
runtime.json fixture，走完读文件→取字段→算值链路，禁止 monkeypatch
read_main_bp_pct 返回值（只重写 fixture timestamp 过 staleness gate，N1）。
所有 executor 测试把四个账本/state/gate log/runtime.json 与 gateway.push 全部
重定向到 tmp，绝不触碰生产文件或真实推送。
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import production.q042_executor as ex
import production.q042_positions as pos
import signals.q042_trigger as trig
import strategy.q042_gate as gate

ET = ZoneInfo("America/New_York")


# ── Fixtures / helpers ─────────────────────────────────────────────────────────

def _fresh_ts(days_ago: int = 0) -> str:
    return (datetime.now(ET) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def _healthy_runtime(spx_pm_bp_pct: float = 18.61, *, ts: str | None = None) -> dict:
    """A realistic NON-degraded sleeve_governance_runtime.json snapshot
    (mirrors current_governance_state output shape: pools=all view with
    nlv_basis>0, pools_by_view.schwab present, status available)."""
    return {
        "timestamp": ts or _fresh_ts(),
        "status": "available",
        "errors": [],
        "basis_dollars": 629_000.0,
        "basis_degraded": False,
        "pools": {
            "view": "all",
            "nlv_basis": 629_000.0,
            "spx_pm_bp_pct": spx_pm_bp_pct,
            "spx_pm_bp_dollars": round(629_000.0 * spx_pm_bp_pct / 100.0, 2),
            "es_span_bp_pct": 0.0,
            "combined_bp_pct": spx_pm_bp_pct,
            "short_vol_bp_pct": 0.0,
        },
        "pools_by_view": {
            "all": {"view": "all", "nlv_basis": 629_000.0, "spx_pm_bp_pct": spx_pm_bp_pct},
            "schwab": {"view": "schwab", "nlv_basis": 560_000.0, "spx_pm_bp_pct": 16.77},
            "etrade": None,
        },
    }


def _degraded_runtime() -> dict:
    """2026-07-07 本机实测 degraded 形态：pools 全零 + pools_by_view 全 null +
    basis_degraded true + timestamp 新鲜。"""
    return {
        "timestamp": _fresh_ts(),
        "status": "available",
        "errors": [],
        "basis_dollars": None,
        "basis_degraded": True,
        "pools": {
            "spx_pm_bp_pct": 0.0,
            "spx_pm_bp_dollars": 0.0,
            "es_span_bp_pct": 0.0,
            "combined_bp_pct": 0.0,
            "short_vol_bp_pct": 0.0,
        },
        "pools_by_view": {"all": None, "schwab": None, "etrade": None},
    }


def _zero_bp_runtime() -> dict:
    """status available + timestamp 新鲜 + basis 正常，但 spx_pm_bp_pct=0.0
    (上游 broker maint 字段静默缺失 → plausibility gate 必须拦)。"""
    r = _healthy_runtime(spx_pm_bp_pct=0.0)
    return r


@pytest.fixture
def q042_env(tmp_path, monkeypatch):
    """Redirect every Q042 disk surface + gateway push to tmp/recorder."""
    runtime = tmp_path / "sleeve_governance_runtime.json"
    gate_log = tmp_path / "q042_gate_log.jsonl"
    state_file = tmp_path / "q042_state.json"
    paper_log = tmp_path / "q042_paper_trades.jsonl"
    live_log = tmp_path / "q042_live_trades.jsonl"

    monkeypatch.setattr(gate, "RUNTIME_STATE_PATH", runtime)
    monkeypatch.setattr(gate, "GATE_LOG", gate_log)
    monkeypatch.setattr(trig, "STATE_FILE", state_file)
    monkeypatch.setattr(pos, "PAPER_LOG", paper_log)
    monkeypatch.setattr(pos, "LIVE_LOG", live_log)
    monkeypatch.setattr(ex, "PAPER_LOG", paper_log)  # executor writes pending here

    # F5b cash context → deterministic n/a-free line (isolated from live brokers).
    import strategy.cash_budget_governance as cbg
    monkeypatch.setattr(cbg, "get_current_liquid_cash", lambda: {"total": 412_000.0})
    monkeypatch.setattr(cbg, "get_open_debit_total_usd", lambda: {"total": 51_000.0})

    # Capture gateway pushes (bypass transport/dedupe entirely).
    pushes: list[dict] = []
    import notify.gateway as gw

    def _record(category, about, title, body="", *, dedupe_key=None, **kw):
        pushes.append({"category": category, "about": about, "title": title,
                       "body": body, "dedupe_key": dedupe_key})
        return True

    monkeypatch.setattr(gw, "push", _record)

    return {
        "runtime": runtime, "gate_log": gate_log, "state_file": state_file,
        "paper_log": paper_log, "live_log": live_log, "pushes": pushes,
    }


def _write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _default_state(**overrides) -> dict:
    st = {
        "ath_running_max": 1000.0,
        "ath_last_update": "2026-07-01",
        "sleeve_a": {"armed": True, "active_position_id": None, "active_position_expiry": None},
        "sleeve_b": {"armed": True, "in_watching": False, "watch_start_date": None,
                     "active_position_id": None, "active_position_expiry": None},
        "combined_bp_pct": 0.0,
    }
    st.update(overrides)
    return st


class _FakeYF:
    """Stand-in for yfinance: history() returns a controlled SPX close series so
    ma10/cal are deterministic and no network is touched."""
    def __init__(self, closes, dates):
        self._df = pd.DataFrame({"Close": closes}, index=pd.DatetimeIndex(dates))

    def Ticker(self, *_a, **_k):
        outer = self

        class _T:
            def history(self, *a, **k):
                return outer._df
        return _T()


def _patch_market(monkeypatch, *, spx_close, today_str, vix=20.0, nlv=500_000.0,
                  ma10_closes=None):
    monkeypatch.setattr(ex, "_fetch_spx_close", lambda: (spx_close, today_str))
    monkeypatch.setattr(ex, "_fetch_vix", lambda: vix)
    monkeypatch.setattr(ex, "_fetch_nlv", lambda: nlv)
    dates = pd.bdate_range(end=today_str, periods=len(ma10_closes or [1] * 12))
    closes = ma10_closes if ma10_closes is not None else [spx_close] * len(dates)
    monkeypatch.setattr(ex, "yf", _FakeYF(closes, dates))


# ── AC-94.2-1 — F3 integration smoke (NON-mock) ────────────────────────────────

def test_ac1_f3_integration_smoke_reads_pool_value(q042_env):
    _write_json(q042_env["runtime"], _healthy_runtime(spx_pm_bp_pct=18.61))
    # 真链路：读文件 → 取 pools.spx_pm_bp_pct → 返回；无 monkeypatch 返回值。
    val = gate.read_main_bp_pct()
    assert val == pytest.approx(18.61)
    assert val > 0
    detail = gate.read_main_bp_source()
    assert detail["reason"] is None
    assert detail["schwab_view_pct"] == pytest.approx(16.77)
    assert detail["timestamp"] is not None
    assert "spx_pm_bp_pct" in detail["source"]


def test_ac1_fixture_asserts_non_degraded_nlv_basis_positive(q042_env):
    snap = _healthy_runtime()
    assert snap["pools"]["nlv_basis"] > 0
    assert snap["basis_degraded"] is False


# ── AC-94.2-2 — F3 fail-closed 三例 ─────────────────────────────────────────────

def test_ac2a_missing_file_and_stale(q042_env):
    # (a1) missing file
    assert not q042_env["runtime"].exists()
    assert gate.read_main_bp_pct() is None
    assert gate.read_main_bp_source()["reason"] == "missing_file"
    # (a2) stale > 2 trading days (timestamp 5 calendar days ago)
    _write_json(q042_env["runtime"], _healthy_runtime(ts=_fresh_ts(days_ago=5)))
    assert gate.read_main_bp_pct() is None
    assert gate.read_main_bp_source()["reason"] == "stale"


def test_ac2b_degraded_fixture(q042_env):
    _write_json(q042_env["runtime"], _degraded_runtime())
    assert gate.read_main_bp_pct() is None
    assert gate.read_main_bp_source()["reason"] in ("basis_degraded", "degraded_pools")


def test_ac2c_zero_bp_available_fresh(q042_env):
    _write_json(q042_env["runtime"], _zero_bp_runtime())
    assert gate.read_main_bp_pct() is None
    assert gate.read_main_bp_source()["reason"] == "nonpositive_bp"


@pytest.mark.parametrize("runtime_builder,expected_reason", [
    (None, "missing_file"),
    (_degraded_runtime, None),
    (_zero_bp_runtime, "nonpositive_bp"),
])
def test_ac2_executor_blocks_fire_on_unavailable(q042_env, monkeypatch,
                                                 runtime_builder, expected_reason):
    """三例 fail-closed 均须：executor 拦截 fire + ACTION 告警 + blocked record。"""
    if runtime_builder is not None:
        _write_json(q042_env["runtime"], runtime_builder())
    # Sleeve A should fire: ddath = 950/1000-1 = -5% ≤ -4%.
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0))
    _patch_market(monkeypatch, spx_close=950.0, today_str="2026-07-08")

    fired = ex.run_eod_evaluation(dry_run=False, verbose=False)

    assert fired == []                                     # fire held
    st = json.loads(q042_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] is None    # no position taken
    assert not q042_env["paper_log"].exists() or q042_env["paper_log"].read_text() == ""
    rows = [json.loads(l) for l in q042_env["gate_log"].read_text().splitlines() if l]
    blocked = [r for r in rows if "blocked_fire" in r]
    assert len(blocked) == 1
    assert blocked[0]["blocked_fire"]["reason"] == "gate_unavailable"
    actions = [p for p in q042_env["pushes"] if p["category"] == "ACTION"]
    assert actions, "expected an ACTION push on fail-closed block"


# ── AC-94.2-3 — F1 settlement wiring ───────────────────────────────────────────

def _open_record(sleeve, signal_date, expiry, *, contracts=1, est_debit=5000.0,
                 long_strike=1000, short_strike=1050, dte=30):
    return {
        "trade_id": f"{sleeve}-{signal_date}", "event": "open", "sleeve_id": sleeve,
        "signal_date": signal_date,
        "entry_target_date": (datetime.strptime(signal_date, "%Y-%m-%d")
                              + timedelta(days=1)).strftime("%Y-%m-%d"),
        "expiry": expiry, "dte": dte,
        "long_strike": long_strike, "short_strike": short_strike,
        "contracts": contracts, "est_debit": est_debit, "fill_debit": None,
        "settled": False, "exit_pnl": None,
    }


def test_ac3_settle_yesterday_expiry_then_fire(q042_env, monkeypatch):
    today = "2026-07-08"
    yesterday = "2026-07-07"
    note_row = {"event": "note", "timestamp": "2026-07-07T10:00:00", "note": "PM comment"}
    _write_jsonl(q042_env["paper_log"], [
        _open_record("A", "2026-06-06", yesterday), note_row,   # B4: note must not crash
    ])
    _write_json(q042_env["state_file"], _default_state(
        ath_running_max=1000.0,
        sleeve_a={"armed": True, "active_position_id": "A-2026-06-06",
                  "active_position_expiry": yesterday},
    ))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=950.0, today_str=today)  # ddath -5% → fire

    fired = ex.run_eod_evaluation(dry_run=False)

    ledger = [json.loads(l) for l in q042_env["paper_log"].read_text().splitlines() if l]
    settled = [t for t in ledger if t.get("event") == "open" and t["trade_id"] == "A-2026-06-06"]
    assert settled and settled[0]["settled"] is True       # settled=true
    st = json.loads(q042_env["state_file"].read_text())
    # today's trigger fired → NEW position present (old one was cleared first)
    assert any(f.sleeve_id == "A" for f in fired)
    assert st["sleeve_a"]["active_position_id"] == "A-2026-07-08"


def test_ac3_boundary_expiry_today_not_rolled_back(q042_env, monkeypatch):
    """expiry=当日：当日结算 + 当日 re-fire，且 EOD 全流程后 state 不被
    pre-settle 副本回滚 (N3)。"""
    today = "2026-07-08"
    _write_jsonl(q042_env["paper_log"], [_open_record("A", "2026-06-07", today)])
    _write_json(q042_env["state_file"], _default_state(
        ath_running_max=1000.0,
        sleeve_a={"armed": True, "active_position_id": "A-2026-06-07",
                  "active_position_expiry": today},
    ))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=950.0, today_str=today)

    fired = ex.run_eod_evaluation(dry_run=False)

    ledger = [json.loads(l) for l in q042_env["paper_log"].read_text().splitlines() if l]
    old = [t for t in ledger if t.get("trade_id") == "A-2026-06-07"][0]
    assert old["settled"] is True                          # settled same day
    st = json.loads(q042_env["state_file"].read_text())
    # NOT rolled back to the settled position; reflects the same-day re-fire.
    assert st["sleeve_a"]["active_position_id"] == "A-2026-07-08"
    assert any(f.sleeve_id == "A" for f in fired)


# ── AC-94.2-4 — F2 expiry derivation (off-by-one fix) ──────────────────────────

def test_ac4_expiry_three_tier():
    entry = datetime(2026, 1, 2)
    exp_a = pos._derive_expiry({"entry_target_date": "2026-01-02", "dte": 30})
    assert exp_a == (entry + timedelta(days=30)).strftime("%Y-%m-%d")  # Sleeve A entry+30
    exp_b = pos._derive_expiry({"entry_target_date": "2026-01-02", "dte": 90})
    assert exp_b == (entry + timedelta(days=90)).strftime("%Y-%m-%d")  # Sleeve B entry+90 (fix off-by-1)
    # explicit expiry wins over dte-derivation
    exp_manual = pos._derive_expiry({"entry_target_date": "2026-01-02", "dte": 30,
                                     "expiry": "2026-03-15"})
    assert exp_manual == "2026-03-15"
    # note row with no date fields → None (no raise, B4)
    assert pos._derive_expiry({"event": "note", "note": "hi"}) is None


# ── AC-94.2-5 — F4 dry-run: bytes unchanged, no push, no record ────────────────

def test_ac5_dry_run_no_disk_no_push(q042_env, monkeypatch):
    today = "2026-07-08"
    # fixture MUST contain an already-expired position (else B6 untested).
    _write_jsonl(q042_env["paper_log"], [_open_record("A", "2026-06-06", "2026-07-07")])
    _write_jsonl(q042_env["live_log"], [])
    _write_json(q042_env["state_file"], _default_state(
        ath_running_max=1000.0,
        sleeve_a={"armed": True, "active_position_id": "A-2026-06-06",
                  "active_position_expiry": "2026-07-07"},
    ))
    q042_env["gate_log"].write_text("")   # pre-existing empty gate log
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=950.0, today_str=today)

    before = {k: q042_env[k].read_bytes() for k in
              ("paper_log", "live_log", "state_file", "gate_log")}

    ex.run_eod_evaluation(dry_run=True, verbose=False)

    after = {k: q042_env[k].read_bytes() for k in
             ("paper_log", "live_log", "state_file", "gate_log")}
    assert before == after, "dry-run must not mutate any Q042 disk surface"
    assert q042_env["pushes"] == []        # no Telegram


# ── AC-94.2-6 — F5 blocked alert + record ──────────────────────────────────────

def test_ac6_gate_zero_blocks_sleeve_a(q042_env, monkeypatch):
    today = "2026-07-08"
    # main_bp 65% → compute_gate cap=0 → sleeve_a_allowance=0.
    _write_json(q042_env["runtime"], _healthy_runtime(spx_pm_bp_pct=65.0))
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0))
    _patch_market(monkeypatch, spx_close=950.0, today_str=today)  # ddath -5% → fire_A

    fired = ex.run_eod_evaluation(dry_run=False)

    assert fired == []
    rows = [json.loads(l) for l in q042_env["gate_log"].read_text().splitlines() if l]
    blocked = [r for r in rows if "blocked_fire" in r]
    assert len(blocked) == 1
    assert blocked[0]["blocked_fire"]["sleeve"] == "A"
    assert blocked[0]["blocked_fire"]["reason"] == "gate_binding_allowance_0"
    actions = [p for p in q042_env["pushes"] if p["category"] == "ACTION"]
    assert len(actions) == 1


def test_ac6_fire_b_is_fyi_by_design(q042_env, monkeypatch):
    today = "2026-07-08"
    _write_json(q042_env["runtime"], _healthy_runtime())  # gate available
    # Sleeve B fires via inner trigger: in_watching + close>ma10.
    _write_json(q042_env["state_file"], _default_state(
        ath_running_max=980.0,   # ddath = 950/980-1 = -3.06% (Sleeve A does NOT fire)
        sleeve_b={"armed": False, "in_watching": True, "watch_start_date": today,
                  "active_position_id": None, "active_position_expiry": None},
    ))
    # ma10 = 900 < spx_close 950 → inner fire_B; feed 12 flat closes at 900.
    _patch_market(monkeypatch, spx_close=950.0, today_str=today,
                  ma10_closes=[900.0] * 12)

    fired = ex.run_eod_evaluation(dry_run=False)

    assert fired == []                     # production cap 0 → held
    rows = [json.loads(l) for l in q042_env["gate_log"].read_text().splitlines() if l]
    blocked = [r for r in rows if "blocked_fire" in r]
    assert len(blocked) == 1
    assert blocked[0]["blocked_fire"]["sleeve"] == "B"
    assert blocked[0]["blocked_fire"]["reason"] == "sleeve_b_production_cap_0_by_design"
    # N2: degraded to FYI (not ACTION)
    assert any(p["category"] == "FYI" for p in q042_env["pushes"])
    assert not any(p["category"] == "ACTION" for p in q042_env["pushes"])


# ── AC-94.2-7 — F6 combined_bp_pct encoding (B2) ───────────────────────────────

def test_ac7_committed_debit_encoding(q042_env, monkeypatch):
    today = "2026-07-08"
    # est_debit=25000 (per contract) × 2 = $50k committed; NLV 500k → 10.0%.
    _write_jsonl(q042_env["paper_log"], [
        _open_record("A", "2026-07-01", "2026-08-01", contracts=2, est_debit=25000.0),
    ])
    committed = pos.get_active_committed_debit_usd(today=today)
    assert committed == 50000.0            # NOT ×100 again (B2)

    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0))
    _write_json(q042_env["runtime"], _healthy_runtime())
    # ddath 0 (spx==ath) → no fire; just exercise the F6 writer.
    _patch_market(monkeypatch, spx_close=1000.0, today_str=today, nlv=500_000.0)

    ex.run_eod_evaluation(dry_run=False)
    st = json.loads(q042_env["state_file"].read_text())
    assert st["combined_bp_pct"] == 10.0


def test_ac7_nlv_zero_skips_write(q042_env, monkeypatch):
    today = "2026-07-08"
    _write_jsonl(q042_env["paper_log"], [
        _open_record("A", "2026-07-01", "2026-08-01", contracts=2, est_debit=25000.0),
    ])
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0,
                                                       combined_bp_pct=7.77))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=1000.0, today_str=today, nlv=0.0)  # NLV unavailable

    ex.run_eod_evaluation(dry_run=False)
    st = json.loads(q042_env["state_file"].read_text())
    assert st["combined_bp_pct"] == 7.77   # prior value preserved (never 0)


def test_ac7_snapshot_reflects_combined_bp(q042_env):
    """/api/q042/state monitor 反映之 —— via the snapshot the route serialises."""
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0,
                                                       combined_bp_pct=10.0))
    df = pd.DataFrame({"close": [1000.0, 1000.0]},
                      index=pd.DatetimeIndex(["2026-07-07", "2026-07-08"]))
    snap = trig.get_current_q042_snapshot(spx_df=df)
    assert snap.combined_bp_pct == 10.0


# ── AC-94.2-8 — gate log carries bp_source + timestamp when available ───────────

def test_ac8_gate_log_has_bp_source_when_available(q042_env, monkeypatch):
    today = "2026-07-08"
    _write_json(q042_env["runtime"], _healthy_runtime(spx_pm_bp_pct=18.61))
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0))
    _patch_market(monkeypatch, spx_close=1000.0, today_str=today)  # no fire

    ex.run_eod_evaluation(dry_run=False)
    rows = [json.loads(l) for l in q042_env["gate_log"].read_text().splitlines() if l]
    gate_rows = [r for r in rows if "main_bp_pct" in r]
    assert gate_rows
    row = gate_rows[-1]
    assert row["main_bp_pct"] and row["main_bp_pct"] > 0
    assert row["bp_source"]["timestamp"] is not None
    assert "spx_pm_bp_pct" in row["bp_source"]["source"]


# ── AC-94.2-9 — F7 snapshot ATH degraded ───────────────────────────────────────

def test_ac9_snapshot_ath_degraded(q042_env):
    # state ath = 0 → degraded; must NOT substitute the 1mo window max.
    _write_json(q042_env["state_file"], _default_state(ath_running_max=0.0))
    df = pd.DataFrame({"close": [1000.0, 900.0]},   # window max 1000, last 900
                      index=pd.DatetimeIndex(["2026-07-07", "2026-07-08"]))
    snap = trig.get_current_q042_snapshot(spx_df=df)
    assert snap.ath_degraded is True
    assert snap.ath_running_max == 900.0            # == spx_close, NOT 1000 window max
    assert snap.ddath == pytest.approx(0.0)


def test_ac9_snapshot_ath_healthy(q042_env):
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0))
    df = pd.DataFrame({"close": [1000.0, 900.0]},
                      index=pd.DatetimeIndex(["2026-07-07", "2026-07-08"]))
    snap = trig.get_current_q042_snapshot(spx_df=df)
    assert snap.ath_degraded is False
    assert snap.ath_running_max == 1000.0
    assert snap.ddath == pytest.approx(-0.10)


def test_ac9_server_serializes_ath_degraded(q042_env, monkeypatch):
    """AC-9 消费端前半：/api/q042/state 透出 ath_degraded（web/server.py 只增字段，
    Quant 2026-07-10 授权补文件清单）。"""
    from web.server import app

    orig_snap = trig.get_current_q042_snapshot

    def _api_for(state_ath: float) -> dict:
        _write_json(q042_env["state_file"], _default_state(ath_running_max=state_ath))
        df = pd.DataFrame({"close": [1000.0, 900.0]},
                          index=pd.DatetimeIndex(["2026-07-07", "2026-07-08"]))
        # route does a call-time `from signals.q042_trigger import ...` — patch
        # the module attribute; the wrapped call still runs the REAL snapshot code.
        monkeypatch.setattr(trig, "get_current_q042_snapshot",
                            lambda spx_df=None: orig_snap(spx_df=df))
        return app.test_client().get("/api/q042/state").get_json()

    degraded = _api_for(0.0)
    assert degraded["ath_degraded"] is True
    healthy = _api_for(1000.0)
    assert healthy["ath_degraded"] is False
    assert healthy["ddath_pct"] == pytest.approx(-10.0)


def test_ac9_daily_snapshot_skips_ddath_when_degraded(q042_env, monkeypatch, capsys):
    """AC-9 消费端后半：daily_snapshot 遇 ath_degraded → warning + ddath 记 null。"""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "daily_snapshot.py"
    spec = importlib.util.spec_from_file_location("daily_snapshot_under_test", path)
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)

    def _canned_fetch(q042_payload):
        def _fetch(p, timeout=30):
            if p == "/api/portfolio/summary":
                return {"account_breakdown": {"schwab_nlv": 500_000.0, "etrade_nlv": 0.0},
                        "bp_usage_by_bucket": {}}
            if p == "/api/q042/state":
                return q042_payload
            return None
        return _fetch

    degraded_payload = {"ath_degraded": True, "ddath_pct": 0.0, "spx_close": 900.0,
                        "sleeve_a": {}, "sleeve_b": {}, "combined_bp_pct": 0.0}
    monkeypatch.setattr(ds, "_fetch", _canned_fetch(degraded_payload))
    monkeypatch.setattr(ds, "_attach_broker_greeks", lambda positions: None)
    rec = ds.build_record()
    assert rec is not None
    assert rec["regime"]["ddath_pct"] is None          # 不记数（null，非 0 填充值）
    assert "ath_degraded" in capsys.readouterr().err   # 记 warning

    healthy_payload = dict(degraded_payload, ath_degraded=False, ddath_pct=-5.25)
    monkeypatch.setattr(ds, "_fetch", _canned_fetch(healthy_payload))
    rec2 = ds.build_record()
    assert rec2["regime"]["ddath_pct"] == pytest.approx(-5.25)   # 健康路径照常记数


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
