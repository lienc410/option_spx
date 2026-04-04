# HC_MC_SYNC_PROTOCOL

## 1. Purpose

This protocol defines how project knowledge, research progress, and selected implementation artifacts are synchronized between two working environments:

- **HC**: external research / documentation / review environment
- **MC**: primary execution / implementation / validation environment

The protocol is designed to satisfy the following goals:

1. Preserve MC as the system of record for data, formal implementation, and validated results.
2. Allow HC to contribute meaningfully to research design, review, documentation cleanup, and strategy refinement.
3. Ensure that, by project completion, HC contains a **complete, current, and correct knowledge mirror** of the project, including strategy logic, parameters, rationale, and validated conclusions.
4. Respect the hard information flow constraints between HC and MC.

---

## 2. Scope

This protocol applies to:

- strategy research
- strategy status documentation
- research notes
- parameter tracking
- experiment summaries
- review notes
- OCR-based document transfer
- limited code or pseudo-code transfer
- weekly and milestone-level knowledge consolidation

This protocol does **not** require HC to contain a full runnable copy of the project repository or any restricted data from MC.

---

## 3. Definitions

### 3.1 MC (Execution Truth Source)

MC is the authoritative environment for:

- raw and derived data
- main source code
- backtest execution
- validation runs
- official metrics
- final parameter values
- final implementation status

### 3.2 HC (Knowledge Mirror Environment)

HC is the authoritative mirror for project knowledge, including:

- strategy structure and rules
- risk logic
- parameter definitions and latest values
- research rationale
- experiment conclusions
- open questions
- review findings
- implementation shape and module mapping

HC is **not** required to store raw data or the complete codebase.

### 3.3 Knowledge Mirror

A **Knowledge Mirror** is a current, structured, human-readable representation of the project that is sufficient for:

- understanding the strategy end to end
- continuing research
- reviewing design decisions
- reconstructing current logic and parameters
- understanding validated conclusions and remaining gaps

### 3.4 Delta Document

A **Delta Document** records only what changed during a given iteration, work session, or handoff window.

### 3.5 Snapshot / Master Document

A **Master Document** records the currently effective project state for a major knowledge domain, such as strategy definition or parameter registry.

---

## 4. Information Flow Constraints

### 4.1 HC -> MC

The following are allowed from HC to MC:

- markdown files
- small data files
- small code files
- review notes
- cleaned OCR documents
- structured summaries
- pseudo-code
- small patch suggestions

Source code transfer from HC to MC is allowed only in limited small-file form and only when appropriate.

### 4.2 MC -> HC

The following constraints apply from MC to HC:

- **No data may be sent from MC to HC**
- markdown documents may be transferred indirectly through OCR / iPhone text scanning
- project knowledge may be transmitted in textual summary form
- no raw result data, detailed time series, or sensitive data exports may be sent

### 4.3 Practical Consequence

MC -> HC synchronization must be designed around:

- OCR-friendly markdown
- summary documents
- parameter tables
- research conclusions
- implementation summaries
- non-sensitive structured descriptions

---

## 5. Operating Model

The environments serve different purposes.

### 5.1 MC Responsibilities

MC is responsible for:

- implementation
- running backtests
- validating hypotheses
- locking official parameters
- producing canonical experiment summaries
- maintaining final truth for performance numbers
- consolidating approved changes into canonical project docs

### 5.2 HC Responsibilities

HC is responsible for:

- research design
- review and critique
- OCR cleanup and correction
- documentation restructuring
- naming and consistency cleanup
- synthesis of findings
- proposal of small patches or pseudo-code
- maintaining a usable project knowledge mirror

### 5.3 Final-State Requirement

At project completion, HC must contain a complete and current **knowledge mirror** of the project, including:

- current strategy logic
- effective parameter values
- current risk controls
- validated experiment conclusions
- known limitations
- current recommended production configuration

This requirement does **not** imply that HC must contain raw MC data or the entire runnable codebase.

---

## 6. Systems of Record

### 6.1 MC as Final Truth Source

The following are always determined by MC:

- official metrics
- official parameter values
- official implementation status
- official experiment outcomes
- official production recommendation
- final code behavior

If HC documentation conflicts with MC outputs, MC prevails.

### 6.2 HC as Knowledge Mirror

HC may contain:

- cleaned and organized project knowledge
- current narrative of strategy logic
- mirrored parameter tables
- module descriptions
- decision histories
- review commentary
- open questions

HC must be updated to remain aligned with MC.

---

## 7. Required Document Sets

The project must maintain two classes of documents:

### 7.1 Master Documents

These represent the latest effective project knowledge state.

Required master documents:

