# SPEC-062 Handoff

## 修改文件
- `backtest/research_views.py:1` — 新增 research view CLI、artifact 生成与固定研究交易集筛选逻辑
- `web/server.py:48` — 新增 `GET /api/research/views`，直接返回预生成 artifact
- `web/templates/backtest.html:191` — 在 backtest 页加入 research pill、banner、子集 metric card 与 trade log 切换逻辑
- `tests/test_spec_062.py:1` — 覆盖 artifact 生成与 research views API 的回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3
- 未通过：AC4, AC5, AC6, AC7, AC8 → 尚未做浏览器人工验收；已完成代码实现与后端/生成链路验证
