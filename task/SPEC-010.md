# SPEC-010: Git Post-Commit Hook — 自动清缓存与重启 Web

## 目标

**What**：新增 `.githooks/post-commit` hook，在 commit 包含触发文件时自动执行清缓存 + Web 重启，替代手动步骤。

**Why**：引入双通道执行模型（Fast Path）后，Claude 直接修改生产代码不经过 Codex，原本由 Codex 负责的缓存清除和 Web 重启步骤无人执行。用 git hook 实现自动化，两条路径均无需人工干预。

---

## 接口定义

### 新增文件：`.githooks/post-commit`

```bash
#!/bin/bash
# 检测本次 commit 是否包含触发文件，若是则清缓存并重启 Web

CHANGED=$(git diff-tree --no-commit-id -r --name-only HEAD 2>/dev/null)

NEEDS_REFRESH=0
for f in $CHANGED; do
    case "$f" in
        strategy/selector.py|backtest/engine.py|signals/*)
            NEEDS_REFRESH=1
            break
            ;;
    esac
done

if [ "$NEEDS_REFRESH" -eq 1 ]; then
    rm -f data/backtest_stats_cache.json
    launchctl kickstart -k "gui/$(id -u)/com.spxstrat.web" 2>/dev/null || true
    echo "[post-commit] Cache cleared & web restarted"
fi
```

权限：`chmod +x .githooks/post-commit`

### 新增文件：`Makefile`（或追加到现有 Makefile）

```makefile
install-hooks:
	git config core.hooksPath .githooks
	@echo "Git hooks installed"
```

### 修改文件：`AGENTS.md`

将"实施完成后的必做步骤"章节中的手动 bash 命令替换为：

```
缓存清除和 Web 重启由 git post-commit hook 自动处理。
确保已运行 `make install-hooks`（首次安装时执行一次）。
若 hook 未生效，可手动执行：
  rm -f data/backtest_stats_cache.json
  launchctl kickstart -k gui/$(id -u)/com.spxstrat.web
```

---

## 边界条件与约束

- 触发文件：`strategy/selector.py`、`backtest/engine.py`、`signals/` 目录下任意文件
- 不触发条件：仅修改 `task/`、`doc/`、`backtest/prototype/`、`.githooks/` 等非生产文件
- `launchctl` 失败时静默忽略（`|| true`），不阻断 commit
- hook 使用 `.githooks/` 目录（可被 git 追踪），通过 `git config core.hooksPath` 激活

---

## 不在范围内

- 不修改 `CLAUDE.md`（Fast Path 说明已足够，hook 是基础设施）
- 不处理 `pre-commit` 或其他 hook 类型
- 不修改 `strategy/selector.py` 或任何信号/回测文件

---

## Prototype
（无，基础设施变更，无需量化验证）

---

## Review
- 结论：PASS

| 文件 | 修改点 | 核查结果 |
|------|-------|---------|
| `.githooks/post-commit` | 触发文件检测、清缓存、重启 Web，`\|\| true` 静默失败 | ✅ 逻辑与 Spec 完全一致 |
| `Makefile` | `install-hooks` target，设置 `core.hooksPath` | ✅ |
| `AGENTS.md:66` | 手动步骤替换为 hook 说明 | ✅ |

验收标准 1–5 全部通过（handoff 自报）。无需人工干预，两条路径（Fast Path + 标准路径）commit 后均自动触发。

---

## 验收标准

1. `.githooks/post-commit` 文件存在且有执行权限（`-rwxr-xr-x`）
2. `git config core.hooksPath` 返回 `.githooks`（或 `make install-hooks` 运行成功）
3. 对 `strategy/selector.py` 做任意修改并 commit 后，`data/backtest_stats_cache.json` 被自动删除
4. 对 `task/` 或 `doc/` 下的文件做修改并 commit，hook 不触发（`backtest_stats_cache.json` 保持不变）
5. `AGENTS.md` 中手动 bash 命令替换为 hook 说明

---
Status: DONE
