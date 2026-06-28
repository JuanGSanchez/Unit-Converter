"""
unit_converter.api.service
===========================
Single shared service layer.

**Both** the REST app (``rest.py``) and the MCP server (``mcp_server.py``)
call this module.  No conversion logic is duplicated here — every operation
is a thin, typed wrapper over the ``unit_converter.core.*`` modules.

Error contract
--------------
Errors from the core are re-raised unchanged so callers can map them to
transport-appropriate codes:

- ``ValueError`` (and its subclasses ``IncompatibleUnitsError``,
  ``IncompatibleDimensionsError``, ``MagnitudeDataError``) → HTTP 422 / MCP
  tool error.
- ``KeyError`` (unknown currency code) → HTTP 404.
- ``urllib.error.URLError`` / ``socket.timeout`` (network failure on
  ``refresh_rates``) → HTTP 503.

Callers (``rest.py``, MCP layer via FastAPI) are responsible for mapping
these to their transport's error format.
"""
from __future__ import annotations

import math
import re
import socket
import urllib.error
from dataclasses import asdict
from typing import Optional

from unit_converter.core.converter import (
    convert as _core_convert,
    list_magnitudes as _core_list_magnitudes,
    list_units as _core_list_units,
)
from unit_converter.core import rates as _rates
from unit_converter.core import expr as _expr
from unit_converter.core import history as _history
from unit_converter.core.data_loader import add_custom_unit as _core_add_custom_unit

# ---------------------------------------------------------------------------
# Module-level cache for the static magnitude list
# ---------------------------------------------------------------------------

# The sorted list of magnitude names is stable after the core DB loads: no
# API operation adds new magnitudes (add_custom_unit adds units to existing
# magnitudes only).  Cache the sorted list on first call so subsequent
# GET /magnitudes requests do not pay the cost of sorted() + list allocation.
_magnitude_list_cache: "list[str] | None" = None


# ---------------------------------------------------------------------------
# Input-validation helpers (boundary guards for state-changing ops)
# ---------------------------------------------------------------------------

# Reject unit names that look like path traversal or TOML-injection attempts.
_SAFE_UNIT_NAME_RE = re.compile(r'^[^\x00-\x1f/\\<>:"|?*\[\]{}#=]+$')
_MAX_UNIT_NAME_LEN = 120


def _validate_unit_name(unit_name: str) -> None:
    """Raise ValueError if *unit_name* is unsafe or malformed."""
    if not unit_name or not unit_name.strip():
        raise ValueError("unit_name must be a non-empty string.")
    if len(unit_name) > _MAX_UNIT_NAME_LEN:
        raise ValueError(
            f"unit_name exceeds maximum length of {_MAX_UNIT_NAME_LEN} characters."
        )
    if not _SAFE_UNIT_NAME_RE.match(unit_name):
        raise ValueError(
            "unit_name contains disallowed characters "
            "(control chars, path separators, or TOML structural chars)."
        )


def _validate_factor(factor: float) -> None:
    """Raise ValueError if *factor* is not a positive finite float."""
    if math.isnan(factor) or math.isinf(factor):
        raise ValueError("factor must be a finite number.")
    if factor <= 0.0:
        raise ValueError(f"factor must be a positive number, got {factor!r}.")


# ---------------------------------------------------------------------------
# Core conversion (existing ops, unchanged)
# ---------------------------------------------------------------------------


def list_magnitudes() -> list[str]:
    """Return the sorted list of available magnitude names.

    Returns
    -------
    list[str]
        Sorted magnitude names, e.g. ``['Area', 'Data', 'Energy', ...]``.

    Notes
    -----
    The result is cached after the first call because the set of magnitudes is
    fixed at data-load time; no API operation adds new magnitudes.
    """
    global _magnitude_list_cache
    if _magnitude_list_cache is None:
        _magnitude_list_cache = _core_list_magnitudes()
    return _magnitude_list_cache


def list_units(magnitude: str) -> dict:
    """Return unit information for *magnitude*.

    Parameters
    ----------
    magnitude:
        Magnitude name (e.g. ``'Mass'``, ``'Data'``).

    Returns
    -------
    dict
        ``{"units": list[str], "base_unit": str}``

    Raises
    ------
    ValueError
        If *magnitude* is not in the database.
    """
    return _core_list_units(magnitude)


