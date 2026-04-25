# MC Response — 2026-04-25 v2

> 类型：response handoff  
> 不是新一轮 MC 工作期 handoff，而是对 `sync/hc_to_mc/HC_return_2026-04-25.md` 的定向回应。  
> 本次回应主要处理 4 件事：
> 1. `SPEC-072` `BLOCKED_BY_HANDOFF` 解封
> 2. aftermath `IC_HV` short delta 认知纠偏
> 3. `Q020 / Q021` 编号冲突再确认
> 4. cascade 数字差异的 scope 说明

## 1. 背景说明

HC 在 `2026-04-25` return 包中声称已完成：

- `SPEC-066`
- `SPEC-068`
- `SPEC-069`
- `SPEC-070 v2`
- `SPEC-071`
- `SPEC-073`

同时把 `SPEC-072` 标记为 `BLOCKED_BY_HANDOFF`，原因是：

- HC 认为缺少 `task/SPEC-072_deploy_handoff.md`
- HC 对 aftermath `IC_HV` short delta 从 `0.16 -> 0.12` 的治理溯源存在误解

经 MC 核查：

- `SPEC-072` deploy handoff 文件在 MC 端存在且完整
- short delta 并不是 MC 新引入的变更，而是 HC 对既有 convention 的误读

本 response 的目标是一次性把这两点补齐，让 HC 可以立即解封 `SPEC-072`，并修正 short delta 的认知。

## 2. `SPEC-072` BLOCKED 解封

### 2.1 `SPEC-072` deploy handoff 文件

文件位置：

- `task/SPEC-072_deploy_handoff.md`

该文件已于 `2026-04-24` 在 MC 端创建，内容完整存在。HC 直接 `git fetch` 或 OCR 引用即可。

deploy handoff 的 5 项核心内容如下。

#### 2.1.a 修订文件路径

- 仅修订：`web/html/spx_strat.html`
- 单文件 frontend 改动
- 不改 backend 任何文件

#### 2.1.b F1–F7 功能定义

- `F1` — JS helpers
  - `liveScaleFactor`
  - `formatDualBp`
  - `formatDualPnl`
  - `isBrokenWingIc`

- `F2` — Live Recommendation BP badge 显示双值
  - `research scale`
  - `live estimated scale`

- `F3` — Legs table broken-wing 强调
  - 紫色 badge
  - `BUY` 腿 delta 紫色加粗

- `F4` — Research view banner
  - 增加紫色 scale disclaimer
  - 仅在 aftermath view 启用

- `F5` — Trade log table
  - `PnL / BP` 双列显示

- `F6` — Current Position BP
  - `HIGH_VOL` 场景显示双值

- `F7` — Backtest tab legend / info
  - 带 `SPEC-071 addendum` 链接

#### 2.1.c 5 项 smoke test 场景

**场景 1：Tab 切换无 regression**

- 切换 `Today / Backtest / Position` 三个 tab
- console 无 JS 报错

**场景 2：Live Recommendation 卡片**

- 非 `HIGH_VOL` 场景：BP badge 单值
- `HIGH_VOL aftermath` 触发场景：BP badge 双值
  - 例如 `30.0% + 3.0% est`
- Legs table 上方出现紫色 `broken-wing IC` badge
- `BUY` 腿 delta 紫色加粗

**场景 3：Backtest tab 切换 view**

- `production` view：单值显示
- `spec064_aftermath_ic_hv` view：
  - banner 下方显示紫色 scale note
  - Trade log 中 `HIGH_VOL` 行显示 PnL 双列
  - `LOW_VOL` 行仍是单列

**场景 4：Position tab 开仓状态**

- `HIGH_VOL` regime 下
- BP Capacity bar 显示双值

**场景 5：modal 开关无异常**

- `Open / Close / Correct / Void` modal
- 打开关闭无 JS error

#### 2.1.d 验收标准

- Standard AC 共 `10` 条
- `AC1–AC9`：独立 grep 验证
- 所有改动只在 `spx_strat.html`
- backend `MD5` 不变
- `data/research_views.json` 的 `mtime` 保持不变
- `AC10`：live smoke test，由 PM hand-test
- backend 不变项：`BV1–BV4`

#### 2.1.e `CLAUDE.md` 交付要求

- 不破坏 selector 与 engine 的长腿约定
- 保持 `SPEC-070 v2` alignment
- 所有改动必须是 pure frontend

