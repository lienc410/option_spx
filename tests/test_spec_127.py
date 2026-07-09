"""SPEC-127 — Diagonal Roll 登记与 Campaign 记账.

AC coverage:
  AC-1 roll 原子性（部分失败回滚）                     → RollEndpointTests
  AC-2 campaign 聚合数学（多 cycle + 部分平仓）         → CampaignMathTests
  AC-3 adjusted basis 与逐 cycle 加总恒等               → CampaignMathTests
  AC-4 止损锚：零 roll bit-identical + 有 roll 按 basis → DebitStopAnchorTests
  AC-5 H-5 21-DTE（含 ROLL 分支/时钟重置）+ collapse    → H5ActionEngineTests
  AC-6 ledger 迁移（campaign_id + legs 回填）           → MigrationTests
  Performance 页 campaign 口径回归                      → PerformanceCampaignTests

测试向量全部脚本生成（seeded RNG / 参数化构造），无手抄常数。
"""
from __future__ import annotations

import json
import os
import random
import struct
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import logs.trade_log_io as tlog
import strategy.bcd_governance as gov
import strategy.state as state_mod
from strategy.bcd_stop import debit_stop_ratio
from strategy.campaign import build_campaigns, current_short_leg, trade_roll_income_usd


TODAY = date.today()


def _iso(days_from_today: int) -> str:
    return (TODAY + timedelta(days=days_from_today)).isoformat()


# ── 向量生成器（脚本生成，禁手抄）────────────────────────────────────────────

def mk_open(tid: str, *, premium: float, contracts: int = 1, account: str = "schwab",
            campaign_id: str | None = None, short_strike: float = 7700,
            long_strike: float = 7200, expiry: str | None = None,
            long_expiry: str | None = None, opened: str | None = None,
            short_entry_price: float | None = None,
            strategy_key: str = "bull_call_diagonal", paper: bool = False) -> dict:
    ev = {
        "id": tid, "event": "open", "timestamp": f"{opened or _iso(-30)}T10:00:00-04:00",
        "strategy_key": strategy_key, "strategy": "Bull Call Diagonal",
        "underlying": "SPX", "account": account,
        "short_strike": short_strike, "long_strike": long_strike,
        "expiry": expiry or _iso(15), "long_expiry": long_expiry or _iso(60),
        "contracts": contracts, "actual_premium": premium,
        "paper_trade": paper,
    }
    if campaign_id:
        ev["campaign_id"] = campaign_id
    if short_entry_price is not None:
        ev["short_entry_price"] = short_entry_price
    return ev


def mk_roll(tid: str, seq: int, *, close_price: float, open_price: float,
            old_strike: float, old_expiry: str, new_strike: float,
            new_expiry: str, contracts: int = 1, when: str | None = None,
            campaign_id: str | None = None) -> dict:
    return {
        "id": tid, "event": "roll",
        "timestamp": f"{when or _iso(-10)}T10:05:00-04:00",
        "roll_id": f"{tid}_roll_{seq}",
        "campaign_id": campaign_id or tid,
        "closed_short": {"strike": old_strike, "expiry": old_expiry, "price": close_price},
        "new_short": {"strike": new_strike, "expiry": new_expiry, "price": open_price},
        "roll_net_credit": round(open_price - close_price, 4),
        "contracts": contracts,
    }


def mk_close(tid: str, *, exit_premium: float, entry_premium: float,
             contracts: int = 1, when: str | None = None,
             reason: str = "discretionary") -> dict:
    return {
        "id": tid, "event": "close",
        "timestamp": f"{when or _iso(-1)}T15:55:00-04:00",
        "open_id": tid, "exit_premium": exit_premium,
        "exit_reason": reason,
        "actual_pnl": round((entry_premium - exit_premium) * 100 * contracts, 2),
        "contracts": contracts,
    }


def mk_chain(rows: list[dict]) -> pd.DataFrame:
    """call chain fixture: rows of {expiry, strike, mid, bid, ask, delta, dte}."""
    return pd.DataFrame(rows)


def resolved_from_events(events: list[dict]) -> list[dict]:
    """Run events through the real resolver (writes a temp ledger)."""
    with tempfile.TemporaryDirectory() as tmp:
        orig = tlog.TRADE_LOG_FILE
        tlog.TRADE_LOG_FILE = Path(tmp) / "trade_log.jsonl"
        try:
            for e in events:
                tlog.append_event(e)
            return tlog.resolve_log()
        finally:
            tlog.TRADE_LOG_FILE = orig


# ── AC-2 / AC-3 — campaign 聚合数学 ──────────────────────────────────────────

