# Unit-Converter — Complete Usage Guide

This guide covers all three ways to use Unit-Converter: the **PySide6 desktop GUI**, the **REST API**, and the **MCP server**. Each face provides the same conversion capabilities and state-changing operations (history, favorites, custom units) — choose the interface that fits your workflow.

---

## Table of contents

1. [Overview: Three ways to use Unit-Converter](#overview-three-ways-to-use-unit-converter)
2. [Part A: Using the PySide6 desktop application](#part-a-using-the-pyside6-desktop-application)
   - [Launching](#launching)
   - [Making a conversion](#making-a-conversion)
   - [Hover tooltips](#hover-tooltips)
   - [Changing the order of magnitude](#changing-the-order-of-magnitude)
   - [Digit sweep](#digit-sweep)
   - [Hover tooltips and help](#hover-tooltips-and-help)
   - [Keyboard shortcuts](#keyboard-shortcuts)
   - [Context menu (right-click)](#context-menu-right-click)
   - [History dialog and Favorites toggle](#history-dialog-and-favorites-toggle)
   - [Settings and theming](#settings-and-theming)
   - [Find Unit search (Ctrl+F)](#find-unit-search-ctrlf)
   - [Batch conversion (Batch convert...)](#batch-conversion-batch-convert)
   - [Input clamping](#input-clamping)
3. [Part B: Using the REST API](#part-b-using-the-rest-api)
   - [Starting the REST server](#starting-the-rest-server)
   - [Base URL and Swagger/ReDoc docs](#base-url-and-swaggerredoc-docs)
   - [Health check](#health-check)
   - [Discovery: list magnitudes and units](#discovery-list-magnitudes-and-units)
   - [Basic conversion](#basic-conversion)
   - [Compound/derived units](#compoundderived-units)
   - [Live currency conversion](#live-currency-conversion)
   - [Conversion history and favorites](#conversion-history-and-favorites)
   - [Custom user-defined units](#custom-user-defined-units)
   - [Error handling](#error-handling)
4. [Part C: Using via MCP](#part-c-using-via-mcp)
   - [Starting the MCP server](#starting-the-mcp-server)
   - [Registering with an MCP client](#registering-with-an-mcp-client)
   - [The 16 MCP tools](#the-16-mcp-tools)
   - [Tool-call examples](#tool-call-examples)
5. [Shared reference](#shared-reference)
   - [Conversion model](#conversion-model)
   - [Significant figures / precision control](#significant-figures--precision-control)
   - [Affine / temperature handling](#affine--temperature-handling)
   - [Dimensional-compatibility guard](#dimensional-compatibility-guard)
   - [Order-of-magnitude prefixes](#order-of-magnitude-prefixes)
   - [Supported magnitudes (25)](#supported-magnitudes-25)
   - [Extending the unit database](#extending-the-unit-database)

---

## Overview: Three ways to use Unit-Converter

### 1. PySide6 Desktop GUI

**For:** Interactive point-and-click conversions on your desktop.

```bash
# Requires pip install "unit-converter[gui]"
unit-converter-gui
```

- Real-time bidirectional conversion
- Visual magnitude and unit selection
- Scroll-based order-of-magnitude and digit-sweep controls
- Centralized help: hover tooltips, keyboard focus, and keyboard shortcuts (Ctrl+C/V/F/Q)
- History panel with favorites and context menu actions
- Custom unit dialog
- Light/Dark themes with per-widget color picker
- Unit search with Find Unit (Ctrl+F) — case- and accent-insensitive substring matching
- Batch conversion: multi-value or one-to-all-units with CSV export
- Clipboard integration: Ctrl+C copies results, Ctrl+V pastes numeric input

**GUI-only features:** Run again, Delete history entry, Right-click context menus for history actions.

### 2. REST API

**For:** Programmatic access via HTTP — integrations, scripts, cross-machine access.

```bash
# Requires pip install "unit-converter[api]"
unit-converter-api           # default: http://127.0.0.1:8000

# or:
uvicorn unit_converter.api.main:app --host 0.0.0.0 --port 8000
```

- All 16 operations available as HTTP endpoints
- Swagger UI docs at `/docs`, ReDoc at `/redoc`
- JSON request/response bodies
- Standard HTTP error codes (422 for validation, 404 for unknown codes, 503 for network)

### 3. MCP Server

**For:** Integration with AI agents (Claude Desktop, Claude Code, custom MCP clients).

```bash
# Requires pip install "unit-converter[api]"

# Method A: stdio (for Claude Desktop, custom CLI tools)
unit-converter-mcp

# Method B: Streamable HTTP (for MCP clients that speak HTTP)
# (started as part of unit-converter-api)
unit-converter-api           # MCP at http://127.0.0.1:8000/mcp
```

- All 16 operations available as MCP tools
- Deterministic tool names (derived from FastAPI operation IDs)
- Structured tool call arguments and responses
- Agent-friendly error reporting (`isError: true`)

---

## Part A: Using the PySide6 desktop application

### Launching

```bash
unit-converter-gui
# or from source:
python -m unit_converter.gui.app
```

Requires the `[gui]` optional dependency group (`pip install "unit-converter[gui]"`).

### Making a conversion

1. Select a **magnitude** from the magnitude drop-down (e.g. `Mass`).
2. The unit drop-downs for **From** and **To** populate with the available units for that
   magnitude.
3. Enter a numeric value in either the **From** or the **To** field. The other field
   updates in real time (bidirectional conversion).
4. Conversion is live — no submit button is needed.

### Hover tooltips and help

Every interactive widget (magnitude selector, unit selectors, order controls, entry fields, sweep control) displays help text through:
- **Hover tooltip** — mouse over the control to see its purpose and valid inputs.
- **Keyboard focus** — Tab to a control and its tooltip appears (accessible description for screen readers).
- **WhatsThis** — keyboard users can press `?` to see detailed help text.

All help text is centralized in a single registry and consistently themed.

### Changing the order of magnitude

Each unit field has an associated **order** control. Scroll the mouse wheel over it, or
use the Up/Down arrow keys while it is focused, to cycle through SI prefix exponents
(e.g. `m` for milli, `k` for kilo, `M` for mega). For the **Data** magnitude the control
cycles through IEC binary prefixes (k = 1024, M = 1024², etc.) instead. Click the control
to reset it to `1` (no prefix).

The conversion formula applied is:

```
result = (value * base^from_order * from_factor) / (base^to_order * to_factor)
```

where `base` is 10 for all magnitudes except Data (where `base` is 1024).

### Digit sweep

A separate **sweep** control lets you adjust the numeric value by scrolling, incrementing
or decrementing by the current sweep step. Scroll the mouse wheel or use Up/Down keys while
the sweep control is focused. Click to reset to `...`.

**Result display:** Result numbers are capped at **10 decimal places (rounded)** by default.
You can override this cap by entering a negative integer into the sweep control (e.g. `-15`
to show 15 decimal places). The sweep control defaults to `"..."` (auto-detect, use the cap),
`"0"` (integer nudge, use the cap), `"-N"` (show N decimal places deep), or `"+N"` (tens/hundreds
position, use the cap).

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Enter / Return | Re-evaluate and trigger conversion |
| Up / Down | Increment / decrement the focused order or sweep control |
| Ctrl+C | Copy the conversion result to clipboard as a full expression (`<value> <unit> = <result> <unit>`) |
| Ctrl+V | Paste a numeric value into the focused entry field and trigger conversion; non-numeric input is silently ignored |
| Ctrl+F | Open the Find Unit search dialog |
| Ctrl+Q | Quit the application |

### Context menu (right-click)

Right-click anywhere in the main window to open a context menu with the following options:

1. **Settings...** — Opens the Settings dialog for theme selection and per-widget color picker.
2. **Copy result** (Ctrl+C) — Copies the conversion result to clipboard as a full expression.
3. **Find Unit...** (Ctrl+F) — Opens a search dialog to find units/magnitudes by substring (case- and accent-insensitive).
4. **Batch convert...** — Opens the batch-conversion dialog for multi-value or one-to-all-units conversions with CSV export.
5. **History / Favorites...** — Opens the conversion history panel to view and manage conversions (see below).
6. **Add Custom Unit...** — Opens the custom unit dialog to define and persist user-defined units.
7. **About...** — Displays application information (author, version, license).
8. **Exit** — Closes the application (equivalent to Ctrl+Q).

### History dialog and Favorites toggle

The History dialog displays a list of recent conversions (most-recent-first, capped at 100 non-favorite entries;
favorite entries are exempt from the cap). The dialog features:

- **Favorites toggle** — Switch between viewing the full history or only favorited entries.
- **Right-click context menu on list entries** with the following actions:
  - **Run again** — Populate the main window with this conversion's parameters and re-run it. **(GUI-only)**
  - **Delete** — Remove this entry from history entirely (works in both full and favorites-only view). **(GUI-only)**
  - **Add to Favorites** — Mark the entry as a favorite with an optional label (full-history view only).
  - **Remove from Favorites** — Clear the favorite flag and label (visible when the entry is already favorited).

### Settings and theming

The GUI supports Light and Dark themes with customizable per-widget colors. Access the Settings dialog by right-clicking the main window and selecting **"Settings..."**.

#### Theme selection

- **Built-in themes:** Choose from "Light" (cool neutral grey + blue accent) or "Dark" (dark blue-grey + warm amber accent).
- **Load theme button:** Click to reset all colors to the selected built-in theme's defaults.

#### Per-widget color picker

The Settings dialog displays 11 semantic color roles that control the appearance of different widget types:

| Color role | Usage |
|-----------|-------|
| `bg_main` | Main window and frame background |
| `bg_title` | Title/header label strips |
| `bg_entry` | Numeric entry field background |
| `bg_sweep` | Digit-sweep control background |
| `bg_combo` | Magnitude and unit dropdown backgrounds |
| `bg_dialog` | Dialog window backgrounds |
| `fg_title` | Title/header text (accent color) |
| `fg_main` | Body label and general text foreground |
| `fg_entry` | Entry field text foreground |
| `border_main` | General control border color |
| `border_heavy` | Thicker ridge border (order label, entry) |

For each color role, you can:

1. **Click the color swatch button** to open the color picker dialog (Office-style palette) and visually select a color.
2. **Type a hex color directly** in the text field (format: `#RRGGBB`, e.g. `#FF0000` for red). Invalid hex strings are highlighted with a red border for visual feedback.
3. **Click "Apply"** to see your changes immediately without closing the Settings dialog.
4. **Click "OK"** to apply your changes, persist them, and close the dialog.
5. **Click "Cancel"** to discard changes and close the dialog.

#### Persistence

Theme selection (Light/Dark) and all color overrides are persisted to `~/.unit-converter/gui_theme.json` and are automatically restored when you launch the application again.

### Find Unit search (Ctrl+F)

Access via **Find Unit...** in the right-click context menu or press **Ctrl+F** to open the search dialog.

1. **Type in the search field** — enter a unit name or magnitude name as a substring (e.g., `meter`, `kilo`, `temperature`, `angstrom`).
2. **Matching is case- and accent-insensitive** — so `metre`, `Metre`, `METRE`, and `mètre` all match equally.
3. **Results display** — matching units and magnitudes appear in a list, ordered by relevance (exact match, prefix, then substring).
4. **Select and apply** — click a result or press Enter to populate the magnitude and From-unit selectors with the selected unit. The To-unit defaults to the same unit.

This is useful for quickly locating a unit when you know its name but not its magnitude category.

### Batch conversion (Batch convert...)

Access via **Batch convert...** in the right-click context menu. (Requires a magnitude to be selected first.)

The batch-conversion dialog offers two modes:

#### Mode 1: Values list

Convert N numeric values from one unit to another, all in one go.

1. **Select mode:** Choose "Values list" from the Mode drop-down.
2. **Input:** Paste or type numeric values (one per line) in the text area, e.g.:
   ```
   1
   2.5
   1000
   ```
3. **Units:** Select source (From unit) and target (To unit) from the combo boxes. The dialog pre-fills these from the main window's current selection.
4. **Run batch:** Click "Run batch" to execute all conversions.
5. **Results table:** Successful conversions appear in the Output column; any errors (malformed input, out-of-range values) display in the Error column.
6. **Export:** Copy the table to clipboard (CSV format) or save to a file.

#### Mode 2: All units

Convert one value to every unit of the selected magnitude in one go.

1. **Select mode:** Choose "All units" from the Mode drop-down.
2. **Input:** Enter a single numeric value in the "Value:" field.
3. **Units:** Select the source (From unit). The dialog will convert your value to all units in the same magnitude.
4. **Run batch:** Click "Run batch" to execute.
5. **Results table:** Shows one row per target unit, with the converted value or error message.
6. **Export:** Copy or save as CSV.

**Export options:**
- **Copy table** — Copies the results to the system clipboard as CSV (tab-separated values, ready to paste into spreadsheets).
- **Save CSV...** — Opens a file-save dialog to write results to a `.csv` file.

### Input clamping

Negative values, `inf`, and `NaN` are clamped to `0.0` before conversion. This is the
documented behaviour of the core. Note: `0.0` is also the result for a genuine input of
exactly `0.0` — the two cases are indistinguishable from the output alone.

---

## Part B: Using the REST API

### Starting the REST server

```bash
# Primary entry point (REST + MCP server combined)
unit-converter-api

# or directly with uvicorn:
uvicorn unit_converter.api.main:app --host 127.0.0.1 --port 8000

# Expose to all network interfaces (use with caution):
unit-converter-api --host 0.0.0.0
uvicorn unit_converter.api.main:app --host 0.0.0.0 --port 8000
```

Default bind is `127.0.0.1:8000` (loopback only, appropriate for a single-user local tool).
The REST API is automatically available when you start the server.

### Base URL and Swagger/ReDoc docs

After starting the server:

| Resource | URL |
|----------|-----|
| REST API (all endpoints) | `http://localhost:8000/` |
| Interactive docs (Swagger) | `http://localhost:8000/docs` |
| Alternative docs (ReDoc) | `http://localhost:8000/redoc` |

All examples below assume the server is running on `http://localhost:8000`.

### Health check

**Endpoint:** `GET /health`

**Purpose:** Liveness check and version confirmation.

```bash
curl http://localhost:8000/health
```

**Response (HTTP 200):**

```json
{
  "status": "ok",
  "version": "1.1.0"
}
```

---

### Discovery: list magnitudes and units

#### List all magnitudes

**Endpoint:** `GET /magnitudes`

```bash
curl http://localhost:8000/magnitudes
```

**Response (HTTP 200):**

```json
[
  "Absorbed_dose",
  "Acceleration",
  "Amount_of_substance",
  "Area",
  "Data",
  "Density",
  "Electric_charge",
  "Electric_resistance",
  "Energy",
  "Equivalent_dose",
  "Force",
  "Frequency",
  "Length",
  "Mass",
  "Plane_angle",
  "Power",
  "Pressure",
  "Radiation_exposure",
  "Radioactivity",
  "Speed",
  "Temperature",
  "Temperature_delta",
  "Time",
  "Voltage",
  "Volume"
]
```

**Note:** Magnitude names use underscores and are case-sensitive. Use this list to confirm exact names.

#### List units for a magnitude

**Endpoint:** `GET /magnitudes/{magnitude}/units`

**Parameters:**
- `magnitude` (path) — Name of the magnitude (e.g. `Mass`, `Length`, `Energy`).

```bash
# Units for Mass
curl http://localhost:8000/magnitudes/Mass/units

# Units for Energy
curl http://localhost:8000/magnitudes/Energy/units
```

**Response (HTTP 200):**

```json
{
  "units": [
    "gram (g)",
    "Av. pound (lb)",
    "Av. ounce (oz)",
    "tonne (t)",
    "stone (st)",
    "grain (gr)",
    "carat (ct)",
    "slug",
    "unified atomic mass unit (u)"
  ],
  "base_unit": "gram (g)"
}
```

**Errors:**
- HTTP 422 if the magnitude is unknown.

---

### Basic conversion

**Endpoint:** `POST /convert`

**Parameters (JSON body):**
- `magnitude` (string, required) — The magnitude name (e.g. `Mass`, `Length`).
- `value` (float, required) — The input value.
- `from_unit` (string, required) — Source unit name (e.g. `"gram (g)"`, `"Av. pound (lb)"`).
- `to_unit` (string, required) — Target unit name.
- `from_order` (string, optional, default `"1"`) — SI/IEC prefix for the source unit (e.g. `"k"`, `"M"`, `"1"` for no prefix).
- `to_order` (string, optional, default `"1"`) — SI/IEC prefix for the target unit.
- `sig_figs` (integer, optional) — Round the result to this many significant figures. Omit or pass `null` to preserve full precision.

#### Example 1: Convert 1 pound to grams

```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": "Mass",
    "value": 1.0,
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)"
  }'
```

**Response (HTTP 200):**

```json
{
  "result": 453.59237
}
```

#### Example 2: Convert 1 kilometer to meters (using prefix)

```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": "Length",
    "value": 1.0,
    "from_unit": "meter (m)",
    "to_unit": "meter (m)",
    "from_order": "k",
    "to_order": "1"
  }'
```

**Response (HTTP 200):**

```json
{
  "result": 1000.0
}
```

#### Example 3: Convert with significant figures

```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": "Mass",
    "value": 1.0,
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
    "sig_figs": 3
  }'
```

**Response (HTTP 200):**

```json
{
  "result": 454.0
}
```

#### Example 4: IEC binary prefixes (Data magnitude)

Convert 1 gigabyte to bytes:

```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": "Data",
    "value": 1.0,
    "from_unit": "byte (B)",
    "to_unit": "byte (B)",
    "from_order": "G",
    "to_order": "1"
  }'
```

**Response (HTTP 200):**

```json
{
  "result": 1073741824.0
}
```

**Errors:**
- HTTP 422 if magnitude, unit, or order is unknown, or if `sig_figs` is invalid.
- HTTP 422 if units are incompatible (dimensional mismatch).

---

### Compound/derived units

The compound unit engine parses and converts expressions like `km/h`, `m/s`, `kg*m/s^2`.

#### Parse a compound expression

**Endpoint:** `GET /convert/compound/parse`

**Parameters:**
- `expr` (query string) — Compound expression (e.g. `"km/h"`, `"kg*m/s^2"`).

```bash
curl "http://localhost:8000/convert/compound/parse?expr=km/h"
```

**Response (HTTP 200):**

```json
{
  "expr": "km/h",
  "factor": 0.27777777777777778,
  "dimensions": {
    "Length": 1,
    "Time": -1
  }
}
```

#### Convert using compound expressions

**Endpoint:** `POST /convert/compound`

**Parameters (JSON body):**
- `value` (float, required) — Input value.
- `from_expr` (string, required) — Source compound expression (e.g. `"km/h"`).
- `to_expr` (string, required) — Target compound expression (e.g. `"m/s"`).

```bash
curl -X POST http://localhost:8000/convert/compound \
  -H "Content-Type: application/json" \
  -d '{
    "value": 100.0,
    "from_expr": "km/h",
    "to_expr": "m/s"
  }'
```

**Response (HTTP 200):**

```json
{
  "result": 27.777777777777776,
  "from_expr": "km/h",
  "to_expr": "m/s"
}
```

**Errors:**
- HTTP 422 if expressions contain syntax errors or unknown unit atoms.
- HTTP 422 if the dimensions do not match (e.g. `km/h` → `kg` is incompatible).

---

### Live currency conversion

Currency rates are fetched from the **Frankfurter API** (`api.frankfurter.dev`) and cached
locally in `~/.unit-converter/rates.json`. On network failure the cached table is used as an offline fallback.

#### List supported currency codes

**Endpoint:** `GET /currencies`

```bash
curl http://localhost:8000/currencies
```

**Response (HTTP 200):**

```json
[
  "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
  "HKD", "HRK", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN",
  "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "RUB", "SEK", "SGD", "THB",
  "TRY", "TWD", "UAH", "USD", "ZAR"
]
```

#### Get an exchange rate

**Endpoint:** `GET /currencies/rate`

**Parameters:**
- `from` (query string) — Source ISO 4217 currency code (e.g. `"USD"`).
- `to` (query string) — Target ISO 4217 currency code (e.g. `"EUR"`).

```bash
curl "http://localhost:8000/currencies/rate?from=USD&to=EUR"
```

**Response (HTTP 200):**

```json
{
  "from": "USD",
  "to": "EUR",
  "rate": 0.91,
  "date": "2026-06-13",
  "is_stale": false
}
```

**Interpretation:**
- `rate`: To convert from `from` to `to`, multiply by this value.
- `date`: Date of the rate in YYYY-MM-DD format.
- `is_stale`: `true` if the rate is from a cached prior date (network was unavailable when rates were loaded).

**Errors:**
- HTTP 404 if either currency code is unknown.
- HTTP 422 if query parameters are missing.

#### Convert between currencies

**Endpoint:** `POST /currencies/convert`

**Parameters (JSON body):**
- `value` (float, required, ≥ 0) — Amount to convert.
- `from` (string, required) — Source ISO 4217 code.
- `to` (string, required) — Target ISO 4217 code.

```bash
curl -X POST http://localhost:8000/currencies/convert \
  -H "Content-Type: application/json" \
  -d '{
    "from": "USD",
    "to": "EUR",
    "value": 100.0
  }'
```

**Response (HTTP 200):**

```json
{
  "result": 91.0,
  "rate": 0.91,
  "date": "2026-06-13",
  "is_stale": false
}
```

**Errors:**
- HTTP 404 if either currency code is unknown.
- HTTP 422 if `value` is negative or required fields are missing.

#### Force-refresh the rate cache

**Endpoint:** `POST /currencies/refresh`

**Parameters:** None.

```bash
curl -X POST http://localhost:8000/currencies/refresh
```

**Response (HTTP 200):**

```json
{
  "date": "2026-06-13",
  "base": "EUR",
  "currency_count": 32,
  "source": "live"
}
```

**Interpretation:**
- `date`: Latest rate date.
- `base`: Base currency (EUR from Frankfurter).
- `currency_count`: Number of rates in the response.
- `source`: `"live"` (rates from Frankfurter) or `"cached"` (offline fallback).

**Errors:**
- HTTP 503 if the upstream Frankfurter API is unreachable (network error).

---

### Conversion history and favorites

History is persisted to `~/.unit-converter/history.json` (most-recent-first).
Non-favorite entries are capped at **100 records**; when exceeded, oldest non-favorite entries are dropped.
**Favorite entries are exempt from the cap and never auto-dropped.**

#### Retrieve full history

**Endpoint:** `GET /history`

```bash
curl http://localhost:8000/history
```

**Response (HTTP 200):**

```json
[
  {
    "magnitude": "Mass",
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
    "from_order": "1",
    "to_order": "1",
    "value": 1.0,
    "result": 453.59237,
    "sig_figs": null,
    "timestamp": "2026-06-13T10:00:00Z",
    "favorite": false,
    "favorite_label": ""
  },
  {
    "magnitude": "Length",
    "from_unit": "meter (m)",
    "to_unit": "meter (m)",
    "from_order": "k",
    "to_order": "1",
    "value": 1.0,
    "result": 1000.0,
    "sig_figs": null,
    "timestamp": "2026-06-13T09:30:00Z",
    "favorite": true,
    "favorite_label": "km to m"
  }
]
```

#### Retrieve favorites only

**Endpoint:** `GET /history/favorites`

```bash
curl http://localhost:8000/history/favorites
```

**Response (HTTP 200):** Same format as `/history`, but only entries with `favorite: true`.

#### Record a conversion

**Endpoint:** `POST /history/record`

**Parameters (JSON body):**
- `magnitude` (string, required, non-empty) — The magnitude name.
- `value` (float, required) — Input value.
- `from_unit` (string, required, non-empty) — Source unit.
- `to_unit` (string, required, non-empty) — Target unit.
- `result` (float, required) — Conversion result.
- `from_order` (string, optional, default `"1"`) — Source prefix.
- `to_order` (string, optional, default `"1"`) — Target prefix.
- `sig_figs` (integer, optional) — Significant figures used (if any).

```bash
curl -X POST http://localhost:8000/history/record \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": "Mass",
    "value": 1.0,
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
    "result": 453.59237
  }'
```

**Response (HTTP 201):**

```json
{
  "magnitude": "Mass",
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)",
  "from_order": "1",
  "to_order": "1",
  "value": 1.0,
  "result": 453.59237,
  "sig_figs": null,
  "timestamp": "2026-06-13T10:05:00Z",
  "favorite": false,
  "favorite_label": ""
}
```

**Errors:**
- HTTP 422 if required fields are empty or missing.
- HTTP 422 if `sig_figs` is invalid.

#### Mark an entry as a favorite

**Endpoint:** `POST /history/favorites`

**Parameters (JSON body):**
- `timestamp` (string, required, non-empty) — ISO-8601 UTC timestamp of the entry to mark (e.g. `"2026-06-13T10:00:00Z"`).
- `label` (string, optional, default `""`) — Human-readable label for the favorite.

```bash
curl -X POST http://localhost:8000/history/favorites \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-06-13T10:00:00Z",
    "label": "lb to g baseline"
  }'
```

**Response (HTTP 200):**

```json
{
  "marked": true,
  "timestamp": "2026-06-13T10:00:00Z"
}
```

**Errors:**
- HTTP 422 if `timestamp` is empty or no matching entry exists.

#### Clear all history

**Endpoint:** `DELETE /history`

**Parameters:** None.

```bash
curl -X DELETE http://localhost:8000/history
```

**Response (HTTP 200):**

```json
{
  "cleared": true
}
```

---

### Custom user-defined units

Custom units are persisted to `~/.unit-converter/custom.toml` and are available immediately
in the same process after adding them. They are added to an existing magnitude with a conversion
factor relative to that magnitude's base unit.

#### Add a custom unit

**Endpoint:** `POST /units/custom`

**Parameters (JSON body):**
- `magnitude` (string, required, non-empty) — Name of an existing magnitude (e.g. `"Mass"`).
- `unit_name` (string, required, non-empty) — Name for the new unit. Must be ≤ 120 characters, free of control characters, path separators (`/`, `\`), and TOML structural characters (`[`, `]`, `=`).
- `factor` (float, required) — Conversion factor relative to the magnitude's base unit. Must be positive and finite. (e.g., if the base unit is grams and you're adding a unit that is 10 grams, pass `10.0`.)

```bash
curl -X POST http://localhost:8000/units/custom \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": "Mass",
    "unit_name": "my-stone",
    "factor": 6350.29
  }'
```

**Response (HTTP 201):**

```json
{
  "magnitude": "Mass",
  "unit_name": "my-stone",
  "factor": 6350.29
}
```

**Errors:**
- HTTP 422 if `magnitude` is unknown.
- HTTP 422 if `unit_name` is empty, too long, or contains forbidden characters.
- HTTP 422 if `factor` is ≤ 0, infinite, or NaN.

---

### Error handling

All errors conform to the following pattern:

**HTTP 422 (Unprocessable Content)** — Validation or conversion errors:
- Unknown magnitude, unit, or order key
- Incompatible units (dimensional mismatch)
- Invalid `sig_figs`, `factor`, or other constraints
- Syntax errors in compound expressions
- Empty or malformed required fields

```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Mass","value":1,"from_unit":"gram (g)","to_unit":"meter (m)"}'
```

**Response (HTTP 422):**

```json
{
  "detail": "IncompatibleUnitsError: Cannot convert between different magnitudes..."
}
```

**HTTP 404 (Not Found)** — Unknown currency code:

```bash
curl "http://localhost:8000/currencies/rate?from=USD&to=XYZ"
```

**Response (HTTP 404):**

```json
{
  "detail": "'XYZ'"
}
```

**HTTP 503 (Service Unavailable)** — Network failure during currency rate refresh:

```bash
# (when Frankfurter API is unreachable)
curl -X POST http://localhost:8000/currencies/refresh
```

**Response (HTTP 503):**

```json
{
  "detail": "Upstream rate service unavailable: [Network error description]"
}
```

---

## Part C: Using via MCP

MCP (Model Context Protocol) is a standard for AI agents to invoke functions across the web or stdio.
The Unit-Converter exposes **all 16 operations** as MCP tools, enabling Claude Desktop, Claude Code,
and other MCP clients to drive conversions programmatically.

### Starting the MCP server

Two transport options:

#### Option A: stdio (for Claude Desktop, CLI tools)

```bash
# Console script entry point
unit-converter-mcp

# or directly:
python -m unit_converter.api.mcp_server
```

Claude Desktop and CLI tools can spawn this process and communicate over stdin/stdout.

#### Option B: Streamable HTTP (for MCP HTTP clients)

```bash
# Part of the combined REST + MCP server
unit-converter-api

# or directly:
uvicorn unit_converter.api.main:app --host 127.0.0.1 --port 8000
```

The MCP server is available at `http://localhost:8000/mcp` (Streamable HTTP protocol).

### Registering with an MCP client

#### Claude Desktop (stdio method)

Edit `~/.config/Claude/claude_desktop_config.json` (macOS/Linux) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "unit-converter": {
      "command": "unit-converter-mcp"
    }
  }
}
```

Restart Claude Desktop. The Unit-Converter tools will appear in the Tool Use panel.

#### Claude Code or other MCP clients (Streamable HTTP method)

Configure the client to connect to the HTTP endpoint:

```json
{
  "mcpServers": {
    "unit-converter": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

(Details vary by client — consult the client's MCP setup documentation.)

### The 16 MCP tools

The following table maps each MCP tool name (derived from FastAPI operation IDs) to its feature and REST equivalent:

| # | MCP Tool Name | Feature | REST Equivalent |
|---|---|---|---|
| 1 | `health_health_get` | Health check | `GET /health` |
| 2 | `get_magnitudes_magnitudes_get` | List magnitudes | `GET /magnitudes` |
| 3 | `get_units_magnitudes` | List units for a magnitude | `GET /magnitudes/{magnitude}/units` |
| 4 | `post_convert_convert_post` | Convert between units | `POST /convert` |
| 5 | `list_currencies_currencies_get` | List currency codes | `GET /currencies` |
| 6 | `get_currency_rate_currencies_rate_get` | Get exchange rate | `GET /currencies/rate` |
| 7 | `post_convert_currency_currencies_convert_post` | Convert currencies | `POST /currencies/convert` |
| 8 | `post_refresh_rates_currencies_refresh_post` | Refresh rate cache | `POST /currencies/refresh` |
| 9 | `get_parse_compound_convert_compound_parse_get` | Parse compound expression | `GET /convert/compound/parse` |
| 10 | `post_convert_compound_convert_compound_post` | Convert compound units | `POST /convert/compound` |
| 11 | `get_history_history_get` | Retrieve full history | `GET /history` |
| 12 | `get_favorites_history_favorites_get` | Retrieve favorites | `GET /history/favorites` |
| 13 | `post_record_conversion_history_record_post` | Record a conversion | `POST /history/record` |
| 14 | `post_add_favorite_history_favorites_post` | Mark as favorite | `POST /history/favorites` |
| 15 | `delete_history_history_delete` | Clear all history | `DELETE /history` |
| 16 | `post_add_custom_unit_units_custom_post` | Add custom unit | `POST /units/custom` |

### Tool-call examples

Each tool is invoked with a set of arguments that match the REST endpoint's parameters. Responses are structured JSON objects (or arrays). On error, the tool returns a result with `isError: true` and a detail message.

#### Example 1: Health check

**Tool:** `health_health_get`

**Arguments:** (none)

**Response:**

```json
{
  "status": "ok",
  "version": "1.1.0"
}
```

#### Example 2: List magnitudes

**Tool:** `get_magnitudes_magnitudes_get`

**Arguments:** (none)

**Response:**

```json
[
  "Absorbed_dose",
  "Acceleration",
  "Amount_of_substance",
  "Area",
  "Data",
  "Density",
  "Electric_charge",
  "Electric_resistance",
  "Energy",
  "Equivalent_dose",
  "Force",
  "Frequency",
  "Length",
  "Mass",
  "Plane_angle",
  "Power",
  "Pressure",
  "Radiation_exposure",
  "Radioactivity",
  "Speed",
  "Temperature",
  "Temperature_delta",
  "Time",
  "Voltage",
  "Volume"
]
```

#### Example 3: List units for a magnitude

**Tool:** `get_units_magnitudes`

**Arguments:**

```json
{
  "magnitude": "Mass"
}
```

**Response:**

```json
{
  "units": [
    "gram (g)",
    "Av. pound (lb)",
    "Av. ounce (oz)",
    "tonne (t)",
    "stone (st)",
    "grain (gr)",
    "carat (ct)",
    "slug",
    "unified atomic mass unit (u)"
  ],
  "base_unit": "gram (g)"
}
```

#### Example 4: Convert a value

**Tool:** `post_convert_convert_post`

**Arguments:**

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

**Response:**

```json
{
  "result": 453.59237
}
```

#### Example 5: Convert with SI prefixes

**Tool:** `post_convert_convert_post`

**Arguments:**

```json
{
  "magnitude": "Length",
  "value": 1.0,
  "from_unit": "meter (m)",
  "to_unit": "meter (m)",
  "from_order": "k",
  "to_order": "1",
  "sig_figs": null
}
```

**Response:**

```json
{
  "result": 1000.0
}
```

#### Example 6: List currencies

**Tool:** `list_currencies_currencies_get`

**Arguments:** (none)

**Response:**

```json
[
  "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
  "HKD", "HRK", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN",
  "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "RUB", "SEK", "SGD", "THB",
  "TRY", "TWD", "UAH", "USD", "ZAR"
]
```

#### Example 7: Get exchange rate

**Tool:** `get_currency_rate_currencies_rate_get`

**Arguments:**

```json
{
  "from": "USD",
  "to": "EUR"
}
```

**Response:**

```json
{
  "from": "USD",
  "to": "EUR",
  "rate": 0.91,
  "date": "2026-06-13",
  "is_stale": false
}
```

#### Example 8: Convert currencies

**Tool:** `post_convert_currency_currencies_convert_post`

**Arguments:**

```json
{
  "from": "USD",
  "to": "EUR",
  "value": 100.0
}
```

**Response:**

```json
{
  "result": 91.0,
  "rate": 0.91,
  "date": "2026-06-13",
  "is_stale": false
}
```

#### Example 9: Refresh currency rates

**Tool:** `post_refresh_rates_currencies_refresh_post`

**Arguments:** (none)

**Response:**

```json
{
  "date": "2026-06-13",
  "base": "EUR",
  "currency_count": 32,
  "source": "live"
}
```

#### Example 10: Parse compound expression

**Tool:** `get_parse_compound_convert_compound_parse_get`

**Arguments:**

```json
{
  "expr": "km/h"
}
```

**Response:**

```json
{
  "expr": "km/h",
  "factor": 0.27777777777777778,
  "dimensions": {
    "Length": 1,
    "Time": -1
  }
}
```

#### Example 11: Convert compound units

**Tool:** `post_convert_compound_convert_compound_post`

**Arguments:**

```json
{
  "value": 100.0,
  "from_expr": "km/h",
  "to_expr": "m/s"
}
```

**Response:**

```json
{
  "result": 27.777777777777776,
  "from_expr": "km/h",
  "to_expr": "m/s"
}
```

#### Example 12: Retrieve history

**Tool:** `get_history_history_get`

**Arguments:** (none)

**Response:**

```json
[
  {
    "magnitude": "Mass",
    "from_unit": "Av. pound (lb)",
    "to_unit": "gram (g)",
    "from_order": "1",
    "to_order": "1",
    "value": 1.0,
    "result": 453.59237,
    "sig_figs": null,
    "timestamp": "2026-06-13T10:00:00Z",
    "favorite": false,
    "favorite_label": ""
  }
]
```

#### Example 13: Retrieve favorites

**Tool:** `get_favorites_history_favorites_get`

**Arguments:** (none)

**Response:** Same format as history, filtered to `favorite: true` entries.

#### Example 14: Record a conversion

**Tool:** `post_record_conversion_history_record_post`

**Arguments:**

```json
{
  "magnitude": "Mass",
  "value": 1.0,
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)",
  "result": 453.59237,
  "from_order": "1",
  "to_order": "1",
  "sig_figs": null
}
```

**Response:**

```json
{
  "magnitude": "Mass",
  "from_unit": "Av. pound (lb)",
  "to_unit": "gram (g)",
  "from_order": "1",
  "to_order": "1",
  "value": 1.0,
  "result": 453.59237,
  "sig_figs": null,
  "timestamp": "2026-06-13T10:05:00Z",
  "favorite": false,
  "favorite_label": ""
}
```

#### Example 15: Mark as favorite

**Tool:** `post_add_favorite_history_favorites_post`

**Arguments:**

```json
{
  "timestamp": "2026-06-13T10:00:00Z",
  "label": "lb to g baseline"
}
```

**Response:**

```json
{
  "marked": true,
  "timestamp": "2026-06-13T10:00:00Z"
}
```

#### Example 16: Clear history

**Tool:** `delete_history_history_delete`

**Arguments:** (none)

**Response:**

```json
{
  "cleared": true
}
```

#### Example 17: Add custom unit

**Tool:** `post_add_custom_unit_units_custom_post`

**Arguments:**

```json
{
  "magnitude": "Mass",
  "unit_name": "my-stone",
  "factor": 6350.29
}
```

**Response:**

```json
{
  "magnitude": "Mass",
  "unit_name": "my-stone",
  "factor": 6350.29
}
```

---

## Shared reference

### Conversion model

All conversion logic lives in `unit_converter/core/converter.py`. The public API is:

```python
from unit_converter.core.converter import list_magnitudes, list_units, convert

# List available magnitudes
list_magnitudes()
# -> ['Absorbed_dose', 'Acceleration', ..., 'Volume']

# List units for a magnitude
list_units("Mass")
# -> {'units': ['gram (g)', 'Av. pound (lb)', ...], 'base_unit': 'gram (g)'}

# Perform a conversion
convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
# -> 453.59237

# Conversion with SI prefix (1 km -> meters)
convert("Length", 1.0, "meter (m)", "meter (m)", from_order="k", to_order="1")
# -> 1000.0

# Data magnitude uses IEC binary prefixes (1 GiB -> bytes)
convert("Data", 1.0, "byte (B)", "byte (B)", from_order="G", to_order="1")
# -> 1073741824.0
```

The database is loaded lazily on the first call. `reload_database(data_dir)` forces a
reload from a specific directory (useful in tests).

---

### Significant figures / precision control

Pass `sig_figs` (a positive integer) to round the result to that many significant figures:

```python
convert("Mass", 1.0, "Av. pound (lb)", "gram (g)", sig_figs=3)
# -> 454.0

convert("Length", 12345.678, "meter (m)", "meter (m)", sig_figs=4)
# -> 12350.0
```

Over REST, include `"sig_figs": <int>` in the `POST /convert` body.
Over MCP, include `sig_figs` in the `post_convert_convert_post` tool arguments.
Omit the field (or pass `null`) to preserve full floating-point precision.

---

### Affine / temperature handling

Magnitudes with offset units (e.g. Temperature: °C, °F, K) use the affine conversion path:

```
base_value = input * order_from * from_factor + from_offset
result     = (base_value - to_offset) / (to_factor * order_to)
```

where `[factor, offset]` are stored per unit in the database. All existing magnitudes that
ship without an offset field use the pure-ratio path unchanged, so existing conversions are
byte-for-byte identical to earlier versions.

---

### Dimensional-compatibility guard

Attempting to convert between units that do not belong to the same magnitude raises
`IncompatibleUnitsError` (a subclass of `ValueError`). Over REST this propagates as
HTTP 422. Over MCP it is returned as a structured tool error (`isError: true`).

```python
from unit_converter.core.converter import IncompatibleUnitsError
try:
    convert("Mass", 1.0, "gram (g)", "meter (m)")   # wrong magnitude for "meter (m)"
except IncompatibleUnitsError as exc:
    print(exc)
```

---

### Order-of-magnitude prefixes

### SI decimal prefixes (all magnitudes except Data)

| Symbol | Name | Exponent (power of 10) |
|--------|------|------------------------|
| `q` | quecto | -30 |
| `r` | ronto | -27 |
| `y` | yocto | -24 |
| `z` | zepto | -21 |
| `a` | atto | -18 |
| `f` | femto | -15 |
| `p` | pico | -12 |
| `n` | nano | -9 |
| `μ` | micro | -6 |
| `m` | milli | -3 |
| `1` | (none) | 0 |
| `k` | kilo | 3 |
| `M` | mega | 6 |
| `G` | giga | 9 |
| `T` | tera | 12 |
| `P` | peta | 15 |
| `E` | exa | 18 |
| `Z` | zetta | 21 |
| `Y` | yotta | 24 |
| `R` | ronna | 27 |
| `Q` | quetta | 30 |

### IEC binary prefixes (Data magnitude only, base 1024)

| Symbol | Name | Exponent (power of 1024) |
|--------|------|--------------------------|
| `1` | (none) | 0 |
| `k` | kibi | 1 |
| `M` | mebi | 2 |
| `G` | gibi | 3 |
| `T` | tebi | 4 |
| `P` | pebi | 5 |
| `E` | exbi | 6 |
| `Z` | zebi | 7 |
| `Y` | yobi | 8 |
| `R` | (extended) | 9 |
| `Q` | (extended) | 10 |

The same symbol (e.g. `"G"`) means giga (10⁹) for all magnitudes except Data, where it
means gibi (1024³).

---

### Supported magnitudes (25)

The default database (`unit_converter/data/magnitudes.toml`) ships with **25 magnitudes**:

Absorbed dose, Acceleration, Amount of substance, Area, Data, Density, Electric charge,
Electric resistance, Energy, Equivalent dose, Force, Frequency, Length, Mass, Plane angle,
Power, Pressure, Radiation exposure, Radioactivity, Speed, Temperature, Temperature delta
(increments), Time, Voltage, Volume.

To see the current list and units at runtime:

```bash
# via the REST API (server must be running on port 8000):
curl http://localhost:8000/magnitudes

# via Python:
python -c "from unit_converter.core.converter import list_magnitudes; print(list_magnitudes())"

# via MCP:
# Use the get_magnitudes_magnitudes_get tool (no arguments)
```

**Note:** Magnitude names are internally stored with underscores (e.g. `Absorbed_dose`, `Electric_charge`)
and are case-sensitive. Use `list_magnitudes()` or the discovery endpoints to confirm exact names.

---

### Extending the unit database

The unit database is `unit_converter/data/magnitudes.toml`. Edit this file to add or
modify magnitudes and units shipped with the application. To add a unit at runtime without
editing the shipped file, use `POST /units/custom` (REST/MCP) or the GUI custom-unit dialog instead.

#### TOML format

Each magnitude is a TOML table with a `base_unit` key (informational) and a `units`
inline table mapping unit names to conversion factors relative to the base unit.

```toml
[Mass]
base_unit = "gram (g)"
units = { "gram (g)" = 1.0, "Av. pound (lb)" = 453.6, "Av. ounce (oz)" = 28.35 }

[Data]
base_unit = "bit (b)"
units = { "bit (b)" = 1.0, "byte (B)" = 8.0 }
```

#### Rules

- **Unit names** are arbitrary strings. Use parenthetical abbreviations by convention
  (e.g. `"kilometer (km)"`).
- **Conversion factors** are relative to the base unit (the first entry by convention).
  The factor for the base unit should be `1.0`.
- **Factors must be positive, non-zero, finite** floats. The loader rejects zero, negative,
  NaN, and infinite factors with a `MagnitudeDataError` and a precise error message.
- **Exponents in unit names** (e.g. `m²`, `m³`) use Unicode superscript characters
  directly. Do not use the digit `2` or `3` as a trailing exponent — write `m²` not `m2`.

#### Adding a new magnitude

```toml
[Speed]
base_unit = "meter per second (m/s)"
units = { "meter per second (m/s)" = 1.0, "kilometer per hour (km/h)" = 0.27778, "mile per hour (mph)" = 0.44704 }
```

After saving, restart the application or call `reload_database()` in Python to pick up
the change. No code changes are required.

---

## Summary

- **GUI:** Launch with `unit-converter-gui` for interactive, visual unit conversions. All features (magnitudes, conversions, history, favorites, custom units) are available through menus and dialogs.
- **REST API:** Start with `unit-converter-api` to access all 16 operations via HTTP. Perfect for scripts, integrations, and cross-machine use.
- **MCP:** Integrate with Claude Desktop or MCP clients using `unit-converter-mcp` (stdio) or the HTTP endpoint at `/mcp`. All 16 tools available.

All three faces delegate to the same pure Python core, so conversions are byte-for-byte identical across interfaces.
