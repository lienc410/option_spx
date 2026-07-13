# SPEC-144 — Aftermath 页面可读性重构 + 展示层事实修正（PM 2026-07-12）

**验收标准（PM 原话）**: 未参与项目的交易员能看懂这个 addon 策略**要做什么、怎么做**。

## 0. Quant 审阅发现（动机）

1. **事实错误（P0）**: Trigger Logic 卡写死 "当前 VIX 必须 < 40"——产码 `is_aftermath` 自 SPEC-118.1 起单源 `params.extreme_vix = 35`。且 `aftermath_state_payload`（web/server.py ~971）残留三处 40：`threshold_vix_max: 40.0`、reason 分支 `vix.vix >= 40.0`、docstring——**VIX ∈ [35,40) 时 active 正确为 False 但 reason 会误报成 off-peak 不足**
2. **最大缺口**: 页面详写触发条件却从不说**交易什么**——四腿结构、出场规则、仓位大小全部缺失。外人看完只知道"某个窗口会激活",不知道激活后干什么
3. **黑话无注**: "broken-wing V3-A"、"condition modifier"、"canonical 路径被 ivp63 门消耗"、"263/263 与 175/175"（Q088 T1 归因注是内部考古,放 hero 第二行外人完全不可读）
4. **镜像漂移实证**: Implementation Reference 写 "selector lines ~634 / ~750"——真值已在 813-821。行号进模板必烂（no-param-mirror 房规）
5. **Q101/SPEC-143 缺席**: 首笔 0.5× staging 已上线但页面只字未提
6. **--text-muted 违规**: Regime/Trend/threshold 数值与 WAIT pill 用 muted（PM 要读的内容,房规禁用,历史已犯 4+ 次）
7. backtest tab §结论块仍是 Q064 时代叙事（"$30k+ alpha"）,未注 Q101 复审勘误

## 1. Dashboard 重构（web/templates/aftermath.html）

按未参与者的五问重排信息架构（全部白话,内部代号首现带一句 gloss 或移入 Implementation Reference 卡）:

1. **这是什么**（hero 下第一卡,3-4 句）: VIX 冲高后开始回落的"余震窗口"策略——恐慌顶峰已过、期权仍贵,在这个窗口卖出一个两侧带保护的 iron condor 变体收权利金;与对称结构的区别是保护翼刻意放宽（买更远的 call 翼 + 相对更近的 put 翼）,为的是"余震再崩"时少赔（Q101 配对证据: 挑战结构恰在延续性崩盘日多亏一倍）
2. **什么时候做**: 三条件 checklist,每条一行 = 白话条件 + 今日实际值 + ✓/✗ 判定（数据全取 `/api/aftermath/state`,替换现在的 dev-speak reason 字符串;例: "近 10 日 VIX 冲过 28（今日峰值 17.2 ✗）"）。ACTIVE 时注明"SPX 主推荐会自动切到本结构,见 /spx"——外人要知道激活的**后果**
3. **交易什么**: 四腿表（方向/类型/DTE/delta）+ 一句白话（卖 δ0.12 双侧、买翼保护;下侧翼更近=更贵=刻意的余震保险）。**腿参数与阈值一律 API 渲染,模板零硬编码**（见 §2）
4. **多大仓位**: HIGH_VOL 基准 0.5× 规模 + Q101 首笔 staging 三态白话说明（首笔半仓直到窗口内 skew 实测落地;实测陡≥1.5×基线则维持半仓等复判）;窗口 ACTIVE 时显示实时 staging 态（§2 payload 扩展,fail-soft: 取不到就只显示静态规则）
5. **什么时候退出 / 什么时候会亏**: 出场 = 60% 利润（至少持有 10 天后）或 DTE≤21 先到者（文案取 catalog `roll_rule_text` 真值）;诚实亏损场景一句话（主要亏损日=余震延续下跌;防护=宽翼+首笔半仓）+ Q101 verdict 一行（2026-07-12 独立复审: 结构保留,edge 幅度依赖定价假设,详 research/q101）

保留卡: Implementation Reference（**删行号**,只留文件/函数名;Q088 T1 归因注改白话一句移入此卡）。Trigger Logic 卡并入五问 ②（不再单列参数表）。

## 2. 展示层单源修正（web/server.py）

- `aftermath_state_payload`: reason 分支 `>= 40.0` → `>= DEFAULT_PARAMS.extreme_vix`;`threshold_vix_max` → 同值单源;docstring 修正;**新增字段**: `v3a_legs`（selector V3-A 腿真值结构化导出）、`exit_rule_text`（catalog descriptor 取）、`sizing_note`（HIGH_VOL 0.5×,selector/catalog 真值）、active 时 `staging`（`strategy.aftermath_staging.evaluate_staging`,fail-soft null）
- reason 人话化可在 payload 加 `reason_human`（保留原 reason 字段,下游零破坏）
- **additive only**: 既有消费方（decision_trace lane D、state_map、tests）零行为变化

## 3. 其他

- --text-muted 违规全修（Regime/Trend/threshold/pill.wait → `--text-2`;muted 仅剩 Loading/空态占位）
- backtest tab（aftermath_backtest.html）: 只做两件——§"结论" 块补 Q101 addendum 注（一行,链 research/q101）;黑话首现 gloss。不重构
- 主题: 继续 link theme.css,颜色用 shared vars;cache-buster 统一 bump spec144
- staging 三态文案若整句展示,逐字取 `decision_trace.q101_staging_label`（SPEC-140 单源铁律);静态规则说明卡允许白话改写(不是三态实时文案)

## AC

1. **单源**: 模板 grep 无 `28`/`0.90`/`35`/`40`/delta 数字硬编码(全部 API 渲染);payload 新字段各有测试;`v3a_legs` 与 selector 真值断言相等(防漂移)
2. **[35,40) reason 修正回归测试**: 构造 VIX=37 快照 → active=False 且 reason 指向 extreme(不再误报 off-peak)
3. 三条件 checklist 逐条今日值+判定渲染(DOM 断言);ACTIVE/WAIT 两态各一渲染测试
4. staging 卡: active+读数三态显示正确(复用 SPEC-143 fixtures);inactive 时只显静态规则;API 失败 fail-soft 不破页
5. --text-muted 扫描: 两模板 muted 仅存于占位符类
6. 全量测试零新增失败;decision_trace/state_map 相关既有测试零改动通过
7. 验收走查(合并后 Quant 亲验): 以"未参与者五问"顺序通读页面,每问在首屏两屏内有答案

## 交付

worktree 隔离;推分支 `spec-144` 不碰 main 不部署;测试 repo venv;回报 commits + AC 逐条 + SPEC 与现实冲突不静默改。
