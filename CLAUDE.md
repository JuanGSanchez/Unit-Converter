# Unit-Converter — repository guide for Claude

A small, factor-based unit-conversion app. One pure core powers a PySide6 GUI, a
dual FastAPI (REST) + FastMCP access layer, and a PyInstaller build. This file is
the always-loaded ground truth for every Claude Code session here: it is injected
into context automatically at session start, so the **Operating contract** below
is in force from the first turn — the active session acts as the canonical
orchestrator and routes work to the in-repo agent suite.

## Operating contract (canonical orchestration — active every session)
This file is auto-loaded into every Claude Code session here, so this contract
governs from the first turn — the **active session is the canonical
orchestrator**; no agent has to be invoked to "switch it on." Apply it by default
to every request:
- **Scope first.** Read the relevant invariants below and verify real current
  state (the backlog is stale by policy) before acting.
- **Multi-subsystem or multi-step work** → act as orchestrator: decompose into
  bounded, single-owner tasks; dispatch each to its owning specialist subagent
  (Task tool) per the AI-asset roster below; sequence by dependency; parallelize
  only genuinely independent tasks; then gate every applied change through
  `reviewer` (PASS/FAIL) before reporting done. Do not edit across subsystem
  boundaries ad hoc — keep the role split.
- **Single-subsystem work** → dispatch to that one owner (a trivial in-boundary
  change may be made directly), then gate through `reviewer`.
- **Runtime/behavior evidence** → drive the live service through
  `unit-conversion-operator`; never present a self-run conversion as proof a
  change works.
- **Always** honor the 7 invariants, the coverage gate, and the branch policy
  (enhancement branch, never `main`/`master`); never commit unless asked.
- **Default to maximal-effort completeness.** Carry every request, task, doubt, and
  investigation through to a definitive end, and build solutions that fully cover the
  requirement and are ready to grow — never the bare minimum — unless the user
  explicitly relaxes the scope. This governs coverage and depth, not verbosity: it
  never overrides minimal-diff or economical prose. See
  `.claude/instructions/ai-execution-discipline.md` Rule 7; a standing user-level
  SessionStart hook (`$HOME/.claude/hooks/claude-orchestration-contract.py`) reinforces
  it across sessions.
- **The `.claude/agents/orchestrator.md` subagent is the dispatchable embodiment
  of this same contract** — invoke it (`@agent-orchestrator`, or via the Task
  tool) when you want a dedicated Opus 4.8 coordinator or nested delegation
  (requires Claude Code ≥ v2.1.172). The authority is THIS contract, always
  active regardless of build; the subagent is one way to run it, not a
  precondition for it.
- **Meta-work on the asset system itself** (authoring or redesigning agents,
  skills, hooks, or this contract) is handled by the top-level session with the
  asset-metaprompting / orchestrator-design skills — not delegated to the
  orchestrator subagent, which declares asset design out of scope.

## Principles Applied
Deployment target: `claude_code` (real `.claude/` tree — agents, skills, hooks, and `settings.json` are live deployed assets, not specs).
External dependency (C7): `$HOME/.claude/hooks/claude-orchestration-contract.py` is the user-level global SessionStart hook — relied upon as-is; no per-project copy required or created.
Engineering disciplines (R17) and programmatic determinism (R18/P11): `repo-enhancer/orchestrator.md` CONVENTIONS — hooks enforce deterministic invariants; prefer scripts/tools over prose for deterministic checks.

- P1 Source-of-Truth Grounding — architecture and commands below are verified
  against the real code (`unit_converter/core/converter.py`, `pyproject.toml`),
  not assumed; read the named file before acting on it.
- P2 Full Determinism — hooks and gate commands produce deterministic outcomes; no inference-based invariant checks.
- P3 Systematicity — the operating contract above is the mandatory execution order from the first turn.
- P4 Consistency — the same agent roster, invariants, and gate commands apply across all sessions.
- P5 Context Budget Discipline — target files by search (Grep/Glob) and read only
  the region you need; this guide exists so agents need not re-discover layout.
- P6 Self-Containment — invariants, gate commands, and agent roles are stated here
  with explicit file paths; no implicit cross-references.
- P7 Reference Hygiene — every path named here resolves in the tree.
- P8 Principles Inheritance — every agent and skill in `.claude/` carries a Principles Applied block derived from this canonical list.
- P9 Role Separation — active session coordinates and gates; dev agents implement; reviewer gates; operator runs the service. No ad-hoc cross-role edits.
- P10 Exit-Status Determinism — reviewer returns PASS/FAIL; agents return COMPLETED/BLOCKED; no soft verdicts.
- P11 Programmatic Determinism — hooks enforce core purity, secrets/artifacts, and Tkinter regression deterministically, not by prose reasoning.
- P12 Maximal-Effort Completeness — carry every request to a definitive end; fully cover the requirement (operating contract above; ai-execution-discipline.md Rule 7).
- P13 Token Economy — economical prose; this guide provides layout so agents target-by-search rather than loading the full tree.

