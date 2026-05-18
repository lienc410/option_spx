"""Q042 Joint BP Gate (F3)

Combined-cap backstop that limits Q042's total BP to avoid crowding the
main strategy during high-utilisation periods.

Formula (from SPEC-094 F3, updated by SPEC-104):
  q042_combined_cap = min(12.5, max(0.0, 60.0 - main_bp_pct))

Per-sleeve allowance:
  - cap ≥ 12.5%: Sleeve A gets 12.5%, Sleeve B gets 0% production
  - cap < 12.5%: prorate Sleeve A only
  - cap = 0:    both sleeves blocked

Gate state is appended daily to data/q042_gate_log.jsonl (AC12).

AC9:  main_bp_pct = 30% → cap = 12.5%, A=12.5% / B=0% (gate not binding)
AC10: main_bp_pct = 55% → cap =  5%, A=5% / B=0%
AC11: main_bp_pct = 65% → cap =  0%, both blocked
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from strategy.q042_config import (
    Q042_SLEEVE_A_PRODUCTION_CAP_PCT,
    Q042_SLEEVE_B_PRODUCTION_CAP_PCT,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_LOG  = REPO_ROOT / "data" / "q042_gate_log.jsonl"

_COMBINED_CAP_MAX    = Q042_SLEEVE_A_PRODUCTION_CAP_PCT + Q042_SLEEVE_B_PRODUCTION_CAP_PCT
_MAIN_BP_BUDGET      = 60.0   # % — governance threshold for main strategy

ET = ZoneInfo("America/New_York")


@dataclass
class GateResult:
    date: str
    main_bp_pct: float
    q042_combined_cap: float
    sleeve_a_allowance: float
    sleeve_b_allowance: float
    gate_binding: bool


def compute_gate(main_bp_pct: float, date: str = "") -> GateResult:
    """
    Compute per-sleeve BP allowance for Q042 given main strategy BP usage.

    Args:
        main_bp_pct: Current main-strategy BP as % of account (0–100).
        date:        ISO date string for the log entry (defaults to today ET).

    Returns:
        GateResult with per-sleeve allowances.
    """
    if not date:
        date = datetime.now(ET).strftime("%Y-%m-%d")

    cap = min(_COMBINED_CAP_MAX, max(0.0, _MAIN_BP_BUDGET - main_bp_pct))
    binding = cap < _COMBINED_CAP_MAX

    if cap >= _COMBINED_CAP_MAX:
        allowance_a = Q042_SLEEVE_A_PRODUCTION_CAP_PCT
        allowance_b = Q042_SLEEVE_B_PRODUCTION_CAP_PCT
    elif cap > 0:
        allowance_a = cap * Q042_SLEEVE_A_PRODUCTION_CAP_PCT / _COMBINED_CAP_MAX
        allowance_b = cap * Q042_SLEEVE_B_PRODUCTION_CAP_PCT / _COMBINED_CAP_MAX
    else:
        allowance_a = 0.0
        allowance_b = 0.0

    return GateResult(
        date=date,
        main_bp_pct=round(main_bp_pct, 2),
        q042_combined_cap=round(cap, 2),
        sleeve_a_allowance=round(allowance_a, 2),
        sleeve_b_allowance=round(allowance_b, 2),
        gate_binding=binding,
    )


def log_gate(result: GateResult) -> None:
    """Append gate state to data/q042_gate_log.jsonl (AC12)."""
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with GATE_LOG.open("a") as f:
        f.write(json.dumps(asdict(result)) + "\n")


def read_main_bp_pct() -> float:
    """
    Read current main-strategy BP% from the position state file.

    Falls back to 0.0 (safe default — gate not binding) if state is
    unavailable so Q042 is never incorrectly blocked by a missing file.
    """
    try:
        from strategy.state import read_state
        st = read_state()
        positions = st.get("positions", [])
        if not positions:
            pos = st
        else:
            pos = positions[0] if positions else {}
        return float(pos.get("bp_pct_account", 0.0))
    except Exception:
        return 0.0
