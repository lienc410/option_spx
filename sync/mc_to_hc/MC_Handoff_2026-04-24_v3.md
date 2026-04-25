# MC Handoff 2026-04-24 v3

> 修订说明：
> - 本文件基于 `sync/mc_to_hc/MC_Handoff_2024-04-24.md` 整理
> - 在 `v2` 基础上吸收 MC 反馈中的 6 项修正（R1-R6）
> - 仅做 OCR 勘误、排版清理、术语标准化、编号修复
> - 不主动改写 MC 原始结论；如与 HC 当前 canonical 编号体系有冲突，保留 MC 原意并明确标注

## 基本信息

- 上次同步日期：2026-04-10
- 本次 MC 工作期：2026-04-11 到 2026-04-24
- 周期性质：长周期 MC 工作期
- 覆盖范围：共 14 天，包含多条 SPEC 链路与多轮 ChatGPT review

## 本期摘要

1. 完成 aftermath 研究主线
   - 从 `Q018` 双峰漏抓，一路推进到 `SPEC-071 V3-A broken-wing IC`
   - 中间涉及 5 个 SPEC 和 7 轮 ChatGPT review

2. 发现两类 live 与 backtest 偏差
   - `Q029`：engine 硬编码 `qty = 1`，忽略 selector 的 `SizeTier`
     - 结果：约 36% 的 HIGH_VOL 交易，在 live 执行是 `1` 张 XSP，和 research / engine 的 `1` 张 SPX 存在约 `10x` notional 差异
   - `Q019`：close 口径 VIX 与 live 的 open 口径 VIX，在约 `4.63%` 的天数上会触发不同的 aftermath 结果

3. 沉淀治理规则
   - 新增 4 条 `CLAUDE.md` 治理规则
   - 新增 1 条 Bloomberg Windows 调用规范
   - 关键规则包括：
     - blocking AC 漏报默认 `FAIL`
     - `PASS with ADDENDUM` 仅允许一次例外
     - handoff 强制 `research` / `live` 双列 reporting
     - aftermath 类 SPEC 必须做全引擎验证

## 当前状态快照

### 当前推荐生产配置

- `overlay_mode = disabled`
- `shock_mode = shadow`
- `use_atr_trend = True`
- `bearish_persistence_days = 1`
- `AFTERMATH_OFF_PEAK_PCT = 0.10`
- `IC_HV_MAX_CONCURRENT = 2`
- `aftermath path = IC_HV`
- `long_call_delta = 0.04`
- `long_put_delta = 0.08`
- `DTE = 45`（保持不变）

### 当前最高优先阻塞

- `/ES runtime safeguards`
  - 尚未有 Spec
  - 对应 `Q013`

### 当前 `PARAM_MASTER` 版本

- `v3`

本期有多条参数变更，见下节。

## 参数变更

### 1. `AFTERMATH_OFF_PEAK_PCT`

- 旧值：`0.05`
- 新值：`0.10`
- 来源 SPEC：`SPEC-066`
- 原因：`Q018 Phase 2-D` cap sweep 结论
- HC ship：2026-04-20
- MC 同步：2026-04-21

### 2. `IC_HV_MAX_CONCURRENT`

- 旧值：`1`
- 新值：`2`
- 来源 SPEC：`SPEC-066`
- 原因：`Q018` 双峰 aftermath 第二峰捕获
- HC ship：2026-04-20
- MC 同步：2026-04-21

### 3. `hv_spell_trade_count`

- 旧逻辑：单一 scalar 计数
- 新逻辑：per-strategy dict 计数
- 来源 SPEC：`SPEC-068`
- 原因：
  - `2026-03` 双峰 HV spell aggregate 计数会超过 `max_trades_per_spell = 2`
  - 从而阻挡 aftermath `IC_HV` 第二笔
  - 现改为按 `strategy_key` 独立计数

### 4. engine `_build_legs` 的 IC 长腿构造

- 旧逻辑：`wing-based`，即 `SPX ± wing`
- 新逻辑：`delta-based`，即使用 `long_d` delta 查询
- 来源 SPEC：`SPEC-070 v2`
- 原因：
  - `SPEC-070 v1` FAIL
  - selector 用 `delta-based`，engine 用 `wing-based`
  - 两侧约定不一致，导致高 SPX 环境下，原本想把 `LP` 从 `0.06 -> 0.08`，实际反而把 11 个 aftermath 事件的 `LP` 移得更远 OTM
  - `v2` 只做语义对齐