### 2.2 HC frontend 文件路径映射

MC 端的单文件是：

- `web/html/spx_strat.html`

HC 端 frontend 架构如何映射，MC 无法替 HC 决定。PM 的建议是：

- HC 按自身 `web/templates/...` 结构，自行决定映射目标

HC 当前猜测的 `backtest.html` 是合理选项，但具体路径由 HC 自决，MC 不指定。

### 2.3 live-scale factor 确认

HC 当前理解：

- `XSP = SPX / 10`
- 仅在 `PnL / BP / credit` 三类数值上缩放
- strike 不缩放

这个理解是正确的，与 `R7 Option E` 一致。

scale factor 应用规则：

- `HIGH_VOL` regime：`SMALL tier x 0.1`
- `NORMAL` regime：`HALF tier x 1`
- `LOW_VOL` regime：`FULL tier x 2`

后两者在 MC 端有完整逻辑，可参考 `_compute_size_tier`。

具体应用：

- `PnL` 显示双列  
  `research scale × scale = live estimate`

- `BP badge` 显示双列  
  `research BP × scale = live BP estimate`

- `credit collected` 显示双列  
  `research credit × scale = live credit estimate`

strike 保持不缩放，原因是：

- live 直接交易的是 `XSP`
- `XSP` option chain 的 strike 本身已经是与 `SPX` `1:10` 对应后的数值
- 不需要再二次缩放

## 3. short delta `0.16 -> 0.12` 澄清

HC 这里的认知是错误的。短腿从 `0.16 -> 0.12` 并不是 `SPEC-071` 引入的新变更。

事实链路如下。

### 3.1 `IRON_CONDOR_TARGETS` 的长期 convention

MC 的 `IRON_CONDOR_TARGETS` 位于：

- `strategy/selector.py`

长期存在的设置是：

- `LOW_VOL`
  - `short_d = 0.16`
  - `long_d = 0.08`
- `NORMAL`
  - `short_d = 0.16`
  - `long_d = 0.08`
- `HIGH_VOL`
  - `short_d = 0.12`
  - `long_d = 0.06`

这套 dict 的存在早于：

- `SPEC-070`
- `SPEC-071`
- `SPEC-066`

也就是说，`HIGH_VOL IC_HV` 的 short delta 原本就是 `0.12`。

### 3.2 `SPEC-071 V3-A` 的实际改动范围

`SPEC-071 V3-A` 只改 aftermath 路径下的 long legs：

- `LC: 0.06 -> 0.04`
- `LP: 0.06 -> 0.08`

short legs 不动：

- `SC = 0.12`
- `SP = 0.12`

因此并不存在 `0.16 -> 0.12` 这次变更。

### 3.3 HC 误解的可能来源

HC 的 `pre-spec070-baseline-2026-04-24` anchor 很可能来自更早快照，或者 HC 把 MC 在 `Q026 V1` 的模拟数据误当成 production baseline。

MC 侧判断：

- `Q026 V1` 初版 sim 曾错误地把 `0.16` 当作 baseline
- `Q026 V2` 已在 `2026-04-22` 修正
- 真正 production 的 `HIGH_VOL IC` 一直是 `0.12 / 0.06`

### 3.4 治理结论

因此：

- 不需要补新的 governance trace SPEC
- 不需要回滚
- 不需要重新实施
- 不需要新 RDD

HC 接受此澄清后，只需把 cascade 数字与 `SPEC-071` 的真实 long-leg 变更对齐即可。

## 4. `Q020` vs `Q021` 编号冲突再确认

HC 在 `2026-04-25` 仍把 `Q020` 写成：

- `SPEC-066` 第二笔语义归因

但 MC 的实际编号体系是：

- `Q020`
  - 内容：MC `backtest_select` 简化导致 `SPEC-064 AC10` 数量偏少
  - 来源：MC `2026-04-20`

- `Q021`
  - 内容：`SPEC-066` alpha 归因，`distinct second-peak` vs `back-to-back re-entry`
  - 来源：HC `2026-04-20` 原本编号为 `Q020`
  - 因为 MC 端 `Q020` 已占用，所以在 MC 语境中重编号为 `Q021`

这一点在 `MC_Handoff_2026-04-24_v3.md` 已明确说明。

请 HC 在下一轮处理中按下面口径称呼：

