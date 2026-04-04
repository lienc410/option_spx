# SPEC-010 Handoff

## 修改文件
- `.githooks/post-commit:1` — 新增 post-commit hook，检测触发文件并自动清缓存、重启 Web
- `Makefile:1` — 新增 `install-hooks` 入口，设置 `core.hooksPath=.githooks`
- `AGENTS.md:66` — 将手动收尾步骤改为 hook 说明和安装提示

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：1, 2, 3, 4, 5
