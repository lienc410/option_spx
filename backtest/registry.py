"""
Experiment registry helpers for backtest runs.
"""

from __future__ import annotations

import hashlib
import json
import random
import string
from dataclasses import asdict, is_dataclass
from datetime import datetime


def generate_experiment_id(timestamp: datetime | None = None) -> str:
    """
    Generate a unique experiment ID.

    Format: EXP-YYYYMMDD-HHMMSS-XXXX
    """
    when = timestamp or datetime.now()
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"EXP-{when.strftime('%Y%m%d-%H%M%S')}-{suffix}"


def config_hash(params: object) -> str:
    """Return a deterministic short hash for a params object."""
    if is_dataclass(params):
        payload = asdict(params)
    elif hasattr(params, "__dict__"):
        payload = vars(params)
    else:
        payload = str(params)
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
