# Q087 P0 D-1 — 运维清册（2026-07-05, Dev）

## 1. launchd 任务全表

### oldair(生产,21 个)

| Label | 触发 | 日志(err) | 当前状态/最近失败 | 失败告警 |
|---|---|---|---|---|
| `web` | KeepAlive 常驻(waitress) | `~/Library/Logs/spx-strat/web.err.log` | last exit -15(nightly restart 的 SIGTERM,预期) | ❌ 静默(worst:进程崩溃只有 KeepAlive 兜底) |
| `bot` | KeepAlive 常驻 | `bot.err.log`(551 error 行) | 运行中 | ❌ 静默 |
| `cloudflared` / `-b` | KeepAlive 常驻 ×2 | `cloudflared/err*.log` | 运行中(last exit 11) | ❌ 静默(断连仅日志) |
| `web_nightly_restart` | 04:00 daily | `web_nightly_restart.err.log` | OK | ❌ |
| `daily_snapshot` | 17:00 交易日 | `daily_snapshot.err.log` | OK | ❌(schema 断裂只会写 stderr) |
| `refresh_backtest` | 02:00 | `refresh_backtest.err.log` | **exit=1 失败中** | ❌ **静默失败实例** |
| `signal_settling` | 09:30 | `q019_settling.err.log`(34 error 行) | **exit=1 失败中** | ❌ **静默失败实例** |
| `etrade_token_renew` | 23:00/23:30 | `etrade_token_renew.err.log` | **exit=1 失败中** | ❌ **静默失败实例** |
| `etrade_keepalive` | 每小时 6-22 | `etrade_keepalive.err.log` | OK | ❌(token 死亡只在下一次人工发现) |
| `etrade_refresh` / `schwab_refresh` | 06:00 / interval | 各自 err.log | OK | ❌ |
| `greek_attribution` | 16:45 | `logs/greek_attribution.err.log`(4 error 行,mtime 6/1 ⚠ 一个月没产出?) | exit=0 | ❌ **疑似静默停摆,需查** |
| `q041_collect` | 16:30 交易日 | `q041_collect.err.log`(207 error 行) | OK | ⚠ 部分(仅 SPX/QQQ 三连败推 Telegram,SPEC-114) |
| `q041_chain_sanity` | 16:45 交易日 | `q041_chain_sanity.err.log` | OK | ✅ 每日报告+告警(SPEC-114,**全系统唯一完整告警的任务**) |
| `q041_t2_paper_signals` | 16:50 | `q041_t2_paper_signals.err.log`(14 error 行) | OK | ⚠ 信号推送有,**任务自身崩溃静默** |
| `q041_t3_earnings_check` | 16:55 | `q041_t3_earnings_check.err.log` | OK | ⚠ 同上 |
| `q085_s2bps` | 16:50 | `logs/q085_s2bps.err.log` | OK(7/4 部署) | ⚠ missing_chain/skew 失败有推送,进程级崩溃静默 |
| `q042_executor` / `q042_history_refresh` | 16:xx / 17:xx | 各自 err.log | OK | ❌ |
| `fundexit.refresh` | 09:00 | `fund_exit/refresh.log` | OK | ❌ |

已卸载遗留:`q041align`(SPEC-114 替代)、`q041_massive_*`(6/6 归档,plist 仍在 LaunchAgents 目录——建议清理)。

### 本机(lienchen,应为零生产任务)

| 文件 | 状态 | 风险 |
|---|---|---|
| `com.cloudflare.cloudflared.plist.disabled-2026-06-12` | 已禁用 ✓ | —(6/12 502 根因,保留为证据) |
| `com.spxstrat.bot.plist` | **休眠未禁用** | 登录拉起 → 双 bot 抢 Telegram getUpdates |
| `com.spxstrat.web.plist` | **休眠未禁用** | 本机起 web(通常无害但混淆) |
| `com.spxstrat.q041_collect.plist` | **休眠未禁用** | **双写 chains → 数据损坏风险** |
| `com.spxstrat.greek_attribution.plist` | **休眠未禁用** | 双写 attribution |
| `com.spxstrat.etrade-monthly.plist` | **休眠未禁用**(SPEC-110 本应部署在 oldair) | 双聚合 |

**建议(checkpoint #1 首批,零成本)**:本机 5 个全部改 `.disabled-*` 后缀——与僵尸 cloudflared 同类隐患,已有一次 3 个月未发现的前科。

## 2. 静默失败点汇总

当前证据:21 个任务中**仅 1 个(chain_sanity)有完整失败告警**;3 个此刻 exit=1 无人知晓;`greek_attribution` err.log 一个月未更新(可能停摆);`bot.err.log` 551 条 error 级行无人巡检。历史上的静默失败(massive 断供 4 天、E-Trade token 日内死亡)全部靠 PM 前端撞见才发现。

## 3. 统一心跳方案草案(选型)

### 方案 A — 中央 monitor 任务(推荐)

新增一个 `com.spxstrat.ops_heartbeat`(17:15 ET 交易日,所有任务收尾后):
1. `launchctl list` 扫 `com.spxstrat.*` 的 last-exit ≠ 0/-15 → 列入告警
2. **产出新鲜度断言**(比扫日志更可靠):当日应有产出的文件清单逐一核对 mtime/内容——`q041_chains/<today>/`、`daily_snapshot.jsonl` 尾行日期、`q085_skew_monitor.jsonl` 尾行、attribution 输出等
3. err.log 增量 grep(记录上次扫描 offset,只看新增 Traceback)
4. 汇总一条 Telegram:全绿则 `✅ ops 20/20`单行;有异常列明细

利:单点实现(~150 行)、覆盖"任务根本没跑"这一自报方案的盲区(launchd 没触发时任务自己不可能报)、新任务只需登记到清单表。
弊:monitor 自身单点(需 PM 约定"每天没收到 ops 行=monitor 死了"的反向纪律);产出清单需随新任务维护。

### 方案 B — 每任务自报(否决理由)

各任务尾部加"完成心跳"写入公共 jsonl,monitor 只查缺席。利:精确到任务内部阶段。弊:要改 21 个任务(大量样板)、**无法覆盖"进程没起来/起来即崩"**(最常见静默模式恰是这类)、与方案 A 的产出断言重复。

**结论**:A 为主,B 的思想已部分存在(chain_sanity/q085 的业务级推送保留不动)。方案 A 实现走 Track D 首个 SPEC。

## 4. 顺带发现

- `refresh_backtest`(02:00)与 nightly web restart(04:00)的产物关系:backtest 缓存刷新失败(当前 exit=1)时,白天 PM 看到的是**静默过期的缓存**——与 D-2 缓存失效纪律直接相关,修复优先级应联动。
- cloudflared 断连告警可并入方案 A(扫 `Registered tunnel connection` 频率异常)。
