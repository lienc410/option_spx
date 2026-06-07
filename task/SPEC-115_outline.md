# SPEC-115 Outline — Q041 Paper Trade Promote (T2 GOOGL + AMZN + T3 COST + JPM Earnings IC)

**Type**: scope outline for PM review (not yet full SPEC)
**Date**: 2026-06-06
**Status**: **drafted**, awaiting PM phase-priority ratify before full SPEC + handoff
**Cross-reference**: [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md) §8 Q1 PM ratify "可以推进", AskUserQuestion 2026-06-06 scope = "T2 + T3 全动"
**Predecessor**: SPEC-114 chain sanity + retry guard (必须先 deploy 完，再开始 SPEC-115 dev)

---

## 0. Why this is an outline, not a full SPEC

T2 + T3 全动是 **2 个工作量量级差距明显** 的工作流合一：

| | T2 (GOOGL + AMZN CSP) | T3 (COST + JPM Earnings IC) |
|---|---|---|
| Strategy type | Daily rolling CSP | Event-driven IC (T-3 from earnings) |
| Data source | Schwab chain (现有 q041_chains) | Schwab chain + **earnings calendar** + IMR for JPM |
| Backtest cache | ✅ 已 ready (`q041_backtest_cache.json` 含 198/188 trades) | ❌ 无 |
| Selector logic 复杂度 | 低 (daily check delta/dte band) | 中 (倒计时 + earnings window gate) |
| Governance gate (5/5 packet) | borderline-formal lane | observe-only / cautious lane |
| 估工作量 | **1-1.5 周 dev** | **1-2 周 dev**（earnings calendar 数据源 + IMR 数据） |

**建议分 phase 推进**，每 phase 独立 SPEC + handoff + dev cycle，前 phase ship 后 PM 看一周 paper trade 信号流再 ratify 后 phase。

---

## 1. Phase A — T2 GOOGL + AMZN CSP paper trade promote

### 1.1 Scope

| Candidate | Spec |
|---|---|
| T2 GOOGL CSP | Δ ≈ 0.20, DTE ≈ 21, daily rolling |
| T2 AMZN CSP | Δ ≈ 0.25, DTE ≈ 21, daily rolling |

both 走 paper trade lane (per SPEC-038 `paper_trade=True`), Q041 sleeve BP cap 守护，每日 EOD 信号推 Telegram。

### 1.2 Files (production code, dev 实施)

- `strategy/catalog.py`: 加 2 个 `StrategyDescriptor` (`q041_t2_googl_csp`, `q041_t2_amzn_csp`)
- `strategy/q041_selector.py` **(NEW)**: T2 entry signal logic (daily check Δ-band + DTE-band on Schwab chain)
- `strategy/sleeve_governance.py`: Q041 sleeve cap config + 2 candidate routing
- `notify/telegram_bot.py`: Q041 daily signal push (新 push 类别)
- `data/q041_paper_log.jsonl` **(NEW)**: paper trade event log (open/close/roll), `paper_trade=True` 强制
- `web/templates/q041.html`: 启用 T2 candidate cards (前端 spec 已 hardcoded line 352-369，只需 wire 到 `/api/q041/overview` 实际数据)
- `web/portfolio_surface.py`: `sleeve_candidates_payload()` 加入 T2 信号
- `tests/test_q041_t2_signals.py` **(NEW)**: T2 entry/exit signal AC

### 1.3 ACs (Phase A)

- **AC-1**: GOOGL Δ0.20 ±5pp + DTE 21 ±3d 信号触发 → paper trade open event
- **AC-2**: AMZN Δ0.25 同上
- **AC-3**: Q041 sleeve BP cap 守护 (5% NLV per SPEC-104?) 限制 candidate 累计 BP
- **AC-4**: paper_trade=True 强制 → 不进 real trade_log, 不影响 SPEC-037 live performance
- **AC-5**: Telegram 每日 EOD 推 T2 信号状态 (entry available / no signal / pending close)
- **AC-6**: dashboard q041.html T2 cards 显示当前 paper position + paper PnL

### 1.4 Decision points (Phase A 内)

- **Q-A1 Sleeve BP cap**: Q041 sleeve 当前是观察期，目标 BP cap = ?
  - 选 A: 沿用 SPEC-104 BP-side 5% NLV
  - 选 B: 沿用 SPEC-111 cash-side 5% liquid (~$1,850)
  - 选 C: 双 cap (BP-side AND cash-side)
