# Quant Review — SPEC-072 Frontend Dual-Scale + Broken-Wing Visual

- 日期：2026-04-25
- 审稿：Quant Researcher
- 实施：Developer (Codex)
- 范围：`web/static/spec072_helpers.js`、`web/templates/{index,backtest,margin}.html`
- 输入：`task/SPEC-072.md`、`task/SPEC-072_handoff.md`

---

## 总体结论

**PASS（代码层）** — F1–F7 全部按 SPEC 落到位，scope 限制在 frontend，
`backend/engine/selector/artifact` 未触动。AC1–AC7 + AC9 可在静态阅读中确认；
AC8 / AC10 仍待浏览器或 PM live smoke。

可推进至 PM live smoke。

---

## 逐项 AC 核对

| AC | 描述 | 验证 | 结论 |
|---|---|---|---|
| AC1 | 4 个 helper 实现并暴露到 window | `web/static/spec072_helpers.js:69-72` 暴露 `liveScaleFactor / formatDualBp / formatDualPnl / isBrokenWingIc`；`liveScaleFactor` 三档（HIGH=0.1, NORMAL=1, LOW=2）正确 | ✅ |
| AC2 | HIGH_VOL aftermath recommendation 显示双值 BP badge | `web/templates/index.html:935-944` `isAftermathHighVol = strategy_key='iron_condor_hv' && regime='HIGH_VOL' && isBrokenWingIc(legs)`，触发 `dual-metric` 渲染 | ✅ |
| AC3 | broken-wing 紫色 badge + delta 加粗仅在 `isBrokenWingIc==true` 时出现 | `index.html` legs build 在 BUY 腿应用 `leg-delta-broken` class；卡片头部条件性渲染 `Broken-wing IC` badge；CSS `web/templates/index.html:262-280` 紫色 #B79CFF | ✅ |
| AC4 | scale disclaimer 仅在 `spec064_aftermath_ic_hv` view 显示 | `web/templates/backtest.html:2030-2048` `updateResearchBanner()` 用 `disclaimer.classList.toggle('hidden', _activeResearchView !== 'spec064_aftermath_ic_hv')`，其他 view 与 production view 都隐藏 | ✅ |
| AC5 | trade log 在 HIGH_VOL 行双列；LOW_VOL 行单列 | `backtest.html:2491-2500` `dualScale = activeView==='spec064_aftermath_ic_hv' && isHighVolRegime(regime)`，pnl/premium/bp% 全部支持 fallback 到单列；`renderDualMetricHtml` 用 `dual-stack` 容器 | ✅（注：实施收紧到 spec064 view，比 SPEC 原文「`HIGH_VOL` 行双列」更窄；handoff §阻塞 §F5 已注明，符合 ST3 规则） |
| AC6 | margin BP 在 HIGH_VOL 持仓时双值 | `web/templates/margin.html:669-674` `isHighVolPosition = open && isHighVolRegime(regime)` → 双值 + 紫色 est；非 HIGH_VOL 退回单值；`/api/position` 通过 `state.regime` 暴露，`web/server.py:428` 写入 | ✅ |
| AC7 | legend 含 SPEC-071 addendum 锚点 | `backtest.html:1142` `<a href="/task/SPEC-071.md">SPEC-071 addendum</a>` (LC δ0.04 / LP δ0.08) | ✅ |
| AC8 | 三主 tab + 四 modal 无 console error | 静态阅读：`SPEC072` namespace 已暴露；helper 入参均做 `Number.isFinite` 守护；`isBrokenWingIc` 对空/非数组短路；理论上不会抛出 | ⏳ 需浏览器 smoke |
| AC9 | backend MD5 / `data/research_views.json` mtime 不变 | Developer handoff 已声明并附 `git diff --stat` / `stat -f` 证据；本次 review 未触发新 backend 改动 | ✅ |
| AC10 | PM live smoke：1 笔历史 aftermath 入场 dual-scale 数值与 0.1× 手算一致 | PM 操作域 | ⏳ PM 任务 |

---

## 静态代码 spot check

### F1 helper 正确性（`spec072_helpers.js`）

- `liveScaleFactor`：regime normalize 用 `String().toUpperCase()`，对 `null/undefined` 安全；HIGH_VOL→0.1, LOW_VOL→2, 其余→1。
- `formatDualBp` / `formatDualPnl`：`Number.isFinite` 守护；非 HIGH_VOL 分支只返回单值，符合 SPEC「LOW/NORMAL 退回单值」要求。
  注：SPEC §核心原则把 LOW_VOL 列为 ×2，但 dual-formatter 没有 LOW_VOL 双值分支——这是 ST3 收窄结论的一致延伸（dual-scale 文案仅 HIGH_VOL 显示），不视为 bug。
- `isBrokenWingIc`：取 `BUY CALL` 与 `BUY PUT` 的 `|delta|`，差 > 0.02 触发；`Number.isFinite` 守护防止字符串 delta；纯对称返回 false（差 = 0）符合 SPEC 边界条件。

