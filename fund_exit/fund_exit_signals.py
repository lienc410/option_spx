# -*- coding: utf-8 -*-
"""基金技术面分批清仓信号工具 (Strategy Spec v2)

定位：纪律 / 行为约束工具，非 alpha 择时、非投资建议。
详见 task/fund_exit_strategy_spec.md。

规则 v2（按优先级取首个命中）：
  ① 强势区   : 上升 且 距近60高 >= -STRONG          -> 纯持有(让利润奔跑, clip 0)
  ② 深套防砍底: 下降 且 距近60高 <= -DEEP            -> 等反弹/硬时限(clip 0)
  ③ 趋势转弱 : 下降 且 距近60高 > -DEEP             -> 主动减(受超卖否决)
  ④ 追踪止盈 : 现价 <= 滚动最高*(1-TRAIL)           -> 重仓出(仅近期赢家豁免超卖否决, runner地板)
  ⑤ 跌破MA20 : 震荡 且 MA20>MA60 且 现价<MA20        -> 止盈减(受超卖否决)
  ⑥ 其余     : -> 持有观察(保底量)

强势区纯持有(PM 风险偏好)：保底时钟只覆盖"非强势"仓。
超卖否决(RSI<30 或 20日新低)只挡 ③⑤，不挡 ④。
TRAIL 连续随波动缩放(σ-scaled, ~1σ 6周移动, clip 5-14%)。STRONG=3% / DEEP=15%。
趋势 band-hysteresis(±1%) 压日度 whipsaw。
"""
from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ── CJK 字体（macOS）：优先全覆盖的 Arial Unicode，避免简体缺字 ──────
for _path, _name in [("/Library/Fonts/Arial Unicode.ttf", "Arial Unicode MS"),
                     ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "Arial Unicode MS"),
                     ("/System/Library/Fonts/STHeiti Medium.ttc", "Heiti TC")]:
    try:
        font_manager.fontManager.addfont(_path)
        plt.rcParams["font.sans-serif"] = [_name]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

import akshare as ak

OUTDIR = Path(__file__).resolve().parent
DATA_DATE = "2026-05-31"

# ── 参数（PM 2026-05-31 敲定）─────────────────────────────────────
STRONG = 0.03          # (PM 2026-05-31: 强势区放宽为"全部上升趋势"持有, STRONG 不再用于持有判定, 保留供参考)
DEEP = 0.15            # 深套界
# 5.4 追踪止盈带：连续随基金自身波动缩放（取代旧两档先验 {high:0.10,low:0.06}）。
# trail = clip(TRAIL_Z · σ_日 · √TRAIL_HORIZON_D, FLOOR, CAP)
#       = clip( 1σ 的 ~6 周移动 , 5%, 14% )
TRAIL_Z = 1.0              # 标准差倍数
TRAIL_HORIZON_D = 30       # 约 6 周（30 交易日）的移动
TRAIL_FLOOR, TRAIL_CAP = 0.05, 0.14   # 经济护栏：任何基金不在 <5% 噪音里出、不给回 >14%
TRAIL_DEFAULT = 0.08      # 波动样本不足时的兜底带
# 5.6 趋势 band-hysteresis：现价在 MA20 ±TREND_BAND 内视为"贴线"（不判方向），压日度 whipsaw
TREND_BAND = 0.01
# 5.3 ④豁免超卖否决仅限"近期赢家(runner)"：近 RUNNER_LOOKBACK 交易日内 ≥ RUNNER_MIN_DAYS
# 天为上升(=真的被趋势性纯持有过)。经济意义：④豁免否决的理由是"赢家无其它出场地板"；
# 非赢家(慢性下跌)从震荡触发④、又在超卖中卖=砸底，应同受否决。崩盘会在数日内 上升→下降，
# 短窗仍有多天上升→保住真赢家地板；而单日 MA razor-thin 穿越(噪音)凑不够天数→不豁免。
RUNNER_LOOKBACK = 15
RUNNER_MIN_DAYS = 5
MA_SHORT, MA_LONG = 20, 60
ROLL_HIGH_WIN = 250    # 滚动最高窗口（次新基用全可用历史）
HIGH60_WIN = 60
RSI_PERIOD = 14
LOW_WIN = 20           # 超卖否决：N 日新低
MONTHLY_FLOOR = 0.10   # 保底月清仓速度（仅非强势仓）
DEEP_LIMIT = "6-8周"

