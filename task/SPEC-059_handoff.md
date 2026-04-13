# SPEC-059 Handoff

## 修改文件
- `backtest/run_bootstrap_ci.py:1` — 新增 block bootstrap 95% CI 工具，固定 `seed=42`，`block_size=max(5, n//4)`，`n<10` 返回 NaN
- `backtest/run_matrix_bootstrap.py:1` — 新增 matrix-level bootstrap 汇总与打印格式，输出 `matrix_audit_bootstrap.csv`
- `tests/test_spec_059.py:1` — 新增 6 个验收测试，覆盖正均值、负均值、跨零、low-n 与 CSV 写出

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1–AC6；`tests.test_spec_059` 6/6；`unittest discover -s tests` 120/120

## 阻塞/备注
- 本 SPEC 仅新增统计工具，不涉及 `strategy/selector.py`、`signals/` 或 `web` 运行态刷新
