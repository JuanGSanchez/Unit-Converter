"""
unit_converter.core.converter
==============================
Pure, UI-independent unit conversion logic.

This module contains **no GUI imports**.  It is the single source of
truth for conversion math and is the layer that the GUI, REST API, and MCP
server all call.

Public API
----------
list_magnitudes() -> list[str]
    Return the sorted list of available magnitude names.

list_units(magnitude: str) -> dict
    Return ``{"units": [str, ...], "base_unit": str}`` for a magnitude.

convert(
    magnitude: str,
    value: float,
    from_unit: str,
    to_unit: str,
    from_order: str = "1",
    to_order: str = "1",
    sig_figs: int | None = None,
) -> float
    Convert *value* from *from_unit* to *to_unit* within *magnitude*.
    *from_order* / *to_order* are SI-prefix keys (e.g. ``"k"``, ``"M"``) or
    ``"1"`` for no prefix.  For the ``Data`` magnitude the 1024-based IEC
    prefix table is used instead of the decimal SI table.
    If *sig_figs* is given (a positive integer), the result is rounded to that
    many significant figures; otherwise full floating-point precision is returned.

Input-clamping policy (matches original UI behaviour)
------------------------------------------------------
Negative values and math.inf are clamped to 0.0 before conversion.
NaN is clamped to 0.0.
Non-finite inputs never propagate to the division.
This is an explicit, documented behaviour, not a silent suppression.

Raises
------
ValueError
    - Unknown magnitude name.
    - Unknown unit name within the magnitude.
    - Unknown order/prefix key.
    - ``to_unit`` factor is zero (should not happen with a validated database,
      but guarded here as a second line of defence).
MagnitudeDataError (from data_loader)
    On first import if the database cannot be loaded.

Notes
-----
*Lazy loading*: the database is loaded once on first call to any public
function, not at module import time.  This allows the module to be imported
(e.g. for inspection or in test collection) without requiring the data files
to be present.  Call ``reload_database(data_dir)`` to force a reload (useful
in tests that supply a custom data directory).
"""

from __future__ import annotations

import math
from typing import Optional

from unit_converter.core.data_loader import MagnitudeDataError, load_magnitudes


# ---------------------------------------------------------------------------
# Public exception for cross-dimension conversions (UC-I02)
# ---------------------------------------------------------------------------

class IncompatibleUnitsError(ValueError):
    """
    Raised when *from_unit* and *to_unit* do not belong to the same magnitude.

    This is a subclass of ``ValueError`` so existing callers that catch
    ``ValueError`` continue to work; callers that need to distinguish
    cross-dimension errors can catch ``IncompatibleUnitsError`` explicitly.
    """


# ---------------------------------------------------------------------------
# SI-prefix / order-of-magnitude tables (matching original numeric behaviour exactly)
# ---------------------------------------------------------------------------

#: Decimal (SI) prefix exponents.  key = prefix symbol, value = power of 10.
DICT_ORDER_SI: dict[str, int] = {
    "q": -30, "r": -27, "y": -24, "z": -21, "a": -18, "f": -15, "p": -12,
    "n": -9,  "μ": -6, "m": -3, "1": 0,  "k": 3,  "M": 6,  "G": 9,
    "T": 12,  "P": 15,     "E": 18, "Z": 21,  "Y": 24,  "R": 27, "Q": 30,
}

#: IEC binary prefix exponents.  key = prefix symbol, value = power of 1024.
#: Used for the "Data" magnitude only (base 1024, matching original dict_order2).
DICT_ORDER_IEC: dict[str, int] = {
    "1": 0, "k": 1, "M": 2, "G": 3, "T": 4,
    "P": 5, "E": 6, "Z": 7, "Y": 8, "R": 9, "Q": 10,
}

#: The magnitude name that uses IEC binary prefixes instead of SI decimal ones.
_DATA_MAGNITUDE = "Data"


# ---------------------------------------------------------------------------
# Module-level database cache
# ---------------------------------------------------------------------------

_db: Optional[dict[str, dict[str, float]]] = None
_db_data_dir: Optional[str] = None  # records which dir was used to populate _db


def _get_db(data_dir: "str | None" = None) -> dict[str, dict[str, float]]:
    """
    Return the magnitude database, loading it lazily on first access.

    Thread safety: not guaranteed (this is a desktop single-thread app).
    If thread safety matters, callers should synchronise around this call.
    """
    global _db, _db_data_dir
    if _db is None or (data_dir is not None and data_dir != _db_data_dir):
        _db = load_magnitudes(data_dir)
        _db_data_dir = data_dir
    return _db


