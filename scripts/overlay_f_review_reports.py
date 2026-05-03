"""Generate a compact Overlay-F telemetry review report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


LOG = Path("data/overlay_f_shadow.jsonl")


def load_events(path: Path = LOG) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def render_markdown(events: list[dict]) -> str:
    by_mode = Counter(str(e.get("mode", "")) for e in events)
    by_strategy = Counter(str(e.get("strategy", "")) for e in events)
    lines = [
        "# Overlay-F Review Report",
        "",
        f"- total_events: {len(events)}",
        f"- by_mode: {dict(by_mode)}",
        f"- by_strategy: {dict(by_strategy)}",
        "",
        "## Latest Events",
        "",
    ]
    for event in events[-20:]:
        lines.append(
            "- {date} {strategy} mode={mode} factor={factor} idle_bp={idle} sg={sg} vix={vix}".format(
                date=event.get("date"),
                strategy=event.get("strategy"),
                mode=event.get("mode"),
                factor=event.get("effective_factor"),
                idle=event.get("idle_bp_pct"),
                sg=event.get("sg_count"),
                vix=event.get("vix"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    print(render_markdown(load_events()))


if __name__ == "__main__":
    main()