### 5. aftermath `IC_HV` 的 `long call delta`

- 参数名：`aftermath IC_HV long call delta`
- 旧值：`0.06`
- 新值：`0.04`
- 来源 SPEC：`SPEC-071`
- 原因：
  - `Q028` 三阶段研究 + `R6` review
  - broken-wing IC 比对称 IC 在 aftermath tail protection 更优
  - 选择 `V3-A` 作为 compromise candidate
  - `V3-C` 的 `LC = 0.03` 留作 `Q032` 监控

### 6. aftermath `IC_HV` 的 `long put delta`

- 参数名：`aftermath IC_HV long put delta`
- 旧值：`0.06`
- 新值：`0.08`
- 来源 SPEC：`SPEC-071`
- 原因：同上，broken-wing 配对的 put 侧

### 7. `BEAR_CALL_DIAGONAL`

- 旧值：存在于 `StrategyName` enum
- 新值：从整个代码库删除
- 来源 SPEC：`SPEC-073`
- 原因：
  - `Q030` dead code cleanup
  - selector 从未 emit 该策略
  - 影响：6 个生产文件 + 1 个审计脚本 + 5 份文档

## SPEC 决策

### `SPEC-066`

- 校验：`SPEC-066（零六六）`
- 新状态：`DONE`
- PM 决策日期：2026-04-20
- 备注：
  - HC 通过 `Q018 Phase 2-D` cap sweep
  - 选定 `cap = 2 + OFF_PEAK = 0.10`
  - MC 在 2026-04-21 已同步 F1 常量

### `SPEC-068`

- 校验：`SPEC-068（零六八）`
- 新状态：`DONE`
- PM 决策日期：2026-04-22
- 备注：
  - per-strategy spell throttle
  - 解决 `2026-03` 第二峰漏抓
  - 含 5 项 unittest，全 PASS

### `SPEC-069`

- 校验：`SPEC-069（零六九）`
- 新状态：`DONE`
- PM 决策日期：2026-04-22
- 备注：
  - `open-at-end` 未平仓持仓在 UI 显示橙色 `OPEN` badge
  - 新增 artifact 字段 `open_at_end`
  - 147 tests 全通过

### `SPEC-070 v1`

- 校验：`SPEC-070（零七零）v1`
- 新状态：`FAIL`，随后 `SUPERSEDED`
- PM 批准日期：2026-04-22
- Review FAIL 日期：2026-04-23
- 备注：
  - v1 试图把 aftermath `IC_HV` 的 `LP` 从 `0.06` 改到 `0.08`
  - review 发现 selector 与 engine 约定不一致（delta vs wing）
  - 11 个 2018 年后事件反方向移动 `LP`
  - 后被 `v2` 替代

### `SPEC-070 v2`

- 校验：`SPEC-070（零七零）v2`
- 新状态：`DONE with PASS + ADDENDUM`
- PM 决策日期：2026-04-23
- 备注：
  - `v2` 只做 engine 对齐，不做 `v1` 的 wing shift
  - 全引擎验证通过
  - 这是首次且唯一的 `PASS + ADDENDUM` 例外

### `SPEC-071`

- 校验：`SPEC-071（零七一）`
- 新状态：`DONE`
- PM 决策日期：2026-04-23（APPROVED）
- Review 过程：
  - Review #1：FAIL，随后 handoff v2
  - Review #2：PASS
  - `SPEC-071 addendum`：2026-04-24
- 最终落地：
  - aftermath broken-wing IC
  - `V3-A = LC 0.04 + LP 0.08`
  - `DTE = 45` 不变
  - `R6 compromise` 选 `V3-A`，不选 `V3-C`
  - 原因：`V3-C` 的 `LC = 0.03` 有 liquidity concern
  - `V3-C` 进入 `Q032 monitor-revisit`

### `SPEC-072`

- 校验：`SPEC-072（零七二）`
- 新状态：`MC-side DONE`
- PM 决策日期：2026-04-24
- 备注：
  - frontend dual-scale display
  - broken-wing visual highlight
  - 单文件：`web/html/spx_strat.html`
  - 不动 backend
  - `AC10 live smoke test` 仍 pending HC deploy

