"""
unit_converter.gui.batch
=========================
Pure, Qt-free batch-conversion engine for SPEC-12.

This module contains **no PySide6 / Qt imports** so every function here is
testable without a running QApplication and independently of the GUI layer.
The GUI (``_BatchDialog`` in ``main_window.py``) drives these helpers;
they never call back into the GUI.

Public API
----------
``BatchRow``
    Frozen dataclass representing one result row.  Fields cover both batch
    modes (values-list and one-to-all-units):

    - ``index``       – row number within a values-list batch (None for
                        unit-table mode).
    - ``unit``        – target unit name (None for values-list mode).
    - ``input_value`` – the original input value as a string (exactly as
                        supplied — not parsed again here).
    - ``output_value``– conversion result ``float``, or ``None`` when an
                        error occurred.
    - ``output_text`` – formatted display string (from
                        :func:`unit_converter.gui.format_result.format_result`)
                        or the error message.
    - ``error``       – error description string, or ``None`` on success.

``batch_convert_values(convert_fn, magnitude, values, from_unit, to_unit,
                       from_order="1", to_order="1") -> list[BatchRow]``
    Convert a list of N numeric values, returning N ``BatchRow`` objects.
    One bad value does *not* abort the rest — the failing row carries the
    error string and ``output_value=None``.  Results must equal N individual
    ``convert_fn(magnitude, value, from_unit, to_unit, from_order, to_order)``
    calls.

``batch_convert_to_all_units(convert_fn, list_units_fn, magnitude, value,
                              from_unit) -> list[BatchRow]``
    Convert one value to every unit listed by ``list_units_fn(magnitude)``,
    returning one ``BatchRow`` per unit.  Each row's ``unit`` identifies the
    target.  Results equal individual ``convert_fn`` calls for each target
    unit.

``rows_to_csv(rows, headers) -> str``
    Serialize a list of ``BatchRow`` objects to a CSV string (``io.StringIO``
    + stdlib ``csv`` module, correctly quoting fields).  *headers* is the
    ordered list of column names; each name must match a ``BatchRow`` field.

Design decisions
----------------
*Qt-free.*
No PySide6 at module top-level.  The ``format_result`` import is also
Qt-free (it is a pure formatting helper).

*Injected dependencies.*
``convert_fn`` and ``list_units_fn`` are passed as callables so tests can
use the real core functions directly (no monkeypatching required) and so
the module is not hard-coupled to a specific import path.

*Per-row error isolation.*
A ``ValueError`` or any other exception in ``convert_fn`` for one value is
caught, stored in ``BatchRow.error``, and the loop continues to the next
value.  This guarantees the batch always returns N rows for N inputs.

*Formatting.*
Output text uses ``format_result(value, sweep_text)`` with ``sweep_text``
defaulting to ``"..."`` (auto cap) unless overridden by the caller.  The
caller (``_BatchDialog``) may pass the live sweep label's text so displayed
values match the main window's active precision.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import for format_result — avoids a circular import if this module is
# ever loaded before the GUI layer is fully initialized.  The helper itself is
# Qt-free; the lazy import is a belt-and-suspenders guard.
# ---------------------------------------------------------------------------

def _fmt(value: float, sweep_text: str = "...") -> str:
    from unit_converter.gui.format_result import format_result  # noqa: PLC0415
    return format_result(value, sweep_text)


# ---------------------------------------------------------------------------
# BatchRow dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BatchRow:
    """
    One result row in a batch operation.

    Fields
    ------
    index:
        Row number (0-based) within a values-list batch.  ``None`` in
        ``batch_convert_to_all_units`` mode.
    unit:
        Target unit name in ``batch_convert_to_all_units`` mode.  ``None``
        in values-list mode.
    input_value:
        Original input value as a string (the caller's repr; not re-parsed
        here).
    output_value:
        Conversion result as a ``float``, or ``None`` when ``error`` is set.
    output_text:
        Human-readable formatted result string (from ``format_result``) or
        the error message when ``error`` is not ``None``.
    error:
        Error description string, or ``None`` on success.
    """

    index: int | None
    unit: str | None
    input_value: str
    output_value: float | None
    output_text: str
    error: str | None


# ---------------------------------------------------------------------------
# batch_convert_values
# ---------------------------------------------------------------------------

def batch_convert_values(
    convert_fn: Callable[..., float],
    magnitude: str,
    values: list[Any],
    from_unit: str,
    to_unit: str,
    from_order: str = "1",
    to_order: str = "1",
    sweep_text: str = "...",
) -> list[BatchRow]:
    """
    Convert a list of numeric values between two units.

    Parameters
    ----------
    convert_fn:
        Callable with the signature
        ``convert(magnitude, value, from_unit, to_unit,
                  from_order, to_order) -> float``.
        Pass ``unit_converter.core.converter.convert`` for production use.
    magnitude:
        The magnitude name (e.g. ``"Length"``).
    values:
        Sequence of numeric values.  Each element should be a ``float`` or
        ``int``; non-numeric elements produce an error row.
    from_unit:
        Source unit name.
    to_unit:
        Target unit name.
    from_order:
        SI/IEC prefix for the source (default ``"1"`` = no prefix).
    to_order:
        SI/IEC prefix for the target (default ``"1"`` = no prefix).
    sweep_text:
        Sweep-label text to drive ``format_result`` precision (default
        ``"..."`` = auto 10-decimal cap).

    Returns
    -------
    list[BatchRow]
        Exactly ``len(values)`` rows.  Each row's ``output_value`` equals
        ``convert_fn(magnitude, v, from_unit, to_unit, from_order, to_order)``
        for valid *v*; rows for bad inputs carry ``error`` and
        ``output_value=None``.

    Notes
    -----
    Per-row exceptions are caught and stored; the loop always produces
    ``len(values)`` rows regardless of individual failures.
    """
    rows: list[BatchRow] = []
    for idx, raw in enumerate(values):
        input_str = str(raw)
        try:
            v = float(raw)
            result = convert_fn(
                magnitude, v, from_unit, to_unit,
                from_order=from_order, to_order=to_order,
            )
            text = _fmt(result, sweep_text)
            rows.append(BatchRow(
                index=idx,
                unit=None,
                input_value=input_str,
                output_value=result,
                output_text=text,
                error=None,
            ))
        except Exception as exc:
            err_msg = str(exc) or repr(exc)
            logger.error(
                "batch_convert_values: row %d value=%r: %s", idx, raw, err_msg
            )
            rows.append(BatchRow(
                index=idx,
                unit=None,
                input_value=input_str,
                output_value=None,
                output_text=err_msg,
                error=err_msg,
            ))
    return rows


# ---------------------------------------------------------------------------
# batch_convert_to_all_units
# ---------------------------------------------------------------------------

def batch_convert_to_all_units(
    convert_fn: Callable[..., float],
    list_units_fn: Callable[[str], dict],
    magnitude: str,
    value: float | int,
    from_unit: str,
    from_order: str = "1",
    sweep_text: str = "...",
) -> list[BatchRow]:
    """
    Convert one value to every unit of a magnitude.

    Parameters
    ----------
    convert_fn:
        Callable with the signature
        ``convert(magnitude, value, from_unit, to_unit,
                  from_order, to_order) -> float``.
    list_units_fn:
        Callable with the signature ``list_units(magnitude) -> dict``
        where the returned dict has a ``"units"`` key whose value is a
        list of unit name strings.  Pass
        ``unit_converter.core.converter.list_units`` for production use.
    magnitude:
        The magnitude name.
    value:
        The source value to convert.
    from_unit:
        The source unit name.
    from_order:
        SI/IEC prefix for the source (default ``"1"``).
    sweep_text:
        Sweep-label text to drive ``format_result`` precision (default
        ``"..."``).

    Returns
    -------
    list[BatchRow]
        One row per unit listed by ``list_units_fn(magnitude)``.  Each
        row's ``unit`` field holds the target unit name.  Rows equal
        individual ``convert_fn(magnitude, value, from_unit, unit)``
        calls.
    """
    info = list_units_fn(magnitude)
    unit_names: list[str] = info.get("units", [])

    rows: list[BatchRow] = []
    input_str = str(value)
    for unit_name in unit_names:
        try:
            result = convert_fn(
                magnitude, float(value), from_unit, unit_name,
                from_order=from_order, to_order="1",
            )
            text = _fmt(result, sweep_text)
            rows.append(BatchRow(
                index=None,
                unit=unit_name,
                input_value=input_str,
                output_value=result,
                output_text=text,
                error=None,
            ))
        except Exception as exc:
            err_msg = str(exc) or repr(exc)
            logger.error(
                "batch_convert_to_all_units: unit=%r: %s", unit_name, err_msg
            )
            rows.append(BatchRow(
                index=None,
                unit=unit_name,
                input_value=input_str,
                output_value=None,
                output_text=err_msg,
                error=err_msg,
            ))
    return rows


# ---------------------------------------------------------------------------
# rows_to_csv
# ---------------------------------------------------------------------------

def rows_to_csv(rows: list[BatchRow], headers: list[str]) -> str:
    """
    Serialize a list of ``BatchRow`` objects to a CSV string.

    Uses the stdlib ``csv`` module writing to ``io.StringIO`` so all fields
    are correctly quoted.  Only the columns named in *headers* are written;
    each name must be a valid ``BatchRow`` field (``index``, ``unit``,
    ``input_value``, ``output_value``, ``output_text``, ``error``).

    Parameters
    ----------
    rows:
        The list of ``BatchRow`` objects to serialize.
    headers:
        Ordered list of column names.  Each name must be a ``BatchRow``
        field.  Unknown names raise ``ValueError`` immediately so the
        caller gets a clear error.

    Returns
    -------
    str
        A UTF-8 CSV string with a header row followed by one data row per
        ``BatchRow``.  Line endings are ``\\r\\n`` (RFC 4180 / csv default).

    Raises
    ------
    ValueError
        If any name in *headers* is not a valid ``BatchRow`` field.

    Examples
    --------
    >>> row = BatchRow(index=0, unit=None, input_value="1", output_value=1.0,
    ...                output_text="1", error=None)
    >>> csv_text = rows_to_csv([row], ["index", "input_value", "output_text"])
    >>> csv_text.splitlines()[0]
    'index,input_value,output_text'
    """
    _VALID_FIELDS = {"index", "unit", "input_value", "output_value", "output_text", "error"}
    for h in headers:
        if h not in _VALID_FIELDS:
            raise ValueError(
                f"Unknown BatchRow field {h!r}. Valid fields: {sorted(_VALID_FIELDS)}"
            )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([getattr(row, h) for h in headers])
    return buf.getvalue()
