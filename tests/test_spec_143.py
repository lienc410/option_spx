"""SPEC-143 — Aftermath 首笔 0.5× staging（Q101 裁决 3）acceptance tests.

AC map（task/SPEC-143.md §AC）:
  AC-1 三态单测（fixtures 合成 monitor 行）：无读数→0.5×+advisory；
       s=1.0→全量；s=1.8→0.5×+复判 advisory；monitor 文件缺失→态 1
                                              → ThreeStateTests
  AC-2 张数下限：标准张数=1 时 staging 仍 ≥1     → StagedContractsTests
  AC-3 信号翻译对齐（双向探针）：2026-05 以来真实 monitor/VIX 回放断言门
       从未激活（已知阴性）；Q101 SKEW2 合成日触发 s≥1.5 复判分支
       （已知阳性）                              → CalibrationProbeTests
  AC-4 回测隔离：select_strategy 永不写 staging + backtest/ 零 import
       （matrix_audit.csv 前后 diff 为空由交付报告的 A/B 重跑证明）
                                              → BacktestIsolationTests
  AC-5 trace/卡片/open-draft 文案单源 verbatim-equality（样式同 SPEC-140）
                                              → VerbatimSingleSourceTests

密闭（tests/conftest.py 房规）：trade ledger 与 skew monitor 路径全部
monkeypatch 到 tmp；真实数据只经 tests/fixtures 冻结副本进入。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import logs.trade_log_io as tlio
import strategy.aftermath_staging as ams
import strategy.decision_trace as dt
from signals.iv_rank import IVSignal
from signals.trend import TrendSignal
from signals.vix_regime import Regime, Trend
from strategy.selector import (DEFAULT_PARAMS, StrategyName,
                               _apply_aftermath_staging_live, is_aftermath,
                               select_strategy)
from tests.test_spec_064 import make_iv, make_trend, make_vix

FIXTURES = Path(__file__).parent / "fixtures"
REAL_VIX_FIXTURE = FIXTURES / "spec143_real_vix_daily_2026-01-02_2026-07-10.json"
REAL_MONITOR_FIXTURE = (
    FIXTURES / "spec143_real_q085_skew_monitor_2026-05-04_2026-07-02.jsonl")


def _window_vix_df(n_pre: int = 40) -> tuple[pd.DataFrame, str]:
    """合成一段以 aftermath 活跃窗口收尾的日度 VIX 序列。

    尾部 34 → 30 → 29 → 28：34 当日未回落 10% 不活跃；30 起三日活跃
    （peak10=34 ≥ 28，vix ≤ 30.6，< 35）→ 窗口起始 = 34 之后第一天。
    """
    dates = pd.bdate_range("2026-04-01", periods=n_pre + 4)
    vals = [16.0] * n_pre + [34.0, 30.0, 29.0, 28.0]
    df = pd.DataFrame({"vix": vals}, index=dates)
    return df, dates[n_pre + 1].date().isoformat()


def _monitor_file(tmpdir: str, rows: list[dict]) -> Path:
    p = Path(tmpdir) / "q085_skew_monitor.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


def _skew_row(date: str, s: float) -> dict:
    """合成 monitor 行：atm_moff 取 Q101 calm 中位 −2.74，d15_moff 反推使
    (d15 − atm) / 4.52 == s。"""
    atm = -2.74
    return {"date": date, "atm_moff": atm,
            "d15_moff": round(atm + s * ams.Q101_CALM_PUT_SLOPE_VP, 6)}


def _aftermath_rec(trend_signal: TrendSignal = TrendSignal.NEUTRAL):
    """走真 selector 拿 aftermath V3-A 推荐（HIGH_VOL × IV HIGH × aftermath）。"""
    vix = make_vix(vix=27.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                   vix_peak_10d=32.0)
    rec = select_strategy(vix, make_iv(signal=IVSignal.HIGH),
                          make_trend(trend_signal), DEFAULT_PARAMS)
    assert rec.strategy == StrategyName.IRON_CONDOR_HV, rec.rationale
    assert "aftermath" in rec.rationale
    return rec


class _StagingEnv:
    """wrapper 测试统一密闭面：ledger → tmp、monitor → 指定文件。"""

    def __init__(self, tmpdir: str, monitor_rows: list[dict] | None,
                 ledger_events: list[dict] | None = None):
        if monitor_rows is None:
            monitor = Path(tmpdir) / "missing_monitor.jsonl"   # 文件缺失态
        else:
            monitor = _monitor_file(tmpdir, monitor_rows)
        ledger = Path(tmpdir) / "trade_log.jsonl"
        if ledger_events:
            with ledger.open("w", encoding="utf-8") as fh:
                for e in ledger_events:
                    fh.write(json.dumps(e) + "\n")
        self._patches = [
            patch.object(ams, "SKEW_MONITOR_PATH", monitor),
            patch.object(tlio, "TRADE_LOG_FILE", ledger),
        ]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False


def _open_event(date: str, *, strategy_key: str = "iron_condor_hv",
                paper: bool = False, trade_id: str = "t1") -> dict:
    return {"event": "open", "id": trade_id, "strategy_key": strategy_key,
            "paper_trade": paper, "timestamp": f"{date}T10:00:00-04:00"}


class ThreeStateTests(unittest.TestCase):
    """AC-1 三态 + 窗口首笔判定。"""

    def setUp(self) -> None:
        self.vix_df, self.win_start = _window_vix_df()

    def _staged_rec(self, monitor_rows, ledger_events=None,
                    trend=TrendSignal.NEUTRAL):
        with tempfile.TemporaryDirectory() as tmp, \
                _StagingEnv(tmp, monitor_rows, ledger_events):
            rec = _aftermath_rec(trend)
            return _apply_aftermath_staging_live(rec, self.vix_df,
                                                 DEFAULT_PARAMS)

    def _staging_node(self, rec) -> dict:
        return next(n for n in rec.trace
                    if n["check"] == "q101_aftermath_staging")

    def test_state1_no_reading_in_window(self) -> None:
        # monitor 只有窗口起始日之前的行 → 视同无读数 → 0.5× + advisory
        rec = self._staged_rec([_skew_row("2026-04-02", 1.0)])
        st = rec.aftermath_staging
        self.assertEqual(st["state"], 1)
        self.assertEqual(st["factor"], ams.Q101_STAGING_FACTOR)
        self.assertIsNone(st["s"])
        self.assertEqual(st["window_start"], self.win_start)
        self.assertTrue(st["first_trade"])
        node = self._staging_node(rec)
        self.assertEqual(node["outcome"], "advisory")   # ⚠ 提示档，非 veto
        self.assertIn("本窗口 skew 未实测，首笔 0.5×，实测落地后恢复",
                      node["label_human"])

    def test_state2_measured_below_threshold_full_size(self) -> None:
        rec = self._staged_rec([_skew_row(self.win_start, 1.0)])
        st = rec.aftermath_staging
        self.assertEqual(st["state"], 2)
        self.assertEqual(st["factor"], 1.0)
        self.assertAlmostEqual(st["s"], 1.0, places=6)
        node = self._staging_node(rec)
        self.assertEqual(node["outcome"], "pass")
        self.assertIn("skew 实测通过", node["label_human"])
        self.assertIn("s = 1.00", node["label_human"])  # trace 注明 s 值

    def test_state3_recheck_branch(self) -> None:
        rec = self._staged_rec([_skew_row(self.win_start, 1.8)])
        st = rec.aftermath_staging
        self.assertEqual(st["state"], 3)
        self.assertEqual(st["factor"], ams.Q101_STAGING_FACTOR)
        self.assertAlmostEqual(st["s"], 1.8, places=6)
        node = self._staging_node(rec)
        self.assertEqual(node["outcome"], "advisory")
        self.assertIn("Q101 预承诺复判触发，通道处置待 Quant 重跑判定网格",
                      node["label_human"])

    def test_monitor_file_missing_is_state1(self) -> None:
        rec = self._staged_rec(None)
        self.assertEqual(rec.aftermath_staging["state"], 1)
        self.assertEqual(rec.aftermath_staging["factor"], 0.5)

    def test_missing_fields_treated_as_no_reading(self) -> None:
        rows = [{"date": self.win_start, "atm_moff": -2.74},          # 缺 d15
                {"date": self.win_start, "d15_moff": 1.78},           # 缺 atm
                {"date": self.win_start, "d15_moff": None, "atm_moff": -2.74}]
        rec = self._staged_rec(rows)
        self.assertEqual(rec.aftermath_staging["state"], 1)

    def test_latest_window_reading_wins(self) -> None:
        # 两行：早 1.0、晚 1.8 → 取窗口内最新一行 → 态 3
        later = (pd.Timestamp(self.win_start) + pd.Timedelta(days=1)).date().isoformat()
        rec = self._staged_rec([_skew_row(self.win_start, 1.0),
                                _skew_row(later, 1.8)])
        self.assertEqual(rec.aftermath_staging["state"], 3)

    def test_both_aftermath_branches_are_staged(self) -> None:
        for trend in (TrendSignal.NEUTRAL, TrendSignal.BEARISH):
            rec = self._staged_rec(None, trend=trend)
            self.assertIsNotNone(rec.aftermath_staging, trend)

    def test_non_aftermath_ic_hv_untouched(self) -> None:
        # HIGH_VOL × NEUTRAL × IV HIGH 但 peak 不足 → SPEC-060 常规 IC_HV，
        # rationale 无 aftermath 标记 → staging 门不碰
        vix = make_vix(vix=27.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                       vix_peak_10d=27.0)
        rec = select_strategy(vix, make_iv(signal=IVSignal.HIGH),
                              make_trend(TrendSignal.NEUTRAL), DEFAULT_PARAMS)
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertNotIn("aftermath", rec.rationale)
        with tempfile.TemporaryDirectory() as tmp, _StagingEnv(tmp, None):
            out = _apply_aftermath_staging_live(rec, self.vix_df,
                                                DEFAULT_PARAMS)
        self.assertIsNone(out.aftermath_staging)
        self.assertNotIn("Q101", out.rationale)

    def test_reduce_wait_untouched(self) -> None:
        vix = make_vix(vix=36.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
                       vix_peak_10d=40.0)
        rec = select_strategy(vix, make_iv(signal=IVSignal.HIGH),
                              make_trend(TrendSignal.NEUTRAL), DEFAULT_PARAMS)
        with tempfile.TemporaryDirectory() as tmp, _StagingEnv(tmp, None):
            out = _apply_aftermath_staging_live(rec, self.vix_df,
                                                DEFAULT_PARAMS)
        self.assertIsNone(out.aftermath_staging)

    def test_first_trade_flag_window_semantics(self) -> None:
        later = (pd.Timestamp(self.win_start) + pd.Timedelta(days=1)).date().isoformat()
        before = "2026-04-03"
        cases = [
            # (ledger events, expected first_trade)
            ([], True),
            ([_open_event(before)], True),                     # 窗口前的开仓不算
            ([_open_event(later)], False),                     # 窗口内已开 → 非首笔
            ([_open_event(later, paper=True)], True),          # paper 不算
            ([_open_event(later, strategy_key="bull_put_spread")], True),
            ([_open_event(later), {"event": "void", "id": "t1",
                                   "timestamp": f"{later}T11:00:00-04:00"}],
             True),                                            # voided 不算
        ]
        for events, expected in cases:
            rec = self._staged_rec(None, ledger_events=events)
            self.assertEqual(rec.aftermath_staging["first_trade"], expected,
                             events)


class StagedContractsTests(unittest.TestCase):
    """AC-2 张数下限 + open-draft 应用层。"""

    def test_floor_with_min_one(self) -> None:
        for std, expect in ((1, 1), (2, 1), (3, 1), (4, 2), (5, 2), (10, 5)):
            self.assertEqual(ams.staged_contracts(std), expect, std)

    def _draft(self, staging: dict | None, contracts: int = 3) -> dict:
        from web.server import _apply_aftermath_staging_to_draft
        payload = {"contracts": contracts, "legs_hint": "SELL CALL 6100 (45D)"}
        rec = SimpleNamespace(aftermath_staging=staging)
        return _apply_aftermath_staging_to_draft(payload, rec)

    def test_draft_halves_contracts_state1(self) -> None:
        label, _ = dt.q101_staging_label({"state": 1, "s": None})
        payload = self._draft({"state": 1, "factor": 0.5, "s": None,
                               "label_human": label}, contracts=3)
        self.assertEqual(payload["contracts"], 1)               # floor(1.5) 下限
        self.assertEqual(payload["standard_contracts"], 3)
        self.assertTrue(payload["legs_hint"].endswith(label))

    def test_draft_standard_one_stays_one(self) -> None:
        payload = self._draft({"state": 1, "factor": 0.5, "s": None,
                               "label_human": "x"}, contracts=1)
        self.assertEqual(payload["contracts"], 1)               # AC-2 ≥ 1

    def test_draft_state2_keeps_standard(self) -> None:
        label, _ = dt.q101_staging_label({"state": 2, "s": 1.0})
        payload = self._draft({"state": 2, "factor": 1.0, "s": 1.0,
                               "label_human": label}, contracts=3)
        self.assertEqual(payload["contracts"], 3)
        self.assertNotIn("standard_contracts", payload)
        self.assertIn(label, payload["legs_hint"])

    def test_draft_noop_without_staging(self) -> None:
        payload = self._draft(None, contracts=3)
        self.assertEqual(payload["contracts"], 3)
        self.assertNotIn("aftermath_staging", payload)
        self.assertEqual(payload["legs_hint"], "SELL CALL 6100 (45D)")


class CalibrationProbeTests(unittest.TestCase):
    """AC-3 双向探针（feedback_signal_translation_alignment_ac）。"""

    @classmethod
    def setUpClass(cls) -> None:
        data = json.loads(REAL_VIX_FIXTURE.read_text(encoding="utf-8"))
        rows = data["rows"]
        cls.real_vix = pd.DataFrame(
            {"vix": [r["vix"] for r in rows]},
            index=pd.to_datetime([r["date"] for r in rows]))

    def test_known_negative_no_activation_since_2026_05(self) -> None:
        """真实 VIX 回放：2026-05-01 起每个交易日门都不激活（期内无
        aftermath 窗口——阴性校准，门不该响就没响）。"""
        vix = self.real_vix["vix"]
        peak10 = vix.rolling(10, min_periods=10).max()
        days = activations = 0
        for i, (ts, v) in enumerate(vix.items()):
            if ts.date().isoformat() < "2026-05-01":
                continue
            days += 1
            peak = peak10.iloc[i]
            snap = SimpleNamespace(vix=float(v),
                                   vix_peak_10d=None if peak != peak else float(peak))
            day_active = is_aftermath(snap, DEFAULT_PARAMS)
            # 逐日重放窗口探测（与 wrapper 同一函数）
            win = ams.aftermath_window_start(self.real_vix.iloc[:i + 1],
                                             DEFAULT_PARAMS)
            self.assertEqual(win is not None, day_active, ts)
            if day_active:
                activations += 1
        self.assertGreaterEqual(days, 45)          # 探针非空窗
        self.assertEqual(activations, 0)           # 门从未激活

    def test_known_negative_real_monitor_never_trips_recheck(self) -> None:
        """真实 monitor 读数（2026-05-04→07-02，30 行）全部 s < 1.5：
        即便窗口覆盖全期，读数也只会落态 2——校准 4.52vp calm 基线。"""
        reading = ams.latest_window_skew("2026-05-04", REAL_MONITOR_FIXTURE)
        self.assertIsNotNone(reading)
        s_values = []
        for line in REAL_MONITOR_FIXTURE.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            s = ams.put_slope_multiple(row.get("d15_moff"), row.get("atm_moff"))
            self.assertIsNotNone(s, row.get("date"))
            s_values.append(s)
        self.assertEqual(len(s_values), 30)
        self.assertLess(max(s_values), ams.Q101_SLOPE_RECHECK_MULT)
        med = sorted(s_values)[len(s_values) // 2]
        self.assertTrue(0.8 <= med <= 1.2,          # calm 中位 ≈ 1× 基线
                        f"calm 基线失准：median s = {med}")

    def test_known_positive_skew2_synthetic_day(self) -> None:
        """已知阳性：Q101 SKEW2 合成日（斜率 ×2 悲观 bracket：atm_moff
        −2.74 / d15_moff = −2.74 + 2×4.52 → s = 2.0）必须触发复判分支。"""
        vix_df, win_start = _window_vix_df()
        skew2 = {"date": win_start, "atm_moff": -2.74,
                 "d15_moff": round(-2.74 + 2 * ams.Q101_CALM_PUT_SLOPE_VP, 6)}
        with tempfile.TemporaryDirectory() as tmp, _StagingEnv(tmp, [skew2]):
            rec = _apply_aftermath_staging_live(_aftermath_rec(), vix_df,
                                                DEFAULT_PARAMS)
        st = rec.aftermath_staging
        self.assertEqual(st["state"], 3)
        self.assertAlmostEqual(st["s"], 2.0, places=6)
        self.assertEqual(st["factor"], 0.5)
        self.assertIn("Q101 预承诺复判触发", rec.rationale)


class BacktestIsolationTests(unittest.TestCase):
    """AC-4 结构证明（matrix_audit.csv A/B diff 为空另由交付报告记录）。"""

    def test_select_strategy_never_sets_staging(self) -> None:
        rec = _aftermath_rec()
        self.assertIsNone(rec.aftermath_staging)
        self.assertNotIn("Q101", rec.rationale)
        self.assertFalse(any(n.get("check") == "q101_aftermath_staging"
                             for n in rec.trace))

    def test_backtest_paths_have_zero_staging_reference(self) -> None:
        """回测/信号/生产 executor 目录零 aftermath_staging 引用——staging
        只活在 live wrapper（selector）与 web 显示层。"""
        offenders = []
        for d in ("backtest", "signals", "production", "notify"):
            for p in (REPO / d).rglob("*.py"):
                if "aftermath_staging" in p.read_text(encoding="utf-8"):
                    offenders.append(str(p.relative_to(REPO)))
        self.assertEqual(offenders, [])

    def test_backtest_engine_never_calls_live_entrypoint(self) -> None:
        src = (REPO / "backtest" / "engine.py").read_text(encoding="utf-8")
        self.assertNotIn("get_recommendation", src)
        self.assertNotIn("_apply_aftermath_staging_live", src)

    def test_wrapper_fail_soft_keeps_recommendation(self) -> None:
        """staging 内部炸掉也不许打断推荐路径（同 SPEC-123 wrapper 先例）。"""
        rec = _aftermath_rec()
        with patch("strategy.aftermath_staging.evaluate_staging",
                   side_effect=RuntimeError("boom")):
            out = _apply_aftermath_staging_live(rec, None, DEFAULT_PARAMS)
        self.assertEqual(out.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertIsNone(out.aftermath_staging)


class VerbatimSingleSourceTests(unittest.TestCase):
    """AC-5 文案单源 + verbatim-equality（断言样式同 SPEC-140 §1）。"""

    def _staged(self, s: float | None):
        vix_df, win_start = _window_vix_df()
        rows = None if s is None else [_skew_row(win_start, s)]
        with tempfile.TemporaryDirectory() as tmp, _StagingEnv(tmp, rows):
            return _apply_aftermath_staging_live(_aftermath_rec(), vix_df,
                                                 DEFAULT_PARAMS)

    def test_trace_node_card_and_draft_verbatim_equal(self) -> None:
        from web.server import _apply_aftermath_staging_to_draft
        for s in (None, 1.0, 1.8):                  # 三态各断言一次
            rec = self._staged(s)
            st = rec.aftermath_staging
            expected, _ = dt.q101_staging_label(st)
            node = next(n for n in rec.trace
                        if n["check"] == "q101_aftermath_staging")
            # trace 节点 == 单源函数输出（逐字）
            self.assertEqual(node["label_human"], expected)
            # 卡片（/api/recommendation rationale 附注）逐字含同一主文
            self.assertTrue(rec.rationale.endswith(f"　[{expected}]"),
                            rec.rationale)
            # open-draft legs_hint 附注逐字同源
            payload = _apply_aftermath_staging_to_draft(
                {"contracts": 2, "legs_hint": "L"}, rec)
            self.assertTrue(payload["legs_hint"].endswith(expected))

    def test_outcome_is_advisory_never_veto(self) -> None:
        """SPEC-143 约束：advisory ⚠ 档（非 veto）——三态 outcome 只允许
        advisory / pass（SPEC-140 §4 映射下 advisory 永不响铃）。"""
        for s, expected in ((None, "advisory"), (1.0, "pass"),
                            (1.8, "advisory")):
            rec = self._staged(s)
            node = next(n for n in rec.trace
                        if n["check"] == "q101_aftermath_staging")
            self.assertEqual(node["outcome"], expected)
            self.assertNotEqual(node["outcome"], "veto")

    def test_wording_single_copy_source(self) -> None:
        """staging 人话主文只活在 strategy/decision_trace.py；消费方
        （selector / web/server / 模板）不得手写第二套。"""
        phrases = ("本窗口 skew 未实测", "预承诺复判触发，通道处置待",
                   "skew 实测通过")
        scan = [p for d in ("strategy", "web", "notify", "production",
                            "signals", "backtest")
                for p in (REPO / d).rglob("*.py")]
        scan += list((REPO / "web" / "templates").rglob("*.html"))
        offenders = []
        for p in scan:
            if p.name == "decision_trace.py":
                continue
            src = p.read_text(encoding="utf-8")
            for ph in phrases:
                if ph in src:
                    offenders.append(f"{p.relative_to(REPO)}: {ph}")
        self.assertEqual(offenders, [], offenders)

    def test_consumers_import_single_source(self) -> None:
        sel = (REPO / "strategy" / "selector.py").read_text(encoding="utf-8")
        self.assertIn("q101_staging_label", sel)
        web = (REPO / "web" / "server.py").read_text(encoding="utf-8")
        self.assertIn("from strategy.aftermath_staging import staged_contracts",
                      web)
        # 模板零新增文案：spx.html 不含任何 staging 词面
        tpl = (REPO / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        self.assertNotIn("Q101", tpl)
        self.assertNotIn("staging", tpl)


if __name__ == "__main__":
    unittest.main()
