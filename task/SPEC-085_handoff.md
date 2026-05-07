# SPEC-085 Handoff

## 修改文件
- `web/portfolio_surface.py:1` — 新增只读 candidates / portfolio summary / attribution carrier helper。
- `web/server.py:206` — 新增 `/api/sleeve-candidates`、`/api/portfolio/summary`、`/api/portfolio/attribution` 三个独立只读 endpoint。
- `web/templates/index.html:442` — 新增独立 `Multi-Sleeve Observation` dashboard panel 与前端加载逻辑。
- `tests/test_spec_085.py:1` — 新增 SPEC-085 API / fail-soft / no-shape-drift 回归测试。
- `task/SPEC-085.md:1` — 标记 `Status: DONE` 并补充 implementation review。

## 收尾
- 缓存清除：否
- Web 重启：否

## 验收结果
- 通过：AC1-AC11

## 阻塞/备注
- F3 attribution 当前返回 `pending_quant_input`，直到 Quant 提供 `data/q041_portfolio_attribution_latest.json` 或通过 `Q041_PORTFOLIO_ATTRIBUTION_FILE` 指向等价静态 artifact。
- 本次未修改 `strategy/state.py` 逻辑，未改 `/api/recommendation` shape，未引入 broker write / auto-ledger-write / unified routing。
