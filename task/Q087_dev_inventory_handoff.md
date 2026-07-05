# Q087 Phase 0 Dev Handoff — Track C/D 清单任务（2026-07-05）

**背景**: Q087 程序 charter 见 `research/q087/q087_program_charter_2026-07-05.md`。Phase 0 只做清单与分诊，**不改任何代码**。Quant 侧两份清单已出（同目录 p0 文件）。请出以下四份，格式自定但需可分诊（每项带影响/风险初判）。

## C-1 代码普查
- 模块清册：路径、LOC、公共入口、依赖方向（signals→strategy→web 的实际依赖图，标出反向依赖）
- 测试覆盖地图：pytest 现有测试对应哪些模块；无覆盖的生产路径列表（重点：web/server.py 各 endpoint、schwab/、notify/）
- 重复实现清点：**已知至少 4 份 BS 定价**（backtest/pricer.py + q082_p6 + q085_p2d/p3 + q085_p3b）——全列出，Track B 将统一；其他重复（SPX 历史加载、Telegram 发送、JSONL 读写）一并清点
- TODO/FIXME/XXX grep 汇总

## C-2 已知与潜伏 bug 清册（seed 如下，请补全）
1. **Greeks 跨券商乘数错配**（PM 2026-06 已知悉暂缓）：portfolio_home 的 "Δ×n" 用 Schwab+ETrade 合计合约数乘 Schwab 单边 Greeks，strikes/expiry 分歧时即错——影响面与修复成本
2. **sleeve_governance.py:30-31 `SPX_NLV/ES_NLV = 100_000` 硬编码**：请查清全部下游用途（CAP_% 换算是否因此失真）并给影响评估——这是 Quant 侧 ⚠️ 项，可能是高价值快赢
3. web/server.py ~4.5k 行的分拆可行性初判（endpoint 分组、共享状态）
4. **selector.py:376 注释 "EXTREME_VOL hard boundary (40)" vs :56 参数默认 35.0**：核实是注释漂移还是存在第二个边界变量；若为漂移请在 C-2 清册标注（修复走后续 SPEC）

## D-1 运维清册
- launchd 任务全表（本机 + oldair）：label、schedule、日志路径、最近失败记录、**是否有失败告警**（当前多数任务失败是静默的——列出全部静默失败点）
- 建议的统一心跳方案草案（一个 monitor 任务扫全部任务日志 vs 每任务自报，选型给利弊）

## D-2 数据谱系
- data/ 全部文件：生产者（哪个任务写）、消费者、增长速率、是否 git 追踪、建议保留策略
- 三套回测磁盘缓存（Q041/ES/SPX）的失效触发条件核对（per `feedback_backtest_cache_refresh`）
- oldair 独有数据（chains、ledgers）的备份现状——**当前 chains 无备份，单机丢失即丢 CALIB 数据基础**，请给方案

## 交付
四份清单入 `research/q087/`（命名 `q087_p0_c1_*.md` 等），commit 后回报。之后进 PM checkpoint #1 统一分诊排序。
