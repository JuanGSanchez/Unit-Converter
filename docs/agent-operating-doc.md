# Unit-Converter — In-Repo Agent Operating Guide

This document describes how an external agent (or any automated client) should drive the
Unit-Converter repository via its access layer. It is the operating guide that the in-repo
Claude agent asset (see below) references.

> **In-repo agent asset:** [`.claude/agents/unit-conversion-operator.md`](../.claude/agents/unit-conversion-operator.md)
> — the `unit-conversion-operator` Claude Code subagent that drives this repo's conversion
> capability headlessly through the MCP/REST access layer described below.

---

## Table of contents

1. [What this repo does for agents](#what-this-repo-does-for-agents)
2. [Starting the access layer](#starting-the-access-layer)
3. [Available tools](#available-tools)
4. [Workflow: performing a conversion](#workflow-performing-a-conversion)
5. [Workflow: discovering available units](#workflow-discovering-available-units)
6. [Input/output reference](#inputoutput-reference)
7. [Transport selection guide](#transport-selection-guide)
8. [Error handling for agents](#error-handling-for-agents)
9. [What the agent does NOT control](#what-the-agent-does-not-control)

---

## What this repo does for agents

Unit-Converter exposes a **read-only, compute-only** service. There are no write or
stateful operations. An agent uses it to:

- Enumerate available **magnitudes** (physical quantities).
- Enumerate available **units** within a magnitude.
- **Convert** a numeric value between any two units within a magnitude, with optional
  SI or IEC binary order-of-magnitude prefixes.

All computation is deterministic and stateless — the same inputs always produce the same
output.

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

## Available tools

| Tool name | Transport | Description |
|-----------|-----------|-------------|
| `health` | REST + MCP | Liveness check; returns status and version |
| `get_magnitudes` | REST + MCP | Sorted list of all magnitude names |
| `get_units` | REST + MCP | Units and base unit for a given magnitude |
| `post_convert` | REST + MCP | Perform a unit conversion (primary tool) |

All four tools are available on both the Streamable HTTP MCP endpoint (`/mcp`) and the
stdio MCP server.

The REST equivalents (for HTTP-native agents) are:

| Tool | REST endpoint |
|------|---------------|
| `health` | `GET /health` |
| `get_magnitudes` | `GET /magnitudes` |
| `get_units` | `GET /magnitudes/{magnitude}/units` |
| `post_convert` | `POST /convert` |

---

## Workflow: performing a conversion

The typical agent workflow is:

1. (Optional) Call `get_magnitudes` to confirm the magnitude name.
2. (Optional) Call `get_units` to confirm exact unit name strings.
3. Call `post_convert` with the magnitude, value, source unit, and target unit.

### Minimal example — convert 1 pound to grams

```json
// post_convert input
{
  "magnitude": "Mass",
  "value": 1.0,
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)"
}
```

```json
// post_convert output
{ "result": 453.6 }
```

### Example with SI prefix — convert 5 km to meters

```json
{
  "magnitude": "Length",
  "value": 5.0,
  "from_unit": "meter (m)",
  "to_unit": "meter (m)",
  "from_order": "k",
  "to_order": "1"
}
```

```json
{ "result": 5000.0 }
```

### Example with IEC binary prefix — convert 2 GiB to bytes (Data magnitude)

```json
{
  "magnitude": "Data",
  "value": 2.0,
  "from_unit": "byte (B)",
  "to_unit": "byte (B)",
  "from_order": "G",
  "to_order": "1"
}
```

```json
{ "result": 2147483648.0 }
```

Note: the `Data` magnitude uses IEC binary prefixes (base 1024). The same prefix symbol
`"G"` means gibi (1024^3) for Data, but giga (10^9) for all other magnitudes.

---

## Workflow: discovering available units

To enumerate all units the agent can use:

```json
// get_magnitudes -> ["Area", "Data", "Energy", "Length", "Mass", "Power", "Pressure", "Time", "Volume"]

// get_units input
{ "magnitude": "Mass" }

// get_units output
{
  "units": ["gram (g)", "Av. pound (lb)", "Av. ounce (oz)"],
  "base_unit": "gram (g)"
}
```

Unit names are **case-sensitive** and must be passed to `post_convert` exactly as
returned by `get_units`.

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

### SI prefix keys (all magnitudes except Data)

`q r y z a f p n μ m 1 k M G T P E Z Y R Q`

`"1"` means no prefix (multiplier = 1).

### IEC binary prefix keys (Data magnitude only)

`1 k M G T P E Z Y R Q`

`"1"` means no prefix. `"k"` = 1024, `"M"` = 1024^2, `"G"` = 1024^3, etc.

### post_convert output

```json
{ "result": <float> }
```

A `result` of `0.0` may mean the input value was zero or was clamped (negative/NaN/inf).

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
| Unknown unit | 422 | true | `"Unknown unit 'X' in magnitude 'Y'. Available: [...]"` |
| Unknown order prefix | 422 | true | `"Unknown order prefix 'X' for magnitude 'Y'. Available: [...]"` |
| Zero conversion factor (database error) | 422 | true | `"Conversion factor for unit 'X' in 'Y' is zero"` |
| Negative / NaN / inf input | — | — | No error — clamped to 0.0, returns `{"result": 0.0}` |

On a 422 / `isError: true` response:
- Check that magnitude name matches exactly (use `get_magnitudes` to confirm).
- Check that unit names match exactly (use `get_units` to confirm).
- Check that `from_order` / `to_order` are valid prefix symbols for the magnitude.

---

## What the agent does NOT control

- **The GUI** (`unit-converter-gui`) — the PySide6 desktop application is a separate entry
  point and is not driven via the API.
- **The database** (`unit_converter/data/magnitudes.toml`) — the agent reads the database
  through `get_units`; it does not write to or reload the database.
- **The packaging build** (`packaging/`) — the PyInstaller executable is a build artifact,
  not an agent-accessible surface.
- **The legacy Tkinter entry point** (`UConverter_UI.pyw`) — not wired to the API layer.
