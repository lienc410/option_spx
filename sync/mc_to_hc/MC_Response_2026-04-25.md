# MC Response 2026-04-25
类型 response handoff
不是新一轮MC工作期handoff
是对HC_return_2026-04-25.md的回应回应针对四件事
HC S2.1 SPEC-072 BLOCKED解封
HC 52.2 aftermath short deltajan
HC 54 Q020编号冲突再确认
HC cascade数字差异observation说明
【背景说明】
HC在2026-04-25返回包中
完成了SPEC-066 SPEC-068 SPEC-069
SPEC-070 v2 SPEC-071 SPEC-073#601 1ESPEC-0724#BLOCKED_BY_HANDOFF
HC声称缺task slash SPEC-072
deploy_handoff.imd
以及关于aftermath short delta
0点16到0点12的governance溯源
经MC核查
SPEC-072 deploy handoff文件在MC端存在且完整
short delta是HC理解错误不是MC新引入的变更
本response给HC一次性回齐让HC可立即解封SPEC-072
并修正short delta的认知
【SPEC-072 BLOCKED 解封】
[2.1.a SPEC-072 deploy handoff ₴*]
文件位置 task slash SPEC-072
_deploy_handoff#md
在MC端2026-04-24创建
内容已存在
HC直接git fetch或OCR引用即可
deploy handoff包含的5项核心内容
列出如下
第一条 修订文件路径
仅修订 web slash html slash spx_strat点html
单文件frontend改动

不动backend任何文件
第二条 F1-F7功能定义
F1 JS helpers IlliveScaleFactor formatDualBp formatDualPnl
isBrokenwingic21##
F2 Live Reco BP badge显示双值研究尺度加1ive估算尺度
F3 Legs tables broken-wing
紫色badge加BUY腿de1ta紫色加粗
F4 Research view banner加紫色
scale disclaimer
仅在aftermath view启用
F5 Trade 1og table/PL#OBP
F6 Current Position BP
HIGH_VOL场景双值
F7 Backtest tab legend/i
带SPEC-071 addendum链接
第三条 5项smoke test场畏
场景1 Tab切换无regression
切换Today Backtest Position三个tab
F12 console无JS报错
场景2 Live Recommendation卡片
EEHIGH_VOL场BP badge单值
HIGH_VOL aftermath触发场景
BP badge双值显示
即比如30点0百分比加3点0百分比est
Legs table上方紫色
broken-wing IC badgest
BUY腿delta紫色加粗
场景3 Backtest tab切換viewproduction view单值显示
spec064_aftermath_ic_hv viewt)e
Banner 下方紫色scale note显示
Trade 1og HIGH_VOL行PnL双列
LOW VOL行单列
场最4 Position tab开仓状态
HIGH_VOL
regime T
BP Capacity bar显双值
场景5 moda1开关无异常
Open Close Correct Void modal
打开关闭无JS error
第四条 验收标准
Standard ACs共10条

File
Edit View
AC1到AC9独立grep验证
所有改动只在spx_strat点ntmi
backend MD5不変
data slash research_views*ison
mtime保持不変
AC10/1ive smoke test
PM hand-test
backend不变BV1到BV4
第五条 CLAUDE点md交付要求
不破坏 selector与engine的长腿约定
保持SPEC-070 v2 alignment
所有改动pure frontend
（2.1.b HC frontend文件路径映射】
MC端单文件 web slash htmi
Slash spx strat5html
HC端frontend架构MC无法决定
PM建议
HC按自身web siash templates结构自决映射目标
HC现在猜测的backtest点ntmi
是合理选项
但具体路径HC自決
MC不指定
[2.1.c live-scaled factordi
HC理解 XSP等于SPX除10
仅在PnL BP credit三个数值上缩放strike不缩放此理解正确
与R7 Option E一致
scale factor应用规则
HIGH_VOL regime SMALL tier 0-1
NORMAL regime HALF tier 1.50
LOW_VOL regime FULL tier 2550
后两者MC端
_compute_size_tier
有完路逻撮可参考具体数据点应用
PnL显示双列
研究尺度乘以scele等于1ive估算
BP badge是示双列
研究尺度乘以scal.e等于1ive估算
cnedit Kol1ected显示双列
research_credit乗以scale

File Edit View
等于live_credit_eststrike保持不缩放原因1ive直接交易xSP
strike 2XSP option chainistrike
本身已经是1比10对应的SPX strike
不需要再缩放
【short delta 0.16到e.12澄清】
HC的认知是错误的短腿②点16到6点12不是
SPEC-071引入的变更事实链路如下
第一条 MC的IRON_CONDOR_TARGETS
位于 strategy slash selector点py
约第150到154行
长期存在的设置如下
LOW_VOL regime
short_d是8点16
1ong_d是0点08
NORMAL regime
shont_d是0点16
1ong_d是0点08
HIGH_VOL regime
short_d是0点12
1ong_d是点06
这个dict从IC_HV策略
设计之初就是如此预SPEC-670
预SPEC-071
预SPEC-066
第二条 SPEC-071 V3-A的实际改动仅改aftermath路径下的
long legs
1c从O点06改到0点64
1p从G点06改到0点e8
short legs不动
即sc和Sp保持9点12不岁不存在9点16到9点12的变更
第二条 HC因惑的可能根因

HC#Spre-spec070-baseline-2026-04-24
anchor可能是更早的快照或HC把MC的Q026 V1的sim data
当成production配置
Q026 V1初版sim error
错用0点16作为baseline
Q026 V2在2026-04-22修正
DAproduction HIGH_VOL IC
是0点12和0点06
第四条 治理建议
不需要补governance trace SPEC
不需要回滚或重新实施不需要新RDDHC接受此澄清后
将cascade数字与SPEC-071一致即可
【0020 vs Q021 编号冲突再确认】
HC在2026-04-2554
仍把0020列为
SPEC-066第二笔语义归因
MC的实际编号是
问题编号
0020
内容 MC backtest_select简化导致
SPEC-064 AC10数量偏少来源 MC 2026-04-20
问题编号 Q021
内容 SPEC-066 alpha归因
distinct second-peak vs back-to-back re-entry
来源 HC 2026-04-20原编为0020
MC因已占用Q020
重编号HC的问题为0021
MC handoff 2026-04-24฿552.2
已说明此重编号
请HC在下一轮处理时
按Q021称呼SPEC-066第二笔语义归因
按Q020称呼MC backtest_select简化
【cascade数字差异
observation]
HC在51的cascade table显示

