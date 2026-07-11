"""SPEC-094.3 — Q042 Fill 确认闭环（幽灵仓位防护）AC-94.3-1..6.

覆盖 F1（每日确认提醒 + T+5 兜底释放 + phantom 标记）与 F2（手动 open 端点
回写 trigger state：幂等 / 冲突告警不覆盖）。

密闭房规（沿 tests/test_spec_094_2.py）：全部账本/state/gate log/runtime.json
重定向 tmp，gateway.push 换 recorder——绝不触碰生产文件或真实推送。

交易日事实锚（strategy/q078_ladder._HOLIDAYS，2026-07-03 为独立日观察假日）：
  2026-07-01 Wed · 07-02 Thu · 07-03 Fri(假) · 07-06 Mon · 07-07 Tue · 07-08 Wed
  entry 2026-07-02 → 至 07-08 经过 n=3 个交易日（T+3，提醒档）
  entry 2026-06-29 → 至 07-08 经过 n=6 个交易日（T+6 ≥ 5，释放档）
"""
from __future__ import annotations

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
TODAY = "2026-07-08"


# ── Fixtures / helpers（沿 094.2 惯例） ────────────────────────────────────────

def _fresh_ts(days_ago: int = 0) -> str:
    return (datetime.now(ET) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def _healthy_runtime(spx_pm_bp_pct: float = 18.61) -> dict:
    return {
        "timestamp": _fresh_ts(),
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

    import strategy.cash_budget_governance as cbg
    monkeypatch.setattr(cbg, "get_current_liquid_cash", lambda: {"total": 412_000.0})
    monkeypatch.setattr(cbg, "get_open_debit_total_usd", lambda: {"total": 51_000.0})

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
    def __init__(self, closes, dates):
        self._df = pd.DataFrame({"Close": closes}, index=pd.DatetimeIndex(dates))

    def Ticker(self, *_a, **_k):
        outer = self

        class _T:
            def history(self, *a, **k):
                return outer._df
        return _T()


def _patch_market(monkeypatch, *, spx_close, today_str, vix=20.0, nlv=500_000.0):
    monkeypatch.setattr(ex, "_fetch_spx_close", lambda: (spx_close, today_str))
    monkeypatch.setattr(ex, "_fetch_vix", lambda: vix)
    monkeypatch.setattr(ex, "_fetch_nlv", lambda: nlv)
    dates = pd.bdate_range(end=today_str, periods=12)
    monkeypatch.setattr(ex, "yf", _FakeYF([spx_close] * 12, dates))


def _pending_record(sleeve, signal_date, entry_date, expiry, *, fill_debit=None,
                    contracts=1, est_debit=5000.0, settled=False, phantom=None,
                    exit_pnl=None, dte=30):
    """A ledger open record; fill_debit=None ⇒ pending（未确认成交）。"""
    rec = {
        "trade_id": f"{sleeve}-{signal_date}", "event": "open", "sleeve_id": sleeve,
        "signal_date": signal_date, "entry_target_date": entry_date,
        "expiry": expiry, "dte": dte,
        "long_strike": 1000, "short_strike": 1050,
        "contracts": contracts, "est_debit": est_debit, "fill_debit": fill_debit,
        "settled": settled, "exit_pnl": exit_pnl,
    }
    if phantom is not None:
        rec["phantom"] = phantom
    return rec


# ── AC-94.3-1 — T+3 pending → 每日 FYI 提醒，state 不动 ─────────────────────────

def test_ac1_daily_reminder_fyi_state_untouched(q042_env, monkeypatch):
    # entry 2026-07-02 → n=3 交易日（第 4 天提醒档，< T+5）
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-07-01", "2026-07-02", "2026-08-01"),
    ])
    _write_json(q042_env["state_file"], _default_state(
        sleeve_a={"armed": False, "active_position_id": "A-2026-07-01",
                  "active_position_expiry": "2026-08-01"},
    ))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=1000.0, today_str=TODAY)  # ddath 0 → no fire

    ex.run_eod_evaluation(dry_run=False)

    reminders = [p for p in q042_env["pushes"]
                 if p["dedupe_key"] == f"q042_fill_reminder_A-2026-07-01_{TODAY}"]
    assert len(reminders) == 1
    assert reminders[0]["category"] == "FYI"           # AC-1: FYI 档
    assert "第 4 天未确认" in reminders[0]["body"]
    assert "T+5 自动释放" in reminders[0]["body"]
    # state 不动
    st = json.loads(q042_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == "A-2026-07-01"
    assert st["sleeve_a"]["active_position_expiry"] == "2026-08-01"
    # 账本无 phantom 标记
    ledger = [json.loads(l) for l in q042_env["paper_log"].read_text().splitlines() if l]
    assert not any(r.get("phantom") for r in ledger)


# ── AC-94.3-2 — T+6 pending → 释放 + phantom + ACTION；同日可正常 fire ──────────

def test_ac2_t5_release_phantom_action_and_same_day_fire(q042_env, monkeypatch):
    # entry 2026-06-29 → n=6 交易日 ≥ 5 → 兜底释放。
    # armed=True + slot 被幽灵占用 = 2026-06-10 counterfactual 场景
    # （re-arm 是 position-agnostic 的，armed 可在 slot 占用期间回真）。
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-06-26", "2026-06-29", "2026-07-29"),
    ])
    _write_json(q042_env["state_file"], _default_state(
        ath_running_max=1000.0,
        sleeve_a={"armed": True, "active_position_id": "A-2026-06-26",
                  "active_position_expiry": "2026-07-29"},
    ))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=950.0, today_str=TODAY)  # ddath -5% ≤ -4%

    fired = ex.run_eod_evaluation(dry_run=False)

    # ① 账本记录打 phantom:true（不删，保审计链）
    ledger = [json.loads(l) for l in q042_env["paper_log"].read_text().splitlines() if l]
    old = [r for r in ledger if r.get("trade_id") == "A-2026-06-26"]
    assert old and old[0]["phantom"] is True
    assert old[0]["settled"] is False                  # 未被误 settle
    # ② ACTION 告警
    releases = [p for p in q042_env["pushes"]
                if p["dedupe_key"] == f"q042_phantom_release_A-2026-06-26_{TODAY}"]
    assert len(releases) == 1
    assert releases[0]["category"] == "ACTION"
    assert "幽灵仓位已释放" in releases[0]["body"]
    assert "补录" in releases[0]["body"]
    # ③ 同日 ddATH ≤ -4% → sleeve 正常 fire（释放先于 update_sleeve_*）
    assert any(f.sleeve_id == "A" for f in fired)
    st = json.loads(q042_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == f"A-{TODAY}"   # 新仓占位（双字段已清后重写）
    assert st["sleeve_a"]["armed"] is False            # fire 消耗 armed；释放不回补 armed
    # ④ 释放档不再发当日提醒
    assert not any(p["dedupe_key"] == f"q042_fill_reminder_A-2026-06-26_{TODAY}"
                   for p in q042_env["pushes"])
    # ⑤ 新 fire 产生新 pending 记录（fill null）
    new = [r for r in ledger if r.get("signal_date") == TODAY]
    assert new and new[0]["fill_debit"] is None


def test_ac2_release_slot_mismatch_keeps_state(q042_env, monkeypatch):
    """释放时 state 槽位若指向不同 id → 只打 phantom + 告警，不清动槽位。"""
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-06-26", "2026-06-29", "2026-07-29"),
    ])
    _write_json(q042_env["state_file"], _default_state(
        sleeve_a={"armed": False, "active_position_id": "A-2026-07-06-001",
                  "active_position_expiry": "2026-08-06"},
    ))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=1000.0, today_str=TODAY)  # no fire

    ex.run_eod_evaluation(dry_run=False)

    ledger = [json.loads(l) for l in q042_env["paper_log"].read_text().splitlines() if l]
    assert ledger[0]["phantom"] is True
    st = json.loads(q042_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == "A-2026-07-06-001"  # 未清动
    releases = [p for p in q042_env["pushes"] if "幽灵仓位已释放" in p["body"]]
    assert releases and "未清动" in releases[0]["body"]


# ── AC-94.3-3 — fill_debit 已回填 → T+5 后不受任何影响 ──────────────────────────

def test_ac3_backfilled_record_unaffected_after_t5(q042_env, monkeypatch):
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-06-26", "2026-06-29", "2026-07-29",
                        fill_debit=7860.0),           # PM 已回填
    ])
    _write_json(q042_env["state_file"], _default_state(
        sleeve_a={"armed": False, "active_position_id": "A-2026-06-26",
                  "active_position_expiry": "2026-07-29"},
    ))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=1000.0, today_str=TODAY)

    before_ledger = q042_env["paper_log"].read_bytes()
    ex.run_eod_evaluation(dry_run=False)

    assert q042_env["paper_log"].read_bytes() == before_ledger   # 账本一字不动
    st = json.loads(q042_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == "A-2026-06-26"  # 槽位保留
    assert not any("fill_reminder" in (p["dedupe_key"] or "") for p in q042_env["pushes"])
    assert not any("phantom_release" in (p["dedupe_key"] or "") for p in q042_env["pushes"])


# ── AC-94.3-4 — phantom 记录不进 F6 committed / settle / lifetime stats ─────────

def test_ac4_phantom_excluded_from_committed(q042_env):
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-07-01", "2026-07-02", "2026-08-01",
                        contracts=2, est_debit=25000.0, phantom=True),
    ])
    assert pos.get_active_committed_debit_usd(today=TODAY) == 0.0


