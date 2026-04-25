# MC Handoff 2026-04-24
上次同步日期
2026-04-10
本次MC工作期
2026-04-11
到 2026-04-24
本期是长周期MC工作期
共跨度14天
包含多条SPEC链路和多轮ChatGPT评审
【本期摘要】
第一条 完成aftermath研究主线
从Q018双峰漏抓一路推进到
SPEC-071 V3-A broken-wing IC
中间涉及5个SPEC和7轮ChatGPT评审第二条 发现两类live与backtest偏差
Q029发现engine硬编码qty等于1
忽略selector的SizeTier
导致36百分比HIGH_VOL交易在live
执行是1张XSP约10倍notional差异
Q019发现close口径VIX与1ive的open
口径在4点6百分比天数触发
aftermath结果不同
第三条 沉淀四条CLAUDE点md治理规则加一条B1oomberg的windows调用规范
blocking AC漏报默认FAILPASS with ADDENDUM仅一次例外
handoff强制research与1ive两列
aftermath类SPEC必须全引擎验证
【当前状态快照】
当前推荐生产配置
overlay_mode等于disabledshock_mode等于shadow
use_atr_trend#FTrue
bearish_persistence_days等于1
AFTERMATH_OFF_PEAK_PCT等于需点10
IC_HV_MAX_CONCURRENT等于2
aftermath#JIC_HV
1ong_Ca11_delta等于客点04
1ong_put_delta等于零点08
DTE等于45保持不变

当前最高优先阻塞
slash ES runtime
尚未有Spec
safeguards
对应Q013
当前PARAM_MASTER版本号v3
本期有多条参数变更
见【参数变更】节
【参数变更】
参数名 AFTERMATH_OFF_PEAK_PCT
旧值 零点05
新值 零点10
来源SPEC SPEC-066
原因 Q018 Phase 2-D
cap sweep结论
HC7E2026-04-20 ship
MC在2026-04-21同步
参数名
IC_H_MAX_CONCURRENT
旧值 1
新值 2
来源SPEC SPEC-066
原因 Q018双峰aftermath第二峰捕获
HC在2026-04-20
MC7E0022 Phase
ship
2026-04-21完成
2激活cap等于2
参数名 hv_spell_trade_count
旧值 单scalar计数新值 pen-strategvdict计数
来源SPEC SPEC-068
原因
2026-03双峰HV spell aggregate
超过max_trades_per_spel1等于2
阻挡aftermath IC_HV第二笔
改为按策略key独立计数
参数名 engine的_build_legs的IC长腿构造日值 wing-based即sp减50
delta-based即使用1ong_d delta查询
来源SPEC SPEC-070 v2
原因 SPEC-070 V1 FAIL
selector fedelta-based enginefwing-based
两侧约定不一致
导致2018年后高SPX环境下
SPEC-070 VI的Ip从零点06到零点08

反而把11个aftermath事件的1p
移得更远OTM
v2对齐两侧语义
参数名 aftermath的IC_HV 1ong
旧值 零点06
新值 客点04
来源SPEC SPEC-071
原因 Q028三阶段研究加R6评审
broken-wing IC比对称IC在aftermathtail protection更好
V3-A)ycompromise candidate
V3-C的1c等于零点03留作0032监控
参数名 aftermath的IC_HV 1ong put delta
旧值 客点06
新值 客点08
来源SPEC SPEC-071
原因 同上
broken-wing配对的put侧
参数名 BEAR_CALL_DIAGONAL
旧值 存在于StrategyName enum
新值 从整个代码库删除
来源SPEC SPEC-073
原因 Q030 dead code cleanupselector从未emit该StrategyName
6个生产文件加1个审计脚本
加5份文档清理
【SPEC决策】
SPEC编号
SPEC-066
校验 SPEC-066（零六六）
新状态 DONE
PM决策日期2026-04-20
备注 HC通过Q018
2-D cap sweep
选定cap等于2加OFF_PEAK等于零点10
MC在2026-04-21已同步F1常量
SPEC编号 SPEC-068
校验 SPEC-068（雾六八）
新状态 DONEPM决策日期
备注 per-strategy spell
throttle
解决2026-03第二峰漏抓
含5项unittest全PASS

