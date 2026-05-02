# MC Handoff 2026-05-01
上次同步日期
2026-04-26
本次MC工作期
2026-04-27
到 2026-05-01
本期周期5天
集中度高
完成7个SPEC和3个研究0
Q038研究弧从问题到落地走完
【本期摘要】
第一条 SPEC-074完成
MC的backtest_select现在delegate到
live#select
_strategy
全保真度对齐
封闭Q020
ROE测量准确度基础设施交付
第二条 Q036 capitalallocation主线落地
PM洗择Option二ESCALATE
Overlay-F sglt2全产品化栈完成
SPEC-075核心逻辑加SPEC-076监控复盘
productization前提一到五全闭环第三条 0037 broad rule audit发现
profit target从零点五零改为零点六零比Overlay F强五到七倍ROE杠杆
SPEC-077当日入产品
第四条 Q938研究弧完整走完
BCD comfortable top模式发现经过两轮ChatGPT评审
SPEC-079入场过滤加SPEC-080止损收紧
组合V5b全栈落地
第五条 dashboard metrics统一
SPEC-078把portfolio metrics唯一权威化解决5y回测PM看到的数字不一致问题第六条 三个治理性收获
trade-1ist反事实系统性低估filter价值
ChatGPT review在SPEC-079阻挡了次优配置
Phase 2C发现V5的stop参数不是最优
【当前状态快照】

当前推荐生产配置
profit target等于零点六零
overlay f mode# Fdisabled bed comfort filter mode#Tdisabled bed stop tightening mode#Fisabled
use atr trend#FTrue
AFTERMATH OFF PEAK PCT等于零点10
IC HV MAX CONCURRENT* T2
long cal1 delta等于零点04
DTE等于45保持不变
当前最高优先阻塞
slash ES runtime safeguards
尚未有Spec
应0013
当前PARAM MASTER版本号 V4
本期升级原因
新增三个toggle参数
profit target从零点五零升级到零点六需本期有多条参数变更
见【参数变更】节
---
【参数变更】
参数名
profit target
新值 零点六零
来源SPEC SPEC-077
校验 SPEC-077（零七七）
原因 Q037 Phase 2A发现全样本加零点九一到一点零三pprecent加零点二三到寄点三一ppSharpe fu11一点零一六到一点一四六
参数名 overlay f mode
旧值 不存在新值 disabled
来源SPEC SPEC-075
校验
SPEC-075（零七五）
原因
#overlay-F sglt2
capital allocation overlay
默认禁用等PM手动shadow

参数名 bcd comfort filter mode
旧值 不存在新值 disabled
来源SPEC SPEC-079
校验 SPEC-079（零七九）
原因 新增BCD comfontable top
入场过滤
默认禁用等PM手动shadow
参数名 bcd stop tightening mode
旧值 不存在新值 disabled
来源SPEC SPEC-080
校验 SPEC-080（零八零）
原因 新燴BCD止损收紧
debit stop loss从零点五零到零点三五
仅BCD
默认禁用等PM手动shadow
参数名 stop mult
旧值 隐式硬编码二点零
新值 显式参数二点零
来源SPEC SPEC-077附带
校验 SPEC-077（零七七）
原因 governance fix
StrategyParams字段已存在但engine未读现已wire通
【SPEC决策】
SPEC编号
SPEC-074
校验 SPEC-074（客七四）
新状杰 DONE
PM决策日期 2026-04-27
经过3次Review attemptv=PASS全部AC验证通过
0020关闭
0036 ranking flip发现
F dominate IC non HV
under SPEC 074 aligned measurement
SPEC编号 SPEC-075
校验 SPEC-075（客七五）
新状态 DONE
PM决策日期 2026-04-28
2RReview attempt
V—AC6 schema缺失

v二修复后通过
ann roe full sample
从十一点七八九到十三点一五九加一点三七一pp
Sharpe一点一零六到一点二零零
fires等于38
Convention flag非阻塞
live scaled est pnl不应用tier
scale
仍为reporting layer职责
校验 SPEC-076（零七六）
新状态 DONE
PM决策日期 2026-04-29
V一三个blocking bug
v二全修复加同日dedup加n4 parity
shadow JSONL 1og加alert文件
加dashboard F乘二badge
加rec card overlay面板
加quarterly review protocol文栏
SPEC编号 SPEC-077
校验 SPEC-077（零七七）
新状态 DONE
PM決策日期 2026-04-28
1XReview PASS
profit target常数升级
StrategyParams wiring stop mult companion fix
ann roe等于十一点七八九pp
SPEC编号
SPEC-078
校验 SPEC-078（零七八）
新状态 DONE
PM決策日期
1*Review PASS
dashboard metrics唯一枚威化
为单一source of truthdashboard JS退化为纯展示
P12 Fast Path后续修复
SPEC编号
SPEC-079
校验 SPEC-079（零七九）
新状态 DONE
PM決策日期
2026-04-29
2次Review
attempt

