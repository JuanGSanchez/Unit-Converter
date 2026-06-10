"""
unit_converter.core.data_loader
================================
Validated loader for the magnitude/unit database.

Load order (highest priority first):
  1. TOML file  — ``magnitudes.toml``   in the same directory as this module's
     data sibling (``unit_converter/data/``).  Parsed with stdlib ``tomllib``
     (Python >= 3.11).
  2. Legacy flat file — ``Magnitudes.txt`` in the same directory, using the
     original three-lines-per-magnitude format.  Kept for backward compat so
     users who only have the old file can still run the converter.

Public interface
----------------
load_magnitudes(data_dir: str | Path | None = None)
    -> dict[str, dict[str, float]]

    Returns a mapping of::

        { "Mass": {"gram (g)": 1.0, "Av. pound (lb)": 453.6, ...}, ... }

    The first unit in each magnitude is the base unit (factor == 1.0 by
    convention for the default database; the loader does NOT enforce that the
    first factor is exactly 1.0 because user databases may use a different base).

    ``data_dir``, when given, overrides the default search path (useful for
    tests and frozen-bundle usage).

Errors
------
``MagnitudeDataError``  -- raised for any structural/content problem that
    prevents safe usage of the database.  The message includes file path and
    line number where known.
"""

from __future__ import annotations

import math
import os
import sys
import tomllib
from pathlib import Path
from typing import Dict


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class MagnitudeDataError(ValueError):
    """Raised when the magnitude database cannot be loaded or validated."""


# ---------------------------------------------------------------------------
# Default data directory
# ---------------------------------------------------------------------------

