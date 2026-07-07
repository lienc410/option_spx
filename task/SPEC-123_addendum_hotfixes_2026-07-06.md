# SPEC-123 增补 — 7/6 首个完整交易日发现的三个 hotfix（quant 已验证）

## H-1（最急）moff 前向首日疑似字段串腿——会静默污染 CALIB

生产 monitor 7/6 行记录 `d30_moff=-4.25`；quant 手算同日链上 put |Δ|0.30 mid-implied = 14.75，VIX 收 15.57 → 真值 offset **−0.82**（与 30 天回填中位 −0.79 一致）。−4.25 恰落在 **call c30** 区间（中位 −4.73）→ 疑似 put 字段被写入 call 值（SPEC-122 把 shadow 步嵌入 16:50 任务后的首次全路径运行，集成回归嫌疑最大）。**calibration.py 直接消费这些字段**，请优先修复 + 更正 7/6 行 + 回归测试锁定 put/call 腿归属（AC-3 式实链断言按腿类型分别验证）。

## H-2 heartbeat 首官跑唯一 violation = settling 注册表路径错

任务实际输出 `logs/q019_settling_state.json`，注册表写 `data/`。settling 本体今晨已验证正常（status=stable）。改注册表路径即可。

## H-3 Ledger close 事件三缺陷 + 今日两行数据更正

今日两笔 BCD close（15:23）暴露：(a) **debit 仓 PnL 符号错**——`actual_pnl=-85100` 实为 -(440+411)×100，正确值 **+2,900/张**（entry 411 debit → exit 440）；(b) close 事件**无 open 关联字段**；(c) close **不带 strikes/合约标识**——ledger 自身无法确定关的是哪笔（本次靠券商持仓反推：关闭的是 6/5 两笔 7200/7700，剩余 6/3 两笔 carve 仓 exp 7/17）。请：修 UI 平仓 PnL 计算（debit 分支）、close 事件补 open_id+strikes 字段、对今日两行发 correction（actual_pnl → +2900）。与 123 §4 的 ID 唯一性同属 ledger 完整性批。

## 随附：BCD 首批实现流水复审记录（预注册触发器，quant 侧已完成）

2 笔实现 **+$2,900/张（+7.1% of debit）**，来自 6/5 SPEC-060 格手动仓（注：exit_reason 下拉记为 60pct_profit，实际 +7%——建议下拉词表补 manual/discretionary 项）。降级四门无一触发（实现和为正）；对 D1/D2 无影响；作为 BCD 结构在当前时代的首个真实数据点记录在案。下一批实现流水：6/3 两笔 carve 仓 2026-07-17 到期。

## H-4 推送发送失败静默（PM review 发现，与 H-1 同级加急）

7/6 16:50 event_push 吃 Telegram 400（"can't parse entities: Unsupported start tag"——消息含非法 HTML），**无重试、无降级、无失败感知**。若失败的是 credit stop TRIGGER 即事故。立即修：(a) 定位并修复该消息的 HTML 构造；(b) 所有发送点加"parse 失败→重发纯文本"降级 + 一次重试；(c) 发送成功/失败计数落盘，heartbeat 注册表加当日发送健康断言。网关级根治见 SPEC-126（本项不等它）。
