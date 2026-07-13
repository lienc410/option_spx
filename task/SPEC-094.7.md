# SPEC-094.7 — Sleeve B 重设计：深跌阶梯（paper-only）

## 目标

Q102 P1+P2（R-20260712-05/-06）confirmatory 门槛判定的落地。PM 2026-07-12 授权
自主推进（"可以自行审核候选方案，一直推进完整结论和代码实现，前端修改"）。
B 保持 **production 0%**；本 spec 全部为 paper 语义 + 告警，供证据积累，
paper→production 时机归 PM（feedback_spec_review_obligation）。

## 研究依据（预注册门槛判定，q102_p2_gates.csv）

| 候选 | CALIB/STRESS 或两括号端 vs 含股息指数基准 | 判定 |
|---|---|---|
| 浅档 −15% immediate×持有×5%/90 | +323.3k/+163.7k vs +40.7k | ✅ |
| 深档 ≤−25% spread（任何宽度） | −34.6k/−106.4k vs −14.9k | ❌ 淘汰 |
| 深档 ITM85 LEAP 365d | +108.5k/+46.6k vs +49.7k | ❌（×1.0 端败） |
| **深档 ITM85 LEAP 730d** | **+210.4k/+131.8k vs +104.7k** | ✅ |
| 自动 rung-stop（全档） | 压力档 −2.1k < 基准 | ❌ → 降级为 FYI 告警 |
| settle jitter D75/90/105 | 全过 | ✅ |

剂量-响应自洽：浅档买"反弹"（90d 窗口足够），深档买"周期复原"（需 2y 跑道 +
内在价值垫）；深档 MA10 reclaim 是熊市反弹顶陷阱（P1 T2, −146.9k）故全档 immediate。

## 接口定义（新 B 状态机 = 唯一真值源 signals/q042_trigger.py）

**F1 阶梯状态机**：rungs {−15,−25,−35,−45}%（`_B_RUNGS`），每 rung 独立
armed、touch 即 fire（T+1 入场，同 A）；全体 rung 在 ddATH ≥ −2% 时复位
（`_REARM_THRESHOLD` 沿用）。watching/MA10-reclaim 机制删除。
state schema v2：`sleeve_b: {schema:2, rungs:{"-15":{armed,active_position_id,
active_position_expiry},...}, breach_alerted:[...]}`；v1 → v2 迁移在 load 路径
（v1 有 active position → 归 −15 档）。同日跨多 rung（gap 崩盘）→ 多发。
**F2 结构路由（strategy/q042_sizing.py 单真值）**：rung = −15% → 现结构
ATM/+5% SPX spread DTE90（compute_sizing "B" 不变，回归兼容）；rung ≤ −25%
（`_B_DEEP_THRESHOLD`）→ **XSP ITM LEAP**：K = round(S×0.85/10)（XSP 尺度，
`_B_LEAP_K_RATIO`），DTE 730（`_B_LEAP_DTE`），est_debit = BS(σ=VIX×0.875
括号中点, q=1.6%, r=4.5%)/10（XSP per-share），contracts = floor(10%
NLV / (est×100))。paper sizing 10% NLV/entry 不变；并发 rung 各自独立记账。
**F3 rung 击穿 FYI**（替代被门槛淘汰的自动止损）：EOD 对每笔在场 B 仓，
若当日 ddATH ≤ 该仓入场 rung 的下一档（−15→−25，…，−45→−55 floor）→
gateway FYI 一次性告警（state.breach_alerted 去重，每仓一生一次）；正文
纯事实（rung/入场日/当前 ddATH/到期日），F2 禁令词表沿 SPEC-142。
**F4 结算扩展（production/q042_positions.py）**：ledger 行新增
`instrument`("SPREAD"|"XSP_LEAP")、`rung`、`symbol` 字段；settle 对
XSP_LEAP 行：underlying = spx_close/10、无 short 腿（**不得**走
`get("short_strike",0)` 默认路径——0 默认会把整个标的当 short 赔付）；
state 清仓按 rung 匹配 active_position_id。
**F5 四层同步**：backtest/q042_engine.py B 侧消费 get_q042_history 新
entries（含 rung/instrument），LEAP 行 CSV short_strike=0 + instrument 列；
web/server.py params.sleeve_b 块改发 rungs/deep 结构参数；q042.html B 卡
渲染阶梯 armed 灯 + 多仓；state_map.html 引擎卡文案更新。