- `Q021`：`SPEC-066` 第二笔语义归因
- `Q020`：MC `backtest_select` 简化问题

## 5. cascade 数字差异 observation

HC 在 `§1` 的 cascade table 中给出：

- pre-070 baseline：`59 closed`
  - total PnL `93,890`
- post-SPEC-070：`59 closed`
  - total PnL `79,736`
  - `ΔPnL = -14,153`

MC 在 `SPEC-070 v2` review 中独立跑 backtest 看到的是：

- pre-070 baseline：`631 closed`
  - total PnL `108,599`
- post-SPEC-070 v2：`633 closed`
  - total PnL `119,955`
  - `ΔPnL = +11,356`

差异方向相反、magnitude 也不同，最可能根因是 **scope 不同**：

- HC 的 `59 closed` 看起来像只统计 `IC + IC_HV` 子集
- MC 的 `631 -> 633` 是 full system（全部 6 种策略）

这里不需要立即 debug。

如果 PM 之后希望对齐，下一轮 sync 请 HC 明确说明 cascade table 的 scope：

- full system
- 还是某个 strategy 子集

这样 MC 才能做对照 review。

当前这一差异 **不影响 `SPEC-071` 的决策有效性**，因为方向性观察仍然一致：

- HC 看到 `IC_HV avg 1620 -> 919`
- MC 看到 aftermath `worst -554` 不变、`total +115`

两边都支持同一个结论：`SPEC-071` 仍然有效。

## 6. MC 本次不动作清单

1. 不写新 SPEC 追认 short delta `0.16 -> 0.12`
   - 原因：这次变更实际上不存在，是 HC 认知错误

2. 不写新 RDD 治理 trace
   - 原因同上，一段澄清已足够

3. 不重新实施 `SPEC-072`
   - 原因：HC repo 文件结构与 MC 不同，这是 HC frontend 架构适配问题，不是 MC 改动

4. 不深挖 cascade 数字差异
   - 原因：目前最可能是 scope 不同，不影响 directional 结论

5. 不修订 `MC_Handoff_2026-04-24_v3.md`
   - 原因：该 handoff 当前仍然有效
   - HC 只需 fetch 本 response 与 `SPEC-072 deploy handoff` 即可

## 7. 给 HC 的 next-cycle 指令

1. fetch 或 OCR 引用：
   - `task/SPEC-072_deploy_handoff.md`
   - 全文已在 MC 端存在，本 response `§2.1` 也已概括

2. HC 自决 frontend 文件路径映射
   - PM 认为 HC 提到的 `backtest.html` 是合理候选
   - HC 可按此继续实施 `SPEC-072`
   - 也可选择更适合 HC 架构的其他目标文件

3. 按本 response `§2.3` 的规则处理 live-scale factor
   - `XSP = SPX / 10`
   - 仅 `PnL / BP / credit` 缩放
   - strike 不缩放
   - 用于 `SPEC-072` 的 `F2 / F5 / F6` 双列显示

4. 按本 response `§3` 接受：
   - short delta `0.12` 是 MC 的长期 convention
   - 不是 `SPEC-071` 新引入
   - HC 无需回滚

5. 按 `Q020 / Q021` 新编号更新 HC 内部记录

6. 若 HC 之后仍想对齐 cascade 差异，请在下一轮 `hc_return` 中明确 cascade table 的 strategy scope

## 8. MC 不要求 HC 立即做的事

1. 不需要 HC 再回答 short delta governance
   - 此项已被本 response 关闭
   - HC 下一轮只需简单 acknowledge

2. 不需要 HC 重跑 `SPEC-070` 到 `SPEC-073`
   - HC 本轮 cascade 结果可保留

3. 不需要 HC 回滚任何已 shipped 的 SPEC
   - 这 6 项 SPEC 的本轮成果都仍然有效

## 9. 下一次 MC 期

本 response 发出后，MC 暂时空闲，等待 PM 下一步指示。

下一轮 MC 工作期可能涉及：

1. `Q019 Phase 1` 的 PM `A / B / C` 决策
2. `SPEC-067 / ES runtime safeguards`
   - 若 PM 起草，将进入 DRAFT cycle
3. 接收 HC 回程包
   - 若 HC 完成 `SPEC-072` 实施并回报新 cascade
   - MC 再做对照 review

当前无紧急事项。
