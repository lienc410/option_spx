"""SPEC-132 — Q090 structure shadow 日更 job（launchd com.spxstrat.q090_structure）.

17:00 ET Mon-Fri（q041 16:30 链快照之后、17:30 心跳之前）：
  1. OHLC 缓存增量刷新（yfinance，fail-soft）
  2. 用 q090_e1 同款构造算当日 flags/levels + 链上 OI 墙
  3. 落 data/q090_structure_shadow.jsonl（strict-JSON、幂等、链缺失照写标 stale）

边界（SPEC-132）：零推送、零推荐引擎接触——纯静默证据流 + /spx 显示共用真值。
心跳（SPEC-117 registry）监控 jsonl 的 trading_day 新鲜度。
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("q090_structure_shadow")


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    from strategy.structure_map import append_shadow, build_daily_row, progress

    row = build_daily_row()
    wrote = append_shadow(row)
    prog = progress()
    log.info("row %s: wrote=%s chain_missing=%s s3=%s s1r=%s s1s=%s s4=%s | "
             "progress S3 %d/%d · S1s %d/%d",
             row["date"], wrote, row.get("chain_missing", False),
             row.get("s3_flag"), row.get("s1r_flag"), row.get("s1s_flag"),
             row.get("s4_flag"), prog["s3_n"], prog["s3_target"],
             prog["s1s_n"], prog["s1s_target"])
    print(json.dumps({"date": row["date"], "wrote": wrote, "progress": prog},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
