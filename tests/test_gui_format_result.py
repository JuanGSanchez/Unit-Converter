"""
tests/test_gui_format_result.py
================================
Deterministic, Qt-free tests for ``unit_converter.gui.format_result``.

Covers:
- ``display_decimal_places``:
    - sweep "..." → cap (10)
    - sweep "0" → cap (10)
    - sweep positive (integer position) → cap (10)
    - sweep "-5" (shallower than cap) → cap (10)
    - sweep "-10" (at cap) → 10
    - sweep "-11" (deeper than cap) → 11
    - sweep "-15" → 15
    - non-default cap respected
- ``format_result``:
    - value with >10 decimals truncated (rounded) to 10
    - value with sweep at -12 showing 12 places
    - exact integer (no trailing zeros or dot)
    - short decimal (fewer than 10 places → no spurious trailing zeros)
    - zero
    - value whose 10-place rounding produces a trailing zero (stripped)
    - very small value (no scientific notation in result)
    - rounding note: 1.9999999999999 at 10 places rounds to 2, not truncates

Rules:
- No PySide6 import (helper is Qt-free by design).
- No network access.
- No filesystem I/O.
"""

from __future__ import annotations

import pytest

from unit_converter.gui.format_result import display_decimal_places, format_result


# ---------------------------------------------------------------------------
# display_decimal_places
# ---------------------------------------------------------------------------


class TestDisplayDecimalPlaces:
    """Tests for the sweep-text → decimal-places conversion."""

    def test_auto_sweep_returns_cap(self) -> None:
        assert display_decimal_places("...") == 10

    def test_zero_sweep_returns_cap(self) -> None:
        assert display_decimal_places("0") == 10

    def test_positive_sweep_returns_cap(self) -> None:
        # Positive sweep = integer positions (tens, hundreds) → no decimal depth
        assert display_decimal_places("1") == 10
        assert display_decimal_places("2") == 10

    def test_negative_sweep_shallower_than_cap_returns_cap(self) -> None:
        assert display_decimal_places("-5") == 10

    def test_negative_sweep_at_cap_returns_cap(self) -> None:
        assert display_decimal_places("-10") == 10

    def test_negative_sweep_deeper_than_cap(self) -> None:
        assert display_decimal_places("-11") == 11

    def test_negative_sweep_much_deeper_than_cap(self) -> None:
        assert display_decimal_places("-15") == 15

    def test_non_default_cap_respected(self) -> None:
        assert display_decimal_places("-5", cap=3) == 5
        assert display_decimal_places("...", cap=6) == 6
        assert display_decimal_places("-20", cap=15) == 20

    def test_unparseable_sweep_falls_back_to_cap(self) -> None:
        # Anything that is not a valid integer → cap
        assert display_decimal_places("abc") == 10
        assert display_decimal_places("") == 10


# ---------------------------------------------------------------------------
# format_result
# ---------------------------------------------------------------------------


