# 多会话协作协议 v2（PM ratify 2026-07-13）

## 事故档案（为什么升级）

同仓多会话（quant 研究会话 ×N + 前端/dev agent）直接共享一个工作区，2026-07-13 一晚两类实质干扰：

1. **瞬态脏撞测试**：A 会话全量测试跑到一半，B 会话正在编辑 SPEC-116 冻结清单内的策略文件 → A 的 `test_frozen_files_unmodified` 假失败（隔离重跑即过）。同晚更早：B 的 pools1 版本键在飞（未提交）连续两轮让 A 的全量验证出现 2-6 个假失败。
2. **未提交 hunk 被扫走（混合提交）**：A 的 SPEC-139 修复改了 `notify/telegram_bot.py` 未及提交，B 提交 SPEC-146（同文件）时把 A 的 hunk 一并扫入 7ea0152——A 的修复变成"半上线"（`_safe_send` 收 meta 但 `apush` 不传），比不上线更隐蔽。此病 2026-06 已在 dev agent 层发作过一次（当时的处方 = dev worktree 隔离），按二次浮面规则升级为全会话协议。

## 硬规则（全部会话，含头部会话）

1. **原子提交**：`git add <显式文件路径>` 逐个列名；**禁 `git add -A` / `git add -u` / `git commit -a`**。staging 前看 `git status`——staged 清单里出现不属于本 lane 当前任务的文件 = 硬停，unstage 后再提交。
2. **不留隔夜脏**：完成一个逻辑单元立即 commit；暂停、等待长任务、结束回合前必须 commit（确实半成品就先不动那个文件）。工作区跨小时保持未提交改动 = 违规。
3. **全量验证前置检查**：跑全量测试 / 回测对账前先 `git status --porcelain`；若有他 lane 的脏文件——要么在 HEAD 临时 worktree 里跑，要么在结论里显式注记"验证含他方 WIP"。他 lane 脏文件造成的失败先归因再排查（今晚两案例均为此）。
4. **Lane 登记（知会制，非锁）**：开始动文件前把文件清单写进 `data/.lane_claims.json`（untracked），提交后清除自己的条目。格式：
   ```json
   {"<lane 名>": {"files": ["path/a.py", "path/b.py"], "task": "SPEC-xxx 一句话", "ts": "ISO 时间"}}
   ```
   lane 名自取稳定即可（如 `quant-fable` / `quant-opus` / `dev-spec147`）。>24h 的条目视为过期。
5. **pre-commit hook（牙齿）**：`scripts/hooks/pre-commit` 在 staged 文件命中 **≥2 个不同 lane 的 claims** 时阻断提交（这正是"扫走"的签名——你的提交不该同时含两个 lane 认领的文件）。新克隆/新机器安装：`bash scripts/hooks/install.sh`。紧急旁通 `git commit --no-verify`，用了必须在 commit message 说明原因。
6. **dev agent 不变**：worktree 隔离 + 推分支不碰 main + spawning 会话负责合并/验收/部署（METHODOLOGY v1.2 既有条款）。
7. **全站共享资产**：theme.css 版本键、DESIGN.md 词表、135.5 冻结向量、141.1 棘轮等"一处改全站变"的资产，变更必须**同 commit** 更新对应棘轮/冻结测试并在 message 注明（今晚 pools1 漏棘轮、070b058 漏向量重生成，均由他 lane 事后补）。
8. **部署串行**：部署 = pull 已提交 origin/main；部署前 `git log origin/main -1` 确认拿到预期 commit；两 lane 短时间先后部署无害（幂等），但改了 strategy/ 的部署方要主动预热三套回测缓存。

## 设计取舍记录

- **为什么不给头部会话也开 worktree**：tests/回测大量读取 untracked 运行时文件（data/market_cache、data/*_state.json、logs/*.jsonl），worktree 没有这些文件，验证必须回真根做——dev agent 已经每次为此付出"worktree 内过、真根再验"的双跑成本。头部会话高频跑验证，worktree 的隔离收益 < 环境失真成本。故选"共享树 + 原子纪律 + hook 牙齿"。
- **为什么 claims 是知会不是锁**：两会话由同一个 PM 驱动，真冲突极少；锁会在忘清除时造成假阻塞。hook 只在"混合提交签名"（跨 2+ lane）时硬拦——这个签名极少误报。