v一两个blocking bug
numpy boo1 JSON序列化静默失败
10g cal1架构错位
V二全修复
BCD comfortable top入场过滤
scoreEskip
単toggle
split toggle
详见v5b说明
ready命名
校验 SPEC-080（零八零）
新状态 DONE
PM決策日期 2026-04-29
1次Review PASS加非阻塞架构flag
Fast Path option B已修复架构flag
BCD debit stop 1oss从零点五零到零点三五
toggle bed stop tightening mode
与SPEC-079独立可切換
1og文件分engine和live source
【研究发现】
发现编号 F-26-04-29-1
内容 BCD comfortable top入场模式
跨13年top+worst 1osses十比十命中
fingerprint等于VIX在十三到十五
加SPX距30日新高小于等于负一加pct MA50大于一点五pp
依据 0038 walk-forward验证
1999到2018独立学到的filter
完美捕获2024到2025三个00S大亏
相关SPEC SPEC-079
校验 SPEC-079（雾七九）
内容 trade-1ist反事实系统性低估
原汁算rejected set EV近零
full engine irejected set
实际为正贡献
21笔BCD reject带来正一万三千六百九十五
fallback strategy slot
DABP cascadeJlconcurrency caps
都未在trade-1ist计算中建模

ChatGPT 2nd Quant Review 55
相关SPEC SPEC-079加SPEC-080
校验 SPEC-079零七九加SPEC-080零八零
发现编号 F-26-04-29-3
内容 VS的stop参数零点三零不是最优真正plateau中心是雾点三五
ann roe十三点五九vs十三点二三
Sharpe一点四零七vs一点三五五
依据 Q038 Phase 2C
11 configs sensitivity sweep
ChatGPT 3rd Quant Review §4 blocking
要求sensitivity sweep
找到次优fitting
相关SPEC SPEC-080
校验 SPEC-080（零八零）
发现编号 F-26-04-29-4
内容 profit tanget零点六零是优势点
零点五零到零点六零inflection
雾点五五到雾点六雾加雾点五三pp
雾点六零到零点六五加零点二六pp
雾点六雾之后递减明显
MaxDD和stop loss count不变零点六五候选deferred
依据 0037 BC1扫描
五点零零五五六零六五七努
相关SPEC SPEC-077
校验 SPEC-077（零七七）
【策略逻辑变更】
变更项 backtest selector
旧运辑
_backtest_select用简化矩降
FiAVIX3M term structure
不读IVP63
TIVR IVP divergence checks
新逻辑_backtest_select delegate到
liveRselect_strategy
完整保真度对茶
含VIX3M term加IVP63加divergence
相关SPEC SPEC-074
校验 SPEC-074（零七四）
变更项 BCD entry filter
旧逻辑 LOW VOL加BULLISH
直接返回BULL
CALL DIAGONAL
新逻辑 加可选comfortable top过滤

当bcd comfort filter mode等于active
且risk score等于三时返回REDUCE WAIT而非BCD
相关SPEC SPEC-079
校验 SPEC-079（零七九）
旧逻辑 所有debit策略统一
DEBIT STOP LOSS RATIO等于负零点五零
新逻辑 仅BCD当
bed stop tightening mode#Factive
debit stop loss改为负零点三五
其他debit策略不变
其他debit策略包括BULL CALL SPREAD
校验 SPEC-080（零八零）
变更项 Overlay-F capital allocation
新逻辑 IC HV入场时若三条件成立
idle BP大于等于七零pp
加VIX小于三零
加pre existing sG count小于二则position size翻倍默认禁用等PM手动shadow
相关SPEC SPEC-075
校验 SPEC-075（零七五）
dashboard metrics rendering
旧逻辑 dashboard JS本地重算
sharpeffsart 12
ann roe用totalpn1除十万除years
新逻辑 API返回portfolio metrics字段
dashboard JS只读pm点ann roe
pmAdaily sharpe pmmax dd dollar*
相关SPEC SPEC-078
校验 SPEC-078（零七八）
【开放问题更新】
问题编号
Q020
新状态 pesolved
结论
SPEC-074 DONE
MC backtest select完全对齐live
select strategy