# clip 档位（占该只仓位的建议月卖出比例）
CLIP = {1: 0.00, 2: 0.00, 3: 0.25, 4: 0.40, 5: 0.15, 6: MONTHLY_FLOOR, 0: MONTHLY_FLOOR}

# ── 持仓清单（去重 10 只，2026-05-31，中信证券 App）──────────────
HOLDINGS = [
    # name, code, market_value, pnl_pct, vol_bucket
    ("华夏卓越成长混合",     "024930", 152086.10,  0.52, "high"),
    ("睿远成长价值混合A",    "007119", 141325.43,  0.69, "low"),
    ("华夏红利价值混合",     "024915", 136386.96, -0.19, "low"),
    ("工银圆兴混合",         "009076", 133813.91,  0.12, "low"),
    ("中信保诚前瞻优势混合", "013610", 103306.75,  0.01, "low"),
    ("华安研究智选混合A",    "011692",  93525.56, -0.08, "low"),
    ("中欧医疗健康混合",     "003095",  50730.79, -0.56, "high"),
    ("朱雀产业智选混合",     "007880",  42118.97, -0.17, "high"),
    ("华夏兴阳一年持有混合", "009010",  32060.03, -0.54, "high"),
    ("泓德卓远混合A",        "010864",  22936.78, -0.11, "low"),
]
# 009010 华夏兴阳一年持有: 2021-01-04 申购 → ~2022-01 满1年持有期 → 已解锁, 现可自由赎回。
# 原"锁定"警告已移除(假约束)。若未来近12个月内有新增申购批次, 该批会重新锁1年, 届时再加回。
LOCKED = {}

ACTION_TEXT = {
    1: "①上升趋势：让利润奔跑，纯持有",
    2: f"②深套防砍底：勿砍底，待反弹至阻力/MA20，硬时限{DEEP_LIMIT}",
    3: "③趋势转弱：主动分批减仓",
    4: "④追踪止盈/止损触发：减仓（runner出场）",
    5: "⑤跌破MA20：动能转弱，止盈减仓",
    6: "⑥持有观察，不为卖而卖（保底量）",
    0: "数据不足：仅保底量，指标待补",
}


# ── 工具函数 ─────────────────────────────────────────────────────
def fetch_nav(code: str, retries: int = 3, pause: float = 0.8) -> pd.DataFrame:
    """拉累计净值走势，retry + 升序。失败抛异常由上层隔离。"""
    last = None
    for i in range(retries):
        try:
            df = ak.fund_open_fund_info_em(symbol=code, indicator="累计净值走势")
            df = df.rename(columns={"净值日期": "date", "累计净值": "nav"})
            df["date"] = pd.to_datetime(df["date"])
            df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
            df = df.dropna(subset=["nav"]).sort_values("date").reset_index(drop=True)
            if len(df) == 0:
                raise ValueError("空返回")
            return df
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(pause * (i + 1))
    raise last


def rsi(nav: pd.Series, period: int = 14) -> float:
    if len(nav) <= period:
        return float("nan")
    delta = nav.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def _trend_label(latest, ma20, ma60) -> str:
    """趋势三态 + band-hysteresis（现价在 MA20 ±TREND_BAND 内=贴线，不判方向）。"""
    if pd.isna(ma20) or pd.isna(ma60):
        return "数据不足"
    if latest > ma20 * (1 + TREND_BAND) and ma20 > ma60:
        return "上升"
    if latest < ma20 * (1 - TREND_BAND) and ma20 < ma60:
        return "下降"
    return "震荡"


def fetch_market_regime() -> str:
    """沪深300 现价 vs MA60 → 上下文提示（不进决策, per 5.5）。"""
    try:
        idx = ak.stock_zh_index_daily(symbol="sh000300")
        idx = idx.sort_values("date").reset_index(drop=True)
        close = pd.to_numeric(idx["close"], errors="coerce").dropna()
        ma60 = close.tail(60).mean()
        last = close.iloc[-1]
        pct = last / ma60 - 1
        state = "强(>MA60)" if last > ma60 else "弱(<MA60)"
        return f"沪深300 {state} 距MA60 {pct:+.1%}"
    except Exception as e:  # noqa: BLE001
        return f"市场regime取数失败({type(e).__name__})"


