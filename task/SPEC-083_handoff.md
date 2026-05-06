# SPEC-083 Handoff

## 修改文件
- `logs/q041_paper_trade_io.py:13` — 新增独立 Q041 paper ledger 存储、schema 校验、原子写入、budget/export/status 逻辑。
- `scripts/q041_paper_ledger.py:33` — 新增 CLI：`add-csp` / `add-ic` / `close` / `update` / `budget` / `export-csp` / `export-ic` / `status`。
- `tests/test_spec_083.py:17` — 新增 SPEC-083 测试，覆盖 AC2–AC9。

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC10

## 阻塞/备注
- F5 采用 `SPEC-083` 允许的 **选项 B**：CLI `status`，未新增 Flask `/q041` 页面。
- `account_total_bp` 仍按 Spec 从 `data/q041_paper_trade_config.json` 读取；未配置时 `budget` / `status` 会 fail closed。
