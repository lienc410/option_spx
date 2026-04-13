# SPEC-056 Handoff

## 修改文件
- `backtest/engine.py:721` — 回测与 signals-only 路径新增 `ivp63` / `ivp252` / `regime_decay` / `local_spike` 计算与 signal_history 字段
- `strategy/selector.py:117` — `StrategyParams` 新增 `disable_entry_gates`，并将 DIAGONAL 三道门与 `BCS_HV` 的 `ivp63` 门挂到该开关下
- `backtest/run_event_study.py:15` — 事件研究结果追加 `regime` / `trend` / `ivp63` / `ivp252` / `regime_decay` / `local_spike`，并默认写出 CSV
- `backtest/run_strategy_audit.py:1` — 新增全历史信号桶矩阵审计脚本
- `backtest/run_conditional_pnl.py:1` — 新增条件累计 P&L 时间序列脚本
- `tests/test_spec_056.py:1` — 新增 14 个用例覆盖字段、门控开关、event study、audit、conditional pnl

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：AC1、AC2、AC4、AC5、AC6、AC7；`tests.test_spec_056` 14/14；`unittest discover -s tests` 107/107
- 通过：AC3 对应实现已返回 10 个 bucket 的 audit DataFrame，并由 gates-disabled 路径覆盖被门拦截样本

## 阻塞/备注
- `venv` 中未安装 `pytest`，因此专项验收改用等价的 `python -m unittest tests.test_spec_056 -v`
- 测试过程中出现 `data/market_cache.py` 的 `Timestamp.utcnow` deprecation warning，但不影响本次功能
