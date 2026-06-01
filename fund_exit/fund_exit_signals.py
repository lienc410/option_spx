# -*- coding: utf-8 -*-
"""基金技术面分批清仓信号工具 (Strategy Spec v3 — 2026-06 审计后重构)

定位：纪律 / 行为约束工具，非 alpha 择时、非投资建议。
详见 task/fund_exit_strategy_spec.md。

核心模型：clip = base(保底·强制清仓节奏) + extra(信号驱动·可被超卖否决)
  · base  ：非强势仓每月强制出 MONTHLY_FLOOR → floor 结构性达标；深套也靠它逐步出。
  · extra ：连续随回撤深度缩放 min(SLOPE×回撤, CAP[rule])；RSI<30 时归零，base 不受影响。
  · 强势①(上升趋势)纯持有，base=extra=0。

规则（优先级取首个命中；深套/追踪统一用"滚动高"参照；extra 温和封顶）：
  ① 上升趋势 : 最新>MA20>MA60                       -> 纯持有(base=extra=0)
  ② 深套     : 下降 且 距滚动高 <= -DEEP             -> base only（不加码砸底）
  ③ 确认下降 : 下降 且 距滚动高 > -DEEP              -> base + extra(≤0.15, 随回撤)
  ④ 震荡破带 : 现价 <= 滚动高*(1-TRAIL_σ)            -> base + extra(≤0.10, 随回撤)
  ⑤ 破MA20   : 震荡 且 MA20>MA60 且 现价<MA20        -> base + extra(≤0.05, 随回撤)
  ⑥ 其余     : -> base only

超卖否决 = 仅 RSI<RSI_OVERSOLD（审计 A1：去掉"创新低"——那是下行动能、非超卖）。
TRAIL σ-scaled(~1σ 6周, clip 5-14%)；趋势 band-hysteresis(±1%) 压日度 whipsaw。
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

# ── 参数（PM 2026-05-31；2026-06 审计后重构）───────────────────────
# 核心模型：clip = base(保底·强制清仓节奏) + extra(信号驱动·可被超卖否决)
#   · base  ：所有"非强势"仓每月强制出 MONTHLY_FLOOR → floor 结构性达标(审计 A3)；
#             深套也靠 base 逐步出，取代旧"硬时限钟"(A2)
#   · extra ：按"继续下跌把握"叠加；超卖(RSI<RSI_OVERSOLD)时归零，但 base 不受影响(A1)
#   · 强势①(上升趋势)纯持有，base=extra=0（PM 接受 ~60% 惰性）
DEEP = 0.15               # 深套界：距滚动高 ≤ -DEEP（A6：深套/追踪统一用滚动高，顺带修 A10）
MONTHLY_FLOOR = 0.10      # base：非强势仓每月强制清仓比例（清仓脊柱）
RSI_OVERSOLD = 30         # 超卖否决阈（A7：原硬编码 → 命名参数）

# extra：连续随"距滚动高的回撤深度"缩放（deeper→more），再按信号类型**温和封顶**。
#   extra = min(EXTRA_SLOPE × max(0,-dist_roll), EXTRA_CAP[rule])
#   SLOPE=1.0 → "回撤多少就额外卖多少"(1:1)，再被 cap 压住 → 对 TWAP 偏离 ≤ cap。
#   温和档（2026-06 PM 定）：信号信息量低(无 backtest)，注码配 edge，只做弱倾斜不重注。
EXTRA_SLOPE = 1.0
EXTRA_CAP = {
    1: 0.00,   # ① 上升趋势：纯持有
    2: 0.00,   # ② 深套：不加码（capitulation 不砸底）
    3: 0.15,   # ③ 确认下降趋势：封顶最高
    4: 0.10,   # ④ 震荡·破追踪带
    5: 0.05,   # ⑤ 震荡·破MA20：封顶最低
    6: 0.00,   # ⑥ 持有观察：仅 base
    0: 0.00,   # ⓪ 数据不足：仅 base
}

# 5.4 追踪止盈带：连续随基金自身波动缩放 trail = clip(1σ·√30d, 5%, 14%)
TRAIL_Z = 1.0
TRAIL_HORIZON_D = 30
TRAIL_FLOOR, TRAIL_CAP = 0.05, 0.14
TRAIL_DEFAULT = 0.08      # 波动样本不足时兜底带
# 5.6 趋势 band-hysteresis：现价在 MA20 ±TREND_BAND 内"贴线"不判方向，压日度 whipsaw
TREND_BAND = 0.01

MA_SHORT, MA_LONG = 20, 60
ROLL_HIGH_WIN = 250       # 滚动高水位窗口（深套 + 追踪止盈统一参照；次新基用全可用历史）
RSI_PERIOD = 14

# ── 持仓清单（去重 10 只，2026-05-31，中信证券 App）──────────────
HOLDINGS = [
    # name, code, market_value, pnl_pct   (A8: vol_bucket 已删—σ-trail 后无用)
    ("华夏卓越成长混合",     "024930", 152086.10,  0.52),
    ("睿远成长价值混合A",    "007119", 141325.43,  0.69),
    ("华夏红利价值混合",     "024915", 136386.96, -0.19),
    ("工银圆兴混合",         "009076", 133813.91,  0.12),
    ("中信保诚前瞻优势混合", "013610", 103306.75,  0.01),
    ("华安研究智选混合A",    "011692",  93525.56, -0.08),
    ("中欧医疗健康混合",     "003095",  50730.79, -0.56),
    ("朱雀产业智选混合",     "007880",  42118.97, -0.17),
    ("华夏兴阳一年持有混合", "009010",  32060.03, -0.54),
    ("泓德卓远混合A",        "010864",  22936.78, -0.11),
]
# 009010 华夏兴阳一年持有: 2021-01-04 申购 → ~2022-01 满1年持有期 → 已解锁, 现可自由赎回。
# 原"锁定"警告已移除(假约束)。若未来近12个月内有新增申购批次, 该批会重新锁1年, 届时再加回。
LOCKED = {}

ACTION_TEXT = {
    1: "①上升趋势：让利润奔跑，纯持有",
    2: "②深套：不加码砸底，仅走保底量逐步出",
    3: "③确认下降趋势：保底 + 额外(随回撤缩放，封顶15%)",
    4: "④震荡·破追踪带：保底 + 额外(随回撤缩放，封顶10%)",
    5: "⑤震荡·破MA20：保底 + 额外(随回撤缩放，封顶5%)",
    6: "⑥持有观察：仅走保底量",
    0: "数据不足：仅走保底量，指标待补",
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
    ok: bool = True
    err: str = ""
    latest: float = float("nan")
    latest_date: str = ""
    n: int = 0
    ma20: float = float("nan")
    ma60: float = float("nan")
    roll_high: float = float("nan")
    trail: float = float("nan")
    trail_trigger: float = float("nan")
    rsi: float = float("nan")
    ann_vol: float = float("nan")
    dist_ma20: float = float("nan")
    dist_ma60: float = float("nan")
    dist_roll: float = float("nan")      # 距滚动高（A6 统一参照）
    trend: str = ""
    rule: int = 6
    action: str = ""
    base: float = 0.0                    # 强制保底量
    extra: float = 0.0                   # 信号额外量（可被超卖否决）
    clip: float = 0.0                    # = base + extra
    oversold: bool = False               # RSI<RSI_OVERSOLD（A1：仅此，不含创新低）
    short_hist: bool = False
    df: pd.DataFrame = field(default=None, repr=False)


def analyze(name, code, mv, pnl_pct) -> FundResult:
    r = FundResult(name=name, code=code, mv=mv, pnl_pct=pnl_pct)
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
    r.roll_high = float(nav.tail(min(ROLL_HIGH_WIN, n)).max())
    r.rsi = rsi(nav, RSI_PERIOD)
    rets = nav.pct_change().dropna()
    sigma_d = float(rets.tail(60).std()) if len(rets) >= 20 else float("nan")
    r.ann_vol = sigma_d * np.sqrt(252) if sigma_d == sigma_d else float("nan")

    # 5.4 追踪止盈带：连续随基金自身波动缩放（σ-scaled），带宽=1σ 的 ~6 周移动。
    if sigma_d == sigma_d:
        r.trail = float(np.clip(TRAIL_Z * sigma_d * np.sqrt(TRAIL_HORIZON_D),
                                TRAIL_FLOOR, TRAIL_CAP))
    else:
        r.trail = TRAIL_DEFAULT
    r.trail_trigger = r.roll_high * (1 - r.trail)
    r.dist_ma20 = r.latest / r.ma20 - 1 if r.ma20 == r.ma20 else float("nan")
    r.dist_ma60 = r.latest / r.ma60 - 1 if r.ma60 == r.ma60 else float("nan")
    r.dist_roll = r.latest / r.roll_high - 1 if r.roll_high == r.roll_high else float("nan")

    # 趋势三态 + 5.6 band-hysteresis（压日度 whipsaw，见 _trend_label）
    r.trend = _trend_label(r.latest, r.ma20, r.ma60)

    # 超卖否决：仅 RSI<RSI_OVERSOLD（A1：去掉"创新低"那条腿——它是下行动能、非超卖）
    r.oversold = (r.rsi == r.rsi and r.rsi < RSI_OVERSOLD)

    # ── 规则引擎（优先级）；深套用 dist_roll（统一滚动高，A6）──
    if r.trend == "上升":   # PM 2026-05-31: 全部上升趋势纯持有(让赢家跑), 不论距高
        rule = 1
    elif r.trend == "下降" and r.dist_roll <= -DEEP:
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
    # base + extra 分层：base 强制（非强势仓）；extra 连续随回撤深度缩放、温和封顶、可被超卖否决
    r.base = 0.0 if rule == 1 else MONTHLY_FLOOR
    depth = max(0.0, -r.dist_roll) if r.dist_roll == r.dist_roll else 0.0
    r.extra = min(EXTRA_SLOPE * depth, EXTRA_CAP[rule])
    if r.oversold and r.extra > 0:   # A1：超卖只挡 extra，不挡 base
        r.extra = 0.0
        r.action += "｜超卖否决额外(RSI<{}，仅走保底)".format(RSI_OVERSOLD)
    r.clip = min(r.base + r.extra, 1.0)
    return r


# ── 主流程 ───────────────────────────────────────────────────────
def main():
    print("=" * 90)
    print(f"基金技术面分批清仓信号  |  数据日 {DATA_DATE}  |  规则 v3(审计后)")
    print("=" * 90)

    regime = fetch_market_regime()
    print(f"市场 regime（仅提示, 不进决策）: {regime}\n")

    results = []
    for name, code, mv, pnl in HOLDINGS:
        print(f"  拉取 {code} {name} ...", end=" ")
        try:
            r = analyze(name, code, mv, pnl)
            if r.ok:
                print(f"OK n={r.n} {r.trend} -> 规则{r.rule} clip={r.clip:.0%}")
            else:
                print(f"失败跳过: {r.err}")
        except Exception as e:  # noqa: BLE001  最后兜底, 绝不中断
            traceback.print_exc()
            r = FundResult(name=name, code=code, mv=mv, pnl_pct=pnl,
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
                "MA20": np.nan, "MA60": np.nan, "滚动最高": np.nan, "追踪带%": np.nan,
                "距MA20%": np.nan, "距滚动高%": np.nan, "趋势": "", "RSI": np.nan,
                "波动(年化)": np.nan, "保底%": np.nan, "额外%": np.nan,
                "建议卖出%": np.nan, "建议卖出¥": np.nan,
                "vsTWAP%": np.nan, "费率": "见App核对", "锁定/备注": LOCKED.get(r.code, ""),
            })
            continue
        dev = r.clip - MONTHLY_FLOOR
        rows.append({
            "基金名称": r.name, "代码": r.code, "市值": round(r.mv, 2),
            "建议动作": r.action, "数据日": r.latest_date, "最新净值": round(r.latest, 4),
            "MA20": round(r.ma20, 4) if r.ma20 == r.ma20 else np.nan,
            "MA60": round(r.ma60, 4) if r.ma60 == r.ma60 else np.nan,
            "滚动最高": round(r.roll_high, 4), "追踪带%": r.trail,
            "距MA20%": r.dist_ma20, "距滚动高%": r.dist_roll, "趋势": r.trend,
            "RSI": round(r.rsi, 1) if r.rsi == r.rsi else np.nan,
            "波动(年化)": r.ann_vol, "保底%": r.base, "额外%": r.extra,
            "建议卖出%": r.clip,
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
        pct_cols = {"追踪带%", "距MA20%", "距滚动高%", "波动(年化)", "保底%", "额外%", "建议卖出%", "vsTWAP%"}
        money_cols = {"市值", "建议卖出¥"}
        headers = {c.value: c.column_letter for c in ws[5]}
        for col, letter in headers.items():
            if col in pct_cols:
                for cell in ws[letter][5:]:
                    cell.number_format = "0.0%"
            elif col in money_cols:
                for cell in ws[letter][5:]:
                    cell.number_format = "#,##0"
            elif col in {"最新净值", "MA20", "MA60", "滚动最高"}:
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
            "ok": r.ok, "err": r.err,
            "latest": _num(r.latest), "latest_date": r.latest_date, "n": r.n,
            "short_hist": r.short_hist,
            "ma20": _num(r.ma20), "ma60": _num(r.ma60),
            "roll_high": _num(r.roll_high), "trail": _num(r.trail),
            "trail_trigger": _num(r.trail_trigger),
            "rsi": _num(r.rsi), "ann_vol": _num(r.ann_vol),
            "dist_ma20": _num(r.dist_ma20), "dist_ma60": _num(r.dist_ma60),
            "dist_roll": _num(r.dist_roll),
            "trend": r.trend, "rule": r.rule, "action": r.action,
            "base": _num(r.base), "extra": _num(r.extra),
            "clip": _num(r.clip), "clip_amt": _num(r.mv * r.clip) if r.ok else None,
            "vs_twap": _num(r.clip - MONTHLY_FLOOR) if r.ok else None,
            "oversold": r.oversold,
            "locked": LOCKED.get(r.code, ""),
            "chart": f"charts/{r.code}_{r.name}.png" if r.ok else None,
        })

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_date": DATA_DATE,
        "market_regime": regime,
        "disclaimer": "纪律工具，非投资建议；阈值先验非优化；费率/锁定/赎回以中信App为准。",
        "params": {"DEEP": DEEP, "rsi_oversold": RSI_OVERSOLD,
                   "trail_formula": f"clip({TRAIL_Z}σ·√{TRAIL_HORIZON_D}d, {TRAIL_FLOOR}, {TRAIL_CAP})",
                   "trend_band": TREND_BAND, "monthly_floor": MONTHLY_FLOOR,
                   "model": "clip = base(保底,强制) + extra(信号,可被RSI<{}否决)".format(RSI_OVERSOLD),
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
    # 滚动高水位点（深套/追踪的统一参照，A6）
    hi_idx = df["nav"].idxmax()
    ax.scatter(df.loc[hi_idx, "date"], df.loc[hi_idx, "nav"], color="red", zorder=5, s=30, label="滚动高")
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

    print(f"\n市场: {regime}")
    print(f"保底 floor(仅非强势仓 ¥{non_strong_mv:,.0f}): ¥{floor_target:,.0f}/月(每只走 base 结构性达标), "
          f"本期建议合计 ¥{suggested_total:,.0f}(base+extra)")

    print(f"\n【建议卖出 {len(sell)} 只】(队列按 clip 降序; clip = 保底base + 信号extra)")
    for r in sorted(sell, key=lambda x: -x.clip):
        print(f"  {r.code} {r.name:<18} {r.action.split('｜')[0]:<26} "
              f"卖{r.clip:.0%}(保{r.base:.0%}+额{r.extra:.0%}) ≈¥{r.mv*r.clip:,.0f}  "
              f"距滚高{r.dist_roll:+.1%} RSI{r.rsi:.0f}{' 超卖' if r.oversold else ''}")

    print(f"\n【上升趋势·让利润奔跑 {len(hold_strong)} 只】(纯持有, 豁免 floor)")
    for r in hold_strong:
        print(f"  {r.code} {r.name:<18} 距滚高{r.dist_roll:+.1%} RSI{r.rsi:.0f}  (vs均匀: 少卖10%)")

    # 深套两只专项
    print("\n【深套专项】中欧医疗 003095 / 华夏兴阳 009010")
    for code in ("003095", "009010"):
        r = next((x for x in ok if x.code == code), None)
        if r is None:
            print(f"  {code}: 取数失败, 见上方报告")
            continue
        note = LOCKED.get(code, "")
        print(f"  {code} {r.name}: {r.trend} 距滚高{r.dist_roll:+.1%} 距MA20{r.dist_ma20:+.1%} "
              f"-> {r.action.split('｜')[0]} (卖{r.clip:.0%})")
        if r.rule == 2:
            print(f"      深套: 不加 extra, 仅 base {r.base:.0%}/月逐步出(取代旧硬时限钟)")
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