- **Q-A2 Entry trigger 频率**: 每日 EOD 仅检查一次（per `/api/q041/overview`）vs 实时（不必要 for 21 DTE）
- **Q-A3 Exit 条件**: 5/5 packet 未明指。建议默认 50% credit target / 21 DTE close, 实际数字 PM 拍
- **Q-A4 Single-name tail caveat 显式守护**: 5/5 packet 警告"missing 2019-2021/COVID tail"；是否在 paper trade 期间额外加 size 限制 (e.g., 单 candidate max position ≤ 1 contract paper)

### 1.5 估工作量

- Dev: 1-1.5 周 (selector + governance + dashboard + tests)
- Quant cycle: 0.5 周 (AC verification + paper signal 第一周观察)

---

## 2. Phase B — T3 COST + JPM Earnings IC paper trade promote

### 2.1 Scope

| Candidate | Spec |
|---|---|
| T3 COST earnings IC | T-3 before earnings, 1.0× IV-implied move IC, VIX ≥ 15 gate |
| T3 JPM earnings IC | T-3 before earnings, 1.0× IC, VIX ≥ 15 gate, **IMR ≥ 33% optional secondary** |

走 cautious paper trade lane (per 5/5 packet "observe-only → cautious paper-trading 升级 per PM 2026-06-06 ratify"). 事件驱动（非 daily rolling），需要 earnings calendar 数据源。

### 2.2 Files (production code, dev 实施)

- `strategy/catalog.py`: 加 2 个 IC descriptor
- `strategy/q041_selector.py` (扩展): T3 entry signal logic (earnings T-3 countdown + VIX/IMR gate)
- `data/earnings_calendar.json` **(NEW)** or 接入外部数据源 (yfinance / earnings_calendar / Schwab 是否提供?)
- `strategy/sleeve_governance.py`: T3 candidate routing
- `notify/telegram_bot.py`: T3 earnings IC trigger 特殊 push (T-3 倒计时提醒, T-2/T-1/T 0 状态推送)
- `web/templates/q041.html`: 启用 T3 candidate cards
- `tests/test_q041_t3_earnings.py` **(NEW)**

### 2.3 ACs (Phase B)

- **AC-7**: earnings calendar 数据源接入 (COST + JPM 未来 2 个 earnings 日期可读)
- **AC-8**: COST T-3 trigger + VIX ≥ 15 gate 全满足 → paper IC open
- **AC-9**: JPM T-3 trigger + VIX ≥ 15 gate + (optional) IMR ≥ 33% → paper IC open
- **AC-10**: VIX < 15 gate 阻断 (5/5 packet P2-2 weak-loss regime)
- **AC-11**: IC structure (1.0× IV-implied move) 正确生成 short call / short put / long call / long put 4 legs
- **AC-12**: earnings 第二天 (T+1) auto-close paper IC

### 2.4 Decision points (Phase B 内)

- **Q-B1 Earnings calendar 数据源**:
  - 选 A: Schwab API（如果有）
  - 选 B: yfinance (`yf.Ticker("COST").calendar`) — 免费但 SLA 弱
  - 选 C: 付费源（IEX Cloud / Polygon earnings calendar）
  - 选 D: 手动 PM 输入每季 earnings 日期
- **Q-B2 JPM IMR 数据源**: 5/5 packet 提到 "IMR>=33%" 但 IMR 来自哪里？(Initial Margin Requirement, 通常 broker 提供) — 需要研究
- **Q-B3 T-3 时点**: 5/5 packet 没明指是 calendar day 还是 trading day。建议 trading day, PM 拍
- **Q-B4 IC size**: 5/5 packet "1.0× IV-implied move"。short strike = spot × (1 ± IV × √(DTE/365)) ×1.0
- **Q-B5 早期 close 条件**: earnings 通常盘后或盘前发布，T+1 open 还是 T 0 close after EOD?

### 2.5 估工作量

- Dev: 1-2 周 (earnings calendar 集成 + IC logic + 数据源接入)
- Quant cycle: 0.5-1 周 (earnings event 取证 + first paper IC trade 观察)

---

## 3. 总体推进顺序建议

**推荐**: 串行推 Phase A 完成 + ship + 1 周 paper observation → 再推 Phase B

