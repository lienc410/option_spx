# fund_exit — 基金技术面分批清仓信号工具

逐步清仓 A股公募基金的**纪律工具**（非 alpha 择时、非投资建议）。**临时性**：全仓清空后整个目录 + `/funds` tab 一并移除（见末节）。

- 策略设计：`task/fund_exit_strategy_spec.md`（spec v2，经 GPT quant review 收敛）
- 前端 handoff：`task/fund_exit_FE_handoff.md`
- 信号刷新 = **日度（交易日）**；月度的是卖出节奏（保底时钟），两者不同 cadence。

## 产物（均 gitignore，由脚本生成）
- `fund_signals.json` — 前端数据契约（`/api/fund-exit/signals` 读它）
- `charts/*.png` — 每只净值图（`/api/fund-exit/chart/<code>` 服务）
- `基金技术出场信号.xlsx` — 带格式汇总表
- `refresh.log` — launchd 运行日志

## 持仓状态 + 记录减仓（写回闭环，均 gitignore）
- `positions.csv` — **持仓真值**（code,name,market_value,pnl_pct）。首次由代码内 `HOLDINGS_SEED` 自动生成；此后由前端"记录减仓"按钮改写。脚本每次读它。
- `trade_log.csv` — 每笔减仓留痕（日期/代码/¥/占比/当时 NAV/规则/建议%/备注），供 vs-TWAP 回溯。
- **工作流**：每周扫描 → 你按建议%在中信 App 赎 → `/funds` 页右上 **"记录减仓"** 录入（基金/¥/日期/备注，可一键填建议额/全部赎回）→ 工具即时减市值、"剩 N 周"倒数推进、trade_log 留痕。
- 端点：`POST /api/fund-exit/record-trade`、`GET /api/fund-exit/trades`；`/signals` 合并 positions 实时市值（记录后即时反映，不必等扫描）。
- 对账：结算(T+1/2)后 App 显示终值，可偶尔把 positions.csv 对齐 App（消除净值漂移）。

## 手动重跑
```bash
# 本地（开发机）
python3 -m venv .venv_fund && .venv_fund/bin/pip install akshare openpyxl matplotlib
.venv_fund/bin/python fund_exit/fund_exit_signals.py
```

## 老 Air 部署（web 服务机，2026-05-31 搭）

web 跑在老 Air，Flask endpoint 读**老 Air 上**的 `fund_signals.json`，所以日度刷新必须在老 Air 跑。

**铁律**：endpoint 只读 JSON，绝不在请求里跑 akshare（慢+限频+block worker）。

### 恢复步骤（换机/重装照做）
```bash
ssh oldair
cd /Users/macbook/SPX_strat && git pull
# 系统 python3 是 3.9.6 → 必须用 3.11（pandas 3.0 需 3.10+）
/usr/local/opt/python@3.11/bin/python3.11 -m venv .venv_fund
.venv_fund/bin/pip install akshare openpyxl matplotlib
.venv_fund/bin/python fund_exit/fund_exit_signals.py   # 验证生成 JSON+图

# launchd 日度任务（周一~五 09:00 / 11:00 / 13:00 本地时间=EDT ×3 次）
cp fund_exit/com.spxstrat.fundexit.refresh.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.spxstrat.fundexit.refresh.plist
launchctl list | grep fundexit                          # 确认加载
launchctl kickstart -k gui/$(id -u)/com.spxstrat.fundexit.refresh  # 强制跑一次验证
```
- 时区：launchd 用机器**本地时间**。老 Air 确认为 **EDT(美东)**。A股基金一天一个净值、收盘后**北京晚上**陆续公布 = 美东上午 8–11 点(北京20:00→ET08:00, 22:00→ET10:00, 24:00→ET12:00)。故跑 **9/11/13 ET 三次**：早出的尽快上、晚出的兜底。**不能**按北京开盘扫(那时新净值还没出)。前端每行状态灯=该只今日净值是否已出。换时区/换机改 plist 的 Hour。
- 操作：每周一次，美东晚间在 App 下赎回单（=北京次日上午，赶下一个 15:00 北京截单）→ 成交落**次日中国净值**（固有 1 日延迟，基金无法按已见净值赎）。
- 改了 `HOLDINGS`/规则等脚本本体后需 `git pull`（定时任务只刷数据、不拉代码）。

## 清仓结束 → 干净移除
```bash
# 老 Air
launchctl unload ~/Library/LaunchAgents/com.spxstrat.fundexit.refresh.plist
rm ~/Library/LaunchAgents/com.spxstrat.fundexit.refresh.plist
rm -rf /Users/macbook/SPX_strat/.venv_fund
# repo
git rm -r fund_exit/
# 移除 web/templates/funds.html、server.py 的 /funds 与 /api/fund-exit/* 路由、各页 nav-link
# 移除 task/fund_exit_*.md（可选保留作记录）
```
低耦合设计：独立 route/template/api/folder，一刀切即可。

## 行业透视层（2026-07-06, display-only）
- `fund_sectors.py`：季报前十大重仓 × 证监会行业（cninfo 按需查询+永久缓存 `sector_map_cache.json`）→ `fund_sectors.json`（均 gitignore）。
- 主扫描内嵌 `refresh_if_stale()`（<7 天跳过）；单独重跑：`.venv_fund/bin/python fund_exit/fund_sectors.py`。
- **不进卖出规则**（季度滞后 + 前十大仅覆盖 40-60% NAV，不足以驱动闸门；同 5.5 regime 降级先例）；用于回答"剩余持仓是否同一行业赌注"。前端：账户条集中度（>30% 金色警示）+ 展开面板每只 top3 行业。
- 数据源备注：EM 个股/板块端点 2026-07 起被反爬（JSONDecodeError/RemoteDisconnected），sina 行业成分 ~2.5min/行业太慢，均弃用。
