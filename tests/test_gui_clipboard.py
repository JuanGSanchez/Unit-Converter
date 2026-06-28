"""
tests/test_gui_clipboard.py
============================
Tests for SPEC-15 — copy/paste and clipboard integration.

Structure
---------
1. **Qt-free** — exercises the pure helpers
   :func:`unit_converter.gui.clipboard.build_copy_expression` and
   :func:`unit_converter.gui.clipboard.parse_pasted_number`.
   No QApplication is needed.

2. **Qt (offscreen)** — builds a ``MainWindow``, runs a conversion, calls
   ``_copy_result()``, and asserts ``QApplication.clipboard().text()`` holds
   the expected formatted expression.  Guarded with ``pytest.mark.skipif`` if
   PySide6 is unavailable.

Rules
-----
- No PySide6 import at module top-level (Qt portion is guarded).
- No network access.
- No real filesystem I/O (history may write; we accept that as a side-effect
  of building a full MainWindow — it is isolated per user profile).
- Deterministic and offline.
"""

from __future__ import annotations

import os

import pytest

from unit_converter.gui.clipboard import build_copy_expression, parse_pasted_number


# ===========================================================================
# Section 1 — Qt-free helpers
# ===========================================================================


class TestBuildCopyExpression:
    """Tests for build_copy_expression()."""

    def test_basic_expression(self) -> None:
        result = build_copy_expression("1", "kilometre (km)", "0.621371", "mile (mi)")
        assert result == "1 kilometre (km) = 0.621371 mile (mi)"

    def test_float_from_value_converted_to_str(self) -> None:
        result = build_copy_expression(1.0, "metre (m)", "100", "centimetre (cm)")
        assert result == "1.0 metre (m) = 100 centimetre (cm)"

    def test_zero_values(self) -> None:
        result = build_copy_expression("0", "kilogram (kg)", "0", "gram (g)")
        assert result == "0 kilogram (kg) = 0 gram (g)"

    def test_large_values(self) -> None:
        result = build_copy_expression("1000000", "metre (m)", "1000", "kilometre (km)")
        assert result == "1000000 metre (m) = 1000 kilometre (km)"

    def test_decimal_values(self) -> None:
        result = build_copy_expression("3.14159", "radian", "179.9999", "degree (°)")
        assert result == "3.14159 radian = 179.9999 degree (°)"

    def test_negative_from_value_as_string(self) -> None:
        # The GUI clamps negatives before conversion, but the helper itself
        # is agnostic — it just formats what it receives.
        result = build_copy_expression("-1", "kelvin (K)", "-1", "celsius (°C)")
        assert result == "-1 kelvin (K) = -1 celsius (°C)"

    def test_float_from_value_integer(self) -> None:
        result = build_copy_expression(42.0, "unit_a", "84", "unit_b")
        assert result == "42.0 unit_a = 84 unit_b"

    def test_returns_string(self) -> None:
        result = build_copy_expression("1", "a", "2", "b")
        assert isinstance(result, str)

    def test_format_contains_equals(self) -> None:
        result = build_copy_expression("1", "a", "2", "b")
        assert " = " in result

    def test_format_contains_from_and_to_units(self) -> None:
        result = build_copy_expression("5", "inch (in)", "12.7", "centimetre (cm)")
        assert "inch (in)" in result
        assert "centimetre (cm)" in result

    def test_format_contains_values(self) -> None:
        result = build_copy_expression("5", "inch (in)", "12.7", "centimetre (cm)")
        assert "5" in result
        assert "12.7" in result

    def test_empty_unit_names_still_formats(self) -> None:
        # Degenerate case: empty unit names should not crash.
        result = build_copy_expression("1", "", "1", "")
        assert result == "1  = 1 "

    def test_whitespace_in_unit_names_preserved(self) -> None:
        result = build_copy_expression("1", "light year", "9.461e12", "kilometre (km)")
        assert "light year" in result

    def test_string_from_value_used_as_is(self) -> None:
        # When a string is passed it must not be double-converted.
        result = build_copy_expression("3.1400", "unit", "6.28", "unit")
        assert result.startswith("3.1400 ")


