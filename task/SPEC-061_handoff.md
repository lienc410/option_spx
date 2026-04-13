# SPEC-061 Handoff

## 修改文件
- `strategy/catalog.py:30` — 新增 `es_short_put` 策略描述，固定 `/ES`、45 DTE、20 delta、3x credit stop 文案
- `strategy/selector.py:1120` — 新增 `/ES` short put 专用趋势过滤推荐入口，并提供 `get_es_recommendation()`
- `web/server.py:347` — 新增 live Schwab NLV / margin / `/ES` 持仓单槽检查
- `web/server.py:605` — 新增 `/api/es/recommendation` 与 `/api/es/position/open-draft`，落地 45 DTE / 20 delta 选链与 `NLV 20%` 保守拦截
- `tests/test_spec_061.py:1` — 覆盖趋势通过/失败、BP 超限、BP 缺失、已有 `/ES` 槽位拦截与成功候选路径

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC7, AC8, AC9
- 未通过：AC6 → 未额外新增专门断言；本次实现未引入 ladder / 动态杠杆 / BSH，实测回归仅覆盖新增 `/ES` 最小路径与既有 selector/API
