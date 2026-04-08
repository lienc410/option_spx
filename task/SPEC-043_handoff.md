# SPEC-043 Handoff

## 修改文件
- `schwab/client.py:142` — `_chain_cache_key()` 现在将 `strike_window` 纳入 centered scan 缓存 key，避免窄窗/宽窗互相污染
- `schwab/client.py:256` — 在最佳 expiry 内按 strike 去重后再裁剪 centered window，避免重复 strike 浪费扩窗额度
- `schwab/scanner.py:12` — 新增 `delta_gap` / `miss_target` 判定，primary 命中不足时自动触发一次 secondary wider scan
- `tests/test_schwab_scanner.py:53` — 新增 wider scan 触发、good-primary 不二次请求与缓存隔离回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5

## 阻塞/备注
- 定向回归通过：`TMPDIR=$PWD/task venv/bin/python -m unittest tests.test_schwab_scanner tests.test_state_and_api -v`
- live sanity：当前 `$SPX` short-call 场景下，`strike_window=24` 已扩到 `7250..7450` 的 24 个去重 strike；scanner 推荐从原来的 `7350 Δ0.016` 改为 `7250 Δ0.028`，较 `target Δ0.20` 更接近。
