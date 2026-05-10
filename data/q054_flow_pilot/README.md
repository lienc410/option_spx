# Q054 Flow Pilot — Data Drop

PM 端从 UW Web UI 手动 export 的 unusual options flow CSV 落点。

## File naming

`seg_NN_YYYYMMDD_YYYYMMDD.csv` （例：`seg_01_20260501_20260509.csv`）

## Schema 最低要求

`ticker, created_at, total_ask_side_prem, total_bid_side_prem, underlying_price`

完整列清单见 `task/q054_pilot_export_instructions_2026-05-10.md`。

## Pipeline

`research/q054/q054_pilot_hit_rate.py` 自动 pick up 此目录所有 `seg_*.csv` 文件。
