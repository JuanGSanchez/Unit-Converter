# Unit-Converter

A multi-magnitude unit converter for **Area, Data, Energy, Length, Mass, Power, Pressure, Time,
and Volume**, plus **live currency conversion** via the Frankfurter API. Structured around a pure
Python core with no third-party runtime dependencies, and optional front-ends for GUI interaction,
REST API access, and MCP agent access.

---

## Architecture overview

```
unit_converter.core.converter   <- pure conversion logic (no UI, no transport)
unit_converter.core.data_loader <- validated TOML database loader
unit_converter.core.rates       <- Frankfurter currency rate cache
unit_converter.core.history     <- conversion history + favorites persistence
unit_converter.core.expr        <- compound/derived unit expression parser
         |
    +----|----------+
    v               v
unit_converter.   unit_converter.
gui.app           api.main
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

---

## Features

- **Significant-figures / precision control** — pass `sig_figs` to round results to N significant figures.
- **Dimensional-compatibility guard** — converting incompatible units raises `IncompatibleUnitsError` (HTTP 422).
- **Affine / temperature handling** — offset + scale units (e.g. °C ↔ °F ↔ K) convert correctly via the affine path.
- **Live currency conversion** — Frankfurter API with a dated cached table and offline fallback.
- **Compound / derived units** — parse and convert expressions such as `km/h → m/s`.
- **Custom user-defined units** — add units at runtime via the API or GUI; persisted to `~/.unit-converter/custom.toml`.
- **Conversion history + favorites** — recent conversions persist across sessions; entries can be favorited and labeled.
- **PySide6 GUI with hover tooltips** — every widget carries a `QToolTip` description.

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

Adds `PySide6~=6.11.1`.

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

### PySide6 GUI

```bash
unit-converter-gui
```

Launches the PySide6 desktop application. Requires the `[gui]` optional group.
Equivalent invocation from source: `python -m unit_converter.gui.app`.

**Features:** Bidirectional live conversion, order-of-magnitude prefixes (SI/IEC), digit sweep, conversion history and favorites, custom units, right-click context menu (Settings, History, Add Custom Unit, About, Exit), and Light/Dark theming with per-widget color picker. See [docs/usage-guide.md](docs/usage-guide.md) for detailed usage.

### REST + MCP server (Streamable HTTP)

```bash
unit-converter-api
```

Starts the combined FastAPI REST + FastMCP server via uvicorn on `127.0.0.1:8000` (loopback only, local access).
Requires the `[api]` optional group.

To expose the server to other machines on the network, override the host:

```bash
unit-converter-api --host 0.0.0.0
```

| Surface | URL |
|---------|-----|
| REST (Swagger UI) | http://localhost:8000/docs |
| REST (ReDoc) | http://localhost:8000/redoc |
| MCP (Streamable HTTP) | http://localhost:8000/mcp |
| Health check | http://localhost:8000/health |

Equivalent invocation (default): `uvicorn unit_converter.api.main:app --host 127.0.0.1 --port 8000`

Equivalent invocation (network access): `uvicorn unit_converter.api.main:app --host 0.0.0.0 --port 8000`

See [docs/agent-access.md](docs/agent-access.md) for REST endpoint reference and example calls.

### MCP server over stdio (for CLI / local agent clients)

```bash
unit-converter-mcp
```

Runs the MCP server over stdio. Suitable for Claude Desktop and other MCP-aware CLI tools.
Requires the `[api]` optional group.

Equivalent invocation: `python -m unit_converter.api.mcp_server`

Configure Claude Desktop or other MCP clients as shown in [docs/agent-access.md § stdio](docs/agent-access.md#stdio-mcp-only).

---

## Running tests

```bash
pytest
# with coverage report:
pytest --cov=unit_converter --cov-report=term-missing
```

The coverage gate is **>= 90% line coverage on `unit_converter/core/`**. GUI and API transport
layers are excluded from the gate.

---

## Building a standalone executable

A PyInstaller spec is provided in `packaging/`. See
[packaging/README-packaging.md](packaging/README-packaging.md) for the full build guide.

Quick start on Windows:

```bat
pip install "pyinstaller~=6.20.0" "PySide6~=6.11.1" Pillow
packaging\build_windows.bat
```

Output: `packaging\bin\UConverter\UConverter.exe` — a self-contained windowed executable
that bundles the TOML database and PySide6 Qt libraries. No Python installation required.

On Linux/macOS:

```bash
pip install "pyinstaller~=6.20.0" "PySide6~=6.11.1" Pillow
bash packaging/build_posix.sh
```

Or use the cross-platform Python runner: `python packaging/build.py`

---

## Extending units

The unit database lives in `unit_converter/data/magnitudes.toml`. See
[docs/usage-guide.md](docs/usage-guide.md#extending-the-unit-database) for the TOML format
and how to add new magnitudes and units. Custom user units can also be added at runtime via
`POST /units/custom` or the GUI without editing the shipped database.

---

## Agent / programmatic access

See [docs/agent-access.md](docs/agent-access.md) for the full REST endpoint and MCP tool
reference (16 operations), transport options, and example calls. The in-repo Claude agent
operating guide is at [docs/agent-operating-doc.md](docs/agent-operating-doc.md).

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
