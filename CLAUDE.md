# Unit-Converter — repository guide for Claude

A small, factor-based unit-conversion app. One pure core powers a PySide6 GUI, a
dual FastAPI (REST) + FastMCP access layer, and a PyInstaller build. This file is
the always-loaded ground truth for any Claude agent working here; the two in-repo
subagents below own the actual work.

## Principles Applied
- P1 Source-of-Truth Grounding — architecture and commands below are verified
  against the real code (`unit_converter/core/converter.py`, `pyproject.toml`),
  not assumed; read the named file before acting on it.
- P5 Context Budget Discipline — target files by search (Grep/Glob) and read only
  the region you need; this guide exists so agents need not re-discover layout.
- P6 Self-Containment — invariants, gate commands, and agent roles are stated here
  with explicit file paths; no implicit cross-references.
- P7 Reference Hygiene — every path named here resolves in the tree.

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
  deriving the four tool names `health`, `get_magnitudes`, `get_units`,
  `post_convert` from FastAPI operation ids), `main.py` (`run_server`). Read-only /
  compute-only: exactly those four operations, no writes.
- **GUI** — `unit_converter/gui/` (PySide6). Separate from core; not agent-driven.
- **Packaging** — `packaging/UConverter.spec`, `packaging/build.py` (PyInstaller).
- **Tests** — `tests/test_converter.py`, `tests/test_data_loader.py`,
  `tests/test_api_smoke.py`.

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
   `api/`, `data/`, `.pyw` omitted. A `fail_under` threshold is currently MISSING
   in `pyproject.toml` (backlog UC-B04) — restoring/holding it is gate discipline.
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

Role split: operator OPERATES the service; the dev agents EDIT their subsystem; reviewer GATES.
The former single `unit-converter-maintainer` is decomposed into core/gui/access/test/packaging/docs.

### Instructions (`.claude/instructions/`) — agents reference these, don't restate them
- **ai-execution-discipline.md** — anti-programmatic guardrails shared by all agents:
  verify-before-edit, assumption checks, minimal change, stop-and-confirm on irreversible/ambiguous,
  acceptance-criteria-driven done, context-budget (target-by-search, checkpoint ~70%, Gleaner=5).
- **python-repo-conventions.md** — stdlib-first, typing, headless-core purity, deterministic offline
  tests, no secrets, optional-dep groups, affine note.

### Skills (`.claude/skills/`)
- **add-unit-or-magnitude** — extend `magnitudes.toml` (unit/magnitude) + locking tests + gate.
- **expose-op** — thread a core fn/param through service→REST→derived MCP tool + error mapping + tests.
- **run-quality-gate** (`scripts/quality_gate.py`) — pytest+coverage + invariant grep sweep → PASS/FAIL.
- **build-release** (`scripts/build_release.py`) — wheel + PyInstaller build, install/import + clean-tree verify.

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