def reload_database(data_dir: "str | None" = None) -> None:
    """
    Force a reload of the magnitude database from *data_dir* (or the default).

    Useful in tests that supply a temporary data directory or a custom TOML
    fixture.  After calling this, the next API call will use the new database.
    """
    global _db, _db_data_dir
    _db = load_magnitudes(data_dir)
    _db_data_dir = data_dir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_magnitudes() -> list[str]:
    """
    Return a sorted list of available magnitude names.

    Example::

        >>> list_magnitudes()
        ['Area', 'Data', 'Energy', 'Length', 'Mass', 'Power', 'Pressure', 'Time', 'Volume']
    """
    return sorted(_get_db().keys())


def list_units(magnitude: str) -> dict:
    """
    Return unit information for *magnitude*.

    Returns
    -------
    dict with keys:
        ``"units"``     — ``list[str]``, unit names in database order.
        ``"base_unit"`` — ``str``, the first unit (factor closest to 1.0 by
                          convention; the convert() math works relative to it).

    Raises
    ------
    ValueError  if *magnitude* is not in the database.

    Example::

        >>> list_units("Mass")
        {'units': ['gram (g)', 'Av. pound (lb)', 'Av. ounce (oz)'], 'base_unit': 'gram (g)'}
    """
    db = _get_db()
    if magnitude not in db:
        raise ValueError(
            f"Unknown magnitude: {magnitude!r}.  "
            f"Available: {sorted(db.keys())}"
        )
    units = list(db[magnitude].keys())
    return {"units": units, "base_unit": units[0]}


def _round_sig_figs(value: float, sig_figs: int) -> float:
    """
    Round *value* to *sig_figs* significant figures.

    Returns 0.0 unchanged (log10 of zero is undefined).
    *sig_figs* must be a positive integer.
    """
    if value == 0.0:
        return 0.0
    magnitude_exp = math.floor(math.log10(abs(value)))
    factor = 10 ** (sig_figs - 1 - magnitude_exp)
    return round(value * factor) / factor


