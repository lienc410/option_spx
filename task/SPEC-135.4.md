# SPEC-135.4 — 首页决策叙事去重与精修（PM 实看抓出，2026-07-08 凌晨，P0）

**根因自认**: 135.3（quant 起草）同时指定"顶部新增摘要卡"+"SPX 卡渲染锚点"，两处同页相邻 = 同一故事一屏讲两遍。本 SPEC 修正设计错误。quant 已亲眼核对生产截图。

## 1. 去重：首页只留一处决策叙事（并入 SPX 卡）

- **删除独立 TODAY'S ACTIONS 锚点摘要卡**
- 锚点故事的家 = SPX 卡（tier-primary 本就定义含 rationale narrative，DESIGN.md §Strategy Card Hierarchy）；"展开完整决策链"入口保留在 SPX 卡锚点区底部
- AC：首页唯一锚点渲染点（DOM 断言 trace 锚点容器恰一个）

## 2. 锚点区精修（全部对照 DESIGN.md 既有规则）

- **溯源标识降级**（违规修复）：`selector._build_recommendation`、`SPEC-123 D1` 等一律移出主行 → `.spec-ref`（mono 0.52rem --text-2 后缀）或 title tooltip。主行纯人话。静态扫描 AC：锚点/依据主行文本不得含 `selector.`、`SPEC-`、函数名 token
- **final verdict 视觉锚**：▶ 行字号升卡内 headline 级（1.2rem Newsreader），带左侧色条；其余锚点行 1.0rem；evidence 0.72rem
- **长说明收纳**：安全刹车行主文只留一句（"安全刹车：该策略家族 18 个月合计收益转负 → 暂停开新仓，等待复核"）；预注册概率说明、pm-clear 命令全部进展开 detail/hover
- **图例**：收进锚点区右上角，0.6rem，项间 8px（走 spacing scale）；或仅在展开态显示（dev 定，截图对比选可读者）
- **词表合规**：状态词 `WAIT`/观望 → `NO ENTRY`（DESIGN.md 明文：WAIT 不在词表）；叙事行写"今日结论：不开新仓"

## 3. 三泳道在首页的最小完整呈现（PM 问"第三泳道呢"）

- **Lane B 语义行**（SPX 卡 OPEN POSITION 区顶部）：动作语义一行 + Action State badge——`WARNING · 短腿 7/17 还剩 10 天 → 规则要求平掉或滚动（今日已提醒）`；数据从既有 position payload 取，禁新数据路径
- **Lane C 一行**（SPX 卡底部，tier-tertiary 灰调）：`地形（只描述，不进决策）：贴 call 墙第 2 天——7550/+0.6% · 7600/+1.9% · 完整图 → Structure Map`；来源 = structure-map API 同 response
- /spx 完整三泳道不动

## AC 汇总

首页唯一锚点容器；主行零溯源 token（静态扫描）；final verdict 层级 CSS 断言；图例间距 scale 值；NO ENTRY 词表；Lane B/C 行存在且同源；**headless 双主题整页截图 + 逐行语义自洽（advisory 非红等 135.3 断言沿用）**；7/7 固定用例回归。
