# Unit-Converter

A multi-magnitude unit converter for **Area, Data, Energy, Length, Mass, Power, Pressure, Time,
and Volume**. The project is structured around a pure Python core with no third-party runtime
dependencies, and optional front-ends for GUI interaction, REST API access, and MCP agent access.

---

## Architecture overview

```
unit_converter.core.converter   <- pure conversion logic (no UI, no transport)
unit_converter.core.data_loader <- validated TOML/legacy-TXT database loader
         |
    +----|----------+-------------------+
    v               v                   v
unit_converter.   unit_converter.     UConverter_UI.pyw
gui.app           api.main            (legacy Tkinter entry, retained)
(PySide6 GUI)     (REST + MCP server)
```

The core module is the single source of truth for all conversions. The GUI and API layers
delegate every computation to it.

---

## Python version

- **Floor: Python >= 3.11** (required for stdlib `tomllib`, used by the TOML data loader).
- **Build/CI ceiling: Python 3.13** (FastMCP 3.4.x declares support through 3.13; the rest
  of the stack supports 3.14). CPython 3.14 installs but is not yet in FastMCP's declared
  classifiers.
- The legacy Tkinter entry point (`UConverter_UI.pyw`) is retained for backward compatibility
  and runs on any Python >= 3.11 with Tkinter available (stdlib).

---

## Installation

The package uses optional dependency groups. Install only what you need.

### Core only (no GUI, no API)

```bash
pip install unit-converter
```

Installs the pure conversion core. No third-party runtime dependencies.

### PySide6 GUI

```bash
pip install "unit-converter[gui]"
```

Adds `PySide6~=6.11.1`. Requires Python 3.10–3.14.

### REST + MCP API server

```bash
pip install "unit-converter[api]"
```

Adds `fastmcp>=3.4,<4`, `fastapi>=0.136,<1`, `uvicorn>=0.49,<1`.

### GUI + API together

```bash
pip install "unit-converter[gui,api]"
```

### Development (tests + packaging tools)

```bash
pip install "unit-converter[dev]"
```

Adds `pytest~=9.0.3`, `pytest-cov~=7.1.0`, `pyinstaller~=6.20.0`.

### From source (editable)

```bash
git clone https://github.com/JuanGSanchez/Unit-Converter
cd Unit-Converter
pip install -e ".[gui,api,dev]"
```

---

## Running

### PySide6 GUI (primary entry point)

```bash
unit-converter-gui
```

Launches the PySide6 desktop application. Requires the `[gui]` optional group.

### REST + MCP server (Streamable HTTP)

```bash
unit-converter-api
```

Starts the combined FastAPI REST + FastMCP server via uvicorn on `0.0.0.0:8000`.
Requires the `[api]` optional group.

| Surface | URL |
|---------|-----|
| REST (Swagger UI) | http://localhost:8000/docs |
| REST (ReDoc) | http://localhost:8000/redoc |
| MCP (Streamable HTTP) | http://localhost:8000/mcp |

### MCP server over stdio (for CLI / local agent clients)

```bash
unit-converter-mcp
```

Runs the MCP server over stdio. Suitable for Claude Desktop and other MCP-aware CLI tools.
Requires the `[api]` optional group.

### Legacy Tkinter entry point

```bash
unit-converter
# or directly:
python UConverter_UI.pyw
```

The original Tkinter UI is retained for backward compatibility. It is no longer the primary
entry point and may be removed in a future release.

---

## Running tests

```bash
pytest
# with coverage report:
pytest --cov=unit_converter --cov-report=term-missing
```

The coverage gate is **>= 90% line coverage on `unit_converter/core/`**. GUI and API transport
layers are excluded from the gate. Measured coverage: 91%.

---

## Building a standalone executable

A PyInstaller spec is provided in `packaging/`. See
[packaging/README-packaging.md](packaging/README-packaging.md) for the full build guide.

Quick start on Windows:

```bat
pip install "pyinstaller~=6.20.0" "PySide6~=6.11.1"
packaging\build_windows.bat
```

Output: `packaging\bin\UConverter\UConverter.exe` — a self-contained windowed executable
that bundles the TOML database and the PySide6 Qt libraries. No Python installation is
required to run it.

Note: the spec file is committed; the built executable is not — run the build scripts
locally or in CI to produce it.

---

## Extending units

The unit database lives in `unit_converter/data/magnitudes.toml` (TOML format, primary) with
`unit_converter/data/Magnitudes.txt` retained as a legacy fallback. See
[docs/usage-guide.md](docs/usage-guide.md#extending-the-unit-database) for the data format
and how to add new magnitudes and units.

---

## Agent / programmatic access

See [docs/agent-access.md](docs/agent-access.md) for the REST endpoints, MCP tools, transport
options, and example calls. An in-repo Claude agent operating guide is at
[docs/agent-operating-doc.md](docs/agent-operating-doc.md).

---

## License

This project is licensed under the **GPL-3.0-only** license.

The PySide6 GUI component uses **Qt for Python (PySide6)** distributed under the
**LGPLv3** license. LGPLv3 is compatible with GPL-3.0. PyInstaller bundles Qt as shared
libraries (dynamic linking), satisfying the LGPL relinkability condition. Distributions of
the packaged executable must include:
- A prominent notice that the software uses Qt under LGPL-3.0.
- Copies of the LGPL-3.0 and GPL-3.0 license texts.
- A means for users to relink against a modified Qt (e.g., a pointer to Qt source).

See [qt.io/development/open-source-lgpl-obligations](https://www.qt.io/development/open-source-lgpl-obligations)
for the full LGPL obligations.
