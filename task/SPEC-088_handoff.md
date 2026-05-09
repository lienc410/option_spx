# SPEC-088 Handoff

## 修改文件
- `web/portfolio_surface.py` — 新增 `/ES` stressed-SPAN 只读 payload，使用 Q012 Phase A Model A2 固定 strike / DTE re-mark 估算，并提供 fail-soft 输出。
- `web/templates/es.html` — 新增独立 Stressed SPAN Visibility panel，明确 read-only / not trade recommendation。
- `tests/test_spec_088.py` — 新增 SPEC-088 API、fail-soft、recommendation shape 和 UI disclaimer 覆盖。

## 收尾
- 缓存清除：否
- Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8

## 阻塞/备注
- `current_es_price` 当前优先读取 state 字段；若没有，则使用 Schwab SPX quote 作为 `/ES` price proxy，并在 payload notes/source 中明确标记。
- `/api/es/stressed-span` endpoint 已存在于当前代码；本轮补齐其 payload implementation 与 UI consumer。
- 本实现只读，不改 `strategy/state.py`，不引入 shared-BP gating / allocator / broker write。
