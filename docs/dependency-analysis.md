# Dependency Analysis & Import-Health Check

Initial analysis and dependency verification of the Unit-Converter repository.
Reference doc — factual, verified against the live tree on 2026-06-14. Not a
changelog; re-run the checks below if the environment changes.

## Environment

- **Python runtime:** 3.13.13 (CI/build target per `pyproject.toml`).
- **Python floor:** 3.11 (`requires-python = ">=3.11"`), required for the stdlib
  `tomllib` module used by `unit_converter/core/data_loader.py`.
- **Python ceiling note (per `pyproject.toml`):** FastMCP 3.4.x declares support
  through Python 3.13 only; the rest of the stack (PySide6, FastAPI, uvicorn,
  PyInstaller) supports 3.14. CI stays on 3.13 until FastMCP publishes a 3.14
  classifier.

## Dependency model

The **pure core has zero third-party runtime dependencies** — `pyproject.toml`
declares `dependencies = []`. All front-end and tooling libraries live in
optional-dependency groups (`[project.optional-dependencies]`):

- `gui` — PySide6
- `api` — fastmcp, fastapi, uvicorn
- `dev` — pytest, pytest-cov, pyinstaller

This keeps `import unit_converter.core.*` installable and runnable with nothing
beyond the standard library.

## Installed / verified library versions

Versions observed in the active environment on 2026-06-14:

| Library      | Version  | Group (pyproject)        |
|--------------|----------|--------------------------|
| PySide6      | 6.11.1   | `gui`                    |
| FastAPI      | 0.136.3  | `api`                    |
| FastMCP      | 3.4.2    | `api` (+ `fastmcp-slim`) |
| uvicorn      | 0.49.0   | `api`                    |
| pydantic     | 2.13.4   | transitive (FastAPI)     |
| httpx        | 0.28.1   | transitive / rates I/O   |
| pytest       | 9.0.3    | `dev`                    |
| pytest-cov   | 7.1.0    | `dev`                    |
| coverage     | 7.14.1   | transitive (pytest-cov)  |
| pyinstaller  | 6.20.0   | `dev`                    |
| setuptools   | 82.0.1   | build backend            |

## Import-health result

All 14 importable package modules import cleanly:

```
unit_converter.api.main           unit_converter.core.converter
unit_converter.api.mcp_server     unit_converter.core.data_loader
unit_converter.api.rest           unit_converter.core.expr
unit_converter.api.service        unit_converter.core.history
                                  unit_converter.core.rates
unit_converter.gui.app            unit_converter.gui.main_window
unit_converter.gui.resources
```
(plus the `api`, `core`, `data`, `gui` package roots).

### Fixed bug — `QShortcut` import location

A now-FIXED import bug previously broke `unit_converter.gui.app` and
`unit_converter.gui.main_window`:

```
ImportError: cannot import name 'QShortcut' from 'PySide6.QtWidgets'
```

`QShortcut` was being imported from `PySide6.QtWidgets`, but in Qt6 / PySide6 it
lives in `PySide6.QtGui`. It is now imported from `QtGui`
(`unit_converter/gui/main_window.py`), and both GUI modules import cleanly.

## Qt6 import-location gotchas

In PySide6 / Qt6, several classes moved from `QtWidgets` (their Qt5 home) to
`QtGui`. Importing them from `QtWidgets` raises `ImportError`. Notable movers:

- `QShortcut`
- `QAction`
- `QKeySequence`
- `QActionGroup`

**Recommendation:** import GUI action / shortcut / key-sequence classes from
`PySide6.QtGui`, not `PySide6.QtWidgets`, when porting Qt5-era code.

## Test / gate status

- **Suite:** 272 passed, 1 skipped.
- **Coverage gate:** core coverage gate green (`fail_under = 90` in
  `[tool.coverage.report]`; `--cov-fail-under=90` in pytest `addopts`). The gate
  is scoped to `unit_converter` with `gui/`, `api/`, and `data/` omitted, so it
  lands on `core/`.

Reproduce:

```
python -m pytest -q
```