class CampaignMathTests(unittest.TestCase):
    def test_multi_cycle_partial_close_aggregation(self) -> None:
        """AC-2: 双 member（一平一开）+ 各自多 cycle 的 campaign 聚合."""
        rng = random.Random(127)
        prem1 = -round(rng.uniform(300, 500), 2)   # debit 负
        prem2 = -round(rng.uniform(300, 500), 2)
        n1, n2 = 1, 2
        e0 = _iso(15)
        rolls1 = [(round(rng.uniform(3, 8), 2), round(rng.uniform(20, 35), 2)),
                  (round(rng.uniform(3, 8), 2), round(rng.uniform(20, 35), 2))]
        rolls2 = [(round(rng.uniform(3, 8), 2), round(rng.uniform(20, 35), 2))]
        exit1 = -round(rng.uniform(400, 480), 2)   # debit 平仓收钱 → cost 为负

        events = [
            mk_open("A1", premium=prem1, contracts=n1, campaign_id="A1",
                    opened=_iso(-30), expiry=e0),
            mk_open("A2", premium=prem2, contracts=n2, account="etrade",
                    campaign_id="A1", opened=_iso(-30), expiry=e0),
        ]
        for k, (c, o) in enumerate(rolls1, start=1):
            events.append(mk_roll("A1", k, close_price=c, open_price=o,
                                  old_strike=7700, old_expiry=e0,
                                  new_strike=7800, new_expiry=_iso(45),
                                  contracts=n1, when=_iso(-20 + k),
                                  campaign_id="A1"))
        for k, (c, o) in enumerate(rolls2, start=1):
            events.append(mk_roll("A2", k, close_price=c, open_price=o,
                                  old_strike=7700, old_expiry=e0,
                                  new_strike=7800, new_expiry=_iso(45),
                                  contracts=n2, when=_iso(-20 + k),
                                  campaign_id="A1"))
        events.append(mk_close("A1", exit_premium=exit1, entry_premium=prem1,
                               contracts=n1, when=_iso(-1)))

        camps = build_campaigns(resolved_from_events(events))
        self.assertEqual(len(camps), 1)
        c = camps[0]

        # 独立算术（同一向量重新推导）
        exp_debit = (-prem1) * 100 * n1 + (-prem2) * 100 * n2
        exp_roll_income = (sum(o - cl for cl, o in rolls1) * 100 * n1
                           + sum(o - cl for cl, o in rolls2) * 100 * n2)
        exp_realized_close = (prem1 - exit1) * 100 * n1
        self.assertEqual(c["campaign_id"], "A1")
        self.assertEqual(c["status"], "open")          # A2 未平 → 部分平仓
        self.assertEqual(sorted(c["members"]), ["A1", "A2"])
        self.assertAlmostEqual(c["initial_debit_usd"], exp_debit, places=2)
        self.assertAlmostEqual(c["roll_income_usd"], exp_roll_income, places=2)
        self.assertAlmostEqual(c["adjusted_basis_usd"], exp_debit - exp_roll_income, places=2)
        self.assertAlmostEqual(c["realized_usd"], exp_realized_close + exp_roll_income, places=2)
        self.assertEqual(c["n_rolls"], len(rolls1) + len(rolls2))
        # cycle 层：open 行 2 + roll 行 3 + close 行 1
        kinds = [r["kind"] for r in c["cycles"]]
        self.assertEqual(kinds.count("open"), 2)
        self.assertEqual(kinds.count("roll"), 3)
        self.assertEqual(kinds.count("close"), 1)

    def test_ac3_identity_randomized(self) -> None:
        """AC-3: adjusted basis == initial debit − Σ(cycle realized)，随机向量."""
        rng = random.Random(20260706)
        for trial in range(25):
            prem = -round(rng.uniform(100, 900), 2)
            n = rng.randint(1, 4)
            n_rolls = rng.randint(0, 5)
            events = [mk_open(f"T{trial}", premium=prem, contracts=n,
                              campaign_id=f"T{trial}", opened=_iso(-40))]
            for k in range(1, n_rolls + 1):
                events.append(mk_roll(
                    f"T{trial}", k,
                    close_price=round(rng.uniform(1, 15), 2),
                    open_price=round(rng.uniform(10, 40), 2),
                    old_strike=7700, old_expiry=_iso(10), new_strike=7800,
                    new_expiry=_iso(50), contracts=n, when=_iso(-30 + k),
                    campaign_id=f"T{trial}"))
            camps = build_campaigns(resolved_from_events(events))
            self.assertEqual(len(camps), 1)
            c = camps[0]
            cycle_sum = sum(r["realized_usd"] for r in c["cycles"]
                            if r["kind"] == "roll")
            self.assertAlmostEqual(
                c["adjusted_basis_usd"], c["initial_debit_usd"] - cycle_sum,
                places=2,
                msg=f"trial {trial}: identity violated")

    def test_legacy_trade_degenerates_to_own_campaign(self) -> None:
        events = [mk_open("L1", premium=8.0, strategy_key="bull_put_spread",
                          long_expiry=None, opened=_iso(-5)),
                  mk_close("L1", exit_premium=3.0, entry_premium=8.0, when=_iso(-1))]
        camps = build_campaigns(resolved_from_events(events))
        self.assertEqual(len(camps), 1)
        c = camps[0]
        self.assertEqual(c["campaign_id"], "L1")
        self.assertEqual(c["status"], "closed")
        self.assertEqual(c["n_rolls"], 0)
        self.assertAlmostEqual(c["realized_usd"], (8.0 - 3.0) * 100, places=2)


