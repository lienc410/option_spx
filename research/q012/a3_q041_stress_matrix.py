"""
Q012/Q052 Action A3 — Q041 IV-Expansion Stress Matrix
======================================================
Run iv_expansion_stress_test on Q041 Tier 1 + Tier 2 CSP candidates.
Output is formatted as a markdown appendix for q041_execution_prep_packet.

Candidates tested:
  - Tier 1: SPX CSP Δ0.20 DTE30 (1 contract)
  - Tier 2: GOOGL CSP Δ0.20 DTE21 (1 contract)
  - Tier 2: AMZN CSP Δ0.25 DTE21 (1 contract)

Stress shocks: VIX +10 / +20 / +40 (per A1 default)

Notes for Q041 context:
  - Q041 doesn't use credit-multiple credit stop like /ES SPEC-061. Q041 CSPs
    typically allow assignment if SPX < K at expiry. Stop_pnl_ratio = -2.0 used
    here is a REFERENCE marker, not a hard rule. The valuable output is mark
    loss / BP expansion paths, not the survival classification per se.
  - For single names (GOOGL / AMZN), iv_proxy_factor maps current option IV to
    VIX. Calibration: GOOGL ~30% IV at VIX 19 → factor 1.58; AMZN ~35% → 1.84.
    These are approximate; production should use observed IV at entry.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research.tools.iv_expansion_stress_test import (
    StressReport, stress_naked_put, DEFAULT_SHOCKS,
)


# Current market reference (2026-05-09)
SPX_SPOT   = 5400.0
GOOGL_SPOT = 386.0    # rounded from $385.69 per Q041 packet
AMZN_SPOT  = 268.0
CURRENT_VIX = 19.0
NLV         = 500_000.0


def run_q041_stress() -> list[StressReport]:
    reports = []

    # Tier 1 — SPX CSP Δ0.20 DTE30
    reports.append(stress_naked_put(
        label="Tier 1 — SPX CSP Δ0.20 DTE30",
        spot=SPX_SPOT, vix=CURRENT_VIX,
        target_delta=0.20, dte=30,
        contracts=1, nlv=NLV, multiplier=100.0,
        iv_proxy_factor=1.0,        # SPX IV ≈ VIX
        stop_pnl_ratio=-2.0,        # reference marker
        use_es_span_model=False,    # use OCC PM
    ))

    # Tier 2 — GOOGL CSP Δ0.20 DTE21
    # Approx: GOOGL 30D IV ~30% at VIX 19 → iv_proxy ≈ 30/19 = 1.58
    reports.append(stress_naked_put(
        label="Tier 2 — GOOGL CSP Δ0.20 DTE21",
        spot=GOOGL_SPOT, vix=CURRENT_VIX,
        target_delta=0.20, dte=21,
        contracts=1, nlv=NLV, multiplier=100.0,
        iv_proxy_factor=1.58,
        stop_pnl_ratio=-2.0,
    ))

    # Tier 2 — AMZN CSP Δ0.25 DTE21
    # Approx: AMZN 30D IV ~35% at VIX 19 → iv_proxy ≈ 35/19 = 1.84
    reports.append(stress_naked_put(
        label="Tier 2 — AMZN CSP Δ0.25 DTE21",
        spot=AMZN_SPOT, vix=CURRENT_VIX,
        target_delta=0.25, dte=21,
        contracts=1, nlv=NLV, multiplier=100.0,
        iv_proxy_factor=1.84,
        stop_pnl_ratio=-2.0,
    ))

    return reports


def format_markdown_appendix(reports: list[StressReport]) -> str:
    """Generate a markdown-formatted appendix to insert into the Q041 packet."""
    lines = []
    lines.append("## 八、IV-Expansion Stress Visibility Appendix（2026-05-09）")
    lines.append("")
    lines.append("**来源：** R-20260509-02 Action A3。使用 Action A1 工具 "
                 "`research/tools/iv_expansion_stress_test.py` 对当前 Tier 1 / "
                 "Tier 2 候选进行 IV expansion stress test。")
    lines.append("")
    lines.append("**目的：** 在 paper trading 启动前，量化各候选在 VIX shock 路径下的 "
                 "mark loss、BP expansion、stop proximity 暴露——补足 Q041 执行包此前缺失 "
                 "的 IV-expansion 维度（参见 R-20260509-02 must-absorb principle 1）。")
    lines.append("")
    lines.append("**模型说明：**")
    lines.append("")
    lines.append("- VIX shock：当前 19 + shock（+10 / +20 / +40 → new VIX 29 / 39 / 59）")
    lines.append("- 相关下跌：每 +3 VIX shock 对应 -1% underlying 下跌（Phase A 校准）")
    lines.append("- IV 扩张：entry IV × (new_vix / current_vix)，单名通过 `iv_proxy_factor` 表达")
    lines.append("- BP 模型：SPX 用 OCC PM；单名同口径")
    lines.append("- `pnl_ratio = mark_loss / entry_credit`（CSP 口径，非 spread 口径）")
    lines.append("")
    lines.append("**Q041 vs /ES stop rule 重要差异：** Q041 CSP **不使用** /ES 类的硬 "
                 "credit-multiple stop（SPEC-061 STOP_MULT=3）。Q041 通常允许 ITM 时被 "
                 "assigned（持有 underlying）。`pnl_ratio = -2.0` 在表中作为**参考标记**，"
                 "不代表 Q041 触发该值时必须平仓。")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-tier table
    for r in reports:
        lines.append(f"### {r.label}")
        lines.append("")
        es = r.entry_state
        lines.append(f"**Entry state（VIX={r.vix}, spot={r.spot}）：**")
        lines.append("")
        lines.append(f"- Strike: {es['strike']}")
        lines.append(f"- Premium per share: ${es['premium_per_share']}")
        lines.append(f"- Credit (1 contract × 100): ${es['credit_dollars']:,.0f}")
        lines.append(f"- Entry BP (OCC PM): ${es['bp_dollars']:,.0f} "
                     f"({es['bp_dollars']/r.nlv*100:.1f}% NLV)")
        lines.append("")

        lines.append("| VIX shock | New VIX | New spot | Mark loss | Stress BP | "
                     "BP exp% | pnl_ratio | Survival |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for p in r.stress_points:
            shk = f"+{p.vix_shock}" if p.vix_shock else "0"
            lines.append(f"| {shk} | {p.new_vix:.0f} | {p.new_spot:.0f} | "
                         f"${p.mark_loss_dollars:,.0f} | "
                         f"${p.stress_bp_dollars:,.0f} | "
                         f"{p.bp_expansion_pct:+.1f}% | "
                         f"{p.pnl_ratio:+.2f} | {p.survival} |")
        lines.append("")

        worst = r.worst_point()
        lines.append(f"**Worst-case stress (+{worst.vix_shock} shock):**")
        lines.append("")
        lines.append(f"- Mark loss: **${worst.mark_loss_dollars:,.0f}** "
                     f"({worst.mark_loss_dollars/r.nlv*100:+.1f}% NLV)")
        lines.append(f"- Stress BP: **${worst.stress_bp_dollars:,.0f}** "
                     f"({worst.stress_bp_dollars/r.nlv*100:+.1f}% NLV)")
        lines.append(f"- pnl_ratio: **{worst.pnl_ratio:+.2f}** "
                     f"({worst.survival.upper()})")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Summary
    lines.append("### 综合判断")
    lines.append("")
    lines.append("| Tier | Worst shock | Mark loss | Stress BP% NLV | Survival |")
    lines.append("|------|------------|-----------|----------------|----------|")
    for r in reports:
        worst = r.worst_point()
        lines.append(f"| {r.label.split('—')[0].strip()} | +{worst.vix_shock} | "
                     f"${worst.mark_loss_dollars:,.0f} | "
                     f"{worst.stress_bp_dollars/r.nlv*100:.1f}% | "
                     f"{worst.survival.upper()} |")
    lines.append("")

    # Decision implications
    lines.append("### 对 paper trading 启动的含义")
    lines.append("")
    lines.append("1. **Tier 1 SPX CSP** 在 +40 VIX shock 下 mark loss 可达单笔账户的 "
                 "几个百分点。这与 Q041 的 paper-trading scope（1 张合约、低 BP 占用）"
                 "在风险吸收范围内。")
    lines.append("")
    lines.append("2. **Tier 2 GOOGL/AMZN CSP** 因 single-name IV 高于 VIX，shock 同 "
                 "VIX 量级时 mark loss 比例更大；这与 Q041 packet 既有的 tail caveat "
                 "（同名 8–10% 单月移动会深度穿越 strike）一致。")
    lines.append("")
    lines.append("3. **没有 hard stop**：Q041 设计上接受 assignment。这意味着 stress 表 "
                 "中的 mark loss 不一定会被实现——可以等到到期 cash settlement 或被"
                 "assigned 持有 underlying。但为了 paper-trading 数据收集，应**记录** "
                 "每个 cycle 的 max mark loss，以便后续校准是否需要引入软退出规则。")
    lines.append("")
    lines.append("4. **不重开 Q041 研究边界**：本附件不修改 Tier 1 或 Tier 2 的 paper "
                 "trading scope，只补足风险可见性。如果 paper trading 在真实运行中观察 "
                 "到 mark loss 远超本表估算，应反过来校准本工具的 IV expansion 模型。")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 82)
    print("A3 — Q041 IV-Expansion Stress Matrix")
    print("=" * 82)
    reports = run_q041_stress()

    for r in reports:
        r.print_table()

    print("\n\n" + "=" * 82)
    print("MARKDOWN APPENDIX (for q041_execution_prep_packet_2026-05-05.md)")
    print("=" * 82)
    print(format_markdown_appendix(reports))
