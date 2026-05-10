# Q042 Manual Execution SOP

最后更新：2026-05-10
持有人：PM（liengucas@gmail.com）

Q042 是 Telegram-only 信号策略——EOD 发出 Telegram alert，PM 次日开盘手动下单。本文档记录每次执行的标准动作。

---

## 当晚（EOD alert 收到时）

1. **检查 Telegram alert** 是否完整：
   - sleeve（A 或 B）
   - 触发原因（dd4 lenient / dd15 + ma10 reclaim）
   - 推荐结构（ATM/+5% call spread, DTE 90, expiry date）
   - 推荐合约数量（基于当前 NLV 与 sizing）
2. **核对 `data/q042_state.json`** 已 mark `pending`（脚本自动写入；若没有 → 检查 `production/q042_executor.py` 日志）
3. **看一眼 NLV**：< $200k → 自动 size=0，无单可下；$200k-$500k → 减码；≥ $500k → 全额 sizing

## 次日开盘前（pre-market 30 分钟）

### A. 必做：常规复核

- [ ] 当日是否 NYSE 交易日？（节假日则该 alert 作废，下一交易日重新评估）
- [ ] 当日开盘前 SPX futures 大幅 gap (≥ ±2%)？若有，停下重新评估 trigger 是否仍在 dd 区间
- [ ] 主策略 BP% 是否 < 60%（否则 gate 关闭，sleeve_allowance=0）

### B. 可选：UW Flow Eyeball Check（zero-cost sanity check）

> 来源：Q054 thread 收口（R-20260510-09，10）。Q054 quant 研究因 CSV export 需付费 ≥$446/yr 而 kill thread。改用人工 eyeball 作为非量化 sanity check。

**操作**（30 秒）：
1. 打开 [unusualwhales.com/option-flow-alerts](https://unusualwhales.com/option-flow-alerts)
2. Filter: ticker = `SPX` 或 `SPY`，过去 24 小时
3. 看主导方向：
   - **大量 ask-side call premium** → 与 Q042 long-call-spread 方向**一致** ✓ 正常入场
   - **大量 bid-side call premium / ask-side put premium** → 与 Q042 方向**冲突** ⚠️ 考虑降码 50% 或跳过
   - **flow 平淡 / mixed** → 无信息 → 默认正常入场

**override 规则**（保守）：
- 仅在 **强烈反向** flow（≥ 3 笔 ≥ $500k 反向 alert）时考虑跳过
- override 需在 `data/q042_state.json` 备注 `manual_skip_reason`（手动编辑）
- override 频率应 < 10%（若超过，说明 eyeball 信号噪声，关闭此规则）

**学术 disclaimer**：unusual flow 通用样本预测力 51-54%（Pan-Poteshman 2006，Cremers-Weinbaum 2010）；SPX/SPY 索引 flow 因机构 hedging 主导预测力更弱。本 eyeball 不是量化信号，仅作为 **gross sanity check** 防止极端反向开仓。

### C. 必做：下单

1. 登入 Schwab/ETrade → Options → Spread → SPX Call Vertical
2. 长腿：ATM strike（`signal_close * 1.00`，最近 listed strike）
3. 短腿：+5% OTM（`signal_close * 1.05`，最近 listed strike）
4. 到期：alert 中 `expiry_date`（DTE 90 calendar days）
5. 数量：alert 中 `contracts`
6. 价格：limit @ NBBO mid（broker 显示），不 chase
7. 时间：开盘 5-15 分钟内（避开开盘 1 分钟 spread 极差）

### D. 必做：成交后回写

1. 编辑 `data/q042_state.json`，sleeve 状态 `pending` → `live`
2. 写入实际 `fill_debit`（每张净 debit，不含 commission）和 `entry_time`（HH:MM ET）
3. （可选）截图 broker 确认单存档 `data/q042_fills/<entry_date>_<sleeve>.png`

## 持仓期（DTE 1-90）

- **不做日内调整**：Q042 设计为持有至到期（cash-settled European）
- **不设 stop-loss**：spread 已锁定 max loss = debit
- **不设 profit target**：MVP 阶段无 50% TP（Tier 4 研究项，2027-05-10 review）
- 偶尔（每周一次）扫一眼 SPX 是否触发 sleeve 的 re-arm threshold（ddATH ≥ -2%）—— state machine 自动处理，但人工 awareness 有助于预判下次 alert

## 到期日（DTE 0）

1. 当日 16:00 ET 后，cash settlement 自动入账（broker 处理）
2. 编辑 `data/q042_state.json`：sleeve 状态 `live` → `closed`，写入 `exit_value` 和 `pnl`
3. 计入 `data/q042_pending_records.jsonl` 关账（脚本自动 from positions 模块）

---

## 标准复核节奏

| 周期 | 检查项 |
|---|---|
| 每周一次（周五收盘后） | state.json 与实际持仓核对 / pending records 是否完整 |
| 每月一次 | Schwab/ETrade NLV 与 spread BP usage 与 risk dashboard 一致 |
| 6 月（2026-11-10） | Q042 paper-trading review：live 胜率 vs research baseline (A=64% / B=100%) |
| 12 月（2027-05-10） | Q042 long review：sleeve cap 10%→15% 升级研究，Tier 4 50% TP/stop 研究 |

## 标准 escalation

- **Live HIGH_VOL trigger（VIX ≥ 22）当天**：Quant 必须 re-run `research/q042/q042_f4_oldair_backfill.py` 对当天 chain 重新验证 model debit vs broker mid（standing obligation 来自 SPEC-094 deployment review 2026-05-10）
- **连续 3 笔 sleeve A 亏损 OR 单笔 sleeve B 亏损**：暂停后续入场，发起 Quant review
- **NLV < $200k 持续 ≥ 5 个交易日**：sleeve 自动 size=0，无 alert 触发；但若发现 sizing 逻辑 bug，立即停 strategy