def test_ac4_phantom_skipped_by_settle(q042_env):
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-06-01", "2026-06-02", "2026-07-07",  # expiry 已过
                        phantom=True),
    ])
    before = q042_env["paper_log"].read_bytes()
    settled = pos.settle_expired_positions(950.0, today=TODAY, paper=True)
    assert settled == []                                # 不结算 phantom
    assert q042_env["paper_log"].read_bytes() == before  # 账本不动


def test_ac4_phantom_excluded_from_lifetime_stats(q042_env):
    _write_jsonl(q042_env["paper_log"], [
        # 防御性：即使 phantom 行被人为标了 settled+exit_pnl 也不进 stats
        _pending_record("A", "2026-06-01", "2026-06-02", "2026-07-02",
                        settled=True, exit_pnl=5000.0, phantom=True),
        _pending_record("A", "2026-05-01", "2026-05-02", "2026-06-01",
                        fill_debit=4000.0, settled=True, exit_pnl=1200.0),
    ])
    stats = pos.get_lifetime_stats(paper=True)
    assert stats["A"]["trades"] == 1                    # 只有真实那笔
    assert stats["A"]["total_pnl"] == 1200.0


def test_ac4_phantom_excluded_from_active_positions(q042_env):
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-06-01", "2026-06-02", "2026-08-01",
                        fill_debit=4000.0),
        _pending_record("A", "2026-06-20", "2026-06-21", "2026-08-10",
                        phantom=True),                  # 更新但 phantom → 跳过
    ])
    active = pos.get_active_positions(paper=True)
    assert active["A"] is not None
    assert active["A"].signal_date == "2026-06-01"      # 取真实记录，非 phantom
    # 只剩 phantom → None
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("B", "2026-06-20", "2026-06-21", "2026-09-20",
                        phantom=True, dte=90),
    ])
    assert pos.get_active_positions(paper=True)["B"] is None


