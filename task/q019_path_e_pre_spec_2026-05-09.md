# Q019 Path E — Pre-SPEC Memo (Quant → Planner)

- **Date**: 2026-05-09
- **From**: Quant Researcher
- **To**: Planner
- **Authorisation**: PM 2026-05-09 selected Path E
- **Related**: `R-20260509-09`, `Q019` in `sync/open_questions.md`, governance section in `QUANT_RESEARCHER.md`

---

## 1. 一句话定义

**把生产 live 系统的每日 strategy recommendation，从"按开盘 intraday-current VIX 决策"改为"等 VIX 早盘稳定后再决策"。**

预期效果：把当前 -0.6pp 到 -0.2pp AnnROE 的 live-vs-backtest 拖累，压到 -0.2pp 到 -0.07pp，年化收益恢复约 **+$2,000 / 年**（$500k NLV）。

---

## 2. 研究层证据（Quant 已交付）

| 测试 | 文件 | 结论 |
|------|------|------|
| Tier 1 selector scan | `research/q019/close_vs_open_sensitivity.py` | 9.48% regime flip（复现 MC 9.71%） |
| Tier 2 full open substitute | `research/q019/tier2_close_vs_open_backtest.py` | -1.37pp upper bound |
| Tier 2.5 mixed-mode | `research/q019/tier2_5_mixed_mode.py` | -0.63pp（current-VIX 单独影响） |
| Tier 2.6 real hourly stable rule | `research/q019/tier2_6_hourly_live_simulation.py` | recovery 67.4%（2024-2026 sample） |
| Tier 2.7 OHLC midpoint proxy | `research/q019/tier2_7_stable_proxy_extended.py` | recovery 72.8% cumulative，worst-5y 中位 62% |

**研究层结论**：stable rule 在 2 年真实 hourly + 19 年静态代理上一致显示能挽回 60-70% 的 open-vs-close 拖累。

---

## 3. SPEC 必须解决的 6 个设计点

### 3.1 Stable 阈值定义 + bar 周期（最终参数，已校准 + PM APPROVED 2026-05-09）

**最终决定（2026-05-09 quant 三轮收敛后，PM approved）：**

```
SETTLING_INTERVAL = "1h"
SETTLING_THRESHOLD = 0.5
SETTLING_TIMEOUT_MIN = 180
SETTLING_DATA_SOURCE = "yfinance:^VIX"
```

**收敛过程**：

1. **F2-r1**：30m bar + θ=0.35（`spec091_threshold_scan_30m.py`）。60 天样本 timeout 10.2%，但 Yahoo 30m 上限 60 天，单一 calm regime，样本不足
2. **F2-r2**：退回 1h + θ=0.5（继承 Tier 2.6）。但 1h bar 的最小 stable 触发时间是开盘后 120m（Yahoo 时间戳结构决定），原 90m timeout 等价于"永远 timeout"，必须改
3. **F2-r3**：1h 全 θ sweep + 真实 engine recovery（`spec091_recovery_sweep.py`，2 年 515 天，6 模式 7 次 engine 跑）

**Recovery sweep 结果**：

| θ | ΔAnnROE | Recovery |
|---|---------|----------|
| 0.40 | -6.86pp | 43.9% |
| **0.50** | **-3.94pp** | **67.4%** ⭐ |
| 0.60 | -4.23pp | 65.0% |
| 0.70 | -4.16pp | 65.6% |
| 0.80 | -4.00pp | 66.9% |

**θ=0.5 是经验最优**：低于 0.5 时 recovery 陡降（fallback 到早盘读数），高于 0.5 时平台 65-67% 但略低于 0.5（捕捉到了 still-drifting 日子的早期错误 VIX）。

**Timeout = 180m 的依据**：
- 1h bar 最快 stable 在 120m 后；80% 日子 180m 内 settle，剩余 12% fallback
- 90m timeout 配 1h bar 是 bug，已修正

**30m 升级路径**（不在本 SPEC 范围）：Path E 上线后 paper trading + live 累计 6+ 个月真实 hourly 数据后，可基于实测做 SPEC-091 v2 评估是否切到 30m。届时样本足够、有 live recovery rate 基线、风险已知。

**未走的候选**（不再考虑，避免 SPEC 评审重提）：
- θ=0.7-0.8（operational 最优但 recovery 略低，有实证 sweep 数据排除）
- C2 `dVIX / VIX < 2.5%` 相对变化阈值（不引入额外参数）
- C3 30 分钟滚动 stdev（30m bar 数据深度问题已落地）

### 3.2 Max wait timeout

极端日（如 2018-02-05 Volmageddon）VIX 可能整天无法稳定。SPEC 需明确：
- 默认建议 timeout = **90 分钟**（market open 09:30 ET → 11:00 ET）
- 超时后 fallback 行为：**用截止时刻的 intraday VIX 直接决策**（即恢复当前 live 行为）
- 超时事件需 log + Telegram 提醒（"VIX 早盘未稳定，按当前值决策"）

理由：极端日恰恰是 stable rule 最不可能等到稳定的日子，但也是最不能错过的决策日。fallback 不能是"跳过当日"。

### 3.3 Production hourly VIX 数据源

候选：
- **Yahoo**（当前 backtest 用的源）：免费，但延迟 ~15 分钟，hourly bars 通过 `interval="1h"` 拿到
- **Schwab API**：需要确认 Schwab 是否提供 VIX 指数 intraday 报价（**Planner 需查证**）
- **Polygon Indices Developer** $79/月：CBOE 官方源，无延迟，但需要常驻订阅

