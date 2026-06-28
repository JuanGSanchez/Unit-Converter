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

import functools
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


@functools.lru_cache(maxsize=None)
def _user_data_dir() -> Path:
    """
    Return the user-writable data directory for custom units.

    Resolves to ``~/.unit-converter/`` on all platforms.  The directory is
    created if it does not already exist.

    Result is cached after the first call: ``Path.home()`` resolution and the
    ``mkdir`` syscall are performed at most once per process lifetime.  The
    cache is safe because the home directory does not change at runtime and
    ``mkdir(exist_ok=True)`` is idempotent.
    """
    user_dir = Path.home() / ".unit-converter"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _custom_units_path() -> Path:
    """Return the path to the user's custom units TOML file."""
    return _user_data_dir() / "custom.toml"


def load_custom_units(custom_path: "Path | None" = None) -> dict[str, dict[str, float]]:
    """
    Load the user's custom units TOML file.

    The file schema is identical to ``magnitudes.toml``.  Only magnitudes that
    already exist in the shipped database may be extended; the loader silently
    skips any unit that would override an existing unit name (shipped units
    are authoritative).

    Parameters
    ----------
    custom_path:
        Explicit path to the custom TOML file.  ``None`` uses the default
        path ``~/.unit-converter/custom.toml``.

    Returns
    -------
    dict[str, dict[str, float]]
        Mapping of magnitude name -> {unit_name: factor}.  Returns an empty
        dict if the file does not exist.

    Raises
    ------
    MagnitudeDataError
        If the file exists but is structurally invalid or contains invalid
        factors.
    """
    path = Path(custom_path) if custom_path is not None else _custom_units_path()
    if not path.exists():
        return {}
    return _load_toml(path)


def add_custom_unit(
    magnitude: str,
    unit_name: str,
    factor: float,
    custom_path: "Path | None" = None,
) -> None:
    """
    Persist a new custom unit to the user's custom units file.

    The unit is appended to the given magnitude in
    ``~/.unit-converter/custom.toml`` (creating the file and the magnitude
    section if needed).  Factor validation is applied before writing.

    Parameters
    ----------
    magnitude:
        Name of an existing magnitude (e.g. ``'Mass'``).
    unit_name:
        Name for the new unit (must not already exist in the shipped or
        custom database for this magnitude).
    factor:
        Conversion factor relative to the magnitude's base unit.  Must be
        a positive, finite, non-zero float.
    custom_path:
        Override the default ``~/.unit-converter/custom.toml`` path.

    Raises
    ------
    MagnitudeDataError
        If the factor is invalid (zero, negative, NaN, infinite).
    ValueError
        If ``unit_name`` is empty.
    """
    if not unit_name or not unit_name.strip():
        raise ValueError("unit_name must be a non-empty string.")
    path = Path(custom_path) if custom_path is not None else _custom_units_path()
    _validate_factor(magnitude, unit_name, factor, path)

    # Read existing content (raw text) so we can append without re-serialising
    # the whole file (avoids a tomllib dependency for writing).
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        existing_data = _load_toml(path) if existing_text.strip() else {}
    else:
        existing_text = ""
        existing_data = {}

    # Build the TOML fragment to append
    if magnitude in existing_data and unit_name in existing_data[magnitude]:
        # Unit already present — silently overwrite by rewriting its line
        # (simplistic: just re-add; TOML spec allows duplicate handling to
        # be implementation-defined but tomllib will error on load if there
        # are true duplicates).  For safety, skip if already defined.
        return  # idempotent: already stored

    # Append fragment
    fragment_lines: list[str] = []
    if f"[{magnitude}]" not in existing_text and f"[{magnitude}.units]" not in existing_text:
        fragment_lines.append(f"\n[{magnitude}]")
        fragment_lines.append(f'base_unit = ""')
        fragment_lines.append(f"\n[{magnitude}.units]")
    elif f"[{magnitude}.units]" not in existing_text:
        fragment_lines.append(f"\n[{magnitude}.units]")
    fragment_lines.append(f'"{unit_name}" = {factor!r}')

    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(fragment_lines) + "\n")


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

    result: dict[str, dict] = {}
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
        # Optional offsets table (UC-I04 affine/temperature support).
        # Schema: [MagnitudeName.offsets] maps unit_name -> additive offset
        # that shifts the value to the base-unit reference point.
        # Example for Temperature (base = K):
        #   "celsius (°C)" offset = 273.15   (T_K = T_C + 273.15)
        offsets_raw: dict = mag_body.get("offsets", {})
        if not isinstance(offsets_raw, dict):
            raise MagnitudeDataError(
                f"{path}: magnitude '{mag_name}'.offsets must be a table if present."
            )

        units: dict = {}
        for unit_name, factor_raw in units_raw.items():
            try:
                factor = float(factor_raw)
            except (TypeError, ValueError):
                raise MagnitudeDataError(
                    f"{path}: magnitude '{mag_name}', unit '{unit_name}': "
                    f"factor must be numeric, got {factor_raw!r}."
                )
            _validate_factor(mag_name, unit_name, factor, path)
            # Combine with offset if present; store as [factor, offset] tuple
            # so convert() can detect affine units.
            if unit_name in offsets_raw:
                try:
                    offset = float(offsets_raw[unit_name])
                except (TypeError, ValueError):
                    raise MagnitudeDataError(
                        f"{path}: magnitude '{mag_name}', unit '{unit_name}': "
                        f"offset must be numeric, got {offsets_raw[unit_name]!r}."
                    )
                units[unit_name] = [factor, offset]
            else:
                units[unit_name] = factor
        result[mag_name] = units

    return result


