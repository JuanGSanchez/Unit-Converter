---
name: run-quality-gate
description: >
  Runs the Unit-Converter quality gate — pytest with core-scoped coverage at fail_under=90, plus a
  grep sweep of the repo invariants (no GUI import in core, no committed build artifacts, no
  asyncio.get_event_loop in tests, exact MCP tool-name assertion present) — and reports a single
  PASS/FAIL with evidence. Use this skill when verifying a change before commit, when asked to "run
  the quality gate", "check coverage", "verify invariants", or as the test-author/reviewer agents'
  done-check.
version: 0.1.0
---
# Run Quality Gate

One deterministic command sweep that proves the Unit-Converter coverage gate and the grep-checkable invariants, returning PASS/FAIL with evidence. Read-only except producing a report.

## Workflow

### Step 1: Locate the repo root
Confirm the working copy root holds `pyproject.toml` and `unit_converter/`. If not, ask for the repo path. All commands run from this root.

### Step 2: Run the coverage gate
Run the deterministic runner `scripts/quality_gate.py` (or the commands it wraps). It executes:
`python -m pytest --cov=unit_converter --cov-report=term-missing --cov-fail-under=90` and captures the printed core total and exit code. READ the output; do not assume green.

### Step 3: Sweep grep-checkable invariants
The runner also checks, and you confirm:
- Core purity: `grep -rnE "PySide|PyQt|tkinter|fastapi|mcp" unit_converter/core/` returns NOTHING.
- Tkinter regression: no `import tkinter` anywhere and no `.pyw` file present.
- Deprecated async: `grep -rn "get_event_loop().run_until_complete" tests/` returns NOTHING (UC-B06).
- Artifact hygiene: `git status --ignored` shows `packaging/bin/`, `packaging/work/`, `dist/`, `build/` ignored and no tracked binaries.
- MCP tool-name contract: `tests/test_api_smoke.py` contains an exact tool-name set assertion (UC-B07).

### Step 4: Report PASS/FAIL
PASS only if the gate exits 0 with core ≥90% AND every invariant sweep is clean. Otherwise FAIL, naming each failing check, its evidence, and the owning agent (test-author for coverage/tests; core-dev/gui-dev for a core purity violation; packaging-builder for artifacts).

## Output Format

A verdict block:
```
QUALITY GATE: PASS | FAIL
- Coverage: core <N>% (exit <code>)
- Core purity (no GUI/transport import in core): OK | VIOLATION <file:line>
- Tkinter regression (no tkinter/.pyw): OK | VIOLATION <path>
- Async (no get_event_loop().run_until_complete): OK | VIOLATION <file:line>
- Artifacts (build dirs ignored, tree clean): OK | ISSUE <path>
- MCP tool-name assertion present: OK | MISSING
Findings: <severity · check · evidence · owning agent> (or "none")
```

## Examples

### Example 1
**Input:** "Run the quality gate before I commit UC-B05."
**Output:**
```
QUALITY GATE: PASS
- Coverage: core 94% (exit 0)
- Core purity: OK
- Tkinter regression: OK
- Async: OK
- Artifacts: OK
- MCP tool-name assertion present: OK
Findings: none
```

## Scripts

- `scripts/quality_gate.py` — runs the coverage gate + invariant greps and prints the verdict block. Run when: verifying a change. Expected output: the verdict block above; exit 0 on PASS, non-zero on FAIL. Deterministic: same tree → same verdict.

## Self-Containment Index

This skill package contains everything needed for its complete usage:
- SKILL.md (this file): workflow, output format, example
- scripts/quality_gate.py: deterministic gate + invariant runner

External dependencies (must be available in the execution environment):
- Python 3.11+ with the repo `[dev]` extras installed (pytest, pytest-cov): the gate command.
- git: artifact-hygiene check.

## Sources
- `CLAUDE.md` (invariants 1,5,6; gate commands), `docs/BACKLOG.md` (UC-B04, UC-B06, UC-B07), `pyproject.toml` (coverage config).
- references/claude.md §SKILL: frontmatter, description rules, body structure.