- `strategy_master.md`
- `params_master.md`
- `module_map.md`
- `experiment_registry.md`
- `implementation_status.md`
- `production_recommended_config.md`
- `decision_log.md`
- `open_questions.md`

### 7.2 Delta Documents

These represent incremental change since the previous handoff or consolidation.

Examples:

- `strategy_status_delta_YYYY-MM-DD.md`
- `research_notes_delta_YYYY-MM-DD.md`
- `params_delta_YYYY-MM-DD.md`
- `open_questions_delta_YYYY-MM-DD.md`
- `review_delta_YYYY-MM-DD.md`

---

## 8. Master Document Requirements

### 8.1 `strategy_master.md`

Must describe:

- strategy framework
- signal definitions
- entry logic
- exit logic
- regime logic
- overlays
- shock logic
- risk control logic
- current behavioral caveats

### 8.2 `params_master.md`

Must contain:

- all currently effective parameters
- parameter values
- module ownership
- plain-English meaning
- source SPEC or originating decision
- last updated date
- deprecated parameters when relevant

### 8.3 `module_map.md`

Must describe:

- main modules
- ownership by function
- interfaces / contracts
- upstream and downstream dependencies
- what is canonical vs helper logic

### 8.4 `experiment_registry.md`

Must record:

- key experiments run
- experiment purpose
- high-level configuration identity
- top-line conclusions
- whether the result changed project direction

### 8.5 `implementation_status.md`

Must distinguish:

- done
- partially implemented
- research complete but not implemented
- blocked
- deprecated

### 8.6 `production_recommended_config.md`

Must record the currently recommended production-like configuration, including:

- enabled components
- disabled components
- current parameter set
- rationale for recommendation
- unresolved caveats

---

## 9. Working Rhythm: 3 Days HC / 3 Days MC

Because work alternates across environments each week, synchronization must be **session-based** and **ritualized**.

### 9.1 At the end of an MC work block

An **MC handoff pack** must be prepared for downstream OCR transfer to HC.

### 9.2 At the end of an HC work block

An **HC return pack** must be prepared for transfer to MC.

### 9.3 Minimum expectation

Each change cycle should produce:

- one incremental handoff
- one mirror update decision
- one consolidation step on MC side when appropriate

---

## 10. MC -> HC Handoff Requirements

The MC handoff exists to update HC without transferring restricted data.

### 10.1 Required contents of MC handoff pack

At minimum:

- strategy status delta
- research notes delta
- parameter delta if any parameters changed
- open questions delta
- mirror update checklist

### 10.2 Allowed content

Allowed:

- textual summaries
- parameter tables
- experiment conclusions
- implementation summaries
- open issues
- module summaries

Not allowed:

- raw data
- detailed trade logs
- detailed daily return series
- sensitive exports
- large codebase dumps

### 10.3 OCR-friendly formatting rules

MC outbound text should be written for OCR robustness:

- short lines
- simple bullets
- simple tables only
- minimal special symbols
- avoid ambiguous characters when possible
- avoid dense mixed Chinese/English variable-heavy prose if a cleaner wording is possible
- prefer one topic per file

---

## 11. HC -> MC Return Requirements

The HC return exists to improve clarity, consistency, and research quality without claiming authority over MC truth.

### 11.1 Required contents of HC return pack

At minimum:

- cleaned OCR documents
- review notes
- consolidation suggestions
- mirror update suggestions
- uncertainty flags
- small patch suggestions or pseudo-code if applicable

### 11.2 HC return categories

HC should separate outputs into:

1. **Cleaned Version**  
   OCR corrected, minimal interpretation.

2. **Reviewed Version**  
   Analytical comments, logic challenges, gap detection.

3. **Consolidation Suggestions**  
   Proposed changes to canonical master docs.

4. **Uncertainty Flags**  
   Any field, number, or naming item that HC could not confirm confidently.

---

## 12. Truth and Conflict Resolution

### 12.1 Numeric Conflicts

If HC and MC documents disagree on metrics, thresholds, or counts:

- MC values prevail
- HC should explicitly flag the discrepancy
- MC should update the canonical document set

### 12.2 Logic Conflicts

If HC proposes a hypothesis or interpretation that MC validation does not support:

- the HC view may remain as a research note
- it must not overwrite validated MC conclusions

### 12.3 Naming Conflicts

If multiple names exist for the same concept:

- the canonical name must be set in MC
- HC mirror documents must adopt the canonical naming
- `glossary.md` is recommended if naming drift becomes material

---

## 13. Mirror Maintenance Rules

### 13.1 HC must not remain delta-only

HC should not accumulate only fragmented deltas.  
HC must maintain an updated set of master documents sufficient to recover full project context.

### 13.2 Mirror refresh cadence

