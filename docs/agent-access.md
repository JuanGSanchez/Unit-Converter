# Unit-Converter — Agent Access

The unit converter exposes a single shared service (`unit_converter.api`) as both a
**REST API** (FastAPI) and an **MCP server** (FastMCP 3.x) from one combined ASGI
application. All conversion logic is delegated to `unit_converter.core.converter` —
the API layer contains no conversion math.

---

## Table of contents

1. [Installation](#installation)
2. [Transports](#transports)
   - [Streamable HTTP (REST + MCP)](#streamable-http-rest--mcp)
   - [stdio (MCP only)](#stdio-mcp-only)
3. [REST endpoints](#rest-endpoints)
4. [MCP tools](#mcp-tools)
5. [Example calls](#example-calls)
6. [Architecture](#architecture)
7. [Error handling](#error-handling)

---

## Installation

```bash
pip install "unit-converter[api]"
```

Installs `fastmcp>=3.4,<4`, `fastapi>=0.136,<1`, and `uvicorn>=0.49,<1`.
Python `>=3.11` required; build/CI ceiling Python 3.13 (FastMCP declared support).

---

## Transports

### Streamable HTTP (REST + MCP)

Start the combined server:

```bash
unit-converter-api
# equivalent:
uvicorn unit_converter.api.main:app --host 0.0.0.0 --port 8000
```

| Surface | URL |
|---------|-----|
| REST docs (Swagger UI) | http://localhost:8000/docs |
| REST docs (ReDoc) | http://localhost:8000/redoc |
| MCP (Streamable HTTP) | http://localhost:8000/mcp |
| Health check | http://localhost:8000/health |

The MCP endpoint at `/mcp` uses the **Streamable HTTP** transport (SSE is deprecated in
the MCP specification as of March 2025 and is not used here).

Configure an MCP client for Streamable HTTP:

```json
{
  "mcpServers": {
    "unit-converter": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### stdio (MCP only)

For CLI tools and MCP clients that communicate over standard input/output (e.g. Claude
Desktop):

```bash
unit-converter-mcp
# equivalent:
python -m unit_converter.api.mcp_server
```

Configure Claude Desktop (or any MCP-stdio client):

```json
{
  "mcpServers": {
    "unit-converter": {
      "command": "unit-converter-mcp"
    }
  }
}
```

The stdio entry point runs the same MCP server as the Streamable HTTP endpoint — same
tools, same core.

---

## REST endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/magnitudes` | List all magnitude names |
| `GET` | `/magnitudes/{magnitude}/units` | List units and base unit for a magnitude |
| `POST` | `/convert` | Perform a unit conversion |

### GET /health

Returns application status and version.

```json
{ "status": "ok", "version": "1.1.0" }
```

### GET /magnitudes

Returns a sorted list of magnitude names.

```json
["Area", "Data", "Energy", "Length", "Mass", "Power", "Pressure", "Time", "Volume"]
```

### GET /magnitudes/{magnitude}/units

Returns units and the base unit for a magnitude.

```
GET /magnitudes/Mass/units
```

```json
{
  "units": ["gram (g)", "Av. pound (lb)", "Av. ounce (oz)"],
  "base_unit": "gram (g)"
}
```

### POST /convert

Request body (JSON):

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

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `magnitude` | string | yes | — | Magnitude name (case-sensitive) |
| `value` | number | yes | — | Value to convert |
| `from_unit` | string | yes | — | Source unit name |
| `to_unit` | string | yes | — | Target unit name |
| `from_order` | string | no | `"1"` | SI/IEC prefix for source unit |
| `to_order` | string | no | `"1"` | SI/IEC prefix for target unit |

Response:

```json
{ "result": 453.6 }
```

`from_order` and `to_order` accept the SI prefix symbol keys (e.g. `"k"` for kilo,
`"M"` for mega) or `"1"` for no prefix. For the `Data` magnitude, IEC binary prefix
symbols are used (same symbol set, different base: 1024).

---

## MCP tools

FastMCP auto-generates one MCP tool per FastAPI route. The four tools exposed are:

| Tool name | Derived from | Description |
|-----------|-------------|-------------|
| `health` | `GET /health` | Liveness check and version |
| `get_magnitudes` | `GET /magnitudes` | Sorted list of all magnitude names |
| `get_units` | `GET /magnitudes/{magnitude}/units` | Units and base unit for a magnitude |
| `post_convert` | `POST /convert` | Perform a unit conversion |

Tool inputs and outputs mirror the REST contract above. `post_convert` is the primary
tool for agent-driven conversions.

---

## Example calls

### REST — curl

```bash
# List magnitudes
curl http://localhost:8000/magnitudes

# List units for Mass
curl http://localhost:8000/magnitudes/Mass/units

# Convert 1 pound to grams
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Mass","value":1.0,"from_unit":"Av. pound (lb)","to_unit":"gram (g)"}'
# -> {"result":453.6}

# Convert 1 km to meters (using SI prefix)
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Length","value":1.0,"from_unit":"meter (m)","to_unit":"meter (m)","from_order":"k","to_order":"1"}'
# -> {"result":1000.0}

# Convert 1 GiB to bytes (Data magnitude — IEC binary prefix)
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Data","value":1.0,"from_unit":"byte (B)","to_unit":"byte (B)","from_order":"G","to_order":"1"}'
# -> {"result":1073741824.0}
```

### REST — Python (httpx)

```python
import httpx

base = "http://localhost:8000"

# List magnitudes
resp = httpx.get(f"{base}/magnitudes")
magnitudes = resp.json()  # ['Area', 'Data', ...]

# Convert
resp = httpx.post(f"{base}/convert", json={
    "magnitude": "Mass",
    "value": 1.0,
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
})
print(resp.json()["result"])  # 453.6
```

### REST — in-process (no server required, for tests)

```python
import httpx
from unit_converter.api.main import app

async def test_convert():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/convert", json={
            "magnitude": "Mass",
            "value": 1.0,
            "from_unit": "Av. pound (lb)",
            "to_unit": "gram (g)",
        })
        assert r.json()["result"] == 453.6
```

### MCP — fastmcp.Client (Streamable HTTP)

```python
from fastmcp import Client

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        # List magnitudes
        result = await client.call_tool("get_magnitudes", {})
        print(result)

        # Convert
        result = await client.call_tool("post_convert", {
            "magnitude": "Mass",
            "value": 1.0,
            "from_unit": "Av. pound (lb)",
            "to_unit": "gram (g)",
        })
        print(result)  # 453.6
```

### MCP — fastmcp.Client (stdio)

```python
from fastmcp import Client

async def main():
    async with Client("unit-converter-mcp") as client:
        result = await client.call_tool("post_convert", {
            "magnitude": "Mass",
            "value": 1.0,
            "from_unit": "Av. pound (lb)",
            "to_unit": "gram (g)",
        })
        print(result)  # 453.6
```

---

## Architecture

```
unit_converter.core.converter   <- pure core (no UI, no transport)
         |
         v
unit_converter.api.service      <- thin typed wrappers (single shared layer)
         |
    +----+------+
    v           v
rest.py      mcp_server.py
(FastAPI)    (FastMCP.from_fastapi -> same FastAPI app)
    |           |
    +----+------+
         v
      main.py   <- combined ASGI app (REST + MCP at /mcp), uvicorn entry
```

The combined app is constructed using `FastMCP.from_fastapi(app=api)` +
`mcp.http_app(path="/mcp", transport="streamable-http")`, which mounts both the REST
routes and the MCP endpoint onto a single FastAPI app and forwards the MCP lifespan
(required to start the FastMCP session manager).

---

## Error handling

Errors from the core (`ValueError` for unknown magnitude, unit, or order key) propagate
through the FastAPI layer as **HTTP 422 Unprocessable Entity**:

```json
{ "detail": "Unknown magnitude: 'Foo'.  Available: ['Area', 'Data', ...]" }
```

Over MCP, the same error is returned as a structured tool error (`isError: true`) with
the `detail` field from the HTTP 422 body.

Input clamping (negative, NaN, infinite values → `0.0`) is performed by the core before
any error check, so clamped inputs always succeed and return `0.0`.
