# SPEC-116 Developer Handoff — Q085 S2-BPS Paper Sleeve

**读我**: 规格与 AC 见 `task/SPEC-116.md`。本 SPEC 纯增量（新文件 + 一个 plist），不改任何现有策略文件（AC-6 有 bit-identical 断言）。参考实现真值在 `research/q085/`，冻结测试向量在本文末尾。

## 新文件清单

```
strategy/q085_s2bps_signal.py       # 信号判定（point-in-time）
notify/q085_s2bps_paper.py          # 16:50 ET 每日任务（skew 监控 + paper 生命周期 + Telegram）
data/q085_skew_monitor.jsonl        # 每日 skew 测量（append-only）
data/q085_paper_log.jsonl           # paper ledger（open/close 事件，append-only）
~/Library/LaunchAgents/com.spxstrat.q085_s2bps.plist   # 16:50 ET Mon-Fri（oldair）
```

## strategy/q085_s2bps_signal.py 要点

```python
def wilder_rsi(closes: list[float], n: int = 2) -> float:
    # 与 research/q085/q085_battery_lib.py 一致：ewm(alpha=1/n) Wilder 平滑
    ...

def oversold_composite(closes: list[float]) -> dict:
    """closes = 按日升序的 SPX 收盘序列（含今日，>= 260 根做 RSI 预热）。
    返回 {"rsi2": float, "down3": bool, "oversold": bool}
    oversold = (rsi2 < 10.0) or down3
    down3 = 最近三根连续收跌（c[-1]<c[-2]<c[-3]... 注意是逐日下跌非累计）"""

def signal_day(spx_closes, vix_close: float, regime: str, strategy_key: str | None) -> dict:
    """四条件与判定明细。regime/strategy_key 由调用方传入——
    取值来源必须与 Telegram bot 每日推荐使用的同一条管线调用
    （bot 侧现成的 recommendation payload 里有 regime 与 strategy_key），
    禁止在本模块内另起一套 VIX/regime 计算（防口径漂移）。"""
    return {
        "oversold": ..., "regime_ok": regime == "NORMAL",
        "blocked": not strategy_key, "layer1_ok": vix_close < 35.0,
        "signal": all([...]),
    }
```

SPX 收盘序列来源：与生产一致的 `signals.trend.fetch_spx_history()`（研究侧确认其 close 与 q085 OHLC cache 一致）。

## notify/q085_s2bps_paper.py 要点

```python
CHAIN_DIR = ROOT / "data" / "q041_chains"
SKEW_OUT  = ROOT / "data" / "q085_skew_monitor.jsonl"
LEDGER    = ROOT / "data" / "q085_paper_log.jsonl"
STOP_X, EXIT_DTE = 3.0, 21

def load_today_chain(date_str):
    df = pd.read_parquet(CHAIN_DIR / date_str / "SPX.parquet")
    return df[(df.option_type == "PUT") & df.iv.notna() & (df.iv > 1)]

def measure_skew(puts, vix):  # 每日
    p = puts[(puts.dte >= 25) & (puts.dte <= 35)].assign(ad=lambda x: x.delta.abs())
    def leg(t): return float(p.iloc[(p.ad - t).abs().argsort()[:3]].iv.mean())
    row = {"date": ..., "vix": vix, "atm_iv": leg(0.50), "d30_iv": leg(0.30), "d15_iv": leg(0.15)}
    row |= {"d30_off": round(row["d30_iv"] - vix, 2), ...}
    # strict-JSON: json.dumps 前断言无 NaN/Inf（math.isfinite 全字段）

def build_paper_bps(puts):    # 仅信号日
    # expiry: puts.dte 最接近 30 的到期；在该到期内取 |delta| 最近 0.30 / 0.15 两腿
    # 记录: strikes、两腿 bid/ask/mid、credit_mid = mid_s - mid_l、
    #       credit_natural = bid_s - ask_l、iv 两腿、dte、entry_spx（chain close 列）、
    #       overlap_main_bps = 主 sleeve 当日是否在场（读 strategy/state.py 持仓）

def manage_open_positions(puts, today):   # 每天
    # 对 ledger 内未平仓记录：同 expiry 同 strikes 取当日报价
    #   cost_mid >= STOP_X * credit_mid -> close(reason="stop")
    #   dte <= EXIT_DTE                 -> close(reason="expiry_rule")
    # close 事件: pnl_mid, pnl_natural, hold_days, vix_max_during, breach(close<ks), reason

def degradation_note(ledger):  # 每次 close 后
    # trailing 10 笔 pnl_mid 和；累计 pnl_mid；<0 / <=-5000 -> Telegram WARNING 注记（不停机）
```

时序：先 A（skew，无条件）→ C（管理开仓）→ 判定 B（新信号开仓）→ D/E。当日链快照缺失 → Telegram 报 `missing_chain` 并跳过（不要静默吞掉，SPEC-114 的 sanity 会另行报警）。

## plist

模板照抄 `com.spxstrat.q041_t2_paper_signals`，时间 16:50 ET Mon-Fri，label `com.spxstrat.q085_s2bps`，日志 `logs/q085_s2bps.log`。

## 冻结测试向量（AC-1 / AC-7）

由 `research/q085/q085_p3b_era_conditional.py` 的 challenger mask 生成（regime/blocked 取自 `research/q078/_signal_history_cache.csv` 对应日）：

正例（signal_day 应为 True）:
2024-01-17, 2024-04-12, 2024-04-15, 2024-05-29, 2024-07-24, 2024-12-17,
2025-01-10, 2025-02-26, 2025-03-26, 2025-06-20, 2025-08-01, 2025-11-13

反例（应为 False，括号注明死因）:
2024-03-14(未超卖), 2024-08-05(HIGH_VOL regime), 2024-11-06(放行日非 blocked),
2025-04-07(VIX>35 Layer-1), 2024-06-12(未超卖), 2024-10-15(放行日),
2025-04-10(HIGH_VOL), 2024-02-13(超卖但放行), 2025-07-01(未超卖),
2024-09-06(超卖但 HIGH_VOL), 2025-05-14(未超卖), 2024-12-30(未超卖)

⚠️ 实现完成后请先用 `_signal_history_cache.csv` 独立复核这 24 个向量再写死进测试——若与 cache 不符以 cache 为准并回报（研究侧手工转录可能有误，这本身是 AC-1 要抓的）。

## 部署核对

1. oldair `git pull` + `launchctl load`
2. 首日运行后核对：`q085_skew_monitor.jsonl` 有当日行、strict-JSON 通过、无 Telegram（除非恰逢信号日）
3. 回报 commit hash + 首日运行输出
