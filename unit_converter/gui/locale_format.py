"""
unit_converter.gui.locale_format
=================================
Qt-free, locale-aware number parsing and formatting (SPEC-20).

Decimal and thousands separators differ by locale: English uses a point for
the decimal and a comma for grouping ("1,234.56"); many European locales swap
them ("1.234,56").  The conversion core always works with canonical Python
floats (a point decimal, no grouping); this module is the presentation/parse
boundary that converts between a locale's textual form and that canonical
float.

Design
------
* **Pure & deterministic.**  A :class:`LocaleSpec` carries the two separators
  explicitly, so parsing/formatting are reproducible and unit-testable without
  touching the process-global :mod:`locale` state (which is fragile and not
  thread-safe).  System-locale derivation is offered as an *optional* helper
  (:func:`system_locale_spec`) layered on top — the pure functions never
  depend on it.
* **Coordinated with SPEC-13 formatting.**  :func:`format_number` takes a
  decimal-places count just like :func:`unit_converter.gui.format_result`; it
  only swaps in the locale separators and optional digit grouping.  Raw
  full-precision values are never rounded upstream (SPEC-16).
* **Graceful edge handling (SPEC-17).**  :func:`parse_number` returns ``None``
  for empty / non-numeric / ambiguous input rather than raising, so callers
  reject garbage without a crash.

Two named locales are provided (:data:`EN_US`, :data:`DE_DE`) so the
round-trip "``1.234,56`` (comma-decimal) and ``1,234.56`` (point-decimal)
parse to the same value under the matching locale" is directly testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "LocaleSpec",
    "EN_US",
    "DE_DE",
    "LOCALES",
    "parse_number",
    "format_number",
    "system_locale_spec",
]


@dataclass(frozen=True)
class LocaleSpec:
    """
    A minimal numeric-locale description.

    Parameters
    ----------
    name:
        Stable identifier (e.g. ``"en_US"``).
    decimal:
        The decimal separator character (``"."`` or ``","``).
    thousands:
        The digit-grouping separator character (``","``, ``"."``, ``" "`` …)
        or an empty string for no grouping.
    """

    name: str
    decimal: str
    thousands: str

    def __post_init__(self) -> None:
        if self.decimal not in (".", ","):
            raise ValueError(f"decimal separator must be '.' or ',', got {self.decimal!r}")
        if self.thousands == self.decimal:
            raise ValueError("thousands separator must differ from the decimal separator")


# Two reference locales covering the swapped-separator cases.
EN_US = LocaleSpec(name="en_US", decimal=".", thousands=",")
DE_DE = LocaleSpec(name="de_DE", decimal=",", thousands=".")

LOCALES: dict[str, LocaleSpec] = {EN_US.name: EN_US, DE_DE.name: DE_DE}


def parse_number(text: str, spec: LocaleSpec = EN_US) -> "float | None":
    """
    Parse a locale-formatted numeric string into a canonical float.

    Strips the locale's grouping separator and normalises its decimal
    separator to a point, then parses with :class:`float`.  Returns ``None``
    for empty, non-numeric, or structurally invalid input (SPEC-17) and for
    non-finite results (``inf`` / ``nan``).

    Parameters
    ----------
    text:
        The user-entered string in *spec*'s conventions (e.g. ``"1.234,56"``
        under :data:`DE_DE`).
    spec:
        The active locale.  Defaults to :data:`EN_US`.

    Returns
    -------
    float | None
        The canonical value, or ``None`` if *text* cannot be parsed.

    Examples
    --------
    >>> parse_number("1,234.56", EN_US)
    1234.56
    >>> parse_number("1.234,56", DE_DE)
    1234.56
    >>> parse_number("abc", EN_US) is None
    True
    """
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None

    # Remove grouping separators, then normalise the decimal to a point.
    if spec.thousands:
        raw = raw.replace(spec.thousands, "")
    if spec.decimal != ".":
        # Reject a stray point (would be ambiguous once the decimal is a comma).
        if "." in raw:
            return None
        raw = raw.replace(spec.decimal, ".")

    try:
        value = float(raw)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value):
        return None
    return value


def format_number(
    value: float,
    places: int,
    spec: LocaleSpec = EN_US,
    *,
    grouping: bool = True,
    strip_trailing_zeros: bool = True,
) -> str:
    """
    Format *value* with *places* decimals using *spec*'s separators.

    Parameters
    ----------
    value:
        The canonical full-precision float to render.
    places:
        Number of decimal places (rounded, IEEE-754, consistent with
        :func:`unit_converter.gui.format_result.format_result`).
    spec:
        The active locale.  Defaults to :data:`EN_US`.
    grouping:
        When ``True`` (default), insert *spec*'s grouping separator every three
        integer digits.
    strip_trailing_zeros:
        When ``True`` (default), drop trailing fractional zeros (and a bare
        decimal separator), so ``1.50`` → ``"1.5"`` and ``5.0`` → ``"5"``.

    Returns
    -------
    str
        The locale-formatted number.

    Examples
    --------
    >>> format_number(1234.56, 2, EN_US)
    '1,234.56'
    >>> format_number(1234.56, 2, DE_DE)
    '1.234,56'
    >>> format_number(1234.0, 2, DE_DE)
    '1.234'
    >>> format_number(1234.56, 2, EN_US, grouping=False)
    '1234.56'
    """
    if places < 0:
        raise ValueError(f"places must be non-negative, got {places}")
    if not math.isfinite(value):
        # inf / nan rendered safely (SPEC-17) without separators.
        return str(value)

    sign = "-" if value < 0 else ""
    text = f"{abs(value):.{places}f}"
    if "." in text:
        int_part, frac_part = text.split(".", 1)
    else:
        int_part, frac_part = text, ""

    if grouping and spec.thousands:
        int_part = _group_digits(int_part, spec.thousands)

    if strip_trailing_zeros:
        frac_part = frac_part.rstrip("0")

    if frac_part:
        return f"{sign}{int_part}{spec.decimal}{frac_part}"
    return f"{sign}{int_part}"


def _group_digits(int_digits: str, sep: str) -> str:
    """Insert *sep* every three digits from the right of *int_digits*."""
    n = len(int_digits)
    if n <= 3:
        return int_digits
    head = n % 3
    chunks = []
    if head:
        chunks.append(int_digits[:head])
    for i in range(head, n, 3):
        chunks.append(int_digits[i : i + 3])
    return sep.join(chunks)


def system_locale_spec(default: LocaleSpec = EN_US) -> LocaleSpec:
    """
    Best-effort derivation of a :class:`LocaleSpec` from the system locale.

    Uses :func:`locale.localeconv` without permanently mutating global locale
    state.  Falls back to *default* if the platform reports no usable
    separators.  This is the only function that touches process-global locale
    machinery; the pure parse/format functions above never call it.

    Parameters
    ----------
    default:
        Locale to return when system separators are unavailable.

    Returns
    -------
    LocaleSpec
        A locale spec derived from the environment, or *default*.
    """
    import locale as _locale

    try:
        conv = _locale.localeconv()
    except Exception:  # pragma: no cover - platform dependent
        return default
    dec = conv.get("decimal_point") or default.decimal
    thou = conv.get("thousands_sep") or ""
    if dec not in (".", ","):
        return default
    if thou == dec:
        thou = ""
    try:
        return LocaleSpec(name="system", decimal=dec, thousands=thou)
    except ValueError:  # pragma: no cover - defensive
        return default
