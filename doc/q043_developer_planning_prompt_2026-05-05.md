# Q043 — Q041 Scanner and Bot Support: Developer Planning Prompt

Date: 2026-05-05
Status: future planning / pre-spec
Priority: low-to-medium（排在 Q041 paper-trading startup + overlap validation + Q036/Q038 monitoring 之后）

---

## 背景

SPEC-083 已关闭（Status: DONE）。Q041 paper-trading ledger 现在稳定可用：

- `data/q041_paper_trades.jsonl` — 主 ledger
- `data/q041_paper_trade_config.json` — account_total_bp 配置
- `logs/q041_paper_trade_io.py` — schema / write / budget / export / status_snapshot
- `scripts/q041_paper_ledger.py` — CLI (add-csp / add-ic / close / update / budget / export-csp / export-ic / status)

Q043 是 SPEC-083 之后的下一个候选支持分支，当前优先级为 low-to-medium，尚未起正式 Spec。
本文档是面向未来实施的 planning input，**不要求立即开工**。

---

## Q043 核心定位：Recommendation & Reminder Support Layer

Q043 是 Q041 paper-trading 的运营辅助，**不是第二套执行引擎**。

严格禁止：

- 自动下单 / 自动平仓
- 写入 broker
- 自动晋升候选为 live 策略
- 与当前 SPX 主推荐路径合并

---

## 三阶段结构

### Phase A — Shadow Scanner（优先级最高）

目标：只读扫描，判断当前市场状态是否满足 Q041 入场条件。

三层候选规则：

- Tier 1：SPX CSP Δ0.20 DTE30（月度窗口）
- Tier 2：GOOGL CSP Δ0.20 DTE21 / AMZN CSP Δ0.25 DTE21（月度窗口）
- Tier 3：COST / JPM earnings IC，硬前置 VIX >= 15，earnings date T-3 窗口

每次扫描输出结构化候选（建议 JSONL audit log）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `candidate_found` | bool | 本次扫描是否发现符合条件的候选 |
| `tier` | str | tier1 / tier2 / tier3 |
| `symbol` | str | |
| `why` | str | 触发原因（例如 "DTE=31, VIX=16.2, within window"） |
| `hard_gate_passed` | bool | VIX gate（Tier 3）或其他硬约束 |
| `bp_impact_est` | float | 估算 BP 占用（美元），基于当前 config account_total_bp |
| `suggested_dte` | int | |
| `suggested_delta_or_structure` | str | |

扫描频率：建议每日一次，可手动触发亦可 cron。
Phase A 不向 bot / 用户推送，只写 audit log 或 dev-only surface。

---

### Phase B — Dev Bot / Shadow Notification

前置：Phase A scanner 语义稳定（建议 ≥ 2 周 shadow 观察后评估）。

目标：将候选消息路由到开发者 bot 或现有 bot 的 dev-mode 分支。

评估维度：

- 消息频率（是否过于噪音）
- 误报率（hard_gate_passed=true 但实际不该进）
- 推荐格式对 PM 是否可读可操作
- budget / tier context 是否充分

仍视为 shadow，不作为 live 推荐。

---

### Phase C — Paper-Trade Reminder Support

前置：Phase B 质量验证通过。

目标：为已记录的 paper trades 提供到期和事件提醒。

- CSP：expiry <= today + 7 → 触发月度 roll / 平仓提醒
- Earnings IC：earnings_date - 3 <= today → 触发 COST/JPM 入场窗口提醒
- 可能的平仓 / expiry bookkeeping 提醒

仍是 support tooling，不是 trade automation。

---

## 建议文件布局（供参考，正式 Spec 时可调整）

```
strategy/q043_scanner.py          ← Phase A 扫描逻辑（read-only，依赖 q041_paper_trade_io）
data/q043_scanner_log.jsonl       ← Phase A audit log
scripts/q043_run_scanner.py       ← Phase A CLI 入口（可 cron 或手动）
（Phase B: 待 Spec 确定后追加 bot routing）
```

关键依赖（不新建数据通道，沿用现有 infrastructure）：

- `logs/q041_paper_trade_io._read_all()` — 读取现有 open positions
- `logs/q041_paper_trade_io.budget_status()` — 当前 BP 占用
- `data/q041_paper_trade_config.json` — account_total_bp
- 市场数据来源（VIX、DTE 计算）沿用现有 market_cache / data layer

---

## 关键风险（开发时需主动防范）

1. **Product creep**：scanner → 不知不觉扩展为第二套推荐引擎
   → 每个 Phase 交付时检查：是否有任何代码写入 ledger 或向 broker 发请求？如有，属越界。

2. **与 SPX 主路径混合**：Q043 的输出不得进入 `engine.py` / `selector.py` 的决策路径
   → AC 建议：grep 检查 q043 相关模块不被 engine.py / selector.py import

3. **Phase B 过早推进**：在 Phase A audit log 不够稳定之前推送 bot 消息
   → Phase B 正式起 Spec 前，Quant 需 review Phase A log 至少 2 周样本

---

## 当前状态 / 何时起 Spec

Q043 目前排在以下工作之后：

- Q041 paper-trading 启动期（SPEC-083 刚上线，需先积累真实记录）
- Q041 overlap validation 20-day window（~2026-05-12 起）
- Q036 / Q038 shadow monitoring
- /ES runtime safeguard follow-up

预计 Phase A DRAFT Spec 时机：Q041 paper-trading 运行 4-6 周后，PM / Quant 评估是否提前 promote。
正式 Spec 起草由 Quant 主导，内容窄于本 planning prompt（只覆盖 Phase A scanner + audit log）。

---

## 参考文档

- `doc/q043_q041_scanner_and_bot_seed_memo_2026-05-05.md` — Planner seed memo（Q043 来源）
- `task/SPEC-083.md` — Q041 paper-trade ledger 的正式 Spec（Q043 的前置依赖）
- `doc/q041_execution_prep_packet_2026-05-05.md` — Q041 三层入场规则与 BP budget 框架
