"""Q042 Walk-Forward Backtest Engine (F8)

Simulates dual-sleeve directional overlay from 2007-01-01 to 2026-05-10.

Design:
  Trigger detection uses the research methodology exactly
  (find_triggers_ddath + apply_no_overlap), so AC21 reproduces research counts.
  P&L calculation uses walk-forward pricing.

  Sleeve A: ddATH ≤ -4%, no MA filter, T+1 open, DTE/width from
            strategy.q042_sizing（SPEC-094.5 起 ATM/+5%, DTE 30——参数不再 mirror）.
  Sleeve B: SPEC-094.7 阶梯 {-15,-25,-35,-45}% touch 即 fire（reclaim 已删）；
            浅档 -15% → ATM/+5% spread D90，深档 ≤-25% → ITM85 LEAP D730
            （SPX-equiv 尺度; 生产走 XSP）。
  Both:     10% account sizing (account_pct 显示口径), hold to expiry.

Acceptance criteria:
  AC21 (SPEC-094 验收时点冻结, 当时参数 ATM/+5%/D90): Sleeve A n=25 win 64%
    +99%/19y maxDD -16.3%; Sleeve B n=5 win 100% +41%. 后续参数变更
    (094.1/094.5) 使这些参考值成为历史验收记录; 活体校验 =
    tests/test_spec_094_5.py 金行 + 信号流对齐。
  AC22: Outputs data/q042_backtest_trades.csv（SPEC-094.6 起 untracked 运行时
    工件——再生跑本引擎, 两机各自落盘, 不进 git）
  AC23: Outputs combined daily BP series (included in BacktestResult)

Run with: python -m backtest.q042_engine [--start 2007-01-01] [--end <today>]
"""

from __future__ import annotations

import argparse
import csv
import pickle
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SPX_PKL = REPO_ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO_ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
TRADES_CSV = REPO_ROOT / "data" / "q042_backtest_trades.csv"

# SPEC-094.5: 结构参数唯一真值源 = strategy.q042_sizing（no-param-mirror——
# 本文件此前 mirror 了 0.025，094.5 改宽度时若忘改这里，dashboard 回测将
# 静默展示旧结构）。
from strategy.q042_sizing import (  # noqa: E402
    _DTE_A, _DTE_B, _OTM_PCT_A as _OTM_A, _OTM_PCT_B as _OTM_B,
)

_SIZING_PCT = 0.10
_NLV_SEED   = 100_000.0
_MA10_WIN   = 10
_WATCH_DAYS = 30   # trading days for Sleeve B MA10 reclaim window


# ── Pricing ───────────────────────────────────────────────────────────────────

def _term_mult(dte: int) -> float:
    if dte <= 45:  return 1.10
    if dte <= 120: return 1.00
    return 0.95

def _skew_mult(m: float) -> float:
    if m >= 1.0: return 1.0 - 1.5 * min(m - 1.0, 0.10)
    return 1.0 + 1.5 * min(1.0 - m, 0.10)

def _bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    # SPEC-119: delegates to the unified pricing core (same scipy CDF, same
    # T-in-years / r=4% / q=0 conventions → bit-identical to the old inline copy).
    from pricing import core as _core
    return float(_core.call_price(S, K, T, sigma, r, q=0.0))

def _price_leap(S: float, K: float, vix: float, dte: int) -> float:
    """SPEC-094.7 深档 ITM LEAP（SPX-equiv per-share；σ=VIX×0.875 括号中点，
    q=1.6%——与 strategy.q042_sizing.compute_leap_sizing est 同convention）。"""
    from pricing import core as _core
    from strategy.q042_sizing import _B_LEAP_VOL_MULT
    sigma = max(vix * _B_LEAP_VOL_MULT / 100.0, 0.01)
    return float(_core.call_price(S, K, dte / 365.0, sigma, 0.045, q=0.016))


