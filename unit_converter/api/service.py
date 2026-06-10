"""
unit_converter.api.service
===========================
Single shared service layer.

**Both** the REST app (``rest.py``) and the MCP server (``mcp_server.py``)
call this module.  No conversion logic is duplicated here — every operation
is a thin, typed wrapper over ``unit_converter.core.converter``.

Error contract
--------------
``ValueError`` raised by the core is re-raised unchanged.  Callers
(REST layer: FastAPI ``HTTPException``; MCP layer: FastMCP tool error) are
responsible for mapping it to their transport's error format.
"""
from __future__ import annotations

from unit_converter.core.converter import (
    convert as _core_convert,
    list_magnitudes as _core_list_magnitudes,
    list_units as _core_list_units,
)


# ---------------------------------------------------------------------------
# Response models (plain dicts — intentionally dependency-free so the service
# module can be imported without fastapi on the path).
# ---------------------------------------------------------------------------


def list_magnitudes() -> list[str]:
    """Return the sorted list of available magnitude names.

    Returns
    -------
    list[str]
        Sorted magnitude names, e.g. ``['Area', 'Data', 'Energy', ...]``.
    """
    return _core_list_magnitudes()


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

    Returns
    -------
    float
        The converted value.

    Raises
    ------
    ValueError
        On unknown magnitude, unit, or order key.
    """
    return _core_convert(magnitude, value, from_unit, to_unit, from_order, to_order)
