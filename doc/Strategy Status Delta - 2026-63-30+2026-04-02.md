Strategy Status Delta - 2026-63-30+2026-04-02
*  适用场显。：快速了解本次迭代变更内容，无需重谈完整文档，
*  *完经文档**：〝doc/strategy_status_2026-04-01.ma"|
## 新增模块（5 个文件）
！文件| 模块内容 | 对应 SPEC 1
backtest/portfolão.pyPortfolioTracker PortfolioTracker DailyPortfolioRow(2771)
_prev_marksdict， 每日 unrealized delta 追踪| SPEC-024 |
backtest/metrics_portfolio.py conpute_portfolio_metrics): daily_sharpe. Sortino. Calmar. CVaR95. worst_5d_drawdown. positive_months_pct
SPEC-024 |
1backtest/registry.py） 1 generate_expeniment_id（）+：EXP-MWWDD-HHYYSS-XxX,config_hash - sha256（params）［：12］，实給结果强制关联 ID |
SPEC-024|
1:backtest/shock_engine-py1 8 标准场最定义，nun_shock_check（），：ShockReportdataclass, shadow/active 双模式，sigme 使用当日 VIX/100 | SPEC-025 |
signals/overlay-py OverlayLevel (0-4) compute_overlay_signals() 4 RH(Freeze/Trim/Hedge/Emergency)book core_shock itte
SPEC-0261
## 51 实证基线 -更并
**Before (2826-03-30, trade-level only) **
| 指标|值
| Sharpe | 1.54 (Bootstrap 95% CI: [1.18, 1.951) |
Calmar 1 26.23|
WR | 75.6% |
Total Pn|+192,234 Raw/S+94,070 Adj
**After（2026-04-01，两套指标并行）**Trade-leve1 （Legacy，保留不变）：同上，
Daily portfolio - SPEC-024 (*F*):
| M | Ann. Ret 1 Sharpe | Calmar | MaxDD |
1 EXP-baseline (F overlay)
| 3.73% | 0.70 | 0.24 | -15.35%||
1 •*EXP-fU1】（推荐生产配置）**|4.26%**| **0.86** | 8*0.35** | -12.22%** |＞计量基础不同，不可直接对比。trade-Leve】用于策略族 ROM 排名：daily portfolio 用于风险控制决策和多版本实验对比。
## 55 StrategyParams -新増字段
**Before （2026-03-30）•：9个参致
(extreme_vix, high_vol_delta. high_vol_dte. high_vol_size, normal_delta, normal_dte. profit_target.stop_mult, min_hold_days)
•*After （2026-04-01） *：25 介參数（新增16个）
###新增字段明畑
**SPEC-024（1↑）**
| 参数| 默认值|说明|
|~initial_equity" | 100,00e | 回测初始净值，DailyPortfo1ioRow 基准！
**SPEC-025 Shock-Risk Engine (6 1)
参数| 默认值 |说明！
“shock_mode’|，"shadow”，| shadow - 只记录：active•超预算时拦說！
shock_budget_core_normal
10.0125 | Normal: core shock fI 1.25% NAV |
shock_budget_core_hv | 0.0100 | HIGH_VOL: core shock Bl 1,00% NAV |
•shock_budget_incrementalf | 0.8840 | Normal：边际 shock 上限 0.40% NAVI
shock_budget_incremental_hv | 0.0030 | HIGH VOL: it shock FR 0.30% NAV |
shock_budget_bp_headroom| 0.15 | 任何 regiae: BP 最低剩余 15% NAY ！

Unimied" Noteoad

Edit
View
**SPEC-026 Acceleration Overlay (10 f) **
！參数|财以值| Levea||
--.١٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠
overlay_node
一'"disabled"，1- |
overlay_freeze_accel" | 0.15 | L1 (OR) | l overlay_freeze_vix* | 30.0 | L1 (OR) | l overlay_trin_accel" | 0.25 | L2 (AND) |/ l 'overlay_trim_shock" | 0.01 | L2 (AND) | l 'overlay_hedge_accel" | 0.35 | L3 (AND) |/ l 'overlay_hedge_shock" | 0.015 | L3 (AND) | l 'overlay_energency_vix" | 40.0 | L4 (OR) | overlay_emergency_shock | 0.025 | L4 (OR) [
I 'overlay energency _bp* | 0.10 | L4 (OR) 1
・・お数数変化※：9→25（+16介）
## 57 入场守护链 -更新
*  Before （2026-03-38） ••：6 出檢查（Steps 1-6， 全部与策略/合位/BP相关）
*  After （2026-04-01）•：新增 4个检查点：
| 新增出票| 时机| 内 | SPEC|
I step e | 每日开始（独立于入场路径）|计算现有合位‘_do11y_book_shock”：修复 L1 freeze 后 book_core_shock=9 的訣陷 | SPEC-026 1I Step pre-entry | 候选入场前 | Overloy freeze check： 'overloy_level 2 1° • 禁止新开 short-voL I SPEC-026 i
I Step7 1SPEC-017guards 25|Shock gatecheck (active mode) :postmaxcore budget MA /SPEC-025 |
I Step post-entry | 仓位建立后（每日收盘）|、overlay_1evel 2 2° 强制 trim；'overlay_level•4+ cnergency exit | SPEC-026 I原 Steps 1-6 不变，新出課攝入其前后。
## S8 历史性能基准 -更新
*  新增内容⋯：Overloy S-Version 对照表（基于 doily portfolfo metrics）
*  •全历史（2000-01-03 至 2026-03-31）*：
」配置 | Ann.Ret | Sharpe | Caimar | MoxDD | CVaR95 | 交易数|
EXP-baseline | 3.73x | 0.70 | 0.24 | -15.35% | -0.837% | 354 |
-0.835% | 331 |
EXP-freeze_trim | 4.25x | 0.85 | 6.34 | -12,38% |
-0.747% | 348 |
**EXP-fu11*• | **4,26%**
xexe-+ihedec.1.3:20x | 0786.93.10-12:591.-0802x1 333
・・圧力容口 MaxD0・*：
naa | 2011 | 2015 | 2020 | 2022 |
Baseline 1-2.78% 1
-2.13% |
EXP-ful1 i•-0.10%** 1
1.45|-5,59% |
-4.13% | -5.20% |
•变化说明⋯：旧版 58 仅有 trade-Leve1 指标 （26yr Sharpe 1.54），新阪增加 doily portfolto 对照表，两套指标井列顧示，
## 59 风险画像-更新
•交更项•：VIX 25+50 中理急升的保护状态
1 风险災型 | Before （2026-03-30） 1 After （2026-04-01）1
| VIX 25450 中轻物升|backwardatfon”帮分保护；•已开会位退出造度（缺日）••ISPEC-025 shock engine（预其门服）+SPEC-026 overiay L2 trin e/ （2015 改到
•新增项⋯：极速 溃（3-5 日 VIX 翻倍）
！风险 型|状态1
！ 极速崩溃（COVID 头型）
A 部分保护：3日窗口滞后：v2 计划 vix_accel_1d fast-path |
*•新增"已实施保护机制完整性“分类**（入场前/持合中/每日监控）
详见完黎文档 $9.
## 未变更项目
以下内容在 2026-03-30 -2026-04-01 送代中**未发生任何改动**：
|章节|内容|
--一------|
§2 信号体系（三维过滤）| VIX regime、IVR/IVP、趋势信号逻辑和阈值均不烧|
1 S3 決策短阵 |CANONICAL_MATRIX 不变
1 S4 六大策略参数|所有策略的 delta、DTE.haircut、出场规则（主动部分）均不烧|SS.1 基础參数| 9个原有參数值不变|
$5.2 BP 利用率| bp_target / bp_ceiling 不始|
1 $5.4 Vol Spel1 Throttle | spell_age_cop=30, max_trades_per_spe11=2 不班 |
1 Sharpe使用指南（SPEC-022）|统计不确定住分析和建议不变（新增 daily Sharpe 作为补充）！
S5.3 Portfolio Grcek 限制 | max_short_gamma_positions=3, synthetic IC b1ocK 涇辑不|
1策略 Grcek 密名速查 |全部 6条记录不疫！
Filter 复杂度协议（SPEC-021）| 准入门限和实证结论不变|
##下一步（截至2026-04-01）
**短期（v2， 待 PM 审批）**：
1.   L3 heage 实际实现 （Long put spread）：需新 SPEC,ChatGPT Revien 建议餘发
2.   vix_accel_1d"L4 fast-path:COVID 类极速前溃优化
3. overlay_mode b "disabled" ฿0%
•"active"：EXP-fu21 已验证，推荐生产部署
*  *中期（下一波研究优先级）**：
*  *Vo1 Persistence Modei•（senior quant review §5.2）：SPEC-024/825/026 基础设施已就绪，可推进信号设计
-多合引|擎：trim 精细化（按 shock 贡献排序平合）
# 追加 Delta:2026-04-01 - 2026-04-02
## 新增模块（5 个文件）
| 文件 | 模块内容 |对应 SPEC 1
backtest/attribution.py | compute_strategy_attribution) (11 )) . compute_regime_attribution) (871)
-| SPEC-028 |
*backtest/run_shock_analysis.py | Phase A shadow analysis: $Bt/regime hit rate, breach type Sis. percentile 3#s | SPEC-027 backtest/run_oos_validation.py _split()
_run_config) 53 (window metrics / overlay advantage / 00S AC / O05 strategy
attribution / 00S regime attribution) | SPEC-029 |
1backtest/run_trend_ablation.py backtest/run_trend_ablation.py | ablation ablation HER (EXP-baseline / EXP-atr/ EXP-persist / EXP-fu11) : RS-020-1 FAIL. SERESCO RS-020-2 1
SPEC-020|
1^backtest/research/SPEC02@_prereq_findings.md'| 57 前置研究结果：gap_sigma 分布、BEARISH streak 条件概密 | SPEC-020 57 |
## 52.3 炮势信号-更新
•*Before （2026-04-01）•：固定 +1% band， 单日
BEARISH 触发 trend_ flip.
**After （2026-04-02, SPEC-028，实施中）•：
| 改动| 内路|
| Entry Gate | ATR-Normalized: 'gap_sigma - (SPX-MA50)/ATR_close(14)*, BULLISH if ≥ +1.00 |
| Exit Filter | Persistence: jeR
*bearish_streak ≥ 3°
天才触发 trend_flip！
1 参数依据| 57 实证：ATR_THRESHOLD-1.6 （gap_s1gma 分布与原 Dand 最接近）。PERSISTENCE 从初始假设 5 修正为 3（条件製率拐点）！