def convert(
    magnitude: str,
    value: float,
    from_unit: str,
    to_unit: str,
    from_order: str = "1",
    to_order: str = "1",
    sig_figs: "int | None" = None,
) -> float:
    """Convert *value* from *from_unit* to *to_unit* within *magnitude*.

    Parameters
    ----------
    magnitude:
        Physical quantity name (e.g. ``'Mass'``, ``'Length'``).
    value:
        Numeric value to convert.  Negative values and ``inf``/NaN are
        clamped to ``0.0`` by the core (see ``core.converter`` docs).
    from_unit:
        Source unit name as it appears in the database.
    to_unit:
        Target unit name as it appears in the database.
    from_order:
        SI (or IEC for ``Data``) prefix key for the source unit.
        Default ``"1"`` means no prefix (multiplier = 1).
    to_order:
        SI (or IEC for ``Data``) prefix key for the target unit.
    sig_figs:
        Optional positive integer — round the result to this many significant
        figures.  ``None`` (default) preserves full floating-point precision.

    Returns
    -------
    float
        The converted value.

    Raises
    ------
    ValueError
        On unknown magnitude, unit, or order key, or if *sig_figs* is invalid.
    IncompatibleUnitsError (subclass of ValueError)
        If *from_unit* or *to_unit* do not exist within *magnitude*.
    """
    return _core_convert(magnitude, value, from_unit, to_unit, from_order, to_order, sig_figs)


# ---------------------------------------------------------------------------
# Currency operations
# ---------------------------------------------------------------------------


def list_currencies() -> list[str]:
    """Return the sorted list of supported ISO 4217 currency codes.

    Uses the cached/live rate table (loads on demand; falls back to bundled
    snapshot if offline).

    Returns
    -------
    list[str]
        Sorted currency codes, e.g. ``['AUD', 'EUR', 'GBP', 'USD', ...]``.
    """
    return _rates.list_currencies()


def get_rate(from_code: str, to_code: str) -> dict:
    """Return the exchange rate from *from_code* to *to_code*.

    Parameters
    ----------
    from_code, to_code:
        ISO 4217 currency codes (e.g. ``"USD"``, ``"EUR"``).

    Returns
    -------
    dict
        ``{"from": str, "to": str, "rate": float, "date": str,
           "is_stale": bool}``

    Raises
    ------
    KeyError
        If either currency code is not in the rate table.
    """
    result = _rates.load_rates()
    rate = _rates.get_rate(from_code, to_code, result)
    return {
        "from": from_code,
        "to": to_code,
        "rate": rate,
        "date": result.date,
        "is_stale": result.is_stale,
    }