def _default_data_dir() -> Path:
    """
    Resolve the data directory at runtime, handling frozen (PyInstaller) builds.

    When running from a PyInstaller bundle, ``sys._MEIPASS`` points to the
    temp dir that contains the bundled files.  Otherwise fall back to the
    directory that lives next to this source file's package root.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "unit_converter" / "data"
    # Running from source: navigate from this file up to package root then data/
    return Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# TOML loader
# ---------------------------------------------------------------------------

def _load_toml(path: Path) -> dict[str, dict[str, float]]:
    """
    Parse ``magnitudes.toml``.

    Expected TOML schema (one table per magnitude)::

        [Mass]
        base_unit = "gram (g)"
        units = { "gram (g)" = 1.0, "Av. pound (lb)" = 453.6, "Av. ounce (oz)" = 28.35 }

        [Data]
        base_unit = "bit (b)"
        units = { "bit (b)" = 1.0, "byte (B)" = 8.0 }

    ``base_unit`` is informational; the units dict is authoritative.
    ``units`` values must be positive, non-zero floats.

    Raises
    ------
    MagnitudeDataError  on any structural, type, or value problem.
    """
    try:
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
    except FileNotFoundError:
        raise MagnitudeDataError(f"TOML data file not found: {path}")
    except tomllib.TOMLDecodeError as exc:
        raise MagnitudeDataError(f"TOML parse error in {path}: {exc}") from exc

    if not isinstance(raw, dict) or not raw:
        raise MagnitudeDataError(f"{path}: top-level value must be a non-empty table.")

    result: dict[str, dict[str, float]] = {}
    for mag_name, mag_body in raw.items():
        if not isinstance(mag_body, dict):
            raise MagnitudeDataError(
                f"{path}: magnitude '{mag_name}' must be a TOML table, got {type(mag_body).__name__}."
            )
        units_raw = mag_body.get("units")
        if units_raw is None:
            raise MagnitudeDataError(
                f"{path}: magnitude '{mag_name}' is missing the required 'units' key."
            )
        if not isinstance(units_raw, dict) or not units_raw:
            raise MagnitudeDataError(
                f"{path}: magnitude '{mag_name}'.units must be a non-empty inline table."
            )
        units: dict[str, float] = {}
        for unit_name, factor_raw in units_raw.items():
            try:
                factor = float(factor_raw)
            except (TypeError, ValueError):
                raise MagnitudeDataError(
                    f"{path}: magnitude '{mag_name}', unit '{unit_name}': "
                    f"factor must be numeric, got {factor_raw!r}."
                )
            _validate_factor(mag_name, unit_name, factor, path)
            units[unit_name] = factor
        result[mag_name] = units

    return result


# ---------------------------------------------------------------------------
# Legacy flat-file loader
# ---------------------------------------------------------------------------

# Characters whose Unicode superscript forms should replace trailing digit
# tokens in unit names.  Only applied to exponent tokens that follow a closing
# parenthesis or are stand-alone — never to the interior of a word like "H2O".
_SUPERSCRIPT_MAP = {"2": "²", "3": "³"}


def _apply_superscripts(name: str) -> str:
    """
    Replace trailing numeric exponents in a unit name with Unicode superscripts.

    Examples::

        "square meter (m2)"  -> "square meter (m²)"
        "cubic meter (m3)"   -> "cubic meter (m³)"
        "H2O"                -> "H2O"   (not changed — '2' is not a trailing exponent)

    Strategy: only replace digits that appear at the very end of the string
    OR immediately before a closing parenthesis ')'.  This is explicit and
    avoids the original code's unconditional ``str.replace`` that would corrupt
    any name containing a bare '2' or '3'.
    """
    if not name:
        return name
    result = list(name)
    i = len(result) - 1
    # Skip trailing whitespace
    while i >= 0 and result[i] == " ":
        i -= 1
    # If last non-space char is ')' look at what is just before it
    if i >= 1 and result[i] == ")":
        i -= 1  # position before ')'
    sup = _SUPERSCRIPT_MAP.get(result[i])
    if sup is not None:
        result[i] = sup
    return "".join(result)


def _load_legacy(path: Path) -> dict[str, dict[str, float]]:
    """
    Parse the original ``Magnitudes.txt`` three-lines-per-magnitude format.

    Format::

        <magnitude name>
        <comma-separated unit names>
        <comma-separated conversion factors>
        <blank line or next magnitude>

    Rules / fixes vs. original code:
    - Blank lines are ignored (the original required zero blank lines at the end).
    - Line-count validation is enforced with a clear error message and line number.
    - Zero conversion factors are rejected (division-by-zero guard).
    - Superscript substitution is made explicit via ``_apply_superscripts``.

    Raises
    ------
    MagnitudeDataError  on any structural or content problem.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MagnitudeDataError(f"Legacy data file not found: {path}")
    except OSError as exc:
        raise MagnitudeDataError(f"Cannot read {path}: {exc}") from exc

    # Strip blank lines so the user does not have to worry about trailing newlines
    raw_lines = text.splitlines()
    lines = [ln for ln in raw_lines if ln.strip()]

    if len(lines) % 3 != 0:
        raise MagnitudeDataError(
            f"{path}: the file has {len(lines)} non-blank line(s) which is not "
            f"divisible by 3.  Each magnitude requires exactly three lines: "
            f"name / unit names / conversion factors."
        )

    result: dict[str, dict[str, float]] = {}
    for block_idx in range(len(lines) // 3):
        line_base = block_idx * 3  # 0-based index into *filtered* lines
        mag_name = lines[line_base].strip()
        unit_names_raw = lines[line_base + 1].split(",")
        factor_strs = lines[line_base + 2].split(",")

        if len(unit_names_raw) != len(factor_strs):
            raise MagnitudeDataError(
                f"{path} (block {block_idx + 1}, magnitude '{mag_name}'): "
                f"unit-name count ({len(unit_names_raw)}) does not match "
                f"factor count ({len(factor_strs)})."
            )

        units: dict[str, float] = {}
        for col_idx, (raw_unit, raw_factor) in enumerate(
            zip(unit_names_raw, factor_strs)
        ):
            unit_name = _apply_superscripts(raw_unit.strip())
            try:
                factor = float(raw_factor.strip())
            except ValueError:
                raise MagnitudeDataError(
                    f"{path} (block {block_idx + 1}, magnitude '{mag_name}', "
                    f"column {col_idx + 1}): cannot parse factor {raw_factor!r} as float."
                )
            _validate_factor(mag_name, unit_name, factor, path)
            units[unit_name] = factor

        if not units:
            raise MagnitudeDataError(
                f"{path} (block {block_idx + 1}): magnitude '{mag_name}' has no units."
            )
        result[mag_name] = units

    return result


# ---------------------------------------------------------------------------
# Shared validation helper
# ---------------------------------------------------------------------------

def _validate_factor(
    mag_name: str, unit_name: str, factor: float, source: Path
) -> None:
    """
    Validate that a conversion factor is a finite, positive, non-zero float.

    Raises MagnitudeDataError otherwise.  A zero factor would cause a
    ZeroDivisionError inside ``convert()``; a negative factor would produce
    nonsensical results; NaN/Inf factors indicate a corrupt data file.
    """
    if math.isnan(factor):
        raise MagnitudeDataError(
            f"{source}: magnitude '{mag_name}', unit '{unit_name}': "
            f"factor is NaN — data file is corrupt."
        )
    if math.isinf(factor):
        raise MagnitudeDataError(
            f"{source}: magnitude '{mag_name}', unit '{unit_name}': "
            f"factor is infinite — data file is corrupt."
        )
    if factor == 0.0:
        raise MagnitudeDataError(
            f"{source}: magnitude '{mag_name}', unit '{unit_name}': "
            f"factor is zero — this would cause a division-by-zero in convert()."
        )
    if factor < 0.0:
        raise MagnitudeDataError(
            f"{source}: magnitude '{mag_name}', unit '{unit_name}': "
            f"factor is negative ({factor}) — conversion factors must be positive."
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_magnitudes(
    data_dir: "str | os.PathLike[str] | None" = None,
) -> dict[str, dict[str, float]]:
    """
    Load the magnitude/unit database.

    Search order:
      1. ``<data_dir>/magnitudes.toml``  (TOML format, preferred)
      2. ``<data_dir>/Magnitudes.txt``   (legacy flat format, backward compat)

    Parameters
    ----------
    data_dir:
        Directory to search.  If ``None``, uses the package-default data dir
        resolved by ``_default_data_dir()`` (handles frozen bundles).

    Returns
    -------
    dict[str, dict[str, float]]
        ``{ magnitude_name: { unit_name: conversion_factor, ... }, ... }``

    Raises
    ------
    MagnitudeDataError
        If neither file exists, or if the found file is structurally invalid.
    """
    search_dir = Path(data_dir) if data_dir is not None else _default_data_dir()

    toml_path = search_dir / "magnitudes.toml"
    legacy_path = search_dir / "Magnitudes.txt"

    if toml_path.exists():
        return _load_toml(toml_path)

    if legacy_path.exists():
        return _load_legacy(legacy_path)

    raise MagnitudeDataError(
        f"No magnitude database found in {search_dir}.  "
        f"Expected 'magnitudes.toml' (preferred) or 'Magnitudes.txt' (legacy)."
    )