def fetch_fee(code: str) -> str:
    """尽力取赎回费率，取不到留 App 核对（per 5.7）。"""
    try:
        df = ak.fund_individual_detail_info_xq(symbol=code)
        # 雪球详情含赎回费阶梯；结构不稳定 → 只做存在性提示
        txt = df.to_string()
        if "赎回" in txt:
            return "见App(雪球有费率, 结构不稳)"
        return "见App核对"
    except Exception:
        return "见App核对"


# ── 指标 + 规则引擎 ──────────────────────────────────────────────
@dataclass
class FundResult:
    name: str
    code: str
    mv: float
    pnl_pct: float
    bucket: str
    ok: bool = True
    err: str = ""
    latest: float = float("nan")
    latest_date: str = ""
    n: int = 0
    ma20: float = float("nan")
    ma60: float = float("nan")
    high60: float = float("nan")
    roll_high: float = float("nan")
    trail: float = float("nan")
    trail_trigger: float = float("nan")
    rsi: float = float("nan")
    low20: float = float("nan")
    ann_vol: float = float("nan")
    dist_ma20: float = float("nan")
    dist_ma60: float = float("nan")
    dist_high60: float = float("nan")
    trend: str = ""
    rule: int = 6
    action: str = ""
    clip: float = 0.0
    veto: bool = False
    was_runner: bool = False
    short_hist: bool = False
    df: pd.DataFrame = field(default=None, repr=False)


def analyze(name, code, mv, pnl_pct, bucket) -> FundResult:
    r = FundResult(name=name, code=code, mv=mv, pnl_pct=pnl_pct, bucket=bucket)
    try:
        df = fetch_nav(code)
    except Exception as e:  # noqa: BLE001
        r.ok = False
        r.err = f"{type(e).__name__}: {e}"
        return r

    r.df = df
    nav = df["nav"]
    n = len(df)
    r.n = n
    r.latest = float(nav.iloc[-1])
    r.latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d")
    r.short_hist = n < MA_LONG

    r.ma20 = float(nav.tail(MA_SHORT).mean()) if n >= MA_SHORT else float("nan")
    r.ma60 = float(nav.tail(MA_LONG).mean()) if n >= MA_LONG else float("nan")
    r.high60 = float(nav.tail(min(HIGH60_WIN, n)).max())
    r.roll_high = float(nav.tail(min(ROLL_HIGH_WIN, n)).max())
    r.low20 = float(nav.tail(min(LOW_WIN, n)).min())
    r.rsi = rsi(nav, RSI_PERIOD)
    rets = nav.pct_change().dropna()
    sigma_d = float(rets.tail(60).std()) if len(rets) >= 20 else float("nan")
    r.ann_vol = sigma_d * np.sqrt(252) if sigma_d == sigma_d else float("nan")

    # 5.4 追踪止盈带：连续随基金自身波动缩放（σ-scaled）。
    # 带宽 = TRAIL_Z·σ_日·√TRAIL_HORIZON_D = 1σ 的 ~6 周移动 →
    # 经济意义：回撤超过"正常 6 周波动"才算真反转、才出场。取代旧两档先验。
    if sigma_d == sigma_d:
        r.trail = float(np.clip(TRAIL_Z * sigma_d * np.sqrt(TRAIL_HORIZON_D),
                                TRAIL_FLOOR, TRAIL_CAP))
    else:
        r.trail = TRAIL_DEFAULT
    r.trail_trigger = r.roll_high * (1 - r.trail)
    r.dist_ma20 = r.latest / r.ma20 - 1 if r.ma20 == r.ma20 else float("nan")
    r.dist_ma60 = r.latest / r.ma60 - 1 if r.ma60 == r.ma60 else float("nan")
    r.dist_high60 = r.latest / r.high60 - 1 if r.high60 == r.high60 else float("nan")

    # 趋势三态 + 5.6 band-hysteresis（压日度 whipsaw，见 _trend_label）
    r.trend = _trend_label(r.latest, r.ma20, r.ma60)
    # 5.3 近期赢家(runner)判定：近 RUNNER_LOOKBACK 交易日内是否曾为"上升"(被纯持有)
    ma20s = nav.rolling(MA_SHORT).mean()
    ma60s = nav.rolling(MA_LONG).mean()
    up_days = sum(
        1 for i in range(max(0, n - RUNNER_LOOKBACK), n)
        if _trend_label(nav.iloc[i], ma20s.iloc[i], ma60s.iloc[i]) == "上升"
    )
    r.was_runner = up_days >= RUNNER_MIN_DAYS

    # 超卖否决：RSI<30 或 20日新低
    r.veto = (r.rsi == r.rsi and r.rsi < 30) or (r.latest <= r.low20)

    # ── 规则引擎（优先级）──
    rule = 6
    if r.trend == "上升":   # PM 2026-05-31: 全部上升趋势纯持有(让赢家跑), 不论距高
        rule = 1
    elif r.trend == "下降" and r.dist_high60 <= -DEEP:
        rule = 2
    elif r.trend == "下降":
        rule = 3
    elif r.latest <= r.trail_trigger:
        rule = 4
    elif r.trend == "震荡" and r.ma20 > r.ma60 and r.latest < r.ma20:
        rule = 5
    elif r.trend == "数据不足":
        rule = 0
    else:
        rule = 6

    r.rule = rule
    r.action = ACTION_TEXT[rule]
    r.clip = CLIP[rule]

    # 超卖否决：③⑤ 主动卖被挡；④ 仅"近期赢家(runner)"豁免（其无其它出场地板），
    # 非赢家(慢性下跌)从震荡触发④、又在超卖中卖=砸底 → 同样受否决（5.3 修订）。
    if r.veto and (rule in (3, 5) or (rule == 4 and not r.was_runner)):
        r.clip = 0.0
        r.action += "｜超卖否决(暂不执行,等非超卖日)"
    return r


