# MC Response 2026-05-02 corrections
类型 OCR校正 reply
对应 HCv2 文件
sync slash MC_to_HC
slash
MC Response 2026-05-02_v2.Hmd
回应针对一件事
V2 OCR 清洗后5项数字错读
其中 critical 影响 HC attribution
分析的需 HC 在使用前修正本 reply 不修改v2文件本身
仅列出 MC canonical 正确数字作为v2的 errata 表
HC 在阅读v2时
请按本 reply 替换错读数字
【背景说明】
HC 在 2026-05-02 完成
mc_response_20260502md
的 OCR清洗
产出 MC Response 2026-05-02_v2
v2 整体格式整洁
绝大多数数字保留正确
但有 5项 critical 数字错读
若 HC 直接用v2做 attribution 分析会得出错误结论
特别是 IC ledger 的6笔 entry_credit
被锚读为缩小 100 倍
若 HC 据此判断 IC trades 量级会严重 underestimate IC
credit 量级
本 reply 列出5项糾正以及对 HC 已正确处理的部分做 acknowledge

【纠正项 — inon_condor_hv 的 PT等于零点五零 PL】
v2 line 288 写法
PT 零点五零 七五 笔 加一万四千一百二十六
v2 自标 OCR-reconstructed
MC canonical 正确值
PT 零点五零 七五 笔 加一万三千六百七十九
校验
原文整数 13679
v2 重构为 14126 是错的两数字差距明显
v2 的 OCR-reconstructed 标签表明 HC 自知不确定但重构方向错了
影响
v2 错值会导致 iron_condor_hv
看起来比实际多贩 447 美金

【纠正项 二 iron_condor_hv 的 delta_pnl】
v2 line 290 写法
delta 減五百八十七
v2 自标 OCR-reconstructed
MC canonical 正确值
delta 减一百四十
1Bo
timelin
此值由纠正项一推导
PT 零点六零 加一为二千五白二十九减
PT 零点五零 加一万三千六百七十九
等于 減一百四十不是 減五百八十七
彩响
v2 错值会让 HC 误以为
profit_target 升至零点六零对 iron_condor_hv 有四点二倍 实际拖累
从而错估 SPEC-077 对各策略影响

【糾正项 三 n_days】
v2 line 173 line 210 line 225
均写 n_days 等于 九六一六
v2 自标 OCR-reconstructed
MC canonical 正确值
n_days 等于 六六二一校验
v2用26点32 乘 365点25
推算日历天 9612 然后取 9616
但 MC engine 计算的是 trading days
即交易日
26点32 年内的交易日数
约250乘26点32等于6580
MC 实测精确值是 6621
影响
ann_roe 公式用 n_years 不用 n_days
所以不影响计算结果
但事实层面 v2 的 9616 是错的本来应是 trading days 6621
IBo
tmelır
【出正项 四 0039 IC ledger 6笔 entry_credit）
v2 line 422 line 435 line 448 line 461
line 474 line 487
六笔 IC ledger 的 entry_credit 字段全部 OCR 错读谈数被除以一百即小数点位置错位
MC canonical 正确值
第1笔2023-08-15
v2 错读 减二九点六二
MC 正E确 減二九六二
单位 USD
第2笔 2023-09-20
v2 错读 减二七点零二
MC 正确 减二七零二
单位 USD

File Edit View
第3笔 2023-10-31
v2 错读 减三四点八七
MC 正确 减三零八七
单位 USD
注意 v2 还有数字错读 34 vs 30不仅是小数点
第4笔 2024-05-03
v2 错读 减二七点九二
MC 正确 减二七九二
单位 USD
第5笔2025-12-18
v2 错读 减四六点三五
MC 正确 減四六三零
单位 USD
注意 v2 还有数字错读 35 vS 30不仅是小数点
第6笔 2026-01-21
v2 错读 減四七点 OCR unclear
MC 正确 減四七一单位 USD
校验
IC 卖出在 SPX 上
通常 entry_credit 量级为 几于美金 per contract
不是 几十美金 per contractv2 的减二九点六二
意味着只收到 30 美金 credit
这与典型 IC 不符应是 减二九六二
即 收到2962关金 crcdit
影响
最大 critical 错谈
若 HC据v2的30美金 credit
判断这 6笔 IC 量级
会严重 underestimate IC 的相对重要性结读后 IC 看起来像微型仓位
实际是接近 BCD entry_credit 量级
即正常 size 的 IC

