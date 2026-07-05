# Q087 P0 D-2 — 数据谱系（2026-07-05, Dev）

体量:oldair `data/` **690MB**,本机 496MB(子集)。git 追踪 43 项;大目录(chains/historical/massive)已 gitignore。

## 1. 数据文件谱系表(主要项)

| 文件/目录 | 大小 | 生产者 | 消费者 | 增长 | git | 保留建议 |
|---|---:|---|---|---|---|---|
| `q041_historical/` | 424MB | 一次性归档(massive 历史下载,6/6 冻结) | Track B 校准研究 | 静态 | ✗ | 冷数据,压缩归档+入备份后可移出工作区 |
| `q041_chains/` | 144MB(46 天) | `q041_collect` 16:30 daily | chain_sanity、T2/T3 selector、**q085 skew(CALIB 基础)**、Track B 回灌 | **~3.1MB/天** | ✗ | **永久保留**——不可再生(见 §3);按月 tar.zst 归档旧月 |
| `bcd_filter_shadow.jsonl` | 61MB | SPEC-079 filter shadow(每次 selector 调用追加) | Track A bcd_filter 审计 | 快(~1MB/周+) | ✗ | 按月轮转 gzip;审计只需聚合 |
| `intraday_governance_log.jsonl` | 30MB | SPEC-107 intraday(盘中高频) | 审计 | 快 | ✗ | 同上 |
| `overlay_f_shadow.jsonl` | 11MB | SPEC-10x overlay shadow | 审计 | 中 | ✗ | 同上 |
| `q041_massive_snapshot/` | 8.8MB | 已停(6/3 断供) | 对齐研究归档 | 静态 | ✗(有 .gitignore 教训:5/12 曾被 stash 吞掉 4 天) | 冻结入备份 |
| `market_cache/` | 3.3MB | yfinance 缓存层 | signals/backtest | 慢 | ✗ | 可再生,无需备份 |
| `backtest_results_cache.json` / `backtest_stats_cache.json` / `es_backtest_cache.json` / `q041_backtest_cache.json` | ~1MB 合计 | `refresh_backtest` 02:00 + 手动 | web 各 backtest 端点 | 覆写 | ✓(混入 git,每次刷新产生 diff 噪音——建议移出 git) | 可再生 |
| `daily_snapshot.jsonl` | 106KB | `daily_snapshot` 17:00 | journal、SPEC-110 T2 聚合、Q081 研究 | ~0.5KB/天 | ✓ | 永久,入备份 |
| `strategy_pnl_attribution.jsonl` | 108KB | `greek_attribution` 16:45(**err.log 停在 6/1,疑停摆——见 D-1**) | journal attribution 图 | ~1KB/天 | ✓ | 永久 |
| `sleeve_governance_{state,decisions}.jsonl`、`cash_budget_decisions.jsonl` | ~180KB | governance 快照/决策 | 审计、counterfactual | 慢 | ✓ | 永久 |
| `q041_paper_log.jsonl` | 21KB | T2/T3 每日 job | Q041 paper 复盘 | 慢 | ✓ | 永久 |
| `q085_skew_monitor.jsonl` / `q085_paper_log.jsonl` | 新 | `q085_s2bps` 16:50 | **CALIB 季度重测、SPEC-116.1 转实盘门** | ~0.2KB/天 | ✓ | 永久,入备份 |
| `positions.json` / `state.json` / 各 runtime.json | KB 级 | 交易操作/各 sleeve | 全系统 | 覆写 | ✓ | 靠 git 历史即可 |
| `etrade_monthly_nlv.jsonl`、`etrade_statements/` | 1.5MB | SPEC-110 T1/T2 | /journal、/portfolio_home | 月度 | ✓ | 永久(官方对账数据) |

## 2. 三套回测缓存失效核对(per `feedback_backtest_cache_refresh`)

**机制现状**:缓存 key = 参数 payload 的 hash(`server.py:148 _cache_key`)+ `_STATS_SCHEMA_VERSION="v3"` 人工版本号。
**结论:参数变更自动失效 ✓;算法/代码变更不失效 ✗** —— 这正是 memory 规则要求"策略算法文件改动后手动刷新三套缓存"的原因。风险链:dev 忘刷 → 前端静默展示旧算法结果;且 `refresh_backtest` 当前 exit=1(D-1),02:00 自动刷新已在断供。
**低成本自动化建议(Track D)**:把 `git log -1 --format=%H -- strategy/ backtest/` 掺入 cache key —— 算法 commit 一变 key 即失效,彻底移除人工纪律依赖。工作量:小。

## 3. oldair 独有数据备份方案(**当前:tmutil 无目的地,零备份**)

**不可再生清单**(丢机即永久损失):`q041_chains/`(CALIB 数据基础,Schwab 不提供历史链)、全部 shadow/ledger jsonl、`q041_historical/`+`massive_snapshot/`(供应商已断)、`~/.spxstrat/`(token)、`~/.cloudflared/`(隧道凭证)、`.env`。合计 <700MB。

**分层方案(建议 Track D 首批,与心跳同一个 SPEC)**:

| 层 | 内容 | 实现 | RPO |
|---|---|---|---|
| L1 每日 pull | oldair `data/` 增量 + `~/.spxstrat` + `~/.cloudflared` + `.env` → 本机 `~/backups/oldair/` | 本机 launchd 05:00 `rsync -az --delete-excluded`(SSH 通道现成;~700MB 首次,日增 <5MB) | 1 天 |
| L2 每周离机 | L1 目录 → iCloud Drive 或 restic→云(加密,token/凭证必须加密层) | 本机 launchd 周日 | 1 周 |
| L3 恢复演练 | 每季度从 L1 恢复 chains 抽一日 parquet 校验行数 | 手动,入 checkpoint 节律 | — |

心跳任务(D-1 方案 A)顺带断言"L1 备份 mtime < 26h",备份断供即告警——避免备份本身成为新的静默失败点。

## 4. 顺带发现

- 4 个回测缓存 json 在 git 内且每日被 `refresh_backtest` 覆写 → 每次部署 `git pull` 都撞本地修改(本 session 已发生 3 次,靠 stash 绕过)。**建议移出 git + gitignore**,消除部署摩擦。
- `backtest_results_cache.tieout2-pre.json`(0.5MB)是 5 月 tie-out 遗留快照,可归档删除。
- `data/q041_test_download.csv.gz`(2.8MB)测试遗留,可删。