# ── 主流程 ───────────────────────────────────────────────────────
def main():
    print("=" * 90)
    print(f"基金技术面分批清仓信号  |  数据日 {DATA_DATE}  |  规则 v2")
    print("=" * 90)

    regime = fetch_market_regime()
    print(f"市场 regime（仅提示, 不进决策）: {regime}\n")

    results = []
    for name, code, mv, pnl, bucket in HOLDINGS:
        print(f"  拉取 {code} {name} ...", end=" ")
        try:
            r = analyze(name, code, mv, pnl, bucket)
            if r.ok:
                print(f"OK n={r.n} {r.trend} -> 规则{r.rule}")
            else:
                print(f"失败跳过: {r.err}")
        except Exception as e:  # noqa: BLE001  最后兜底, 绝不中断
            traceback.print_exc()
            r = FundResult(name=name, code=code, mv=mv, pnl_pct=pnl, bucket=bucket,
                           ok=False, err=f"{type(e).__name__}: {e}")
            print(f"异常跳过: {r.err}")
        results.append(r)
        time.sleep(0.4)

    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]

    # ── 保底时钟（仅非强势仓）+ TWAP 对照 ──
    non_strong = [r for r in ok if r.rule != 1]
    non_strong_mv = sum(r.mv for r in non_strong)
    floor_target = MONTHLY_FLOOR * non_strong_mv
    suggested_total = sum(r.mv * r.clip for r in ok)

    # ── 汇总表 ──
    rows = []
    for r in results:
        if not r.ok:
            rows.append({
                "基金名称": r.name, "代码": r.code, "市值": r.mv,
                "建议动作": f"❌取数失败: {r.err}", "数据日": "", "最新净值": np.nan,
                "MA20": np.nan, "MA60": np.nan, "近60高": np.nan, "滚动最高": np.nan,
                "追踪带%": np.nan,
                "距MA20%": np.nan, "距近高%": np.nan, "趋势": "", "RSI": np.nan,
                "波动(年化)": np.nan, "建议卖出%": np.nan, "建议卖出¥": np.nan,
                "vsTWAP%": np.nan, "费率": "见App核对", "锁定/备注": LOCKED.get(r.code, ""),
            })
            continue
        dev = r.clip - MONTHLY_FLOOR
        rows.append({
            "基金名称": r.name, "代码": r.code, "市值": round(r.mv, 2),
            "建议动作": r.action, "数据日": r.latest_date, "最新净值": round(r.latest, 4),
            "MA20": round(r.ma20, 4) if r.ma20 == r.ma20 else np.nan,
            "MA60": round(r.ma60, 4) if r.ma60 == r.ma60 else np.nan,
            "近60高": round(r.high60, 4), "滚动最高": round(r.roll_high, 4),
            "追踪带%": r.trail,
            "距MA20%": r.dist_ma20, "距近高%": r.dist_high60, "趋势": r.trend,
            "RSI": round(r.rsi, 1) if r.rsi == r.rsi else np.nan,
            "波动(年化)": r.ann_vol, "建议卖出%": r.clip,
            "建议卖出¥": round(r.mv * r.clip, 0), "vsTWAP%": dev,
            "费率": fetch_fee(r.code) if r.rule in (3, 4, 5) else "见App核对",
            "锁定/备注": (LOCKED.get(r.code, "") + (" 次新基样本不足" if r.short_hist else "")).strip(),
        })

    df = pd.DataFrame(rows)
    # 排序：强势(rule1)沉底，其余按建议卖出%降序（卖出队列）
    rule_map = {r.code: r.rule for r in results}
    df["_rule"] = df["代码"].map(rule_map).fillna(99)
    df["_clip"] = df["建议卖出%"].fillna(-1)
    df = df.sort_values(["_clip", "市值"], ascending=[False, False]).drop(columns=["_rule", "_clip"])

    # ── 输出 Excel ──
    xlsx = OUTDIR / "基金技术出场信号.xlsx"
    write_excel(df, xlsx, regime, floor_target, suggested_total, non_strong_mv)
    print(f"\n写出 {xlsx}")

    # ── 输出 JSON（前端数据契约, schema 见 task/fund_exit_FE_handoff.md）──
    write_json(results, OUTDIR / "fund_signals.json", regime,
               floor_target, suggested_total, non_strong_mv)
    print(f"写出 {OUTDIR / 'fund_signals.json'}")

    # ── 图 ──
    chart_dir = OUTDIR / "charts"
    chart_dir.mkdir(exist_ok=True)
    for r in ok:
        try:
            plot_fund(r, chart_dir)
        except Exception as e:  # noqa: BLE001
            print(f"  绘图失败 {r.code}: {e}")
    print(f"写出 {len(ok)} 张图 -> {chart_dir}")

    # ── 文字小结 ──
    print_summary(ok, failed, regime, floor_target, suggested_total, non_strong_mv)