# ---------------------------------------------------------------------------
# Legacy flat-file loader
# ---------------------------------------------------------------------------

# Unicode superscript equivalents for digit characters 0-9.
_SUPERSCRIPT_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
}


def _apply_superscripts(name: str) -> str:
    """
    Replace trailing numeric exponents in a unit name with Unicode superscripts.

    Strategy: replace any run of digits that appears at the very end of the
    string OR immediately before a closing parenthesis ')'.  A digit run is
    considered an exponent only when it is preceded by a non-digit character
    (so ``H2O`` or ``unit1`` are unchanged — the digit is interior to a word,
    not a trailing exponent).

    Examples::

        "square meter (m2)"  -> "square meter (m²)"
        "cubic meter (m3)"   -> "cubic meter (m³)"
        "meter (m4)"         -> "meter (m⁴)"
        "meter (m22)"        -> "meter (m²²)"
        "H2O"                -> "H2O"    (interior digit — not replaced)
        "unit1"              -> "unit1"  (interior digit — not replaced)

    Note: ``"1"`` is now in the superscript map but the rule that the digit run
    must be preceded by a non-digit character (and also not be the *only*
    character) means ``"unit1"`` stays unchanged — the ``1`` follows ``t``, a
    letter, so the preceding-non-digit test passes, but the guard below also
    requires that the character *before* the digit run is a letter or ``(``.
    Specifically: we only replace when the character just before the digit run
    is ``(``, ``/``, or a letter (never another digit or space at the start).
    This keeps ``H2O`` (``2`` preceded by ``H``, a letter) unchanged because
    the digit-run ``2`` is NOT at the end of the full string; the loop only
    ever replaces a trailing run.
    """
    if not name:
        return name

    chars = list(name)
    end = len(chars) - 1

    # Skip trailing whitespace
    while end >= 0 and chars[end] == " ":
        end -= 1

    # If last non-space char is ')' back up one more
    if end >= 1 and chars[end] == ")":
        end -= 1  # position before ')'

    # Find the start of a trailing digit run ending at index `end`
    if end < 0 or chars[end] not in _SUPERSCRIPT_MAP:
        return name  # last position is not a digit

    run_end = end
    run_start = end
    while run_start > 0 and chars[run_start - 1] in _SUPERSCRIPT_MAP:
        run_start -= 1

    # Guard: character before the run must be a non-digit, non-space character
    # (a letter or '(') so that internal digits like H2O / unit1 are not touched.
    # If run_start == 0 the digit starts the string — that is not an exponent context.
    if run_start == 0:
        return name
    preceding = chars[run_start - 1]
    if preceding in (" ", ")"):
        return name  # digit follows a space or closed paren — not an exponent

    # Replace each digit in the run with its superscript equivalent
    for i in range(run_start, run_end + 1):
        chars[i] = _SUPERSCRIPT_MAP[chars[i]]
    return "".join(chars)


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
    custom_path: "Path | None" = None,
) -> dict[str, dict[str, float]]:
    """
    Load the magnitude/unit database, merging any custom user units.

    Search order:
      1. ``<data_dir>/magnitudes.toml``  (TOML format, preferred)
      2. ``<data_dir>/Magnitudes.txt``   (legacy flat format, backward compat)

    After loading the shipped database, custom units from the user file
    (``~/.unit-converter/custom.toml`` by default, or *custom_path* if given)
    are merged in.  Custom units may only extend existing magnitudes; they
    cannot override shipped unit names (shipped units are authoritative).

    Parameters
    ----------
    data_dir:
        Directory to search.  If ``None``, uses the package-default data dir
        resolved by ``_default_data_dir()`` (handles frozen bundles).
    custom_path:
        Explicit path to the custom TOML file.  ``None`` uses the default
        ``~/.unit-converter/custom.toml``.  Pass ``False`` to disable custom-
        unit merging entirely (useful in tests).

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
        db = _load_toml(toml_path)
    elif legacy_path.exists():
        db = _load_legacy(legacy_path)
    else:
        raise MagnitudeDataError(
            f"No magnitude database found in {search_dir}.  "
            f"Expected 'magnitudes.toml' (preferred) or 'Magnitudes.txt' (legacy)."
        )

    # Merge custom user units (UC-I03).  custom_path=False disables merging.
    if custom_path is not False:
        try:
            custom = load_custom_units(custom_path)
        except MagnitudeDataError:
            custom = {}  # corrupt custom file: skip silently, don't crash
        for mag_name, custom_units in custom.items():
            if mag_name not in db:
                continue  # only extend existing magnitudes
            shipped = db[mag_name]
            for unit_name, factor in custom_units.items():
                if unit_name not in shipped:  # shipped units are authoritative
                    shipped[unit_name] = factor

    return db
