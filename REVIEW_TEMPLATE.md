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
