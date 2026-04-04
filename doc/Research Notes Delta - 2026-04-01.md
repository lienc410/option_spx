# Research Notes Delta - 2026-04-01
**说明*：本文件为增量文档，仅记录 2026-04-01 新增的研究发现。不重复已有章节（51-531）的内容。如需参考已有章节，请见、doc/research_notes.md’.
E-T: 531 "Concentrated Exposure & Stress Period Analysis" (2026-03-30)
## 532 Daily Portfolio Metrics - M Trade-Level Daily Portfolio Level (SPEC-024, 2026-04-01)
**Status:V已实施*：
### 研究问题
Sharpe和 Calmar基于 trade-1evel计算：每笔交易作为独立观测单元，用其PnL构建收益序列。在单仓串行运行时，这是合理的近似。但在多合并行时，重受持合便交易之
-trade-level metnics 会系统性低估相关性，高估多样化效果，
现有系统的间不独疗-
具体后果：
-两笔重强持仓同时在 VIX spike期间亏损，trade-Leve1将其计算为“两次独立事件"，实际它们是同一个市场日的同一次）中击
-用 trade-level Shanpe 作为下一轮 signal设计的驱动指标，会产生系统性误判一
-优化目标与实际组合风险脱节
### 核心发现
1. **多仓并行时，实际组合波动来自每日净值变化，而非每笔交易独立结算**。重叠仓位期间的相关性决定真实drawdown深度，
1.    **所有组合层风险控制（shock budget. overlay、资金利用率）都需要 daily book view.入场守护链（SPEC-025/026）无法基于 trade-1evei 序列做实时判断——立需要知道“今天的 portfolio 在各场晨下损失多少”
2.    •trade-level Shanpe作为下一轮设计的驱动指标会产生系统性误判*。Dailyportfolio Shanpe（基于实际净值日度变化）才是与真实资本消耗对济的度量。
### 实现方路
’PortfolioTracker‘（backtest/portfolio.py):
**^DailyPortfolioRow ** （17 亨段）；
1 字段1说明！
date 日期|
start_equity| 日初净值|
end_equity1日末净值|
*daily_petunn_gross~|毛收益率（不含 haircut）|daily_netunn_net，1净收益率（含 naircut）！
peelized_pn11 当日结算的已实现 PnL！
unnea1ized_pnl_delte、| unrealized PnL 絞前日变化！
total_ pni | realized + unrealized delta |
bp_used |当日使用的 Buying Powenbp_headnoom”|BP剩余（占 NAV比例）！
short_comma_count〉|short_gomma 仓位数|
open_positions™|开仓数量
negime，|当日 VIX Regimevix’| 世日 VIX |
cumulative_equity"|累计净值
1^arawdown，|当日 drawdown（vs历史高点）
fexperiment_ia，| 所届实验 Ip|
me_prev_marks*oict**：追踪每个position_ian的前一日 mark.计算日度 unrealized delta. 每日收盘后更新，持仓到期/平合时清除。
**compute_portfolio_metrics) ** (backtest/metrics_portfolio.py)
python daily_sharpe daily_sortino
- mean(daily return net)
daily calmar
- mean(daily return net) / sta(dailyreturnnet[daily_return_net < 01) * sart(252)
ann_return / abs(max_drawdown)
cvar_95
- mean (bottom_5pct_daily_returns)
worst 5d dd
- min(rolling_5d_drawdown)
positive_months_pct - months_positive / total months
### 与 Trade-Leve1 指标的关系
- *保留，compute_metrics（） （trade-1eve2）用于向后非容及策略族横向对比（ROM 排名等）
Ln 506, Col 1
Windows (CRLF)
UTF-8


*Untitled - Notepad

File
Edit
View
- **新增 daily pontfolio 指标**作为主要决策依满一所有 SPEC-025/026 的风险控制均基于 daily portfolio
view
- 两套指标数字差异来源：（1）haircut 应用方式不同：（2）daily metrics 使用 net return序列而非trade P&L 聚合。详见 $8说明（strategy_status_2026-04-01.na）
### Experiment Registry
引入generate_experiment_id（）'→式EXP-YYYYMMDD-HHMMSS-XXXX®（XXXX4位机学符）。
config_hash - sha256（params JSON） ［：12］；参数完全确定的情况下产生相同哈希，支持去重和结果回放。
**所有回测输出强制关联^experiment_id”**，保证：
-  每次实验可精确复现（通过 config_hash定位参数）
-   多版本結果可対比（EXP-baseline vs EXP-fu11等）
-审计日志不丢失（shock report. overlay 1og 均携带 experiment_id）
家現文件：”backtest/registry.py

## 533 Portfolio Shock-Risk Engine - 基于场景的组合风险预算（SPEC-025, 2026-04-01）
**Status:V已实施**
###研究问毁
现有系统的入场控制依赖 count-based rule（^max_short_gamma_positions=3）：只要 short_gamma 仓位数不超过3，就允许入场。这个规则无法区分同样是“3 个 short-gamm仓位”但风险截然不同的情况：
- 场最 A:3 个窄 wing BPS，各自最大亏损$500，组合极端损失约 $1,580
-场 B：
3 个宽IC +高 DTE，各自最大亏损 $3,908，组合极端损失可达 $9,000
Count-based rule 对两者一视同仁。需要真正的组合层面 tail risk度量，以 NAV 百分比表达。
###设计决策- 8个标准场具
TD
场最名称|
Spot_pct
vix_shock_pt | 分类

S1
S2
S3
下行轻冲中击
-2%1
+5pt| Cone
下行中冲击
=3%
+8pt Core
下行重冲中 ！
=5%
纯波动大16%+15pt Core
+10pt
I Core 1
上行経中主
S6
上行重中击
1+2%1
-3pt | Tail
S7
+5%| -8pt | Tail
反弹 +Vo1 正常化|+3%
S8
-Spt
Tail
1 下行 +期限结构反转 |-2%1 +5pt | 独立记录
S1-S4 （Core Scenarios）用于计算、max_core-2033_pct_pBYi，作为主聚取算门限。55-57（To31 Scenarios）独立记录，首不纳入预算控制（v2 扩展）。S8与 S1 数慷相同但独立记录：spec明确要求分离，后续可调整 spot/vo1参数以专门捕捉期限结构反转效应。
### 关键实现细节
**S1gma 使用当日 VIx/180（外部传入），非'pos.entry_sigma”+
设计原因：shock engine 的目的是“在当前 sigma 水平下，如果 spot进一出移动，仓位会损失多少"。使用历史入场 sigma 会任估当前的期权敏感度-VIX-25，若用 15%sigmo 重估，会低估 vega损失约40%.
python
sigma = current_vix / 100.e
sigma = max(0.05, min(2.00, sigma))
份收口，入场时 VIX=15，今日
#champ 防止 B5 公式数值退化
**增量风险贡献**
python
incremental_shock_pct - post_max core - pre max core
仅衡量加入候选合位的边际风险贡献，而非 pontfo2i。绝对风验。这允许在 portfolio 已有低风险仓位时，接受边际员献致小的新食位。
，运行模式*
shaaowi模式（默认）：始终approved-True，仅记录审计日志（ShockReport 存入CSV）。不阻断任何交嗣，允许观察历史数模中snock分布，
-active”模式：abs（post_max_Core）>budget”时，approved-False"，阻断入场，记录reject_reason”，

File
Edit
View
-'active，模式：'abs（post_max_core）>budget时，approved=False，阻断入场，记录 reject_reason".
###风险预算（默认信）
#* | Normal Regime | HIGH_VOL Regime | shock_budget_core_normal | 1.25% NAV
shock_budget_core_hvI-
1.00% NAV
shock_budget_incremental | 0.40% NAV
shock_budget_incremental_hv
一-
0.30% NAV
shock budget bo headroom"
15% NAV 15% NAV
HIGH_VOL regime预算更严格、理由：HIGH_VOL 时actual correlation上升（共同对 VIX 敏感），原本分散的合位在压力下相关性趋近1。
### ShockReport 数据结构
mpython
@dataclass class ShockReport:
date: str nav: float
pre_scenarios: dict[str, float] pre_max_core_loss_pct: float post_scenarios: dict[str, float] post max core loss pct: float incremental shock pct: float budget_core: float budget_incremental: float approved: bool
reject_ reason: str | None mode: str
#8 个场景的 pre-entry 损失 （$）
#S1-S4 最差，占 NAV
# 含候选仓位后的8 场景损失
# "shadow" | "active"
实现文件：backtest/shock_engine.pyi

## 534 VIX Acceleration Overlay _ 组合层加速度防御状态机 （SPEC-026, 2026-04-01）
**Status：♥己安施**
### 研究问题
Senior auant neview （58.24）指出：单笔 panie stop 无效（已有实证）本组合层 overlay 无价值。两者的核心区别：
维度 |单笔 panic stop ］ 组合层 overlay
--------------
触发时机|单笔仓位已大幅亏损后平仓|市场加速阶段，先于大亏损触发|执行成本|最差价差时点机械全平，成本最高|分级响应，先冻结新风险再评估 trim|
1 信号质量|单合 PnL（滞后指标）|vix_accel x book_shock（前餘组合）|
1历史实证 |2015/2020 panic stop 期望为负 |L2 tnim 在 2015 VIX spike 显著有效（S35）|结论：废除单笔 panic stop，在组合层引入VIX加速度驱动的分级状态机。
###信号选择
•放弃 term_inversion（VIX3M 无历史数据）**，使用以下三个信号：
1.   w#vix_accel_3d = （VIX_t / VIX_｛t-3｝）- 2”*：市场加速度。3日窗口平衡了噪声和响应速度（1日窗口噪高过大，5日窗口响应太慢）。
2.   ~book_core_shock：当日已有仓位在8个场最下的最差 core 1oss（来自 shock engine， 每日独立计算），衡量”当前 portfolio 有多脂弱"，与 vix_accel 构成 AND条件。
3.    *#vix’**；绝对水位 （Level 4 emergency保护）。
4.    **~bp_headroom**：资金紧急状态 （Level 4 兜底）
### 关键设计决定 - book_core_shock 信号路径修复
*初始实现的缺陷**：“booK_Core_shock从 ShockRepont 取值，而 ShockReport 只在有候选入场时生成，缺陷的具体后果：
Level 1 freeze 触发
→当日无入場候造
Ln 506, Col 1
Windows (CRLF)
UTF-8

File
Edit
View
Level 1 freeze 触发
• 当日无入场候选
→ 无 ShockReport 生成
+ book_core_shock = 0（默认值）
+ L2 AND 条件永远不满足
•L2 永远不触发
m修复方案”：在主循环中独立计算每日existing portfo11o shock，不依赖入场路径；
hipython
＃每日收盘后，无论有无候选入场，都计算现有合位的 shocK
if position is not None:
-sc_results- compute_portfolio_shock(
[position], spx, sigma, SCENARIOS, nav
_daily_book_shock max_core_loss_pct(sc_results)
_daily_book_shock ee
# fosS overlay state machine
overlay_result - compute_overlay_signals
vix-vix, vix_3d_ago=vix_3d_ago,
book_core_shock-_daily_book_shock, bp_headroom-bp_headroom, params-params,
2..
此修复使 L2 在 2015 VIX spike 等真实压力事件中正常触发（§35实验数据验证）。
#耕# 行动分级（状态机）
1 Leve1 | 触发条件 | 逻辑 | 行动|
1 e Normal 1 -|- | 正常运行，无限制 |
1 1 Freeze 1accel_3d >15%〉OR vix ≥ 30| OR | 蔡止新开 short-vol 仓位1
！ 2 Freeze + Trim | accel_3d >25%AND "booK_core_shock ≥ 1% | AND | Freeze + 强制平当前全部特合|1 3 Freeze + Trim + Hedge |'accei_3d 〉35%AND book_core._shock 2 1.5%）| AND | V1：执行同 L2:v2： 额外开 long put spread hedge I
1 4 Emergency I^vix P 48°OR~book_core_shock 2 2.5%OR“bp_headroom < 10%"1 OR | 强制退出所有合位
*  AND 条件的设计還辑（L2/L3）**：防止 VIX 正常上升但合位风险可控时误触。若 portfo1io完全由 1ong-vega 策略（Diogona1）构成，VIX上升反而有利。此时L2的 AND 餐件使“book_core_shock”保持低位，不触发 trim.
*  •OR 经件的设计运辑 （L4）•：任何一个极端信号出现（VIx已达 48，或 portfo1o 已承受极端压力，或BP 危机）时，立即强制保护，不等待AND条件同时满足。
### StrategyParams 中的 Overlay 参数（9个）
參数| 默认值 | Level 映射！
overlay_mode"
1"disabled"|-|
overlay freeze accel overlay_freeze_vix"
10.15 | 111
overlay_trim_accel overlay_trim_shock"
1e.25
0.01
overlay_hedge_accel overlay_hedge_shock"
0.015
以L2L2L3
L3
overlay_emergency_vix
overlay_emergency_shock"
40.0L4
0.025 | L4 |
overlay_emergency_bp"
/ 0.10 | L4 |
实现文件：'signo15/overlay.py
## 535 Overlay 5-Version 对照回測（2026-04-01）
**Status：• 实验充成**### 实验设计
控 senior quant review 58.24-8.25 的要求，对比5个 overlay 配置在 2000-2026 全历史*4个压力會口的表现。实验均使用 daily port folio meteics （SPEC-024），每次运行关联独立 experiment_1d.

*Untitled - Notepad

口

File
Edit
View
### 实验设计

按 senior quant review S8.24-8.25 的要求，对比5个
overlay
次运行关联独立 experiment_id.
配置在 2000-2026 全历史+4个压力窗口的表现。实验均使用 daily portfo110 metrics （SPEC-024），每
**5 1实验配置**：
实验名|overlay_mode|说明|
-------||
EXP-baseline"1 disabled |原始系统，无任何 overlay|「EXp-freeze™| active， 仅L1| 只东结，不trim|
EXP-freeze_trim | active, L1+L2 | 冻结 +trim |
I active. L1+L3 | 冻结 +trim+hedge （V1.
EXP-freeze_hedge，
^EXP-fu111 active. L1+L2+L3+L4 | 全层级开启|
实际同 trim）|
所有实验使用相同信号参数（SPEC-015 spel2 throttle. SPEC-017 synthetic IC b10Ck. SPEC-025 shock engine shadow mode），仅 over2ay 层差异.
### 全历史指标（2000-01-03 至 2026-03-31）
M | Ann.Ret | Sharpe | Calmar | MaxDD
CVaR95 |交易数|
EXP-baseline (F overlay) | 3.73% | 0.70 | 6.24 | -15.35% | -0.837% | 354 İ
EXP-freeze (L1 only) | 3.77% | 0.70 | 0.30 | -12.63% | -0.835% | 331 |
EXP-freeze_trim (L1+L2) | 4.25% | 0.85 | 0.34 | -12.38% | -0.747% | 348 | EXP-freeze_hedge (L1+L3) | 3.90% | 0.74 | 0.31 | -12.59% | -0.808% | 333 |
**EXP-fu11 (L1+L2+L3+L4) ** | **4.26%** 1**0.86** | **0.35** |=*-12.22%=* | **-0.736%**/**348** |
〉注：EXP-baseline 与 strategy_status_2026-03-36.md 的历史基准（26yrSharpe 1.54）使用不同计量基础前者是 daily portfolio metrics.后者是 trade-levelmetrics.两者不可直接对比，但方向一致（均显示系統有正期望）。
### 圧力盛口 Max Drawdown 対比
配置|2011 EU债务危机|2015 VIX spike | 2020 COVID | 2022 熊市 |
EXP-baseline 1-2.78%1-2.13%1-4.45%1-5.59%
EXP-freeze (L1) | -2.78% | -2.13% | -4.45% | -5.59% |
EXP-freeze_trim （L1+L2） 1 -0.10%1 -0.46%1-4.13%1-5.20%
EXP-freeze_hedge（L1+L3） | -0.15% | -0.52% | -4.18% | -5.25%）
*  *EXP-fu11 (L1+L2+L3+L4) *= |**-0.10%*= |*•-0.46%**|**-4.13%**|*=-5.20%-- |
*  注：EXP-freeze 在2011/2015 无改善—
这两个事件的 VIX 加速度超过L2 阂值但未达L2.纯 freeze 无法保护已开合位。L2 trim 触发后才有显著效果
### 验收标准 （VS EXP-baseline, EXP-fu11）验收项！门限|EXP-fU1实|通过|
MaxDD 改善1≥10%128.4%（15.35%→12.22%）｜マ|
I CVaR95改善|≥10%| 12.1%（0-837%-10.736%，
关糖压力食日 araudoun 改 」明早」2025改路76%，2013改期00%1 ！
1年化收益不降（PnL保护）|≥92% of baseline |+14% （3.73%-4.26%）
1交易数降幅1≤ 10％1-1.7%（354-348）|くー
### 为何 Freeze+Trim 优于纯 Freeze （L2 的价值）
*机制1一8P程放与再入场*：Trim 后 BP释放，下一个更好的入场点（VIX回著后）可再次入场，EXP-freeze_trim交易教348>BXP-freeze的331，说明 12 trim后系能实际增加了优质入场机会，而非简单减少交易。
*  *机制 2-已开仓位的期望值转负**：L2 触发条件为accel_3d》25%AND shock ≥ 1%，此时：VIX 正在加速上升（非简单高位盘）当前仓位在 core scenarios 下已承受≥1% NAV 的潜在损失继续持有等到期：期望在 VIX 持续攀升中损失加深，平合成本虽高但低于继续持有的期望损失
*  机制3＝肘机非最茶点＊＊：12在vix_acce】年期限（3日発＞258）、通常不足VIX 的絶対経値（万史数期中、12 銀2日平均VIX 経固本有3-7天）・国出trimB的
bid-ask 仍在可接受范围。
### 2028 COVID 效果有限的原因
COVID的 VIX 崩溃速度异常：2026-02-24 至 2026-63-16.VIX 从 25 双升至 85，约15 个交易日。但其中最购烈的阶段（VTX 40-85）发生在约5个交易日内，超过vix_accel_3d 3 日窗口的响应速度
-L4 emergency exit 触发时，部分损失已无法规避。
改进方向（待v2）：增加 vix_accei_ia”快速响应路径，专门处理 COVID 类的极速崩溃事件（参见未解决问题 #2），
Ln 287 Col 32
80%
Windows (CRLF)
*Untitled - Notepad
File
Edit
View
改进方向（待v2）：增加*vix_acce1_1d°快速响应路径，专门处理 COVID 类的极速崩溃事件（参见未解决问题 #2）。
### 推荐生产配置
**EXP-fU11**（overlay_mode="active”，所有阈值使用 SPEC-026 默认值）
理由：
-   EXP-fu11 与 ExP-freeze_trim全历史指标几乎相同（Sharpe 6.86 vs 0.85,MaxDD 12.22% vs 12.38%），L4 emergency 提供额外的极端事件保护，且对全历史几乎无成本
-   L3 hedge （v2 实现后）将进一步区分 EXP-fu11 与EXP-freeze_trim
### 未解决的问题
1.    **L3 heage 实际开合（v2）**：V2中L3实际执行trim（与L2行为相同），真正的long put spread hedge（在trim的同时开保护性头寸）待v2实现并验证
2.   ** vix_accel_1d用于L4 fast-path**：提升对极速崩溃（COVID类型）的响应。需要额外的backtest 验证避免L4被日内噪声误触，
3.   **多合引|擎下 trim 精细化*：当前L2/L4触发时全平所有仓位。扩展到多仓后，可精细到“只关闭shock 贡献最高的仓位”而保留低风险仓位，提高资本效率，

## §36 Shock Engine Active Mode 校准与 A/B 验证（SPEC-027, 2026-04-02）
**Status: V
### 研究问题
SPEC-025实现的 Shock Engine 在 shadow mode 下运行一所有风险报告计算并输出，但不泪止入场或强制退出。要格其切换为 active mode（真正守护资本），需要先验证：shadow
mode 下"如果 shock gate 是 active 的，拦截率是多少？分布如何？“只有 nit rate 落在合理区间（过高则系统入场大少，过低则守护无意义），才能安全启用 active mode.
## Phase A: Shadow 模式下的 ShockReport 分析
**核心分析维度：**
1. wHit rate（年度分布）**：哪些年份 shock gate 会频終拦截？历史上高 VIX年（2062.2008-09、2020.
2.
**Breach type 分布**：
2022）是否 nit rate 显著更高？
3.
post_max_cone_1oss_pct”超预算 vs"incrementa1_shocK_pct、超预算 vsbp_headroom_pct低于15%一三类 breach 各占多少？
wpencentile 分布**：shock 数值的分布（中位数、P95.P99），为 budget 校准提供依据。
**关键实现问题（Fast Path 修复）*：
icompute_hit_rates、中有 bug:any_breach_rate使用＜~shock_df ［"approved"1）・sumO）但 shadow mode 中•approved”永遠方"True（shadow 不裁）、写
致"would-be rejection rate"恒为0%.完全失去 Phase A的意义
*  *修复**：改用预算列直接比绞：
*  python
any_core_b = shock_df["post_max_core_loss_pct"].abs() > shock df["budget_max_core")
any_inc_b
- shock_df["incremental_shock_pct"].abs()
> shock_dfl"budget_incremental"]
any_bp_b
• shock_df["bp_headroom_pct"| < 0.15
any_breach - (any_core_b | any_inc_b | any_bp_b). sum()
### Phase B: Active vs Shadow A/B
**Acceptance Criteria (active mode (E) = **
！AC|指标 | 阈值 |
81
82
B3
1B4
Trade count 下降|≤10%（active 不过度收窄入场）！
PnL 变化|下降≤8%（守护成本可接受）！
MaxDD 1不劣子 shadow l
CVaR（5%）|不劣于 shadow|
## §37 资本效率指标与 PnL归因（SPEC-028,2026-04-02）
*Status：义 已实施*
### 研究问题
BUtty daily portfolio metrics (Sharpe. MaxDD
###核心新增指标
星*结果指标一，无法回會“哪个策略类型员献了PnL？哪个 regime 下系統最赚线？资本是否故高效利用？“
Ln 287, Col 32
80%
Windows (CRLF)
UTF-B

##＃核心新增指标
**pnl_per_bp_day”（资本利用率调堅后收益）**
pr_per_bp_day = total_net_pn1 / I (daily_used bp)
单位：每占用1 美元保证金1天获得的净 PnL（美元）。将持仓时间和资金占用同时纳入分母，消除“长时间持有低效仓位“对胜率的扭曲。
※* compute_strategy_attribution（）＊*ー 技策路型で急（11列：trade count. win rate. net_pnl. mean_pni_per_trade. pni_per_bp_day等。
**'compute_regime_attribution（）** -按 VIX regime 汇总（8列）：
day_count. pct_of_trading_days. mean_daily_return_net. regime_sharpe, mean_bp_utilization, total_net_pnl_contribution S.
###研究意义
^pni_per_bp_day是评估策略”资本效逐”的关键指标。Diagona1占用BP时间按长，如果其 pn1_per_bp_doy 明是低于 BPS，说明资本被低效占用。结合§38的 005 验证，可以量化 Diagona1在 0os期的资本效密劣化程度，成为 trend signa1改进（546）的数值目标。

##§38 出祥本（00S）验证：IS-2000-2019/0OS-2020-2026（SPEC-029,2026-04-02）
**Status:V已实施*
### 研究设计
**单次全历史回测+日期过滤**（非两次独立回测），避免00S回测缺小IS 期仓位状态的 cold-stant artifact.
0OS AC （完松子全万史）：MaxDD improvement 15%（Vs Ful1 218%）， PnL retention 285%（vs Fuaa 1928）・
###5 张对比报表
报表！内容！
| R1 | Fu11 / IS / O0S =#• Ann.Ret. Sharpe. Calmar. MaxDD. CVaR. Trades |
1R2 | EXP-FU12 VS EXP-baseline delta，按三會口分列|
1 R3 | O0S AC FIS (Sharpe>® / MaxDD≥5% / PnL retention285% / Trade drop≤15%)|
人！
00s期（2620-2626）策略归因（pn1_per_bp_day by strategy）|
1R5 R51 00S 18 Regime VE (Sharpe/BP util by VIX regime)[
## 639 SPX 趋势信号深度研究：Alternative Signal 评估 （2026-04-02）
*Status： • 研究完成，立项建议已写入 SPEC-020**
封勘# 两类核心问题
1.    **Entry Gate 假 BULLISH**：能市反弹导致 SPX短暂站上MA50+1%，系统开 BPS/Diagonal •回溶亏损。
2.    *Exit Trigeer 误触发 trend_flip*e: 3-7 天正常修正触发单日 BEARISH•系統卖在局部麻部，#耕# 评分矩阵
1 方向 | 减少假信号 | 及时性 |实现复杂度 | 数据素求|总分|
1 **ATR Gap (Entry) * 14 | 4 | 4| 3 | 20/25**|
1 •*Persistence Filter (Exit) * | 5 | 3 | 4 | 5| **22/25** |
1 Regime-Conditiona1（登加）
| 5| 4
| 3 | 3* | 19/25 |
ADX 碗认（Exit辅助）
14131313*
27/25
ROC/MACD 1115|4|518/25
Swing Structure |3|212|5
14/25
*不推荐方向报本原因 ：ROC/MACD 的信号逻辑（动量始大越 BEARISH）与 short-Vo1策略（修正是机会）方向相反，Swing Structure识别时市场已下跌 10-15%，无时效性，且話要 1ookback window 参数，过拟合风险极高，
## 540 ATR-Normalized Entry Gate + Persistence Exit Filter (SPEC-020, 2026-04-02)
•*Status:
实施中 （RS-020-1 FAIL， 待 RS-020-2）•
Ln 287, Col 32

### 问题根因
固定1%band 在VIX=12 时等效t3.30（难触发），在VIX=30时等效 0.67。（极易触发）。ATR 标准化后〝gap_sigma = （SPX-MA58）/ATR（14）． 1。阈值在任何 VIX「下含义一致。
Persistence filter：〝bearish_streak >= 3、才触发 trend_flip（代替单日 BEARISH）。streak 在日循坏顶层维护。
### 67 前置研究结果
•参数|初始假设| 实证修正|
ATR_THRESHOLD™| 1.0 | 1.0（确认，gap_sigma 分布与原 +1% band 最接近）|
"BEARISH_PERSISTENCE_DAYS"
**修正为 3**（streak=3 是条件概率拐点 P=0.850:N=5 与N=3 概密几乎相同 e.849，延迟代价不值）！
### ChatGPT Review 关键决策
**采纳**：强制 4-way ablation （EXP-baseline / EXP-atr/EXP-persist / EXP-fU11），按 regime 分层报告，3x3 稳健性参数网格。
**驳回*：“信号语义改变是缺路，—ATR normalization 将信号变为”状态依赖过法器“是**设计意图**，已在S1.3明确说明。
### 当前状态
ablation 未完成（AC7-AC10无法验证）。**待AMP提交RS-020-2**。