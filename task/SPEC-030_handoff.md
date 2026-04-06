# SPEC-030 Handoff

## 修改文件
- `backtest/prototype/SPEC-030_intraday_stop.py:1` — 用现有 `GSPC` 缓存读取 OHLC，并改为重建真实 BPS legs 后用 `_current_value()` 精确扫描日内 stop/profit
- `tests/test_spec_030_intraday_stop.py:1` — 新增 cache-OHLC 与 exact-leg reconstruction regression tests

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：1, 2, 3, 4

## 阻塞/备注
- 修复 Bug 1：确认 `data/market_cache/yahoo__GSPC__max__1d.pkl` 已含 `Open/High/Low/Close`，prototype 改为直接复用本地缓存，不再新建 `GSPC_ohlc` key 触发网络请求
- 修复 Bug 2：删除线性近似；改为用 `trade.entry_spx + trade.entry_vix + strategy` 重建真实 BPS/BPS_HV legs，并用 `_current_value(legs, spx_low/high, sigma_close, days_held)` 精确重估
- 实测结果：
  - Report 1：BPS/BPS_HV `stop_loss` 仅 1 笔；`同日触及=1`，`提前1天=0`，`提前2天=0`，`提前3天+=0`，`从未提前=0`
  - Report 2：无提前触及记录，因此无可计量的提前止损节省
  - Report 3：唯一 stop 交易出现在 `2022`，提前率 `0.0%`
  - Report 4：BPS/BPS_HV `50pct_profit` 共 23 笔；`同日触及=19 (82.6%)`，`提前1+天=4 (17.4%)`，平均提前 `1.50` 天
  - AC4 结论：`提前触及率=0.0%`、`平均提前量=0.00天`，因此“现有收盘判断已足够，关闭此研究方向”
- 验证：
  - `venv/bin/python backtest/prototype/SPEC-030_intraday_stop.py`
  - `venv/bin/python -m unittest discover -s tests -v` → 29/29 通过