SPEC编号 SPEC-069
校验 SPEC-069（零六九）
新状态 DONE
PM决策日期 2026-04-22
备注 open-at-end未平仓持仓在UI显示橙色OPEN badge
加artifact字段open_at_end
147 tests全通过
SPEC编号 SPEC-070 V1
校验 SPEC-070（零七零）v1
新状态 FAIL然后SUPERSEDEDPM决策日期2026-04-22批准
2026-04-23 Review FAIL
备注 V1试图把aftermath
IC_HV的1p从零点06改到零点08
Review发现selecton与engine约定不一致（delta vs wing）
11个2018年后事件反方向移动1p
被v2替代
SPEC编号 SPEC-070 V2
校验 SPEC-070（零七零）v2
新状态 DONE with PASS加ADDENDUMPM决策日期 2026-04-23
备注v2只做engine对齐不做v1的W shift
全引擎验证通过
首次且唯一的PASS加ADDENDUM例外
SPEC编号 SPEC-071
校验 SPEC-071（寄七一）新状态 DONE
PM决策日期 2026-04-23 APPROVED
Review #1 FAIL*handoff v2
Review #2 PASS
ESPEC-071 addendum on 2026-04-24
* ftermath broken-wing IC
V3-A即1c零点04加1p点08
DTE等于45不变
R6 compromise选V3-A而非V3-C
因为V3-C的lc需点03有1iquidity concern
V3-c 进入Q032 monitor-revisit
SPEC编号 SPEC-072
校验 SPEC-072（零七二）
新状态 MC侧DONE
PM决策日期2026-04-24
# frontend dual-scale display
hbroken-wing visual highlight

单文件web slash html slash spx_strat点html
不动backend
AC10 live smoke test pending HC deploy
SPEC编号 SPEC-073
校验 SPEC-073（零七三）
新状态 DONE
PM决策日期 2026-04-24
** BEAR_CALL_DIAGONAL dead-code cleanup
6生产文件加1审计脚本加5文档
零behavior变化
154 tests全通过
SPEC编号 SPEC-067
校验 SPEC-067（零六七）
新状态 DRAFT
备注 ES runtime safeguards
等AMP实施对应B1阻塞项
【研究发现】
发现编号 F001
内容 aftermath IC_HV替换方向被证伪
Q025两轮评审驳回
BPS_HV own-exit
Bull Call Spread
LEAP 1ong ca11三个替换方向依据 Q925 ful1 universe研究相关SPEC SPEC-071
发现编号 F002
内容 IC-family结构选择
Q026确认broken-wing优于
richer wingfl5th-leg tail put
依据 Q026三阶段研究
相关SPEC SPEC-071
发现编号 F003
内容 selector与engine的IC长腿约定长期不一致是历史遗留问题不是SPEC-070 V1引入
Q027 narrow audit显示
10策略乘3 era乘23 legs
全部零mismatch除IC_HV外依据
Q027 audit脚本
相关SPEC SPEC-070 v2

发现编号 F004
内容 engine硬编码qty等于1
忽略selector的SizeTier
36百分比HIGH_VOL交易在live
是1 XSP约1比10 SPX notionalengine当1 SPX模拟
导致所有aftermath研究的magnitude约10倍高估1ive实际依据 0029 5-dim parity audit
相关SPEC 无
产出Q033
Option BilE resolution
发现编号
F005
内容 BS simaftermath研究两次systematic over-predict
SPEC-071 sim/l1861 vs engine/D115
约16倍over
Q031 sim DTE等于60优
sign inverted
依据 SPEC-071和Q031对比相关SPEC 无
产出CLAUDE点md新规则
aftermath类SPEC必须全引擎验证
发现编号 F006
M close-based VIX5 open-based VIX
在4点63百分比天数触发aftermath
结果不同
regime层9点71百分比天数不同
trend层31点54百分比天数不同
319个aftermath flip中
179个close是False开open是True
即backtest漏抓1ive信号
140个相反
依据 Q019 Phase 1全27年BBG OHLC分析相关SPEC SPEC-064 SPEC-066
SPEC-068 SPEC-070
V2 SPEC-071
PM决策待定A或B或C
发现编号 F007
内容 SPEC-066 shipping后
2A-lite retrospectiveli
EXTREME_VOL hard stop
已经mitigate 2008年GFC假设tail
Phase 1 Variant A预期的2008-09负7968单笔损失在整合stack下不materialize
依据 Q018 R8 retrospective
2A-litehn2C-lite