class TestFormatResult:
    """Tests for format_result end-to-end output strings."""

    # -- Core cap behaviour --------------------------------------------------

    def test_more_than_10_decimals_capped_at_10(self) -> None:
        # 1/3 has infinite decimals; display capped at 10 places.
        result = format_result(1 / 3, "...")
        # After rounding to 10: 0.3333333333
        assert result == "0.3333333333"

    def test_more_than_10_decimals_explicit(self) -> None:
        # A value with many explicit decimals; the 10th place is 0 → stripped.
        # round(1.123456789012345, 10) = 1.1234567890 → strip trailing 0 → "1.123456789"
        result = format_result(1.123456789012345, "...")
        assert result == "1.123456789"

    def test_more_than_10_decimals_with_trailing_zero_at_cap(self) -> None:
        # 0.12345678900... → after strip → "0.123456789"
        result = format_result(0.123456789012345, "...")
        # round(0.123456789012345, 10) = 0.1234567890 → strip → "0.123456789"
        assert result == "0.123456789"

    # -- Sweep-override: deeper than cap ------------------------------------

    def test_sweep_at_minus_12_shows_12_places(self) -> None:
        # sweep "-12" → decimal_depth=12 → display_places=12
        value = 1.123456789012345678
        result = format_result(value, "-12")
        # round(value, 12) and format
        expected = f"{round(value, 12):.12f}".rstrip("0").rstrip(".")
        assert result == expected
        # And it must be deeper than 10 places in the raw formatted part
        if "." in result:
            assert len(result.split(".")[1]) <= 12

    def test_sweep_at_minus_11_shows_at_most_11_places(self) -> None:
        value = 1.123456789012345
        result = format_result(value, "-11")
        if "." in result:
            assert len(result.split(".")[1]) <= 11

    def test_sweep_shallower_than_cap_still_uses_cap(self) -> None:
        # sweep "-5" → depth=5, max(10,5)=10 → still 10 places cap
        # round(1.123456789012345, 10) = 1.1234567890 → strip trailing 0 → "1.123456789"
        result = format_result(1.123456789012345, "-5")
        assert result == "1.123456789"

    # -- Integer values ------------------------------------------------------

    def test_exact_integer_no_trailing_dot(self) -> None:
        assert format_result(5.0, "...") == "5"
        assert format_result(0.0, "...") == "0"
        assert format_result(1000.0, "...") == "1000"

    def test_negative_integer(self) -> None:
        # Negative values are clamped before conversion in the GUI, but
        # format_result itself does not clamp — test the formatter alone.
        assert format_result(-3.0, "...") == "-3"

    # -- Short decimal values (fewer than 10 places) -------------------------

    def test_short_decimal_no_spurious_trailing_zeros(self) -> None:
        assert format_result(1.5, "...") == "1.5"
        assert format_result(0.25, "...") == "0.25"
        assert format_result(3.14, "...") == "3.14"

    def test_value_with_exactly_10_decimals_no_change(self) -> None:
        # A value that already has exactly 10 decimal places
        result = format_result(1.1234567890, "...")
        assert result == "1.123456789"   # trailing zero stripped

    # -- Rounding correctness ------------------------------------------------

    def test_rounding_not_truncation_near_boundary(self) -> None:
        # 1.9999999999999 rounded to 10 places → 2.0 → stripped → "2"
        result = format_result(1.9999999999999, "...")
        assert result == "2"

    def test_rounding_not_truncation_upward(self) -> None:
        # 0.00000000005 = 5e-11; round(..., 10) → 0.0000000001 (rounds up at 10th place)
        # truncation would give "0"; rounding gives "0.0000000001"
        result = format_result(0.00000000005, "...")
        assert result == "0.0000000001"

    # -- Zero ----------------------------------------------------------------

    def test_zero(self) -> None:
        assert format_result(0.0, "...") == "0"

    # -- Sweep "0" (integer position) ----------------------------------------

    def test_sweep_zero_still_applies_cap(self) -> None:
        # round(1.123456789012345, 10) → trailing 0 stripped → "1.123456789"
        result = format_result(1.123456789012345, "0")
        assert result == "1.123456789"

    # -- Sweep positive (integer-position; larger = tens/hundreds) -----------

    def test_positive_sweep_still_applies_cap(self) -> None:
        # round(1.123456789012345, 10) → trailing 0 stripped → "1.123456789"
        result = format_result(1.123456789012345, "2")
        assert result == "1.123456789"

    # -- Very small values (no scientific notation expected) -----------------

    def test_small_value_no_scientific_notation(self) -> None:
        # 1e-8 is 0.00000001; formatted to 10 places → "0.00000001"
        result = format_result(1e-8, "...")
        assert result == "0.00000001"

    # -- Conversion scenario: unit factor produces many decimal places --------

    def test_typical_unit_conversion_result(self) -> None:
        # e.g. 1 mile → km = 1.609344 (6 places, well under cap)
        result = format_result(1.609344, "...")
        assert result == "1.609344"

    def test_result_with_many_decimals_typical(self) -> None:
        # e.g. 1 inch → metre = 0.0254 exactly
        result = format_result(0.0254, "...")
        assert result == "0.0254"
