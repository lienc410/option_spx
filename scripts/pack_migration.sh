#!/usr/bin/env bash
# pack_migration.sh — 打包迁移到 Windows 所需的最小必传文件
# 用法：bash scripts/pack_migration.sh
# 输出：~/Desktop/spx_migration.zip

set -euo pipefail

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MEMORY_DIR="$HOME/.claude/projects/-Users-lienchen-Documents-workspace-SPX-strat/memory"
GLOBAL_CLAUDE="$HOME/.claude/CLAUDE.md"
STAGING="$(mktemp -d)/spx_migration"
OUTPUT="$HOME/Desktop/spx_migration.zip"

mkdir -p "$STAGING/memory"
mkdir -p "$STAGING/claude_global"

echo "=== 打包迁移文件 ==="

# 1. .env
if [ -f "$PROJ_DIR/.env" ]; then
  cp "$PROJ_DIR/.env" "$STAGING/.env"
  echo "[✓] .env"
else
  echo "[!] .env 不存在，跳过"
fi

# 2. Claude 项目记忆
if [ -d "$MEMORY_DIR" ]; then
  cp "$MEMORY_DIR"/*.md "$STAGING/memory/" 2>/dev/null && echo "[✓] memory/*.md ($(ls "$MEMORY_DIR"/*.md | wc -l | tr -d ' ') 个文件)"
else
  echo "[!] Claude 记忆目录不存在：$MEMORY_DIR"
fi

# 3. 全局 CLAUDE.md
if [ -f "$GLOBAL_CLAUDE" ]; then
  cp "$GLOBAL_CLAUDE" "$STAGING/claude_global/CLAUDE.md"
  echo "[✓] ~/.claude/CLAUDE.md"
else
  echo "[!] 全局 CLAUDE.md 不存在，跳过"
fi

# 4. 写入 README（Windows 端操作说明）
cat > "$STAGING/README.txt" << 'EOF'
=== SPX Strategy — Windows 迁移包 ===

【操作步骤】

1. .env
   → 复制到：C:\workspace\SPX_strat\.env

2. memory\*.md
   → 目标路径（替换 {用户名} 为你的 Windows 用户名）：
   C:\Users\{用户名}\.claude\projects\-Users-{用户名}-workspace-SPX_strat\memory\
   若目录不存在，请手动创建。

3. claude_global\CLAUDE.md
   → 复制到：C:\Users\{用户名}\.claude\CLAUDE.md
   若已有该文件，合并内容（勿直接覆盖）。

【验证】
- 在项目目录运行：python -c "import dotenv; dotenv.load_dotenv(); print('env ok')"
- 打开 Claude Code，新会话里输入"你还记得这个项目吗"，确认记忆已加载

EOF

# 打包
cd "$(dirname "$STAGING")"
zip -qr "$OUTPUT" "$(basename "$STAGING")"

echo ""
echo "=== 完成 ==="
echo "输出文件：$OUTPUT"
echo "大小：$(du -sh "$OUTPUT" | cut -f1)"

# 清理临时目录
rm -rf "$(dirname "$STAGING")"