### `SPEC-073`

- 校验：`SPEC-073（零七三）`
- 新状态：`DONE`
- PM 决策日期：2026-04-24
- 备注：
  - `BEAR_CALL_DIAGONAL` dead-code cleanup
  - 6 个生产文件 + 1 个审计脚本 + 5 份文档
  - `0` behavior change
  - 154 tests 全通过

### `SPEC-067`

- 校验：`SPEC-067（零六七）`
- 新状态：`DRAFT`
- 备注：
  - `/ES runtime safeguards`
  - 等 AMP 实施
  - 对应当前 blocker `B1`

## 研究发现

### `F001`

- 内容：aftermath `IC_HV` 替换方向被证伪
- 结论：
  - `Q025` 两轮评审驳回
  - `BPS_HV own-exit`
  - `Bull Call Spread`
  - `LEAP long call`
  - 三个替换方向均被 `Q025 full universe` 研究否决
- 相关 SPEC：`SPEC-071`

### `F002`

- 内容：IC-family 结构选择
- 结论：
  - `Q026` 确认 broken-wing 优于 richer wing / 5th-leg tail put
- 依据：`Q026` 三阶段研究
- 相关 SPEC：`SPEC-071`

### `F003`

- 内容：selector 与 engine 的 IC 长腿约定长期不一致，是历史遗留问题，不是 `SPEC-070 v1` 引入
- 结论：
  - `Q027 narrow audit`
  - `10` 策略 × `3` era × `23` legs
  - 除 `IC_HV` 外全部 `0 mismatch`
- 相关 SPEC：`SPEC-070 v2`

### `F004`

- 内容：engine 硬编码 `qty = 1`，忽略 selector 的 `SizeTier`
- 结论：
  - 约 `36%` HIGH_VOL 交易在 live 是 `1 XSP`
  - 但 engine 用 `1 SPX` 模拟
  - 导致所有 aftermath 研究的 magnitude 约 `10x` 高估 live 实际
- 依据：`Q029 5-dim parity audit`
- 相关 SPEC：无
- 产出：`Q033 Option B+E resolution`

### `F005`

- 内容：BS sim 对 aftermath 研究出现两次 systematic over-predict
- 结论：
  - `SPEC-071 sim +$1,861 vs engine +$115`
  - 约 `16x` over-predict
  - `Q031` 中 sim 预测 `DTE = 60` 更优，但 full-engine 结果 `sign inverted`
- 依据：`SPEC-071` 和 `Q031` 对比
- 相关 SPEC：无
- 产出：
  - `CLAUDE.md` 新规则
  - aftermath 类 SPEC 必须全引擎验证

### `F006`

- 内容：close-based VIX 与 open-based VIX 存在系统性差异
- 结论：
  - `4.63%` 天数的 aftermath 结果不同
  - regime 层 `9.71%` 天数不同
  - trend 层 `31.54%` 天数不同
  - `319` 个 aftermath flip 中：
    - `179` 个是 `close=False / open=True`
    - `140` 个相反
  - 即 backtest 会漏抓一部分 live 信号，也会反向多抓一部分
- 依据：`Q019 Phase 1` 全 27 年 `BBG OHLC` 分析
- 相关 SPEC：
  - `SPEC-064`
  - `SPEC-066`
  - `SPEC-068`
  - `SPEC-070 v2`
  - `SPEC-071`
- PM 决策：待定 `A / B / C`

### `F007`

- 内容：`SPEC-066` shipping 后，`2A-lite retrospective` 显示 `EXTREME_VOL` hard stop 已缓解 2008 tail 假设
- 结论：
  - `2A-lite retrospective` 显示
  - `EXTREME_VOL` hard stop 已经 mitigate 2008 GFC 假设 tail
  - Phase 1 Variant A 预期的 `2008-09 -7968` 单笔损失，在整合 stack 下不再 materialize
- 依据： 
  - Q018 R8 retrospective
  - `2A-lite` 
  - `2C-lite`
- 相关 SPEC：`SPEC-066`

## 策略逻辑变更

### 1. aftermath `IC_HV` 入场结构

- 旧逻辑：对称 IC，即 `LC 0.06 + LP 0.06`
- 新逻辑：broken-wing，即 `LC 0.04 + LP 0.08`
- 适用范围：仅在 aftermath 场景生效
- 相关 SPEC：`SPEC-071`

