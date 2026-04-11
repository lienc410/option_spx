# MC Handoff 2026-04-10
上次HC Return日期 2026-04-07
本次HC工作期 2026-04-08 到2026-04-10
【本期摘要】
第一条 完成IVP四象限全策略审计
为DIAGONAL增加三道新守护内
第二条 修正SPEC-048 regime decay误应用发现仅DIAGONAL受益，其他策略均负第三条 SPEC-055降级为诊断tag
ChatGPT Review驳回size-up提案
n等于12不足以支持sizing决策
【当前状态快照】
当前推荐生产配置
overlay_mode=disabled shock mode=show
use_atr_trend=True
bearish_persistence_days=1
当前最高优先阻塞
Schwab Developer Portal批准等待中
当前PARAM_MASTER版本号v2
本期无新参数变更
【参数变更】
本期无参数变更
（注：新增逻辑为code constants
非StrategyParams参数不需要PARAM_MASTER更新）
【SPEC决策】
SPEC编号 SPEC-048
校验 SPEC-048（零四八）
新状态 DONE
PM决策日期 2026-04-08
备注 regime decay信号及ivp63字段建立事后发现size-up应仅限DIAGONAL
已由SPEC-053修正
SPEC编号 SPEC-049

校验 SPEC-049（零四九）
新状态 DONE
PM决策日期2026-04-10
备注 DIAGONAL入场内ivp252在30到50
范围内则REDUCE_WAIT
SPEC编号 SPEC-050
校验 SPEC-050（零五零）
新状态 DONE
PM决策日期 2026-04-10
备注 Non-overlapping event study工具建立不改变交易逻辑
SPEC编号 SPEC-051
校验 SPEC-051（零五一）新状态 DONE
PM决策日期 2026-04-10
备注 LOW_VOL 加BULLISH加iV=HIGH
则REDUCE」
_WAIT
SPEC编号 SPEC-052
校验 SPEC-052（零五二）
新状态 DONE
PM决策日期 2026-04-10
备注 HIGH_VOL加BEARISH加iVp63大于等于70
JUREDUCE_WAIT
SPEC编号 SPEC-053
校验 SPEC-053（零五三）
新状态
- DONE
PM决策日期 2026-04-10
备注 regime decay size-up限DIAGONAL专属修正SPEC-048对BPS等的误应用
SPEC编号 SPEC-054
校验 SPEC-054（零五四）
新状态 DONE
PM决策日期 2026-04-10
备注 DIAGONAL ivp63大于等于50且1Vp252大于等于50则REDUCE_WAITSPEC编号 SPEC-055
校验 SPEC-055（零五五）
新状态 DONE
PM决策日期 2026-04-10
备注 降级为诊断tag only不size-up
ChatGPT Review REVISE已采纳2条

【研究发现】
发现编号 F001
内容 event study n=89 DIAGONAL平均盈亏加1577美元胜率72%
# backtest/run_event_study.py
#E*SPEC SPEC-050
发现编号 F002
內容 DIAGONAL唯一有入场信号alpha的策略fixed_hold未触及目标时平均仍赚1062美元
*# run_event_study_analysis.py
相关SPEC SPEC-059
发现编号 F003
内容 IC在fixed
L_hold=21天胜率等于0%
是设计行为非bug
IC的alpha完全来自exit timing
* run_event_study_analysis.py
相关SPEC SPEC-050
发现编号 F004
内容 regime decay size-up仅DIAGONAL
有效Sharpe加3.56
BPS Sharpef 10.87
BPS_HV Sharpef11.12
BCS HV Sharpef 12.84
k# backtest/run_ivp_regime_audit.py
相关SPEC SPEC-053
发现编号 F005
内容 DIAGONAL 1ocalspike子条件
ivp63大于等于50且ivp252小于50
n等于12平均盈亏加3918
胜率92%Sharpe加4.12
kt run_ivp_regime_audit.py
相关SPEC SPEC-055
发现编号 F006
内容 DIAGONAL both-high子条件
ivp63大于等于50且ivp252大于等于50
n等于8平均负2556 Sharpe负1.36
SPEC-049加051无法全部拦截
6笔穿透均值负2624
最差单笔负14973
（2020-02-06 COVID前期）依据 run-
_ivp_regime_audit.py
相关SPEC SPEC-054