def test_ac4_f6_writer_excludes_phantom_end_to_end(q042_env, monkeypatch):
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-07-01", "2026-07-02", "2026-08-01",
                        contracts=2, est_debit=25000.0, phantom=True),
    ])
    _write_json(q042_env["state_file"], _default_state(combined_bp_pct=3.33))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=1000.0, today_str=TODAY, nlv=500_000.0)

    ex.run_eod_evaluation(dry_run=False)
    st = json.loads(q042_env["state_file"].read_text())
    assert st["combined_bp_pct"] == 0.0                 # $50k phantom 不进 committed


# ── AC-94.3-5 — F2 手动 open 端点回写 state ─────────────────────────────────────

@pytest.fixture
def api_env(tmp_path, monkeypatch):
    """Hermetic surface for /api/q042/position/open：账本 + state + gateway。"""
    import web.server as srv

    paper_log = tmp_path / "q042_paper_trades.jsonl"
    state_file = tmp_path / "q042_state.json"
    monkeypatch.setattr(srv, "_q042_ledger_path", lambda: paper_log)
    monkeypatch.setattr(trig, "STATE_FILE", state_file)

    pushes: list[dict] = []
    import notify.gateway as gw

    def _record(category, about, title, body="", *, dedupe_key=None, **kw):
        pushes.append({"category": category, "about": about, "title": title,
                       "body": body, "dedupe_key": dedupe_key})
        return True

    monkeypatch.setattr(gw, "push", _record)
    return {"client": srv.app.test_client(), "paper_log": paper_log,
            "state_file": state_file, "pushes": pushes}


_OPEN_PAYLOAD = {
    "sleeve_id": "A", "signal_date": "2026-07-08",
    "long_strike": 6000, "short_strike": 6150, "contracts": 1,
    "expiry": "2026-08-21", "est_debit": 7860.0,
}


