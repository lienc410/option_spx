# Q076 — Hourly Recommendation Churn — 2nd Quant Review

**Date**: 2026-05-26
**Reviewer**: 2nd Quant
**Subject memo**: `research/intraday/q076_findings_2026-05-26.md`
**Verdict**: REVISE — proceed to mitigation replay, do not expand sample yet

---

## Top-line verdict

> **不要先扩展 6 个月数据。先做 A+B 的修复方案回放。**

21 天样本虽小，但诊断清楚：15 hourly flips、7/21 天日内切换、BPS 中位持仓 4h、churn 全部是 BPS ↔ Wait（同一策略 gate 抖动，不是策略真改变）。这不是 alpha 研究，是 **execution governance** 问题。

---

## 论点要点

### 1. 这是 execution governance，不是 trading alpha
- Frontend hourly rec 如果被当作可执行指令 → BPS theta 策略被结构性误用为 day trade
- 1-3h 持仓几乎没 theta，只承担 bid/ask、slippage、delta/vega 噪声
- 优先目标：**防止 dashboard rec 被误读成 intraday execution signal**

### 2. 不建议先扩展 6 个月
- 当前是最容易抖动的中间态（VIX 16-19, IVP 在 55 附近）
- HIGH_VOL 期 IVP 锁 ≥80, deep LOW_VOL 期 ≤30 — 都稳定
- 扩展样本会**稀释问题，而不是解决**
- 正确顺序：在已知最坏 jitter regime 上测修复 → 通过后扩展确认

### 3. 三个修复方向取舍
- **A. Hysteresis 53/57**：必测 — directly targets root cause
- **B. Scheduled eval 10:00 + 15:30**：也应测 — execution cadence 问题
- **C. 24h min-hold**：暂不测 — 改变 trade lifecycle 太多 (stop/stress/second-leg 例外定义复杂)，P2 fallback only

### 4. 提议测 4 个 variants
```
Baseline: current hourly recommendation
A only: IVP hysteresis 53/57
B only: eval only 10:00 + 15:30
A+B: hysteresis + time windows
```

### 5. 成功标准（hard targets）
- intraday flips 减少 ≥ 50%
- ≤3h BPS episodes 减少 ≥ 75%
- EOD recommendation agreement ≥ 90%
- 不增加策略种类误切换
- 不影响 stress / stop / second-leg hard exits

### 6. 前端语义同时修
即使技术做了 A+B，前端要避免把 hourly card 表达成 "现在应该开/关"。降级为：
- Current state snapshot
- Execution recommendation evaluated at scheduled decision times
- Intraday state changes are informational unless stop/stress trigger fires

> **把 hourly recommendation 从"交易指令"降级成"状态观察"，只有 scheduled decision times 才产生 actionable recommendation。**

---

## Proposed phase plan

```
Q076 P2: test hysteresis + scheduled eval on current 21-day jitter window
Q076 P3: if successful, expand to 6–12 months for robustness
Q076 SPEC: frontend / selector execution-governance change
```