A **weekly mirror refresh** is recommended, ideally at the end of the last MC workday of the week or at the end of each major feature cycle.

### 13.3 Mandatory mirror update check

Each delta document should include:

- whether `strategy_master.md` needs update
- whether `params_master.md` needs update
- whether `experiment_registry.md` needs update
- whether `implementation_status.md` needs update
- whether `production_recommended_config.md` needs update

---

## 14. Parameter Synchronization Rules

Because final HC completeness explicitly includes parameters, parameter tracking is mandatory.

### 14.1 Parameter change handling

Any effective parameter change must be reflected in at least one of:

- `params_delta_YYYY-MM-DD.md`
- `params_master.md`

### 14.2 Parameter table minimum fields

Each parameter entry should include:

- name
- current value
- module
- description
- source SPEC / decision
- effective date
- status (`active`, `deprecated`, `experimental`)

### 14.3 Canonical rule

If a parameter value is uncertain in HC, it must be marked uncertain and later reconciled against MC.

---

## 15. Snapshot / Consolidation Policy

### 15.1 Weekly consolidation

At least once per week, the project should decide whether current deltas require snapshot/master updates.

### 15.2 Milestone consolidation

At the completion of any major feature or research module, the relevant master docs should be refreshed.

Examples:

- new signal architecture
- new overlay regime
- shock engine change
- production configuration change
- major OOS validation milestone

### 15.3 Final consolidation requirement

Before project completion is declared, HC master docs must be reviewed for completeness and correctness against MC canonical state.

---

## 16. OCR Workflow

### 16.1 MC side

MC prepares OCR-friendly markdown and exports via permitted manual route.

### 16.2 HC side

HC performs:

- OCR cleanup
- formatting normalization
- naming normalization
- uncertainty flagging
- review annotation when requested

### 16.3 Return to MC

HC returns:

- cleaned markdown
- optional review markdown
- optional consolidation proposal

### 16.4 Do not mix concerns

OCR cleanup and analytical review should be in separate sections or separate files wherever possible.

---

## 17. Recommended Directory Structure

### 17.1 MC side

```text
doc/
  strategy_master.md
  params_master.md
  module_map.md
  experiment_registry.md
  implementation_status.md
  production_recommended_config.md
  decision_log.md
  open_questions.md

delta/
  mc_outbox/
    strategy_status_delta_*.md
    research_notes_delta_*.md
    params_delta_*.md
    open_questions_delta_*.md

handoff/
  mc_to_hc/
    mc_handoff_YYYY-MM-DD/
```

### 17.2 HC side

```text
mirror/
  strategy_master.md
  params_master.md
  module_map.md
  experiment_registry.md
  implementation_status.md
  production_recommended_config.md
  decision_log.md
  open_questions.md

delta/
  scanned_from_mc/
  cleaned_from_mc/
  hc_reviews/

handoff/
  hc_to_mc/
    hc_return_YYYY-MM-DD/
```

---

## 18. Mirror Completeness Standard

HC mirror completeness should be evaluated using the following checklist:

- latest strategy framework synced
- latest effective parameters synced
- latest recommended production configuration synced
- latest research conclusions synced
- latest experiment summaries synced
- latest implementation status synced
- latest open questions synced
- latest decision history synced
- latest module map synced

### 18.1 Status grading

- **Green**: materially current and complete
- **Yellow**: small known lag; still usable
- **Red**: materially stale; not reliable as project mirror

---

## 19. Success Criteria

This protocol is working if:

1. MC remains the undisputed execution truth source.
2. HC remains a current and useful knowledge mirror.
3. Handoffs do not rely on memory or informal chat alone.
4. Parameter drift between HC and MC is rare and quickly corrected.
5. Major design decisions can be reconstructed from docs alone.
6. At project completion, HC contains a complete, current, and correct knowledge representation of the project.

---

## 20. Non-Goals

This protocol does **not** aim to:

- create a full bidirectional repo sync
- move restricted data from MC to HC
- make HC independently runnable with full fidelity
- replace MC as the source of validated performance truth

---

## 21. Minimum Operating Discipline

If a lightweight version is needed, the following rules are mandatory:

1. All cross-environment sync should be documented in markdown.
2. MC must send deltas, not rely on memory.
3. HC must return cleaned docs and review separately.
4. MC values prevail for all final numbers and effective parameters.
5. HC must maintain current master docs, not only deltas.
6. A weekly mirror refresh decision must occur.

---

## 22. Effective Interpretation

If any clause is ambiguous, interpret the protocol in the direction of:

- preserving MC data boundaries
- improving HC knowledge completeness
- reducing documentation drift
- increasing reproducibility of project understanding
