# SPEC-094.8 — BPS fallback 触发日现场校验（三态 + 自动冻结）

## 目标

DD Overlay 表达讨论三轮外审的最终签字条件（verdict: Accept for implementation）。
BPS fallback（094.4 三分支之二）的定价真实性是 P6 剩余最大不确定性（P6c 实证：
FLAT 高估净 credit +45%、保守端仍 +26%、CALIB −2.1%，平静期）；危机期不可
预验 → 治理解法 = 触发日现场校验 + 预注册容差 + 自动冻结，零现场裁量。

## 规则（预注册，2026-07-30 外审 ratify）

| |err%|（CALIB vs 现场 vendor mid credit）| 状态 | 动作 |
|---|---|---|
| ≤10% | PASS | fallback 分支照常，advisory 附校验标注 |
| 10–15% | WARNING | 同上（标注 WARNING）——监控 CALIB 漂移用 |
| >15% 或当日无法校验 | FREEZE / UNVERIFIABLE | **fallback 自动降级为空仓分支**，advisory 明示已冻结与原因 |

**阈值选择为治理一致性而非统计最优**（threshold selected for governance
consistency rather than statistical optimality；15% 对齐 F4 tie-out 门槛惯例，
10% 警戒线为监控约定）。三态每次评估落 `data/q042_fallback_check_log.jsonl`
（运行时文件，untracked）——外审非阻塞建议：记录三态而非仅冻结与否，供长期
CALIB 漂移监控与未来阈值调整供证。

## 接口定义

**F1** `production/q042_executor.py`：`_classify_fallback_err`（纯函数三态）+
`_fallback_onsite_check`（Schwab 现场 put 链 Δ0.30/0.15 腿 mid → real credit，
CALIB put 曲线同 strikes 定价 → err%）+ `_log_fallback_check`。集成于
`_ammo_advisory` 的 bps_fallback 分支：校验先于建议；FREEZE/UNVERIFIABLE →
branch=`bps_fallback_frozen`、文案替换为空仓指令。任何异常 = UNVERIFIABLE
（fallback 为次选，天然 fail-closed；094.4 提示不拦语义不变——冻结改变的是
建议内容，不拦 fire/记账）。
**F2** 环境（fallback 只在"现金不足+铺垫型"评估）：充足现金分支零校验零日志。
**F3** 日常漂移监控由既有 q085 skew monitor（moff 日更）承担，本 log 记录
fire 日实弹校验点。

## 验收标准

| AC# | 描述 | 结果 |
|---|---|---|
| AC-94.8-1 | 三态分类边界（≤10 PASS / ≤15 WARNING / >15 FREEZE，含 P6c 量级 −45.5→FREEZE） | ✅ |
| AC-94.8-2 | PASS/WARNING → 原 fallback 分支保留 + 校验标注；payload 带 fallback_check | ✅ 2 tests |
| AC-94.8-3 | FREEZE → 降级空仓、文案含误差与容差、无 strikes 残留；UNVERIFIABLE（异常）同语义 | ✅ 2 tests |
| AC-94.8-4 | 三态记录落盘（date/state/err/credits）；测试环境重定向 tmp | ✅ |
| AC-94.8-5 | 充足现金分支零校验零日志（只在 fallback 评估时跑） | ✅ |
| AC-94.8-6 | 回归：094.2/4 相邻套件绿；全仓测试绿 | ✅ 42 邻近 + 全套见部署行 |

## Handoff Contract

What changes：`production/q042_executor.py`（三函数 + advisory 集成）、`.gitignore`、
`tests/test_spec_094_8.py`（新）、`tests/test_spec_094_2/4.py`（fixture 注入 PASS 默认 + log 重定向）。
Invariants：fire/gate/settle/记账零变化；094.4 三分支语义仅在校验失败时改变建议文案。
Rollback：advisory 集成块摘除即回（校验函数无其他消费方）。

---
Status: DEPLOYED 2026-07-30（外审 verdict: Accept for implementation；非阻塞建议三态记录已内建）
