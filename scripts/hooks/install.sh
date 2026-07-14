#!/bin/bash
# 多会话协作协议 v2 hook 安装（doc/MULTI_SESSION_PROTOCOL.md §5）
set -e
ROOT=$(git rev-parse --show-toplevel)
cp "$ROOT/scripts/hooks/pre-commit" "$ROOT/.git/hooks/pre-commit"
chmod +x "$ROOT/.git/hooks/pre-commit"
echo "pre-commit hook installed -> .git/hooks/pre-commit"