理由：
- Phase A 大部分基础设施 (`q041_selector.py`, `q041_paper_log.jsonl`, sleeve_governance routing, dashboard) **Phase B 复用**。先 ship 让基础设施 hardened，Phase B 增量加 earnings logic 更稳。
- Phase B 涉及外部数据源（earnings calendar），如果数据源选择 fall through (Q-B1)，可能产生未预料的 dev 延期。Phase A 独立可 ship 不被 block。
- PM 可在 Phase A 上线后第一周观察 paper signal 流（Telegram push + dashboard），如果 UX 有调整需求可在 Phase B 一起改。

**替代**: 并行推 Phase A + B（如果 PM 想尽早看 earnings IC 信号）— 但 dev 工作量 ≥ 2.5 周, scope creep 风险高，不推荐。

---

## 4. 我需要 PM 拍板的事

### Q-1 Phase priority
推 Phase A → Phase B 串行（推荐），还是并行？

### Q-2 Phase A decision points (§1.4)
- **Q-A1** sleeve BP cap (5% NLV / 5% liquid / 双 cap)
- **Q-A2** entry trigger 频率
- **Q-A3** exit 条件默认值
- **Q-A4** single-name tail size 限制

如果 PM 不想现在拍，我按 5/5 review packet 默认推荐起 full SPEC，PM 看 SPEC 时再 challenge。

### Q-3 Phase B 数据源
- **Q-B1** earnings calendar 选 A/B/C/D？
- **Q-B2** JPM IMR 是否真的能拿到 (yfinance/Schwab)？这条若 fall through，IMR ≥ 33% 是否作为 strict requirement 还是 nice-to-have？

### Q-4 SPEC-114 (chain sanity) 先 deploy 完，再开始 SPEC-115 dev

confirm 串行依赖？SPEC-114 是 SPEC-115 的数据基础 (Schwab chain 完整性), 不能跳过。

---

## 5. Open process question

Q083 → SPEC-113 走过 2nd quant review G-review packet 流程（撤回 3 次 + reviewer 抓 5 个 pattern）。SPEC-115 工作量大于 SPEC-113，需要 2nd quant review packet 吗？

**建议**: 是。SPEC-115 是 Q041 paper trade lane **首次 promote**, 跨 selector / governance / dashboard / data source 多层，又是 cash-bound 账户的 paper trade 起步, reviewer 应该至少看一次 SPEC + Phase A AC list, 避免 P12 同型"被多次撤回后压力 ship"陷阱（per `feedback_post_withdrawal_proposals_front_load_robustness`）。

不需要 PM 此刻拍 2nd quant review 时机, 我起 SPEC 时会把 G-review 节点列在 §"Process" 里。

---

## 6. Next steps (after PM ratify outline)

1. PM 答 §4 Q-1 ~ Q-4 (可全拒答, 我用默认推荐推进)
2. 我起 SPEC-115_phase_a.md (full SPEC) + handoff
3. 2nd quant review packet (G-review) for SPEC-115_phase_a
4. Reviewer ratify → dev impl Phase A → deploy
5. Phase A ship 后 1 周 paper observation → PM ratify Phase B
6. 起 SPEC-115_phase_b.md + handoff + G-review
7. Phase B dev impl → deploy → 全 Q041 paper trade lane up

时间预估: outline ratify → Phase A ship 约 2-3 周 (含 G-review cycle). Phase B 再 2-3 周.

---

## 7. Files referenced

- [task/q041_2nd_quant_review_packet_2026-05-05.md](q041_2nd_quant_review_packet_2026-05-05.md) — 5/5 candidate stratification
- [task/q041_t1_es_governance_review_archive_2026-05-09.md](q041_t1_es_governance_review_archive_2026-05-09.md) — T1 retirement
- [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md) — data alignment closure
- [doc/q041_phase2_summary_2026-05-05.md](../doc/q041_phase2_summary_2026-05-05.md) — Phase 2 results
- [doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md](../doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md) — GOOGL/AMZN evidence
- [doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md](../doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md) — COST/JPM evidence
- [data/q041_backtest_cache.json](../data/q041_backtest_cache.json) — GOOGL/AMZN cached (T3 missing)
- [web/templates/q041.html:341-379](../web/templates/q041.html#L341-L379) — T2/T3 dashboard skeleton (already coded)
- [strategy/sleeve_governance.py](../strategy/sleeve_governance.py) — existing sleeve framework
