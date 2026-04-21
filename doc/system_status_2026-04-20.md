# SPX Options Strategy — System Implementation Status
**Date: 2026-04-20 | 承接 `system_status_2026-04-07.md`**

*本版新增内容：*
- *live runtime canonical host 已正式迁移到 old Air*
- *`SPEC-060`：recommendation event log 已成为当前审计链路的一部分*
- *`SPEC-062 / 063 / 065`：research views 与 SPX 图联动已落地*
- *`SPEC-064 / 066`：HIGH_VOL aftermath IC_HV 生产实现已完成*

*以下章节无变更，请参阅 `system_status_2026-04-07.md`：*
- *项目概览 / 技术栈 / 目录结构的大框架*
- *Schwab 扫描器与 quote 客户端*
- *Bot / web 基础结构*
- *核心回测引擎与 portfolio / pricer 层*

---

## 1. 当前系统拓扑（截至 2026-04-20）

### Runtime vs Compute

当前系统已经明确分成两种主机职责：

**old Air = canonical live runtime**
- Telegram bot
- Flask web dashboard
- Cloudflare Tunnel
- live recommendation 行为
- runtime logs

**主力机 = default compute / development host**
- 代码实现
- Quant 研究
- heavy backtests
- research view generation
- artifact 再生

这不是临时习惯，而是当前正式架构。
相关规则见：
- `SERVER_RUNTIME.md`
- `doc/old_air_server_maintainer.md`

### old Air 上的 canonical services

当前以 `launchd` 托管：
- `com.spxstrat.bot`
- `com.spxstrat.web`
- `com.spxstrat.cloudflared`
- `com.spxstrat.cloudflared-b`

因此：
- 若要看 public web / bot health / live recommendation / runtime log，应优先以 old Air 为准
- 不应再把主力机本地 Flask / bot 状态当作生产事实

---

## 2. Recommendation / Auditability 路径更新

### `SPEC-060` — Recommendation Event Log

当前系统已经有结构化 recommendation event log。

这解决了一个重要历史问题：
- 早期（如 `2026-04-08`）bot 虽然发过消息，但无法从结构化日志直接还原“当时到底发了什么 recommendation”

现在 recommendation 相关事件会进入结构化日志，用于：
- morning push
- EOD push
- `/today`
- 其他可审计 recommendation 输出

**当前意义**：
- live recommendation 不再只能靠 `bot-error.log` 或聊天截图回忆
- 后续 `SPEC-064/066` 这类新路径可以通过 recommendation 事件日志追踪 rationale 与触发

---

## 3. Backtest / Research View UI 路径更新

### `SPEC-062 / SPEC-063 / SPEC-065`

当前 web backtest 页面已不只是单一 baseline 可视化，而具备研究视图能力。

已落地能力包括：
- research-view 生成 artifact
- 在 backtest 页面切换研究交易集
- SPX 图联动研究交易时序
- `SPEC-064` aftermath trades 的专属 research pill

这意味着：
- `Q015`、`Q016`、`SPEC-064` 这类研究/实现轨迹，已经从“一次性 prototype 图”升级为**可持续复查 artifact**
- 研究结论可被 PM / Quant 在 web 层复看，而不必每次临时生成 HTML

### 已暴露的工程教训

在 research-view tooling 落地过程中，已确认一个重要语义陷阱：

- 如果生成器只拿“当前 production”当 baseline，
- 那么一旦某条 Fast Path 已经进了 production，
- 原本的 marginal diff 会坍缩为 0

这个问题在 Q015 上已经出现过，并已修正。
当前系统因此默认需要在生成 research diff 时显式区分：
- 当前生产行为
- 旧行为 / comparison baseline

---

## 4. HIGH_VOL Aftermath 路径当前实现状态

### `SPEC-064`

系统当前已实现：
- `HIGH_VOL aftermath IC_HV bypass`

实现位置核心在：
- `strategy/selector.py`

其本质是：
- 在 HIGH_VOL、IV_HIGH、aftermath 条件下，
- 对 `IC_HV` 路径跳过 `VIX_RISING` 与部分高 IV gate，
- 同时保留 `EXTREME_VOL` 硬保护

### `SPEC-066`

随后系统已进一步实现：
- `IC_HV_MAX_CONCURRENT = 2`
- `AFTERMATH_OFF_PEAK_PCT = 0.10`

核心位置：
- `strategy/selector.py`
- `backtest/engine.py`
- `data/research_views.json`

当前实现语义是：
- `IC_HV` 最多允许 2 槽并发
- 非 `IC_HV` 策略仍保持单槽位
- aftermath 条件比 `SPEC-064` 更严格（`0.10` 而非 `0.05`）

### 当前需知的系统级 caveat

虽然 `SPEC-066` 已 `DONE`，但 PM 又识别出一个新的研究语义问题 `Q020`：

- 现在捕捉到的第二笔 `IC_HV`
- 可能是“同一峰后的 back-to-back 连抓”
- 而不是“第二峰回落后的真正第二次机会”

这说明：
- 实现已经存在并通过 review
- 但其 alpha 解释在研究层仍可能继续被拆分

**系统状态角度的结论**：
- 代码当前是 canonical 事实
- 研究含义仍可能继续被限定

---

## 5. 研究 / Prototype 资产现状

当前系统已有较完整的 prototype 轨迹，尤其是 HIGH_VOL 线：

- `backtest/prototype/q017_phase1_strategy_pnl.py`
- `backtest/prototype/q017_phase2_ex_ante.py`
- `backtest/prototype/q018_phase1_multi_slot.py`
- `backtest/prototype/q018_phase1_cluster_replay.py`
- `backtest/prototype/q018_phase2a_full_engine.py`
- `backtest/prototype/q018_phase2b_combo.py`
- `backtest/prototype/q018_phase2c_unlimited.py`
- `backtest/prototype/q018_phase2d_cap_sweep.py`

这些 prototype 当前作用：
- 支撑 `SPEC-064`
- 支撑 `SPEC-066`
- 为 `Q020` 提供再拆分基础

它们仍然属于**研究资产**，不是生产 engine 的一部分。

---

## 6. 当前系统实现状态总览

### 已实现并生效

| 项目 | 状态 |
|------|------|
| `SPEC-060` recommendation event log | DONE |
| `SPEC-062` research view | DONE |
| `SPEC-063` SPX 图联动 | DONE |
| `SPEC-064` HIGH_VOL aftermath IC_HV bypass | DONE |
| `SPEC-065` SPEC-064 research pill | DONE |
| `SPEC-066` IC_HV multi-slot + tightened off-peak | DONE |
| old Air canonical runtime split | 已生效 |

### 当前最相关但未实现

| 项目 | 状态 |
|------|------|
| `/ES` runtime stop monitoring + bot alert | open (`Q013`) |
| VIX open vs close timing-basis effect on HIGH_VOL paths | research (`Q019`) |
| `SPEC-066` second-slot semantic refinement | research (`Q020`) |

---

## 7. 当前系统架构理解（给新 agent / MC）

如果要快速重建截至 `2026-04-20` 的系统实现状态，应优先把系统理解成：

1. **runtime 已迁到 old Air**
2. **recommendation 已具备结构化审计能力**
3. **backtest web 已具备 research-view / SPX 图复盘能力**
4. **HIGH_VOL aftermath 线已不是研究假设，而是生产实现**
5. **但 `SPEC-066` 的第二笔语义仍有新的研究问题 `Q020`**
6. **`/ES` 仍然不是 entry logic 问题，而是 runtime safeguard 问题**

