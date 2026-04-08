# SPEC-047 Handoff

## 修改文件
- `schwab/scanner.py:7` — 将 centered scan 改为 80/140/220 三轮自适应扩窗，并新增边界命中检测，保留 SPEC-045 的 `delta_gap` / `interpolated_center`
- `tests/test_schwab_scanner.py:53` — 新增多轮扩窗、边界命中和 pass3 fallback 回归测试，覆盖 AC1–AC9

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9
