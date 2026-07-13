# SPEC-094.6 — Q042 运行时 state 防覆写（stash-clobber 修复 + ATH 重锚 tripwire）

## 目标

SPEC-094.5 实施途中发现（2026-07-12，Q100 顺带产物）：`data/q042_state.json` 被
git 追踪（2e4142b 提交了全零默认值），而 old Air 的部署解冲突习惯是 `git stash`
——**每次 stash 把生产 state 打回全零**，executor 次日以 `max(0, 今日收盘)` 静默
重锚 running ATH，ddATH 长期读浅。取证（stash reflog 6 条，2026-06-10/11/12 +
07-04×3）：

- **2026-06-10 11:48 stash → 当日 16:15 executor ath=0 → ddATH 读 0%（真值
  −4.51%，ATH 7609.78 @ 06-02，executor 06-02 亲历 SPX=7610）→ Sleeve A 漏火**。
  审计 7/7 读到的 7537.43 与今日 7575.39 均为 07-04 stash 后的重锚痕迹，全时间线对账吻合。
- `data/closed_trades.jsonl` / `data/capital_flows.jsonl` 同为 tracked+mutable，
  同向量；取证按 trade_id 逐行核对——**总账无损**（9 行全在，realized 合计与 G2
  复审一致），c603a1a 手术行的字符串差异为后续字段校正。

## 接口定义

**F1 untrack**：`git rm --cached` + `.gitignore`：`q042_state.json` /
`closed_trades.jsonl` / `capital_flows.jsonl`。持久性归 SPEC-117.1 L1/L2 备份
（已日备+周备，含 data/ 全量），git 只负责代码。old Air 落地用 mv-aside →
pull → mv-back 序列（tracked-modified 文件直接 pull 会拒绝）。
**F2 ATH tripwire**：`production/q042_executor.py` EOD 流程中 `prior_ath ≤ 0`
→ gateway ACTION 告警（dedupe 每日），不再静默重锚；每日 INFO 行增加
`ath= ddath= (prior_ath=)` 可观测性（本缺陷 6 周不可见的直接原因是 executor
从不打印 ATH）。
**F3 生产 state 重设**：old Air `ath_running_max` → 7609.78（2007 起算真值，
2026-06-02 收盘，Yahoo 全历史 cummax 复核），`ath_last_update` 同步。armed
状态不动（双 sleeve armed=true 正确：从未 fire、当前 ddATH −0.45% ≥ −2%）。
**F4 runbook 修订**：`doc/deploy-to-oldair.md` 增加规则：old Air 上禁 `git
stash`；运行时可变文件禁 git 追踪；pull 因 dirty tracked 文件拒绝时，修的是
tracking（untrack），不是 stash。

## 漏火处置（PM 知情项，非本 spec 动作）

06-10 漏掉的 fire 按当时结构（2.5%/D30）反事实：strikes 7265/7450，若 T+1 开
则 07-13（周一）到期结算；07-10 收盘 7575.39 已满宽——反事实价值见 findings
交付时计算。**不补录不追单**（T+1 语义已过，追进 = 追高 +4%，非本策略）；
按 R-20260712-04 登记。

## 验收标准

| AC# | 描述 | 结果 |
|---|---|---|
| AC-94.6-1 | 三文件 unstaged/ignored：`git ls-files` 无此三项且 `git status` 不再显示 | |
| AC-94.6-2 | tripwire：state ath=0 → ACTION 告警一条（dedupe `q042_ath_reset_{date}`）；dry-run 不告警 | |
| AC-94.6-3 | old Air state ath_running_max == 7609.78 且次日 EOD 日志出现 `ath=` 行 | |
| AC-94.6-4 | old Air `git status` 干净（三文件不再列出）；再跑一次 `git stash` 不再触碰三文件（无 tracked 修改） | |
| AC-94.6-5 | 回归：094.2/.3/.4 + 142 全绿 | |

## Handoff Contract

1. **What changes**：`.gitignore`、`production/q042_executor.py`（tripwire + log 行）、`doc/deploy-to-oldair.md`（规则节）、old Air state 重设（运维动作）。
2. **Invariants**：trigger/gate/settle 语义零变化；tripwire 只在 ath≤0 时发声。
3. **Rollback**：executor 两处 diff 摘除即回；untrack 不可逆但无害（备份链在）。

---
Status: DEPLOYED 2026-07-12 (old Air state 重设 + untrack 落地 + tripwire 上线)
