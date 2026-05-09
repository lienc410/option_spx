# Strategy Review Template (2nd Quant)

## Metadata
- Spec ID:
- Strategy Name:
- Reviewer: ChatGPT (2nd Quant)
- Date:
- Version:

---

## 1. Executive Summary
- Verdict: APPROVE / REVISE / REJECT
- One-line thesis:
- Key concern (if any):

---

## 2. Strategy Understanding (Restatement)
- Core idea:
- Signal drivers:
- Position structure:
- Expected edge source (carry / timing / vol risk premium / skew / others):

---

## 3. PnL Decomposition (Expected)
- Primary PnL driver:
- Secondary drivers:
- Conditions for positive PnL:
- Conditions for losses:

---

## 4. Risk Assessment

### 4.1 Tail Risk
- Exposure to vol spike:
- Gap risk:
- Left tail scenarios:

### 4.2 Greeks Exposure
- Delta:
- Gamma:
- Vega:
- Theta:

### 4.3 Hidden Risks
- Short gamma disguised?
- Vol crush / expansion asymmetry:
- Liquidity risk:
- Model risk:

---

## 5. Regime Dependency
- Works best in:
- Breaks in:
- Sensitivity to:
  - VIX level
  - Rate environment
  - Market trend

---

## 6. Assumption Stress Test
- IV assumptions realistic?
- Skew behavior stable?
- Execution assumptions valid?
- Any look-ahead bias risk?

### 6.1 Short-Premium Standard Checks（强制项，仅适用于 short-premium specs）

来源：`QUANT_RESEARCHER.md#short-premium-risk-management-principles`（从 Q012/Q051/Q052 closure 沉淀）

**应用范围说明（2nd Quant 校正 R-20260509-06）**：以下检查项原则上对所有 short-premium spec 强制。但若 spec 涉及的路径满足以下**任一**条件，可在 review 中明确豁免对应检查项：

- 完全自动化、broker-side auto-close、不依赖人工 alert→执行链 → 可豁免 Execution-drift sensitivity（Principle 4）
- EOD-only signal、无 intraday 决策 → 同上可豁免
- 完全 mechanical 入场（无 PM judgment override）→ 同上可豁免

豁免必须在 review 中明确标注理由，不能默默跳过。其他 4 项（stress-capital、IV expansion test、stop methodology、scale dependence）在所有 short-premium spec 上**无豁免**。

- **Stress-capital basis（Principle 3）** — 无豁免：
  - [ ] 给出 entry BP/margin 数字
  - [ ] 给出 VIX +10 / +20 / +40 shock 下的 stress BP/margin 数字（用 `iv_expansion_stress_test` 工具）
  - [ ] stress BP / NLV 比例是否仍可接受（建议 ≤ 35% NLV）
  - [ ] 不接受只用 entry BP% 作为资本效率论证
- **Execution-drift sensitivity（Principle 4）** — when applicable（见上述豁免条件）：
  - [ ] 明确执行假设（immediate / next close / next open / +1 day / +2 day）
  - [ ] 对依赖人工执行的规则，提供 T+0 / T+1 / T+2 sensitivity 测试
  - [ ] 如果 T+0 显著、T+1/T+2 不显著，明确标记为执行风险
- **IV expansion stress test（Principle 1）** — 无豁免：
  - [ ] 已运行 `iv_expansion_stress_test`（见 R-20260509-02 Action A1）
  - [ ] 在 grinding-decline 路径下（VIX 持续 20-30 数月）的累计 PnL 表现
  - [ ] 不接受只看 spike-based stress 的论证
- **Stop methodology（Principle 2）** — 无豁免，但需区分 spread vs naked：
  - [ ] **spread-based 策略**：使用 `pnl_ratio` / loss-budget-relative stop，不是 mark-multiple stop
  - [ ] 若 spread 策略使用 mark-multiple，明确说明在不同 premium 等级下的触发概率差异
  - [ ] **naked options 策略**：mark-multiple 仍可接受，但需在不同 delta / DTE 下做触发率敏感度
- **Scale dependence（Principle 5）** — 无豁免：
  - [ ] 明确这个策略在什么账户规模下经济成立
  - [ ] 如果 scale-dependent，给出 revisit gate 条件（如"NLV ≥ X 后激活"）

---

## 7. Implementation Risks
- Data requirements:
- Signal timing ambiguity:
- Execution timing (EOD vs intraday):
- Slippage / transaction cost sensitivity:
- Overfitting risk:

---

## 8. Backtest Review (if available)
- Sharpe:
- Max drawdown:
- Win rate:
- PnL consistency:
- Any red flags:
  - High win rate but poor PnL?
  - Sudden crashes?
  - Regime clustering?

---

## 9. Suggested Improvements
- Risk reduction:
- Signal refinement:
- Hedging ideas:
- Parameter adjustments:

---

## 10. Final Verdict
- APPROVE:
- REVISE:
- REJECT:

### Required Actions (if REVISE)
- [ ] 
- [ ] 
- [ ] 

---

## 11. Confidence Level
- High / Medium / Low

---

## 12. Open Questions
- 
- 
- 

---

# 🔒 Reviewer Default Behavior（内置规则，无需重复说明）

- Always output in structured review format (strictly follow this template)
- Focus on signal logic， risks and failure modes, not general explanation
- Be critical and challenge assumptions
- Do not rely on prior conversation context
- Only use provided inputs (Spec + optional results)

---

# 🔁 Reviewer → SPEC 写回规则（必须执行）

## 写回目标

生成一个 Quant Researcher 可读、可直接下载的 `{被review file name}_Review.md` 文件：


```md
## Review (2nd Quant)

### Reviewer Target File: {Target File name}
### Reviewer: ChatGPT
### Date: {YYYY-MM-DD}

### Verdict
APPROVE / REVISE / REJECT

### Key Issues (with mechanism)
- {问题} → {机制} → {影响}

### Failure Modes (when it breaks)
- {条件} → {结果}

### Risk Exposure (core)
- {风险类型}: {暴露方式}

### Suggested Actions (actionable)
- {动作} → {目标风险} → {实现方向}

### Notes
{补充}

### What this is NOT
- 防止 Quant Researcher 误建模（错误归因）

Constraints:
- Do NOT propose code-level or implementation-specific changes
- Focus on strategy logic, risk exposure, and failure modes only