def convert_currency(value: float, from_code: str, to_code: str) -> dict:
    """Convert *value* from *from_code* to *to_code*.

    Parameters
    ----------
    value:
        Amount to convert (must be non-negative).
    from_code, to_code:
        ISO 4217 currency codes.

    Returns
    -------
    dict
        ``{"result": float, "rate": float, "date": str, "is_stale": bool}``

    Raises
    ------
    KeyError
        If either currency code is not in the rate table.
    ValueError
        If *value* is negative, NaN, or infinite.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError("value must be a finite number.")
    if value < 0:
        raise ValueError("value must be non-negative.")
    result = _rates.load_rates()
    rate = _rates.get_rate(from_code, to_code, result)
    return {
        "result": value * rate,
        "rate": rate,
        "date": result.date,
        "is_stale": result.is_stale,
    }


def refresh_rates() -> dict:
    """Force a live fetch of exchange rates and update the local cache.

    Returns
    -------
    dict
        ``{"date": str, "base": str, "currency_count": int, "source": str}``

    Raises
    ------
    urllib.error.URLError / socket.timeout
        If the upstream Frankfurter API is unreachable.
    """
    result = _rates.refresh_rates()
    return {
        "date": result.date,
        "base": result.base,
        "currency_count": len(result.rates),
        "source": result.source,
    }


# ---------------------------------------------------------------------------
# Compound unit operations
# ---------------------------------------------------------------------------


def parse_compound(expr: str) -> dict:
    """Parse a compound unit expression and return its dimension vector.

    Parameters
    ----------
    expr:
        Compound unit expression, e.g. ``"km/h"``, ``"kg*m/s^2"``.

    Returns
    -------
    dict
        ``{"expr": str, "factor": float, "dimensions": dict[str, int]}``

    Raises
    ------
    ExpressionSyntaxError / UnknownUnitError (subclasses of ValueError)
        On invalid expression or unknown unit atom.
    """
    cr = _expr.parse_compound(expr)
    return {
        "expr": cr.unit_str,
        "factor": cr.factor,
        "dimensions": cr.dimensions,
    }


def convert_compound(value: float, from_expr: str, to_expr: str) -> dict:
    """Convert *value* from *from_expr* to *to_expr* (compound units).

    Parameters
    ----------
    value:
        Numeric value to convert.
    from_expr:
        Source compound unit expression (e.g. ``"km/h"``).
    to_expr:
        Target compound unit expression (e.g. ``"m/s"``).

    Returns
    -------
    dict
        ``{"result": float, "from_expr": str, "to_expr": str}``

    Raises
    ------
    IncompatibleDimensionsError (subclass of ValueError)
        If the dimension vectors of *from_expr* and *to_expr* differ.
    ExpressionSyntaxError / UnknownUnitError (subclasses of ValueError)
        On invalid expression or unknown unit atom.
    """
    result = _expr.convert_compound(value, from_expr, to_expr)
    return {"result": result, "from_expr": from_expr, "to_expr": to_expr}


# ---------------------------------------------------------------------------
# History operations
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: "_history.HistoryEntry") -> dict:
    return asdict(entry)


def load_history() -> list[dict]:
    """Return the full conversion history, most-recent-first.

    Returns
    -------
    list[dict]
        Each dict is a serialised ``HistoryEntry``.
    """
    return [_entry_to_dict(e) for e in _history.load_history()]


def list_favorites() -> list[dict]:
    """Return only the entries marked as favorites, most-recent-first.

    Returns
    -------
    list[dict]
        Each dict is a serialised ``HistoryEntry`` with ``favorite=True``.
    """
    return [_entry_to_dict(e) for e in _history.list_favorites()]


def record_conversion(
    magnitude: str,
    value: float,
    from_unit: str,
    to_unit: str,
    result: float,
    *,
    from_order: str = "1",
    to_order: str = "1",
    sig_figs: "int | None" = None,
) -> dict:
    """Append a completed conversion to the history file.

    Parameters
    ----------
    magnitude:
        Magnitude name.
    value:
        Input value.
    from_unit, to_unit:
        Unit names.
    result:
        Converted output value.
    from_order, to_order:
        SI/IEC prefix keys (default ``"1"``).
    sig_figs:
        Significant figures used, or ``None``.

    Returns
    -------
    dict
        The newly-appended ``HistoryEntry`` as a dict.

    Raises
    ------
    ValueError
        If required string fields are empty.
    """
    if not magnitude or not magnitude.strip():
        raise ValueError("magnitude must be a non-empty string.")
    if not from_unit or not from_unit.strip():
        raise ValueError("from_unit must be a non-empty string.")
    if not to_unit or not to_unit.strip():
        raise ValueError("to_unit must be a non-empty string.")
    entry = _history.record(
        magnitude, value, from_unit, to_unit, result,
        from_order=from_order, to_order=to_order, sig_figs=sig_figs,
    )
    return _entry_to_dict(entry)


def add_favorite_by_timestamp(timestamp: str, label: str = "") -> None:
    """Mark an existing history entry (by timestamp) as a favorite.

    Parameters
    ----------
    timestamp:
        ISO-8601 UTC timestamp of the entry to mark (as stored in the history
        file).
    label:
        Optional human-readable label for the favorite.

    Raises
    ------
    ValueError
        If *timestamp* is empty or no matching entry is found.
    """
    if not timestamp or not timestamp.strip():
        raise ValueError("timestamp must be a non-empty string.")
    entries = _history.load_history()
    for entry in entries:
        if entry.timestamp == timestamp:
            _history.add_favorite(entry, label)
            return
    raise ValueError(f"No history entry with timestamp {timestamp!r}.")


def clear_history() -> dict:
    """Delete all conversion history entries.

    Returns
    -------
    dict
        ``{"cleared": true}``
    """
    _history.clear_history()
    return {"cleared": True}


# ---------------------------------------------------------------------------
# Custom unit operations
# ---------------------------------------------------------------------------


def add_custom_unit(magnitude: str, unit_name: str, factor: float) -> dict:
    """Persist a new custom unit to the user's custom units file.

    Validates *unit_name* for injection/path-traversal safety and confirms
    *factor* is a positive finite number before delegating to the core.

    Parameters
    ----------
    magnitude:
        Name of an existing magnitude (e.g. ``'Mass'``).
    unit_name:
        Name for the new unit.  Must not be empty, must not contain control
        characters, path separators, or TOML structural characters.
    factor:
        Conversion factor relative to the magnitude's base unit.  Must be
        a positive, finite, non-zero float.

    Returns
    -------
    dict
        ``{"magnitude": str, "unit_name": str, "factor": float}``

    Raises
    ------
    ValueError
        If *unit_name* is empty, unsafe, or *factor* is invalid.
    MagnitudeDataError (subclass of ValueError)
        If the factor is rejected by the core validator or the magnitude
        does not exist.
    """
    if not magnitude or not magnitude.strip():
        raise ValueError("magnitude must be a non-empty string.")
    _validate_unit_name(unit_name)
    _validate_factor(factor)
    _core_add_custom_unit(magnitude, unit_name, factor)
    return {"magnitude": magnitude, "unit_name": unit_name, "factor": factor}
