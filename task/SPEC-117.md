
---

## SPEC-117.2 — 每日绿线降噪（PM 2026-07-13 直接指令）

**动因**：ops 心跳绿线（29/29 green）与链体检报告（17/17 ✅）几乎永远全绿，
PM 判定为每日噪音。但绿线承担反向心跳（没收到 = 监控自己死了），不能直接砍。

**改动**：
1. `scripts/ops_heartbeat.py`：每次运行落 `logs/ops_heartbeat_state.json`
   （ts/total/violations）；**绿天不再推送**；违规日 ACTION 照旧；月度
   DEFERRED digest 照旧。
2. `research/q041/daily_chain_sanity.py`：全绿日体检报告不推（jsonl 记录照写）；
   异常日报告 + ACTION 告警照旧。
3. `notify/telegram_bot.py` digest 新增**健康位**（`_digest_health_bits`）：
   `健康：ops 29/29 ✓（07-13 17:30）· 链体检 17/17 ✓（2026-07-13）`。
   **反向心跳搬家**：ops state 过期 >26h → 令牌变 ⚠ 且 digest 升 ACTION
   （PM 必读渠道承接 dead-man 语义）；违规日令牌 ⚠ 但不重复升级（独立
   ACTION 已响）；state 缺失首日宽限（升级部署当天）。

**AC**（tests/test_spec_117_2.py，7 tests + 126/140/chain_sanity 60 绿）：
全绿单行令牌无升级；过期 >26h 升 ACTION；违规 ⚠ 不重复升级；绿天心跳零推送
且 state 落盘；红天 ACTION 照响。

**收件预算变化**：每天 −2 条固定 FYI（心跳绿线 + 链体检报告）；digest +1 行。

Status: DEPLOYED 2026-07-13