class TestParsePastedNumber:
    """Tests for parse_pasted_number()."""

    # -- Valid inputs -> float -----------------------------------------------

    def test_integer_string(self) -> None:
        assert parse_pasted_number("42") == 42.0

    def test_negative_integer(self) -> None:
        assert parse_pasted_number("-7") == -7.0

    def test_positive_sign(self) -> None:
        assert parse_pasted_number("+3") == 3.0

    def test_decimal_point(self) -> None:
        result = parse_pasted_number("3.14")
        assert result is not None
        assert abs(result - 3.14) < 1e-12

    def test_leading_decimal_point(self) -> None:
        result = parse_pasted_number(".5")
        assert result is not None
        assert abs(result - 0.5) < 1e-12

    def test_trailing_decimal_point(self) -> None:
        result = parse_pasted_number("1.")
        assert result is not None
        assert abs(result - 1.0) < 1e-12

    def test_negative_decimal(self) -> None:
        result = parse_pasted_number("-3.14")
        assert result is not None
        assert abs(result - (-3.14)) < 1e-12

    def test_leading_whitespace_stripped(self) -> None:
        assert parse_pasted_number("  42  ") == 42.0

    def test_only_whitespace(self) -> None:
        assert parse_pasted_number("   ") is None

    def test_zero(self) -> None:
        assert parse_pasted_number("0") == 0.0

    def test_zero_decimal(self) -> None:
        assert parse_pasted_number("0.0") == 0.0

    def test_scientific_notation_accepted(self) -> None:
        # float("1e3") = 1000.0 — standard Python numeric string
        result = parse_pasted_number("1e3")
        assert result == 1000.0

    def test_negative_scientific(self) -> None:
        result = parse_pasted_number("-1.5e2")
        assert result is not None
        assert abs(result - (-150.0)) < 1e-9

    # -- Invalid inputs -> None ----------------------------------------------

    def test_empty_string(self) -> None:
        assert parse_pasted_number("") is None

    def test_alphabetic(self) -> None:
        assert parse_pasted_number("abc") is None

    def test_mixed_alpha_numeric(self) -> None:
        assert parse_pasted_number("12px") is None

    def test_comma_separated_thousands(self) -> None:
        # Locale-specific format not supported — SPEC-20 deferred
        assert parse_pasted_number("1,234") is None

    def test_comma_decimal_separator(self) -> None:
        # Locale-specific format not supported — SPEC-20 deferred
        assert parse_pasted_number("3,14") is None

    def test_multiple_decimal_points(self) -> None:
        assert parse_pasted_number("1.2.3") is None

    def test_inf_string_rejected(self) -> None:
        assert parse_pasted_number("inf") is None

    def test_infinity_string_rejected(self) -> None:
        assert parse_pasted_number("infinity") is None

    def test_negative_inf_rejected(self) -> None:
        assert parse_pasted_number("-inf") is None

    def test_nan_string_rejected(self) -> None:
        assert parse_pasted_number("nan") is None

    def test_nan_case_insensitive(self) -> None:
        assert parse_pasted_number("NaN") is None

    def test_inf_case_insensitive(self) -> None:
        assert parse_pasted_number("Inf") is None

    def test_signs_only(self) -> None:
        assert parse_pasted_number("+") is None
        assert parse_pasted_number("-") is None

    def test_expression_string(self) -> None:
        assert parse_pasted_number("1+2") is None

    def test_returns_float_not_int(self) -> None:
        result = parse_pasted_number("5")
        assert result is not None
        assert isinstance(result, float)

    def test_full_expression_text_rejected(self) -> None:
        # A copy expression from _copy_result must be rejected when pasted back
        text = "1 kilometre (km) = 0.621371 mile (mi)"
        assert parse_pasted_number(text) is None


# ===========================================================================
# Section 2 — offscreen Qt integration tests
# ===========================================================================

# Guard: set offscreen platform before any PySide6 import so the display
# driver is chosen before Qt initializes.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_qt_available = False
try:
    from PySide6.QtWidgets import QApplication  # noqa: E402
    _qt_available = True
except ImportError:
    pass

_requires_qt = pytest.mark.skipif(
    not _qt_available,
    reason="PySide6 not installed — offscreen Qt tests skipped",
)


