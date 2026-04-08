# SPEC-039 Handoff

## 修改文件
- `schwab/client.py:139` — 新增 `/marketdata/v1/chains` 解析与 `get_option_chain()`，沿用现有 Schwab TTL 缓存
- `schwab/scanner.py:8` — 新增 `scan_strikes()` / `build_strike_scan()`，实现流动性过滤、评分、推荐与 fallback
- `web/server.py:284` — `GET /api/position/open-draft` 在 Schwab 已配置时按两档字段调用 scanner，并返回 `strike_scan`
- `web/templates/index.html:1041` — Open modal 新增 per-leg strike scan 表、推荐标记、橙色 spread 警示与点击回填
- `tests/test_schwab_scanner.py:8` — 新增 scanner / option chain 解析与缓存测试
- `tests/test_state_and_api.py:134` — 新增 `open-draft` 在 Schwab ready 时注入 `strike_scan` 的 API 测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8

## 阻塞/备注
- 按 PM 澄清，本次只在现有两档字段范围内实现：BPS/BCS 系列扫描 `short_strike + long_strike`，Iron Condor 仅扫描并回填 call 侧；put 侧与四腿 schema 扩展留给后续 SPEC。
- 线上修正：Schwab `chains` 对指数期权需使用 `symbol=$SPX`；已在 `schwab/client.py` 统一做 marketdata symbol 规范化，修复了 `SPX` 直接请求返回 400 的问题。