## 边界条件

- 现 paper 账本无在场 B 仓（audit 07-07 + 今日核对）→ 无迁移中仓位。
- LEAP est 为括号中点估价，paper 实际 fill 走 SPEC-094.3 pending-fill 流程记录。
- 4 档并发 × 10% = 40% NLV paper 上限；**production promote 前置条件**（G3）：
  现金叠栈规则必须按彼时池水位重算并写入 promote spec。
- XSP LEAP 上市周期为季度/年度到期，live 时按最近上市到期 snap；paper 用精确 +730d。

## 不在范围内

production cap（维持 0%）；A sleeve 一切；自动止损（门槛已否）；LEAP 真实链
校准（登记为 promote 前数据缺口）。

## 验收标准

| AC# | 描述 | 结果 |
|---|---|---|
| AC-94.7-1 | 状态机：−15 touch→fire_B(rung −15)；gap 日跨 −15/−25 → 两发；re-arm −2% 全档复位；每 rung 每周期一发 | ✅ 3 tests（含闩锁：re-arm 后被在场仓挡、清仓后补发） |
| AC-94.7-2 | v1→v2 schema 迁移：旧 state（含 in_watching/active pos）load 后正确归档；094.2/3/4 旧 fixture 全绿 | ✅（v1 armed/仓归 −15 档、in_watching 置 not-armed、深档全新 armed、幂等）+ 旧 fixture 经 load 路径迁移全绿 |
| AC-94.7-3 | 结构路由：rung −15 → SPX spread（与 094.5 前逐位一致）；rung −25/−35/−45 → XSP LEAP（K=round(S×0.85/10), DTE730, est>0） | ✅ |
| AC-94.7-4 | settle：XSP_LEAP 行按 spx/10 内在结算、无 short 默认路径污染；SPREAD 行结算与现行为逐位一致 | ✅ 3 tests（含毒化守卫 + 按 trade_id 只清对应 rung） |
| AC-94.7-5 | rung 击穿 FYI：触发一次且仅一次（breach_alerted 去重）；正文过 F2 禁令扫描；dry-run 零推送 | ✅ 3 tests（含 gap 日双档拦截 dedupe 不互吞） |
| AC-94.7-6 | 走查对齐：get_q042_history B 侧信号流 == q102 研究脚本 ladder_entries（immediate）逐日期一致（feedback_signal_translation_alignment_ac） | ✅ 10/10 事件逐 (date, rung) 相等；A 侧 38 零扰动 |
| AC-94.7-7 | 引擎/CSV/params 端点：B 行含 rung+instrument；params.sleeve_b 发 rungs 数组；全套回归（094.2/3/4/5/6/7 + 142）绿 | ✅ 81 passed；引擎 B n=10 WR80% maxDD −5.1%；payload smoke rungs 全量下发 |

**部署验证**：见下方 status 行。手动开仓端点/draft/前端 modal 均 rung 化（深档 LEAP 免 short strike）；141 AC-4 zero-diff 守卫在 commit 后复绿（工作树检查）。

## Handoff Contract

1. **What changes**：signals/q042_trigger.py（B 状态机 v2 + 迁移 + 走查）、strategy/q042_sizing.py（deep 路由常量 + compute_sizing rung 分支）、production/q042_executor.py（B 多发循环 + F3 告警 + F1 清仓 rung 化）、production/q042_positions.py（instrument 字段 + settle 分支 + 多仓查询）、backtest/q042_engine.py（B instrument 分支）、web/server.py（params.sleeve_b）、web/templates/q042.html + state_map.html（B 卡/文案）、tests/test_spec_094_7.py。
2. **Invariants**：Sleeve A 全链零 diff；production cap 0 不动；gateway/dedupe 语义沿用；paper ledger 旧行向后兼容（无 instrument 字段 = SPREAD）。
3. **Rollback**：git revert 单 commit + state 文件 schema v2→v1 手动降档（或直接删 sleeve_b 键让 default 重建——无在场仓位期间零损失）。

---
Status: DEPLOYED 2026-07-13 (autonomous per PM grant; old Air verified)
