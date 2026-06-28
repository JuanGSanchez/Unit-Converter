"""
unit_converter.core.expr
=========================
Limited compound/derived unit parser (UC-I06).

Scope
-----
Parses simple compound unit expressions of the form::

    "km/h"    - quotient
    "m^2"     - power (positive integer exponent)
    "kg*m/s^2" - combined product/quotient/power

No general arithmetic, parentheses, or free-form expressions (those are
deferred - see BACKLOG Deferred section).  Only multiplication ``*``,
division ``/``, and positive-integer powers ``^``.

The parsed result is a ``CompoundResult``:

- ``factor``     - combined conversion factor relative to SI base units
- ``dimensions`` - dimension vector ``{"Length": 1, "Mass": 1, ...}`` so the
                   caller can detect dimensional mismatches (UC-I02 guard)

Public API
----------
parse_compound(expr, db=None) -> CompoundResult
    Parse a compound unit expression.  ``db`` may be a custom
    ``dict[unit_name, (factor, magnitude)]`` for testing/extension.

convert_compound(value, from_expr, to_expr, db=None) -> float
    Convert *value* from *from_expr* to *to_expr*; raises
    ``IncompatibleDimensionsError`` if the dimension vectors do not match.

Invariants
----------
- No GUI imports.
- Does not depend on the converter module (avoids circular imports).
- All existing single-unit conversions are unaffected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class UnknownUnitError(ValueError):
    """Raised when an atom in the compound expression is not in the unit table."""


class IncompatibleDimensionsError(ValueError):
    """Raised when from/to dimension vectors do not match."""


class ExpressionSyntaxError(ValueError):
    """Raised when the expression cannot be tokenised/parsed."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CompoundResult:
    """
    Result of parsing a compound unit expression.

    Attributes
    ----------
    factor:
        Combined conversion factor to SI base units.
    dimensions:
        Dimension vector, e.g. ``{"Length": 1, "Time": -1}`` for m/s.
    unit_str:
        Original expression string (for display).
    """
    factor: float
    dimensions: dict = field(default_factory=dict)
    unit_str: str = ""


# ---------------------------------------------------------------------------
# Built-in unit table: unit_name -> (factor_relative_to_SI_base, magnitude)
# ---------------------------------------------------------------------------

# SI base-unit factors and magnitude tags for dimension tracking.
_BUILTIN_UNIT_TABLE: dict[str, tuple] = {
    # Length (base: meter)
    "m": (1.0, "Length"),
    "km": (1000.0, "Length"),
    "in": (0.0254, "Length"),
    "yd": (0.9144, "Length"),
    "mi": (1609.34, "Length"),
    "cm": (0.01, "Length"),
    "mm": (0.001, "Length"),
    # Mass (base: gram, matching converter base unit)
    "g": (1.0, "Mass"),
    "kg": (1000.0, "Mass"),
    "lb": (453.6, "Mass"),
    "oz": (28.35, "Mass"),
    # Time (base: second)
    "s": (1.0, "Time"),
    "min": (60.0, "Time"),
    "hr": (3600.0, "Time"),
    "h": (3600.0, "Time"),
    "d": (86400.0, "Time"),
    # Energy (base: joule)
    "J": (1.0, "Energy"),
    "kJ": (1000.0, "Energy"),
    "cal": (4.184, "Energy"),
    "Wh": (3600.0, "Energy"),
    # Power (base: watt)
    "W": (1.0, "Power"),
    "kW": (1000.0, "Power"),
    "HP": (745.7, "Power"),
    # Pressure (base: pascal)
    "Pa": (1.0, "Pressure"),
    "kPa": (1000.0, "Pressure"),
    "bar": (100000.0, "Pressure"),
    "atm": (101325.0, "Pressure"),
    # Newton (derived: kg*m/s^2) - for N*m -> J convenience
    "N": (1000.0 * 1.0 / 1.0, "Force"),   # 1 N = 1000g * m / s^2 ... use composite
    # Volume (base: m^3 via Length^3)
    "l": (0.001, "Volume"),
    "L": (0.001, "Volume"),
}

