# SPX Strategy — Dual-Layer Documentation Standard

## Goal

The project keeps two documentation layers in parallel:

- Detailed layer: preserves full research context for HC/MC sync, audits, and deep review
- Index layer: provides low-cost, fast-retrieval summaries for planning and coordination

The index layer does not replace the detailed layer.
It exists to reduce repeated long-context reconstruction.

---

## Layer 1: Detailed Docs

Purpose:
- Preserve full reasoning, experiment design, edge cases, and evidence
- Support HC/MC sync and full context rebuild
- Act as source-of-truth narrative for research history

Typical files:
- `doc/research_notes.md`
- `doc/strategy_status_YYYY-MM-DD.md`
- dated deltas, review memos, sync packets

Rules:
- Rich explanations, tables, case studies, and historical context are allowed
- Dated snapshots are allowed
- These files may be long
- These files are not optimized for frequent low-cost agent retrieval

---

## Layer 2: Index Docs

Purpose:
- Provide fast project orientation
- Minimize repeated Claude context rebuild
- Let a lower-cost Planner maintain status without redesigning strategy logic

Canonical files:
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`

Rules:
- Short, structured, and stable headings only
- No long tables unless absolutely necessary
- No full derivations or large evidence dumps
- Each item should point to a detailed source when deeper context is needed
- Prefer `See: doc/...` over repeating long explanations

---

## Role Boundaries

PM:
- Final decision-maker
- Approves priorities and Spec status transitions

Claude:
- Produces research, strategy judgment, counterarguments, and Spec drafts
- May reference index docs, but does not need to maintain them by default

Planner or other low-cost model:
- Updates `PROJECT_STATUS.md`
- Updates `RESEARCH_LOG.md`
- Summarizes and links to detailed docs
- Does not make final strategy judgment

Codex:
- Implements `Status: APPROVED` Specs only
- Does not maintain `RESEARCH_LOG.md` unless a Spec explicitly requires it

---

## Update Policy

### When to update detailed docs

Update detailed docs when:
- a research question is materially explored
- a major strategy conclusion changes
- a dated snapshot is needed for historical reconstruction
- HC/MC sync requires full evidence

### When to update index docs

Update index docs when:
- a new meaningful research conclusion appears
- a priority or blocker changes
- a Spec changes state in a way PM wants surfaced
- an open question changes status

---

## File Responsibilities

### `PROJECT_STATUS.md`

Answers:
- Where is the project now?
- What is active?
- What is blocked?
- What are the next priorities?

Should contain:
- current phase
- active approved specs
- top blockers
- open questions summary
- next priorities
- links to latest detailed status docs

Should not contain:
- long research arguments
- historical narrative across many dates
- parameter-by-parameter detail dumps

### `RESEARCH_LOG.md`

Answers:
- What has been researched?
- What was concluded?
- How confident are we?
- Should it enter Spec, stay on hold, or be dropped?

Each entry should contain:
- topic
- findings
- risks or counterarguments
- confidence
- next tests
- recommendation
- related spec or detailed doc

Should not contain:
- full experiment dumps
- long case-by-case tables
- duplicate copies of `research_notes.md`

---

## Recommended Flow

1. Claude or MC produces a detailed research output
2. Detailed evidence remains in `doc/` or sync artifacts
3. Planner writes a short entry into `RESEARCH_LOG.md`
4. Planner updates `PROJECT_STATUS.md` only if priorities, blockers, or active work changed
5. PM decides whether a conclusion becomes a Spec

---

## Sync Compatibility

HC/MC sync should keep using detailed packets.
The only new requirement is that sync outputs should include enough structured summary for the index layer to be updated without rereading the full packet.

Recommended minimum sync summary fields:
- Topic
- Findings
- Risks
- Confidence
- Recommendation
- Related detailed doc

---

## Practical Constraints

- `PROJECT_STATUS.md` should usually fit within 1 to 2 screens
- `RESEARCH_LOG.md` should be skimmable and append-only by default
- If a summary starts becoming long, move detail back to `doc/...`
- The detailed layer is for evidence
- The index layer is for navigation
