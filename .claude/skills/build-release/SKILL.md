---
name: build-release
description: >
  Builds Unit-Converter release artifacts deterministically — the PEP 517 sdist+wheel and (optionally)
  the PyInstaller executable — then verifies install (`import unit_converter`), confirms the spec
  bundles the data file, and checks the tree stays clean (no artifact tracked). Use this skill when
  asked to "build a release", "make the wheel", "build the executable", or to verify the build
  pipeline before tagging. Pairs with the packaging-builder agent.
version: 0.1.0
---
# Build Release

Deterministic build + verify pipeline for Unit-Converter (setuptools wheel + PyInstaller executable), reporting buildability and clean-tree hygiene.

## Workflow

### Step 1: Locate the repo root and confirm prerequisites
Confirm the root holds `pyproject.toml`, `packaging/UConverter.spec`, and `packaging/build.py`. Confirm `[build-system] build-backend = "setuptools.build_meta"` (a wrong backend blocks the build — UC-B01; if wrong, STOP and route to packaging-builder).

### Step 2: Build and verify the wheel
Run `scripts/build_release.py --mode wheel`. It runs `python -m build`, then `pip install` of the wheel into an isolated check and `import unit_converter`. READ the output. A non-zero exit means the package is not installable — report and stop.

### Step 3: Build the executable (optional)
If an executable is requested, run `scripts/build_release.py --mode exe`. It runs `python packaging/build.py` and confirms the spec bundled `magnitudes.toml` (data file present in the build). Never edit the spec here — that is packaging-builder's job.

### Step 4: Verify clean tree
Run the hygiene check (`git status --ignored`): build output (`packaging/bin/`, `packaging/work/`, `dist/`, `build/`) must be ignored and no built binary tracked (UC-B02). A new tracked artifact is a FAIL.

### Step 5: Report
Report each stage PASS/FAIL with the proving evidence (build exit code, import result, data-file presence, clean-tree status). Do not claim a stage passed without reading its output.

## Output Format

```
BUILD RELEASE: PASS | FAIL
- Backend valid (setuptools.build_meta): OK | WRONG
- Wheel/sdist build + install + import: OK (exit 0) | FAIL <detail>
- Executable build (if requested): OK (data file bundled) | FAIL <detail> | skipped
- Clean tree (no tracked artifacts): OK | ISSUE <path>
Findings: <stage · evidence · owning agent> (or "none")
```

## Examples

### Example 1
**Input:** "Build the wheel and verify it installs."
**Output:**
```
BUILD RELEASE: PASS
- Backend valid (setuptools.build_meta): OK
- Wheel/sdist build + install + import: OK (exit 0)
- Executable build (if requested): skipped
- Clean tree (no tracked artifacts): OK
Findings: none
```

## Scripts

- `scripts/build_release.py` — runs the requested build mode, verifies install/import, confirms data-file bundling, and checks tree hygiene. Run when: building a release. Expected output: the report block; exit 0 on PASS. Deterministic given the source tree (PyInstaller binary bytes vary, but the verified properties — installability, data-file presence, clean tree — are stable).

## Self-Containment Index

This skill package contains everything needed for its complete usage:
- SKILL.md (this file): workflow, output format, example
- scripts/build_release.py: deterministic build + verify runner

External dependencies (must be available in the execution environment):
- Python 3.11+ with `build` and the repo `[dev]` extras (pyinstaller) installed.
- git: clean-tree hygiene check.

## Sources
- `CLAUDE.md` (invariants 4, 6; build/install commands), `docs/BACKLOG.md` (UC-B01, UC-B02), `pyproject.toml` (`[build-system]`, package-data), `packaging/UConverter.spec`, `packaging/build.py`.
- references/claude.md §SKILL: frontmatter, description rules, body structure.