## Architecture (one core, many faces)
- **Pure core** — `unit_converter/core/converter.py` (`list_magnitudes`,
  `list_units`, `convert(magnitude, value, from_unit, to_unit, from_order="1",
  to_order="1")`, `_clamp_input`) and `unit_converter/core/data_loader.py`
  (`load_magnitudes`, `_validate_factor`, `_apply_superscripts`). **No GUI imports
  here, ever.** Conversion is multiplicative factor-ratio relative to a base unit;
  SI prefixes are base-10 except the `Data` magnitude, which uses IEC base-1024.
- **Units data** — `unit_converter/data/magnitudes.toml` (canonical). Legacy
  `Magnitudes.txt` is retained but its unit names may differ (see backlog UC-B09).
- **Access layer (one shared core, two transports)** —
  `unit_converter/api/service.py` (shared), `rest.py` (FastAPI; maps `ValueError`
  → HTTP 422 via `_value_error_to_422`), `mcp_server.py` (FastMCP `from_fastapi`,
  deriving 16 MCP tool names from the FastAPI operation ids), `main.py`
  (`run_server`). 16 operations span discovery, convert, compound, currency,
  history, and custom units — including a small set of state-changing operations
  (currency rate refresh, history/favorites record + clear, add custom unit), so
  it is NOT read-only. The authoritative tool-name list is `_EXPECTED_TOOL_NAMES_16`
  in `tests/test_api_routes.py`.
- **GUI** — `unit_converter/gui/` (PySide6). Separate from core; not agent-driven.
- **Packaging** — `packaging/UConverter.spec`, `packaging/build.py` (PyInstaller).
- **Tests** — `tests/test_converter.py`, `tests/test_data_loader.py`,
  `tests/test_api_smoke.py`, `tests/test_api_routes.py` (16-route / 16-tool-name
  suite), `tests/test_expr.py`, `tests/test_history.py`, `tests/test_rates.py`,
  `tests/test_service_validation.py`.

## Invariants (do not break these)
1. Core has no Tkinter/Qt/PySide imports.
2. Conversion-factor accuracy + round-trip correctness; affine/temperature units
   (offset + scale) are handled distinctly from multiplicative scale factors.
3. Behavior changes go in the shared core/service — not forked into REST or MCP.
   Changing a FastAPI operation id changes the derived MCP tool name and the
   operator-agent/docs contract.
4. The PyInstaller spec keeps building (datas + hidden imports stay valid).
5. The `core/`-scoped pytest coverage gate stays green at ≥90%. The gate is
   scoped via `[tool.coverage.run] source=["unit_converter"]` with `gui/`,
   `api/`, `data/`, `.pyw` omitted. The `fail_under = 90` threshold is now enforced
   in `pyproject.toml` in both places — `[tool.coverage.report] fail_under = 90`
   and `--cov-fail-under=90` in `[tool.pytest.ini_options] addopts` (UC-B04
   resolved) — holding it green is gate discipline.
6. Never commit secrets or build artifacts (`packaging/bin/`, `packaging/work/`,
   `dist/`, `build/`).
7. Commits land on the enhancement branch, never `main`/`master`.

## Gate commands (run, then read the output)
- Core coverage gate: `python -m pytest --cov=unit_converter --cov-report=term-missing --cov-fail-under=90`
- Targeted tests: `python -m pytest tests/test_converter.py -q`
- Build/install check: `python -m build` then `pip install .` (clean venv), `import unit_converter`.
- Artifact hygiene: `git status --ignored` (build dirs ignored, tracked tree clean).

## AI asset suite (single source of truth — use these; don't do their jobs ad hoc)

### Agents (`.claude/agents/`)
- **orchestrator** — the dispatchable embodiment of the **Operating contract** above (the canonical
  orchestration always runs in the active session; this subagent is its invokable form). Plans
  multi-subsystem work, decomposes it into bounded single-owner tasks, dispatches the specialist
  agents below as subagents (Task tool), then gates every applied change through reviewer. Coordinates
  and gates; holds no Edit/Write — never edits files itself. Requires Claude Code ≥ v2.1.172 (nested
  subagents); else it emits a dispatch plan for the top-level session. Invoke it for a dedicated
  Opus 4.8 coordinator or nested delegation — it is not a precondition for orchestration.
- **unit-conversion-operator** — drives the RUNNING service via the 16-op MCP/REST access layer
  (no GUI): convert, compound, currency, history, custom units, discovery. Operates, never edits.
