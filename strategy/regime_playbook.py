"""SPEC-145 — Regime Playbook 单真值源（PM ratified 2026-07-13 对话裁决）。

三场景操作准则（箱体内 / 上破 / 下破）+ 当日动态点位，供 /state-map
PLAYBOOK 面板展示。纪律：

  - 点位零静态数字——全部由 (ath, band_lo, band_hi) 现算；参数 import 自
    各自真值源（_DD4_THRESHOLD/_B_RUNGS ← q042_trigger；_EPISODE_BAND ←
    executor，与 state_surface 同源；结构路由 ← q042_sizing）。
  - 基率文案 import 自 strategy.state_flip_notify（SPEC-142 同一字符串，
    不复制——两处漂移即谎言）。
  - 本模块是**展示层**（PM 请求的决策支持手册），不进 push 管道；
    SPEC-142 F2 禁令管推送，不管 PM 自 ratify 的手册面板。
  - 每条准则强制 provenance 标签（SPEC-132 badge 纪律同源）。
"""
from __future__ import annotations

from typing import Optional

from production.q042_executor import _EPISODE_BAND
from signals.q042_trigger import _B_RUNGS, _DD4_THRESHOLD
from strategy.q042_sizing import b_rung_structure
from strategy.state_flip_notify import (
    _DOWN_BREAK_LINE, _RANGE_AMMO_PREFIX, _UP_BREAK_LINE,
)

_WEAK_POKE_PCT = 0.01   # Q097 P3b：4/4 崩盘签名 = 探出箱顶 <1% 的弱上破


def compute_levels(ath: float, band_lo: Optional[float],
                   band_hi: Optional[float]) -> Optional[dict]:
    """当日点位地图。箱体死亡线由带宽恒等式反解：
    (h−l)/((h+l)/2) = lim → 上亡 h' = l×(2+lim)/(2−lim)，下亡对称。"""
    if not ath or ath <= 0:
        return None                      # F7 ath_degraded → 不给点位，不给假数
    lim = _EPISODE_BAND
    out = {
        "ath": round(ath, 2),
        "a_trigger": round(ath * (1 + _DD4_THRESHOLD), 2),
        "b_rungs": [
            {"rung_pct": r * 100, "level": round(ath * (1 + r), 2),
             "instrument": b_rung_structure(r)["instrument"],
             "dte": b_rung_structure(r)["dte"]}
            for r in _B_RUNGS
        ],
    }
    if band_lo and band_hi:
        up_death = band_lo * (2 + lim) / (2 - lim)
        down_death = band_hi * (2 - lim) / (2 + lim)
        out.update({
            "band_lo": round(band_lo, 2), "band_hi": round(band_hi, 2),
            "box_up_death": round(up_death, 2),
            "box_down_death": round(down_death, 2),
            "weak_poke_hi": round(band_hi * (1 + _WEAK_POKE_PCT), 2),
            # 本箱下破路径是否先经过 A 触发线（箱型相关，逐日现算）
            "a_fires_before_box_death": bool(ath * (1 + _DD4_THRESHOLD) > down_death),
        })
    return out


