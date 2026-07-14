# Compatibility Note

本项目中 `Claude` 对应 **Quant Researcher** 角色。

请改读：
- `QUANT_RESEARCHER.md`

## Design System

Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## 多会话协作协议 v2（PM ratify 2026-07-13，全会话强制）

本仓常有多个 Claude 会话（quant ×N + 前端/dev agent）共享同一工作区。硬规则（详见 doc/MULTI_SESSION_PROTOCOL.md，含事故档案）：

1. 提交只用显式路径 `git add <file...>`；**禁 `git add -A`/`-u`、`git commit -a`**——staged 里出现非本 lane 文件即硬停
2. 不留跨小时未提交改动；暂停/等长任务/结束回合前必须 commit
3. 跑全量验证前查 `git status`；有他 lane 脏文件 → HEAD worktree 里跑或结论注记
4. 动文件前登记 `data/.lane_claims.json`（lane 名/files/task/ts），提交后清除自己条目
5. pre-commit hook 阻断跨 lane 混合提交；新环境 `bash scripts/hooks/install.sh`
6. dev agent 维持 worktree + branch-only + spawning 会话合并部署（不变）
7. 全站共享资产（theme.css 版本键/DESIGN.md 词表/冻结向量/棘轮测试）变更必须同 commit 更新配套测试
8. 部署前确认 origin/main 顶是预期 commit；改 strategy/ 的部署方主动预热回测缓存
