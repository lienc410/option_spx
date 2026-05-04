# SPEC-081 Handoff

## 修改文件
- `research/q041/download_massive.py:1` — 新增 Massive Flat Files 历史批量下载脚本，包含 S3 下载、OCC 解析、symbol mapping、断点续传与 parquet 落盘。
- `tests/test_spec_081.py:1` — 新增 SPEC-081 基础单测，覆盖 OCC 解析、symbol mapping 与 safe filename。
- `.gitignore:1` — 忽略 `data/q041_historical/` 产物目录。

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9

## 阻塞/备注
- 已完成小窗验收：`arch -arm64 venv/bin/python -m research.q041.download_massive --start 2022-05-06 --end 2022-05-10 --verbose`
- 已完成全量下载：`arch -arm64 venv/bin/python -m research.q041.download_massive`
- 数据产物写入 `data/q041_historical/`，未纳入 git 提交。