**Quant 建议**：先用 Yahoo（与 backtest 一致 + 免费），延迟 15 分钟在 stable rule 框架下不构成致命问题（stable 判断本来就在 09:30 之后 30-90 分钟才发生）。如 paper trading 发现 Yahoo 延迟造成 stable 判断错位，再考虑升级到 Schwab 或 Polygon。

### 3.4 决策路径范围

**走 stable rule 的**：
- 每日 strategy recommendation（Web UI、Telegram bot 主推送）
- Position-action queries（建议持仓动作）

**不走 stable rule 的**：
- **Intraday alerts (SPEC-086 等)**：保持 real-time，不受影响
- 任何 mark-multiple / pnl_ratio stop trigger
- 任何 EXTREME_VOL alert

理由：intraday alerts 的设计目的就是捕捉实时风险，stable rule 会破坏其响应性。

### 3.5 Operational behavior

**当前 live 行为**：market open 后立刻发推荐（Telegram + Web UI 同步刷新）

**Path E 行为**：
- 09:30 ET market open 后，系统进入 "VIX stabilising" 状态
- Web UI 显示 "Waiting for VIX to stabilise (current: 24.3, prev hour: 25.1, Δ=-0.8 > 0.5)"
- Telegram bot 不发主推荐（避免用户基于早期 VIX 行动）
- 一旦 stable 触发：发推荐 + 标注 "VIX stabilised at 23.8 after 47 min"
- 一旦 timeout（90 min）：发推荐 + 标注 "Max wait reached, using current VIX 24.3"

### 3.6 Paper-trading 验证 + 上线 gate

**最低验证周期**：1-2 个月 paper trading
- 记录每日 stable 触发时刻、stable VIX vs open VIX 差值、是否 timeout
- 与并行的"假装是当前 live"baseline 比对，统计 recommendation 差异
- 至少覆盖 1 次 VIX > 22 跨阈值事件

**上线 gate**（必须全部满足）：
1. Paper trading ≥ 30 个交易日
2. ≥ 80% 的日子在 60 分钟内触发 stable（验证 timeout 设置合理）
3. 没有"stable 后立刻又 unstable"的 oscillation 案例（验证阈值不会震荡）
4. 2nd Quant review approve

---

## 4. 不在 SPEC 范围内（明确剔除）

- 改 backtest 的 VIX 口径（仍用 close）
- 改 intraday alert (SPEC-086) 的 VIX 口径（仍 real-time）
- 改 vix_window / 5d MA / IV history 的计算口径（仍 close-based）
- 任何 VIX 阈值参数本身的调整（HIGH_VOL=22, LOW_VOL=15 等不动）

---

## 5. 风险注记（SPEC review 须显式回应）

- **R1**：Tier 2.6 真实 hourly 数据只有 2 年（2024-2026），未覆盖 2018/2019/2021 worst years。Path E 在那几年的实际表现是用 Tier 2.7 静态代理估计的，存在 model risk
- **R2**：Path E 引入 live 决策延迟，违背"开盘即推荐"的现有 UX 约定。需用户教育成本
- **R3**：极端日 timeout fallback 行为本质上回到当前 live 行为，无伤害下界但也无 Path E 收益
- **R4**：Yahoo VIX 数据源延迟 15 分钟。如出现"已稳定但 stable 判断尚未触发"的 lag，可能错过最优决策窗口
- **R5**：Path E 期望收益约 $2k/年，规模相对较小，SPEC + paper trading + 2nd review 的工程量需保持比例

---

## 6. Planner 起草 SPEC 时的可参考结构

```
# SPEC-XXX — Path E: Settling-VIX rule for daily strategy recommendation

## Goal
[一句话目标]

## Logic
[6 个设计点的精确实现]

## Interface
- `web/server.py` 的 daily recommendation endpoint：从 "use current VIX" 改为 "use stable VIX"
- 新增 `production/vix_settling.py` 实现 stable 判断与 timeout
- Telegram bot 状态机 + Web UI status indicator

## Boundary
- Backtest engine 不变
- Intraday alerts 不变
- vix_window 计算不变

## Out of scope
- Backtest convention 调整
- VIX 阈值参数本身

## Prototype
research/q019/tier2_6_hourly_live_simulation.py 已提供 stable rule 参考实现
（仅 backtest 用途，不可直接搬到 production；production 需做 timeout / fallback / state machine）

## Review checklist
- 已显式回应 R1-R5 风险？
- Paper trading gate 是否量化？
- 2nd Quant review 是否安排？
- 已引用 QUANT_RESEARCHER.md "Backtest-vs-Live Convention Divergence (Q019 governance)" 章节？

## Acceptance criteria
- 上线 gate 4 条全部满足
- Path E 上线后第 1/3/6 个月，由 Quant 跑 live-vs-backtest 实测，更新 governance 章节的 recovery rate 数字
```

---

## 7. Out-of-scope 但相关的后续追踪项

- Path E 上线 6 个月后由 Quant 做 retrospective：实际 recovery 是否落在研究层预测的 60-70% 范围
- 如真实 recovery < 50%，说明 stable rule 假设有问题，需开 Q019 续集
- 如真实 recovery > 80%，可能值得考虑把 backtest 也改成 stable rule（对齐口径，研究界面更干净）

---

*Quant Researcher, 2026-05-09*