def test_ac5_manual_open_writes_state(api_env):
    _write_json(api_env["state_file"], _default_state())

    res = api_env["client"].post("/api/q042/position/open", json=_OPEN_PAYLOAD)
    body = res.get_json()
    assert res.status_code == 200 and body["status"] == "ok"
    assert body["trade_id"] == "A-2026-07-08-001"
    assert body["state_synced"] is True
    assert body["state_conflict"] is None

    st = json.loads(api_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == "A-2026-07-08-001"
    assert st["sleeve_a"]["active_position_expiry"] == "2026-08-21"
    assert api_env["pushes"] == []                      # 正常路径零告警


def test_ac5_conflict_alert_no_overwrite(api_env):
    _write_json(api_env["state_file"], _default_state(
        sleeve_a={"armed": False, "active_position_id": "A-2026-07-01-001",
                  "active_position_expiry": "2026-07-31"},
    ))

    res = api_env["client"].post("/api/q042/position/open", json=_OPEN_PAYLOAD)
    body = res.get_json()
    assert res.status_code == 200 and body["status"] == "ok"   # 记账本身成功
    assert body["state_synced"] is False
    assert body["state_conflict"] == {"existing_id": "A-2026-07-01-001",
                                      "new_trade_id": "A-2026-07-08-001"}
    # state 不覆盖
    st = json.loads(api_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == "A-2026-07-01-001"
    assert st["sleeve_a"]["active_position_expiry"] == "2026-07-31"
    # 冲突 ACTION 告警
    conflicts = [p for p in api_env["pushes"]
                 if p["dedupe_key"] == "q042_open_state_conflict_A-2026-07-08-001"]
    assert len(conflicts) == 1 and conflicts[0]["category"] == "ACTION"
    assert "双仓" in conflicts[0]["title"] or "双仓" in conflicts[0]["body"]
    # 账本记录已写入（告警不阻塞记账）
    ledger = [json.loads(l) for l in api_env["paper_log"].read_text().splitlines() if l]
    assert any(r.get("trade_id") == "A-2026-07-08-001" for r in ledger)


def test_ac5_idempotent_same_id_no_op(api_env):
    # 预置槽位 = 即将生成的 trade_id（空账本 → 后缀 -001）→ 幂等不动、零告警
    _write_json(api_env["state_file"], _default_state(
        sleeve_a={"armed": False, "active_position_id": "A-2026-07-08-001",
                  "active_position_expiry": "2026-08-21"},
    ))
    before_state = api_env["state_file"].read_bytes()

    res = api_env["client"].post("/api/q042/position/open", json=_OPEN_PAYLOAD)
    body = res.get_json()
    assert body["trade_id"] == "A-2026-07-08-001"
    assert body["state_synced"] is True
    assert body["state_conflict"] is None
    assert api_env["state_file"].read_bytes() == before_state   # state 一字不动
    assert api_env["pushes"] == []


# ── AC-94.3-6 — dry-run：全部 F1 动作零落盘零推送（hash 比对） ──────────────────

def test_ac6_dry_run_zero_disk_zero_push(q042_env, monkeypatch):
    # fixture 同时含释放档（T+6）与提醒档（T+3），两条 F1 路径都被推演到
    _write_jsonl(q042_env["paper_log"], [
        _pending_record("A", "2026-06-26", "2026-06-29", "2026-07-29"),  # n=6 → 释放档
        _pending_record("A", "2026-07-01", "2026-07-02", "2026-08-01"),  # n=3 → 提醒档
    ])
    _write_jsonl(q042_env["live_log"], [])
    _write_json(q042_env["state_file"], _default_state(
        sleeve_a={"armed": True, "active_position_id": "A-2026-06-26",
                  "active_position_expiry": "2026-07-29"},
    ))
    q042_env["gate_log"].write_text("")
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=950.0, today_str=TODAY)  # 释放后 would-fire 亦被推演

    before = {k: q042_env[k].read_bytes() for k in
              ("paper_log", "live_log", "state_file", "gate_log")}

    ex.run_eod_evaluation(dry_run=True, verbose=False)

    after = {k: q042_env[k].read_bytes() for k in
             ("paper_log", "live_log", "state_file", "gate_log")}
    assert before == after, "dry-run must not mutate any Q042 disk surface"
    assert q042_env["pushes"] == []                     # 零推送（提醒/释放/fire 全静默）


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