- **core-dev** — headless conversion core: `magnitudes.toml`, factors, ratio/affine math, prefixes,
  sig-figs, dimensional guard, `expr.py`/`rates.py`/`history.py` (UC-B05, UC-I01/I02/I04/I06).
- **gui-dev** — PySide6 GUI; thin client over the core, hover-tooltip invariant, non-masking error
  handling (UC-B03, UC-I07).
- **access-dev** — dual MCP+REST over one shared service: thread params, error-code mapping,
  boundary validation, bind, operation-id→tool-name contract (UC-I01/I02, UC-B07/B08, gated I03/I05).
- **test-author** — pytest + core coverage-gate custody (≥90%), deterministic offline tests, exact
  MCP tool-name assertion (UC-B04/B06/B07).
- **packaging-builder** — PEP 517 backend + PyInstaller spec/build + artifact hygiene (UC-B01/B02).
- **docs-writer** — keeps README / operating doc / access docs / agent contracts truthful to code
  (UC-I01..I06, UC-B09).
- **reviewer** — read-only correctness + security/boundary gate: verifies the 7 invariants, surface
  safety, secrets/artifacts, coverage; returns PASS/FAIL. Authors no fix.

Role split: the active session is the canonical orchestrator (per the Operating contract), with the
orchestrator subagent as its dispatchable form — both COORDINATE (dispatch + gate, never edit);
operator OPERATES the service; the dev agents EDIT their subsystem; reviewer GATES. The roster is
split by subsystem: core/gui/access/test/packaging/docs.

Model assignment (per-agent `model:` frontmatter, capability-tiered): **Opus 4.8**
(`claude-opus-4-8`) — orchestrator, reviewer (coordination + judgment gate). **Sonnet 4.6**
(`claude-sonnet-4-6`) — core-dev, access-dev, gui-dev, test-author (substantive implementation +
test correctness). **Haiku 4.5** (`claude-haiku-4-5-20251001`) — docs-writer, packaging-builder
(well-scoped doc/config edits). unit-conversion-operator inherits the session model. The `model:`
field may be overridden by `CLAUDE_CODE_SUBAGENT_MODEL` and is ignored on some Claude Code builds.

### Instructions (`.claude/instructions/`) — agents reference these, don't restate them
- **ai-execution-discipline.md** — anti-programmatic guardrails shared by all agents:
  verify-before-edit, assumption checks, minimal change, stop-and-confirm on irreversible/ambiguous,
  acceptance-criteria-driven done, context-budget (target-by-search, checkpoint ~70%, Gleaner=5).
- **python-repo-conventions.md** — stdlib-first, typing, headless-core purity, deterministic offline
  tests, no secrets, optional-dep groups, affine note.
- **sdd-constitution.md** — SDD stage-gate rules governing the specify→clarify→plan→tasks→analyze→checklist pipeline.
- **pyside6-best-practices.md** — PySide6 patterns; referenced by `gui-dev`.

### Skills (`.claude/skills/`)
- **add-unit-or-magnitude** — extend `magnitudes.toml` (unit/magnitude) + locking tests + gate.
- **expose-op** — thread a core fn/param through service→REST→derived MCP tool + error mapping + tests.
- **run-quality-gate** (`scripts/quality_gate.py`) — pytest+coverage + invariant grep sweep → PASS/FAIL.
- **build-release** (`scripts/build_release.py`) — wheel + PyInstaller build, install/import + clean-tree verify.
- **SDD pipeline:** `specify`→`clarify`→`plan`→`tasks`→`analyze`→`checklist`; `analyze`/`checklist` back-ended by `run-quality-gate`; governed by `.claude/instructions/sdd-constitution.md`.

### Hooks (`.claude/settings.json` + `.claude/hooks/`) — harness-enforced invariants
- **headless_core_guard.py** (PreToolUse) — blocks a GUI/transport import into `unit_converter/core/*`
  (invariant 1).
- **no_secrets_or_artifacts.py** (PreToolUse) — blocks writing a secret or a build-artifact path
  (invariant 6 / UC-B02).
- **tkinter_regression_guard.py** (PreToolUse) — blocks any `import tkinter` or `.pyw` reappearing.
- **coverage_gate_reminder.py** (PostToolUse, non-blocking) — reminds to run the gate after touching
  core/ or tests/ (invariant 5 / UC-B04).

## Backlog
The authoritative work list is `docs/BACKLOG.md`, referenced by item ID
(`UC-B01`…`UC-B09`, `UC-I01`…`UC-I07`). Each item is self-contained with
acceptance criteria; backlog line references are stale by policy — re-verify
locations before editing.
