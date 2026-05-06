# SPEC-082 Handoff

## 修改文件
- `schwab/client.py:262` — `_parse_chain_response` 追加 Schwab IV、Greeks、expiry type、OHLC 与 last 字段。
- `research/q041/collect_chains.py:179` — Q041 chain frame 末尾追加新增列，并对新增数值列做 `pd.to_numeric` 转换。

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC5, AC6, AC7
- 未通过：AC3 → 实测 AAPL `iv_min=-999.0`, `iv_max=629.206` vs 目标 `10 <= iv <= 200`
- 未通过：AC4 → 实测 AAPL `expiry_type=['S', 'W']` vs 目标同时出现 `['M', 'W']`

## 阻塞/备注
- `arch -arm64 venv/bin/python -m research.q041.collect_chains --force --verbose` 成功，`ok=17 errors=0 total_rows=60980`。
- `python -m pytest tests/test_schwab_scanner.py` 与 `arch -arm64 venv/bin/python -m pytest tests/test_schwab_scanner.py` 均无法运行：当前 venv 未安装 `pytest`。
- 默认 `python` 导入 pandas 失败，原因是解释器为 x86_64、venv 中 NumPy 扩展为 arm64；可执行校验改用 `arch -arm64 venv/bin/python`。
