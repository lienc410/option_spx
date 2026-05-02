# SPEC-074 简短版供 HC 复现类型 SPEC summary
适用 HC 同步实施 SPEC-074
原始文档 task
slash
SPEC-074 md
SPEC编号 SPEC-074
校验 SPEC-074（零七四）
状态 DONEPM决策日期
2026-04-27
关闭 0020
【一句话目标】
让MC的_backtest_select
不再使用简化决策矩阵而是 delegate
fl live select_strategy
保证 backtest
：选择和 1ive 推荐
完全一致
【为什么需要】
MC 的 _backtest_select 缺七个 gate
live select_strategy #
backtest 没有
具体缺的 gate 列表
第一个 BACKWARDATION filter
SO BPS_HVDO IC_HV aftermath
原因 MC 没有 term_structure
第二个 VIX_RISING gate
影响 BCS_HV bearish 路径

第三个 IVP63 大于等于 70 gate
影响 BCS_HV
第四个 IC IVP range filter
范围 二十 小于 ivp 小于 五十
第五个 DIAGONAL IV-high gate
来源 SPEC-051
第六个 DIAGONAL both-high gate
来源 SPEC-054
第七个 Aftermath bypass
Al backwardation retention
【已 documented 的差距证据】
WEIR SPEC-064 AC16 BELOW TARGET target aftermath IC_HV count
等于 二十二 加減 三
Cfull-history backtest m
MC 实际 measured 等于 五
差距巨大
证据二 Q036 reconstruction gap
MC # negative years
overlay-F 上的差异
MC recent baseline 正F 一九四八五六
HC 正E一六四九五八
gap 三万美金 in smaller account
【HC 实施需要五个组件】
组件一 VIX3M 历史数据 blocking dependencyHC 需要在 Bloomberg Windows
# data slash fetch_bbg_vix3m#py

回传
data
slash vix3m_historyÆesv
覆盖 2003-12-04 到 today
VIX3M inception # 2003-12-04
pre 2003
效据用 None
组件二 IVP63 helper function
#f# compute_iv_percentile_63d
计算当前 VIX
* trailing 63 trading day
历史分布的
percentile
可在 signals slash vix_regime点py 中
组件三
Full
snapshot construction
在 backtestengine 主循环中
每个 daily tick 需 build
完整的 VixSnapshot 含
vixillvix3mJlterm_structure
完整的 IVSnapshot 含
iv_percentile_252hDiv_percentile_63
Aliv_signal
完路的 TrendSnapshot 含
spxJlma2@0hltrend_signal
select_strategy delegation
格 _backtest_select（.•.）调用
strategy underlying rationale legs
等于 select_strategy（
vix_snap i_snap
trend_snap)
_backtest_select 2 backward compat
但 body 改为 delegation
组件五 测试 parity 验证
#it tests slash test_backtest_select_paritylipy
覆盖至少 二十 个手挑日期
范围 2008 加 2018 加 2020 加 2022
验证
backtest
selection
和 1ive
selection 充全一致
---|

|【关键代码改动文件】
backtest slash enginempy
主要改动 line 689-704
JD snapshot construction
tl delegation call
*_backtest_select(regime, iv, trend,...)
#ME select_strategy(vix_snap, iv_snap, trend_snap)
strategy slash selectorpy
不需要改
live select_strategy canonical
保持原状
backtest slash metrics_portfolio/py
不需要 SPEC-074改
但 SPEC-078 有改
屈于 dashboard metrics
，同步
signals slash vix_regimeSpy
#ft compute_iv_percentile_63d
和 term_structure classification 函数
data slash vix3m_historydicsv
新数据文件
HC 需要从 BBG 拉取
data slash fetch_bbg_vix3m/#py
新 fetcher
模式参考 data slash fetch_bbg_vix_ohlc点py
bin slash run_fetch_bbg_vix3m5.cmd
Windows launcher
模式参考其他 bin slash run_fetch_bbg_pattern点cmd
【验收标准 简化版 HC 复现关注】
关注一 Decision parity
测试通过
百分之九十九以上日期backtest 和 live 选同-
strategy

