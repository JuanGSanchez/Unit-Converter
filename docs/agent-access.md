# Unit-Converter — Agent Access

The unit converter exposes a single shared service (`unit_converter.api`) as both a
**REST API** (FastAPI) and an **MCP server** (FastMCP 3.x) from one combined ASGI
application. All conversion logic is delegated to `unit_converter.core` — the API layer
contains no conversion math.

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

16 operations across 5 tag groups.

### Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check; returns `{"status":"ok","version":"<ver>"}` |

### Discovery

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/magnitudes` | Sorted list of all magnitude names |
| `GET` | `/magnitudes/{magnitude}/units` | Units and base unit for a magnitude |

### Conversion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/convert` | Convert a value between units (supports `sig_figs`) |
| `GET` | `/convert/compound/parse` | Parse a compound unit expression |
| `POST` | `/convert/compound` | Convert a value using compound unit expressions |

### Currency

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/currencies` | Sorted list of supported ISO 4217 currency codes |
| `GET` | `/currencies/rate` | Exchange rate for a currency pair |
| `POST` | `/currencies/convert` | Convert an amount between currencies |
| `POST` | `/currencies/refresh` | Force-refresh the exchange rate cache from Frankfurter |

### History

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/history` | Full conversion history, most-recent-first |
| `GET` | `/history/favorites` | Favorited entries only |
| `POST` | `/history/record` | Append a conversion to history (HTTP 201) |
| `POST` | `/history/favorites` | Mark a history entry as a favorite |
| `DELETE` | `/history` | Clear all history |

### Units

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/units/custom` | Add a custom unit to the user database (HTTP 201) |

---

### Route details

#### GET /health

```json
{ "status": "ok", "version": "1.1.0" }
```

#### GET /magnitudes

```json
["Absorbed_dose", "Acceleration", "Amount_of_substance", "Area", "Data", "Density",
 "Electric_charge", "Electric_resistance", "Energy", "Equivalent_dose", "Force", "Frequency",
 "Length", "Mass", "Plane_angle", "Power", "Pressure", "Radiation_exposure", "Radioactivity",
 "Speed", "Temperature", "Temperature_delta", "Time", "Voltage", "Volume"]
```

#### GET /magnitudes/{magnitude}/units

```
GET /magnitudes/Mass/units
```

```json
{ "units": ["gram (g)", "Av. pound (lb)", "Av. ounce (oz)"], "base_unit": "gram (g)" }
```

HTTP 422 if `magnitude` is unknown.

#### POST /convert

Request body:

```json
{
  "magnitude": "Mass",
  "value": 1.0,
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)",
  "from_order": "1",
  "to_order": "1",
  "sig_figs": null
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `magnitude` | string | yes | — | Magnitude name (case-sensitive) |
| `value` | number | yes | — | Value to convert |
| `from_unit` | string | yes | — | Source unit name (exact, from `get_units`) |
| `to_unit` | string | yes | — | Target unit name (exact, from `get_units`) |
| `from_order` | string | no | `"1"` | SI/IEC prefix symbol for source unit |
| `to_order` | string | no | `"1"` | SI/IEC prefix symbol for target unit |
| `sig_figs` | integer | no | `null` | Round result to N significant figures |

Response: `{ "result": 453.6 }`

HTTP 422 on unknown magnitude, unit, incompatible units, or invalid order key.

#### GET /convert/compound/parse

```
GET /convert/compound/parse?expr=km/h
```

```json
{ "expr": "km/h", "factor": 0.27778, "dimensions": { ... } }
```

HTTP 422 on syntax errors or unknown unit atoms.

#### POST /convert/compound

```json
{ "value": 100, "from_expr": "km/h", "to_expr": "m/s" }
```

```json
{ "result": 27.778, "from_expr": "km/h", "to_expr": "m/s" }
```

HTTP 422 on dimension mismatch, unknown unit atoms, or syntax errors.

#### GET /currencies

```json
["AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", ...]
```

#### GET /currencies/rate

```
GET /currencies/rate?from=EUR&to=USD
```

```json
{ "from": "EUR", "to": "USD", "rate": 1.082, "date": "2026-06-13", "is_stale": false }
```

`is_stale: true` when the cache is from a prior date. HTTP 404 if either code is unknown.

#### POST /currencies/convert

```json
{ "from": "EUR", "to": "USD", "value": 100 }
```

```json
{ "result": 108.2, "rate": 1.082, "date": "2026-06-13", "is_stale": false }
```

HTTP 404 if either currency code is unknown; HTTP 422 if `value` is invalid.

#### POST /currencies/refresh

```json
{ "date": "2026-06-13", "base": "EUR", "currency_count": 33, "source": "frankfurter" }
```

HTTP 503 if the upstream Frankfurter API is unreachable.

#### GET /history

Returns a list of `HistoryEntry` objects (most-recent-first):

```json
[
  {
    "magnitude": "Mass",
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
    "from_order": "1",
    "to_order": "1",
    "value": 1.0,
    "result": 453.6,
    "sig_figs": null,
    "timestamp": "2026-06-13T10:00:00Z",
    "favorite": false,
    "favorite_label": ""
  }
]
```

#### GET /history/favorites

Same schema as `GET /history`, filtered to `"favorite": true` entries only.

#### POST /history/record

```json
{
  "magnitude": "Mass",
  "value": 1.0,
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)",
  "result": 453.6,
  "from_order": "1",
  "to_order": "1",
  "sig_figs": null
}
```

Returns the created `HistoryEntry` (HTTP 201). HTTP 422 if required fields are missing.

#### POST /history/favorites

```json
{ "timestamp": "2026-06-13T10:00:00Z", "label": "lb to g baseline" }
```

