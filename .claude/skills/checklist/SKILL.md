---
name: checklist
description: >
  Emits the quality/acceptance checklist gate for a completed feature — deriving
  checklist items from the spec's acceptance criteria, verifying task completion,
  and delegating all gate execution to the existing `run-quality-gate` skill.
  Use this skill after implementation is complete, when the user says "run the
  checklist", "final check", "acceptance gate", or "is this feature done". Never
  reimplements the pytest/coverage/invariant logic owned by `run-quality-gate`.
  The SDD "implement" stage maps to the existing `core-dev`, `gui-dev`, and
  `access-dev` agents — no new coding agent is added by this pipeline.
version: 0.1.0
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity
    - P4 — Consistency
    - P5 — Context Budget Discipline
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P8 — Principles Inheritance
    - P9 — Role Separation
    - P10 — Exit-Status Determinism
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
  refs:
    - "R17 Engineering Disciplines; R18=P11 Programmatic Determinism: D:/Documentos/Recursos/Recursos IA/Repo Enhancer/repo-enhancer/orchestrator.md CONVENTIONS"
  custom:
    - id: C1
      name: Gate Delegation
      requires: this skill must not run pytest, grep invariants, or measure
        coverage directly. All gate execution is delegated to the `run-quality-gate`
        skill. A checklist verdict of PASS requires `run-quality-gate` to report
        GATE: PASS. A PASS verdict is not emitted if the gate was skipped or
        returned GATE: FAIL.
      rationale: Single-point gate ownership (P4) — `run-quality-gate` is
        Unit-Converter's authoritative gate; a parallel gate risks drift and
        undermines the invariant guarantee.
---

# Checklist

Emits the acceptance checklist for a completed feature and delegates quality-gate execution to `run-quality-gate`.

## Workflow

### Step 1: Gate — artifacts and analyze output must exist
Verify `.claude/sdd/spec.md` (Status: CLARIFIED) and `.claude/sdd/tasks.md` exist, and that an `analyze` report has been produced (in context or as a file). If any is missing, STOP: "Run `analyze` first."

### Step 2: Derive acceptance checklist items
From `.claude/sdd/spec.md` Acceptance Criteria section, generate one checklist item per criterion:

```
[ ] (FR-N/AC-M) <criterion text>
```

If `.claude/instructions/sdd-constitution.md` is available (load it), also emit one item per constitution-defined gate. Always include at minimum:

```
[ ] Headless core purity (CLAUDE.md Invariant 1): no GUI/transport import in unit_converter/core/*
[ ] Affine accuracy (CLAUDE.md Invariant 2): offset+scale units routed through offset path (if applicable)
[ ] No logic forking (CLAUDE.md Invariant 3): behavior changes in core/service, not forked in transports
[ ] Data-file integrity (CLAUDE.md Invariant 4): magnitudes.toml is canonical; UConverter.spec still valid
[ ] Coverage gate (CLAUDE.md Invariant 5): pytest --cov=unit_converter --cov-fail-under=90 passes
[ ] No secrets or artifacts (CLAUDE.md Invariant 6): no credentials or build output committed
[ ] Branch policy (CLAUDE.md Invariant 7): commits on enhancement branch, not main/master
[ ] Quality gate: run-quality-gate reports GATE: PASS
```

### Step 3: Verify task completion
Read `.claude/sdd/tasks.md`. For each task, check its Status field:
- `DONE` — satisfied.
- `TODO` or `IN PROGRESS` — checklist item flagged as incomplete.

Add one checklist item per task:
```
[ ] T001: <title> — <DONE|TODO|IN PROGRESS>
```

A checklist with any non-DONE task cannot yield a PASS verdict.

### Step 4: Delegate gate execution (C1)
Invoke the `run-quality-gate` skill. Record its full output verbatim under the "Quality Gate" heading. Do not filter, reinterpret, or re-run it.

If `run-quality-gate` is unavailable, record:
```
Quality Gate: BLOCKED — run-quality-gate skill not found; verdict cannot be determined.
```
and halt with BLOCKED status.

### Step 5: Emit checklist verdict
- `CHECKLIST: PASS` — all acceptance criteria items checked, all tasks DONE, run-quality-gate reports `GATE: PASS`.
- `CHECKLIST: FAIL` — otherwise; list each failing item.

Note: The "implement" stage of the SDD pipeline is executed by the existing `core-dev`, `gui-dev`, and `access-dev` agents. This checklist skill does not add or replace those agents — it gates their output.

## Output Format

```
CHECKLIST: <Feature Name>
Verdict: PASS | FAIL | BLOCKED
Date: <YYYY-MM-DD>

## Acceptance Criteria
- [x/ ] (FR-1/AC-1) <criterion text>
- [x/ ] (FR-1/AC-2) <criterion text>
...

## Task Completion
- [x/ ] T001: <title> — DONE | TODO | IN PROGRESS
...

## Quality Gate
<run-quality-gate output verbatim>

## Constitution Gates
- [x/ ] Headless core purity (Invariant 1)
- [x/ ] Affine accuracy (Invariant 2, if applicable)
- [x/ ] No logic forking (Invariant 3)
- [x/ ] Data-file integrity (Invariant 4)
- [x/ ] Coverage gate ≥90% (Invariant 5)
- [x/ ] No secrets or artifacts (Invariant 6)
- [x/ ] Branch policy (Invariant 7)

Verdict: CHECKLIST: PASS | FAIL | BLOCKED
Failing items: <list or "none">
```

## Self-Containment Index

This skill package contains everything needed for its complete usage:
- SKILL.md (this file): workflow, output format

External dependencies:
- `.claude/sdd/spec.md` — acceptance criteria source; must exist.
- `.claude/sdd/tasks.md` — task completion status; must exist.
- `run-quality-gate` skill (`.claude/skills/run-quality-gate/SKILL.md`) — invoked in Step 4; must be present for a PASS verdict. If missing: halt with BLOCKED.
- `.claude/instructions/sdd-constitution.md` — constitution-level gate items; loaded in Step 2 if available. If missing: use the default invariant checklist items stated in Step 2; note gap.

## Sources
- User requirement: SDD pipeline stage-6 skill (checklist) for Unit-Converter Group E.
- SDD pipeline: asset-metaprompting `references/software-development.md §2`.
- `references/claude.md §SKILL`; `templates/claude_skill.md`.
- `D:/Documentos/Recursos/Recursos IA/Repo Enhancer/repo-enhancer/orchestrator.md` CONVENTIONS (R17/R18).