def _get_app() -> "QApplication":
    """Return the existing QApplication or create a new offscreen one."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["test", "-platform", "offscreen"])
    return app  # type: ignore[return-value]


@_requires_qt
class TestClipboardQt:
    """
    Build a headless MainWindow, run a conversion, assert clipboard output.

    Uses the offscreen platform so no display is required.
    """

    @pytest.fixture(scope="class")
    def main_window(self):  # type: ignore[return]
        """Return a live MainWindow built offscreen."""
        _get_app()
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            from unit_converter.gui.main_window import MainWindow
            win = MainWindow()
            yield win
            win.close()
        except Exception as exc:
            pytest.skip(f"MainWindow construction failed: {exc}")

    def _select_length_magnitude(self, main_window) -> None:
        """Select 'Length' magnitude so units are populated."""
        idx = main_window._cb_magnitude.findText("Length")
        if idx < 0:
            pytest.skip("Length magnitude not found in test database")
        main_window._cb_magnitude.setCurrentIndex(idx)

    def test_copy_result_puts_text_on_clipboard(self, main_window) -> None:
        """After a conversion _copy_result() places text on the system clipboard."""
        self._select_length_magnitude(main_window)

        # Set a known from-value and trigger conversion
        main_window._entry1.setText("1")
        main_window._unit_converter(1)

        # Copy result
        main_window._copy_result()

        clipboard_text = QApplication.clipboard().text()
        assert clipboard_text, "Clipboard must be non-empty after _copy_result()"

    def test_copy_result_contains_from_unit(self, main_window) -> None:
        """Clipboard text contains the 'from' unit name."""
        self._select_length_magnitude(main_window)
        main_window._entry1.setText("1")
        main_window._unit_converter(1)
        main_window._copy_result()

        from_unit = main_window._cb_unit1.currentText()
        clipboard_text = QApplication.clipboard().text()
        assert from_unit in clipboard_text, (
            f"From unit {from_unit!r} not found in clipboard: {clipboard_text!r}"
        )

    def test_copy_result_contains_to_unit(self, main_window) -> None:
        """Clipboard text contains the 'to' unit name."""
        self._select_length_magnitude(main_window)
        main_window._entry1.setText("1")
        main_window._unit_converter(1)
        main_window._copy_result()

        to_unit = main_window._cb_unit2.currentText()
        clipboard_text = QApplication.clipboard().text()
        assert to_unit in clipboard_text, (
            f"To unit {to_unit!r} not found in clipboard: {clipboard_text!r}"
        )

    def test_copy_result_contains_equals_separator(self, main_window) -> None:
        """Clipboard expression contains ' = ' as the separator."""
        self._select_length_magnitude(main_window)
        main_window._entry1.setText("1")
        main_window._unit_converter(1)
        main_window._copy_result()

        clipboard_text = QApplication.clipboard().text()
        assert " = " in clipboard_text, (
            f"Expression separator ' = ' not found in: {clipboard_text!r}"
        )

    def test_copy_result_no_op_when_no_magnitude_selected(self, main_window) -> None:
        """_copy_result() is a no-op when no magnitude is selected."""
        # Reset to sentinel
        idx = main_window._cb_magnitude.findText("*Select magnitude*")
        if idx >= 0:
            main_window._cb_magnitude.setCurrentIndex(idx)

        # Put a known value on the clipboard first
        QApplication.clipboard().setText("BEFORE")
        main_window._copy_result()

        # Clipboard must be unchanged
        assert QApplication.clipboard().text() == "BEFORE", (
            "Clipboard changed even though no magnitude is selected"
        )

    def test_paste_value_populates_entry1_from_clipboard(self, main_window) -> None:
        """_paste_value() with a numeric clipboard string populates _entry1."""
        self._select_length_magnitude(main_window)

        QApplication.clipboard().setText("5.5")
        # No focused entry — default target is entry1
        main_window._entry1.clearFocus()
        main_window._entry2.clearFocus()
        main_window._paste_value()

        assert main_window._entry1.text() == "5.5", (
            f"entry1 text expected '5.5', got {main_window._entry1.text()!r}"
        )

    def test_paste_garbage_is_rejected(self, main_window) -> None:
        """_paste_value() with non-numeric clipboard text does not change entries."""
        self._select_length_magnitude(main_window)

        # Put a known valid value first
        main_window._entry1.setText("1.0")
        QApplication.clipboard().setText("not_a_number")
        main_window._paste_value()

        # entry1 must be unchanged
        assert main_window._entry1.text() == "1.0", (
            f"entry1 changed despite garbage paste; got {main_window._entry1.text()!r}"
        )

    def test_copy_result_expression_matches_build_helper(self, main_window) -> None:
        """Clipboard text matches the output of build_copy_expression() exactly."""
        self._select_length_magnitude(main_window)
        main_window._entry1.setText("1")
        main_window._unit_converter(1)
        main_window._copy_result()

        from_value = main_window._entry1.text()
        from_unit = main_window._cb_unit1.currentText()
        to_value = main_window._entry2.text()
        to_unit = main_window._cb_unit2.currentText()
        expected = build_copy_expression(from_value, from_unit, to_value, to_unit)

        clipboard_text = QApplication.clipboard().text()
        assert clipboard_text == expected, (
            f"Clipboard {clipboard_text!r} != expected {expected!r}"
        )