def write_excel(df, path, regime, floor_target, suggested_total, non_strong_mv):
    from openpyxl.styles import Font, PatternFill, Alignment

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="信号", startrow=4)
        ws = xw.sheets["信号"]
        ws["A1"] = f"基金技术面分批清仓信号  |  数据日 {DATA_DATE}  |  纪律工具, 非投资建议"
        ws["A2"] = f"市场regime(仅提示): {regime}"
        ws["A3"] = (f"保底月清仓(仅非强势仓 ¥{non_strong_mv:,.0f}): 目标 ¥{floor_target:,.0f}/月  |  "
                    f"本期建议合计 ¥{suggested_total:,.0f}  |  "
                    f"{'✅达标' if suggested_total >= floor_target else '⚠️低于保底,需补齐'}")
        ws["A1"].font = Font(bold=True, size=12)

        # 百分比格式列
        pct_cols = {"追踪带%", "距MA20%", "距近高%", "波动(年化)", "建议卖出%", "vsTWAP%"}
        money_cols = {"市值", "建议卖出¥"}
        headers = {c.value: c.column_letter for c in ws[5]}
        for col, letter in headers.items():
            if col in pct_cols:
                for cell in ws[letter][5:]:
                    cell.number_format = "0.0%"
            elif col in money_cols:
                for cell in ws[letter][5:]:
                    cell.number_format = "#,##0"
            elif col in {"最新净值", "MA20", "MA60", "近60高", "滚动最高"}:
                for cell in ws[letter][5:]:
                    cell.number_format = "0.0000"
        for cell in ws[5]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDDDDD")
            cell.alignment = Alignment(horizontal="center")
        widths = {"基金名称": 22, "代码": 9, "建议动作": 42, "费率": 22, "锁定/备注": 28}
        for col, letter in headers.items():
            ws.column_dimensions[letter].width = widths.get(col, 12)
        ws.freeze_panes = "A6"


