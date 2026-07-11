# SPEC-094.4: Q042 触发告警弹药路由（BPS fallback 决策支持）

## 目标

把 Q095 P6 的 ratified 规则装进 Q042 触发告警（**提示不拦**，执行仍人工）：现金充足 → call spread（默认，不变）；现金不足 + 震荡铺垫型 → BPS fallback（并提醒收益差距）；现金不足 + 突发崩盘型 → 建议空仓。

审批链：PM 2026-07-12 逐字 ratify 规则（"现金不足+震荡型→BPS；突发型→空仓"）+ 同日追加提醒要求（"推荐开 BPS 时提醒我 BPS 赚的少"）。依据：`research/q095/q095_p6_findings_2026-07-12.md`。

## 策略/信号逻辑

无自动执行变更；trigger/armed/sizing/cap 不动。新增的只是告警正文里的**建议块**与其分类逻辑。

### 触发型分类（live 版，须与 P6 研究分层对齐）

**（Rev 2026-07-12，Quant 裁决——替换初稿定义）** `episode 型 ⟺ 对截至信号日的 Close 序列跑研究同款因果贪婪分段（find_episodes 原样，5% 带 / ≥15TD，数据截断至信号日），信号日落在某 episode 段内或段末端后 ≤7 日历日`。否则 = `突发型`。

*初稿定义（"前 7 日内存在 trailing 15TD 极差比 ≤5% 日"）被 Developer AC-3 重放证伪：trailing 窗口跨骑已完结的旧 episode，把全部 4 个突发型误判为 episode 型——现金不足时会把崩盘延续路由到 BPS fallback，恰是本规则要防的失败模式（该型 BPS −$101k vs call spread capped −$25k）。市场结构注记：4/4 突发崩盘触发前 2-3 周都存在刚完结的压缩 episode（n=4，仅登记）。变体 B = 注册研究定义的忠实因果截断，参数 5%/15TD/7d 未动。Developer handoff §五 + Quant 独立复现（31-32/35，突发 4/4，差异全部错向保守侧）。*

## 接口定义

### F1 — 触发告警建议块（AC14.2 amendment）

Q042 fire 告警在 F5b 现金行之后追加建议块，三分支：

1. **现金充足**（本次 est 总 debit ≤ liquid cash）→ `→ 弹药充足：Call Spread（默认结构）`
2. **不足 + episode 型** → `→ 现金不足·震荡铺垫型：可用 BPS fallback — SELL PUT {K1}(Δ0.30) / BUY PUT {K2}(Δ0.15)，同 expiry，预算按 BP（max loss ≤ 12.5% NLV ≈ ${X}）。⚠️ BPS 收益显著低于 call spread（26 年同预算差 3.7-7.4×，Q095 P6）——弹药不足下的次优替代`（strikes 用 `find_strike_for_delta` 按当日 SPX/VIX 现算）
3. **不足 + 突发型** → `→ 现金不足·突发崩盘型（无震荡铺垫）：建议空仓 — 历史该型 BPS 亏损 4× 于 call spread capped debit，且 call spread 自身 4 例 3 亏（Q095 P6）`

分类与建议同步写入 gate log 行（新可选字段 `ammo_advisory: {branch, episode_type, liquid, need, bps_strikes?}`）——为突发型 n=4 的 paper 证据积累建管道。

### F2 — 失败降级

分类/报价任一环节失败 → 建议块显示 `弹药路由 n/a`（不阻塞告警，AC16；沿 F5b try/except 惯例）。

## 边界条件与约束

- 提示不拦：三分支都不改变 fire 语义、不写仓、不改 sizing。
- AC14.1 既有行保持；本块为 AC14.2 追加（SPEC-094 AC14 再记 amendment）。
- dry-run：建议块随告警一起被抑制（零推送零落盘，沿 094.2/094.3 语义）。
- episode 分类只用 trailing 信息（禁止任何前视）。

## 不在范围内

