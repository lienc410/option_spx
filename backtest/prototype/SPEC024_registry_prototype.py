"""
Experiment Registry — SPEC-024

Generates unique experiment IDs and config hashes to associate
backtest runs with their parameter configurations.

Format: EXP-YYYYMMDD-HHMMSS-XXXX
  where XXXX is a 4-character alphanumeric random suffix
Config hash: sha256(sorted params dict)[:12]
"""

import hashlib
import json
import random
import string
from datetime import datetime


def generate_experiment_id(timestamp: datetime | None = None) -> str:
    """
    Generate a unique experiment ID.

    Format: EXP-YYYYMMDD-HHMMSS-XXXX
    XXXX = 4 random alphanumeric characters for collision avoidance.

    Example: EXP-20260401-143022-A7F2
    """
    if timestamp is None:
        timestamp = datetime.now()
    date_str = timestamp.strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"EXP-{date_str}-{suffix}"


def config_hash(params: object) -> str:
    """
    Compute a deterministic 12-character hex hash of a StrategyParams instance.

    Uses sha256 of the sorted JSON representation of the params dataclass fields.
    Ensures identical configs always produce the same hash across runs.

    Returns the first 12 hex characters (48 bits) — sufficient for experiment
    deduplication in a single research session.
    """
    from dataclasses import asdict
    try:
        d = asdict(params)
    except TypeError:
        # fallback for non-dataclass objects
        d = vars(params) if hasattr(params, "__dict__") else str(params)

    canonical = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


if __name__ == "__main__":
    # Smoke test
    exp_id = generate_experiment_id()
    print(f"Generated ID: {exp_id}")
    assert exp_id.startswith("EXP-")
    assert len(exp_id) == 4 + 1 + 8 + 1 + 6 + 1 + 4  # EXP-YYYYMMDD-HHMMSS-XXXX = 20 chars
    print("registry.py OK")