# ── AC-4 — 止损锚 ────────────────────────────────────────────────────────────

class DebitStopAnchorTests(unittest.TestCase):
    def test_zero_roll_bit_identical(self) -> None:
        """零 roll：新口径必须与旧表达式 (cv−ev)/|ev| bit-identical."""
        rng = random.Random(4242)
        for _ in range(500):
            ev = rng.uniform(0.01, 1000.0)      # debit 为正（engine convention）
            cv = rng.uniform(-100.0, 1500.0)
            legacy_pnl = cv - ev
            legacy = legacy_pnl / abs(ev)
            new = debit_stop_ratio(ev, cv, 0.0)
            self.assertEqual(struct.pack("<d", legacy), struct.pack("<d", new),
                             msg=f"bit divergence at ev={ev!r} cv={cv!r}")

    def test_roll_income_moves_anchor_to_adjusted_basis(self) -> None:
        """有 roll：止损线 = 现值 ≤ 0.5 × (D − R)，不再是 0.5 × D."""
        rng = random.Random(88)
        for _ in range(50):
            D = round(rng.uniform(200, 600), 2)
            R = round(rng.uniform(10, D * 0.6), 2)
            basis = D - R
            eps = 0.01
            # 刚好越过新止损线 → 触发
            self.assertLessEqual(debit_stop_ratio(D, 0.5 * basis - eps, R), -0.50)
            # 新线之上 → 不触发
            self.assertGreater(debit_stop_ratio(D, 0.5 * basis + eps, R), -0.50)
            # 旧锚（0.5×D）位置在新口径下不触发（旧线 > 新线）
            if 0.5 * D > 0.5 * basis + eps:
                self.assertGreater(debit_stop_ratio(D, 0.5 * D, R), -0.50)

    def test_basis_fully_recovered_disables_ratio_stop(self) -> None:
        self.assertEqual(debit_stop_ratio(400.0, 10.0, 400.0), 0.0)
        self.assertEqual(debit_stop_ratio(400.0, 10.0, 500.0), 0.0)

    def test_engine_position_has_roll_income_default_zero(self) -> None:
        from backtest.engine import Position
        from strategy.selector import StrategyName
        p = Position(strategy=StrategyName.BULL_CALL_DIAGONAL, underlying="SPX",
                     entry_date="2026-01-01", entry_spx=6000.0, entry_vix=15.0,
                     entry_sigma=0.15)
        self.assertEqual(p.roll_income, 0.0)


# ── AC-1 — roll 原子性（endpoint 层）─────────────────────────────────────────

class RollEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        tmp = self.tmpdir.name
        self.orig_state = state_mod.STATE_FILE
        self.orig_closed = state_mod.CLOSED_TRADES_FILE
        self.orig_log = tlog.TRADE_LOG_FILE
        state_mod.STATE_FILE = os.path.join(tmp, "current_position.json")
        state_mod.CLOSED_TRADES_FILE = os.path.join(tmp, "closed_trades.jsonl")
        tlog.TRADE_LOG_FILE = Path(tmp) / "trade_log.jsonl"

        from web.server import app
        self.client = app.test_client()

        # 向量
        self.prem = {"T1": -411.0, "T2": -415.0}
        self.n = {"T1": 1, "T2": 2}
        self.short0, self.exp0 = 7700, _iso(11)
        self.long_exp = _iso(70)
        for tid, acct in (("T1", "schwab"), ("T2", "etrade")):
            state_mod.write_state(
                "Bull Call Diagonal", "SPX", strategy_key="bull_call_diagonal",
                account=acct, trade_id=tid, short_strike=self.short0,
                long_strike=7200, expiry=self.exp0, long_expiry=self.long_exp,
                contracts=self.n[tid], actual_premium=self.prem[tid],
                campaign_id="T1")
            tlog.append_event(mk_open(tid, premium=self.prem[tid],
                                      contracts=self.n[tid], account=acct,
                                      campaign_id="T1", expiry=self.exp0,
                                      long_expiry=self.long_exp))

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state
        state_mod.CLOSED_TRADES_FILE = self.orig_closed
        tlog.TRADE_LOG_FILE = self.orig_log

    def _roll_payload(self, close1=5.0, open1=30.0, close2=6.0, open2=31.0) -> dict:
        return {
            "legs": [
                {"trade_id": "T1", "close_price": close1, "open_price": open1},
                {"trade_id": "T2", "close_price": close2, "open_price": open2},
            ],
            "new_short_strike": 7900,
            "new_expiry": _iso(45),
            "note": "test roll",
        }

    def _ledger_bytes(self) -> bytes:
        return Path(tlog.TRADE_LOG_FILE).read_bytes()

    @patch("notify.gateway.push", return_value=True)
    def test_happy_path_atomic_roll(self, _push) -> None:
        payload = self._roll_payload()
        res = self.client.post("/api/position/roll", json=payload)
        self.assertEqual(res.status_code, 200, res.get_json())
        data = res.get_json()
        self.assertTrue(data["ok"])

        # ledger: 每 leg 一个 roll 事件，roll_id/campaign_id 完整
        resolved = {t["id"]: t for t in tlog.resolve_log()}
        for i, tid in enumerate(("T1", "T2")):
            rolls = resolved[tid]["rolls"]
            self.assertEqual(len(rolls), 1)
            r = rolls[0]
            self.assertEqual(r["roll_id"], f"{tid}_roll_1")
            self.assertEqual(r["campaign_id"], "T1")
            spec = payload["legs"][i]
            self.assertAlmostEqual(r["roll_net_credit"],
                                   spec["open_price"] - spec["close_price"], places=4)

        # state：短腿更新 + roll_income 累积 + short_entry_price
        st = state_mod.read_all_positions()
        for p in st["positions"]:
            spec = next(s for s in payload["legs"] if s["trade_id"] == p["trade_id"])
            self.assertEqual(p["expiry"], payload["new_expiry"])
            self.assertEqual(p["short_strike"], payload["new_short_strike"])
            self.assertAlmostEqual(p["roll_income"],
                                   spec["open_price"] - spec["close_price"], places=4)
            self.assertAlmostEqual(p["short_entry_price"], spec["open_price"], places=4)
            self.assertAlmostEqual(p["actual_premium"], self.prem[p["trade_id"]])  # 不动

        # closed_trades cycle 行：realized = net×100×n
        rows = [json.loads(line) for line in
                Path(state_mod.CLOSED_TRADES_FILE).read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        for row in rows:
            spec = next(s for s in payload["legs"] if s["trade_id"] == row["trade_id"])
            self.assertTrue(row["cycle_event"])
            self.assertEqual(row["close_reason"], "roll")
            self.assertEqual(row["campaign_id"], "T1")
            self.assertAlmostEqual(
                row["realized_pnl"],
                (spec["open_price"] - spec["close_price"]) * 100 * self.n[row["trade_id"]],
                places=2)

        # campaign 聚合吃到 roll income
        camp = build_campaigns(tlog.resolve_log())[0]
        exp_income = sum((s["open_price"] - s["close_price"]) * 100 * self.n[s["trade_id"]]
                         for s in payload["legs"])
        self.assertAlmostEqual(camp["roll_income_usd"], exp_income, places=2)

    def test_validation_failure_writes_nothing(self) -> None:
        before_ledger = self._ledger_bytes()
        before_state = json.dumps(state_mod._load_raw(), sort_keys=True)
        payload = self._roll_payload()
        payload["legs"][1]["trade_id"] = "GHOST"   # 无效 leg → 全单拒绝
        res = self.client.post("/api/position/roll", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self._ledger_bytes(), before_ledger)
        self.assertEqual(json.dumps(state_mod._load_raw(), sort_keys=True), before_state)
        self.assertFalse(os.path.exists(state_mod.CLOSED_TRADES_FILE))

    def test_partial_failure_rolls_back(self) -> None:
        """AC-1：cycle 行写入失败 → 状态恢复 + roll_void 抵销 + campaign 归零."""
        before_state = json.dumps(state_mod._load_raw(), sort_keys=True)
        with patch.object(state_mod, "append_roll_cycle_rows",
                          side_effect=OSError("disk full (injected)")):
            res = self.client.post("/api/position/roll", json=self._roll_payload())
        self.assertEqual(res.status_code, 500)
        # 状态恢复
        self.assertEqual(json.dumps(state_mod._load_raw(), sort_keys=True), before_state)
        # roll 事件被 roll_void 抵销 → resolved rolls 为空
        resolved = {t["id"]: t for t in tlog.resolve_log()}
        for tid in ("T1", "T2"):
            self.assertEqual(resolved[tid]["rolls"], [],
                             "voided roll must not survive resolution")
        raw_events = tlog.load_log()
        self.assertEqual(sum(1 for e in raw_events if e.get("event") == "roll_void"), 2)
        # campaign 数学不受影响
        camp = build_campaigns(tlog.resolve_log())[0]
        self.assertEqual(camp["roll_income_usd"], 0.0)
        self.assertEqual(camp["n_rolls"], 0)
        # cycle 行未写
        self.assertFalse(os.path.exists(state_mod.CLOSED_TRADES_FILE))

    @patch("notify.gateway.push", return_value=True)
    def test_api_campaigns_endpoint_serves_finite_json(self, _push) -> None:
        self.client.post("/api/position/roll", json=self._roll_payload())
        res = self.client.get("/api/campaigns?status=open")
        self.assertEqual(res.status_code, 200)
        text = res.get_data(as_text=True)
        for bad in ("NaN", "Infinity"):
            self.assertNotIn(bad, text)
        camps = res.get_json()["campaigns"]
        self.assertEqual(len(camps), 1)
        self.assertEqual(camps[0]["campaign_id"], "T1")
        self.assertEqual(camps[0]["n_cycles"], 2)


# ── AC-5 — H-5 动作引擎 ──────────────────────────────────────────────────────

class H5ActionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        tmp = Path(self.tmpdir.name)
        self._orig = {k: getattr(gov, k) for k in
                      ("STATE_PATH", "MARKS_PATH", "CLOSED_TRADES", "SHADOW_PATH", "ROOT")}
        gov.STATE_PATH = tmp / "gov_state.json"
        gov.MARKS_PATH = tmp / "marks.jsonl"
        gov.CLOSED_TRADES = tmp / "closed.jsonl"
        gov.SHADOW_PATH = tmp / "shadow.jsonl"
        gov.ROOT = tmp
        self.orig_log = tlog.TRADE_LOG_FILE
        tlog.TRADE_LOG_FILE = tmp / "trade_log.jsonl"
        self.today = TODAY.isoformat()

    def tearDown(self) -> None:
        for k, v in self._orig.items():
            setattr(gov, k, v)
        tlog.TRADE_LOG_FILE = self.orig_log

    def _chain(self, *, short_strike=7700.0, short_expiry=None, short_mid=12.0):
        short_expiry = short_expiry or _iso(11)
        rows = [
            # 当前短腿（残值报价）
            {"expiry": short_expiry, "strike": short_strike, "mid": short_mid,
             "bid": short_mid - 0.5, "ask": short_mid + 0.5, "delta": 0.18,
             "dte": max((date.fromisoformat(short_expiry) - TODAY).days, 0)},
            # 45 DTE 建议腿（|Δ| 0.30 最近）
            {"expiry": _iso(45), "strike": 7900.0, "mid": 29.1, "bid": 28.4,
             "ask": 29.8, "delta": 0.31, "dte": 45},
            {"expiry": _iso(45), "strike": 8000.0, "mid": 18.0, "bid": 17.5,
             "ask": 18.5, "delta": 0.22, "dte": 45},
        ]
        return mk_chain(rows)

    def test_21dte_trigger_fires(self) -> None:
        tlog.append_event(mk_open("B1", premium=-411.0, expiry=_iso(11)))
        actions = gov.evaluate_short_leg_actions(self.today, self._chain())
        self.assertEqual(len(actions), 1)
        a = actions[0]
        self.assertEqual(a["trade_id"], "B1")
        self.assertEqual(a["short_dte"], 11)
        self.assertTrue(any("≤ 21" in t for t in a["triggers"]))
        # 建议新短腿 = 45 DTE |Δ|0.30 行
        self.assertEqual(a["suggested_new_short"]["strike"], 7900.0)
        msg = gov._action_message(a)
        self.assertIn("CLOSE 或 ROLL", msg)

    def test_collapse_trigger_fires_below_15pct(self) -> None:
        # 短腿 40 DTE（不触发 21-DTE），残值 = 10% 入场权利金 → collapse
        entry_credit = 30.0
        exp = _iso(40)
        tlog.append_event(mk_open("B2", premium=-411.0, expiry=exp,
                                  short_entry_price=entry_credit))
        chain = self._chain(short_expiry=exp,
                            short_mid=round(entry_credit * 0.10, 2))
        actions = gov.evaluate_short_leg_actions(self.today, chain)
        self.assertEqual(len(actions), 1)
        self.assertTrue(any("collapse" in t for t in actions[0]["triggers"]))
        # 残值 20% → 不触发
        chain2 = self._chain(short_expiry=exp,
                             short_mid=round(entry_credit * 0.20, 2))
        self.assertEqual(gov.evaluate_short_leg_actions(self.today, chain2), [])

    def test_spec137_collapse_activation_filled_vs_unfilled(self) -> None:
        """SPEC-137 §3 填/不填双路径：cycle-0 collapse ≤15% 检查只在开仓记录了
        per-leg fill（short_entry_price）时激活；不填则退回纯 21-DTE 兜底，即便
        链上残值很低也不因 collapse 触发。"""
        exp = _iso(40)   # 40 DTE — 远离 21-DTE 兜底，隔离 collapse 判定
        # 残值 = 5% of a plausible credit — 若 collapse 激活必触发
        chain = self._chain(short_expiry=exp, short_mid=1.5)

        # (a) 填了 fill=30 → 残值 1.5 ≤ 15%×30=4.5 → collapse 触发
        tlog.append_event(mk_open("F1", premium=-411.0, expiry=exp,
                                  short_entry_price=30.0))
        filled = gov.evaluate_short_leg_actions(self.today, chain)
        self.assertEqual(len(filled), 1)
        self.assertTrue(any("collapse" in t for t in filled[0]["triggers"]))
        self.assertEqual(filled[0]["short_entry_price"], 30.0)

        # (b) 没填 → 无入场权利金基线 → collapse 无从激活；40 DTE 未到 21-DTE
        #     → 该仓位零动作（纯兜底路径）
        tlog.TRADE_LOG_FILE.unlink()
        tlog.append_event(mk_open("U1", premium=-411.0, expiry=exp))  # 无 short_entry_price
        unfilled = gov.evaluate_short_leg_actions(self.today, chain)
        self.assertEqual(unfilled, [])

        # (c) 没填但短腿已 ≤21 DTE → 21-DTE 兜底仍独立触发（collapse 缺席不影响它）
        tlog.TRADE_LOG_FILE.unlink()
        tlog.append_event(mk_open("U2", premium=-411.0, expiry=_iso(11)))
        fallback = gov.evaluate_short_leg_actions(self.today, self._chain(short_expiry=_iso(11)))
        self.assertEqual(len(fallback), 1)
        self.assertTrue(any("≤ 21" in t for t in fallback[0]["triggers"]))
        self.assertFalse(any("collapse" in t for t in fallback[0]["triggers"]))

    def test_roll_branch_resets_dte_clock(self) -> None:
        """AC-5 ROLL 分支：roll 后时钟按新短腿重置."""
        old_exp = _iso(11)
        tlog.append_event(mk_open("B3", premium=-411.0, expiry=old_exp))
        # roll 前触发
        self.assertEqual(len(gov.evaluate_short_leg_actions(self.today, None)), 1)
        # roll 到 45 DTE → 时钟重置，不触发
        tlog.append_event(mk_roll("B3", 1, close_price=5.0, open_price=30.0,
                                  old_strike=7700, old_expiry=old_exp,
                                  new_strike=7900, new_expiry=_iso(45),
                                  when=self.today))
        self.assertEqual(gov.evaluate_short_leg_actions(self.today, None), [])
        # 新短腿也走到 15 DTE → 再次触发（针对新腿）
        tlog.append_event(mk_roll("B3", 2, close_price=4.0, open_price=25.0,
                                  old_strike=7900, old_expiry=_iso(45),
                                  new_strike=7950, new_expiry=_iso(15),
                                  when=self.today))
        actions = gov.evaluate_short_leg_actions(self.today, None)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["short_expiry"], _iso(15))
        self.assertEqual(actions[0]["short_dte"], 15)
        # collapse 参考价也跟随新短腿的 credit
        self.assertEqual(actions[0]["short_entry_price"], 25.0)

    def test_daily_update_pushes_action_via_gateway(self) -> None:
        tlog.append_event(mk_open("B4", premium=-411.0, expiry=_iso(11)))
        sent: list[dict] = []

        def _rec(category, about, title, body, **kw):
            sent.append({"category": category, "about": about,
                         "title": title, "body": body, **kw})
            return True

        with patch("notify.gateway.push", side_effect=_rec):
            summary = gov.daily_update(self.today, calls=self._chain(), dry_run=False)
        self.assertEqual(len(summary["short_leg_actions"]), 1)
        action_pushes = [s for s in sent if "CLOSE 或 ROLL" in s.get("body", "")]
        self.assertEqual(len(action_pushes), 1)
        p = action_pushes[0]
        self.assertEqual(p["category"], "ACTION")
        self.assertEqual(p["about"], "持仓 B4")
        self.assertIn("B4", p["dedupe_key"])

    def test_marks_follow_rolled_short_leg(self) -> None:
        """roll 后 record_daily_marks 用新短腿报价."""
        old_exp, new_exp = _iso(11), _iso(45)
        tlog.append_event(mk_open("B5", premium=-411.0, expiry=old_exp,
                                  long_expiry=_iso(70), short_strike=7700.0,
                                  long_strike=7200.0))
        tlog.append_event(mk_roll("B5", 1, close_price=5.0, open_price=30.0,
                                  old_strike=7700.0, old_expiry=old_exp,
                                  new_strike=7900.0, new_expiry=new_exp,
                                  when=self.today))
        long_mid, new_short_mid = 460.0, 29.1
        chain = mk_chain([
            {"expiry": _iso(70), "strike": 7200.0, "mid": long_mid,
             "bid": 458.0, "ask": 462.0, "delta": 0.72, "dte": 70},
            {"expiry": old_exp, "strike": 7700.0, "mid": 12.0,
             "bid": 11.5, "ask": 12.5, "delta": 0.18, "dte": 11},
            {"expiry": new_exp, "strike": 7900.0, "mid": new_short_mid,
             "bid": 28.4, "ask": 29.8, "delta": 0.31, "dte": 45},
        ])
        rows = gov.record_daily_marks(chain, self.today)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["value_mid"], long_mid - new_short_mid, places=4)


