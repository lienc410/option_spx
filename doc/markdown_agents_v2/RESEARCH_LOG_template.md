# RESEARCH_LOG

Last Updated: YYYY-MM-DD
Owner: Planner or PM

---

## Entry Template

### R-YYYYMMDD-01 — Topic

- Topic: one-line research subject
- Findings: 1 to 3 short lines
- Risks / Counterarguments: 1 to 3 short lines
- Confidence: `low` / `medium` / `high`
- Next Tests: one-line next validation step
- Recommendation: `enter Spec` / `hold` / `drop`
- Related Spec: `SPEC-XXX` or `N/A`
- See: `doc/...`

---

## Entries

### R-YYYYMMDD-01 — Example Topic

- Topic: DIAGONAL entry filter under both-high IV pressure
- Findings: both-high appears negative alpha in current research sample
- Risks / Counterarguments: sample size is still small; live behavior may differ
- Confidence: medium
- Next Tests: monitor live n and rerun after threshold is reached
- Recommendation: hold
- Related Spec: SPEC-054
- See: `doc/strategy_status_2026-04-10.md`

### R-YYYYMMDD-02 — Example Topic

- Topic: local_spike should affect size-up or tagging only
- Findings: current evidence supports diagnostic tagging, not sizing change
- Risks / Counterarguments: no meaningful live sample yet
- Confidence: low
- Next Tests: wait for live sample count target before reassessment
- Recommendation: hold
- Related Spec: SPEC-055
- See: `doc/strategy_status_2026-04-10.md`