# Dimension vectors for each magnitude
_MAGNITUDE_DIMENSIONS: dict[str, dict] = {
    "Length":      {"Length": 1},
    "Mass":        {"Mass": 1},
    "Time":        {"Time": 1},
    "Energy":      {"Energy": 1},
    "Power":       {"Power": 1},
    "Pressure":    {"Pressure": 1},
    "Area":        {"Length": 2},
    "Volume":      {"Length": 3},
    "Data":        {"Data": 1},
    "Force":       {"Mass": 1, "Length": 1, "Time": -2},
}


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_T_UNIT = "UNIT"
_T_MUL  = "MUL"
_T_DIV  = "DIV"
_T_POW  = "POW"
_T_INT  = "INT"
_T_EOF  = "EOF"

_TOKEN_RE = re.compile(
    r"(?P<UNIT>[A-Za-z][A-Za-z0-9]*)"
    r"|(?P<MUL>\*)"
    r"|(?P<DIV>/)"
    r"|(?P<POW>\^)"
    r"|(?P<INT>[0-9]+)"
    r"|(?P<SPACE>\s+)"
)


def _tokenise(expr: str) -> list:
    """Tokenise *expr* into a list of ``(type, value)`` pairs."""
    tokens = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if m is None:
            raise ExpressionSyntaxError(
                "Unrecognised character {!r} at position {} in {!r}.".format(
                    expr[pos], pos, expr
                )
            )
        kind = m.lastgroup
        if kind != "SPACE":
            tokens.append((kind, m.group()))
        pos = m.end()
    tokens.append((_T_EOF, ""))
    return tokens


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _lookup_unit(
    name: str,
    db: Optional[dict],
) -> tuple:
    """
    Look up *name* in *db* (preferred) then in the built-in table.

    Returns ``(factor, magnitude)``.
    Raises ``UnknownUnitError`` if not found.
    """
    # Fast path: no custom db — avoid copying the built-in table entirely.
    if not db:
        if name in _BUILTIN_UNIT_TABLE:
            return _BUILTIN_UNIT_TABLE[name]
        raise UnknownUnitError(
            "Unknown unit {!r} in compound expression.  "
            "Available: {}".format(name, sorted(_BUILTIN_UNIT_TABLE.keys()))
        )
    # Custom db present: check it first (takes precedence), then fall back.
    if name in db:
        return db[name]
    if name in _BUILTIN_UNIT_TABLE:
        return _BUILTIN_UNIT_TABLE[name]
    combined_keys = sorted(set(_BUILTIN_UNIT_TABLE.keys()) | set(db.keys()))
    raise UnknownUnitError(
        "Unknown unit {!r} in compound expression.  "
        "Available: {}".format(name, combined_keys)
    )


def _dim_vector(magnitude: str) -> dict:
    """Return the base dimension vector for *magnitude*.

    Returns the canonical dict directly when the magnitude is known (callers
    only iterate it — they never mutate the returned value).  For unknown
    magnitudes, the inline default ``{magnitude: 1}`` is already a fresh dict.
    """
    return _MAGNITUDE_DIMENSIONS.get(magnitude, {magnitude: 1})


def _merge_dims(base: dict, other: dict, sign: int) -> dict:
    """Merge dimension vectors: base * other^sign."""
    result = dict(base)
    for k, v in other.items():
        result[k] = result.get(k, 0) + sign * v
    return {k: v for k, v in result.items() if v != 0}


