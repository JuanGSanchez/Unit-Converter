"""
tests/test_expr.py
==================
Unit tests for unit_converter.core.expr (UC-I06).

Covers:
- parse_compound: happy paths, power, multi-token, dimension vectors
- convert_compound: km/h->m/s, error cases (dimension mismatch, unknown unit,
  syntax error)
- _tokenise: basic tokenisation
- ExpressionSyntaxError / UnknownUnitError / IncompatibleDimensionsError
"""
from __future__ import annotations

import pytest

from unit_converter.core.expr import (
    CompoundResult,
    ExpressionSyntaxError,
    IncompatibleDimensionsError,
    UnknownUnitError,
    _tokenise,
    convert_compound,
    parse_compound,
)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

class TestTokenise:
    def test_single_unit(self):
        tokens = _tokenise("m")
        assert tokens[0] == ("UNIT", "m")
        assert tokens[-1][0] == "EOF"

    def test_mul_operator(self):
        tokens = _tokenise("m*s")
        types = [t[0] for t in tokens[:-1]]
        assert types == ["UNIT", "MUL", "UNIT"]

    def test_div_operator(self):
        tokens = _tokenise("m/s")
        types = [t[0] for t in tokens[:-1]]
        assert types == ["UNIT", "DIV", "UNIT"]

    def test_pow_operator(self):
        tokens = _tokenise("m^2")
        types = [t[0] for t in tokens[:-1]]
        assert types == ["UNIT", "POW", "INT"]

    def test_whitespace_ignored(self):
        tokens = _tokenise("m / s")
        types = [t[0] for t in tokens[:-1]]
        assert types == ["UNIT", "DIV", "UNIT"]

    def test_invalid_char_raises(self):
        with pytest.raises(ExpressionSyntaxError):
            _tokenise("m!s")


# ---------------------------------------------------------------------------
# parse_compound
# ---------------------------------------------------------------------------

class TestParseCompound:
    def test_single_unit_length(self):
        r = parse_compound("m")
        assert r.factor == pytest.approx(1.0)
        assert r.dimensions == {"Length": 1}

    def test_km_factor_and_dimension(self):
        r = parse_compound("km")
        assert r.factor == pytest.approx(1000.0)
        assert r.dimensions == {"Length": 1}

    def test_m_squared(self):
        r = parse_compound("m^2")
        assert r.factor == pytest.approx(1.0)
        assert r.dimensions == {"Length": 2}

    def test_km_per_h(self):
        r = parse_compound("km/h")
        assert r.dimensions == {"Length": 1, "Time": -1}
        assert r.factor == pytest.approx(1000.0 / 3600.0)

    def test_m_per_s(self):
        r = parse_compound("m/s")
        assert r.dimensions == {"Length": 1, "Time": -1}
        assert r.factor == pytest.approx(1.0)

    def test_kg_times_m(self):
        r = parse_compound("kg*m")
        assert r.dimensions == {"Mass": 1, "Length": 1}

    def test_unit_str_preserved(self):
        r = parse_compound("km/h")
        assert r.unit_str == "km/h"

    def test_unknown_unit_raises(self):
        with pytest.raises(UnknownUnitError):
            parse_compound("foobar")

    def test_syntax_error_raises(self):
        with pytest.raises((ExpressionSyntaxError, UnknownUnitError)):
            parse_compound("m!!s")

    def test_compound_result_type(self):
        r = parse_compound("m")
        assert isinstance(r, CompoundResult)

    def test_custom_db_overrides(self):
        custom_db = {"myunit": (42.0, "Length")}
        r = parse_compound("myunit", db=custom_db)
        assert r.factor == pytest.approx(42.0)
        assert r.dimensions == {"Length": 1}


# ---------------------------------------------------------------------------
# convert_compound
# ---------------------------------------------------------------------------

class TestConvertCompound:
    def test_km_per_h_to_m_per_s(self):
        # 1 km/h = 1000/3600 m/s = 0.27778 m/s
        result = convert_compound(1.0, "km/h", "m/s")
        assert result == pytest.approx(1000.0 / 3600.0, rel=1e-5)

    def test_m_per_s_to_km_per_h(self):
        # 1 m/s = 3.6 km/h
        result = convert_compound(1.0, "m/s", "km/h")
        assert result == pytest.approx(3.6, rel=1e-5)

    def test_km_to_m(self):
        result = convert_compound(1.0, "km", "m")
        assert result == pytest.approx(1000.0, rel=1e-9)

    def test_m_to_km(self):
        result = convert_compound(1000.0, "m", "km")
        assert result == pytest.approx(1.0, rel=1e-9)

    def test_roundtrip_km_h_m_s(self):
        ms = convert_compound(3.6, "km/h", "m/s")
        kmh = convert_compound(ms, "m/s", "km/h")
        assert kmh == pytest.approx(3.6, rel=1e-9)

    def test_dimension_mismatch_raises(self):
        with pytest.raises(IncompatibleDimensionsError):
            convert_compound(1.0, "m", "s")

    def test_dimension_mismatch_length_vs_mass(self):
        with pytest.raises(IncompatibleDimensionsError):
            convert_compound(1.0, "km", "kg")

    def test_unknown_unit_in_from_raises(self):
        with pytest.raises(UnknownUnitError):
            convert_compound(1.0, "unknownunit", "m")

    def test_unknown_unit_in_to_raises(self):
        with pytest.raises(UnknownUnitError):
            convert_compound(1.0, "m", "unknownunit")

    def test_zero_value_converts_to_zero(self):
        result = convert_compound(0.0, "km/h", "m/s")
        assert result == 0.0

    def test_power_expression_m2(self):
        # 1 m^2 = 1 m^2 (identity)
        result = convert_compound(1.0, "m^2", "m^2")
        assert result == pytest.approx(1.0)

    def test_kg_per_s_to_g_per_min(self):
        # 1 kg/s = 1000 g/s = 60000 g/min
        result = convert_compound(1.0, "kg/s", "g/min")
        assert result == pytest.approx(60000.0, rel=1e-6)
