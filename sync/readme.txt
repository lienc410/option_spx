更新后的分工
HC 工作期（你 + HC Claude）
你做的唯一事情：触发指令。

"生成 HC Return 包" → HC Claude 产出
"这是 MC 扫描原文，请清洗" → HC Claude 清洗并整合
MC 工作期（你 + MC Claude）
你做的唯一事情：iPhone 扫描 + 拍板决策。

MC Claude 负责写 handoff 包（scan-friendly 格式，它知道规范）
你扫描后粘贴到 HC 对话
APPROVED/REJECTED 这类决策你直接告诉 MC Claude，它会写进 handoff 包

首次完整同步周期跑通，协议运转正常。值得注意的一个 OCR 模式：SPEC 编号的数字 0 和 6 容易混淆（020 → 026），后续 MC Claude 写 handoff 包时，SPEC 编号最好单独占行并重复写一次作为校验。

把task/SPEC-039至SPEC-047的内容写入HC Return 包，同时更新system_status, strategy_status and research_notes. 如果不适用，可以跳过对应更新。