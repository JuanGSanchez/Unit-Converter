"""
unit_converter.gui.clipboard
=============================
Qt-free pure helpers for clipboard copy/paste integration (SPEC-15).

Design decisions
----------------
*Qt-free by design.*
Both helpers are pure functions that operate on plain Python types and do not
import PySide6.  This mirrors the ``format_result`` module's structure and
allows them to be unit-tested without a ``QApplication``.

*build_copy_expression.*
Produces a human-readable conversion expression of the form::

    "<from_value> <from_unit> = <to_value> <to_unit>"

The ``to_value`` string is the already-formatted display string (produced by
:func:`unit_converter.gui.format_result.format_result`), not a raw float, so
the clipboard text is identical to what the user sees in the result field.

*parse_pasted_number.*
Accepts strings that a QDoubleValidator would accept:
- Optional leading ``+`` / ``-`` sign.
- Integer or decimal form (``"3"``, ``"3.14"``, ``".5"``).
- Returns ``None`` for empty strings, non-numeric text, or anything that is
  not a finite float after parsing (``inf``, ``nan``).

This helper intentionally does not accept locale-specific separators
(e.g. comma-as-decimal) — that is deferred to SPEC-20.  It does strip
surrounding whitespace before parsing.

Public API
----------
``build_copy_expression(from_value, from_unit, to_value_str, to_unit) -> str``
    Build a human-readable clipboard expression string.

``parse_pasted_number(text: str) -> float | None``
    Parse a plain-text clipboard string to a float, returning ``None`` for
    garbage input.
"""

from __future__ import annotations

import math

__all__ = ["build_copy_expression", "parse_pasted_number"]


def build_copy_expression(
    from_value: str | float,
    from_unit: str,
    to_value_str: str,
    to_unit: str,
) -> str:
    """
    Build a human-readable clipboard expression string.

    Parameters
    ----------
    from_value:
        The source value as a string or float.  Floats are formatted with
        ``str()``; strings are used as-is (caller controls display format).
    from_unit:
        The source unit name (e.g. ``"kilometre (km)"``).
    to_value_str:
        The formatted result string as it appears in the result field
        (e.g. ``"0.621371"`` — produced by ``format_result``).
    to_unit:
        The target unit name (e.g. ``"mile (mi)"``).

    Returns
    -------
    str
        A string of the form ``"<from_value> <from_unit> = <to_value> <to_unit>"``.

    Examples
    --------
    >>> build_copy_expression("1", "kilometre (km)", "0.621371", "mile (mi)")
    '1 kilometre (km) = 0.621371 mile (mi)'
    >>> build_copy_expression(1.0, "metre (m)", "100", "centimetre (cm)")
    '1.0 metre (m) = 100 centimetre (cm)'
    """
    from_str = str(from_value) if not isinstance(from_value, str) else from_value
    return f"{from_str} {from_unit} = {to_value_str} {to_unit}"


def parse_pasted_number(text: str) -> float | None:
    """
    Parse a clipboard text string to a float, returning ``None`` for garbage.

    Accepts the same numeric forms as ``QDoubleValidator`` in standard-notation
    mode:
    - Optional leading ``+`` / ``-`` sign.
    - Integer (``"42"``, ``"-7"``) or decimal (``"3.14"``, ``".5"``, ``"1."``).
    - Leading/trailing whitespace is stripped.

    Returns ``None`` for:
    - Empty string (after stripping).
    - Non-numeric text (``"abc"``, ``"1,2,3"``, ``"12px"``).
    - Non-finite results (``"inf"``, ``"infinity"``, ``"nan"`` — case-insensitive).

    Parameters
    ----------
    text:
        The raw clipboard text.

    Returns
    -------
    float or None
        The parsed float, or ``None`` if *text* is not a valid finite number.

    Examples
    --------
    >>> parse_pasted_number("3.14")
    3.14
    >>> parse_pasted_number("  -42  ")
    -42.0
    >>> parse_pasted_number("+.5")
    0.5
    >>> parse_pasted_number("abc")
    >>> parse_pasted_number("")
    >>> parse_pasted_number("1,234")
    >>> parse_pasted_number("inf")
    >>> parse_pasted_number("nan")
    """
    stripped = text.strip()
    if not stripped:
        return None
    try:
        value = float(stripped)
    except (ValueError, TypeError):
        return None
    # Reject non-finite values (inf, -inf, nan)
    if not math.isfinite(value):
        return None
    return value
