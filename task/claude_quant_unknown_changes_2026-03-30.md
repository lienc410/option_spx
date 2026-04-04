# Claude Quant Update — 2026-03-30

这份说明只总结“Claude quant 还不一定知道”的实现层修改，不重复策略 spec 原意。

## 1. 已完成的统一数据源重构

新增了 [strategy/catalog.py](/Users/lienchen/Documents/workspace/SPX_strat/strategy/catalog.py)，现在它是策略展示和映射的统一来源，集中定义：

- `strategy_key` 稳定主键
- display name
- emoji
- direction / underlying
- DTE / delta / risk / target / roll 文案
- canonical matrix 映射
- manual entry 可选策略

目前 active catalog 内的策略为：

- `bull_call_diagonal`
- `iron_condor`
- `bull_put_spread`
- `bull_put_spread_hv`
- `bear_call_spread_hv`
- `iron_condor_hv`
- `reduce_wait`

## 2. Selector 层的变化

[strategy/selector.py](/Users/lienchen/Documents/workspace/SPX_strat/strategy/selector.py) 现在仍然负责“决策”，但不再自己维护展示元数据。

已做的调整：

- `Recommendation` 新增 `strategy_key`
- 新增 `_build_recommendation(...)`，统一从 catalog 注入：
  - `underlying`
  - `max_risk`
  - `target_return`
  - `roll_rule`
- `get_position_action(...)` 调用链已改为传入 `strategy_key`

这次重构目标是让 selector 只决定“选哪个策略”，而不是同时兼任前端文案源。

## 3. Bot 推荐与手工录入已切到 catalog

[notify/telegram_bot.py](/Users/lienchen/Documents/workspace/SPX_strat/notify/telegram_bot.py) 的以下内容已不再硬编码：

- 推荐消息 emoji
- 策略显示名来源
- `/entered manual` 的策略列表

现在 bot 通过 catalog 渲染推荐信息，并在写持仓状态时同时写入 `strategy_key`。

## 4. 前端 dashboard / matrix 已改为读统一源

[web/server.py](/Users/lienchen/Documents/workspace/SPX_strat/web/server.py) 新增：

- `/api/strategy-catalog`

该接口向前端提供：

- 全量策略 descriptor
- canonical matrix
- manual entry options

前端调整如下：

- [web/templates/index.html](/Users/lienchen/Documents/workspace/SPX_strat/web/templates/index.html)
  - 不再维护本地 emoji 映射
  - 当前 recommendation 卡片和 position panel 改为依赖 `strategy_key + catalog`
- [web/templates/matrix.html](/Users/lienchen/Documents/workspace/SPX_strat/web/templates/matrix.html)
  - 删除原先硬编码的 `STRAT` / `MATRIX`
  - 现在从 `/api/strategy-catalog` 拉取 canonical matrix 和策略详情
  - cell、高亮、详情面板、trade log 都已改为 key-based

## 5. State 层兼容了旧数据

[strategy/state.py](/Users/lienchen/Documents/workspace/SPX_strat/strategy/state.py) 做了兼容升级：

- `write_state(...)` 若未显式传入 `strategy_key`，会自动从 display name 推导
- `read_state()` 读到旧格式持仓记录时，会尝试回填 `strategy_key`
- `get_position_action(...)` 优先用 `strategy_key` 比较当前仓位与新推荐，避免 display name 漂移

这意味着旧的 `logs/current_position.json` 不需要手工迁移。

## 6. API 契约的新增字段

这些接口现在已经开始携带 key-based 信息：

- `/api/recommendation`
  - 已返回 `strategy_key`
- `/api/position`
  - 已返回 `strategy_key`
  - 若可解析，也会带 `strategy_meta`
- `/api/backtest`
  - trade records 新增 `strategy_key`
- `/api/backtest/stats`
  - per-strategy 聚合目前改为以 `strategy_key` 为 key

这一点对任何后续脚本、前端过滤、统计展示都很关键。

## 7. 这次顺手修掉的额外 bug

除统一数据源之外，还顺手修了几处先前没单独写给 Claude quant 的问题：

- intraday recommendation 已确保 `/today` 与 `/entered` 走同一条 intraday 逻辑
- intraday 模式下，IV snapshot 现在会随 live VIX override 一起更新，不再出现“regime 是实时的、IV 状态却是昨收”的混合状态
- backtest 已补上历史 `VIX3M` / backwardation，避免 live filter 与 backtest 行为不一致
- `matrix.html` 修复了 catalog 尚未加载就先建 matrix 的初始化问题
- `matrix.html` 去掉了对 `::before` 的无效 `querySelector`，避免 detail panel 点击时报错
- `index.html` 之前读取 `iv.signal` / `divergence_warning` 的旧字段问题已经修正，现按 `iv_signal` 和 IVP override 规则计算

## 8. 已做验证

已完成的验证包括：

- `compileall` 通过
- 新增 `unittest` 回归测试并通过
- 覆盖了 selector 关键路径：
  - LOW_VOL bullish
  - NORMAL bullish/high-IV
  - NORMAL bullish/backwardation
  - NORMAL bearish/neutral-IV
  - HIGH_VOL bearish/rising
  - HIGH_VOL bearish/stable
- 覆盖了：
  - catalog/matrix 一致性
  - state 旧记录兼容
  - `/api/strategy-catalog`
  - `/api/position`
  - `/api/recommendation`

## 9. 仍然值得 Claude quant 关注的点

当前已经完成的是“统一展示与映射来源”，不是“把所有策略结构参数都抽成完全 declarative 的执行模板”。

也就是说：

- selector 决策逻辑已经和 catalog 解耦
- 但 backtest 的腿生成逻辑仍然主要在 engine 内
- catalog 目前更像“统一元数据 + canonical matrix + UI/bot source of truth”

如果后续 Claude quant 想继续推进，下一步最自然的是：

- 把 backtest leg template 也进一步挂到 catalog 或单独的 execution schema
- 增加一个全历史 pre/post recommendation diff 工具，自动验证重构前后 selector 行为是否逐日一致

## 10. 一句话结论

现在策略代码、前端 matrix/dashboard、Telegram bot 推荐信息，已经基本收口到同一套 catalog 数据源；后续再改策略展示或 canonical matrix，不需要再分别改三处硬编码。
