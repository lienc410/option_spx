# SPEC-045 Handoff

## 修改文件
- `schwab/scanner.py:7` — 新增宽窗常量、delta 插值寻靶函数，并将 `build_strike_scan()` 改为单次宽窗拉取 + 插值选中心 + 局部评分
- `schwab/client.py:142` — 将 `strike_window` 显式纳入 centered chain cache key，避免不同窗口污染缓存
- `tests/test_schwab_scanner.py:43` — 用 SPEC-045 的验收口径替换旧扩窗测试，补 AC2/AC4 的插值与边界覆盖

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7
- 未通过：无
