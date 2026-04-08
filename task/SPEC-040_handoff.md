# SPEC-040 Handoff

## 修改文件
- `schwab/client.py:142` — 为 option chain 缓存 key 引入 `center_strike`，并在 centered scan 时扩大原始抓取窗口后按中心 strike 做本地裁剪
- `schwab/scanner.py:46` — `build_strike_scan()` 接收并透传 `center_strike`
- `web/server.py:342` — `GET /api/position/open-draft` 按每条理论 leg strike 传入 `center_strike`
- `tests/test_schwab_scanner.py:37` — 增加 centered scan 参数透传、缓存隔离与局部窗口裁剪测试
- `tests/test_state_and_api.py:130` — 校验 `open-draft` 调用 scanner 时带上理论 strike 作为 `center_strike`

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5

## 阻塞/备注
- live sanity 已确认 centered scan 生效：`$SPX` 45 DTE call 链从原先偏近 ATM 的宽段切到 `7300–7330` 的理论 strike 邻域。
- 当前 live rows 仍可能触发 fallback；原因是 `SPEC-039` 保留的 `open_interest >= 100` 与 `spread_pct <= 0.50` 硬过滤未变，不属于本 spec 范围。
