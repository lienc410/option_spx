# SPEC-041 Handoff

## 修改文件
- `notify/telegram_bot.py:102` — 新增 `_morning_snapshot` RAM 缓存与 EOD snapshot 格式化辅助函数
- `notify/telegram_bot.py:295` — `_reset_intraday_state()` 现在同步清空 `_morning_snapshot`
- `notify/telegram_bot.py:703` — `scheduled_push()` 成功后写入 morning snapshot，新增 `scheduled_eod_push()`
- `notify/telegram_bot.py:676` — 在 `post_init()` 注册 4:03pm ET 的 `eod_push` scheduler job
- `tests/test_telegram_bot.py:11` — 新增 EOD snapshot 格式、morning cache 与 reset 行为回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8

## 阻塞/备注
- 定向回归通过：`venv/bin/python -m unittest tests.test_telegram_bot -v`
- 全量 `unittest discover` 中 `tests.test_state_and_api` 被系统临时目录耗尽阻塞：`FileNotFoundError: No usable temporary directory found ...`；这属于当前机器磁盘/临时目录环境问题，不是本 spec 的 bot 逻辑回归。
