"""Weekly regime-flags refresh — keeps the Gov BT page's data alive.

The q064→q072 daily-flags chain was a one-shot research artifact (last manual
run 2026-05-15); the Governance & Regime Backtest page silently served a
frozen distribution and missed the 2026-06 VIX-22 episode entirely
(PM review 2026-07-07, option B: invest to revive).

Pattern (SPEC-132 precedent): the RESEARCH artifacts stay tracked in git as
reproducibility truth — this script runs the chain, copies the fresh daily
flags to a gitignored RUNTIME file (data/q072_daily_flags_runtime.csv), then
restores the tracked research outputs to their committed state so oldair's
working tree never drifts. Server reads prefer the runtime copy when newer
(strategy/sleeve_governance.py:q072_daily_flags_path).

Inputs are yahoo-only (VIX/SPX history) plus committed backtest trade CSVs —
no expired vendor dependency. Trade-signal overlay columns extend only when
those trade CSVs are regenerated; regime/episode columns (what the page's
summary, episode log and current-episode card read) refresh every run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

CHAIN = [
    REPO / "research" / "q064" / "q064_p1_aftermath_windows.py",
    REPO / "research" / "q072" / "q072_p1_episode_detection.py",
]
FLAGS_SRC = REPO / "research" / "q072" / "q072_p1_daily_flags.csv"
FLAGS_RUNTIME = REPO / "data" / "q072_daily_flags_runtime.csv"

# Everything the chain writes into the tracked research tree — restored after
# the runtime copy is taken.
TRACKED_OUTPUTS = [
    "research/q064/q064_p1_windows.csv",
    "research/q064/q064_p1_daily_flags.csv",
    "research/q072/q072_p1_daily_flags.csv",
    "research/q072/q072_p1_episodes.csv",
    "research/q072/q072_p1_capital_stack.csv",
    "research/q072/q072_p1_coactivation_matrix.csv",
    "research/q072/q072_p1_coactivation_4way.csv",
]


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [regime-flags] {msg}", flush=True)


def main() -> int:
    for script in CHAIN:
        log(f"running {script.relative_to(REPO)}")
        res = subprocess.run([PY, str(script)], cwd=str(REPO),
                             capture_output=True, text=True, timeout=1200)
        if res.returncode != 0:
            log(f"FAILED ({res.returncode}): {res.stderr.strip()[-400:]}")
            return 1

    if not FLAGS_SRC.exists():
        log("chain succeeded but flags CSV missing — aborting")
        return 1

    FLAGS_RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FLAGS_SRC, FLAGS_RUNTIME)

    # Report freshness from the runtime copy's last row.
    try:
        last = FLAGS_RUNTIME.read_text().strip().rsplit("\n", 1)[-1].split(",")[0]
        log(f"runtime flags updated → {FLAGS_RUNTIME.name} (last row {last})")
    except Exception:
        log(f"runtime flags updated → {FLAGS_RUNTIME.name}")

    # Restore tracked research artifacts (reproducibility truth stays at the
    # committed state; fresh data lives only in the runtime copy).
    res = subprocess.run(["git", "checkout", "--", *TRACKED_OUTPUTS],
                         cwd=str(REPO), capture_output=True, text=True)
    if res.returncode != 0:
        log(f"WARN git restore failed: {res.stderr.strip()[-200:]}")
    else:
        log("tracked research outputs restored to committed state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
