# SPEC-121 — /ES HV Ladder 止损口径统一至 10×（Q087 A3，PM 2026-07-05 ratify 方案 a′）

**依据**: `research/q087/q087_a3_v2f_stop_verdict_2026-07-05.md`（外审 CONFIRMED）+ PM 知情确认（含同日多梯级集中度风险与 -$24k 级单笔存在于已验证分布内）。

## 变更（canonical stop = 10×，一个数字贯穿全系统）

1. **实盘监控**（SPEC-086 路径，notify/ 下 intraday monitor）：TRIGGER 3× → **10×**；WARNING 2× 保留不变
2. **回测常量**：`research/strategies/ES_puts/backtest.py` `V2F_STOP_MULT 15.0 → 10.0`（Q071 P4 网格内；A3 runner 已证与 15× 逐笔 bit-identical，26 年零触发）
3. **展示层**：/es 页 credit stop progress bar 与文案（2×/3× → 2×/10×）；catalog ES 描述文本同步
4. **ES 回测磁盘缓存刷新**（per `feedback_backtest_cache_refresh`；若 SPEC-118 git-hash key 已落地则自动失效，验证即可）

## AC

- AC-1 monitor 边界测试：mark=9.9× 无 TRIGGER、10.0× TRIGGER；2× WARNING 路径不变
- AC-2 回测 bit-identical：V2F_STOP_MULT=10 与 =15 的 promoted config 逐笔相同（用 `research/q087/q087_a3_stop_convention_runner.py` 断言）
- AC-3 /es 页展示与新阈值一致；AC-4 缓存刷新验证
- AC-5 本 SPEC 不改 SPX 侧任何止损（BPS 3× credit 是另一独立纪律，不在本 SPEC 范围）

## 风险披露（已获 PM 确认）

止损触发历史全部聚集于 VIX 22-43 时代且呈同日多梯级团灭形态；10× 下该保护层后移，灾难级 fail-safe 保留（10× 触发≈异常 mark/跳空场景）。2× WARNING 仍提供早期情报。