# ── AC-6 — ledger 迁移 ───────────────────────────────────────────────────────

class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        tmp = Path(self.tmpdir.name)
        self.orig_log = tlog.TRADE_LOG_FILE
        tlog.TRADE_LOG_FILE = tmp / "trade_log.jsonl"

        import scripts.spec127_campaign_migration as mig
        self.mig = mig
        # closed_trades long_expiry lookup 指到测试文件
        self._orig_root = mig.ROOT
        mig.ROOT = tmp
        (tmp / "data").mkdir()
        self.opened = _iso(-33)
        self.long_exp = _iso(55)
        with (tmp / "data" / "closed_trades.jsonl").open("w") as f:
            for tid in ("2026-06-05_bcd_001", "2026-06-05_bcd_002"):
                f.write(json.dumps({"trade_id": tid, "long_expiry": self.long_exp,
                                    "strategy_key": "bull_call_diagonal"}) + "\n")

        # 双仓（open 事件不带 long_expiry/campaign_id/legs — 模拟迁移前 ledger）
        for tid, acct in (("2026-06-05_bcd_001", "schwab"), ("2026-06-05_bcd_002", "etrade")):
            ev = mk_open(tid, premium=-411.0, account=acct, opened=self.opened,
                         expiry=_iso(12), long_expiry=None)
            ev.pop("long_expiry")
            tlog.append_event(ev)
            # PM 已登记的 discretionary close（残对平仓）→ 同 campaign
            tlog.append_event(mk_close(tid, exit_premium=-440.0,
                                       entry_premium=-411.0, when=_iso(-1),
                                       reason="discretionary"))
        # 干扰项：非 BCD + voided BCD
        tlog.append_event(mk_open("2026-05-14_bps_001", premium=43.3,
                                  strategy_key="bull_put_spread", opened=_iso(-50)))
        tlog.append_event(mk_open("2026-04-05_bcd_void", premium=-100.0,
                                  opened=_iso(-90)))
        tlog.append_event({"id": "2026-04-05_bcd_void", "event": "void",
                           "timestamp": f"{_iso(-89)}T10:00:00-04:00", "reason": "test"})

    def tearDown(self) -> None:
        tlog.TRADE_LOG_FILE = self.orig_log
        self.mig.ROOT = self._orig_root

    def test_backfill_groups_dual_position_into_first_campaign(self) -> None:
        rc = self.mig.main(["--apply"])
        self.assertEqual(rc, 0)
        resolved = {t["id"]: t for t in tlog.resolve_log()}
        for tid in ("2026-06-05_bcd_001", "2026-06-05_bcd_002"):
            o = resolved[tid]["open"]
            self.assertEqual(o["campaign_id"], "2026-06-05_bcd_001")
            self.assertEqual(len(o["legs"]), 2)
            sides = {leg["side"] for leg in o["legs"]}
            self.assertEqual(sides, {"short", "long"})
            long_leg = next(l for l in o["legs"] if l["side"] == "long")
            self.assertEqual(long_leg["expiry"], self.long_exp)   # closed_trades 回捞
            self.assertEqual(o["long_expiry"], self.long_exp)
        # 非 BCD 不动
        self.assertNotIn("campaign_id", resolved["2026-05-14_bps_001"]["open"])
        # campaign 聚合：双仓 = 一个 campaign，closed，含 discretionary close
        camps = [c for c in build_campaigns(tlog.resolve_log())
                 if c["strategy_key"] == "bull_call_diagonal"]
        self.assertEqual(len(camps), 1)
        c = camps[0]
        self.assertEqual(sorted(c["members"]),
                         ["2026-06-05_bcd_001", "2026-06-05_bcd_002"])
        self.assertEqual(c["status"], "closed")
        exp_realized = 2 * (-411.0 - (-440.0)) * 100
        self.assertAlmostEqual(c["realized_usd"], exp_realized, places=2)

    def test_migration_is_idempotent(self) -> None:
        self.mig.main(["--apply"])
        n_before = len(tlog.load_log())
        self.mig.main(["--apply"])
        self.assertEqual(len(tlog.load_log()), n_before,
                         "second --apply must append nothing")

    def test_dry_run_writes_nothing(self) -> None:
        n_before = len(tlog.load_log())
        self.mig.main([])
        self.assertEqual(len(tlog.load_log()), n_before)


