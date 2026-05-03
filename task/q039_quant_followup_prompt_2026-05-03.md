# Quant Follow-up Prompt — Q039 Mini Attribution Table

请作为 Quant Researcher 工作。

先读取：
- `QUANT_RESEARCHER.md`
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`
- `sync/mc_to_hc/MC Response 2026-05-02_v2.md`
- `sync/hc_to_mc/HC_return_2026-05-02.md`
- `doc/tieout_2_2026-05-02/README.md`
- `doc/tieout_3_2026-05-02/README.md`
- 如需要，再读：
  - `doc/q037_ac3_attribution_note_2026-05-03.md`

本轮目标：

- 不重开 `Q036`
- 不重开 `Q021`
- 不继续扩 `SPEC-077 AC3` 大调查
- 不先做 `IVP` sweep

你本轮只处理一个窄问题：

> `Q039` 的最小下一步：做一个 `IC regular` mini attribution table

---

## 任务

基于：

- MC 提供的 6 笔 `IC regular` ledger
- HC 当前 `IC regular` 13 笔 / 其中 HC-only 11 笔

请做一个紧凑 attribution table，并回答：

### 1. MC 6 笔基础表

请整理：

- `entry date`
- 是否与 HC 共有
- `entry VIX`
- `entry SPX`
- `exit reason`
- `PnL`

### 2. HC-only 11 笔最小归因表

请对 HC-only 11 笔至少标出：

- `entry date`
- `ivp252 bucket`
  - `<30`
  - `[30,55)`
  - `>=55`
- `trend state`
- 是否已有同类 `IC` slot occupied
- HC route reason

### 3. 结论桶

请把 HC-only trade 按最小结论桶分组：

- `high-IVP fallback/gate`
- `low-IV bug candidate`
- `MC-missing despite valid [30,55)`
- `other`

### 4. 最终判断

请回答：

1. 当前 `Q039` 是否仍主要表现为：
   - high-IVP `NORMAL IC` fallback / gate 差异
   - 而不是 slot blocking
2. 是否继续不建议先做 `IVP` sweep？
3. `Q039` 是否仍应保持在 research，不升级成更强的 parity investigation？

---

## 输出要求

- 先给一句话结论
- 再给：
  - `MC 6-trade table`
  - `HC-only 11-trade mini attribution table`
  - `bucket summary`
- 最后给 Planner 一个明确建议：
  - `Q039` 是否维持当前 open 状态
  - 是否需要任何进一步动作，还是这张 mini table 已足够作为下一阶段基线
