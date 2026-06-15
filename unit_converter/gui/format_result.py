"""
unit_converter.gui.format_result
=================================
Qt-free helper for formatting conversion-result floats for display in the
main-window entry fields.

Design decisions
----------------
*Rounding, not truncation.*
The task spec says "truncated (drop digits beyond the cap)" but notes to
pick the most correct consistent behaviour.  Python's ``f"{v:.Nf}"`` rounds
to N places (banker's-rounding via IEEE 754), which is numerically more
correct than truncation: a result of ``1.9999999999999`` capped at 10 with
truncation would show ``1.9999999999`` while rounded it correctly shows
``2.0``.  The existing nudge logic in ``_NumEntry._nudge`` also uses
``round()``.  Rounding is chosen as the consistent behaviour; this is noted
in the acceptance checklist.

*Trailing-zero stripping.*
``f"{1.5:.10f}"`` → ``"1.5000000000"``; after stripping → ``"1.5"``.
Integers are likewise returned without a decimal point (``"5"`` not
``"5.0"``).

*Sweep semantics.*
The ``_SweepLabel`` stores:
- ``"..."``  → auto-detect (treat as cap = *cap* default)
- ``"0"``    → integer nudge position (no decimal places → cap default)
- ``"-N"``   → N decimal places deep  (N = abs(int(text)))
- ``"+N"``   → integer tens/hundreds position (no decimal → cap default)

The display cap is ``max(cap, decimal_depth)`` where ``decimal_depth`` is
the absolute value of a negative sweep value, or 0 otherwise.

*Precision preservation.*
This helper only formats for display.  The caller (``_unit_converter``)
already stores the full-precision ``result`` in ``self._val2`` /
``self._val1`` before calling this.  ``textEdited`` signals fire only on
user input, not on ``setText``, so the displayed truncated text is never
silently fed back into a conversion unless the user explicitly edits it.
"""

from __future__ import annotations

__all__ = ["format_result", "display_decimal_places"]

_DEFAULT_CAP = 10


def display_decimal_places(sweep_text: str, cap: int = _DEFAULT_CAP) -> int:
    """
    Return the number of decimal places to display, given the sweep label text.

    Parameters
    ----------
    sweep_text:
        The current text of the ``_SweepLabel`` widget (``"..."``, ``"0"``,
        ``"-N"``, or ``"+N"``).
    cap:
        Default maximum decimal places (default 10).

    Returns
    -------
    int
        ``max(cap, depth)`` where *depth* is the absolute value of
        *sweep_text* when it is a negative integer string, otherwise 0.

    Examples
    --------
    >>> display_decimal_places("...")
    10
    >>> display_decimal_places("0")
    10
    >>> display_decimal_places("-5")
    10
    >>> display_decimal_places("-11")
    11
    >>> display_decimal_places("-15", cap=10)
    15
    >>> display_decimal_places("2")   # positive → integer position
    10
    """
    try:
        val = int(sweep_text)
    except (ValueError, TypeError):
        # "..." or anything unparseable → use the cap
        return cap

    if val < 0:
        depth = -val  # e.g. "-11" → depth=11
    else:
        depth = 0     # "0", positive → integer position, no deeper

    return max(cap, depth)


def format_result(
    value: float,
    sweep_text: str,
    cap: int = _DEFAULT_CAP,
) -> str:
    """
    Format *value* for display in a result entry field.

    Parameters
    ----------
    value:
        The full-precision conversion result from core.
    sweep_text:
        Current text of the ``_SweepLabel`` associated with the entry field
        that will receive the result (``"..."``, ``"0"``, ``"-N"``, ``"+N"``).
    cap:
        Default maximum decimal places (default 10).  Override only in tests
        or if the UI default changes.

    Returns
    -------
    str
        Formatted string with at most ``max(cap, sweep_depth)`` decimal
        places and trailing zeros stripped.  Exact integers have no decimal
        point (``"5"`` not ``"5.0"``).

    Notes
    -----
    - Uses rounding (``:.Nf`` format), not truncation, for numerical
      correctness; see module docstring for rationale.
    - Very large or very small values are handled: Python's ``:.Nf`` produces
      a full decimal string (no scientific notation) so the result field
      stays consistent with user input.  The ``_lab_val1``/``_lab_val2``
      scientific-notation labels cover the magnitude view.
    - Does NOT handle ``NaN`` or ``inf`` — the caller clamps those before
      conversion via ``_clamp_input`` in core.

    Examples
    --------
    >>> format_result(1.123456789012345, "...")
    '1.1234567890'
    >>> format_result(1.123456789012345, "-11")
    '1.12345678901'
    >>> format_result(5.0, "...")
    '5'
    >>> format_result(1.5, "...")
    '1.5'
    >>> format_result(0.0, "...")
    '0'
    """
    places = display_decimal_places(sweep_text, cap=cap)
    formatted = f"{value:.{places}f}"
    # Strip trailing zeros after the decimal point, then a bare decimal point.
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted
