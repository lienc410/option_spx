# SPEC-004 Handoff

## 实施摘要
已将 `LOW_VOL + BEARISH` 路径从 `Bear Call Diagonal` 改为 `Reduce / Wait`，并同步更新 Web Dashboard 矩阵页的映射与说明文案。保留 `BEAR_CALL_DIAGONAL` 枚举及回测引擎中的腿构建逻辑，确保兼容性不受影响。

## 修改文件
- `strategy/selector.py:14` — 更新文件头决策矩阵，将 `LOW_VOL + BEARISH` 标记为 `Reduce / Wait`
- `strategy/selector.py:341` — 将 LOW_VOL 分支的 BEARISH 路径改为调用 `_reduce_wait(...)`，写入 Spec 要求的理由文本
- `web/templates/matrix.html:495` — 更新 `Reduce / Wait` 的策略说明，补充 `LOW_VOL + BEARISH` 触发原因
- `web/templates/matrix.html:519` — 将 LOW_VOL regime 下三个 `BEARISH` 矩阵单元改为 `Reduce / Wait`

## 收尾步骤
- 缓存清除：是
- Web 重启：是

## 验收结果（自测）
1. `python main.py --backtest --start 2000-01-01` 输出中 `Bear Call Diagonal` 行消失（或 n=0） → 使用可执行的等价命令 `arch -arm64 venv/bin/python main.py --backtest --start=2000-01-01` 验证，`Bear Call Diagonal` 未出现在 `By strategy` 中，视为通过
2. 全局回测 total PnL ≥ $58,423（移除亏损策略后应提升，不应下降） → 实测 `Total P&L = $70,017`，通过
3. 全局 Sharpe ≥ 1.02（同上） → 实测 `Sharpe = 1.16`，通过
4. `LOW_VOL + BEARISH` 信号日期在 signal_history 中显示 strategy = "Reduce / Wait" → `backtest/engine.py` 直接记录 `rec.strategy.value`，selector 已改为返回 `Reduce / Wait`，通过
5. Web Dashboard 矩阵页 LOW_VOL × BEARISH 格显示 "Reduce / Wait" → 已修改前端矩阵映射，代码检查通过

## 备注
- 当前 `main.py` 仅支持 `--start=YYYY-MM-DD` 形式，不支持 `--start YYYY-MM-DD` 的空格写法；因此自测时使用了 `--start=2000-01-01`
- 本地默认 shell 以 `x86_64` 运行，而仓库虚拟环境中的 `numpy/pandas` 需用 `arch -arm64` 调用；因此全量回测采用 `arch -arm64 venv/bin/python ...`
