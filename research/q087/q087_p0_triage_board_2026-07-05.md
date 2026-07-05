# Q087 P0 统一分诊板（2026-07-05）— PM Checkpoint #1 待 ratify

**输入**: quant 侧（参数清单 + verdict map + B1 审计）+ dev 侧（C1/C2/D1/D2，16b26a1）。
**Quant 复核注记**: settling 失败已定位为代码回归（SettlingState 缺参调用，production/vix_settling.py:402）；greek_attribution 在跑但需新鲜度核查；refresh_backtest/etrade_token_renew 无日志可循——佐证 D1 告警缺失结论。

## 建议执行包（按序）

### 包 1 · 数据安全与止血 — dev，立即，不等其他
| 项 | 依据 | 量级 |
|---|---|---|
| chains 三层 rsync 备份 | 144MB 不可再生 + 日增 3.1MB + **零备份**（CALIB 数据基础的单点） | 小 |
| settling 代码回归修复 | TypeError 已定位，功能已瘫约未知时长 | 小 |
| greek_attribution 新鲜度核查 + 另两任务定位 | 6/1 起疑似停摆 | 小 |
| 本机 5 休眠 plist 禁用 | 僵尸 cloudflared 前科 | 零 |
| 心跳监控 SPEC（D1 方案 A：中央 monitor + 产出新鲜度断言） | 21 任务仅 1 个有失败告警 | 中 |

### 包 2 · 快赢修复 — dev，小 SPEC 批
| 项 | 依据 |
|---|---|
| aftermath 35/40 口径分裂 | 决策路径与 /api 展示端点在 VIX∈[35,40) 分裂（dev seed-4 判定翻转：真有第二个硬编码 40.0） |
| NLV=100k fallback | fail-closed 误拦（broker 降级时 CAP 提前误触发）——比初判温和但仍改 |
| 回测缓存 git-hash 掺 key | 算法改动静默不失效的病根（`feedback_backtest_cache_refresh` 根治） |
| 4 个缓存 json 出 git | 每次部署 stash 摩擦 |

### 包 3 · Track B 主工程 — quant 设计 → dev 实现（P1 重审的强制前置）
统一定价库（**生产侧 5 份 + 研究侧多份 → 1 份**，三模式 flat/CALIB/pessimistic）；skew monitor 扩 call 侧 + 多 DTE 桶；矩阵 26y CALIB 重跑 → 逐格对比 → P1 重审（矩阵地基/Q082/Q071）。

### 包 4 · Track A 研究审计 — quant 串行（与包 3 的 dev 实现期并行）
IVP 双门+NNB（头号）→ IV_LOW=30/252d → V2F 止损双口径 → SPEC-079 复核。SPEC-111 并入 8/1 排期复审。每项 verdict 外审。

### 包 5 · Track C 结构工程 — dev 分批消化（全部 bit-identical guard）
反向依赖解除（sleeve_governance→web.portfolio_surface）；JSONL 读写统一（7 份，锁/NaN 纪律不一）；节假日表统一（≥5 份硬编码）；server.py 118 routes 分拆 + 测试补齐（95+ 零测试）；Greeks 跨券商乘数（PM 曾缓议，重排队尾待确认）。

### 包 E · 贯穿 — METHODOLOGY.md + 模板 + 决策权矩阵（quant，PM 终审）

## 并行结构

```
dev:   包1 → 包2 → 包3实现 → 包5（分批）
quant: 包3设计SPEC → 包4逐项审计（外审随行）→ 包E收口
PM:    checkpoint #1（本板）→ 行为变更类 SPEC ratify → ~2周程序复盘
```
