## Review (2nd Quant)

### Reviewer Target File: research_notes.md
### Reviewer: ChatGPT
### Date: 2026-03-29

### Verdict
REVISE

### Key Issues (with mechanism)
- 收益来源 = theta + vol compression → 本质为 short vol → 在 vol 不回落或上升时系统性亏损
- 使用 VIX 作为 IV proxy → 隐含未来信息偏差 → Sharpe 被系统性高估
- MA50 滞后信号 → 入场发生在价格已完成主要移动之后 → 承担反转风险而非趋势收益

### Failure Modes (when it breaks)
- VIX 上升 + SPX 快速反弹 → short gamma 放大 → 短时间内亏损放大
- crisis regime（VIX > 30–35）→ IV 扩张 + skew 非线性变化 → spread 无法有效对冲
- 长期高波动环境（vol 不回落）→ theta 收益无法覆盖持续 mark-to-market 损失

### Risk Exposure (core)
- short gamma: 尾部行情损失呈凸性，亏损加速
- short vega: 波动率上升直接侵蚀 PnL
- regime clustering: 多策略在同一环境下叠加 short vol 暴露

### Suggested Actions (actionable)
- 明确收益来源归因 → 区分 vol risk premium 与方向性收益 → 避免误建模
- 建立风险环境识别 → 在 VIX 上升或高位环境下降低风险暴露
- 优化趋势信号 → 减少滞后性 → 提高入场质量
- 从组合视角评估风险 → 控制多策略同向暴露

### Notes
当前策略体系本质为经过 regime 过滤的 short vol engine。核心风险不在单一策略，而在于在错误 regime 中多策略同时暴露时的系统性回撤。

### What this is NOT
- Not a directional alpha strategy
- Not a low-risk carry strategy
- Not robust across all volatility regimes
