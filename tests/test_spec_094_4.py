"""SPEC-094.4 — Q042 触发告警弹药路由（BPS fallback 决策支持）AC-94.4-1..5.

覆盖 F1（三分支建议块 + 因果贪婪分段分类器 + gate log `ammo_advisory` 管道）
与 F2（分类/报价失败 → `弹药路由 n/a`，告警照发）。AC-3 为 35 个历史触发日
重放（Rev 2026-07-12 方向敏感门槛：突发型 4/4 硬 + 总对齐 ≥31/35 + 差异全部
错向 sudden/空仓）。

密闭房规（沿 tests/test_spec_094_2.py / _094_3.py）：全部账本/state/gate log/
runtime.json 重定向 tmp，gateway.push 换 recorder，市场数据换 stub——绝不触碰
生产文件或真实推送。例外：AC-3 重放按 spec 用只读真值文件
（data/q042_backtest_trades.csv + data/market_cache/yahoo__GSPC__max__1d.pkl +
research/q095/q095_p6_bps_sub.csv）。

合成序列锚：
  _episode_closes — 60TD 陡趋势热身（明显出带）+ 40TD 1000/1002 窄幅收尾于
    信号日 → 分段末端 = 信号日 → episode 型
  _sudden_closes — 60TD 窄幅段后接 30TD 连续 -1%/日下跌收尾于信号日 →
    最后 episode 段末端距信号 ~25TD（≈35 日历日 >7）→ 突发型
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import production.q042_executor as ex
import production.q042_positions as pos
import signals.q042_trigger as trig
import strategy.q042_gate as gate

ET = ZoneInfo("America/New_York")
TODAY = "2026-07-08"
REPO = Path(__file__).resolve().parents[1]


# ── Fixtures / helpers（沿 094.2/094.3 惯例） ──────────────────────────────────

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


# ── Synthetic close series（deterministic，无网络） ────────────────────────────

def _mk_closes(vals, end=TODAY) -> pd.Series:
    dates = pd.bdate_range(end=end, periods=len(vals))
    return pd.Series([float(v) for v in vals], index=dates)


def _episode_closes(end=TODAY) -> pd.Series:
    vals = [500.0 + 8.0 * i for i in range(60)] + [1000.0, 1002.0] * 20
    return _mk_closes(vals, end)


def _sudden_closes(end=TODAY) -> pd.Series:
    vals = [1000.0, 1002.0] * 30 + [1000.0 * (0.99 ** i) for i in range(1, 31)]
    return _mk_closes(vals, end)


def _prime_fire_a(q042_env, monkeypatch, *, closes, liquid=None):
    """标准 fire_A 场景：ath 1000 / spx 950（ddath −5%）+ healthy gate。"""
    _write_json(q042_env["state_file"], _default_state(ath_running_max=1000.0))
    _write_json(q042_env["runtime"], _healthy_runtime())
    _patch_market(monkeypatch, spx_close=950.0, today_str=TODAY)
    monkeypatch.setattr(ex, "_fetch_spx_close_series", lambda today_str: closes)
    if liquid is not None:
        import strategy.cash_budget_governance as cbg
        monkeypatch.setattr(cbg, "get_current_liquid_cash", lambda: {"total": liquid})


def _trigger_bodies(q042_env) -> list[str]:
    return [p["body"] for p in q042_env["pushes"]
            if (p["dedupe_key"] or "").startswith("q042_trigger_")]


def _ammo_rows(q042_env) -> list[dict]:
    if not q042_env["gate_log"].exists():
        return []
    rows = [json.loads(l) for l in q042_env["gate_log"].read_text().splitlines() if l]
    return [r for r in rows if "ammo_advisory" in r]


# ── AC-94.4-1 — 三分支建议块正文 ───────────────────────────────────────────────

def test_ac1_branch1_sufficient_cash_call_spread(q042_env, monkeypatch):
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes())  # liquid 412k 充足

    fired = ex.run_eod_evaluation(dry_run=False)

    assert any(f.sleeve_id == "A" for f in fired)
    bodies = _trigger_bodies(q042_env)
    assert len(bodies) == 1
    body = bodies[0]
    assert "→ 弹药充足：Call Spread（默认结构）" in body
    # AC14.1 既有行保持 + 建议块在 F5b 现金行之后（AC14.2 amendment 顺序）
    assert "Strikes: long K=" in body
    assert "Liquid cash" in body
    assert body.index("Liquid cash") < body.index("→ 弹药充足")


def test_ac1_branch2_bps_fallback_with_yield_gap_reminder(q042_env, monkeypatch):
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)

    fired = ex.run_eod_evaluation(dry_run=False)

    assert any(f.sleeve_id == "A" for f in fired)          # 提示不拦：fire 语义不变
    body = _trigger_bodies(q042_env)[0]
    assert "→ 现金不足·震荡铺垫型：可用 BPS fallback" in body
    m = re.search(r"SELL PUT (\d+)\(Δ0\.30\) / BUY PUT (\d+)\(Δ0\.15\)，同 expiry", body)
    assert m, f"BPS strikes 行缺失: {body!r}"
    k_short, k_long = int(m.group(1)), int(m.group(2))
    assert k_short > k_long                                 # Δ0.30 严格高于 Δ0.15
    assert k_short < 950 and k_long < 950                   # 两腿均为 OTM put
    assert k_short % 5 == 0 and k_long % 5 == 0             # $5 增量
    assert "预算按 BP（max loss ≤ 12.5% NLV ≈ $62,500）" in body   # 500k × 12.5%
    # AC-1 硬要求（PM 2026-07-12）：收益差距提醒句
    assert "BPS 收益显著低于 call spread（26 年同预算差 3.7-7.4×，Q095 P6）" in body
    assert "次优替代" in body


def test_ac1_branch3_sudden_stand_aside(q042_env, monkeypatch):
    _prime_fire_a(q042_env, monkeypatch, closes=_sudden_closes(), liquid=10_000.0)

    fired = ex.run_eod_evaluation(dry_run=False)

    assert any(f.sleeve_id == "A" for f in fired)
    body = _trigger_bodies(q042_env)[0]
    assert "→ 现金不足·突发崩盘型（无震荡铺垫）：建议空仓" in body
    assert "4 例 3 亏（Q095 P6）" in body
    assert "BPS fallback" not in body                       # 不给突发型报 strikes


# ── AC-94.4-2 — gate log 携带 ammo_advisory ────────────────────────────────────

def test_ac2_gate_log_ammo_advisory_branch2(q042_env, monkeypatch):
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)

    fired = ex.run_eod_evaluation(dry_run=False)

    rows = _ammo_rows(q042_env)
    assert len(rows) == 1
    assert rows[0]["date"] == TODAY
    adv = rows[0]["ammo_advisory"]
    assert adv["sleeve"] == "A"
    assert adv["branch"] == "bps_fallback"
    assert adv["episode_type"] == "episode"
    assert adv["liquid"] == 10_000.0
    spec = fired[0]
    assert adv["need"] == pytest.approx(
        spec.est_debit_per_contract * spec.contracts, abs=0.01)
    assert adv["need"] > adv["liquid"]
    ks = adv["bps_strikes"]
    assert ks["short_put"] > ks["long_put"]
    # gate log 正文与告警正文的 strikes 单源一致
    body = _trigger_bodies(q042_env)[0]
    assert f"SELL PUT {ks['short_put']}(Δ0.30)" in body
    assert f"BUY PUT {ks['long_put']}(Δ0.15)" in body


def test_ac2_gate_log_ammo_advisory_branch1_and_branch3_fields(q042_env, monkeypatch):
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes())  # 充足

    ex.run_eod_evaluation(dry_run=False)
    adv = _ammo_rows(q042_env)[0]["ammo_advisory"]
    assert adv["branch"] == "call_spread"
    assert adv["episode_type"] == "episode"
    assert "bps_strikes" not in adv                         # 可选字段仅分支 2
    assert adv["need"] <= adv["liquid"] == 412_000.0

    # 突发型（分支 3）→ stand_aside，episode_type=sudden（paper 证据管道字段）
    q042_env["gate_log"].write_text("")
    q042_env["pushes"].clear()
    _prime_fire_a(q042_env, monkeypatch, closes=_sudden_closes(), liquid=10_000.0)
    ex.run_eod_evaluation(dry_run=False)
    adv3 = _ammo_rows(q042_env)[0]["ammo_advisory"]
    assert adv3["branch"] == "stand_aside"
    assert adv3["episode_type"] == "sudden"
    assert "bps_strikes" not in adv3


def test_ac2_ammo_row_not_picked_up_as_gate_state(q042_env, monkeypatch):
    """ammo_advisory 是 payload 行，不是门状态——Lane D reader 必须跳过。"""
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)
    ex.run_eod_evaluation(dry_run=False)

    assert _ammo_rows(q042_env)                             # ammo 行存在且在 gate 行之后
    latest = gate.read_latest_gate_row()
    assert latest is not None
    assert "ammo_advisory" not in latest
    assert "main_bp_pct" in latest                          # 仍取到当日 gate 状态行


# ── AC-94.4-3 — 历史重放（Rev 2026-07-12 方向敏感门槛） ────────────────────────

def test_ac3_historical_replay_directional_alignment():
    """35 个 sleeve A 历史触发日重放 live 分类器 vs P6 研究分层（FLAT 35 行）。

    ①突发型 4/4 全对（硬，安全关键）②总对齐 ≥31/35 ③全部差异错向
    sudden/空仓（保守侧）。真值文件只读。
    """
    closes = ex._normalize_close_series(pd.read_pickle(ex._SPX_DAILY_CACHE))
    trades = pd.read_csv(REPO / "data" / "q042_backtest_trades.csv")
    sigs = trades[trades.sleeve_id == "A"].signal_date.tolist()
    ref = pd.read_csv(REPO / "research" / "q095" / "q095_p6_bps_sub.csv")
    ref = ref[ref.pricing == "FLAT"].set_index("signal")["stratum"]
    # SPEC-094.5 起 CSV 由 scripts/q042_regen_backtest.py 再生并随数据窗口后延；
    # P6 真值冻结在研究时点的 35 笔——对齐检查限定在这 35 笔（新信号无 P6 真值）。
    assert len(ref) == 35
    assert set(ref.index) <= set(sigs), "冻结真值信号必须仍在再生流内"
    sigs = sorted(ref.index)

    live = {s: ex._classify_trigger_type(closes, s) for s in sigs}
    diffs = {s: {"p6": ref[s], "live": live[s]} for s in sigs if live[s] != ref[s]}
    n_match = 35 - len(diffs)

    sudden_ref = [s for s in sigs if ref[s] == "sudden"]
    assert len(sudden_ref) == 4
    # ① 硬门槛：突发型（BPS 亏 4× 的危害向量）4/4 全对
    assert all(live[s] == "sudden" for s in sudden_ref), \
        f"突发型硬门槛失败（危险侧误路由 BPS）: {diffs}"
    # ② 总对齐 ≥ 31/35
    assert n_match >= 31, f"总对齐 {n_match}/35 < 31: {diffs}"
    # ③ 全部差异必须错向 sudden/空仓（保守侧：错失 fallback，不误开 BPS）
    assert all(d["live"] == "sudden" for d in diffs.values()), \
        f"存在错向危险侧的差异: {diffs}"


def test_ac3_tail_window_exactly_15td_run_admitted():
    """尾窗修正：恰好 15TD 收尾于信号日的 in-band 段必须被接纳（原研究扫描界
    `s < n - MIN_LEN` 在截断序列上会漏掉；Quant 2026-07-12 裁决采用修正版）。"""
    # 60TD 陡趋势（出带）+ 跳空 + 15TD 窄幅收尾——趋势尾无法并入窄幅段
    vals = [500.0 + 8.0 * i for i in range(60)] + [1030.0, 1032.0] * 7 + [1030.0]
    closes = _mk_closes(vals, end=TODAY)
    eps = ex._find_chop_episodes(closes.values)
    assert (60, 74) in eps                                  # s = n−15 的段被扫描到
    assert ex._classify_trigger_type(closes, TODAY) == "episode"


def test_ac3_trailing_only_no_lookahead():
    """禁止前视：信号日之后的数据不得影响分类（截断语义）。"""
    dates = pd.bdate_range(end="2026-10-01", periods=130)
    vals = ([1000.0, 1002.0] * 30 + [1000.0 * (0.99 ** i) for i in range(1, 31)]
            + [800.0, 802.0] * 20)                          # 信号后走出新窄幅段
    closes = pd.Series(vals, index=dates)
    sig = dates[89].strftime("%Y-%m-%d")                    # 下跌段末=信号日
    assert ex._classify_trigger_type(closes, sig) == "sudden"
    # 同一序列在未来日期分类为 episode —— 证明未来段存在但未泄漏进 sig 的分类
    assert ex._classify_trigger_type(closes, dates[-1].strftime("%Y-%m-%d")) == "episode"


def test_ac3_stale_series_raises_for_failsoft():
    """截至信号日的序列末端 >7 日历日 → raise（caller 降级 n/a，AC-4 通道）。"""
    closes = _episode_closes(end="2026-06-19")              # 距 TODAY 19 天
    with pytest.raises(ValueError):
        ex._classify_trigger_type(closes, TODAY)


# ── AC-94.4-4 — 分类/报价失败 → 弹药路由 n/a，告警照发（AC16） ─────────────────

def test_ac4_classification_failure_degrades_to_na(q042_env, monkeypatch):
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes())

    def _boom(today_str):
        raise RuntimeError("cache gone")

    monkeypatch.setattr(ex, "_fetch_spx_close_series", _boom)

    fired = ex.run_eod_evaluation(dry_run=False)

    assert any(f.sleeve_id == "A" for f in fired)           # 告警照发，fire 不受阻
    body = _trigger_bodies(q042_env)[0]
    assert "弹药路由 n/a" in body
    assert _ammo_rows(q042_env) == []                       # 失败不写 ammo 行
    # fire 语义完整：pending 记录 + state 落仓
    st = json.loads(q042_env["state_file"].read_text())
    assert st["sleeve_a"]["active_position_id"] == f"A-{TODAY}"
    ledger = [json.loads(l) for l in q042_env["paper_log"].read_text().splitlines() if l]
    assert any(r.get("signal_date") == TODAY for r in ledger)


def test_ac4_pricing_failure_degrades_to_na(q042_env, monkeypatch):
    # 分支 2 路径中报价失败（find_strike_for_delta 炸）→ 整块降级 n/a
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)
    import backtest.pricer as pricer

    def _boom(*a, **k):
        raise RuntimeError("pricer down")

    monkeypatch.setattr(pricer, "find_strike_for_delta", _boom)

    fired = ex.run_eod_evaluation(dry_run=False)

    assert any(f.sleeve_id == "A" for f in fired)
    body = _trigger_bodies(q042_env)[0]
    assert "弹药路由 n/a" in body
    assert "BPS fallback" not in body                       # 不残留半截建议
    assert _ammo_rows(q042_env) == []


# ── AC-94.4-5 — dry-run 零推送零落盘（含 gate log 无 ammo_advisory 行） ────────

def test_ac5_dry_run_zero_disk_zero_push(q042_env, monkeypatch):
    # 分支 2 全要素齐备（episode + 现金不足）→ dry-run 下建议块随告警一起被抑制
    q042_env["paper_log"].write_text("")
    q042_env["live_log"].write_text("")
    q042_env["gate_log"].write_text("")
    _prime_fire_a(q042_env, monkeypatch, closes=_episode_closes(), liquid=10_000.0)

    before = {k: q042_env[k].read_bytes() for k in
              ("paper_log", "live_log", "state_file", "gate_log")}

    ex.run_eod_evaluation(dry_run=True, verbose=False)

    after = {k: q042_env[k].read_bytes() for k in
             ("paper_log", "live_log", "state_file", "gate_log")}
    assert before == after, "dry-run must not mutate any Q042 disk surface"
    assert q042_env["pushes"] == []                         # 零推送
    assert "ammo_advisory" not in q042_env["gate_log"].read_text()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
