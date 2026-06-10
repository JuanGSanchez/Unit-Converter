# Unit-Converter — Usage Guide

This guide covers the PySide6 GUI, the conversion model, and how to extend the unit database.

---

## Table of contents

1. [Using the PySide6 GUI](#using-the-pyside6-gui)
2. [Conversion model](#conversion-model)
3. [Order-of-magnitude prefixes](#order-of-magnitude-prefixes)
4. [Supported magnitudes](#supported-magnitudes)
5. [Extending the unit database](#extending-the-unit-database)
6. [Legacy Tkinter entry point](#legacy-tkinter-entry-point)

---

## Using the PySide6 GUI

### Launching

```bash
unit-converter-gui
```

Requires the `[gui]` optional dependency group (`pip install "unit-converter[gui]"`).

### Making a conversion

1. Select a **magnitude** from the magnitude drop-down (e.g. `Mass`).
2. The unit drop-downs for **From** and **To** populate with the available units for that
   magnitude.
3. Enter a numeric value in either the **From** or the **To** field. The other field
   updates in real time (bidirectional conversion).
4. Conversion is live — no submit button is needed.

### Changing the order of magnitude

Each unit field has an associated **order** control. Scroll the mouse wheel over it, or
use the Up/Down arrow keys while it is focused, to cycle through SI prefix exponents
(e.g. `m` for milli, `k` for kilo, `M` for mega). For the **Data** magnitude the control
cycles through IEC binary prefixes (k = 1024, M = 1024², etc.) instead.

The conversion formula applied is:

```
result = (value * base^from_order * from_factor) / (base^to_order * to_factor)
```

where `base` is 10 for all magnitudes except Data (where `base` is 1024).

### Digit sweep

A separate **sweep** control lets you adjust the numeric value by scrolling, incrementing
or decrementing by the current sweep step. Scroll the mouse wheel or use Up/Down keys while
the sweep control is focused.

### Reset

Click the value field to reset it to zero and clear the conversion.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| Enter / Return | Re-evaluate the current value |
| Up / Down | Increment / decrement the focused order or sweep control |
| Right Ctrl | Cycle the sweep step |

### Context menu

Right-click a value field for clipboard operations (copy/paste).

### Input clamping

Negative values, `inf`, and `NaN` are clamped to `0.0` before conversion. This is the
documented behaviour of the core and matches the original application.

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
modify magnitudes and units. The legacy `Magnitudes.txt` is still readable but the TOML
format is preferred.

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
- **Exponents in unit names** (e.g. `m²`, `m³`) are stored using Unicode superscript
  characters directly. Do not use the digit `2` or `3` as a trailing exponent in new
  entries — write `m²` not `m2`.

#### Adding a new magnitude

```toml
[Speed]
base_unit = "meter per second (m/s)"
units = { "meter per second (m/s)" = 1.0, "kilometer per hour (km/h)" = 0.27778, "mile per hour (mph)" = 0.44704 }
```

After saving, restart the application or call `reload_database()` in Python to pick up
the change. No code changes are required.

### Legacy Magnitudes.txt format

The legacy file uses a three-lines-per-magnitude structure:

```
<magnitude name>
<comma-separated unit names>
<comma-separated conversion factors>
```

Blank lines between blocks are ignored. The loader enforces the same zero-factor and
positive-factor rules as the TOML loader.

When both `magnitudes.toml` and `Magnitudes.txt` are present, TOML takes precedence.

---

## Legacy Tkinter entry point

`UConverter_UI.pyw` is the original Tkinter-based application, retained for backward
compatibility. It is no longer the primary entry point.

To run it directly:

```bash
python UConverter_UI.pyw
# or via the installed script:
unit-converter
```

The Tkinter entry point does not use the `unit_converter.core` package. It is a
self-contained legacy module. It may be removed in a future release.