### 2. `IC_HV` concurrency cap

- 旧逻辑：硬编码 1 槽位
- 新逻辑：`cap = 2`
- 含义：在 aftermath 场景下，允许最多 2 笔 `IC_HV` 并发
- 相关：`SPEC-066` 和 `Q022`

### 3. HV spell throttle

- 旧逻辑：aggregate 计数，所有 HV 策略共享 spell budget
- 新逻辑：per-strategy dict 计数，每个 HV 策略独立 spell budget
- 相关 SPEC：`SPEC-068`

### 4. engine IC 长腿构造约定

- 旧逻辑：`wing-based`，即 `SPX ± 50`
- 新逻辑：`delta-based`，即按 `long_d` delta 查询
- 目的：对齐 selector
- 相关 SPEC：`SPEC-070 v2`

### 5. 策略目录

- 旧逻辑：包含 `BEAR_CALL_DIAGONAL`，即 8 个策略
- 新逻辑：移除 `BEAR_CALL_DIAGONAL`，仅 7 个有效策略
- 原因：selector 从未 emit 该策略，属于 dead code cleanup
- 相关 SPEC：`SPEC-073`

## 开放问题更新

### `Q017`

- 新状态：`resolved via SPEC-064`

### `Q018`

- 新状态：`CLOSED`
- 日期：2026-04-24
- 结论：
  - resolved in production via `SPEC-066 + Q022 + SPEC-068 + SPEC-069`
  - `R8 retrospective validation` 完成
  - `2A-lite` 表明 `EXTREME_VOL` 已 mitigate tail
  - `2C-lite` 表明 `OFF_PEAK = 0.10` 形成 stable plateau
  - 含 6 条显式 reopen triggers

### `Q020`

- 新状态：`open`（低优先）
- 内容：
  - MC 认为 `backtest_select` 简化导致 `SPEC-064 AC10` 数量偏少
  - HC 目标 `22 ± 3`
  - MC 实测 `5`
  - MC 认为这不是 bug，而是 measurement gap
  - 根因：MC 缺 `VixTermStructure` 等历史上下文

### `Q021`

- 新状态：`open`（research only）
- 内容：
  - `SPEC-066` 的 alpha 归因，是否来自 distinct second-peak 语义，而非 back-to-back re-entry
  - HC 原提案内是 `Q020`
  - 但 MC 端已占用 `Q020` 编号
  - 因此 HC 问题在 MC 语境中重编号为 `Q021`

### `Q022`

- 新状态：`resolved`（2026-04-21）
- 结论：
  - MC backtest engine 单仓位到多仓位架构重构完成
  - 三阶段交付：
    - Phase 1 fingerprint 一致
    - Phase 2 `cap = 2` 激活
    - Phase 3 `139 tests` 全通过

### `Q023`

- 新状态：`resolved`（2026-04-22）
- 结论：
  - multi-position 后风险画像
  - 27 年数据无新风险模式
  - MaxDD `+75%` 属于 trade count 缩放，可接受

### `Q024`

- 新状态：`resolved`（2026-04-22）
- 结论：
  - aftermath false-positive 过滤研究结果为 `NULL RESULT`
  - 现 `SPEC-066` 门槛已过滤 `peak_10d < 28` 的 legacy 情况
  - `SPX stabilization filter` 出现 backfire

### `Q025`

- 新状态：`resolved`（2026-04-22）
- 结论：
  - aftermath 下 `BPS_HV` / `Bull Call Spread` / `LEAP` 三个替换方向全证伪
  - `IC + tail put` 变体在部分场景强，但依赖 legacy artifact
  - ChatGPT `R3` 驳回
  - `DEFERRED` 到 `Q026`

### `Q026`

- 新状态：`resolved`（2026-04-22）
- 结论：
  - IC-family 对比里，broken-wing 胜过 richer wing / 5-leg tail
  - 2nd Quant endorse `A + C` 路径
  - 产出 `SPEC-071` 候选

### `Q027`

- 新状态：`CLOSED NULL`（2026-04-23）
- 结论：
  - narrow-scope leg-construction convention audit
  - `10` 策略 × `3` era × `23` legs 全部 `0 mismatch`
  - `SPEC-070 v2` 是最后一个历史约定错配
  - ChatGPT `R5` 要求不能标成 `systemic audit complete`
  - 只能称为 `leg-construction convention audit`
  - 未审 5 维度归入 `Q029`