### F2/F3 卡片逻辑（`index.html`）

`isAftermathHighVol` 同时要求 `strategy_key === 'iron_condor_hv'` && `regime === 'HIGH_VOL'` && `isBrokenWingIc(legs)`。
- 含义上等于「aftermath broken-wing IC_HV」三连判，比 SPEC「HIGH_VOL aftermath recommendation 双值」更严：要求 broken-wing 才双值。
- 这避免了 NORMAL/LOW_VOL IC_HV（理论上不存在但出于防御性）误显双值；可接受。
- broken-wing badge 与 dual-scale BP 共享同一 gate，没有违反 SPEC §核心原则「broken-wing 视觉与 dual-scale 独立」——因为 IC_HV aftermath 默认全是 broken-wing；同 gate 不会出现「broken-wing without dual-scale」漏判。

### F5 trade log（`backtest.html:2491+`）

- `dualScale` gate 用 `_activeResearchView === 'spec064_aftermath_ic_hv' && isHighVolRegime(regime)`：
  - production view 永远单列；
  - spec064 view 的 LOW_VOL/NORMAL 行（虽然子集应该都是 HIGH_VOL）也单列；
  - HIGH_VOL 行三列（pnl / premium / bp_pct_account）全部双堆叠。
- `SPEC072.renderDualMetricHtml(t.exit_pnl, regime, 'currency')`：参数 `'currency'` 不等于 `'bp'`，正确走 `formatCurrencyValue`。

### F6 margin（`margin.html:669-674`）

- `isHighVolPosition = Boolean(position?.open) && SPEC072.isHighVolRegime(position?.regime)`：未开仓 → 单值；
- 双值文案 `${pct}% + ${pct * 0.1}% est`，与 helper 输出格式一致；附加紫色 `card-note` 解释 dual-scale 含义。
- `/api/position` 在 `web/server.py:222` 把 `state` spread 入响应，`state.regime` 由 `api_position_open` (`web/server.py:428`) 写入；当 state 缺 regime 字段时，`isHighVolRegime(undefined)` 返回 false，gracefully 退回单值。

---

## 与 SPEC 偏差备注（已批注 / 不阻塞）

1. **F5 收紧到 spec064 view**：SPEC §F5 写「HIGH_VOL regime 行的 entry_credit / total_bp / exit_pnl 列改为双列」未限定 view；ST3 用 `production view: 单列；spec064_aftermath_ic_hv: HIGH_VOL 行双列` 收紧。Developer 实施按 ST3，handoff 注明，可接受。
2. **F3 与 dual-scale 同 gate**：SPEC §核心原则强调「broken-wing 视觉与 dual-scale 独立」。实施层把两者都收到 `isAftermathHighVol`；因为 aftermath IC_HV 默认全是 broken-wing，业务上没有 violation；如果未来出现 HIGH_VOL aftermath 非 broken-wing entry，会同时丢 badge + dual-scale。建议在未来 SPEC 拆分（不要求本次回工）。
3. **`columns` 列名映射**：SPEC §F5 字段是 `entry_credit / total_bp / exit_pnl`；HC 实际表头列叫 `Premium / BP% / P&L`，对应 `t.option_premium / t.bp_pct_account / t.exit_pnl`。语义一致，不阻塞。

---

## 推荐下一步（给 PM）

1. **浏览器 smoke（AC8）**：起 dev server，按 ST1–ST5 逐项过一遍：
   - ST1 三主 tab 切换
   - ST2 选 2026-03-09 / 2026-03-10 aftermath 推荐日，看 BP badge 双值 + 紫色 broken-wing badge + BUY 腿 delta 加粗
   - ST3 backtest 切到 `SPEC-064 Aftermath` view，确认 banner 紫色 disclaimer 出现 + HIGH_VOL 行 P&L/Premium/BP% 双列
   - ST4 持仓非空时去 /margin 看 BP 双值
   - ST5 四个 modal 开关无 console error
2. **PM live smoke（AC10）**：用任意一笔历史 aftermath（例 2026-03-09 IC_HV），口算 `pnl_research × 0.1 ≈ pnl_live_est`，与 dual-stack 显示比对。
3. 通过后由 PM 把 SPEC-072 翻成 DONE；Quant 不主动 flip 状态。

---

## 风险与遗留

- 没有引入新 backend 字段，符合 §核心原则；future Q029 主线（live XSP 下单）仍需独立 SPEC。
- HC 当前 `web/templates/` 多文件实现与 MC 单文件版本同 spirit，分歧由 §HC 文件映射记录；后续 sync 不再展开。
- `position?.regime` 依赖前端在 `api_position_open` 提交时传 `regime` 字段；如果后续 schwab 自动 import 路径漏掉这个字段，F6 会安静退回单值；不属于 bug，但可作 SPEC-072 followup 跟进项（不阻塞本次）。
