# AI Execution Discipline — shared by every Unit-Converter agent

Behavioral contract all in-repo agents reference instead of restating. Counters literal/programmatic
execution and protects the context budget. Scope: every code/data/test/doc/build action in this repo.

## Principles Applied
Engineering disciplines (R17) and programmatic determinism (R18/P11): `repo-enhancer/orchestrator.md` CONVENTIONS.

- P1 Source-of-Truth Grounding — act only on the real file you just read; backlog `File:line` refs are
  stale by policy (`docs/BACKLOG.md` preamble) — re-confirm before editing.
- P2 Full Determinism — the verify→act→prove loop is a fixed protocol; no step skipped or inferred.
- P3 Systematicity — the verify→act→prove loop below is the mandatory order for every change.
- P4 Consistency — the same discipline (verify-before-edit, minimal change, done = all criteria met) applies across every agent and item.
- P5 Context Budget Discipline — target by search; checkpoint at ~70%.
- P6 Self-Containment — all rules stated here; no implicit agent-specific behavior assumed.
- P7 Reference Hygiene — cite CLAUDE.md / BACKLOG IDs / file:symbol; never restate their content here.
- P8 Principles Inheritance — every agent referencing this instruction applies these rules.
- P9 Role Separation — act within the declared owned surface; cross-boundary edits require escalation.
- P10 Exit-Status Determinism — done means every acceptance criterion is explicitly met with evidence.
- P11 Programmatic Determinism — run deterministic gates/scripts rather than reasoning about their result (Rule 6).
- P12 Maximal-Effort Completeness — carry every task, doubt, and investigation to a definitive end and
  fully cover the item; governs coverage/depth, not verbosity, and never overrides Rule 3 (minimal
  diff). Relax only on explicit user scope-down.
- P13 Token Economy — acceptance checklists and gate output quoted concisely; no padding.

## Rules

1. Never edit a location you have not just read. Before any Edit, Grep the symbol and Read only its
   region; confirm the symbol still exists at that line. No edit on a remembered or backlog-quoted line.
2. Always state assumptions before acting, then verify each against the real file: the unit model
   (multiplicative ratio vs affine offset+scale, see `core/converter.py`), the prefix table (SI base-10
   vs IEC base-1024 for `Data`), and the layer (core vs service vs transport vs GUI). An unverified
   assumption is a bug waiting to ship.
3. Always make the MINIMAL change that satisfies the acceptance criteria. Do not refactor, rename, or
   reformat unrelated code. Every changed line must trace to the item.
4. Stop and confirm before any irreversible or ambiguous action: `git rm`/untracking, adding a
   third-party dependency, adding a state-changing/network endpoint (expands the access surface — F4
   tool-count + access-layer safety re-approval), or any destructive git/filesystem command. State the
   action and the options; do not pick one silently.
5. Always treat the item's acceptance criteria as the definition of done. Restate them verbatim up
   front, and finish with a checklist marking each criterion met (with evidence: test name, gate
   output, file:symbol, doc edit) or NOT met. Never claim done while any criterion is unmet or any
   CLAUDE.md invariant is unproven.
6. Always run the named gate and READ its output before claiming a gate passed. No "done" on an
   assumed-green gate; quote the printed result.
7. Always pursue the item to completeness: resolve every sub-part, doubt, and implied follow-up the
   acceptance criteria require — never stop at a partial or bare-minimum pass — while keeping the
   change itself minimal (Rule 3) and the response economical. Maximal effort means full coverage and
   definitive follow-through, not extra scope or verbosity; relax only when the user explicitly scopes
   the effort down.

## Conditional rules
- If understanding a change would require reading 5 or more files, then summarize what you have and
  emit a GATHERING REQUEST for that file set rather than loading them all (Gleaner threshold = 5).
- If context grows past ~70% before the item is verified, then write
  `docs/checkpoint-<agent>-<item>-<timestamp>.md` (item, files touched, edits applied, gate status,
  remaining criteria) so work resumes without re-discovery.
- If an acceptance criterion cannot be met without violating a CLAUDE.md invariant, then STOP and
  report the conflict (criterion, invariant, 2–3 options) — do not break the invariant.

## Sources
- `CLAUDE.md` (repo invariants, gate commands), `docs/BACKLOG.md` (item IDs, stale-line policy).
- references/claude.md §INSTRUCTION: XML/markdown directive structure, negative-instruction patterns.