# ── Performance 页 campaign 口径 ─────────────────────────────────────────────

class PerformanceCampaignTests(unittest.TestCase):
    def test_campaign_counts_as_one_trade_with_roll_income(self) -> None:
        from performance.live import compute_live_performance
        prem1, prem2 = -411.0, -415.0
        exit1, exit2 = -440.0, -445.0
        roll_net = 30.0 - 5.0
        events = [
            mk_open("C1", premium=prem1, campaign_id="C1", opened=_iso(-30)),
            mk_open("C2", premium=prem2, account="etrade", campaign_id="C1",
                    opened=_iso(-30)),
            mk_roll("C1", 1, close_price=5.0, open_price=30.0, old_strike=7700,
                    old_expiry=_iso(10), new_strike=7900, new_expiry=_iso(45),
                    when=_iso(-15), campaign_id="C1"),
            mk_close("C1", exit_premium=exit1, entry_premium=prem1, when=_iso(-2)),
            mk_close("C2", exit_premium=exit2, entry_premium=prem2, when=_iso(-1)),
        ]
        perf = compute_live_performance(resolved_from_events(events))
        self.assertEqual(perf["summary"]["closed_trades"], 1)   # campaign 为单元
        exp_pnl = ((prem1 - exit1) + (prem2 - exit2)) * 100 + roll_net * 100
        self.assertAlmostEqual(perf["summary"]["total_realized_pnl"], exp_pnl, places=2)
        row = perf["recent_closed"][0]
        self.assertEqual(row["id"], "C1")
        self.assertIn("campaign", row)
        self.assertEqual(row["campaign"]["n_rolls"], 1)
        self.assertAlmostEqual(row["campaign"]["roll_income_usd"], roll_net * 100, places=2)

    def test_partially_closed_campaign_stays_out_of_closed_stats(self) -> None:
        from performance.live import compute_live_performance
        events = [
            mk_open("P1", premium=-411.0, campaign_id="P1", opened=_iso(-30)),
            mk_open("P2", premium=-415.0, account="etrade", campaign_id="P1",
                    opened=_iso(-30)),
            mk_close("P1", exit_premium=-440.0, entry_premium=-411.0, when=_iso(-1)),
        ]
        perf = compute_live_performance(resolved_from_events(events))
        self.assertEqual(perf["summary"]["closed_trades"], 0)
        self.assertEqual(perf["summary"]["open_trades"], 1)   # P2 仍开

    def test_legacy_trades_unchanged(self) -> None:
        """零 campaign/roll 的 resolved 集合 → 与旧口径完全一致（同 fixture 独立算术）."""
        from performance.live import compute_live_performance
        rng = random.Random(9)
        events, exp = [], []
        for i in range(4):
            prem = round(rng.uniform(2, 9), 2)
            exit_p = round(rng.uniform(0.5, prem), 2)
            n = rng.randint(1, 3)
            tid = f"G{i}"
            events.append(mk_open(tid, premium=prem, contracts=n,
                                  strategy_key="bull_put_spread",
                                  opened=_iso(-20 + i)))
            events.append(mk_close(tid, exit_premium=exit_p, entry_premium=prem,
                                   contracts=n, when=_iso(-10 + i)))
            exp.append((prem - exit_p) * 100 * n)
        perf = compute_live_performance(resolved_from_events(events))
        self.assertEqual(perf["summary"]["closed_trades"], len(exp))
        self.assertAlmostEqual(perf["summary"]["total_realized_pnl"], sum(exp), places=2)
        wins = [p for p in exp if p > 0]
        self.assertAlmostEqual(perf["summary"]["win_rate"], len(wins) / len(exp), places=4)
        for row in perf["recent_closed"]:
            self.assertNotIn("campaign", row)


