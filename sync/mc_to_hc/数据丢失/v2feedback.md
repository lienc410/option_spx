Task Type: runtime maintenance（同步包一次修订）
Next Owner:HC Claude（由 PM 转达 4项修正指令后重发 v3）
或PM 手动在v2上 patch
Why This Route:
1.    R1/R2/R3/R4 是真•数据丢失或残留 OCR，不是格式问题
2.   R2 的 0033 scale factor 和 addendum 项，直接影响 HC对R7 Option B+E dual-colum reporting 规则的实现
3.   v2 整体质量已经够高，值得再收尾一版而不是整体重写
Required Files:
-   sync/MC_to_HC/mc_handoff_20260424.md (truth)
-   sync/MC_to_HC/MC_Handoff.
_2026-04-24_v2.md（待补）
PM Context To Preserve:
-   HC已经做过一轮 OCR 清理，能理解 paraphrase边界
-   只需要点名4处 CRITICAL 和2处 MEDIUM，不要求整体重排
Forward Prompt（给HC 的修订指令）：
请基于v2再产出v3，修正以下6点：
R1. §开放问题 Q018 结论中补“加 SPEC-069"：
resolved in production via SPEC-066 + 0022 + SPEC-068 + SPEC-069
R2. 5开放问题Q033补齐4项：
-  日期 2026-04-24
-   SCale factor 完整列表：HIGH_VOL SMALL tier x 0.1FULL tier x 2HALF tier x 1
-  产出物：对 SPEC-071 加 live-scale addendum
R3. §下周 MC计划>计划1>若A：
“写 RDD-0019 CLOSE” 改为”写 RDD-0019CLOSE"
R4. §研究发现 F005：
"SPEC-071
sim / I1861 vs engine / D115"
EX "SPEC-071 sim +$1,861 vs engine +$115"
R5. SHC 指令>指令6：
“SeqMaxD”改 “SegMaxDD"
R6.
§研究发现 F007：
把“Q018 R8 retrospective 表明..”改回
"2A-lite retrospective 'EE EXTREME_VOL hard stop
已经 mitigate..
归因来源是 2A-11te 变体，R8 是 review 轮次