问题编号
Q036
新状态 resolved
结论 PM选Option二ESCALATE
SPEC-075核心逻辑加SPEC-076
监控复盘均DONE
productization前提一到五全闭环
overlay f modelti/disabled
等PM手动shadow
问题编号 Q037
新状态 部分pesolved
结论 Phase 2A profit target主发现
入SPEC-077已DONE
Phase 2B NORMAL BPS audit deferred
最低优先级
Phase 2A零点六五候选deferred
等零点六零观察live效果
问题编号 Q038
新状态 部分resolved
內容 BCD comfortable top模式
SPEC-079入场过滤加SPEC-080
止损收紧均DONE
但仍是umbrella research保持open
未来候选包括state conditional stop
和score大于等于二的更激进filter
问题编号 Q009
新状态 仍blocked
内容 Schwab Developer Portal
HCE通过MC仍等待
不影响backtest仅影响live
execution
【新增问题】
问题编号
candidate research
ivp252大于等于55触发REDUCE WAIT
3y backtest发现HC的11笔IC
但MC因此gate全部跳过
合计正一万三千九百五十二
是否over restrictive待研究
依据HC vs MC 3y tieout 2026-05-01
【Master Doc影响清单】

PARAM MASTER需要更新 yes
新增三个toggle参数
profit target从零点五零升级到零点六零
stop mult显式化
open
questions需要更新 yes
Q020加0036加Q037部分加Q038部分均resolved或更新
Q039候选
strategy status蒂要更新 yes
策略选择逻辑实质变化
SPEC-074/ABCD filter/lBCD stop
research notes需要更新 yes
Q038研究弧完整记录
trade-list方法论修正
SPEC状态需要更新 yes
SPEC-074加075加076加077加078加079加080
均DONE状态
【HC指命】
指命1 同步SPEC实施
HC需要将以下七个SPEC的代码改动
全部同步到HC端codebase
SPEC-074加SPEC-075加SPEC-076
加SPEC-077加SPEC-078加SPEC-079
加SPEC-080
PM会单独传输每个SPEC的源代码diff
指令2 重跑3y backtest tieoutHC在同步代码后
重跑2023到2026 3y backtest
导出CSV格式与之前相同
回传供MC比对收敛度
目标至少99pp trade match
总PnL差小于一千美金
指命3 backfil1 VIX3M数据
SPEC-074M #VIX3M term structure
HC需B1oomberg Windows机器跑
data slash fetch bbg vix3m点py
回传vix3m history点csv
指令4 dashboard同步

SPEC-078/DP12 Fast Path iweb slash html slash
spx stratihtml
HC需同步否则dashboard显示仍是trade based metrics
指令5 productization部署姿态保持所有四个toggle参数
overlay f modelshock mode bubcd comfort filter mode tabcd stop tightening mode
HC默认值必须保持disabled
不允许HC自行翻activePM会通过下次handoff
单独决定shadow flip时机
指令6 backtest tieout特殊关注
3y期间HC独有29个entry日期
MC独有24个entry日期
重跑后这两个数字应该显著缩小到e或个位数
若仍有大量divergence
说明SPEC-074同步不完全需要进一步reconcile
【不要推断的项目】
项目1 SPEC-079和SPEC-080的thresholdspost hoc参数不要HC擅自调整
VIX的13和15
dist 30d high的负一pct MA50的一点五
debit stop的负需点三五
均为Phase 2B和Phase 2C验证后的值HC实施时严格使用这些数值不要重新优化
项目2 V5b的combined部署不要让HC自动翻active
两个toggle独立可控
PM会先flip到shadow观察后再决定观察期至少四到八周
项目3 SPEC-079 v2的fix history
AMP在SPEC-080同期session里
顺手修了SPEC-079 Attempt 1的两个bug
但没filed正式v2 handoff
HC同步时应使用SPEC-079最新代码
含bool castillog call moved

两个修复
项目4 Q038的研究路径实质是PM选了Path GSPEC-079单独立先
SPEC-080并行验证后再开
HC不要把它们当成被动的两个独立SPEG
是有先后依赖关系的pair
【下周Mc计划】
计划1 等待HC return包确认SPEC同步完成度
#E3y tieout #2
目标收敛到trade差零或个位数
计划2 准备双toggle shadow部署
当HC sync完成后
PM$flip
bed comfort filter mode#|shadow bed stop tightening mode#shadow overlay f mode#l|shadow
观察1ive期一到二个月
计划3 SPEC-076 review protocol
3周后约2026-05-20
#doc slash OVERLAY F REVIEW PROTOCOL md
检查shadow 1og累积
若fires大于等于10或90天
启动quarterly review
计划4 0039 candidate research
若PM拍板研究
MUlIVP gate sensitivity sweep
看ivp252阙值放宽到60或65
能否回收本期发现的11笔IC
EV
计划5 备选研究方向
profit target零点六五follow up
等当前雾点六雾观察1ive效果
约2026-06到08考虑
【3y backtest tieout数据】
本期最后一项工作
PM要求做HC加MC的trade tieout

