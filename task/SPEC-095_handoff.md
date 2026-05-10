# SPEC-095 Handoff

## 修改文件
- `research/strategies/ES_puts/backtest.py` — 新增 `run_phase2_v2f()`、V2f 常量、20-seed bootstrap stability 指标
- `web/server.py` — 新增 fail-soft `GET /api/es-backtest/v2f` 和 V2f metrics/caveats summary
- `web/templates/es_backtest.html` — 新增 V2f tab、V0 vs V2f compare cards、visible caveat banner
- `tests/test_spec_095.py` — 新增 SPEC-095 专项验证（V2f metrics、route fail-soft、UI surface、V0 route invariant）
- `task/SPEC-095.md` — `Status: DONE` + Review 补全

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC10, AC11

## 阻塞/备注
- Spec 中引用的 `web/templates/es.html` 实际未承载 `/es-backtest` 页面；实现按 live route 真实模板 `web/templates/es_backtest.html` 落地。
- V2f summary surface 默认 `mode=baseline`，因为该路径与研究归档中的 bootstrap 100% 显著结论一致；`run_phase2_v2f()` 仍保留 `filtered` / `baseline` 双模式。
