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
    """三场景准则。line = 中文叙事（domain jargon 豁免），ref = 证据出处。"""
    return [
        {
            "key": "range",
            "title": "IN BOX",
            "subtitle": "箱体内（含宽幅震荡）",
            "lines": [
                {"line": "照常收 premium——确认震荡后入场的 BPS/BCD 显著为正"
                         "（t +4.2~+6.1，Σ$32-58万/26y）；theta 照收，敌人是下跌不是横盘",
                 "ref": "Q095 K3"},
                {"line": "贴箱顶（上 1/3）的新方向单等 1-2 天——79% 方向单天然落在箱顶区，"
                         "下 1/3 单笔均值近 2×（软指引，不规则化）",
                 "ref": "Q095 P2c"},
                {"line": _RANGE_AMMO_PREFIX + "liquid ≥ reserve（数值见 L2 引擎卡）——"
                         "箱体期 = 抄底弹药待命期",
                 "ref": "SPEC-142 / Q093"},
                {"line": "别开第二笔 BCD——第二笔花掉的就是抄底子弹",
                 "ref": "Q096"},
                {"line": "期权墙可以看、别加权重（S3 唯一存活家族，证据积累中 n≥60）",
                 "ref": "Q090 S3"},
            ],
        },
        {
            "key": "up_break",
            "title": "UP BREAK",
            "subtitle": "向上破位（真假确认 → 第一动作）",
            "lines": [
                {"line": "真假突破没有盘面预判特征：量能零分离（崩盘上破落良性分布 "
                         "43-79 分位，置换 p=0.79-0.96）、通道形态零预警——用基率和时间，不猜",
                 "ref": "Q097 P3c/P3"},
                {"line": _UP_BREAK_LINE, "ref": "Q097 P3b"},
                {"line": "弱上破（探出箱顶 <1%）→ 5-10TD 警觉窗：不加仓速、盯 VIX 档位；"
                         "只警觉不 veto（条件概率仅 3.3%）",
                 "ref": "Q097 P3b"},
                {"line": "确认真突破后第一动作：不等回调，selector 照常发单——"
                         "等回调 = 饿死（33 vs 137 笔，CI 全跨零）；顶部入场被证赚",
                 "ref": "Q089 E2 / Q095 K3"},
            ],
        },
        {
            "key": "down_break",
            "title": "DOWN BREAK",
            "subtitle": "向下破箱（第一动作）",
            "lines": [
                {"line": "第一动作 = 查弹药，不是加对冲——dip 触发与下破常同窗"
                         "（点位表给出今日 A 触发线与箱底的先后），接 T+1 fire 告警",
                 "ref": "Q093 / SPEC-094.7"},
                {"line": _DOWN_BREAK_LINE, "ref": "Q097 P3b"},
                {"line": "新仓发行交给 veto 层（VIX 升档自动 0.5×/停发）；在场仓位走既有"
                         "纪律：短腿 ≤7DTE 强制决策点、collapse buyback ≤15% 回补、"
                         "亏损归 G2/D1——不手动恐慌平仓",
                 "ref": "Q095 P3 / Q089 / SPEC-123"},
                {"line": "继续跌由阶梯逐档接（−15% spread / ≤−25% XSP LEAP 730d）；"
                         "持仓 rung 击穿有一次性 FYI，割肉裁量归 PM",
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
