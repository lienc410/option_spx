# SPEC-132 — 市场结构地图：可视化 + shadow 证据流共管道（草案，2026-07-07）

**来源**: Q090 封账后 PM 提议可视化结构信号。**设计立场：描述性态势感知层，不是信号**——Q090 verdict 必须随显示携带（badge），否则就是我们自己刚清理过的"页面宣传死物"模式。

## 为什么值得做（双重目的，一份工程两份回报）

1. **PM 态势感知**：PM 手动交易本来就看位（提示不拦领地）——在我们自己的页面看，好过在 TradingView 看，因为我们能带上证据状态标签。
2. **研究证据流**：同一条计算管道就是 Q090 注册的前瞻收集器——**S3 持仓墙正式测需 n≥60 触发样本，S1s 支撑簇重开需 n≥100**。可视化每天算的 flag 落 JSONL，就是这两个重开条件的进度条。显示和取证共用真值，无镜像。

## 内容（/spx 页新卡 "Structure Map"）

- **持仓墙**（第一优先，OPEN 状态 badge）：当日链快照 top-3 call 墙（上方）/ put 墙（下方），strike + OI + 距现价 %。数据源 q041 chain parquet，日更
- **压力/支撑簇**（NULL/无裁决 badge）：Q090 胜者定义（S1r b3_t3 / S1s b3_t2，pivot k=5 确认滞后 5td——复用 q090_e1 代码，生产函数单一化），最近簇位 + 触碰数 + 距现价 %
- **递减趋势线**（NULL badge）：活跃时画线值
- **今日量比** V/20d（NULL badge）
- **Badge 词汇表**（强制）：`墙: 前瞻收集中 n=X/60` / `簇/线/量: Q090 无验证边际，仅描述`——每个元素带证据状态，DESIGN.md 合规，禁 --text-muted

## Shadow JSONL（data/q090_structure_shadow.jsonl，日更 job）

每日一行：{date, spot, walls:[...], s1r_flag+level, s1s_flag+level, s4_flag+line, vol_ratio}。心跳注册（SPEC-117 registry）。月度 digest 报 n 进度（S3 n/60、S1s n/100）。

## AC 要点

flag 计算与 q090_e1 runner 同函数 import（禁旁路重推，附 bit-identical 断言样本日）；badge 文案与 Q090 verdict 对齐（内容审计项）；JSONL strict-JSON；链快照缺失 fail-soft（卡片显示 stale 日期）；心跳注册。

## 边界

不进推荐引擎、不进 gateway 推送（纯页面 + 静默 shadow）；未来若 S3 攒够 n≥60 → 按 framing 正式测，届时才谈信号化。
