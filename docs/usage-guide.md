# Unit-Converter — Usage Guide

This guide covers the PySide6 GUI, the conversion model, currency conversion, compound
units, history and favorites, custom units, and how to extend the unit database.

---

## Table of contents

1. [Using the PySide6 GUI](#using-the-pyside6-gui)
2. [Conversion model](#conversion-model)
3. [Significant figures / precision control](#significant-figures--precision-control)
4. [Affine / temperature handling](#affine--temperature-handling)
5. [Dimensional-compatibility guard](#dimensional-compatibility-guard)
6. [Order-of-magnitude prefixes](#order-of-magnitude-prefixes)
7. [Compound / derived units](#compound--derived-units)
8. [Live currency conversion](#live-currency-conversion)
9. [Conversion history and favorites](#conversion-history-and-favorites)
10. [Custom user-defined units](#custom-user-defined-units)
11. [Supported magnitudes](#supported-magnitudes)
12. [Extending the unit database](#extending-the-unit-database)

---

## Using the PySide6 GUI

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

### Hover tooltips

Every widget (magnitude selector, unit selectors, order controls, entry fields, sweep
control) carries a `QToolTip` description. Hover the mouse over any control to see its
purpose and valid inputs.

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

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| Enter / Return | Re-evaluate the current value |
| Up / Down | Increment / decrement the focused order or sweep control |
| Ctrl+Q | Quit the application |

### Context menu

Right-click the title-bar area for About and Exit options.

### Input clamping

Negative values, `inf`, and `NaN` are clamped to `0.0` before conversion. This is the
documented behaviour of the core. Note: `0.0` is also the result for a genuine input of
exactly `0.0` — the two cases are indistinguishable from the output alone.

---

## Conversion model

All conversion logic lives in `unit_converter/core/converter.py`. The public API is:

```python
from unit_converter.core.converter import list_magnitudes, list_units, convert

# List available magnitudes
list_magnitudes()
# -> ['Area', 'Data', 'Energy', 'Length', 'Mass', 'Power', 'Pressure', 'Time', 'Volume']

# List units for a magnitude
list_units("Mass")
# -> {'units': ['gram (g)', 'Av. pound (lb)', 'Av. ounce (oz)'], 'base_unit': 'gram (g)'}

# Perform a conversion
convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
# -> 453.6

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

## Significant figures / precision control

Pass `sig_figs` (a positive integer) to round the result to that many significant figures:

```python
convert("Mass", 1.0, "Av. pound (lb)", "gram (g)", sig_figs=3)
# -> 454.0

convert("Length", 12345.678, "meter (m)", "meter (m)", sig_figs=4)
# -> 12350.0
```

Over REST, include `"sig_figs": <int>` in the `POST /convert` body.
Over MCP, include `sig_figs` in the `post_convert` tool arguments.
Omit the field (or pass `null`) to preserve full floating-point precision.

---

## Affine / temperature handling

Magnitudes with offset units (e.g. Temperature: °C, °F, K) use the affine conversion path:

```
base_value = input * order_from * from_factor + from_offset
result     = (base_value - to_offset) / (to_factor * order_to)
```

where `[factor, offset]` are stored per unit in the database. All existing magnitudes that
ship without an offset field use the pure-ratio path unchanged, so existing conversions are
byte-for-byte identical to earlier versions.

---

## Dimensional-compatibility guard

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

## Order-of-magnitude prefixes

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

## Compound / derived units

The compound unit engine (`unit_converter.core.expr`) parses expressions like `km/h`,
`m/s`, `kg*m/s^2`. It resolves each atom against the magnitude database, computes a
combined SI factor and dimension vector, and checks dimensional compatibility before
converting.

### REST

```bash
# Parse an expression
curl "http://localhost:8000/convert/compound/parse?expr=km/h"
# -> {"expr": "km/h", "factor": 0.27778, "dimensions": {...}}

# Convert using compound expressions
curl -X POST http://localhost:8000/convert/compound \
  -H "Content-Type: application/json" \
  -d '{"value": 100, "from_expr": "km/h", "to_expr": "m/s"}'
# -> {"result": 27.778, "from_expr": "km/h", "to_expr": "m/s"}
```

HTTP 422 is returned on dimension mismatches, unknown unit atoms, or syntax errors.

---

## Live currency conversion

Currency rates are fetched from the **Frankfurter API** (`api.frankfurter.dev`) and cached
locally as a dated table in `~/.unit-converter/rates.json`. On network failure the cached
table is used as an offline fallback.

### REST

```bash
# List supported ISO 4217 currency codes
curl http://localhost:8000/currencies

# Get the EUR→USD rate
curl "http://localhost:8000/currencies/rate?from=EUR&to=USD"
# -> {"from": "EUR", "to": "USD", "rate": 1.082, "date": "2026-06-13", "is_stale": false}

# Convert 100 EUR to USD
curl -X POST http://localhost:8000/currencies/convert \
  -H "Content-Type: application/json" \
  -d '{"from": "EUR", "to": "USD", "value": 100}'
# -> {"result": 108.2, "rate": 1.082, "date": "2026-06-13", "is_stale": false}

# Force-refresh the rate cache
curl -X POST http://localhost:8000/currencies/refresh
```

`is_stale: true` means the cached rates are from a prior date (offline or stale).
HTTP 404 is returned for unknown currency codes; HTTP 503 if the upstream is unreachable
during a forced refresh.

---

## Conversion history and favorites

History is persisted to `~/.unit-converter/history.json` (capped list, most-recent-first).
Each entry records magnitude, units, orders, input value, result, `sig_figs`, and an
ISO-8601 UTC timestamp. Entries can be marked as favorites with an optional label.

### REST

```bash
# Retrieve full history
curl http://localhost:8000/history

# Retrieve only favorites
curl http://localhost:8000/history/favorites

# Record a conversion manually
curl -X POST http://localhost:8000/history/record \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Mass","value":1.0,"from_unit":"Av. pound (lb)","to_unit":"gram (g)","result":453.6}'

# Mark an entry as a favorite
curl -X POST http://localhost:8000/history/favorites \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2026-06-13T10:00:00Z","label":"lb to g baseline"}'

# Clear all history
curl -X DELETE http://localhost:8000/history
```

### GUI

The history panel is accessible from the main window. Recent conversions appear
automatically; click an entry to mark it as a favorite.

---

## Custom user-defined units

Custom units are persisted to `~/.unit-converter/custom.toml` and are available
immediately in the same process after adding them. They are added to an existing
magnitude with a conversion factor relative to that magnitude's base unit.

### REST

```bash
curl -X POST http://localhost:8000/units/custom \
  -H "Content-Type: application/json" \
  -d '{"magnitude":"Mass","unit_name":"stone (st)","factor":6350.29}'
# -> {"magnitude":"Mass","unit_name":"stone (st)","factor":6350.29}  (HTTP 201)
```

Validation: `unit_name` must be non-empty, ≤ 120 chars, free of control characters, path
separators, and TOML structural characters. `factor` must be a positive finite number.
HTTP 422 on any validation failure.

### GUI

Use the **Add custom unit** dialog (accessible from the main window) to define and persist
a new unit without editing any file.

---

## Supported magnitudes

The default database (`unit_converter/data/magnitudes.toml`) ships with nine magnitudes:
Area, Data, Energy, Length, Mass, Power, Pressure, Time, Volume.

To see the current list and units at runtime:

```bash
# via the REST API (server must be running on port 8000):
curl http://localhost:8000/magnitudes

# via Python:
python -c "from unit_converter.core.converter import list_magnitudes; print(list_magnitudes())"
```

---

## Extending the unit database

The unit database is `unit_converter/data/magnitudes.toml`. Edit this file to add or
modify magnitudes and units shipped with the application. To add a unit at runtime without
editing the shipped file, use `POST /units/custom` or the GUI custom-unit dialog instead.

### TOML format

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