### `Q028`

- 新状态：`resolved`（2026-04-23）
- 结论：
  - aftermath tail protection 在 aligned baseline 下重研究
  - broken-wing IC family dominate
  - 产出 `SPEC-071` 候选

### `Q029`

- 新状态：`CLOSED`（2026-04-24）
- 结论：
  - 其他 5 个 parity 维度 audit 结果：`4` 个 `no issue / minor drift`
  - `1` 个 material issue：engine 硬编码 `qty = 1`，忽略 `SizeTier`
  - 触发 `Q033 + Q034` follow-up

### `Q030`

- 新状态：`CLOSED via SPEC-073`（2026-04-24）
- 结论：
  - `BEAR_CALL_DIAGONAL` dead code cleanup 完成

### `Q031`

- 新状态：`CLOSED NULL`（2026-04-24）
- 结论：
  - aftermath `IC_HV DTE = 60` 被 full-engine 驳回
  - `Q028 Phase 3` 中，BS sim 预测的 `DTE = 60` 优势在 full-engine 下被推翻
  - system Sharpe 约 `-0.005`
  - worst single case 恶化约 `2.2x`
  - 属于第 2 次 BS sim over-prediction pattern

### `Q032`

- 新状态：`open`（monitoring only）
- 内容：
  - `V3-C`：`LC = 0.03`
  - 作为 monitor-and-revisit 候选
  - `SPEC-071` 落地后，观察前 `5-10` 笔 live aftermath
  - 若 `V3-A` worst-case 改善达标，且 `LC = 0.03` liquidity 良好，再考虑升级

### `Q033`

- 新状态：`CLOSED`
- 日期：2026-04-24
- 结论：
  - `SizeTier -> Contract Qty`
  - ChatGPT `R7` 裁决为 `Option B+E`
  - engine 保持 `1-SPX uniform`，不改代码
  - 强制所有 handoff / SPEC / RDD 增加
    - `research_1spx`
    - `live_scaled_est`
    两列数字
  - HIGH_VOL scale factor 完整列表：
    - `SMALL tier x 0.1`
    - `FULL tier x 2`
    - `HALF tier x 1`
  - 产出物：
    - 对 `SPEC-071` 加 `live-scale addendum`

### `Q034`

- 新状态：`open`（optional, low priority）
- 内容：
  - strike rounding `/5 grid`
  - engine 当前 round 到 int
  - live 是 `/5`
  - 最多 `±2.5` 点漂移
  - 仅在 precision execution matching 场景下 material

### `Q035`

- 新状态：`open`（long-term）
- 内容：
  - future live-scale backtest engine architecture / RDD
  - 若未来希望 engine 直接输出 live-scale 数字，而不是 `research scale × live_factor` 换算
  - 则需要完整架构重写
  - `R7` 建议 defer

### `Q019`

- 新状态：`Phase 1 complete, decision deferred`
- 内容：
  - close vs open based VIX 的 27 年全期 `BBG OHLC` 分析已完成
  - aftermath 层 `4.63%` flip
  - regime 层 `9.71%` flip
  - 存在三个 PM 决策选项：`A / B / C`
  - Claude 倾向 `A + C` 组合

## Master Doc 影响清单

- `PARAM_MASTER` 需要更新：`yes`
  - 多条参数变更，版本号 `v2 -> v3`

- `open_questions` 需要更新：`yes`
  - `Q018`
  - `Q022`
  - `Q023`
  - `Q024`
  - `Q025`
  - `Q026`
  - `Q027`
  - `Q028`
  - `Q029`
  - `Q030`
  - `Q031`
  - `Q033` 全部 `CLOSED`
  - `Q019` `DEFERRED`
  - `Q020`
  - `Q021` 新开
  - `Q032`
  - `Q034`
  - `Q035` 新增

- `strategy_status` 需要更新：`yes`
  - aftermath `IC_HV` 结构改为 broken-wing
  - concurrency cap = 2
  - spell throttle = per-strategy

- `research_notes` 需要更新：`yes`
  - 本期 7 条研究项目
  - `RESEARCH_LOG.md` 需要新增 2026-04-24 条目

