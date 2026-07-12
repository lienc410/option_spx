# SPEC-141 实施 Handoff — 统一状态面（S1）+ State Map 页（S2a）

**Date**: 2026-07-11 · **Role**: Developer · **Status**: 实施完成，留工作区未 commit（按任务要求）
**待办**: Quant fidelity review + AC-9 browse QA（见 §五清单）

---

## 一、文件-F 对照

| 文件 | 状态 | 对应 F | 内容 |
|---|---|---|---|
| `strategy/state_surface.py` | 新增 | F1+F2 | `compute_state_surface()` 纯只读聚合（7 个 spec 契约字段 + 3 个页面支持字段），逐字段 fail-soft；`bar_geometry()` 量表几何单源（AC-6）；`append_daily_log()` 幂等日志 + 首跑 90 TD 回填；`read_history()`；CLI `--print/--log` |
| `web/server.py` | 修改（+2 路由） | F2/F3 | `/state-map` 页路由；`/api/state-surface`（恒 200，`_json_sanitize` 走 NaN 纪律，附 `history` 最近 90 行） |
| `scripts/daily_snapshot.py` | 修改（+hook） | F2 | `_state_surface_hook()`：日度 job 内调用 `append_daily_log()`；隔离 try/except，放在 trading-day gate 之后、snapshot 幂等检查之前（状态面日志有独立幂等，snapshot 已记录/失败都不影响补写） |
| `web/templates/state_map.html` | 新增 | F3 | 四层纵向层框活版（L0 veto 灯条 / L1 双轴+四事件灯+DIP 距离条 / L2 三引擎卡（§4 静态身份块 + live 行）/ L3 双池绝对刻度条）+ 90 天双色带 + 触发预演面板（DIP 灯点击展开） |
| `web/templates/portfolio_home.html` | 修改（纯新增一块） | F4 | 顶部 hero 条（VOL/STRUCT/DIP/AMMO 一行摘要 → 链接 /state-map），marker 注释定界的单一连续插入块（style+html+js 全在块内）；**其余逐字节不动** |
| `web/templates/_nav.html` | 修改（+1 行） | F3 | `State Map` nav 入口（Portfolio 之后；nav 单源，全页生效） |
| `tests/test_spec_141.py` | 新增 | 验收 | 26 条，覆盖 AC-1..8、10（AC-9 归 Quant browse QA） |

复用源（零重写）：`ex._find_chop_episodes/_classify_trigger_type/_ammo_advisory/_fetch_spx_close_series/_EPISODE_*`（094.4 LOCKED）、`signals/vix_regime`（15/22 阈值）、`strategy/selector`（`is_aftermath`、`DEFAULT_PARAMS.extreme_vix=35`、`get_recommendation`）、`signals/q042_trigger`（`_DD4_THRESHOLD`、snapshot）、`strategy/sleeve_governance.RUNTIME_STATE_PATH`（runtime 快照只读）、`strategy/cash_budget_governance`（liquid/debit/floor/cap 常量）、`strategy/q042_sizing`（`compute_sizing`、`q042_sleeve_cap_pct("A")=12.5`）。

## 二、AC 逐条 + 证据

