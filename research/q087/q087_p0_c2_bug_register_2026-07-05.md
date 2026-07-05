# Q087 P0 C-2 — 已知与潜伏 bug 清册（2026-07-05, Dev）

每项:现状证据 → 影响 → 修复成本 → 分诊建议。seed 1-4 已逐一核实,另补 5-9。

## 1. Greeks 跨券商乘数错配(seed,已核实)

**证据**:`portfolio_home.html:1779-1794` 与 `spx.html:1250-1262` —— `totalContracts = Σ(所有账户 contracts)`,再 `live.delta × totalContracts × 100`;而 `live`(`/api/position → schwab_live`)是 **Schwab 单腿链报价的 per-contract Greeks**。两账户 strikes/expiry 一致时数值恰好对;分歧时(如 Schwab 7300/7000 + ETrade 7200/6950)Δ×n/Γ×n/Θ×n/V×n 全错。
**影响**:PM 风险读数错误(展示层,不影响下单/governance——governance 用 max-loss 口径)。错幅与两账户结构分歧成正比。
**修复成本**:中。正解是 `/api/position` 按账户分别取链 Greeks 再加权(ETrade 侧 SPEC-089 的 `get_option_spread_quote` 已有链读取,缺 Greeks 字段透出);短平快是 UI 标注"Schwab-leg Greeks × 全量合约,分歧时失真"。
**分诊**:中影响/低风险/中工作量。PM 2026-06 已知悉暂缓——维持,排 Track C 中段;先上标注(1 行)。

## 2. `sleeve_governance.py:30-32` NLV 硬编码(seed,已核实,**判定:有界但值得快赢**)

**证据**:`SPX_NLV=ES_NLV=100_000 → COMBINED_NLV=200_000`。下游 5 处全部形如 `_num(state.get("basis_dollars")) or COMBINED_NLV` —— **仅作 fallback**:活动路径的 basis 来自 `portfolio_summary_payload` 实时 NLV(约 $1.24M)。
**触发条件**:broker/汇总层故障(`errors` 非空)时 `basis_dollars` 缺失 → 分母瞬间变 200k → `requested_pct` 膨胀 ~6.2× → R1-R6 各 CAP **提前误触发**。方向是 fail-closed(误拦不误放),但会在 broker 抖动时静默拒绝合法开仓,且 `evaluate_candidate` 的拒绝理由不标注"degraded basis"。
**修复成本**:低——fallback 改读最近一次 `sleeve_governance_runtime.json` 的 basis(磁盘上有),并在 decision 里加 `basis_degraded` 标记。
**分诊**:**高价值快赢确认**(Quant ⚠️ 判断成立,但机制是 fail-closed 误拦而非 CAP 失真放行)。建议 Track C 首批。

## 3. `web/server.py` 6,470 行分拆可行性(seed,初判:可行,低风险)

**证据**:118 routes 自然聚类——q041(9)、hvladder(9)、q042(8)、position(8)、etrade(6)、es(6)、portfolio(5)、fund-exit(5)、schwab(4)、experiments(4)、aftermath(4)、backtest(3)、其余零散;另有 ~20 个页面 route。
**共享状态**:模块级缓存 9 个(`_backtest_cache`、`_STRATEGY_MATRIX_CACHE`、`_ES_BT_CACHE`、`_AFTERMATH_*` 等)+ `_json_sanitize/_EnumEncoder/_no_store_html` 等横切件。
**建议切法**:Flask Blueprint 按上述聚类切 8-10 个文件,横切件入 `web/common.py`,缓存随各自 Blueprint 走;每步 bit-identical(路由表 + 响应 golden 对比)。
**分诊**:高工作量/低风险(纯搬移)/收益=可测性与变更隔离。排 Track C 主体,分 3-4 个 SPEC 渐进。

## 4. `selector.py` EXTREME 边界 35 vs 40(seed,已核实:**非注释漂移,是真实的第二边界,且在 selector 路径不可达**)