发现编号 F0e7
内容 BCS_HV ivp63大于等于70区间
n等于14均值负2222胜率21%
经济逻辑VIX在63天高位时
mean reversion风险最高
# run_matrix_audit.py
相关SPEC SPEC-052
内容 SPEC-055
ChatGPT Review REVISE
采纳2条驳回3条
采纳n=12太小不足sizing
采纳两种状态混淆问题
驳回DIAGONAL是delta-driven故
IV信号无关（与SPEC-049等矛盾）
驳回两个发散方向都size-up问题
驳回timing不成熟（改tag已解决）
# task/SPEC-055_chatgpt.md
相关SPEC-055
【策略逻辑变更】
变更项 LOW_VOL加BULLISH分支新增SPEC-049内
旧逻辑
TREND=BULLISH则直接DIAGONAL
新逻辑 ivp252在30到50范围内
JUREDUCE WAIT
相关SPEC SPEC-049
变更项 LOW_VOL加BULLISH分支新增SPEC-051内
旧逻辑 ivp252内后直接DIAGONAL
新逻辑 iV=HIGH则REDUCE_WAIT
相关SPEC SPEC-051
变更项 LOW_VOL加BULLISH分支新增SPEC-054内
旧逻辑 SPEC-051内后直接DIAGONAL
新逻辑 ivp63大于等于50且
ivp252大于等于50则REDUCE_WAIT
相关SPEC SPEC-054
变更项 HIGH_VOL加BEARISH分支新增SPEC-052内
旧逻辑 VIX_RISING检查后直接BCS_HV
新逻辑 ivp63大于等于70则REDUCE_WAIT
相关SPEC SPEC-052

变更项
_compute_size_tier regime decay
旧逻辑
regime decay时对所有策略
HALFÄ-FULL
新逻辑 regime decaysize-up限定在
strategy等于BULL_CALL_DIAGONAL时相关SPEC SPEC-053
变更项
Recommendation新增1ocal_spike
旧逻辑 无此字段
新逻辑 1ocal_spike布尔字段
ivp63大于等于50且ivp252小于50时为True否则为False
不影响size tier仅为诊断tag
UI显示厌蓝色注释
相关SPEC SPEC-055
【开放问题更新】
问题编号 Q009
新状态 blocked无变化
结论 Schwab Developer Pontal仍在等待问题编号 Q002
新状态 open无变化
结论 Shock activemode待Phase B验证
问题编号 Q010
新状态 新增
内容 SPEC-055b前置条件追踪
local spike条件下真实DIAGONAL
交易数n需达到25笔才重评size-up
当前n等于e笔真实交易
问题编号 Q011
新状态 新增
内容 DIAGONAL ivp252在50以上ivp63小于50区间（regime decay）
n等于8 Sharpe加3.56
样本偏小需真实交易验证
[Master
Doc影响清单】
PARAM_MASTER需要更新 noopen_questions需要更新 yes
新增Q010和Q011
Strategy_status需要更新 yes
已生成strategy_status_2026-04-10.md

research_notes需要更新 yes
已生成research_notes_2026-04-10.md
SPEC状态需要更新 yes
SPEC-048到SPEC-055全部DONE
【HC指令】
指令1 确认selector.py LOW_
I_VOLJOBULLISH
分支三道gate串联顺序正确
SPEC-049先于SPEC-051先于SPEC-054
指令2确认_compute_size_tier已正确增加strategy参数
BPS和BCS_HV不再触发regime decay
size-up
指令3确认Recommendation.local_spike
字段已存在且default为False
两个caller均传入local_spike参数指令4 确认API endpoint/api/recommendation的JSON响应
包含local_spike布尔字段
指令5 更新open_questions.md
新增Q010和Q011（见本包内容）
指令6 更新SPEC状态文件
SPEC-048到SPEC-055全部改为DONE
指令7 strategy/selector.py中
IVP相关常量确认
REGIME_DECAY_IVP63_MAX=50
REGIME_DECAY_IVP252_MIN=50
LOCAL_SPIKE_IVP63_MIN=50
LOCAL_SPIKE_IVP252_MAX=50
---
【不要推断的项目】
项目1 SPEC-055 size-up将来重新评估的时间节点由PM决定
HC不自行判断n=25是否已达到
项目2 overlay_mode切换active的时机由PM决策HC不自行切换

【下周MC计划】
计划1 追踪真实交易中1ocal spike
条件的DIAGONAL笔数累积进度为SPEC-055b评估做数据准备
计划2 评估Shock active mode
Phase B A/B验证时间表
计划3 继续观察HIGH_VOL加LOW
加BEARISH到BCS_HV路当前n=11标记为观察状态