# Python Repo Conventions — Unit-Converter

Python engineering rules for THIS repo. Agents reference this instead of restating. Scope: every
`.py` edit/addition in `unit_converter/`, `tests/`, `packaging/`.

## Principles Applied
Python best-practices instruction for Unit-Converter (PEP 8 + pytest; UC tailoring: conversion accuracy, affine/factor units, no logic forking in transports). Engineering disciplines (R17): `repo-enhancer/orchestrator.md` CONVENTIONS.

- P1 Source-of-Truth Grounding — conventions verified against `pyproject.toml` and the real tree.
- P2 Full Determinism — rules are prescriptive; no per-case exceptions beyond those stated below.
- P3 Systematicity — all `.py` edits follow these rules; no selective application.
- P4 Consistency — same typing/stdlib/test bar across core, api, gui, packaging.
- P5 Context Budget Discipline — read only the relevant module region before editing.
- P6 Self-Containment — all constraints stated here; no implicit project conventions assumed.
- P7 Reference Hygiene — cite CLAUDE.md invariants by number; do not restate them.
- P8 Principles Inheritance — every agent referencing this instruction applies these rules to Python edits.
- P9 Role Separation — conventions apply within each subsystem boundary; cross-boundary changes route to the correct agent.
- P10 Exit-Status Determinism — gate exit 0 = PASS; non-zero = FAIL; no soft interpretation.
- P11 Programmatic Determinism — prefer deterministic test fixtures and scripts; avoid probabilistic assertions.
- P12 Maximal-Effort Completeness — new code ships with tests; coverage gate always met; never the bare minimum.
- P13 Token Economy — terse test names and docstrings; no redundant assertions.

## Rules

1. Always prefer the stdlib. The core has ZERO third-party runtime deps (`pyproject.toml`
   `dependencies = []`): use `tomllib`, `decimal`/`math`, `dataclasses`, `pathlib` — not NumPy
   (`np.round`/`np.inf` were removed on purpose). A new third-party dep is a stop-and-confirm action
   (ai-execution-discipline Rule 4) and only ever lands under the right `[project.optional-dependencies]`
   group (`gui`/`api`/`dev`), never in `dependencies`.
2. Always keep the core headless and pure (CLAUDE.md invariant 1): never import Tkinter/Qt/PySide,
   FastAPI, MCP, or any GUI/transport symbol inside `unit_converter/core/*`. Core is import-safe with
   no optional deps installed. The `headless-core-guard` hook blocks violations.
3. Always type public functions: parameter + return annotations on every function in
   `core/`, `api/service.py`, and new helpers. Match the existing style (`list[str]`, `dict`,
   `"str | None"` string-form unions for the 3.11 floor). Floor is `requires-python>=3.11` (needs
   stdlib `tomllib`); CI target 3.13 (FastMCP ceiling) — do not use 3.13-only syntax.
4. Always keep tests deterministic and offline: no real network, clock, or filesystem-of-record
   dependence. Mock the rates source (`core/rates.py`) — never hit Frankfurter live; use `tmp_path`
   for history/custom-unit files; assert exact floats with tolerance, not snapshots of wall-clock.
   Use `asyncio.run(...)`, never the deprecated `asyncio.get_event_loop().run_until_complete(...)`.
5. Always change behavior in the shared core/service (CLAUDE.md invariant 3), never by forking logic
   into `rest.py` or `mcp_server.py`. MCP tool names derive from FastAPI operation ids — changing an
   operation id changes the tool name and the operator/docs contract.
6. Never commit secrets, credentials, or build artifacts (CLAUDE.md invariant 6). No API keys, tokens,
   or `.env` values in source; rates/currency code reads config, not literals. The
   `no-secrets-or-artifacts` hook blocks violations.
7. Always preserve the core coverage gate (CLAUDE.md invariant 5): `core/`-scoped `fail_under = 90`.
   New core code ships with tests; never lower the threshold or widen the omit list to pass.

## Conditional rules
- If a unit is affine (temperature offset+scale), then route it through the offset path in `convert`
  and never push an offset through the multiplicative ratio formula (CLAUDE.md invariant 2).
- If adding a magnitude/unit, then edit `unit_converter/data/magnitudes.toml` (canonical), keep
  factors positive non-zero finite, and confirm `packaging/UConverter.spec` still bundles the data
  file (CLAUDE.md invariant 4).

## Sources
- `pyproject.toml` (deps=[], optional groups, requires-python, coverage config), `CLAUDE.md`
  invariants 1–7, real tree (`core/converter.py`, `core/rates.py`, `tests/`).
- references/claude.md §INSTRUCTION: structure, negative-instruction patterns.
