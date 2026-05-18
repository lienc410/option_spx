"""Q042 production cap constants.

SPEC-104 promotes Q042 Sleeve A with staged production sizing while keeping
Sleeve B out of production routing for now.
"""

from __future__ import annotations

import os

Q042_SLEEVE_A_STAGE_LABEL = "stage_1"
Q042_SLEEVE_A_PRODUCTION_CAP_PCT = float(os.getenv("Q042_SLEEVE_A_PRODUCTION_CAP_PCT", "12.5"))
Q042_SLEEVE_A_TARGET_CAP_PCT = 17.5
Q042_SLEEVE_B_PRODUCTION_CAP_PCT = 0.0
Q042_SLEEVE_B_PAPER_SIZING_PCT = 10.0
