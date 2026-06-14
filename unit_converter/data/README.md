# Unit-Converter data files

This directory holds the magnitude / unit database.

## Files

- **`magnitudes.toml`** — the **canonical, authoritative** unit database. Loaded
  by `unit_converter.core.data_loader` (stdlib `tomllib`). All unit names
  exposed by the GUI and the REST/MCP API come from this file.
- **`Magnitudes.txt`** — the legacy CSV-style database, retained for reference.
  Its unit names differ from the TOML in some cases (see mapping below). It is
  **not** the source of truth.
- **`currency_snapshot.json`** — cached exchange-rate snapshot for the Currency
  feature (written/refreshed by `unit_converter.core.rates`).

## Canonical unit names — source of truth (UC-B09)

`magnitudes.toml` is the single source of truth for supported unit names. Use the
TOML names when calling `convert`, `list_units`, the REST routes, or the MCP
tools. The legacy `Magnitudes.txt` "corrected" some spellings and lacks Unicode
superscripts, so the two files are **not** name-identical — a name valid in one
file may not resolve in the other.

### Legacy → canonical name mapping

Verified by reading both `Magnitudes.txt` and `magnitudes.toml` on 2026-06-14.

**Energy** (spelling corrections):

| Legacy name (`Magnitudes.txt`) | Canonical name (`magnitudes.toml`) |
|--------------------------------|-------------------------------------|
| `jule (J)`                     | `joule (J)`                         |
| `electronvolt (Ev)`            | `electronvolt (eV)`                 |

**Area** (ASCII digit → Unicode superscript):

| Legacy name           | Canonical name        |
|-----------------------|-----------------------|
| `square meter (m2)`   | `square meter (m²)`   |
| `square inch (in2)`   | `square inch (in²)`   |
| `square yard (yd2)`   | `square yard (yd²)`   |
| `square mile (mi2)`   | `square mile (mi²)`   |

**Volume** (ASCII digit → Unicode superscript):

| Legacy name         | Canonical name      |
|---------------------|---------------------|
| `cubic meter (m3)`  | `cubic meter (m³)`  |

(The superscript normalisation is applied by
`data_loader._apply_superscripts`; the legacy file stores plain ASCII `2`/`3`.)

### Names that match in both files

Mass, Length, Time, Power, Pressure, and Data unit names are identical across the
two files. The `Temperature` and `Temperature_delta` magnitudes exist only in
`magnitudes.toml` (added with the affine-temperature feature) and have no legacy
counterpart.

### If you load the legacy file

If you load `Magnitudes.txt` directly, expect the legacy spellings above; they
will not match the canonical TOML keys. Always prefer `magnitudes.toml`.
