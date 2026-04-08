# SPEC-042 Handoff

## 修改文件
- `schwab/scanner.py:8` — 新增指数链识别，`scan_strikes()` 对 `SPX` 改用 relaxed OI penalty 而非 `<100` 硬过滤
- `schwab/scanner.py:55` — `build_strike_scan()` 继续复用原接口，但显式把 `symbol` 透传给 scanner
- `tests/test_schwab_scanner.py:27` — 新增 `SPX` 低 OI 保留候选、非指数低 OI 仍排除的回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5

## 阻塞/备注
- 定向回归通过：`venv/bin/python -m unittest tests.test_schwab_scanner -v`
- live sanity 通过：当前 `$SPX` short-call 场景下 `build_strike_scan('SPX', 'CALL', 0.20, 45, center_strike=7315)` 返回 `rows=1, fallback=False`，推荐 strike 为 `7325.0`。
- 全量 `unittest discover` 中 `tests.test_state_and_api` 被系统临时目录耗尽阻塞：`FileNotFoundError: No usable temporary directory found ...`；这属于当前机器磁盘/临时目录环境问题，不是本 spec 的 scanner 回归。