def _price_spread(S: float, K_long: float, K_short: float, vix: float, dte: int) -> float:
    T = dte / 365.0
    sigma_atm = max(vix / 100.0, 0.10) * _term_mult(dte)
    p_long  = _bs_call(S, K_long,  T, sigma_atm * _skew_mult(K_long  / S))
    p_short = _bs_call(S, K_short, T, sigma_atm * _skew_mult(K_short / S))
    return max(0.0, p_long - p_short)


# ── Trade record ──────────────────────────────────────────────────────────────

@dataclass
class Q042Trade:
    sleeve_id: str
    signal_date: str
    entry_date: str
    exit_date: str
    ath_at_signal: float
    ddath_at_signal: float
    long_strike: float
    short_strike: float
    contracts: float
    debit_per_share: float
    exit_pnl: float
    account_pct: float
    win: bool
    status: str = "CLOSED"  # "CLOSED" (expired) or "OPEN" (in-flight at backtest end, MTM)
    instrument: str = "SPREAD"     # SPEC-094.7: SPREAD | XSP_LEAP（CSV 尺度为 SPX-equiv）
    rung: Optional[float] = None   # SPEC-094.7: B 阶梯档位


@dataclass
class DailyRow:
    date: str
    sleeve_a_bp_pct: float
    sleeve_b_bp_pct: float
    combined_bp_pct: float
    account_equity: float


@dataclass
class BacktestResult:
    trades_a: list[Q042Trade]
    trades_b: list[Q042Trade]
    daily_rows: list[DailyRow]

    @property
    def all_trades(self) -> list[Q042Trade]:
        return self.trades_a + self.trades_b


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_history(start: str, end: str) -> pd.DataFrame:
    try:
        spx = pickle.loads(SPX_PKL.read_bytes())
        vix = pickle.loads(VIX_PKL.read_bytes())
    except FileNotFoundError:
        import yfinance as yf
        spx = yf.Ticker("^GSPC").history(period="max", interval="1d")[["Open", "High", "Low", "Close"]]
        vix = yf.Ticker("^VIX").history(period="max", interval="1d")[["Close"]]

    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    spx.columns = [c.lower() for c in spx.columns]
    spx["vix"] = vix["Close"]
    spx = spx.loc[start:end].copy()
    spx["vix"] = spx["vix"].ffill()
    spx.dropna(subset=["close", "open"], inplace=True)
    return spx


# ── Trigger detection ─────────────────────────────────────────────────────────
# SPEC-094.5: raw-crossing + no-overlap 的本地重实现已删除——它与 production
# 状态机存在 armed-闩锁语义差（漏到期日再触发）。信号流见 run_backtest Step 1
# （signals.q042_trigger.get_q042_history）。冻结的研究方法学副本保留在
# research/q062/q062_tier1_structure_scan.py。


# ── Position tracker ──────────────────────────────────────────────────────────

@dataclass
class _ActivePos:
    sleeve_id: str
    signal_date: str
    entry_date: str
    ath_at_signal: float
    ddath_at_signal: float
    long_strike: float
    short_strike: float
    debit_per_share: float
    contracts: float
    expiry_date: str
    account_at_entry: float
    instrument: str = "SPREAD"
    rung: Optional[float] = None


# ── Main walk-forward ─────────────────────────────────────────────────────────

