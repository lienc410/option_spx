# SPEC-117（包1 数据安全与止血）+ SPEC-118（包2 快赢修复）Dev Handoff — 2026-07-05

**来源**: Q087 checkpoint #1 已 ratify 推荐序。分诊依据见 `research/q087/q087_p0_triage_board_2026-07-05.md` 与你们的 C1/C2/D1/D2 清单。两批可先后或交叉，包1 优先。

## SPEC-117 · 数据安全与止血

1. **chains 三层 rsync 备份**：按你们 D2 方案实施（本机 + 外部目的地 + 保留策略自定）；AC = 备份任务入 launchd + 首次全量完成 + 恢复演练一次（从备份取任一日 SPX.parquet 校验 checksum）
2. **settling 代码回归修复**：根因已定位——`production/vix_settling.py:402` 的 `SettlingState(...)` 调用缺新增必填参数 `signal1_captured_at`。修复方式（补参 vs 字段给默认值）由你们判断，行为以"回归引入前"为准；AC = 任务连续 2 日成功 + 回归测试覆盖该构造点
3. **greek_attribution 新鲜度核查**：6/1 err（q042 cache 缺失）后近期 append 0 行——判定是"无新数据可加"还是"静默停摆"，修复或说明
4. **refresh_backtest / etrade_token_renew 定位**：两任务无日志可循，查 plist 指向与实际状态
5. **本机 5 个休眠 plist 禁用**（launchctl unload + 移入 archive，同 q041 massive 前例）
6. **心跳监控（D1 方案 A）**：中央 monitor 任务（建议 17:30 ET）扫描任务注册表（job → 期望产出文件 + 最大陈旧时长），违约即 Telegram；注册表格式自定（yaml/json），**所有 21 个 oldair 任务 + 本机存活任务全部入表**；AC = 人为弄旧一个产出文件能触发告警（integration，非 mock）

## SPEC-118 · 快赢修复

1. **aftermath 35/40 口径统一**：`is_aftermath` 内第二个硬编码 40.0 与决策路径 extreme_vix=35 分裂——统一到单一来源（StrategyParams）；决策路径行为必须 bit-identical（本就不可达），仅展示端点在 VIX∈[35,40) 变化——完成报告里注明该展示变化
2. **NLV=100k fallback**：broker 降级时改为"最近一次成功读数 + 陈旧告警"，彻底移除 100k 常数；AC 含 broker-降级模拟测试
3. **回测缓存 git-hash 掺 key**：三套缓存（Q041/ES/SPX）的 key 掺入相关算法文件的 git blob hash，算法改动自动失效；AC = 改一行算法文件（临时）验证缓存重建后还原
4. **4 个缓存 json 出 git**：.gitignore + `git rm --cached`，确认 oldair 部署流程不再 stash 摩擦；注意保留首次生成路径（新机器冷启动可再生）

## 回报格式照旧：commit hash + 各 AC 结果 + 部署验证。