【纠正项 五 0039 IC ledger dte_at_exit）
v2 写法
第2第 dte_at_exit 等子
第3笔 dte_at_exit 等于第4笔 dte_at_exit 等于
MC canonical 正确值
第2笔 dte_at_exit 等于二-第3笔 dte_at_exit 等于第 4笔 dte_at_exit 等于
ニー
exit_reason S roll_21dte
ro11 触发条件是 dte 等于 21
不是 22
若是 dte 等于 22
ro11 21dte 不会触分
v2 的22与 exit_reason 矛盾第1笔 dte_at_exit 二五 v2 正确
第5宅 dte_at_exit 二五v2正確
第6笔 dte_at_exit 二五 v2 正确
彩响
小 但应纠正
exit_reason 与 dte 一致性
是 audit trail 重要屈性
【对v2 已正确处理的 acknowledge】
1 Bo
acknowledge - OR Delta vs A Mili footnote
v2 line 8 加了 footnote
说明扫描件中
Delta 字符大量被识別为 AHC 主动文档化此 OCR pipeline
常见问题 是好做法
建议 HC 后续 sync 包都保留此炎 OCR pipeline 注释
acknowledge
二 HC 自标 OCR uncertain 但其实正确
以下v2 自标 OCR uncertain
但其实 MC 数字正确
不需要修改 仅 acknowledge

File
Edit
View
bul1 put_spread_hv delta 减二六
v2 自标 1ikely 减二五 减二六 OCR uncertain
MC 正确 減二六
v2 猜对了
bull_call
_diagonal delta 加九八
v2 At OR minimal fix
MC 正确 加九八
v2 猜对了
第6笔 entry_spx六八七六
v2 自标 OCR likely
MC 正确 六八七六
v2 猜 了
acknowledge 三 校验行格式简化
MC 原稿用中文数字校验行
零七四 零七五 等
v2 简化为 校验 SPEC-编号不带括号中文数字
此简化无書
v2 自身已是 OCR 后电子文件不再需要中文数字防 A6误读
acknowledge 四 整体v2 高质量除上述 5 项错读外
v2 把 99多 percent 的数字正确保留
SPEC 编号 全部正确
PT 0点50 vs PT 0点60 主表
所有数字一致
by exit_reason 全部一致
HC OCR pipeline 整体可靠

【完整数字对账 防再误读】
为防止本 reply 再被 OCR 错读关键数字逐项列出
iron_condor_hv 全样本
PT 零点五零 七五 笔 加一三六七九 USD
PT 零点六零 七三 笔加一三五三九USD
delta_pnl 減一四零 USD
delta_n 減二

X
1 Bo
timelir
n_days 全祥本
等 六六ニー trading days
不是 九六一六
Q039 IC ledger entry_credit 6 €
按 entry_date 顺序
2023-08-15 减二九六二
2023-09-20 減二七零二
2023-10-31 减三零八七
2024-05-83 減二七九二
2025-12-18
，減四六三零
2026-01-21 減四七—
单位均为 美金
量级 三千 不是三十
0039 IC ledger dte_at_exit 6 €
f entry date Not
2023-08-15 dte_at_exit 等于
2023-09-20 dte_at_exit
等于
2823-10-31 dte_at_exit等子
2024-05-03 dte_at_exit 等于
一一二
2025-12-18 dte_at_exit等子
2026-81-21 dte_at_exit 等子
五三三五五
校验
exit_reason 等子 50pct_profit 肘
dte_at_exit 等子二五
exit reason STrollidte B$
dte_at_exit 等于二一
[SPEC编号 校验汇总】
SPEC編号 SPEC-074
校验 SPEC-074（零七四）
SPEC编号 SPEC-075
校验 SPEC-075（零七五）
SPEC編号 SPEC-076
校验 SPEC-076（零七六）

File
Edit
View
SPEC编号
SPEC-077
校验 SPEC-077（零七七）
涉及Q编号
Q039 IC regular ledger
内容由本 reply 的纠正项 四五校正
【HC 收到本 reply 后建议动作】
第一步
将本 reply 的 项糾正
应用到对 v2的阅读理解不需要重写v2 文件本身
但 HC 任何基于v2 数字做的 attribution 分析应使用本 reply 的正确值
第二步
特别是 Q039
attack
HC 在做
ivp252 三个分桶分析时
请用本 reply 的 IC ledger
正确 entry_credit 值
进行 trade 量级判断不要用v2的30美金量级
第三步
若 HC 自己后续生成
HC return 包时引用了v2 中错读的数字请基于本 reply 修正第四步
本 reply 为可能成为
v3 OCR 清洗的 reference
HC 若再做一轮清洗请将本 reply 的纠正合井到v3 中
保持 audit trail 完整
1 Bo
tımelir
【MC 不修改原稿声明】

MC 端不修改原始
mc_response_20260502Fmd
保留 audit trail
仅在本 corrections 文件中
如 HC 需要更新
HC return el HC index E
请使用本 reply 的正确数字作为 canonical 引用
文档结束
格式遵循 OCR friendly
SPEC编号带校验行
关键数字均文字化
所有金额含明确单位 USD
所有 trade 字段
均与 entry_date 对应不依赖位置顺序记忆