**ATR 实现**：V1 使用收盘价差分近似（无需B1oomberg H/L）：v2 升级路径待数据就绪。
##§5 新增指标（SPEC-028）
**pn1_per_bp_day** #f#backtest/metrics_portfolio.py
pn]_per_bp_day = total_net_pn1 / I(daily_used_bp)
衡量每占用1 美元保证金1天的净收益，消除持仓时长对胜率的扭曲。
** BEARISH_PERSISTENCE_DAYS = 3"** #f#= signals/trend.py (SPEC-020) .
## 56 出场规则- 更新
！规则1 Befone（2026-04-01） 1 After （2026-04-62）
trend_flip | 持仓 ≥3天，当日 trend= BEARISH|持仓 ≥ 3天，**连续 bearish_streak ≥ 3 天**|
## 68 新增：00S 验证结果（SPEC-029）
！报表！內容|
1 R3 OOS AC #TS | Sharpe>e / MaxDD improvement25% / PnL retention285% / Trade drop≤15%, PASS/FAIL |
## SPEC 变更历史_新增
SPEC | 内容 | 状态|
SPEC-827 | Shock Engine Active Mode //: Phase A shadow analysis + A/B AC: any_breach_rate bug fix (Fast Path) / DONE 1
SPEC-028 | Capital efficiency (pnl_per_bp_day) + strategy/regime PnL atribution |~ DONE |
SPEC-029 | OS Validation IS=2000-2019 / 005-2020-2026:
5 reports; 9/9 tests | ~ DONE |
1 SPEC-026 （new） 1 ATR-Normalized Entry cate + Persistence Exit; 57 前置研究完成；RS-020-1 FATL （ablation 未完成）一待RS-020-2|日 进行中|
## 研究优先级- 更新
•新增已完成**：SPEC-027（Shock active mode 校住），SPEC-028 （Capital attribution）， SPEC-629 （00S val idation），SPX 趋勢信号源感研究（$39）、
*  *当前阻塞**：SPEC-020 RS-020-2 （AMP 修复 Pun_backtest toggle + 光龄 ablation）.
*  *下一波研究（SPEC-020 完成后）*：
| 优先级 | 任务 |
| P3 | Vol Persistence Model (senior quant review 55.2)
P4| Shock Active Mode 生产切换（SPEC-027 Phase B数据驱动决策）！
P5| ATR v2: Bloomberg H/L TIS ATR
P6| ADX 辅助确认（若 SPEC-620 005 仍有>20%误触发）|