def run_backtest(start: str = "2007-01-01", end: str = "2026-05-10") -> BacktestResult:
    df  = _load_history(start, end)
    idx = df.index
    ma10 = df["close"].rolling(_MA10_WIN).mean()
    ath  = df["close"].cummax()
    ddath = df["close"] / ath - 1.0

    # ── Step 1: trigger streams from the LIVE state machine ──────────────────
    # SPEC-094.5: 本引擎原自带一份 raw-crossing + no-overlap 重实现，与
    # production 状态机存在语义差——armed 在持仓期内闩锁（条件持续满足时
    # 仓位到期日立即再 fire），重实现把持仓期内穿越直接丢弃，历史上漏
    # 2007-11-19 / 2015-12-14 两笔到期日再触发。信号流唯一真值源 =
    # signals.q042_trigger.get_q042_history（与 executor 同一状态机）。
    from signals.q042_trigger import get_q042_history
    entries_a, entries_b = get_q042_history(df, start=start, end=end)
    sig_a_set = {pd.Timestamp(e["signal_date"]) for e in entries_a}
    # SPEC-094.7: B 阶梯——按日期聚合（gap 崩盘单日可多档），保留 rung/instrument/dte
    sig_b_map: dict = {}
    for e in entries_b:
        sig_b_map.setdefault(pd.Timestamp(e["signal_date"]), []).append(e)

    # ── Step 2: walk-forward pricing and P&L ─────────────────────────────────
    active_a: Optional[_ActivePos] = None
    active_b: dict = {}                     # SPEC-094.7: rung → _ActivePos（并发）
    trades_a: list[Q042Trade] = []
    trades_b: list[Q042Trade] = []
    daily_rows: list[DailyRow] = []
    account = _NLV_SEED

    def _exp_date(signal_str: str, dte: int) -> str:
        # SPEC-094.5: expiry 锚点 = signal + 1 自然日 + DTE —— 与 production 逐位
        # 一致（executor: entry_date = today+1 calendar, expiry = entry+DTE；
        # signals.q042_trigger.get_q042_history 同）。此前用"交易日 entry + DTE"，
        # 周五信号比 production 晚到期 2 天，挡掉到期日再触发（2007-11-19 类）。
        # R-20260510-15 的本意（expiry 从 entry 起算而非 signal 起算）保持不变。
        return (datetime.strptime(signal_str, "%Y-%m-%d")
                + timedelta(days=1 + dte)).strftime("%Y-%m-%d")

    def _maybe_expire(pos: Optional[_ActivePos], trades: list, today: str, close: float) -> Optional[_ActivePos]:
        if pos is None or today < pos.expiry_date:
            return pos
        if pos.instrument == "XSP_LEAP":
            pnl_ps = max(0.0, close - pos.long_strike) - pos.debit_per_share
        else:
            long_payoff  = max(0.0, close - pos.long_strike)
            short_payoff = max(0.0, close - pos.short_strike)
            pnl_ps = long_payoff - short_payoff - pos.debit_per_share  # per share, net
        pnl    = pnl_ps * 100 * pos.contracts                      # total dollar P&L
        # account_pct matches research: (pnl_pct_debit / 100) * sizing_pct * 100
        # = pnl_ps / debit_per_share * sizing_pct
        pct    = (pnl_ps / pos.debit_per_share) * _SIZING_PCT
        trades.append(Q042Trade(
            sleeve_id=pos.sleeve_id, signal_date=pos.signal_date,
            entry_date=pos.entry_date, exit_date=today,
            ath_at_signal=pos.ath_at_signal, ddath_at_signal=pos.ddath_at_signal,
            long_strike=pos.long_strike, short_strike=pos.short_strike,
            contracts=pos.contracts, debit_per_share=pos.debit_per_share,
            exit_pnl=round(pnl, 2), account_pct=round(pct, 4), win=pnl_ps > 0,
            instrument=pos.instrument, rung=pos.rung,
        ))
        return None

    def _enter(sleeve_id: str, signal_dt, i: int,
               meta: Optional[dict] = None) -> Optional[_ActivePos]:
        if i + 1 >= len(df): return None
        next_row = df.iloc[i + 1]
        S_entry   = float(next_row["open"])
        sig_close = float(df.iloc[i]["close"])
        vix_val   = float(df.iloc[i]["vix"]) if not pd.isna(df.iloc[i]["vix"]) else 20.0
        ath_val   = float(ath.iloc[i])
        dd_val    = float(ddath.iloc[i])
        instrument = (meta or {}).get("instrument", "SPREAD")
        rung = (meta or {}).get("rung")
        if instrument == "XSP_LEAP":
            # SPEC-094.7 深档：SPX-equiv 尺度（K 按 XSP $1 粒度 ×10 对齐生产取整）
            from strategy.q042_sizing import _B_LEAP_K_RATIO, _XSP_SCALE
            dte = int((meta or {}).get("dte", 730))
            K_long  = float(round(sig_close * _B_LEAP_K_RATIO / _XSP_SCALE) * _XSP_SCALE)
            K_short = 0.0
            debit_ps = _price_leap(S_entry, K_long, vix_val, dte)
        else:
            dte = _DTE_A if sleeve_id == "A" else int((meta or {}).get("dte", _DTE_B))
            otm = _OTM_A if sleeve_id == "A" else _OTM_B
            K_long    = float(round(sig_close / 5) * 5)
            K_short   = float(round(sig_close * (1 + otm) / 5) * 5)
            debit_ps  = _price_spread(S_entry, K_long, K_short, vix_val, dte)
        if debit_ps <= 0: return None
        # Use fractional contracts (1.0) — research does not filter by affordability.
        # P&L is computed as % of debit (research methodology), so integer contracts
        # are not needed for metric reproduction.
        return _ActivePos(
            sleeve_id=sleeve_id,
            signal_date=signal_dt.strftime("%Y-%m-%d"),
            entry_date=df.index[i + 1].strftime("%Y-%m-%d"),
            ath_at_signal=ath_val, ddath_at_signal=dd_val,
            long_strike=K_long, short_strike=K_short,
            debit_per_share=debit_ps, contracts=1.0,
            expiry_date=_exp_date(signal_dt.strftime("%Y-%m-%d"), dte),
            account_at_entry=_NLV_SEED,
            instrument=instrument, rung=rung,
        )

    for i, (dt, row) in enumerate(df.iterrows()):
        today_str = dt.strftime("%Y-%m-%d")
        close = float(row["close"])
        vix   = float(row["vix"]) if not pd.isna(row["vix"]) else 20.0

        active_a = _maybe_expire(active_a, trades_a, today_str, close)
        for rk in list(active_b):
            active_b[rk] = _maybe_expire(active_b[rk], trades_b, today_str, close)
            if active_b[rk] is None:
                del active_b[rk]

        # Enter on signal dates (positions must be closed — no-overlap already guaranteed)
        if dt in sig_a_set and active_a is None:
            active_a = _enter("A", dt, i)

        for meta in sig_b_map.get(dt, []):
            if meta["rung"] not in active_b:
                pos = _enter("B", dt, i, meta)
                if pos is not None:
                    active_b[meta["rung"]] = pos

        bp_a = (active_a.debit_per_share * 100 * active_a.contracts / account * 100
                if active_a else 0.0)
        bp_b = sum(p.debit_per_share * 100 * p.contracts / account * 100
                   for p in active_b.values())
        daily_rows.append(DailyRow(
            date=today_str,
            sleeve_a_bp_pct=round(bp_a, 2),
            sleeve_b_bp_pct=round(bp_b, 2),
            combined_bp_pct=round(bp_a + bp_b, 2),
            account_equity=round(account, 2),
        ))

    # ── Step 3: mark in-flight positions as OPEN (mark-to-market) ─────────────
    # Trades whose expiry > backtest end never trip _maybe_expire. Without this
    # step they vanish from the CSV — see RESEARCH_LOG R-20260510-11.
    end_dt = df.index[-1]
    end_str = end_dt.strftime("%Y-%m-%d")
    end_close = float(df.iloc[-1]["close"])
    end_vix = float(df.iloc[-1]["vix"]) if not pd.isna(df.iloc[-1]["vix"]) else 20.0

    def _record_open(pos: Optional[_ActivePos], trades: list) -> None:
        if pos is None:
            return
        expiry_dt = datetime.strptime(pos.expiry_date, "%Y-%m-%d")
        dte_remaining = max(1, (expiry_dt - end_dt).days)
        if pos.instrument == "XSP_LEAP":
            mtm_ps = _price_leap(end_close, pos.long_strike, end_vix, dte_remaining)
        else:
            mtm_ps = _price_spread(end_close, pos.long_strike, pos.short_strike, end_vix, dte_remaining)
        pnl_ps = mtm_ps - pos.debit_per_share
        pnl = pnl_ps * 100 * pos.contracts
        pct = (pnl_ps / pos.debit_per_share) * _SIZING_PCT
        trades.append(Q042Trade(
            sleeve_id=pos.sleeve_id, signal_date=pos.signal_date,
            entry_date=pos.entry_date, exit_date=end_str,
            ath_at_signal=pos.ath_at_signal, ddath_at_signal=pos.ddath_at_signal,
            long_strike=pos.long_strike, short_strike=pos.short_strike,
            contracts=pos.contracts, debit_per_share=pos.debit_per_share,
            exit_pnl=round(pnl, 2), account_pct=round(pct, 4),
            win=pnl_ps > 0, status="OPEN",
            instrument=pos.instrument, rung=pos.rung,
        ))

    _record_open(active_a, trades_a)
    for pos in active_b.values():
        _record_open(pos, trades_b)

    return BacktestResult(trades_a=trades_a, trades_b=trades_b, daily_rows=daily_rows)


