"""SPEC-141 — 统一状态面（S1）+ State Map 页（S2a）AC-141-1..8、10.

覆盖：
  AC-1  /api/state-surface 全字段 + 与源交叉一致（episode_day 对 094.4 分类器、
        ddath 对 q042 snapshot、caps 对 governance runtime、liquid 对 cash_budget）
  AC-2  日志幂等一天一行 + 首跑回填 90 TD（backfill:true 简版）
  AC-3  子源注入失败 → 对应字段 n/a、API 恒 200、模板有 n/a 呈现路径
  AC-4  shadow invariant：selector / production/* / sleeve_governance 零 diff
        且无 state_surface import
  AC-5  徽章词汇 ∈ {ON, STANDBY}；Q042 armed 为行内字段
  AC-6  量表绝对刻度：width_pct = value/scale_max（同值同长）；cap 刻度线位置
  AC-7  portfolio home hero 条纯新增（Open Position / Portfolio Snapshot 逐字节不动）
  AC-8  触发预演三例（episode / sudden / 现金不足）复用 094.4 helper 非重写
（AC-9 browse QA 归 Quant；AC-10 = 094.x 回归，跑 pytest 全套命令验证。）

密闭房规：全部子源 monkeypatch/fake，日志写 tmp——绝不触碰生产文件或网络。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import production.q042_executor as ex
import strategy.state_surface as ss

TODAY = "2026-07-08"
TPL = REPO / "web" / "templates"


# ── Fixtures：合成序列（锚定 094.4 测试惯例）与健康子源 fake ───────────────────

def _mk_closes(vals, end=TODAY) -> pd.Series:
    dates = pd.bdate_range(end=end, periods=len(vals))
    return pd.Series([float(v) for v in vals], index=dates)


def _episode_closes(end=TODAY) -> pd.Series:
    """60TD 陡趋势热身 + 40TD 1000/1002 窄幅收尾于信号日 → episode 型。"""
    return _mk_closes([500.0 + 8.0 * i for i in range(60)] + [1000.0, 1002.0] * 20, end)


def _sudden_closes(end=TODAY) -> pd.Series:
    """窄幅段后 30TD 连续 −1%/日下跌收尾 → 突发型。"""
    return _mk_closes([1000.0, 1002.0] * 30
                      + [1000.0 * (0.99 ** i) for i in range(1, 31)], end)


def _mixed_closes(end=TODAY) -> pd.Series:
    """±6% 交替（出 5% band）且 MA50 gap ≈ 0 → 非 RANGE + NEUTRAL → MIXED。"""
    vals = [1000.0 if i % 2 == 0 else 940.0 if (i // 2) % 2 == 0 else 1060.0
            for i in range(90)]
    return _mk_closes(vals, end)


def _vix_snap(vix=18.4, peak10d=21.0, vix3m=20.1, backwardation=False):
    return SimpleNamespace(
        date=TODAY, vix=vix, regime="NORMAL", trend="FLAT", vix_5d_avg=vix,
        vix_5d_ago=vix, transition_warning=False, vix3m=vix3m,
        backwardation=backwardation, vix_peak_10d=peak10d)


def _trend_snap(signal="BULLISH", spx=1002.0, ma50=990.0):
    return SimpleNamespace(
        date=TODAY, spx=spx, ma20=spx, ma50=ma50,
        ma_gap_pct=(spx - ma50) / ma50, signal=SimpleNamespace(value=signal),
        above_200=True)


def _q042_snap(ddath=-0.005, armed_a=True, ath=1007.0, degraded=False):
    return SimpleNamespace(
        date=TODAY, spx_close=round(ath * (1 + ddath), 2), ath_running_max=ath,
        ddath=ddath, ath_degraded=degraded,
        sleeve_a=SimpleNamespace(armed=armed_a, active_position_id=None),
        sleeve_b=SimpleNamespace(armed=True, in_watching=False,
                                 active_position_id=None),
        combined_bp_pct=0.0)


def _gov(spx_pm=15.8, short_vol=15.8, combined=15.8, es=0.0,
         second_leg=False, cap=80.0):
    return {
        "timestamp": "2026-07-08T16:50:00-04:00",
        "basis_dollars": 629_000.0,
        "second_leg_active": second_leg,
        "stress_episode_active": False,
        "active_spx_pm_cap_regime": "normal",
        "pools": {"nlv_basis": 629_000.0, "spx_pm_bp_pct": spx_pm,
                  "short_vol_bp_pct": short_vol, "combined_bp_pct": combined,
                  "es_span_bp_pct": es},
        "caps": {"active_spx_pm_cap_pct": cap, "R2_es_span_cap_pct": 80.0,
                 "R3_combined_cap_pct": 60.0, "R4_short_vol_cap_pct": 50.0},
    }


def _rec(key="bull_put_spread", name="Bull Put Spread", action="OPEN"):
    return SimpleNamespace(strategy=SimpleNamespace(value=name),
                           strategy_key=key, position_action=action,
                           size_rule="Full size")


@pytest.fixture
def env(monkeypatch):
    """健康子源全 fake（零网络零生产盘面）；测试可改 env 字典再算 surface。"""
    e = {
        "closes": _episode_closes(),
        "vix": _vix_snap(),
        "trend": _trend_snap(),
        "q042": _q042_snap(),
        "gov": _gov(),
        "liquid": {"total": 152_000.0, "source": "live", "error": None},
        "debit": {"total": 22_000.0},
        "rec": _rec(),
        "positions": {"positions": [
            {"trade_id": "t1", "strategy_key": "bull_put_spread", "contracts": 2,
             "expiry": "2026-08-21", "status": "open", "underlying": "SPX"}]},
    }
    vix_df = pd.DataFrame({"vix": [18.0] * 30},
                          index=pd.bdate_range(end=TODAY, periods=30))

    def maybe(fn):
        def inner(*a, **k):
            v = fn()
            if isinstance(v, Exception):
                raise v
            return v
        return inner

    monkeypatch.setattr("signals.vix_regime.fetch_vix_history",
                        lambda *a, **k: vix_df)
    monkeypatch.setattr("signals.vix_regime.get_current_snapshot",
                        maybe(lambda: e["vix"]))
    monkeypatch.setattr("signals.trend.fetch_spx_history",
                        lambda *a, **k: pd.DataFrame(
                            {"close": e["closes"].values}, index=e["closes"].index))
    monkeypatch.setattr("signals.trend.get_current_trend",
                        maybe(lambda: e["trend"]))
    monkeypatch.setattr(ex, "_fetch_spx_close_series",
                        maybe(lambda: e["closes"]))
    monkeypatch.setattr("signals.q042_trigger.get_current_q042_snapshot",
                        maybe(lambda: e["q042"]))
    monkeypatch.setattr(ss, "_read_governance_runtime", maybe(lambda: e["gov"]))
    monkeypatch.setattr("strategy.cash_budget_governance.get_current_liquid_cash",
                        maybe(lambda: e["liquid"]))
    monkeypatch.setattr("strategy.cash_budget_governance.get_open_debit_total_usd",
                        maybe(lambda: e["debit"]))
    monkeypatch.setattr("strategy.selector.get_recommendation",
                        lambda *a, **k: (_ for _ in ()).throw(e["rec"])
                        if isinstance(e["rec"], Exception) else e["rec"])
    monkeypatch.setattr("strategy.state.read_all_positions",
                        maybe(lambda: e["positions"]))
    return e


# ── AC-141-1 — 全字段 + 源交叉一致 ─────────────────────────────────────────────

F1_FIELDS = ("vol_axis", "structure_axis", "trend_signal", "events",
             "veto", "ammo", "today")


def test_ac1_all_fields_present_and_ok(env):
    s = ss.compute_state_surface(today=TODAY)
    for f in F1_FIELDS:
        assert f in s, f
    for f in ("vol_axis", "structure_axis", "trend_signal", "veto", "ammo", "today"):
        assert s[f].get("status") == "ok", (f, s[f])
    for ev in ("dip", "aftermath", "backwardation", "second_leg"):
        assert s["events"][ev].get("status") == "ok", ev


def test_ac1_episode_day_matches_094_4_classifier(env):
    s = ss.compute_state_surface(today=TODAY)
    ax = s["structure_axis"]
    assert ax["state"] == "RANGE"
    # 交叉真值：直接跑 094.4 分段器（同一 helper），episode_day 必须逐一致
    trail = env["closes"].loc[ex._EPISODE_SCAN_START:pd.Timestamp(TODAY)]
    eps = ex._find_chop_episodes(trail.values)
    seg_start, seg_end = eps[-1]
    assert ax["episode_day"] == len(trail) - seg_start
    assert ax["band_lo"] == round(float(min(trail.values[seg_start:seg_end + 1])), 2)
    assert ax["band_hi"] == round(float(max(trail.values[seg_start:seg_end + 1])), 2)
    # membership 语义 = _classify_trigger_type 的 episode 判定（尾窗同 094.4）
    assert ex._classify_trigger_type(env["closes"], TODAY) == "episode"
    assert s["events"]["dip"]["type_if_now"] == "episode"


def test_ac1_structure_sudden_and_mixed_paths(env):
    env["closes"] = _sudden_closes()
    env["trend"] = _trend_snap(signal="BEARISH", spx=740.0, ma50=900.0)
    s = ss.compute_state_surface(today=TODAY)
    assert s["structure_axis"]["state"] == "TREND_DOWN"
    assert s["events"]["dip"]["type_if_now"] == "sudden"

    env["closes"] = _mixed_closes()
    env["trend"] = _trend_snap(signal="NEUTRAL", spx=1000.0, ma50=1000.0)
    s = ss.compute_state_surface(today=TODAY)
    assert s["structure_axis"]["state"] == "MIXED"     # NEUTRAL 非 episode → MIXED


def test_ac1_cross_consistency_q042_gov_cash(env):
    s = ss.compute_state_surface(today=TODAY)
    # ddath 对 q042 snapshot
    assert s["events"]["dip"]["ddath_pct"] == round(env["q042"].ddath * 100, 2)
    assert s["events"]["dip"]["sleeve_a"]["armed"] is env["q042"].sleeve_a.armed
    # caps 对 governance runtime
    assert s["veto"]["detail"]["caps"]["active_spx_pm_cap_pct"] == \
        env["gov"]["caps"]["active_spx_pm_cap_pct"]
    assert s["veto"]["detail"]["pools"]["spx_pm_bp_pct"] == \
        env["gov"]["pools"]["spx_pm_bp_pct"]
    assert s["pools"]["bp"]["spx_pm"]["value"] == env["gov"]["pools"]["spx_pm_bp_pct"]
    # liquid 对 cash_budget
    assert s["ammo"]["liquid"] == env["liquid"]["total"]
    assert s["ammo"]["in_flight_debit"] == env["debit"]["total"]
    # reserve = 12.5% × NLV 现算（q042_sizing 单源）
    from strategy.q042_sizing import q042_sleeve_cap_pct
    assert s["ammo"]["reserve_need"] == pytest.approx(
        env["gov"]["basis_dollars"] * q042_sleeve_cap_pct("A") / 100.0)
    # vol 轴阈值/距离
    assert s["vol_axis"]["state"] == "NORMAL"
    assert s["vol_axis"]["dist_next"] == pytest.approx(22.0 - 18.4)
    # today 对 selector
    assert s["today"]["strategy_key"] == env["rec"].strategy_key
    assert s["today"]["resource"] == "bp"


def test_ac1_api_returns_full_payload(env):
    from web.server import app
    canned = ss.compute_state_surface(today=TODAY)
    with patch("strategy.state_surface.compute_state_surface",
               return_value=canned), \
         patch("strategy.state_surface.read_history", return_value=[]):
        res = app.test_client().get("/api/state-surface")
    assert res.status_code == 200
    data = res.get_json()
    for f in F1_FIELDS:
        assert f in data, f
    assert "history" in data
    assert data["semantics"].startswith("shadow")


def test_bcd_routes_resource_cash(env):
    env["rec"] = _rec(key="bull_call_diagonal", name="Bull Call Diagonal")
    s = ss.compute_state_surface(today=TODAY)
    assert s["today"]["resource"] == "cash"


# ── AC-141-2 — 日志幂等 + 首跑回填 90 TD ──────────────────────────────────────

def _long_closes(n=200) -> pd.Series:
    vals = ([500.0 + 4.0 * i for i in range(n - 60)]
            + [1000.0, 1002.0] * 30)[:n]
    return _mk_closes(vals, end=TODAY)


def test_ac2_first_run_backfills_and_is_idempotent(tmp_path, env):
    log = tmp_path / "state_surface.jsonl"
    closes = _long_closes()
    vix_by_date = {d.strftime("%Y-%m-%d"): 18.0 for d in closes.index}
    surface = ss.compute_state_surface(today=TODAY)

    r1 = ss.append_daily_log(date=TODAY, log_path=log, surface=surface,
                             closes=closes, vix_by_date=vix_by_date)
    assert r1["status"] == "written"
    assert r1["backfilled"] == ss.BACKFILL_TRADING_DAYS == 90

    rows = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(rows) == 91
    backfill, full = rows[:-1], rows[-1]
    assert all(r["backfill"] is True for r in backfill)
    assert all(set(r) == {"date", "backfill", "vol_state", "structure_state"}
               for r in backfill)                       # 简版：仅两状态
    assert all(r["vol_state"] == "NORMAL" for r in backfill)
    assert full["backfill"] is False
    assert full["date"] == TODAY
    assert full["surface"]["vol_axis"]["state"] == "NORMAL"
    # 回填日期 = 当日之前的 90 个交易日（升序、不含当日）
    assert backfill[-1]["date"] < TODAY
    assert [r["date"] for r in backfill] == sorted(r["date"] for r in backfill)

    before = log.read_bytes()
    r2 = ss.append_daily_log(date=TODAY, log_path=log, surface=surface,
                             closes=closes, vix_by_date=vix_by_date)
    assert r2["status"] == "skipped"
    assert log.read_bytes() == before                   # 幂等：一天一行

    hist = ss.read_history(limit=90, log_path=log)
    assert len(hist) == 90
    assert hist[-1]["date"] == TODAY and hist[-1]["backfill"] is False
    assert hist[0]["backfill"] is True


def test_ac2_second_day_appends_single_row_no_rebackfill(tmp_path, env):
    log = tmp_path / "state_surface.jsonl"
    closes = _long_closes()
    vix_by_date = {d.strftime("%Y-%m-%d"): 18.0 for d in closes.index}
    surface = ss.compute_state_surface(today=TODAY)
    ss.append_daily_log(date=TODAY, log_path=log, surface=surface,
                        closes=closes, vix_by_date=vix_by_date)
    n_before = len(log.read_text().splitlines())
    r = ss.append_daily_log(date="2026-07-09", log_path=log, surface=surface)
    assert r["status"] == "written" and r["backfilled"] == 0
    assert len(log.read_text().splitlines()) == n_before + 1


# ── AC-141-3 — 注入失败 → n/a、API 200、页面 n/a 呈现 ─────────────────────────

def test_ac3_each_subsource_failure_degrades_only_its_field(env):
    env["vix"] = RuntimeError("vix feed down")
    env["liquid"] = RuntimeError("broker down")
    s = ss.compute_state_surface(today=TODAY)
    assert s["vol_axis"]["status"] == "n/a"
    assert s["events"]["aftermath"]["status"] == "n/a"      # 依赖 vix
    assert s["events"]["backwardation"]["status"] == "n/a"  # 依赖 vix
    assert s["ammo"]["status"] == "n/a"                     # 依赖 cash
    assert s["veto"]["extreme_ok"] == "n/a"
    assert s["veto"]["cash_floor_ok"] == "n/a"
    # 其余字段不被拖垮
    assert s["structure_axis"]["status"] == "ok"
    assert s["events"]["dip"]["status"] == "ok"
    assert s["events"]["second_leg"]["status"] == "ok"
    assert s["veto"]["second_leg_ok"] is True
    assert s["today"]["status"] == "ok"


def test_ac3_ath_degraded_dip_is_na_not_zero(env):
    env["q042"] = _q042_snap(degraded=True)
    s = ss.compute_state_surface(today=TODAY)
    dip = s["events"]["dip"]
    assert dip["status"] == "n/a"
    assert "ath_degraded" in dip["error"]
    assert "ddath_pct" not in dip                # 绝不把 0 填充当真值
    assert dip["sleeve_a"]["armed"] is True      # armed 行内字段仍可用


def test_ac3_api_stays_200_even_if_module_raises(env):
    from web.server import app
    with patch("strategy.state_surface.compute_state_surface",
               side_effect=RuntimeError("total meltdown")):
        res = app.test_client().get("/api/state-surface")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "n/a"
    assert "history" in data


def test_ac3_template_has_na_render_paths():
    src = (TPL / "state_map.html").read_text(encoding="utf-8")
    assert "class=\"na\"" in src                 # n/a 样式（--text-2，可读）
    assert src.count("n/a") > 10                 # 各 section 均有 n/a 兜底
    assert "状态面数据不可用" in src               # fetch 失败中文 status message


# ── AC-141-4 — shadow invariant ───────────────────────────────────────────────

def test_ac4_no_state_surface_import_in_decision_modules():
    files = [REPO / "strategy" / "selector.py",
             REPO / "strategy" / "sleeve_governance.py"]
    files += sorted((REPO / "production").glob("*.py"))
    for p in files:
        assert "state_surface" not in p.read_text(encoding="utf-8"), p


def test_ac4_zero_diff_on_decision_paths():
    try:
        out = subprocess.run(
            ["git", "diff", "HEAD", "--name-only", "--",
             "strategy/selector.py", "strategy/sleeve_governance.py",
             "production"],
            cwd=REPO, capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")
    assert out.stdout.strip() == "", \
        f"decision-path files modified: {out.stdout.strip()}"


# ── AC-141-5 — 徽章词汇 ∈ {ON, STANDBY}；armed 为行内字段 ─────────────────────

def test_ac5_engine_badges_vocabulary(env):
    s = ss.compute_state_surface(today=TODAY)
    assert set(s["today"]["engines"].values()) <= {"ON", "STANDBY"}
    # Quant 裁决 2026-07-13（单一归属，P1 依据：BPS delta 份额 59%/R²0.94）：
    # BPS → Trend 引擎；Premium = IC 家族 only。doc §4 已同步修正。
    assert s["today"]["engines"]["premium"] == "STANDBY"
    assert s["today"]["engines"]["trend"] == "ON"
    assert s["today"]["engines"]["convexity"] == "STANDBY"

    env["rec"] = _rec(key="reduce_wait", name="Reduce / Wait", action="WAIT")
    env["q042"] = _q042_snap(ddath=-0.05)               # DIP 触发 + armed
    s = ss.compute_state_surface(today=TODAY)
    eng = s["today"]["engines"]
    assert eng["premium"] == "STANDBY" and eng["trend"] == "STANDBY"
    assert eng["convexity"] == "ON"
    assert set(eng.values()) <= {"ON", "STANDBY"}


def test_ac5_template_badge_words_and_inline_armed():
    src = (TPL / "state_map.html").read_text(encoding="utf-8")
    assert "const BADGE_WORDS = { ON: 'ON', STANDBY: 'STANDBY' };" in src
    assert "if (word !== 'ON' && word !== 'STANDBY') return NA;" in src
    assert "Trigger armed:" in src               # armed = 行内字段（非徽章）
    # 禁止第三词徽章（ARMED/ACTIVE/READY 等不得作为 badge 文本出现）
    for banned in (">ARMED<", ">READY<", ">FIRE<"):
        assert banned not in src, banned
    badge_html = re.findall(r'class="engine-badge[^"]*">([^<]+)<', src)
    assert all(t in ("ON", "STANDBY", "${BADGE_WORDS[word]}") for t in badge_html)


# ── AC-141-6 — 量表绝对刻度（同值同长）+ cap 刻度线 ───────────────────────────

def test_ac6_bar_geometry_absolute_scale():
    a = ss.bar_geometry(15.8, 100.0, cap=80.0)
    b = ss.bar_geometry(15.8, 100.0, cap=50.0)
    assert a["width_pct"] == b["width_pct"] == 15.8      # 同值同长（cap 无关）
    assert a["cap_pos_pct"] == 80.0 and b["cap_pos_pct"] == 50.0
    assert ss.bar_geometry(120.0, 100.0)["width_pct"] == 100.0   # clamp
    assert ss.bar_geometry(-3.0, 100.0)["width_pct"] == 0.0
    g = ss.bar_geometry(22_000.0, 152_000.0)
    assert g["width_pct"] == pytest.approx(14.47, abs=0.01)
    with pytest.raises(ValueError):
        ss.bar_geometry(1.0, 0.0)
    with pytest.raises(ValueError):
        ss.bar_geometry(None, 100.0)


def test_ac6_pools_share_absolute_100_scale(env):
    env["gov"] = _gov(spx_pm=30.0, short_vol=30.0)       # mockup bug 回归：同值
    s = ss.compute_state_surface(today=TODAY)
    bp = s["pools"]["bp"]
    assert bp["spx_pm"]["scale_max"] == bp["short_vol"]["scale_max"] == 100.0
    assert bp["spx_pm"]["width_pct"] == bp["short_vol"]["width_pct"] == 30.0
    assert bp["spx_pm"]["cap_pos_pct"] == 80.0
    assert bp["short_vol"]["cap_pos_pct"] == 50.0
    cash = s["pools"]["cash"]
    assert cash["committed"]["scale_max"] == cash["liquid"]


def test_ac6_template_consumes_geometry_only():
    """模板 JS 只消费 API 的 width_pct/cap_pos_pct，不自行重算宽度。"""
    src = (TPL / "state_map.html").read_text(encoding="utf-8")
    assert "geom.width_pct + '%'" in src
    assert "g.width_pct ?? 0" in src
    assert "cap_pos_pct" in src
    # 防碰撞：刻度线标签在条外侧轨道 + 位置感知锚点换向
    assert "bar-tick-label" in src
    assert "translateX(-100%)" in src and "translateX(-50%)" in src


# ── AC-141-7 — hero 条纯新增（不动锚点逐字节一致） ─────────────────────────────

HERO_START = "<!-- ── SPEC-141 F4 hero strip start"
HERO_END = "<!-- ── SPEC-141 F4 hero strip end ── -->"


def test_ac7_hero_strip_pure_addition_diff_range():
    tpl_rel = "web/templates/portfolio_home.html"
    cur = (REPO / tpl_rel).read_text(encoding="utf-8")
    assert HERO_START in cur and HERO_END in cur
    assert 'href="/state-map"' in cur
    try:
        head = subprocess.run(
            ["git", "show", f"HEAD:{tpl_rel}"],
            cwd=REPO, capture_output=True, text=True, timeout=30, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")
    if HERO_START in head:
        return                                   # 已落地版本：diff-范围断言自然满足
    # 逐行剥除 hero 块（起止 marker 行 + 其后紧邻的一个空行），必须逐字节
    # 恢复 HEAD → 除 hero 外零改动；Open Position / Portfolio Snapshot 自动被覆盖
    lines = cur.split("\n")
    i = next(k for k, l in enumerate(lines) if HERO_START in l)
    j = next(k for k, l in enumerate(lines) if HERO_END in l)
    assert i < j
    del_to = j + 1
    if del_to < len(lines) and lines[del_to].strip() == "":
        del_to += 1                              # 吃掉插入时补的空行
    stripped = "\n".join(lines[:i] + lines[del_to:])
    assert stripped == head, \
        "portfolio_home.html 存在 hero 块之外的改动（AC-7 违例）"


def test_ac7_protected_sections_unchanged():
    tpl_rel = "web/templates/portfolio_home.html"
    cur = (REPO / tpl_rel).read_text(encoding="utf-8")
    open_pos = '<div class="pos-header">Open Position</div>'
    snapshot = 'Portfolio Snapshot</div>'
    assert open_pos in cur and snapshot in cur
    try:
        head = subprocess.run(
            ["git", "show", f"HEAD:{tpl_rel}"],
            cwd=REPO, capture_output=True, text=True, timeout=30, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")

    def section(text: str, start_marker: str, end_marker: str) -> str:
        i = text.index(start_marker)
        j = text.index(end_marker, i)
        return text[i:j]

    # Open Position 块（SPX 卡 card-position → settling panel 前）逐字节一致
    cur_pos = section(cur, '<div class="card-position" id="position-spx">',
                      '<div class="settling-panel"')
    head_pos = section(head, '<div class="card-position" id="position-spx">',
                       '<div class="settling-panel"')
    assert cur_pos == head_pos
    # Portfolio Snapshot zone 起始块逐字节一致（zone 头 → 第一个卡片结束锚）
    cur_snap = section(cur, '<!-- Portfolio Snapshot zone -->',
                       '<div class="pos-comp-section"')
    head_snap = section(head, '<!-- Portfolio Snapshot zone -->',
                        '<div class="pos-comp-section"')
    assert cur_snap == head_snap


# ── AC-141-8 — 触发预演三例（复用 094.4 helper 非重写） ────────────────────────

def test_ac8_rehearsal_episode_sufficient_cash(env):
    s = ss.compute_state_surface(today=TODAY)
    r = s["rehearsal"]
    assert r["status"] == "ok"
    assert r["episode_type"] == "episode"
    assert r["branch"] == "call_spread"
    assert "弹药充足：Call Spread" in r["advisory"]
    assert r["contracts"] > 0 and r["long_strike"] < r["short_strike"]


def test_ac8_rehearsal_episode_insufficient_cash_bps_fallback(env):
    env["liquid"] = {"total": 10_000.0, "source": "live", "error": None}
    s = ss.compute_state_surface(today=TODAY)
    r = s["rehearsal"]
    assert r["branch"] == "bps_fallback"
    assert "BPS fallback" in r["advisory"]
    assert "SELL PUT" in r["advisory"] and "BUY PUT" in r["advisory"]
    assert "3.7-7.4×" in r["advisory"]           # 收益差提醒句（Q095 P6）
    ks = r["ammo"]["bps_strikes"]
    assert ks["short_put"] > ks["long_put"]


def test_ac8_rehearsal_sudden_insufficient_stand_aside(env):
    env["closes"] = _sudden_closes()
    env["liquid"] = {"total": 10_000.0, "source": "live", "error": None}
    s = ss.compute_state_surface(today=TODAY)
    r = s["rehearsal"]
    assert r["episode_type"] == "sudden"
    assert r["branch"] == "stand_aside"
    assert "建议空仓" in r["advisory"]
    assert "BPS fallback" not in r["advisory"]


def test_ac8_rehearsal_delegates_to_094_4_helper(env, monkeypatch):
    """复用非重写：预演正文必须来自 ex._ammo_advisory 本体。"""
    sentinel = ("SENTINEL-ADVISORY", {"branch": "call_spread",
                                      "episode_type": "episode",
                                      "liquid": 1.0, "need": 0.5})
    monkeypatch.setattr(ex, "_ammo_advisory", lambda **kw: sentinel)
    s = ss.compute_state_surface(today=TODAY)
    assert s["rehearsal"]["advisory"] == "SENTINEL-ADVISORY"


# ── 页面/导航 wiring（F3 入口 + 路由 200） ─────────────────────────────────────

def test_state_map_route_renders_and_nav_entry_present(env):
    from web.server import app
    res = app.test_client().get("/state-map")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "State <em>Map</em>" in html
    assert 'class="nav-link active">State Map</a>' in html
    for token in ("LAYER 0", "LAYER 1", "LAYER 2", "LAYER 3",
                  "Survival Veto", "Market State", "Engines", "Resource Pools",
                  "Last 90 Trading Days", "Trigger Rehearsal"):
        assert token in html, token
    nav = (TPL / "_nav.html").read_text(encoding="utf-8")
    assert '>State Map</a>' in nav


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
