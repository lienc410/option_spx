# 前端完整 Review Charter（2026-07-06，PM 发起）

**三方分工**：
- **Quant（主会话）**: 内容正确性——每页展示的策略逻辑/参数/回测数字 vs 代码与生产真值；重点核对本轮全部策略变更（SPEC-113 carve、121 止损 10×、124 退役与 60% 文案、SPEC-060 归因、A5 ladder 披露）是否完整正确上屏
- **前端工程师（设计审计 subagent）**: DESIGN.md 合规 + 可读性 + 美观——语言位置规则、mono 数字、badge/tier 词汇表、间距刻度、回测页模板三要件（指标行/价格叠加图/Trading Discipline）、信息层级
- **Dev**: 汇总两侧 findings 后统一修复批（SPEC-125 预留）

**页面清单**（web/templates/）: portfolio_home / spx / backtest / matrix / es / es_backtest / q041 / q041_backtest / q042×2 / aftermath×2 / performance / margin / funds / partnership / 其他

**重点风险区**（quant 预判）:
1. /matrix 页数据源——canonical 展示 vs 行为真值（5 个已知分歧格的归因是否上屏）
2. 回测页是否披露定价口径——Q087 后我们已知 FLAT 高估 credit 结构，26y 数字继续裸展示是否误导（内容级判断，需三方合议）
3. 策略卡参数文案 vs 现行 StrategyParams（60%/10×/disabled filter 等本周变更）
4. 已退役/shadow 项是否仍在页面宣传（SPEC-026 overlay 等）
5. Q085/S2-BPS、BCD shadow 等新证据流是否有展示面（或有意不展示——需决策记录）

**产出**: 双侧 findings 文件 → 合并分诊 → SPEC-125 修复批 handoff → dev 实施 → 三方复验。