# ── Output & metrics ──────────────────────────────────────────────────────────

def _metrics(trades: list[Q042Trade], years: float) -> dict:
    # AC21 reproduction: count and win-rate use CLOSED trades only
    # (OPEN positions are MTM snapshots, not realized outcomes).
    closed = [t for t in trades if t.status == "CLOSED"]
    open_trades = [t for t in trades if t.status == "OPEN"]
    if not closed:
        return {"n": 0, "n_open": len(open_trades)}
    wins  = [t for t in closed if t.win]
    total_pnl_pct = sum(t.account_pct for t in closed) * 100
    equity = [1.0]
    for t in closed:
        equity.append(equity[-1] * (1 + t.account_pct))
    peak = 1.0; max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak)
    return {
        "n": len(closed),
        "n_open": len(open_trades),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1),
        "total_pnl_pct": round(total_pnl_pct, 1),
        "annualized_pct": round(total_pnl_pct / years, 2),
        "max_dd_pct": round(max_dd * 100, 1),
    }


def write_trades_csv(result: BacktestResult) -> None:
    TRADES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with TRADES_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "sleeve_id", "signal_date", "entry_date", "exit_date",
            "ath_at_signal", "ddath_at_signal",
            "long_strike", "short_strike", "contracts",
            "debit_per_share", "exit_pnl", "account_pct", "status",
            "instrument", "rung",       # SPEC-094.7（旧消费方按列名读，尾插安全）
        ])
        for t in result.all_trades:
            w.writerow([
                t.sleeve_id, t.signal_date, t.entry_date, t.exit_date,
                round(t.ath_at_signal, 2), round(t.ddath_at_signal, 4),
                int(t.long_strike), int(t.short_strike), round(t.contracts, 0),
                round(t.debit_per_share, 4), round(t.exit_pnl, 2), round(t.account_pct, 4),
                t.status,
                t.instrument, ("" if t.rung is None else t.rung),
            ])
    print(f"  wrote {TRADES_CSV}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Q042 walk-forward backtest")
    # 默认全窗口到今天：2026-07-11 一次 ad-hoc 短 --start 调用把 old Air 的
    # CSV 刷成 2 行（dashboard 残表）。默认值必须产出完整诚实的表。
    p.add_argument("--start", default="2007-01-01")
    p.add_argument("--end",   default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()
    print(f"running Q042 backtest {args.start} → {args.end} …")
    result = run_backtest(args.start, args.end)
    years = (datetime.strptime(args.end, "%Y-%m-%d") - datetime.strptime(args.start, "%Y-%m-%d")).days / 365.25
    print(f"\n── Sleeve A ──")
    for k, v in _metrics(result.trades_a, years).items():
        print(f"  {k}: {v}")
    print(f"\n── Sleeve B ──")
    for k, v in _metrics(result.trades_b, years).items():
        print(f"  {k}: {v}")
    write_trades_csv(result)
    print(f"\nAC22 trades CSV: {TRADES_CSV}")
    print(f"AC23 daily BP rows: {len(result.daily_rows)}")