def _num(x):
    """NaN/inf -> None（JSON 友好）。"""
    try:
        f = float(x)
        return None if (f != f or f in (float("inf"), float("-inf"))) else round(f, 6)
    except (TypeError, ValueError):
        return None


def write_json(results, path, regime, floor_target, suggested_total, non_strong_mv):
    """前端数据契约。schema 见 task/fund_exit_FE_handoff.md。"""
    import json
    from datetime import datetime

    ok = [r for r in results if r.ok]
    strong = [r for r in ok if r.rule == 1]
    total_mv = sum(r.mv for r in results)
    strong_mv = sum(r.mv for r in strong)

    funds = []
    for r in results:
        funds.append({
            "name": r.name, "code": r.code, "mv": _num(r.mv), "pnl_pct": _num(r.pnl_pct),
            "bucket": r.bucket, "ok": r.ok, "err": r.err,
            "latest": _num(r.latest), "latest_date": r.latest_date, "n": r.n,
            "short_hist": r.short_hist,
            "ma20": _num(r.ma20), "ma60": _num(r.ma60), "high60": _num(r.high60),
            "roll_high": _num(r.roll_high), "trail": _num(r.trail),
            "trail_trigger": _num(r.trail_trigger),
            "rsi": _num(r.rsi), "ann_vol": _num(r.ann_vol),
            "dist_ma20": _num(r.dist_ma20), "dist_ma60": _num(r.dist_ma60),
            "dist_high60": _num(r.dist_high60),
            "trend": r.trend, "rule": r.rule, "action": r.action,
            "clip": _num(r.clip), "clip_amt": _num(r.mv * r.clip) if r.ok else None,
            "vs_twap": _num(r.clip - MONTHLY_FLOOR) if r.ok else None,
            "veto": r.veto, "was_runner": r.was_runner,
            "locked": LOCKED.get(r.code, ""),
            "chart": f"charts/{r.code}_{r.name}.png" if r.ok else None,
        })

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_date": DATA_DATE,
        "market_regime": regime,
        "disclaimer": "纪律工具，非投资建议；阈值先验非优化；费率/锁定/赎回以中信App为准。",
        "params": {"DEEP": DEEP,
                   "trail_formula": f"clip({TRAIL_Z}σ·√{TRAIL_HORIZON_D}d, {TRAIL_FLOOR}, {TRAIL_CAP})",
                   "trend_band": TREND_BAND,
                   "monthly_floor": MONTHLY_FLOOR, "deep_limit": DEEP_LIMIT,
                   "strong_rule": "全部上升趋势(最新>MA20>MA60)纯持有"},
        "account": {
            "total_mv": _num(total_mv), "held_strong_mv": _num(strong_mv),
            "held_strong_pct": _num(strong_mv / total_mv) if total_mv else 0,
            "non_strong_mv": _num(non_strong_mv),
            "floor_target": _num(floor_target), "suggested_total": _num(suggested_total),
            "floor_met": bool(suggested_total >= floor_target),
        },
        "funds": funds,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def plot_fund(r: FundResult, chart_dir: Path):
    df = r.df.tail(min(ROLL_HIGH_WIN, r.n)).copy()
    nav = df["nav"]
    dates = df["date"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(dates, nav, label="累计净值", color="#1f3a5f", lw=1.4)
    if r.n >= MA_SHORT:
        ax.plot(dates, nav.rolling(MA_SHORT).mean(), label=f"MA{MA_SHORT}", color="#e08a00", lw=1.0)
    if r.n >= MA_LONG:
        ax.plot(dates, nav.rolling(MA_LONG).mean(), label=f"MA{MA_LONG}", color="#2e7d32", lw=1.0)
    # 近60高点
    tail60 = df.tail(min(HIGH60_WIN, len(df)))
    hi_idx = tail60["nav"].idxmax()
    ax.scatter(df.loc[hi_idx, "date"], df.loc[hi_idx, "nav"], color="red", zorder=5, s=30, label="近60高")
    # 追踪止盈触发位
    ax.axhline(r.trail_trigger, color="purple", ls="--", lw=1.0,
               label=f"追踪止盈触发 {r.trail_trigger:.4f} (滚动高-{r.trail*100:.1f}% σ缩放)")
    ax.set_title(f"{r.name} ({r.code})  {r.trend}  -> {r.action.split('｜')[0]}", fontsize=11)
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(chart_dir / f"{r.code}_{r.name}.png", dpi=110)
    plt.close(fig)


def print_summary(ok, failed, regime, floor_target, suggested_total, non_strong_mv):
    print("\n" + "=" * 90)
    print("文字小结")
    print("=" * 90)
    by_rule = {}
    for r in ok:
        by_rule.setdefault(r.rule, []).append(r)

    sell = [r for r in ok if r.clip > 0]
    hold_strong = by_rule.get(1, [])
    deep = by_rule.get(2, [])
    wait = [r for r in ok if r.clip == 0 and r.rule != 1]

    print(f"\n市场: {regime}")
    print(f"保底时钟(仅非强势仓 ¥{non_strong_mv:,.0f}): 目标 ¥{floor_target:,.0f}/月, "
          f"本期建议合计 ¥{suggested_total:,.0f} "
          f"{'✅达标' if suggested_total >= floor_target else '⚠️低于保底'}")

    print(f"\n【可减仓 {len(sell)} 只】(卖出队列, 按建议比例降序)")
    for r in sorted(sell, key=lambda x: -x.clip):
        print(f"  {r.code} {r.name:<18} {r.action.split('｜')[0]:<28} "
              f"卖{r.clip:.0%} ≈¥{r.mv*r.clip:,.0f}  距近高{r.dist_high60:+.1%} RSI{r.rsi:.0f}")

    print(f"\n【上升趋势·让利润奔跑 {len(hold_strong)} 只】(纯持有, 豁免保底时钟)")
    for r in hold_strong:
        print(f"  {r.code} {r.name:<18} 距近高{r.dist_high60:+.1%} RSI{r.rsi:.0f}  (vs均匀清仓: 少卖10%)")

    print(f"\n【等待 {len(wait)} 只】")
    for r in wait:
        print(f"  {r.code} {r.name:<18} {r.action.split('｜')[0]}")

    # 深套两只专项
    print("\n【深套专项】中欧医疗 003095 / 华夏兴阳 009010")
    for code in ("003095", "009010"):
        r = next((x for x in ok if x.code == code), None)
        if r is None:
            print(f"  {code}: 取数失败, 见上方报告")
            continue
        note = LOCKED.get(code, "")
        print(f"  {code} {r.name}: {r.trend} 距近高{r.dist_high60:+.1%} 距MA20{r.dist_ma20:+.1%} "
              f"-> {r.action.split('｜')[0]}")
        if r.rule == 2:
            print(f"      勿砍底; 反弹锚 MA20={r.ma20:.4f}/近20高; 硬时限{DEEP_LIMIT}到期走保底量")
        if note:
            print(f"      {note}")

    if failed:
        print(f"\n【取数失败 {len(failed)} 只】(已跳过, 不影响其余)")
        for r in failed:
            print(f"  {r.code} {r.name}: {r.err}")

    strong_mv = sum(r.mv for r in hold_strong)
    total_mv = sum(r.mv for r in ok) + sum(r.mv for r in failed)
    held_pct = strong_mv / total_mv if total_mv else 0
    print(f"\n注: 上升趋势纯持有为 PM 风险偏好(接受惰性, 让赢家跑), 当前 {len(hold_strong)} 只 "
          f"¥{strong_mv:,.0f} ≈ 账户 {held_pct:.0%}, 只要保持上升就不卖; 阈值是先验非优化; "
          "费率/锁定/具体赎回以中信App为准。")


if __name__ == "__main__":
    main()
