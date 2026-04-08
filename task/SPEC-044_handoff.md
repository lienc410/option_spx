# SPEC-044 Handoff

## 修改文件
- `web/server.py:339` — `/api/position/open-draft` 在 `strike_scan` rows 中补充 `target_delta`、`live_delta`、`delta_gap`
- `web/templates/index.html:529` — 新增 `gap-mid` / `gap-high` 视觉样式，给高 `Δ Gap` 行显式提示
- `web/templates/index.html:1064` — Open modal strike scan 表格扩为 `Target Δ / Live Δ / Δ Gap` 三列，保留原点击回填和推荐逻辑
- `tests/test_state_and_api.py:161` — 新增 API payload 中 `target_delta / live_delta / delta_gap` 的回归断言

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5

## 阻塞/备注
- 定向回归通过：`TMPDIR=$PWD/task venv/bin/python -m unittest tests.test_schwab_scanner tests.test_telegram_bot tests.test_state_and_api -v`
- live sanity：`/api/position/open-draft` 当前 short-leg row 已返回 `target_delta=0.2`、`live_delta=0.016`、`delta_gap=0.184`，前端可直接按偏差阈值上色。