- BPS fallback 的自动下单/自动记账（人工执行，走 `/api/q042/position/open`，094.3 F2 已回写 state）；fallback 仓位的 stop/管理规则（沿主策略 BPS 惯例，人工）；分类器参数调整（5%/15TD/7d 锁死，改动须新研究）。

## Prototype
（无——分类逻辑复用 research/q095 已验证代码路径）

## Review
- 结论：**PASS（Quant fidelity review 2026-07-12）**
  - 实施经历一次正确的 BLOCK：Developer AC-3 重放证伪初稿 trailing 定义（4/4 突发型误判向危险侧）；Quant 裁决采纳变体 B（因果贪婪分段直译）+ AC-3 改方向敏感门槛，spec 已记 errata。
  - 最终验证（Quant 亲跑）：AC-3 = **32/35 总对齐、突发型 4/4 硬门槛过、3 笔差异全部错向保守侧**（inside-early 不可判例）；全套 48 tests passed（13 新 + 094.2/094.3 35 invariant）；收益差距提醒句逐字在测。
  - Developer 会话在 handoff 更新前中断，最终数字由 Quant 亲自执行补录（handoff §六）。
  - handoff：`task/SPEC-094.4_handoff.md`。

## 验收标准

| AC# | 描述 | 验证 |
|---|---|---|
| AC-94.4-1 | 三分支建议块：充足/不足+episode/不足+突发 三例正文正确，**分支 2 必含收益差距提醒句**（PM 2026-07-12 要求） | pytest（gateway recorder） |
| AC-94.4-2 | gate log 行携带 `ammo_advisory`（branch/episode_type/liquid/need） | pytest |
| AC-94.4-3 | **live 分类器与 P6 研究分层对齐（Rev 2026-07-12 方向敏感形态）**：35 个历史触发日重放——①**突发型 4/4 全对（硬门槛，安全关键）**；②总对齐 ≥ 31/35；③全部差异必须错向 `sudden/空仓`（保守侧）。差异逐笔列 handoff。*初稿平铺 ≥33/35 在锁死参数下原理性无解（3 笔 inside-early 对 trailing-only 不可判），门槛形态按危害不对称重定：崩盘误路由 BPS = 危害向量，错失 fallback = 小成本* | pytest + 历史重放 |
| AC-94.4-4 | 分类/报价异常 → `弹药路由 n/a`，告警照发（AC16） | pytest 注入异常 |
| AC-94.4-5 | dry-run 零推送零落盘（含 gate log 无 ammo_advisory 行） | pytest hash 比对 |
| AC-94.4-6 | SPEC-094.2 22 tests + 094.3 13 tests 继续全绿 | pytest |

## Handoff Contract

1. **What changes**：`production/q042_executor.py`（F1/F2：建议块 + 分类；fire 路径内）；`q042_gate_log.jsonl` schema 增可选 `ammo_advisory`。episode 分类的 trailing 计算可放 executor 内部 helper（SPX 日线已在 executor 可得）。
2. **Invariants**：fire/armed/sizing/cap；AC14.1 既有行；AC16；094.2/094.3 全部 AC。
3. **Acceptance checks**：AC-94.4-1..6（关键 = AC-3 历史对齐）。
4. **Out of scope**：见上节。
5. **Failure / rollback**：建议块内容错误不影响交易安全（提示性质）；若 AC-3 对齐 < 33/35 → 停止实施回 Quant 复核分类定义。

## Quant standing obligation（随本 spec 登记）

首次 live BPS fallback 执行前后，Quant 须完成 fallback 腿的 **CALIB+成本级验证**（`research_bs_flat_vix_pricing_bias` 强制：合成 credit 结论 research-grade，P6 已给 -2vp bracket，正式采纳补 CALIB 口径）；突发型分类每积累 1 次新触发即更新 P6 分层账本（n=4 → n≥8 时复检"空仓"分支）。

---
Status: DONE