HC文件
data slash backtest trades 3y 2026-04-29 csv
HC共57
trades
HC急exit pnl正七万三千九百五十二
MC当前默认配置
profit target等于零点六零
所有toggle disabled
MC对照模式为公平比对
MC手动设profit target回零点五零
MC#52 trades
MC.急exit pn1正四万五千九百二十二
差异分解
第一类 入场日期分歧 主要原因
HC独有入场日期 二九个
MC独有入场日期 二四个
双方都入场的日期二八个
当双方在同一日都入场时百分百洗择同一策略分歧不在策略选择而在是否入场的gate行为第二类 策略组合分化
BCD HC二一笔MC一五笔
HC pn1正三万七千七百一十四
MC pn1正三万二千八百一十三差六笔差四千九百零二
BPS HC一四笔MC二一笔
HC pn1正一万一千六百一十九
MC pn1正七千二百零五
差正七笔但pn1差负四千四百一十四
IC regular HC一三笔MC六笔
HC pn1正一万六千七百零五
MC pn1正一千努九十
差负七笔差负一万五千六百一十四最大单一拖累在此
IC HV HC八笔MC六笔
差负二笔差负三千五百零六
BPS HV HC一笔MC四笔
差正三笔差正四百零六

第三类 同入场同退出原因不同pn1
最显著案例是2024-12-13 BCDHC加MC同日入场SPX等于六雾五一
HC在2024-12-18退出pn1正六六二
MC在2025-01-14退出pn1负九五七七差超过一万美金
原因是persistence filter
触发时机不同
HC单日bearish即翻
MC等多日确认
是SPEC-020设计trade off
斋HC核对项
HC的_backtest_select源代码是否仍是简化矩阵fallback
而非delegate到live
若是说明SPEC-074同步必要
strategy
HC的trend signal逻辑
ATR
persistence filter版本
请告知current commit
以确认2024-12-13
BCD时机差异
属哪个SPEC尚未同步
HCAJQ015 IVP gate
ivp252大于等于55是否在NORMAL VOL fallback路径上若HC的fallback是直接返回IC
而MC通过live tree
此即11笔IC reject根因
【SPEC技术细节供HC参考】
为帮助HC同步代码
列出本期主要代码改动文件
SPEC-074
backtest slash enginespy strategy slash
selector Spy
backtest slash
metrics portfolioSpy
SPEC-075
strategy slash overlayipy NEW strategy slash selectorspy backtest slash enginesipy backtest slash portfoliopy

SPEC-076
strategy slash overlayipy strategy slash selectoripy scripts
slash overlay f review reportipy NEW
doc slash OVERLAY F REVIEW PROTOCOLAmd NEW
SPEC-077
strategy slash selectorspy backtest slash enginespy
SPEC-078
web slash api serverspy
web slash html slash spx strathtm
backtest slash engine#py docstring only
SPEC-079
strategy slash bed filterSpy NEW
strategy slash selector#py backtest slash enginespy doc slash BCD FILTER
SHADOW LOGAmd NEW
SPEC-080
strategy slash bed stopsipy NEW
backtest slash enginespy
strategy slash selector&py for live log call
测试文件清单
tests slash test overlay f gatespy tests slash test overlay f monitoringpy tests slash test bed filterapy tests slash test bed stoppy tests slash
test dashboard metrics consistencyripy
【完整SPEC文档传输需求】
HC同步前需要的完整文档清单
SPEC文档七份
task slash SPEC-0745md task slash SPEC-075Amd task slash SPEC-076md task slash SPEC-077Smd task slash SPEC-078Smd task slash SPEC-079 md task slash SPEC-080#m
研究文档三份
task slash 0038 2024 2025 drawdown analysis 点md

task slash 0038 phaseb findings md task slash 0038 phase2c
findings Amd
ChatGPT review三份
task slash Q038 2nd quant reviewmd
Q038 3rd quant reviewamd
task slash SPEC-070 V2 Q027 Review点md仅参考
新燴数据文件清单
data slash data
slash
bed filter shadow#jsonl bed filter alert lateststxt
data slash bcd stop shadow enginejsonl data slash bed stop shadow live#jsonl data slash overlay
f shadowijsonl
data slash
overlay falert latestitxt
新墖测试文件清单
见上一节测试文件清单
【HC收到后回包要求】
HC在执行完同步后
请按标准HC return包格式返回
重点回报
确认项一
SPEC-074#|SPEC-080
全部七个SPEC实施完成度逐个PASS or FAIL状态
确认项二
3y backtest tieout #2结果
HC trade count vs MC 52 trade count
差异多少笔
PnL差异多少美金
若差异大于五千美金
请提供具体divergence trade列表
确认项三
所有四个toggle参数保持disabled状态确认
确认项四
0039候洗
Hc对IVP gate sensitivity research
是否有补充看法