相关SPEC SPEC-066
【策略逻辑变更】
变更项 aftermath IC_HV入场结构
旧逻辑
对称IC即1c需点06加1p零点06
新逻辑 broken-wing即1c零点04加1p零点08仅在aftermath场景生效相关SPEC SPEC-071
IC_HV concurrency cap
旧逻辑 硬编码1槽位
新逻辑 cap等于2
即在aftermath场景下
允许最多2笔IC_HV并发
相关SPEC SPEC-066和Q022
变更项
HV spell throttle
旧逻辑 aggregate计f数所有HV策略共享spell budget
新逻辑 per-strategy dict计数每个HV策略独立spel1 budget
相关SPEC SPEC-068
变更项
旧逻辑
engine IC长腿构造约定
wing-based即sp减50
新逻辑
delta-based即1ong_d delta查询
对齐selector
相关SPEC SPEC-070 V2
变更项 策略目录
旧逻辑 包含BEAR_CALL_DIAGONAL
即8个策略
新逻辑 移除BEAR_CALL_DIAGONAL
仅7个有效策略
BEAR_CALL_DIAGONAL从未被selector emit
dead code cleanup
相关SPEC SPEC-073
【开放问题更新】
问题编号 Q017
新状态 resolved via SPEC-064
问题编号 Q018
新状态 CLOSED
2026-04-24

结论 resolved
in production via
SPEC-066加Q022加SPEC-068
R8 retrospective validation完成
2A-lite EXTREME_VOLEmitigate tail
2C-lite OFF_PEAK等于客点10
stable plateau
含6条显式reopen triggers
问题编号 Q020
新状态 open低优先内容 MC
backtest_select简化
导致SPEC-064 AC10数量偏少
HC目标22加减3
MC实测5
非bug是measurement gap
根因MC缺VixTermstructure等历史上下文问题编号 Q021
新状态 open research only
内容 SPEC-066 alpha）日因
distinct second-peak语义
vs back-to-back
re-entry
HC原提內Q020
MC端已占用Q020编号
故HC问题重编号为Q021
问题编号 Q022
新状态 resolved 2026-04-21
结论 MC backtest engine
单仓位到多仓位架构重构完成
三阶段交付
Phase 1 fingerprint一致
Phase 2 cap等于2激活
Phase 3 139 tests全通过
问题编号 Q023
新状态 resolved 2026-04-22
结论 multi-position后风险画像
27年数据无新风险模式
MaxDD加75百分比是trade count缩放
接受现状
问题编号 Q024
新状态 resolved 2026-04-22
结论 aftermath false-positive
过滤研究 NULL RESULT
现SPEC-066内槛已过滤
peak_10d小于28的1egacy
SPX stabilization filter backfire

问题编号 Q025
新状态 resolved
2026-04-22
结论 aftermath下BPS_HV
Bull Call Spread LEAP
三个替换方向全证伪
IC加tail put变体在部分场景强
但依赖legacy artifact
ChatGPT
R3驳回
DEFERRED到0026
问题编号 Q026
新状态 resolved
2026-04-22
结论 IC-family对比
wEDricher wing dominate TE5-leg tail
2nd Quant endorse A加C路径产出SPEC-071候选
问题编号 Q027
新状态 CLOSED NULL 2026-04-23
narrow scope
it convention-layer leg-builder audit
10策略乘3 era乘23 legs全需mismatch
SPEC-070 v2是最后一个历史约定错配
ChatGPT R5要求不能1abel为
systemic audit complete
1XEleg-construction convention audit
未审5维度归0029
问题编号 Q028
新状态 resolved 2026-04-23
结论 aftermath tail protection
在aligned baseline下重研究
broken-wing IC family dominate
产出SPEC-071候选
问题编号Q029
新状态 CLOSED 2026-04-24
结论 其他5 parity维度audit
41 no issuesiminor drift
1个material
engine硬编码qty等于1
忽略SizeTier
触发Q033加Q034 fo11ow-uP
问题编号
- Q030
新状态 CLOSED Via SPEC-073
2026-04-24
HiE BEAR_CALL_DIAGONAL dead code
cleanup完成

问题编号
0031
新状态
CLOSED NULL 2026-04-24
结论 aftermath IC_HV DTE等于60
full-engine驳回0028 Phase
BS
sim的DTE等于60优势预期
system Sharpe负零点005
wonst single 2点2倍恶化
第2次BS
sim over-prediction pattern
问题编号 0032
新状态 open monitoring only
内容 V3-C 1c等于零点03的monitor-and-revisit候选
SPEC-071落地后观察前5到10笔live aftermath
若V3-A worst改善达标
且1c零点03 liquidity良好考虑升级到SPEC-073级别的V3-C
问题编号 Q933
新状态 CLOSED
结论 SizeTier到Contract Qty
ChatGPT R7裁决
engine保持1-SPX uniform不改代码
强制所有handoff SPEC RDD加
research_1spx与1ive_scaled_est两列
HIGH_VOL SMALL tier乘零点1
FULL tierie2
XJSPEC-071/live-scale addendum
问题编号 Q034
新状态
open
optional
low priority
内容 strike
rounding#slash 5 grid
engine当前round到int
live#|slash 5
最多加减2点5点漂移
Xiprecision execution matching
才material
问题编号 Q035
新状态 open long-term
* future live-scale backtest engine architecture RDD
若未来希望engine直出1ive-scale数字
而非research scale乘1ive_factor换算需要完整架构重写
R7建议defer

