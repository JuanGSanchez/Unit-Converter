# Unit-Converter — Agent Access Layer

Single shared service (`service.py`) exposed as **REST** (FastAPI) and **MCP** (FastMCP 3.x)
from one combined ASGI app.  No conversion logic lives in this layer — all computation is
delegated to `unit_converter.core.converter`.

## Installation

```bash
pip install "unit-converter[api]"
```

This installs `fastmcp>=3.4,<4`, `fastapi>=0.136,<1`, and `uvicorn>=0.49,<1`.

---

## Run the REST + MCP server (Streamable HTTP)

```bash
unit-converter-api
# or equivalently:
uvicorn unit_converter.api.main:app --host 0.0.0.0 --port 8000
```

After startup:

| Surface | URL |
|---------|-----|
| REST docs (Swagger) | http://localhost:8000/docs |
| REST docs (ReDoc)   | http://localhost:8000/redoc |
| MCP (Streamable HTTP) | http://localhost:8000/mcp |

---

## Run the MCP server over stdio (for CLI / local agent clients)

```bash
unit-converter-mcp
# or equivalently:
python -m unit_converter.api.mcp_server
```

Configure your MCP client (e.g. Claude Desktop) to use:

```json
{
  "mcpServers": {
    "unit-converter": {
      "command": "unit-converter-mcp"
    }
  }
}
```

---

## REST routes

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check; returns `{"status":"ok","version":"<ver>"}` |
| `GET`  | `/magnitudes` | Sorted list of magnitude names |
| `GET`  | `/magnitudes/{magnitude}/units` | Units and base unit for a magnitude |
| `POST` | `/convert` | Perform a unit conversion |

### POST /convert — request body

```json
{
  "magnitude": "Mass",
  "value": 1.0,
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)",
  "from_order": "1",
  "to_order": "1"
}
```

### POST /convert — response

```json
{ "result": 453.6 }
```

### Error responses

`ValueError` from the core is returned as HTTP **422 Unprocessable Entity**:

```json
{ "detail": "Unknown magnitude: 'Foo'.  Available: ['Area', 'Data', ...]" }
```

---

## MCP tools

FastMCP auto-generates one tool per FastAPI route.  The tools exposed are:

| Tool name | Derived from | Description |
|-----------|-------------|-------------|
| `health` | `GET /health` | Liveness + version |
| `get_magnitudes` | `GET /magnitudes` | List all magnitude names |
| `get_units` | `GET /magnitudes/{magnitude}/units` | List units for a magnitude |
| `post_convert` | `POST /convert` | Perform a unit conversion |

`ValueError` propagates from the FastAPI layer as a structured MCP tool error
(`isError: true` with the `detail` message from the HTTP 422 body).

---

## Architecture

```
unit_converter.core.converter   ← pure core (no UI, no transport)
         │
         ▼
unit_converter.api.service      ← thin typed wrappers (single shared layer)
         │
    ┌────┴─────┐
    ▼          ▼
rest.py     mcp_server.py
(FastAPI)   (FastMCP.from_fastapi → same FastAPI app)
    │          │
    └────┬─────┘
         ▼
      main.py   ← combined ASGI app (REST + MCP at /mcp), uvicorn entry
```

---

## Notes for downstream agents

- **Testing agent**: smoke-test `GET /health`, `GET /magnitudes`, `POST /convert` via
  `httpx.AsyncClient(app=app, base_url="http://test")` (no server needed).
  MCP tool smoke-test: call `post_convert` via `fastmcp.Client` with a known conversion.
- **Docs agent**: REST routes above + MCP tool table above are the canonical reference.
- **Metaprompter**: the in-repo agent asset should reference the `post_convert` tool
  and the Streamable HTTP endpoint for remote access.
- **Transport confirmation (research L3)**: `transport="streamable-http"` is set
  explicitly in `mcp_server.py` rather than relying on the default.