**证据**:`:56 extreme_vix=35.0`(参数);`:383 if vix.vix >= 40.0: return False` 在 `is_aftermath()` 内硬编码。调用方:`selector.py:711/827`(均在 HIGH_VOL 分支,该分支仅当 `vix < extreme_vix=35` 才进入 → **40 守卫在 selector 内不可达**);`web/server.py:752`(aftermath 状态展示端点,直接调 `is_aftermath` → 35-40 区间时 **UI 可能显示 aftermath=active 而 selector 实际已 REDUCE_WAIT**,展示与决策口径分裂)。
**影响**:决策路径无实际错误;展示层在 VIX∈[35,40) 有口径分裂窗口;未来若调 extreme_vix>40 会静默改变 aftermath 语义。
**修复成本**:低——`is_aftermath` 的 40.0 改引 `params.extreme_vix` 或显式命名常量 + 注释修正。走后续 SPEC(行为变更需 bit-identical 例外说明:仅影响 35-40 展示窗口)。
**分诊**:低影响/低成本,顺手项;与 Track A 的 extreme_vix 参数审计合并处理最economical。

## 5. 手动 `json.dumps` 端点的 NaN 逃逸面(新增,历史事故同源)

**证据**:6/10 事故(`feedback_nan_json_browser_vs_python`)后全局 `_SafeJSONProvider` 只覆盖 `jsonify`;`server.py` 仍有 2 处手动 dumps 响应路径(`:242 _json_dc`、`:583 api_recommendation`)靠事后补的 `_json_sanitize` 包裹。**任何新端点若模仿手动 dumps 模式且漏包裹,NaN 事故复发**。
**分诊**:低成本预防——加一条 CI 断言(grep `app.response_class(json.dumps` 必须同行含 `_json_sanitize`)或统一改走 jsonify。Track C 首批顺手项。

## 6. 本机休眠 LaunchAgents = 僵尸 connector 同类隐患(新增,→ 同录 D-1)

**证据**:本机 `~/Library/LaunchAgents/` 存有 `com.spxstrat.bot/web/q041_collect/greek_attribution/etrade-monthly` 5 个 plist(当前未 load,但 `RunAtLoad` 语义下登录/重启可拉起)。6/12 的 502 根因(本机僵尸 cloudflared 分流 1/3 流量)正是此类。双 bot 会互抢 Telegram getUpdates,双 collect 会写坏 chains。
**分诊**:**高风险/零成本**——重命名加 `.disabled` 后缀即可。建议立即执行(本清单任务不改代码,列为 checkpoint #1 首批动作)。

## 7. `etrade/client.py` 模块级 `_CACHE` 与 `expire_token_on_401` 的进程内 debounce(新增)

**证据**:`_LAST_401_RENEW` debounce 与报价 `_CACHE` 均为进程内存——web(waitress 多线程)、bot、scripts 各自进程互不知晓;401 风暴时多进程可并发打 renew 端点(debounce 只在单进程内生效)。
**影响**:低(renew 幂等,只是浪费调用);列册备查。

## 8. `q041_t3_earnings_check._US_HOLIDAYS_2026` 注释名与实际内容漂移 + 多份节假日表(新增,并入 C-1 重复清点)

2027 年表已在部分副本补齐、部分未补(`daily_snapshot.py` 只到 2026)。**2027-01-01 起 `daily_snapshot` 会把元旦当交易日跑**(fail-soft,但产生脏行)。统一到 `pandas_market_calendars`(已是依赖)。

## 9. `strategy/state.py` 位置文件无 schema 版本(新增,观察项)

`daily_snapshot.jsonl` 有 `schema_version=4`,但 `positions.json/state.json` 无版本字段;历史上靠 `_STRATEGY_BUCKET` 兼容层消化旧形态。跨 SPEC 加字段(如 SPEC-115 的 `cash_need_usd`)全靠 `.get()` 容错。低风险,Track C 重构 state 层时一并加版本戳。

---

## 分诊汇总(建议给 checkpoint #1)

| # | 项 | 影响 | 风险 | 工作量 | 建议 |
|---|---|---|---|---|---|
| 6 | 本机休眠 plist | 高 | 零 | 分钟 | **立即** |
| 2 | NLV fallback 误拦 | 中(degraded 时) | 低 | 小 | 首批快赢 |
| 5 | NaN 逃逸面 CI 断言 | 中(预防) | 零 | 小 | 首批顺手 |
| 4 | 35/40 双边界 | 低 | 低 | 小 | 并入 Track A extreme_vix 审计 |
| 1 | Greeks 乘数 | 中(展示) | 低 | 中 | 先标注后修 |
| 8 | 节假日表统一 | 中(2027 起) | 低 | 小 | 年内完成 |
| 3 | server.py 分拆 | 高(长期) | 低 | 大 | Track C 主体,分 SPEC |
| 7/9 | 观察项 | 低 | — | — | 列册即可 |
