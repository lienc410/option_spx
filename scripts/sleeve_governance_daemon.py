#!/usr/bin/env python3
"""One-shot SPEC-103 sleeve governance state tracker.

Launchd can run this periodically; each invocation appends one read-only
portfolio governance snapshot and emits transition alerts when needed.
"""

from __future__ import annotations

import json

from strategy.sleeve_governance import record_state_snapshot


def main() -> int:
    state = record_state_snapshot(send_alerts=True)
    print(json.dumps({
        "ok": True,
        "timestamp": state.get("timestamp"),
        "stress_episode_active": state.get("stress_episode_active"),
        "second_leg_active": state.get("second_leg_active"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