# ---------------------------------------------------------------------------
# Recursive descent parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: list, db: Optional[dict]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._db = db

    def _peek(self) -> tuple:
        return self._tokens[self._pos]

    def _consume(self, expected_type: Optional[str] = None) -> tuple:
        tok = self._tokens[self._pos]
        if expected_type and tok[0] != expected_type:
            raise ExpressionSyntaxError(
                "Expected {!r} but got {!r}.".format(expected_type, tok)
            )
        self._pos += 1
        return tok

    def parse(self) -> CompoundResult:
        factor, dims = self._parse_expr()
        if self._peek()[0] != _T_EOF:
            raise ExpressionSyntaxError(
                "Unexpected token {!r} after expression end.".format(self._peek())
            )
        return CompoundResult(factor=factor, dimensions=dims)

    def _parse_expr(self) -> tuple:
        factor, dims = self._parse_atom()
        while self._peek()[0] in (_T_MUL, _T_DIV):
            op = self._consume()[1]
            f2, d2 = self._parse_atom()
            if op == "*":
                factor *= f2
                dims = _merge_dims(dims, d2, +1)
            else:
                factor /= f2
                dims = _merge_dims(dims, d2, -1)
        return factor, dims

    def _parse_atom(self) -> tuple:
        kind, val = self._peek()
        if kind != _T_UNIT:
            raise ExpressionSyntaxError(
                "Expected a unit name, got {!r} ({!r}).".format(kind, val)
            )
        self._consume(_T_UNIT)
        unit_factor, magnitude = _lookup_unit(val, self._db)
        base_dims = _dim_vector(magnitude)

        exp = 1
        if self._peek()[0] == _T_POW:
            self._consume(_T_POW)
            _, int_str = self._consume(_T_INT)
            exp = int(int_str)

        combined_factor = unit_factor ** exp
        combined_dims = {k: v * exp for k, v in base_dims.items()}

        return combined_factor, combined_dims


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_compound(
    expr: str,
    db: Optional[dict] = None,
) -> CompoundResult:
    """
    Parse a compound unit expression.

    Parameters
    ----------
    expr:
        A compound unit expression, e.g. ``"km/h"``, ``"m^2"``, ``"kg*m/s^2"``.
    db:
        Optional custom unit table ``{unit_name: (factor, magnitude)}``.
        Merged with the built-in table (custom entries take precedence).

    Returns
    -------
    CompoundResult
        ``.factor`` - combined factor relative to SI base units.
        ``.dimensions`` - dimension vector.
        ``.unit_str`` - original expression.

    Raises
    ------
    UnknownUnitError
        If any atom is not in the unit table.
    ExpressionSyntaxError
        If the expression cannot be parsed.
    """
    tokens = _tokenise(expr.strip())
    result = _Parser(tokens, db).parse()
    result.unit_str = expr.strip()
    return result


def convert_compound(
    value: float,
    from_expr: str,
    to_expr: str,
    db: Optional[dict] = None,
) -> float:
    """
    Convert *value* from *from_expr* to *to_expr*.

    Raises ``IncompatibleDimensionsError`` if the dimension vectors differ.

    Parameters
    ----------
    value:
        Numeric value to convert.
    from_expr:
        Source compound unit expression (e.g. ``"km/h"``).
    to_expr:
        Target compound unit expression (e.g. ``"m/s"``).
    db:
        Optional custom unit table.

    Returns
    -------
    float
        Converted value.

    Raises
    ------
    IncompatibleDimensionsError
        If ``from_expr`` and ``to_expr`` have different dimension vectors.
    UnknownUnitError / ExpressionSyntaxError
        On invalid unit names or malformed expressions.

    Examples
    --------
    >>> round(convert_compound(1.0, "km/h", "m/s"), 6)
    0.277778
    """
    from_result = parse_compound(from_expr, db)
    to_result = parse_compound(to_expr, db)

    if from_result.dimensions != to_result.dimensions:
        raise IncompatibleDimensionsError(
            "Dimension mismatch: {!r} has dimensions {} but {!r} has "
            "dimensions {}.".format(
                from_expr, from_result.dimensions,
                to_expr, to_result.dimensions,
            )
        )

    if to_result.factor == 0.0:
        raise ValueError(
            "Target expression {!r} has a zero combined factor.".format(to_expr)
        )

    return value * from_result.factor / to_result.factor