问題编号 Q019
新状态 Phase 1 complete decision DEFERRED
内容 close vs open based VIX日往
27年全期BBG OHLC分析完成
aftermath层4点63百分比flipregime层9点71百分比flip
三个PM决策选项A或B或C待定
Claude倾向A加C组合
【Master Doc影响清单】
PARAM_MASTER需要更新 yes
多条参数变更见上述版本号v2到v3
open_questions需要更新 yes
Q018 Q022 Q023 Q024 Q025
Q026 Q027 Q028 Q029
Q030
Q031
Q033全部CLOSED
{019
DEFERRED
Q020
Q921新开
Q032
Q034 Q035新升
strategy_status需要更新 yesaftermath IC_HV结构改为broken-wingconcurrency cap等于2
spell throttle per-strategy
research_notes需要更新 yes
本期7条研究荣目
doc slash RESEARCH_LOGmd
日期2026-04-24的条目
SPEC状态需要更新 yes
SPEC-066 DONE SPEC-068 DONE SPEC-069 DONE
SPEC-070 V2 DONE
SPEC-071 DONEDDaddendum
SPEC-072 MCDONE
SPEC-073 DONE
【HC指令】
指令1 确认SPEC-066参数

AFTERMATH_OFF_PEAK_PCT等于零点10
与MC端同步
HC是源头
MC在2026-04-21已同步
指令2确认SPEC-071的broken-wing
在live selector输出中
aftermath路径返回的leg
Ic delta等于零点04
1p delta等于零点e8
short callishort put delta
保持零点12不变
DTE等于45不变
指命3部署SPEC-072 frontend
单文件web slash html slash spx_strat点html
#task slash SPEC-072_deploy_handofflimd
含5个smoke test场景需要HC在old Ain部署后
live smoke test
AC10为HC侧验证
指命4 留意0019 Phase 1发现
319 Taftermath flip over 27 years
SPEC-064 SPEC-066 SPEC-068
SPEC-070 V2 SPEC-071全基于
close-based VIX做决策
若PM决定洗A或B或C
会有后续指命
指令5 接收并整合CLAUDE点md
四条新governance规则
blocking ACiEFAIL
PASS with ADDENDUM一次例外
handoff lreporting
aftermath SPEC必须全引擎
B*Bloomberg Windows launcher pattern
指令6 0033 Option B加E resolution
未来所有涉及PnL worst
SeqMaxD BP#handoff SPEC RDD
必须含research_1spx和live_scaled_est
两列数字
aftermath HIGH_VOL默认scale乘零点1
【不要推断的项目】
项目1 9019 Phase 1 PM决策

PM推迟了A或B或C的选择
HC不要自行假设
Claude倾向A加C组合但最终要等PM拍板
项目2 SPEC-067 ESruntime safeguards
PM尚未有DRAFT
HC不要自行起草Spec
可提醒PM这是top blocker B1
项目3 Q032 V3-C升级时机
需要HC 1ive累积5到10笔aftermath后才能触发评估
HC不要过早自行升级到V3-C
miE4 0035 future live-scale engine
是long-term watch项
HC不要自行启动
仅当R7 Option E的dual-column
体验不佳触发PM决定时才考虑
【下周MC计划】
计划1 等PM决定0019 A或B或C
若A 写RDD-0019
CLOSE
若B Phase 2重跑SPEC-066和SPEC-071
关键sample的open-based reproduction
若C加CLAUDE点md
aftermath
双口径sensitivity规则
计划2 SPEC-067 ES runtime
safeguards
若PM批准起草
Claude协助写DRAFT Spec
最小范围是stop条件系统监控
hibot alert
计划3 接收HC Return包
整合SPEC-066加SPEC-068加SPEC-069
加SPEC-070 v2加SPEC-071加SPEC-072加SPEC-073的HC侧状态
确认MC端参数与HC端PARAM_MASTER
一致无漂移
计划4 继续监控Q032
V3-C monitor-revisit触发条件
5到10笔live aftermath
计划5 若HC做了SPEC-072部署

与claude review AC10 live smoke test结果