关注二 SPEC-064 AC10 对齐
aftermath IC_HV count
落任 HC target 二十二 加减 三 范围内
SPEC-074 实施前 MC等于五
SPEC-074 实施后 MC 等于二十五
PM it def b-original * canonical
ED net change in IC_HV position- IDs
四十 new 减十五 1ost等于加二十五 net
关注三 Zero
behavior regression
其他已
closed
SPECS 在 SPEC-074后
继续保持 directiona1 一致
PnL 变化小小于等于 五pp
Sharpe 变化小于等于 零点一零
MaxDD 变化小于等于 二十五pp
注意 Sharpe 和 MaxDD 是
PM amended
bounds 不是原 SPEC
关注四 0036 Phase 4 重新跑
overlay-F fire count
应该接近 HC 的二十三
MC 当前二十二
SPEC-074 后预期
converge

【关健数字汇总】
SPEC-064 AC10
target 二十二 加减三
pre SPEC-074I
post SPEC-074 加二十五 net 含义见上
AC5 amended bounds PnL:
变化阈值 五pp
Sharpe 变化阈值 零点一零
MaxDD 变化阈值 二十五pp
VIX3M data range
2003-12-04
到 today
inception # 2003-12-04
parity test 覆盖

*New Text Document (2).txt - Notepad
File Edit View
至少 二十 个手挑日期
分布在 2008 2018 2020 2022四个年份
下游影响
0036 ranking flip 发现
post SPEC-074 measurement T
F dominate IC non-V
即 IC_HV overlay-F 主导
胜过 IC non-HV
【范围外】
不在 SPEC-074 范围
position state evolution
已通过0022 对齐不在 SPEC-074 范围
leg construction conventions
已通过 SPEC-070 v2 对齐不在 SPEC-074 范围
BP 加 qty 处理
屈于 Q029加 Q033 dual-column reporting
不在 SPEC-074 范围
PARAM_MASTER 參数值
SPEC-074 不改任何參数
【实施顺序建议】
第一步 PM 在 BBG Windows
跑 fetch_bbg_vix3m 拿数据回MC后 HC同步 Csv
第二步 HC 实施 IVP63 helper
# term_structure helper
单元测试通过
第三步 HC 改 backtest engine
加 snapshot construction

加 delegation
第四步 HC 跑
parity test
覆盖二十个日期
确认百分之九十九以上一致第五步 HC跑
, full-history backtest
检查 SPEC-064 AC10
等于 二十二 加减三
第六步 HC 跑 closed SPEGs regression
确认 directional 一致amended bounds 内通过
第七步 HC 重跑
0036 Phase 4
ail overlay-Ffire count
接近 二十三
第八步 HC 重跑 3y backtest
tieout
回传 csv 给 MC
对比和 MC 收效度
【风险注意点】
风险一 VIX3M 早期数据流动性差
2003-2008段
VIX3M 数据可能稀疏
graceful fallback #J None
不影响 backward compat
风险二 IVP63 历史 compute 可能慢
建议 pre-compute 到 time series cache
类似 ivp252 已 cached 模式
风险三 closed
SPECS 可能 regress
方向性变化是 expected
绝对值变化在 amended bounds 内 OK
若超出
escalate to PM
风险四 Q036 数字可能 shift
这是预期的 SPEC 价值

不是问题
但需 PM看
ranking flip 是否影响决策
【完整 SPEC-074 全文位置】
详细推导和评审过程
A task slash SPEC-074md
其中含
problem statement 详细分析
* implementation plan
三轮 review 历史
V1 PASS-with-ADDENDUM 不可用
v2 三个 substantive FAIL
V3 PASS - PM
amendment
review verdict 文件
task slash RV-074-15md FAIL task slash RV-074-25md FAIL task slash RV-074-3-md PASS
数据 fetch handoff
task slash SPEC-074_data_fetch_handoff.5md
【HC 后续问题】
如 HC 在实施过程遇到任何不一致
可在 HC return 包中，按以下格式提出
不一致项编号
例如
D001
描述 一句话
建议解决方向 MC决策 或 HC自查
MC 会在下一轮handoff 回应