def convert(
    magnitude: str,
    value: float,
    from_unit: str,
    to_unit: str,
    from_order: str = "1",
    to_order: str = "1",
    sig_figs: "int | None" = None,
) -> float:
    """
    Convert *value* from *from_unit* to *to_unit* within *magnitude*.

    Parameters
    ----------
    magnitude:
        Name of the physical quantity (e.g. ``"Mass"``, ``"Data"``).
    value:
        Numeric value to convert.  Negative values and infinity are clamped
        to 0.0 (see *Input-clamping policy* in the module docstring).
    from_unit:
        Source unit name as it appears in the database.
    to_unit:
        Target unit name as it appears in the database.
    from_order:
        SI (or IEC for Data) prefix applied to *from_unit*.  Default ``"1"``
        means no prefix (multiplier = 1).  Example: ``"k"`` for kilo.
    to_order:
        SI (or IEC for Data) prefix applied to *to_unit*.
    sig_figs:
        If given (a positive integer), round the result to this many
        significant figures.  ``None`` (default) preserves full precision.

    Returns
    -------
    float
        The converted value.

    Raises
    ------
    ValueError
        On unknown magnitude, unit, or order key; or if *sig_figs* is not a
        positive integer.
    IncompatibleUnitsError
        If *from_unit* or *to_unit* do not exist within *magnitude* — a more
        specific subclass of ``ValueError`` for cross-dimension detection.

    Notes
    -----
    The conversion formula is::

        result = (value * base**from_order_exp * from_factor) /
                 (base**to_order_exp   * to_factor)

    where ``base`` is 10 for all magnitudes and 1024 for ``Data``,
    ``from_order_exp`` and ``to_order_exp`` are the integer exponent values
    from DICT_ORDER_SI / DICT_ORDER_IEC, and ``from_factor`` / ``to_factor``
    are the conversion factors relative to the base unit.

    For affine/temperature magnitudes (UC-I04), the formula uses offset
    metadata stored alongside the factor in the database; all existing
    magnitudes with no offset field use the pure-ratio path unchanged.

    Example::

        >>> convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
        453.6
        >>> convert("Data", 1.0, "byte (B)", "bit (b)")
        8.0
        >>> convert("Length", 1.0, "meter (m)", "meter (m)", from_order="k", to_order="1")
        1000.0
        >>> convert("Mass", 1.0, "Av. pound (lb)", "gram (g)", sig_figs=3)
        454.0
    """
    # --- validate sig_figs early ---
    if sig_figs is not None:
        if not isinstance(sig_figs, int) or sig_figs < 1:
            raise ValueError(
                f"sig_figs must be a positive integer, got {sig_figs!r}."
            )

    db = _get_db()

    # --- validate magnitude ---
    if magnitude not in db:
        raise ValueError(
            f"Unknown magnitude: {magnitude!r}.  "
            f"Available: {sorted(db.keys())}"
        )
    units = db[magnitude]

    # --- validate units (UC-I02: typed error for unknown/incompatible units) ---
    if from_unit not in units:
        raise IncompatibleUnitsError(
            f"Unknown unit {from_unit!r} in magnitude {magnitude!r}.  "
            f"Available: {list(units.keys())}"
        )
    if to_unit not in units:
        raise IncompatibleUnitsError(
            f"Unknown unit {to_unit!r} in magnitude {magnitude!r}.  "
            f"Available: {list(units.keys())}"
        )

    # --- select prefix table ---
    if magnitude == _DATA_MAGNITUDE:
        order_table = DICT_ORDER_IEC
        base = 1024
    else:
        order_table = DICT_ORDER_SI
        base = 10

    # --- validate order keys ---
    if from_order not in order_table:
        raise ValueError(
            f"Unknown order prefix {from_order!r} for magnitude {magnitude!r}.  "
            f"Available: {list(order_table.keys())}"
        )
    if to_order not in order_table:
        raise ValueError(
            f"Unknown order prefix {to_order!r} for magnitude {magnitude!r}.  "
            f"Available: {list(order_table.keys())}"
        )

    # --- input clamping (matches original UI behaviour) ---
    clamped = _clamp_input(value)

    # --- fetch factors (supports both plain float and affine [factor, offset] entries) ---
    from_entry = units[from_unit]
    to_entry = units[to_unit]
    if isinstance(from_entry, (list, tuple)):
        from_factor, from_offset = float(from_entry[0]), float(from_entry[1])
    else:
        from_factor, from_offset = float(from_entry), 0.0
    if isinstance(to_entry, (list, tuple)):
        to_factor, to_offset = float(to_entry[0]), float(to_entry[1])
    else:
        to_factor, to_offset = float(to_entry), 0.0

    # Short-circuit: 0.0 input on a pure-ratio magnitude always gives 0.0.
    # Do NOT short-circuit affine units (e.g. 0°C → 273.15 K is non-zero).
    is_affine = (from_offset != 0.0 or to_offset != 0.0)
    if clamped == 0.0 and not is_affine:
        return 0.0

    # Second-line defence: guard division by zero even if loader missed it.
    if to_factor == 0.0:
        raise ValueError(
            f"Conversion factor for unit {to_unit!r} in {magnitude!r} is zero "
            f"— cannot perform conversion."
        )

    # --- compute order multipliers ---
    order_from_exp = order_table[from_order]
    order_to_exp = order_table[to_order]
    order_from = base ** order_from_exp
    order_to = base ** order_to_exp

    # --- affine / offset handling (UC-I04) ---
    # For magnitudes with offset units (e.g. Temperature: °C, °F, K),
    # the database stores [factor, offset] per unit.
    # The affine formula (absolute conversion):
    #   base_value = clamped * order_from * from_factor + from_offset
    #   result     = (base_value - to_offset) / (to_factor * order_to)
    #
    # offset==0 for all existing magnitudes → pure-ratio path, byte-for-byte identical.
    if is_affine:
        # Affine path: offset units (e.g. temperature absolute conversion).
        # Convention: [factor, offset] such that T_base = T_unit * factor + offset.
        # Forward: base_value = clamped * order_from * from_factor + from_offset
        # Reverse: result = (base_value - to_offset) / (to_factor * order_to)
        base_value = clamped * order_from * from_factor + from_offset
        result = (base_value - to_offset) / (to_factor * order_to)
    else:
        # Pure-ratio path (all existing magnitudes): verbatim from original
        result = (clamped * order_from * from_factor) / (order_to * to_factor)

    # --- significant figures rounding (UC-I01) ---
    if sig_figs is not None:
        result = _round_sig_figs(result, sig_figs)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp_input(value: float) -> float:
    """
    Apply the input-clamping policy documented in the module docstring.

    Returns 0.0 for negative, NaN, or +inf/-inf inputs; otherwise returns
    the value unchanged.  Uses stdlib math throughout (no NumPy dependency).
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0

    if math.isnan(f) or math.isinf(f) or f < 0.0:
        return 0.0
    return f
