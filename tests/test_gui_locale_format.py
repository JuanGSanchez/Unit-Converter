"""
Tests for SPEC-20 locale-aware number parsing/formatting
(:mod:`unit_converter.gui.locale_format`).

These are Qt-free: the module is pure Python.  The headline acceptance
criterion — "``1.234,56`` (comma-decimal) and ``1,234.56`` (point-decimal)
parse to the same value under the matching locale" — is locked by
:func:`test_swapped_separators_parse_equal`.
"""

from __future__ import annotations

import math

import pytest

from unit_converter.gui.locale_format import (
    DE_DE,
    EN_US,
    LOCALES,
    LocaleSpec,
    format_number,
    parse_number,
    system_locale_spec,
)


# ---------------------------------------------------------------------------
# parse_number
# ---------------------------------------------------------------------------

def test_swapped_separators_parse_equal():
    """SPEC-20: the two locale forms of 1234.56 parse to the same value."""
    en = parse_number("1,234.56", EN_US)
    de = parse_number("1.234,56", DE_DE)
    assert en == de == pytest.approx(1234.56)


@pytest.mark.parametrize(
    "text,spec,expected",
    [
        ("1234.56", EN_US, 1234.56),
        ("1,234.56", EN_US, 1234.56),
        ("1,234,567.89", EN_US, 1234567.89),
        ("0.5", EN_US, 0.5),
        ("-42", EN_US, -42.0),
        ("+3.5", EN_US, 3.5),
        ("1234,56", DE_DE, 1234.56),
        ("1.234,56", DE_DE, 1234.56),
        ("1.234.567,89", DE_DE, 1234567.89),
        ("0,5", DE_DE, 0.5),
        ("-42", DE_DE, -42.0),
    ],
)
def test_parse_valid(text, spec, expected):
    assert parse_number(text, spec) == pytest.approx(expected)


@pytest.mark.parametrize(
    "text,spec",
    [
        ("", EN_US),
        ("   ", EN_US),
        ("abc", EN_US),
        ("1,2,3.4.5", EN_US),
        ("1,2,3", DE_DE),      # multiple decimal commas → not a number
        ("inf", EN_US),
        ("nan", EN_US),
        ("1e999", EN_US),      # overflow → inf → rejected
        (None, EN_US),
    ],
)
def test_parse_garbage_returns_none(text, spec):
    assert parse_number(text, spec) is None


# ---------------------------------------------------------------------------
# format_number
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,places,spec,expected",
    [
        (1234.56, 2, EN_US, "1,234.56"),
        (1234.56, 2, DE_DE, "1.234,56"),
        (1234567.89, 2, EN_US, "1,234,567.89"),
        (1234567.89, 2, DE_DE, "1.234.567,89"),
        (1234.0, 2, DE_DE, "1.234"),          # trailing zeros stripped
        (5.0, 4, EN_US, "5"),                  # exact int, no decimal point
        (1.5, 4, EN_US, "1.5"),
        (-1234.5, 2, DE_DE, "-1.234,5"),       # sign + grouping + comma decimal
        (0.0, 2, EN_US, "0"),
    ],
)
def test_format_valid(value, places, spec, expected):
    assert format_number(value, places, spec) == expected


def test_format_no_grouping():
    assert format_number(1234.56, 2, EN_US, grouping=False) == "1234.56"
    assert format_number(1234.56, 2, DE_DE, grouping=False) == "1234,56"


def test_format_keep_trailing_zeros():
    assert format_number(1.5, 3, EN_US, strip_trailing_zeros=False) == "1.500"


def test_format_non_finite_safe():
    assert format_number(math.inf, 2, EN_US) == "inf"
    assert format_number(math.nan, 2, EN_US) == "nan"


def test_format_negative_places_rejected():
    with pytest.raises(ValueError):
        format_number(1.0, -1, EN_US)


# ---------------------------------------------------------------------------
# round-trip parse <-> format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", [EN_US, DE_DE])
@pytest.mark.parametrize("value", [0.0, 1.5, 1234.56, 1234567.89, -42.25])
def test_round_trip(spec, value):
    text = format_number(value, 6, spec)
    assert parse_number(text, spec) == pytest.approx(value)


# ---------------------------------------------------------------------------
# LocaleSpec validation + registry + system helper
# ---------------------------------------------------------------------------

def test_localespec_rejects_bad_decimal():
    with pytest.raises(ValueError):
        LocaleSpec(name="bad", decimal="x", thousands=",")


def test_localespec_rejects_equal_separators():
    with pytest.raises(ValueError):
        LocaleSpec(name="bad", decimal=".", thousands=".")


def test_locales_registry():
    assert LOCALES["en_US"] is EN_US
    assert LOCALES["de_DE"] is DE_DE


def test_system_locale_spec_returns_spec():
    spec = system_locale_spec()
    assert isinstance(spec, LocaleSpec)
    assert spec.decimal in (".", ",")
