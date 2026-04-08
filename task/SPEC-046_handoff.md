# SPEC-046 Handoff

## 修改文件
- `schwab/client.py:67` — 新增 index quote 缓存与归一化 helpers，提供 `get_vix_quote()` / `get_spx_quote()`
- `signals/intraday.py:55` — 给 intraday alert dataclass 增加 `realtime` 元数据，并新增 quote-driven `get_vix_spike_from_quote()` / `get_spx_stop_from_quote()`
- `notify/telegram_bot.py:47` — intraday monitor 改为 Schwab primary / Yahoo fallback，并在告警消息中增加 `sent` / `delayed` 标注
- `tests/test_spec_046_quotes.py:13` — 新增 Schwab quote 归一化与 quote-driven intraday signal 单元测试
- `tests/test_telegram_bot.py:130` — 新增 bot 优先 Schwab、失败回落 Yahoo、stale/non-realtime 标签测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：F1, F2, F3, F4, F5, F6, F7, F8
- 未通过：无
