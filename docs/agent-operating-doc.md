# Unit-Converter — In-Repo Agent Operating Guide

This document describes how an external agent (or any automated client) should drive the
Unit-Converter repository via its access layer.

> **In-repo agent assets:** (full roster + instructions/skills/hooks registered in `CLAUDE.md`)
> - [`.claude/agents/unit-conversion-operator.md`](../.claude/agents/unit-conversion-operator.md)
>   — drives conversions headlessly via the 16-op MCP/REST access layer.
> - Repo maintenance is owned by focused dev agents — `core-dev`, `gui-dev`, `access-dev`,
>   `test-author`, `packaging-builder`, `docs-writer` — and gated by `reviewer`. See `CLAUDE.md`.

---

## Table of contents

1. [What this repo does for agents](#what-this-repo-does-for-agents)
2. [Starting the access layer](#starting-the-access-layer)
3. [Available tools (16 operations)](#available-tools-16-operations)
4. [Workflow: performing a conversion](#workflow-performing-a-conversion)
5. [Workflow: currency conversion](#workflow-currency-conversion)
6. [Workflow: compound unit conversion](#workflow-compound-unit-conversion)
7. [Workflow: history and favorites](#workflow-history-and-favorites)
8. [Workflow: custom units](#workflow-custom-units)
9. [Input/output reference](#inputoutput-reference)
10. [Transport selection guide](#transport-selection-guide)
11. [Error handling for agents](#error-handling-for-agents)
12. [What the agent does NOT control](#what-the-agent-does-not-control)

---

## What this repo does for agents

Unit-Converter exposes a **compute + state service** through its access layer. An agent uses it to:

- Enumerate available **magnitudes** (physical quantities) and their **units**.
- **Convert** a numeric value between any two units within a magnitude, with optional
  SI or IEC binary order-of-magnitude prefixes and significant-figure rounding.
- Convert **compound/derived units** (e.g. `km/h → m/s`) using expression parsing.
- Fetch **live currency exchange rates** (Frankfurter, cached dated table, offline fallback)
  and convert amounts between ISO 4217 currency codes.
- Read and write **conversion history** and **favorites** persisted in `~/.unit-converter/`.
- **Add custom user-defined units** persisted to `~/.unit-converter/custom.toml`.

Core unit conversion is deterministic and stateless. Currency rates, history, and custom
units are stateful (file-backed, per-user).

---

## Starting the access layer

Before any tool call the server must be running (Streamable HTTP transport), or the
`unit-converter-mcp` process must be launched (stdio transport).

### Streamable HTTP (preferred for remote / multi-client use)

```bash
pip install "unit-converter[api]"
unit-converter-api
# Server ready at http://localhost:8000
# MCP endpoint: http://localhost:8000/mcp
```

### stdio (preferred for local / single-client use)

```bash
pip install "unit-converter[api]"
unit-converter-mcp
```

MCP client configuration:

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

## Available tools (16 operations)

| Tool name | REST equivalent | Description |
|-----------|-----------------|-------------|
| `health` | `GET /health` | Liveness check; returns status and version |
| `get_magnitudes` | `GET /magnitudes` | Sorted list of all magnitude names |
| `get_units` | `GET /magnitudes/{magnitude}/units` | Units and base unit for a magnitude |
| `post_convert` | `POST /convert` | Convert a value between units (primary tool) |
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
| `post_add_custom_unit` | `POST /units/custom` | Add a custom unit to the user database |

All 16 tools are available on both the Streamable HTTP MCP endpoint (`/mcp`) and the
stdio MCP server.

---

## Workflow: performing a conversion

1. (Optional) Call `get_magnitudes` to confirm the magnitude name.
2. (Optional) Call `get_units` to confirm exact unit name strings.
3. Call `post_convert` with magnitude, value, source unit, target unit, and (optionally)
   `from_order`, `to_order`, and `sig_figs`.

### Minimal example — convert 1 pound to grams

```json
// post_convert input
{
  "magnitude": "Mass",
  "value": 1.0,
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)"
}
// post_convert output
{ "result": 453.6 }
```

### With SI prefix and significant figures — 5 km to meters, 3 sig figs

```json
{
  "magnitude": "Length",
  "value": 5.0,
  "from_unit": "meter (m)",
  "to_unit": "meter (m)",
  "from_order": "k",
  "to_order": "1",
  "sig_figs": 3
}
// -> { "result": 5000.0 }
```

### IEC binary prefix — 2 GiB to bytes (Data magnitude)

```json
{
  "magnitude": "Data",
  "value": 2.0,
  "from_unit": "byte (B)",
  "to_unit": "byte (B)",
  "from_order": "G",
  "to_order": "1"
}
// -> { "result": 2147483648.0 }
```

Note: `"G"` means gibi (1024³) for `Data`, but giga (10⁹) for all other magnitudes.

---

## Workflow: currency conversion

1. (Optional) Call `list_currencies` to get the available ISO 4217 codes.
2. Call `post_convert_currency` (or `get_currency_rate` if you need only the rate).

```json
// post_convert_currency input
{ "from": "EUR", "to": "USD", "value": 100 }
// output
{ "result": 108.2, "rate": 1.082, "date": "2026-06-13", "is_stale": false }
```

`is_stale: true` means the cache is from a prior date. Call `post_refresh_rates` to fetch
fresh data from Frankfurter. HTTP 503 if Frankfurter is unreachable.

---

## Workflow: compound unit conversion

1. (Optional) Call `get_parse_compound` to inspect factor and dimensions of an expression.
2. Call `post_convert_compound` with a value and two expression strings.

```json
// post_convert_compound input
{ "value": 100, "from_expr": "km/h", "to_expr": "m/s" }
// output
{ "result": 27.778, "from_expr": "km/h", "to_expr": "m/s" }
```

HTTP 422 on dimension mismatch, unknown unit atoms, or syntax errors in either expression.

---

## Workflow: history and favorites

```json
// Record a conversion
// POST /history/record input:
{
  "magnitude": "Mass", "value": 1.0,
  "from_unit": "Av. pound (lb)", "to_unit": "gram (g)", "result": 453.6
}

// Mark as favorite
// POST /history/favorites input:
{ "timestamp": "2026-06-13T10:00:00Z", "label": "lb to g baseline" }

// Retrieve favorites
// GET /history/favorites output: [ { "magnitude": "Mass", ..., "favorite": true, "favorite_label": "lb to g baseline" } ]

// Clear history
// DELETE /history output: { "cleared": true }
```

---

## Workflow: custom units

```json
// POST /units/custom input:
{ "magnitude": "Mass", "unit_name": "stone (st)", "factor": 6350.29 }
// output (HTTP 201):
{ "magnitude": "Mass", "unit_name": "stone (st)", "factor": 6350.29 }
```

After adding, `stone (st)` is immediately available in `get_units("Mass")` and `post_convert`.

---

## Input/output reference

### post_convert inputs

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `magnitude` | string | yes | — | Case-sensitive. Use `get_magnitudes` to enumerate. |
| `value` | number | yes | — | Negative, NaN, infinite → clamped to 0.0 (returns 0.0, no error). |
| `from_unit` | string | yes | — | Exact name from `get_units`. |
| `to_unit` | string | yes | — | Exact name from `get_units`. |
| `from_order` | string | no | `"1"` | SI prefix key, or `"1"` for no prefix. IEC for Data. |
| `to_order` | string | no | `"1"` | SI prefix key, or `"1"` for no prefix. IEC for Data. |
| `sig_figs` | integer | no | `null` | Round result to N significant figures (positive integer). |

### SI prefix keys (all magnitudes except Data)

`q r y z a f p n μ m 1 k M G T P E Z Y R Q`

`"1"` means no prefix (multiplier = 1).

### IEC binary prefix keys (Data magnitude only)

`1 k M G T P E Z Y R Q`

`"1"` means no prefix. `"k"` = 1024, `"M"` = 1024², `"G"` = 1024³, etc.

### post_convert output

```json
{ "result": <float> }
```

A `result` of `0.0` may mean the input was zero, or was clamped (negative/NaN/inf). A
genuine input of `0.0` also returns `{"result": 0.0}` — distinguish the two in your report
rather than asserting a clamp occurred when the input was simply zero.

---

## Transport selection guide

| Scenario | Recommended transport |
|----------|-----------------------|
| Remote agent / multi-client / CI pipeline | Streamable HTTP (`unit-converter-api`, MCP at `/mcp`) |
| Local agent / Claude Desktop / CLI tool | stdio (`unit-converter-mcp`) |
| In-process Python test | ASGI in-process (`httpx.AsyncClient(app=app, base_url="http://test")`) |
| HTTP-native client (curl, requests, httpx) | REST endpoints directly |

---

## Error handling for agents

| Error condition | HTTP status | MCP `isError` | `detail` message pattern |
|----------------|-------------|---------------|--------------------------|
| Unknown magnitude | 422 | true | `"Unknown magnitude: 'X'. Available: [...]"` |
| Unknown / incompatible unit | 422 | true | `"Unknown unit 'X' in magnitude 'Y'. Available: [...]"` |
| Unknown order prefix | 422 | true | `"Unknown order prefix 'X' for magnitude 'Y'. Available: [...]"` |
| Zero conversion factor (database error) | 422 | true | `"Conversion factor for unit 'X' in 'Y' is zero"` |
| Dimension mismatch (compound) | 422 | true | `"Incompatible dimensions: ..."` |
| Unknown currency code | 404 | true | `"'X'"` |
| Rate service unreachable | 503 | true | `"Upstream rate service unavailable: ..."` |
| Negative / NaN / inf input | — | — | No error — clamped to 0.0 |

On a 422 / `isError: true` response:
- Check that magnitude name matches exactly (use `get_magnitudes` to confirm).
- Check that unit names match exactly (use `get_units` to confirm).
- Check that `from_order` / `to_order` are valid prefix symbols for the magnitude.

---

## What the agent does NOT control

- **The GUI** (`unit-converter-gui`) — the PySide6 desktop application is a separate entry
  point and is not driven via the API.
- **The database** (`unit_converter/data/magnitudes.toml`) — agents read units through
  `get_units`; the shipped database is not writable via the API (use `POST /units/custom`
  for runtime additions, or the `unit-converter-maintainer` agent for database edits).
- **The packaging build** (`packaging/`) — the PyInstaller executable is a build artifact,
  not an agent-accessible surface.
