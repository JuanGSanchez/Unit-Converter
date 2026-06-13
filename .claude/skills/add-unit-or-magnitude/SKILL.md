---
name: add-unit-or-magnitude
description: >
  Extends the Unit-Converter units database with a new unit (name + factor under an existing
  magnitude) or a new magnitude (table of units), then adds the locking tests and verifies the core
  gate — preserving the multiplicative-vs-affine and prefix invariants. Use this skill when asked to
  "add a unit", "add a magnitude", "add <unit> to <magnitude>", or to extend `magnitudes.toml`.
  Pairs with the core-dev agent. For an affine (temperature/offset) magnitude, follow the affine note.
version: 0.1.0
---
# Add Unit or Magnitude

Procedural workflow for safely extending `unit_converter/data/magnitudes.toml` and locking the change with tests. Verify-before-edit; minimal change; core gate held.

## Workflow

### Step 1: Restate the request as data
Identify: target magnitude (new or existing), each unit name (canonical, including its symbol e.g. `stone (st)`), and each conversion factor relative to the magnitude's base unit. Confirm the unit model: multiplicative (default) or affine (temperature offset+scale). State this before editing.

### Step 2: Read the real TOML region
Read the `magnitudes.toml` header (schema rules) and the target `[Magnitude]`/`[Magnitude.units]` table. Confirm the base unit and existing names. Never edit on a remembered structure — the file is the source of truth.

### Step 3: Validate factors
Each factor must be a positive, non-zero, finite float (the loader's `_validate_factor` enforces this — match it). The base unit is the first entry (factor 1.0 by convention). For an affine magnitude, the unit record carries an `offset` field — do NOT add an offset to a multiplicative magnitude.

### Step 4: Edit the TOML minimally
Add the unit line(s) under `[Magnitude.units]`, or a new `[Magnitude]` + `[Magnitude.units]` table for a new magnitude. Use exact canonical names with Unicode superscripts where needed (no escaping). Change nothing else.

### Step 5: Confirm packaging still bundles the data file
The data file is bundled by `pyproject.toml [tool.setuptools.package-data]` and `packaging/UConverter.spec`. Adding rows to the existing file needs no packaging change; a NEW data file would (route to packaging-builder). Confirm `magnitudes.toml` is still the loaded path.

### Step 6: Add locking tests
In `tests/test_converter.py` (and `test_data_loader.py` for parsing/validation), assert: a representative conversion using the new unit is correct; an invalid factor is rejected at load; and — critically — every pre-existing magnitude's results are unchanged (regression). For an affine magnitude, assert the offset cases (e.g. 0°C→32°F) AND that increment conversions use scale only.

### Step 7: Run the core gate and report
Run `python -m pytest --cov=unit_converter --cov-report=term-missing --cov-fail-under=90`, READ the core total, confirm ≥90% and exit 0. Report the added rows, tests, gate output, and an acceptance checklist.

## Output Format

```
ADD UNIT/MAGNITUDE: <magnitude> += <unit(s)>
- Model: multiplicative | affine(offset)
- TOML edit: <table.units lines added>
- Factors validated (positive/finite): OK | REJECTED <unit>
- Tests added: <names> (incl. existing-magnitude regression)
- Core gate: <N>% (exit <code>)
- Checklist: <criterion: met/NOT met + evidence>
```

## Examples

### Example 1
**Input:** "Add stone (st) = 6350.29 g to Mass."
**Output:**
```
ADD UNIT/MAGNITUDE: Mass += "stone (st)"
- Model: multiplicative
- TOML edit: [Mass.units] "stone (st)" = 6350.29
- Factors validated (positive/finite): OK
- Tests added: test_convert_stone_to_gram, test_existing_mass_unchanged
- Core gate: 94% (exit 0)
- Checklist: stone converts ✓; invalid factor rejected ✓; existing Mass unchanged ✓
```

## Self-Containment Index

This skill package contains everything needed for its complete usage:
- SKILL.md (this file): workflow, output format, example

External dependencies (must be available in the execution environment):
- Python 3.11+ with the repo `[dev]` extras (pytest) installed: the gate command.

## Sources
- `unit_converter/data/magnitudes.toml` (schema + canonical names), `unit_converter/core/data_loader.py` (`_validate_factor`), `core/converter.py` (ratio vs affine path).
- `CLAUDE.md` (invariants 2, 4, 5), `docs/BACKLOG.md` (UC-I03 custom units, UC-I04 affine).
- `.claude/instructions/python-repo-conventions.md` (affine note, deterministic tests).
- references/claude.md §SKILL: frontmatter, description rules, body structure.