- `SPEC` 状态需要更新：`yes`
  - `SPEC-066 DONE`
  - `SPEC-068 DONE`
  - `SPEC-069 DONE`
  - `SPEC-070 v2 DONE`
  - `SPEC-071 DONE + addendum`
  - `SPEC-072 MC-side DONE`
  - `SPEC-073 DONE`

## HC 指令

### 指令 1：确认 `SPEC-066` 参数

- `AFTERMATH_OFF_PEAK_PCT = 0.10`
- 与 MC 端同步
- HC 是源头
- MC 在 2026-04-21 已同步

### 指令 2：确认 `SPEC-071` 的 broken-wing live selector 输出

- aftermath 路径返回的 legs 应为：
  - `LC delta = 0.04`
  - `LP delta = 0.08`
  - `short call / short put delta` 保持 `0.12` 不变
  - `DTE = 45` 不变

### 指令 3：部署 `SPEC-072` frontend

- 单文件：`web/html/spx_strat.html`
- handoff：`task/SPEC-072_deploy_handoff.md`
- 含 5 个 smoke test 场景
- 需要 HC 在 old Air 部署后做 live smoke test
- `AC10` 为 HC 侧验证

### 指令 4：留意 `Q019 Phase 1` 发现

- `319` 个 aftermath flip over 27 years
- `SPEC-064 / SPEC-066 / SPEC-068 / SPEC-070 v2 / SPEC-071`
  全都基于 close-based VIX 做决策
- 若 PM 决定走 `A / B / C`，会有后续指令

### 指令 5：接收并整合 `CLAUDE.md` 新治理规则

- blocking AC 即 `FAIL`
- `PASS with ADDENDUM` 一次例外
- handoff 双列 reporting
- aftermath SPEC 必须全引擎
- Bloomberg Windows launcher pattern

### 指令 6：`Q033 Option B+E resolution`

- 未来所有涉及：
  - `PnL`
  - `worst`
  - `SeqMaxDD`
  - `BP`
  - handoff / SPEC / RDD
- 必须同时含：
  - `research_1spx`
  - `live_scaled_est`
- aftermath HIGH_VOL 默认 `scale × 0.1`

## 不要推断的项目

### 项目 1：`Q019 Phase 1` 的 PM 决策

- PM 推迟了 `A / B / C` 选择
- HC 不要自行假设
- Claude 倾向 `A + C`，但最终仍要等 PM 拍板

### 项目 2：`SPEC-067 / ES runtime safeguards`

- PM 尚未有 DRAFT
- HC 不要自行起草 Spec
- 可提醒 PM：这是当前 top blocker `B1`

### 项目 3：`Q032 / V3-C` 升级时机

- 需要 HC 积累 `5-10` 笔 live aftermath 后才能触发评估
- HC 不要过早自行升级到 `V3-C`

### 项目 4：`Q035 / future live-scale engine`

- 这是 long-term watch 项
- HC 不要自行启动
- 仅当 `R7 Option E` 的 dual-column 体验不佳，并触发 PM 决定时才考虑

## 下周 MC 计划

### 计划 1：等待 PM 决定 `Q019` 走 `A / B / C`

- 若 `A`：写 `RDD-Q019 CLOSE`
- 若 `B`：Phase 2 重跑 `SPEC-066` 和 `SPEC-071` 关键 sample 的 open-based reproduction
- 若 `C`：给 `CLAUDE.md` 增加 aftermath 双口径 sensitivity 规则

### 计划 2：`SPEC-067 / ES runtime safeguards`

- 若 PM 批准起草，Claude 协助写 DRAFT Spec
- 最小范围：
  - stop 条件系统监控
  - bot alert

### 计划 3：接收 HC Return 包

- 整合：
  - `SPEC-066`
  - `SPEC-068`
  - `SPEC-069`
  - `SPEC-070 v2`
  - `SPEC-071`
  - `SPEC-072`
  - `SPEC-073`
  的 HC 侧状态
- 确认 MC 端参数与 HC 端 `PARAM_MASTER` 一致，无漂移

### 计划 4：继续监控 `Q032`

- `V3-C monitor-revisit` 触发条件：
  - `5-10` 笔 live aftermath

### 计划 5：若 HC 完成 `SPEC-072` 部署

- 回收 Claude review `AC10 live smoke test` 结果