```json
{ "marked": true, "timestamp": "2026-06-13T10:00:00Z" }
```

HTTP 422 if `timestamp` is empty or no matching entry is found.

#### DELETE /history

```json
{ "cleared": true }
```

#### POST /units/custom

```json
{ "magnitude": "Mass", "unit_name": "stone (st)", "factor": 6350.29 }
```

```json
{ "magnitude": "Mass", "unit_name": "stone (st)", "factor": 6350.29 }
```

Returns HTTP 201. HTTP 422 on validation failure (empty name, factor ≤ 0, invalid chars).

---

## MCP tools

FastMCP auto-generates one MCP tool per FastAPI route. The 16 tools exposed mirror the
REST contract above exactly.

> **Rationale — 16 tools, an accepted expansion of SPEC-04 (recorded 2026-06-28).**
> The original product spec (`SPECIFICATIONS-archive-20260625.md`, SPEC-04) called for a
> minimal three-tool MCP surface (`list_magnitudes`, `list_units`, `convert`). That criterion
> is deliberately **superseded**: the shipped surface is the 16 operations above, adding
> compound-unit parsing/conversion, currency discovery/rate/convert/refresh, conversion
> history & favorites, and custom-unit registration. The expansion still honors the F4
> "small, purposeful toolset" intent — every tool maps 1:1 to a single curated FastAPI
> operation (no redundant or overlapping tools), all 16 share the one conversion core (no
> logic fork), and the exact set is locked by `_EXPECTED_TOOL_NAMES_16` in
> `tests/test_api_routes.py`. The number is a capability decision, not an accident; do not
> regress it to three. Tracked as SPEC-R1.

| Tool name | Derived from | Description |
|-----------|-------------|-------------|
| `health` | `GET /health` | Liveness check and version |
| `get_magnitudes` | `GET /magnitudes` | Sorted list of all magnitude names |
| `get_units` | `GET /magnitudes/{magnitude}/units` | Units and base unit for a magnitude |
| `post_convert` | `POST /convert` | Convert a value between units |
| `get_parse_compound` | `GET /convert/compound/parse` | Parse a compound unit expression |
| `post_convert_compound` | `POST /convert/compound` | Convert using compound unit expressions |
| `list_currencies` | `GET /currencies` | List supported ISO 4217 currency codes |
| `get_currency_rate` | `GET /currencies/rate` | Exchange rate for a currency pair |
| `post_convert_currency` | `POST /currencies/convert` | Convert an amount between currencies |
| `post_refresh_rates` | `POST /currencies/refresh` | Force-refresh the rate cache |
| `get_history` | `GET /history` | Full conversion history |
| `get_favorites` | `GET /history/favorites` | Favorited history entries |
| `post_record_conversion` | `POST /history/record` | Append a conversion to history |
| `post_add_favorite` | `POST /history/favorites` | Mark a history entry as a favorite |
| `delete_history` | `DELETE /history` | Clear all history |
| `post_add_custom_unit` | `POST /units/custom` | Add a custom unit |

**State-changing tools** (mutations): `post_refresh_rates`, `post_record_conversion`, `post_add_favorite`, `delete_history`, `post_add_custom_unit`.

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

# Convert with sig_figs
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Mass","value":1.0,"from_unit":"Av. pound (lb)","to_unit":"gram (g)","sig_figs":3}'
# -> {"result":454.0}

# Convert 1 km to meters (SI prefix)
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Length","value":1.0,"from_unit":"meter (m)","to_unit":"meter (m)","from_order":"k","to_order":"1"}'
# -> {"result":1000.0}

# Compound conversion
curl -X POST http://localhost:8000/convert/compound \
  -H "Content-Type: application/json" \
  -d '{"value":100,"from_expr":"km/h","to_expr":"m/s"}'
# -> {"result":27.778,"from_expr":"km/h","to_expr":"m/s"}

# Currency rate
curl "http://localhost:8000/currencies/rate?from=EUR&to=USD"
```

### REST — Python (httpx)

```python
import httpx

base = "http://localhost:8000"

# Convert
resp = httpx.post(f"{base}/convert", json={
    "magnitude": "Mass",
    "value": 1.0,
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
    "sig_figs": 3,
})
print(resp.json()["result"])  # 454.0
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
unit_converter.core.*          <- pure core (no UI, no transport)
         |
         v
unit_converter.api.service     <- thin typed wrappers (single shared layer)
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

| Error condition | HTTP status | MCP `isError` | Detail pattern |
|----------------|-------------|---------------|----------------|
| Unknown magnitude | 422 | true | `"Unknown magnitude: 'X'. Available: [...]"` |
| Unknown / incompatible unit | 422 | true | `"Unknown unit 'X' in magnitude 'Y'. Available: [...]"` |
| Unknown order prefix | 422 | true | `"Unknown order prefix 'X' for magnitude 'Y'. Available: [...]"` |
| Zero conversion factor | 422 | true | `"Conversion factor for unit 'X' in 'Y' is zero"` |
| Dimension mismatch (compound) | 422 | true | `"Incompatible dimensions: ..."` |
| Unknown currency code | 404 | true | `"'X'"` |
| Upstream rate service down | 503 | true | `"Upstream rate service unavailable: ..."` |
| Negative / NaN / inf input | — | — | No error — clamped to 0.0, returns `{"result": 0.0}` |

On a 422 / `isError: true` response:
- Verify the magnitude name exactly against `GET /magnitudes`.
- Verify unit names exactly against `GET /magnitudes/{magnitude}/units`.
- Verify `from_order` / `to_order` are valid prefix symbols for the magnitude's prefix table.
- For currency errors, verify the code against `GET /currencies`.