def scenarios() -> list[dict]:
    """三场景准则。语言标准（PM 2026-07-13）：没参与本项目但懂期权的交易员
    可以直接读懂——项目内部代号（selector/veto 层/G2/rung 等）一律翻译成
    通用交易语言，统计速记展开成白话。line = 中文叙事（domain jargon 豁免），
    ref = 证据出处。"""
    return [
        {
            "key": "range",
            "title": "IN BOX",
            "subtitle": "箱体内（含宽幅震荡）",
            "lines": [
                {"line": "照常卖权收租——确认进入震荡后再开的 bull put spread / "
                         "看涨对角价差，26 年回测依然显著盈利（累计 +$32~58 万）；"
                         "横盘期 theta 照收，真正的敌人是下跌不是横盘",
                 "ref": "Q095 K3"},
                {"line": "价格贴近箱顶（上 1/3）时，新的方向性开仓等 1-2 天再动手——"
                         "本系统 79% 的方向单天然落在箱顶区（趋势信号与箱顶同源），"
                         "而箱体下 1/3 入场的历史单笔均值接近 2 倍。仅作参考，不设硬规则",
                 "ref": "Q095 P2c"},
                {"line": _RANGE_AMMO_PREFIX + "保持可动用现金 ≥ 预留额"
                         "（实时数值见上方引擎卡）——箱体期就是抄底资金的待命期",
                 "ref": "SPEC-142 / Q093"},
                {"line": "箱体内不开第二笔 bull call diagonal——每笔占用约 $38k 现金，"
                         "第二笔花掉的就是崩盘时的抄底子弹",
                 "ref": "Q096"},
                {"line": "期权持仓墙（open interest 聚集的行权价）可以参考、先别加权重——"
                         "它是目前唯一未被证伪的技术面信号，但证据还在积累（样本 <60）",
                 "ref": "Q090 S3"},
            ],
        },
        {
            "key": "up_break",
            "title": "UP BREAK",
            "subtitle": "向上破位（真假确认 → 第一动作）",
            "lines": [
                {"line": "真假突破没有可靠的盘面预判特征：成交量区分不了（崩盘前的上破"
                         "量能与良性上破无统计差异），通道/形态也无预警力——"
                         "判断只能靠基率和事后走势，不要猜",
                 "ref": "Q097 P3c/P3"},
                {"line": _UP_BREAK_LINE, "ref": "Q097 P3b"},
                {"line": "弱上破之后两周保持警觉：放慢新开仓节奏、盯紧 VIX 是否升档；"
                         "只是警觉，不是停止交易——3.3% 的基率不值得为此放弃 96.7% 的正常行情",
                 "ref": "Q097 P3b"},
                {"line": "确认真突破（新箱体在更高位置站稳 / 趋势状态确认）后的第一个动作："
                         "照常按信号开仓，不要等回调——回测里'等回调再进'只等到 33 笔"
                         "（正常节奏 137 笔），单笔优势完全补不回错过的量；趋势中在高位入场"
                         "长期是赚钱的",
                 "ref": "Q089 E2 / Q095 K3"},
            ],
        },
        {
            "key": "down_break",
            "title": "DOWN BREAK",
            "subtitle": "向下破箱（第一动作）",
            "lines": [
                {"line": "第一个动作是清点抄底资金，不是加对冲——抄底触发线（距历史高点 "
                         "−4%）常与破箱同窗出现（今日两者先后见上方点位表），触发后次日"
                         "开盘执行",
                 "ref": "Q093 / SPEC-094.7"},
                {"line": _DOWN_BREAK_LINE, "ref": "Q097 P3b"},
                {"line": "新开仓交给波动率分层自动管：VIX 升档 → 新仓自动减半，再升 → "
                         "停发新仓。在场仓位按既有纪律执行：短腿剩 ≤7 天到期必须主动决策"
                         "（平仓/滚动/接受结算）、短腿残值跌到 ≤15% 回补锁定、亏损进入"
                         "预设的风控复核——不做恐慌性手动平仓",
                 "ref": "Q095 P3 / Q089 / SPEC-123"},
                {"line": "继续下跌由预设的抄底阶梯逐档接：−15% 开 90 天 call spread，"
                         "−25%/−35%/−45% 各开一笔 2 年期 XSP 深度实值 LEAP call；"
                         "持仓跌破下一档时收到一次性提醒，是否止损离场由交易员裁量",
                 "ref": "Q102 / SPEC-094.7"},
            ],
        },
    ]


_ACTIVE_MAP = {"RANGE": "range", "TREND_UP": "up_break", "TREND_DOWN": "down_break"}


def build_payload(state: Optional[dict] = None,
                  surface_row: Optional[dict] = None) -> dict:
    """组装面板 payload。state/surface_row 可注入（测试）；默认读生产真值。"""
    if state is None:
        from signals.q042_trigger import load_state
        state = load_state()
    if surface_row is None:
        from strategy.state_flip_notify import _latest_two_rows
        from strategy.state_surface import STATE_SURFACE_LOG
        _, surface_row = _latest_two_rows(STATE_SURFACE_LOG)
    surface_row = surface_row or {}
    sa = (surface_row.get("surface") or {}).get("structure_axis") or {}
    ath = float(state.get("ath_running_max", 0.0) or 0.0)
    levels = compute_levels(ath, sa.get("band_lo"), sa.get("band_hi"))
    structure = surface_row.get("structure_state")
    return {
        "ratified": "PM 2026-07-13",
        "as_of": surface_row.get("date"),
        "structure_state": structure,
        "active_scenario": _ACTIVE_MAP.get(str(structure)),   # MIXED/None → null
        "ath_degraded": ath <= 0,
        "levels": levels,
        "scenarios": scenarios(),
    }
