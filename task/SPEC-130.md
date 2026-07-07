# SPEC-130 — 推送通道测试密闭性（INCIDENT 2026-07-07，最高优先级）

**事故**: PM 于 7/7 上午收到 ~百条无信息量推送（合成仓位）。取证：本机（dev 机）`logs/push_stats.json` 7/7 sent=187（7/6 sent=68），oldair 生产端同期零发送。根因：`notify/event_push` 运行时读 env 凭证，本机 .env 含真 token，pytest 全量跑（dev 两次 + quant 验收复跑）中未被 mock 的路径把测试夹具仓位真实推送给 PM。**7/6 的 68 条说明 SPEC-127 测试当天已在泄漏**——两天验收数据全部污染。

**治理定性**: "测试触碰生产资源"第二实例（#1 = ghost ledger rows，47648fa 修复 CLOSED_TRADES_FILE 隔离；#2 = 本次真推送）。按二次浮面规则，密闭性升级为强制房规，不再逐通道打补丁。

**临时止血（已做，quant 2026-07-07 09:05）**: 本机 .env `TELEGRAM_BOT_TOKEN` key 改名禁用。此为临时措施，防线不得依赖它（见 AC-4）。

## 修复三层

1. **传输层主机 guard（deny-by-default）**: `notify/event_push._send` 开头检查 `SPX_PUSH_ENABLE=1`，未设置 → log + return False（零 HTTP）。仅 oldair 生产 launchd plists 设置该 env（bot、web、q085、q019、daily_snapshot、ops_heartbeat 等全部 push-capable jobs——建议统一 EnvironmentVariables dict，逐个核对 plist 清单）。生产行为零变化；其它任何机器天然哑火。
2. **pytest 全局密闭 fixture**: tests/conftest.py autouse——monkeypatch event_push 传输为 recorder；任何测试尝试真 HTTP 到 telegram 即 fail。真需要活体发送的集成冒烟用显式 `@pytest.mark.live_push` + env opt-in，默认跳过。conftest docstring 维护"外部副作用通道隔离清单"（ledger 文件、telegram、broker 写操作、缓存文件），新增通道必须同步登记——这是房规落点，不开镜像文档。
3. **元断言**: 测试会话结束钩子断言 push_stats.json 计数在会话期间零增量（stats 写入同样置于 guard 后）。

## AC

- **AC-1**: guard 单测——无 `SPX_PUSH_ENABLE` → `_send` 零外呼（socket/requests mock 断言）+ 返回 False；`=1` → 正常发送路径（mock 200）。
- **AC-2**: oldair plists 更新 + 服务重启后生产冒烟：真发一条 STATE 测试推送成功（**须提前告知 PM 会收到这一条**）——证明 guard 未误伤生产。
- **AC-3**: 本机全量 pytest（凭证在位、guard 未设）→ telegram 零外呼 + push_stats 零增量。
- **AC-4**: 恢复本机 .env token 原 key 名后重复 AC-3 仍零外呼——防线独立于止血改名；此后保持恢复态（live_push 冒烟依赖它）。

## 附带

- SPEC-126 收件预算验收时钟重置：guard 落地次日起重新计 day 1（7/6-7/7 数据作废）。
- 复盘补一行进 task/SPEC-126 验收注记：验收期间 dev 机测试即污染源——密闭性先于验收。
