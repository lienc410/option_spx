#!/usr/bin/env python
"""SPEC-135.5 — Lane D 测试向量生成（7/11 生产快照固定用例）.

生成 tests/fixtures/spec135_5_lane_d_vectors.json：
  inputs   = 四台引擎的数据源 payload 固定向量（7/11 实况格：双 sleeve armed、
             main_bp 15.8%、Aftermath 未激活 NORMAL、压力机 normal、
             ES Ladder 0/5 blocked VIX）
  expected = 以上 inputs 灌入 strategy.decision_trace.lane_d_sleeves() 的
             全量输出（冻结回归锁——任何文案/结构变更都必须有意识地重跑
             本脚本并在 commit message 注明"向量重生成"）

gate log 行不手写：用 strategy.q042_gate.compute_gate（生产公式唯一真值）
生成——脚本层也不重推公式。strict-JSON：allow_nan=False。

用法：./venv/bin/python scripts/gen_spec135_5_vectors.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT = REPO / "tests" / "fixtures" / "spec135_5_lane_d_vectors.json"

BP_SOURCE = {
    "source": "sleeve_governance_runtime.pools.spx_pm_bp_pct(all)",
    "timestamp": "2026-07-11T09:40:00-04:00",
}


def build_inputs() -> dict:
    from strategy.q042_gate import compute_gate

    # ── gate log 行：生产公式生成（SPEC-094 F3；main_bp 15.8% = 094.2 AC-8
    #    dry-run 实测读数）。附一条更早行 + 一条 blocked_fire 行，锁
    #    read_latest_gate_row 的"最新 + 跳过反事实行"语义。
    row_711 = asdict(compute_gate(15.8, date="2026-07-11"))
    row_711["bp_source"] = BP_SOURCE
    row_710 = asdict(compute_gate(16.2, date="2026-07-10"))
    blocked_fire_row = {
        "date": "2026-07-11",
        "blocked_fire": {"sleeve": "B", "reason": "allowance_zero",
                         "would_be_contracts": 1, "ddath": -0.0421},
    }
    gate_log_rows = [row_710, row_711, blocked_fire_row]

    # 压缩/归零/fail-closed 变体（联动线四档文案的另外三档）——同样走生产公式
    row_squeezed = asdict(compute_gate(55.0, date="2026-07-11"))
    row_squeezed["bp_source"] = BP_SOURCE
    row_zero = asdict(compute_gate(65.0, date="2026-07-11"))
    row_zero["bp_source"] = BP_SOURCE
    row_failclosed = {
        "date": "2026-07-11", "main_bp_pct": None, "q042_combined_cap": 0.0,
        "sleeve_a_allowance": 0.0, "sleeve_b_allowance": 0.0,
        "gate_binding": True, "gate_available": False, "bp_source": BP_SOURCE,
    }

    # ── /api/q042/state payload 格（q042_state_payload 输出形状；7/11 实况：
    #    双 sleeve armed，回撤 −0.9%——spec 例文数字）
    q042_state = {
        "date": "2026-07-11", "spx_close": 7537.0, "ath_running_max": 7605.5,
        "ath_degraded": False, "ddath_pct": -0.9,
        "sleeve_a": {"armed": True, "production_cap_pct": 12.5,
                     "target_cap_pct": 17.5, "stage": "stage_1",
                     "active_position": None, "stats": {}},
        "sleeve_b": {"armed": True, "production_status": "research_only",
                     "production_cap_pct": 0.0, "in_watching": False,
                     "watch_start_date": None, "active_position": None,
                     "stats": {}},
        "combined_bp_pct": 0.0,
        "monitors": {},
    }

    # ── /api/aftermath/state payload 格（aftermath_state_payload 输出形状；
    #    未激活：10 日峰值 18.4 < 28，NORMAL）
    aftermath_state = {
        "active": False, "vix": 15.03, "vix_peak_10d": 18.41,
        "off_peak_pct": 18.36, "threshold_off_peak_pct": 10.0,
        "threshold_peak_min": 28.0, "threshold_vix_max": 40.0,
        "regime": "NORMAL", "trend": "FALLING",
        "reason": "peak_below_threshold (18.4 < 28.0)", "date": "2026-07-11",
    }

    # ── sleeve_governance._latest_market_stress 输出形状（normal 态）
    market_stress = {
        "status": "available", "vix": 15.03, "spx_close": 7537.0,
        "ma50": 7301.2, "ddath": -0.009, "dd_20d": -0.011, "dd_60d": -0.015,
        "vix_5d_change": 0.3, "ivp252": 24.0,
        "stress_episode_active": False, "second_leg_active": False,
        "source": "live_cache_quote_best_effort",
    }

    # ── /api/hvladder/live payload 格（status_human = 卡片/Lane D 共享 copy）
    hvladder_live = {
        "date": "2026-07-11", "threshold": 22.0, "vix_current": 15.03,
        "vix_5td_avg": 15.89, "latest_close_date": "2026-07-10",
        "quote_time": None, "vix_source": "schwab", "vix_stale": False,
        "vix_gate_distance": -6.97, "active_slots": 0, "max_slots": 5,
        "cadence_elapsed_trading_days": None,
        "trend": {"warmed": True, "trend_ok": True, "ok": True, "error": None},
        "gate_status": {"warmed": True, "trend_ok": True, "cadence_ok": True,
                        "slots_ok": True, "vix_ok": False},
        "signal_live": False, "production_status": "research_only",
        "production_allocation_pct": 0.0, "execution_allowed": False,
        "research_only_note": ("Research-only / paper-only per SPEC-104. "
                               "NO PRODUCTION EXECUTION."),
        "blockers": ["vix_ok"],
        "status_human": {"slots_text": "slots 0/5", "blockers_human": ["VIX"],
                         "state_text": "blocked: VIX",
                         "badge_word": "NO ENTRY", "badge_label": "NO ENTRY"},
        "last_signal": None, "status": "ok",
        "errors": {"vix": None, "trend": None},
    }

    return {
        "gate_log_rows": gate_log_rows,
        "gate_row_squeezed": row_squeezed,
        "gate_row_zero": row_zero,
        "gate_row_failclosed": row_failclosed,
        "q042_state": q042_state,
        "aftermath_state": aftermath_state,
        "market_stress": market_stress,
        "hvladder_live": hvladder_live,
    }


def run_lane_d(inputs: dict, tmp_gate_log: Path) -> dict:
    """把 inputs 灌进 lane_d_sleeves（与测试同一 patch 面）。"""
    import strategy.q042_gate as qg
    import strategy.sleeve_governance as sg
    import web.server  # noqa: F401 — lane_d 惰性 import 的目标模块

    tmp_gate_log.write_text(
        "\n".join(json.dumps(r) for r in inputs["gate_log_rows"]) + "\n",
        encoding="utf-8")

    from strategy.decision_trace import lane_d_sleeves
    with patch("web.server.q042_state_payload",
               return_value=inputs["q042_state"]), \
         patch.object(qg, "GATE_LOG", tmp_gate_log), \
         patch("web.server.aftermath_state_payload",
               return_value=inputs["aftermath_state"]), \
         patch.object(sg, "_latest_market_stress",
                      return_value=inputs["market_stress"]), \
         patch.object(sg, "booster_mode", return_value="shadow"), \
         patch.object(sg, "ladder_mode", return_value="shadow"), \
         patch("web.server.hvladder_live_payload",
               return_value=inputs["hvladder_live"]):
        return lane_d_sleeves()


def main() -> int:
    import tempfile

    inputs = build_inputs()
    with tempfile.TemporaryDirectory() as tmp:
        expected = run_lane_d(inputs, Path(tmp) / "gate_log.jsonl")
    vectors = {
        "_provenance": ("SPEC-135.5 AC：7/11 快照固定测试用例（双 sleeve armed + "
                        "main_bp 15.8% 联动线）。gate 行由 q042_gate.compute_gate "
                        "生成（公式唯一真值）；expected_lane_d = 冻结回归锁，"
                        "重生成必须在 commit message 注明。生成脚本："
                        "scripts/gen_spec135_5_vectors.py"),
        "inputs": inputs,
        "expected_lane_d": expected,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(vectors, ensure_ascii=False, indent=1, sort_keys=True,
                   allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"wrote {OUT}")
    print("linkage label:", [n["label_human"] for n in expected["engines"]
                             if n["check"] == "dd_overlay_main_linkage"][0])
    print("summary_line:", expected["summary_line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