# ── resolver roll_void 语义 ──────────────────────────────────────────────────

class RollVoidResolutionTests(unittest.TestCase):
    def test_roll_void_drops_roll_from_resolution(self) -> None:
        events = [
            mk_open("V1", premium=-400.0, opened=_iso(-20)),
            mk_roll("V1", 1, close_price=5.0, open_price=30.0, old_strike=7700,
                    old_expiry=_iso(10), new_strike=7900, new_expiry=_iso(45)),
            {"id": "V1", "event": "roll_void", "roll_id": "V1_roll_1",
             "timestamp": f"{_iso(-5)}T10:06:00-04:00", "reason": "atomic rollback"},
            mk_roll("V1", 2, close_price=4.0, open_price=20.0, old_strike=7700,
                    old_expiry=_iso(10), new_strike=7950, new_expiry=_iso(50),
                    when=_iso(-4)),
        ]
        resolved = resolved_from_events(events)
        rolls = resolved[0]["rolls"]
        self.assertEqual(len(rolls), 1)
        self.assertEqual(rolls[0]["roll_id"], "V1_roll_2")
        # roll income 只含幸存 roll
        self.assertAlmostEqual(trade_roll_income_usd(resolved[0]), (20.0 - 4.0) * 100,
                               places=2)

    def test_current_short_leg_follows_last_surviving_roll(self) -> None:
        events = [
            mk_open("V2", premium=-400.0, opened=_iso(-20), short_strike=7700,
                    expiry=_iso(10)),
            mk_roll("V2", 1, close_price=5.0, open_price=30.0, old_strike=7700,
                    old_expiry=_iso(10), new_strike=7900, new_expiry=_iso(45)),
        ]
        resolved = resolved_from_events(events)
        cur = current_short_leg(resolved[0])
        self.assertEqual(cur["strike"], 7900)
        self.assertEqual(cur["expiry"], _iso(45))
        self.assertEqual(cur["entry_price"], 30.0)


if __name__ == "__main__":
    unittest.main()