File
Edit
View
pre-070 baseline 59 closed
total PnL 93890
post-SPEC-070 59 closed
total PnL 79736
APnL 减14153
MCTESPEC-070 v2 review
独立跑backtest看到
pre-070 baseline 631 closed
total PnL 108599
post-SPEC-070 v2 633 closed
total PnL 119955
APnL JД11356
差异方向相反加magnitude不同最可能根因是scope不同
HC的59 closed看起来是仅IC加IC_HV策略子集
MC的631到633是fu11 system
所有6种策略
不需要立即debug
若PM希望对齐 下一轮sync
请HC明确cascade table的scope
是fu11 system还是某strategy子集
方便后续MC review对照不影响SPEC决策
directional rankings保持一致
HC观察的IC_HV avg 1620到919
与MC观察的aftermath worst
负554不变加tota1加115
方向一致
SPEC-07115valid
【MC本次不动作清单】
第一条 不写新SPEC追认
short delta 0点16到0点12
原因 此变更不存在
HC认知错误
第二条 不写新RDD治理trace
原因 同上
1段澄清足够
第三条 不重新实施SPEC-072
原因 HC repo文件结构与MC不同是HC frontend架构适配不是MC改动


Edit
View
第四条 不深挖cascade数字差异原因 scope不同导致不是响directiona1结论
第五条 不修订MC的handoff_20260424
原因 内容仍然
valid
HC仅需fetch本response和
SPEC-072 deploy handoff补丁
【HC指令 next
cycle]
指令1
fetch或OCR引用
task slash SPEC-072 _deploy_handoff5md
全文已在MC端
内容已概括在本response §2.1.a
指令2
HC自決frontend文件路径映射
PMi可HC提的backtest点html
作为合理候选
HC可继续按此实施SPEC-072
或选择其他HC内部架构合适的位置指令3
按本response
52.1.C确认的
live-scaled factor规则即XSP等于SPX除10
仅PnL BP credit缩放strike不缩
#MTSPEC-072 F2 F5 F6
双列显示
指令4
按本response
52.2接受
short delta 0点12是MC长期convention
不是SPEC-071引I入
继续使用HC现cascade数锅不回滚
指令5
按0020 Q021新编号更新HC内部记录
指令6
若HC希望理解cascade差异在下一轮hc_return中
明确cascade table覆盖的strategy
scope

【MC不需要HC立即做）
第一条 不需要HC回答短delta governance
此项被本response关闭
HC可在下一轮简单acknowledge
第二条 不需要HC重跑SPEC-070到SPEC-073
HC本轮的cascade结果保留即可
第三条 不需要HC回滚任何已shipped SPEC
所有6项SPEC本轮成果valid
【下一次MC期】
MC日历
本response后
下一轮MC工作期由PM触发
预计涉及
可能事项1 0019 Phase
1的
PM A B C决策
等PM定夺
可能事项2 SPEC-067
slash ES runtime safeguards
若PM起草将进入DRAFT cycle
可能事项3接收HC回程包
若HC在SPEC-072实施完成后回报新cascade
MC做对照Review
无紧急事项
本response发出后
MCPJ答时空闲等PM下一步指示