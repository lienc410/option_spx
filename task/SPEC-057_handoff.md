# SPEC-057 Handoff

## 修改文件
- `strategy/selector.py:120` — `StrategyParams` 新增 `force_strategy`，并加入 `_build_forced_recommendation()` 与 `select_strategy()` 头部早返回
- `backtest/engine.py:792` — 两条 `signal_history` 路径补充 `iv_signal`
- `backtest/run_matrix_audit.py:1` — 新增全历史强制入场矩阵回测脚本
- `tests/test_spec_057.py:1` — 新增 6 个验收测试，覆盖 force 策略、matrix audit 与 `iv_signal`

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：AC1–AC6；`tests.test_spec_057` 7/7；`unittest discover -s tests` 114/114

## 阻塞/备注
- `data/market_cache.py` 仍会打印 `Timestamp.utcnow` deprecation warning，但不影响本次实现或测试结果