| AC | 结论 | 证据 |
|---|---|---|
| AC-141-1 | ✅ | `test_ac1_*` 5 条：episode_day/band 直接对 `ex._find_chop_episodes` 段真值逐一致；`type_if_now` 对 `_classify_trigger_type`；ddath/armed 对 q042 snapshot；caps/pools 对 governance runtime；liquid/debit 对 cash_budget；reserve = basis × `q042_sleeve_cap_pct("A")`；API 全字段 200 |
| AC-141-2 | ✅ | `test_ac2_*`：首跑 91 行（90 回填 + 1 全量），回填行仅 `{date, backfill:true, vol_state, structure_state}`；同日二跑字节不变；次日只追加 1 行。真数据实测：26y 缓存回填 90 TD 3.4s，分布 RANGE 52 / TREND_UP 23 / TREND_DOWN 12 / MIXED 3（与"5-05 起在区间里"一致） |
| AC-141-3 | ✅ | `test_ac3_*` 4 条：vix+cash 注入失败 → 仅对应字段 n/a，其余 ok；ath_degraded → dip n/a 且**无 ddath 字段**（0 填充不当真值，沿 094.2 F7）；模块级 raise → API 仍 200；模板 n/a 呈现路径断言。**dev 机活体证据**：本机无 governance runtime → ammo/pools/rehearsal/second_leg = n/a 带原因，vol/structure/trend/today 正常 |
| AC-141-4 | ✅ | `test_ac4_*`：selector/sleeve_governance/production/*.py 无 "state_surface" 字样 + `git diff HEAD` 三路径为空。依赖方向 state_surface → 决策模块，单向 |
| AC-141-5 | ✅ | 数据层：engines 值域 ⊆ {ON, STANDBY}（含 reduce_wait、DIP+armed 场景）；模板层：`BADGE_WORDS` 常量只两词、`engineBadge` 非法词降级 n/a、`Trigger armed:` 行内字段、无 `>ARMED<`/`>READY<`/`>FIRE<` 徽章文本 |
| AC-141-6 | ✅ | `bar_geometry` 单测：同值同长（cap 不影响宽度）、width=value/scale_max×100、clamp、cap_pos_pct；pools 断言 spx_pm 与 short_vol 同 scale_max=100、同值 30/30 同宽（mockup bug 回归）；模板只消费 `width_pct/cap_pos_pct` 不重算 |
| AC-141-7 | ✅ | `test_ac7_*`：逐行剥除 marker 定界 hero 块后与 `git show HEAD:` **逐字节一致**（全文件级，两不动锚点自动覆盖）+ Open Position 块与 Portfolio Snapshot zone 头分别单独 byte-diff 断言 |
| AC-141-8 | ✅ | 三例：episode+现金足 → call_spread/「弹药充足」；episode+10k → bps_fallback/SELL PUT/BUY PUT/「3.7-7.4×」提醒句；sudden+10k → stand_aside/「建议空仓」且无 BPS strikes。另加**委托断言**：monkeypatch `ex._ammo_advisory` 哨兵 → 预演正文=哨兵（证明复用非重写） |
| AC-141-9 | ⏳ Quant | browse QA 归 Quant（§五清单） |
| AC-141-10 | ✅ | 见 §三回归数字 |

## 三、回归

- **Spec 指定命令**：`venv/bin/python -m pytest tests/test_spec_094_2.py tests/test_spec_094_3.py tests/test_spec_094_4.py tests/test_spec_141.py tests/test_state_and_api.py -q` → **92 passed**（其中 test_spec_141 26 条）。
- **改动波及面加跑**：模板/导航扫描套件 `125/087/132_1/135_2/135_5/139_2_fonts` → **98 passed**；daily_snapshot/portfolio_home 相关 `110/089/108_1/135_3/135_4` → **115 passed（+4 subtests）**。
- **冒烟**：`py_compile` 三文件过；本机起 Flask（:5199）→ `/state-map` 200、`/api/state-surface` 200（1.6s）、`/` 含 hero 条；payload 严格 grep 无 `NaN/Infinity`（浏览器 .json() 安全）。
- 决策路径零 diff：`git diff HEAD -- strategy/selector.py strategy/sleeve_governance.py production` 为空（且有测试常驻断言）。

## 四、取舍与歧义（Quant 复核点）

1. **governance 读取 = runtime 快照文件而非现算**：`current_governance_state()` 会打 broker/selector（贵且有告警副作用），状态面读 `sleeve_governance_runtime.json`（record_state_snapshot 日度落盘），staleness 以 `runtime_ts` 全程透出。代价：caps/pools 最长滞后一个快照周期。若 Quant 认为 veto 灯必须现算，改一处 `_read_governance_runtime` 即可。
2. **引擎归属映射 `ENGINE_STRUCTURES`（display-only 新映射）**：§4 矩阵里 BPS 家族同时出现在 Premium（NORMAL×TREND-UP 行、HIGH 行 HV 半仓变体）与 Trend 两列 → 我按"列出现即归属"编码，路由 BPS 当日 Premium 与 Trend **双亮 ON**（忠实矩阵、也与 doc §7 mockup 双 ON 一致）。若要单一归属（BPS 只算 Trend），改常量集合 + 两条测试。
3. **Convexity ON 定义** = `dip.active（ddath ≤ −4%）且 sleeve A armed`；开着的 Q042 仓位不点亮 ON（"今日被路由"严格口径），仓位在 live 行显示。armed 永远是行内字段。
4. **并发 BCD 余量的"一张标准"** = `DEFAULT_PARAMS.bcd_max_debit_usd`（$22k，沿 `resource_waterline()` 先例 + no-param-mirror 纪律取代码真值）。doc §5 叙述"一张 BCD = $38-41k"（$118k/$158k 算术隐含 ~$39.5k）——两口径不一致，**请 Quant 裁决**；display-only，改一行。
5. **episode_day 口径**：贪婪段起点 → 最新收盘的交易日数（含当日）。greedy 分段的左贪特性会把入带前 2-3 根爬坡 bar 吸进段内（合成例：直觉 40 天，段真值 43 天）——与 094.4 verbatim 检测器完全一致，未做任何"修正"；测试以分段器输出为真值交叉。
6. **回填简版的 trend fallback**：非 RANGE 日用截断序列 MA50 gap ± `TREND_THRESHOLD`（1%，import signals.trend）分类——与 live 路径同公式同阈值，但 live 用 trend 快照（1y fetch）、回填用 26y 缓存截断，极端情况下同日可有微小出入（简版仅供色带）。
7. **debit 读失败不当 0**：`get_open_debit_total_usd()` 带 error 时 ammo/pools.cash 整体 n/a（沿 SPEC-138 F6 姿态），绝不用 0 假造 in-flight。
8. **F1 契约外 additive 字段**：`positions`（L2 live 行）、`pools`（L3 几何）、`rehearsal`（预演），同一 fail-soft 语义；F1 表格的 7 字段一个不少。
9. **首跑回填触发点**：日度 job 首跑或手动 `venv/bin/python -m strategy.state_surface --log`。部署 old Air 后时间轴在第一次 16:50 job 前为空（页面显示中文空态说明，不空白）。本机验证跑写在 scratchpad，**未在 repo 内产生 data/state_surface.jsonl**。
10. **rehearsal 的现金判定在 `ex._ammo_advisory` 内部**读 cash_budget（与触发告警同源）；预演的 need 用今日 close 现算 sizing，非明日开盘价——这是"若明天触发"的固有近似，正文未声称成交价。

## 五、给 Quant 的复核提示（AC-9 browse QA 核查点清单）

部署后用 browse 工具在 **1280 / 900 / 390** 三宽度截图核查 `/state-map` 与 `/`：

**文字重叠（约束 3 硬点）**
- L3 条形图：cap 金线标签（`cap 80%` / `cap 50%`）与 ammo 线标签在**条上方独立轨道**，0%/100%（cash 为 $0/$liquid）刻度在**条下方**——三宽度下标签不得压线、不得互叠；标签位置 >78% 应右锚、<8% 左锚（JS `tickHtml`）。
- 390px：veto 灯全宽堆叠、axis segments 折行、engine 卡单列、pool 单列——检查各 mono 值无溢出。

**量表（约束 2 硬点）**
- BP 双条同值日必须目测同长（当前 runtime spx_pm=short_vol 时可直接验证）；cap 线位于 80%/50% 绝对位置（非条端）。
- cash 条满格=liquid，金色 ammo 线在 `liquid − 12.5%×NLV` 位置。

**badge / 行内字段（约束 1）**
- 全页徽章词汇只见 ON / STANDBY；Convexity 卡 live 行有 `Trigger armed: yes/no`；veto/事件灯是纯色点无词。

**其余**
- dark/light 双主题 toggle 后全部 token 变色正常（无写死色值）。
- 全数字 mono；中文 rationale 行主色 `--text`（engine 卡身份块、pool-note、layer-sub）；`--text-2` 只在 section 标签/次级 chrome。
- portfolio home：hero 条在 Page hero 与 Regime banner 之间，点击跳 /state-map；Open Position / Portfolio Snapshot 视觉无任何位移。
- 时间轴 hover title = 日期+状态；回填格半透明；图例常显。
- DIP 灯点击 → 预演面板展开并平滑滚动定位。
- 空态核查（可在 dev 机看）：无 governance runtime 时 ammo/pools/rehearsal 显示 n/a 不空白。
- fidelity 复核建议顺序：§四 2/4 两个 display-only 判定 → `ENGINE_STRUCTURES` 与 `bcd_standard_usd` 是仅有的两处"新解释"，其余全部是源值直传。

---

**Rollback**：新页/新 API 独立——摘 `_nav.html` 一行 + revert server.py 两路由即 404 归零；hero 块 marker 定界可单独剥除；`data/state_surface.jsonl` 为纯 append 日志可直接删除。零策略影响（AC-4 有常驻测试）。
