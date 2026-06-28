"""
tests/test_gui_batch.py
========================
Tests for SPEC-12 — batch conversion engine (``unit_converter.gui.batch``).

Structure
---------
1. **Qt-free** (the critical heart of the suite) — uses the real core
   ``convert`` / ``list_units`` functions from
   ``unit_converter.core.converter`` to assert:

   - :func:`batch_convert_values` produces N rows exactly matching N
     individual ``convert()`` calls.
   - :func:`batch_convert_to_all_units` produces one row per unit of the
     magnitude, each equal to the direct ``convert()`` call.
   - A bad / garbage value in the values list produces a row with ``error``
     set and does NOT abort the rest of the batch.
   - :func:`rows_to_csv` produces correctly-quoted, parseable CSV
     (round-trip via ``csv.reader``).
   - ``BatchRow`` is a frozen dataclass (immutable).

2. **Qt (offscreen smoke test)** — builds a ``_BatchDialog`` offscreen to
   confirm the dialog constructs without errors.  Guarded with
   ``pytest.mark.skipif`` if PySide6 is unavailable.

Rules
-----
- No PySide6 import at module top-level.
- Uses the REAL core (no mocks for values/units) so results can be
  compared against independent ``convert()`` calls.
- No network access; no filesystem write (beyond what pytest temp-dirs give
  us).
- Fully deterministic and offline.
"""

from __future__ import annotations

import csv
import io
import os

import pytest

from unit_converter.core.converter import convert, list_units
from unit_converter.gui.batch import (
    BatchRow,
    batch_convert_values,
    batch_convert_to_all_units,
    rows_to_csv,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _direct_convert(magnitude, value, from_unit, to_unit, from_order="1", to_order="1"):
    """Thin wrapper so the call signature matches the injected convert_fn."""
    return convert(magnitude, value, from_unit, to_unit,
                   from_order=from_order, to_order=to_order)


# ===========================================================================
# Section 1 — Qt-free tests
# ===========================================================================

class TestBatchConvertValues:
    """batch_convert_values results EQUAL N individual convert() calls."""

    _MAGNITUDE = "Length"
    _FROM = "meter (m)"
    _TO = "foot (ft)"
    _VALUES = [1.0, 2.5, 1000.0]

    def _expected(self, v: float) -> float:
        return convert(self._MAGNITUDE, v, self._FROM, self._TO)

    def test_returns_correct_length(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, self._VALUES,
            self._FROM, self._TO,
        )
        assert len(rows) == len(self._VALUES)

    def test_each_output_equals_direct_convert(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, self._VALUES,
            self._FROM, self._TO,
        )
        for row, v in zip(rows, self._VALUES):
            expected = self._expected(v)
            assert row.output_value == expected, (
                f"Row for input {v!r}: got {row.output_value!r}, "
                f"expected {expected!r}"
            )

    def test_no_errors_for_valid_inputs(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, self._VALUES,
            self._FROM, self._TO,
        )
        for row in rows:
            assert row.error is None, f"Unexpected error on row: {row}"

    def test_index_assigned_correctly(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, self._VALUES,
            self._FROM, self._TO,
        )
        for i, row in enumerate(rows):
            assert row.index == i

    def test_unit_field_is_none_in_values_mode(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, self._VALUES,
            self._FROM, self._TO,
        )
        for row in rows:
            assert row.unit is None

    def test_input_value_preserved_as_string(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, ["42", "0.5"],
            self._FROM, self._TO,
        )
        assert rows[0].input_value == "42"
        assert rows[1].input_value == "0.5"

    def test_output_text_is_nonempty_string(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, [1.0],
            self._FROM, self._TO,
        )
        assert isinstance(rows[0].output_text, str)
        assert rows[0].output_text.strip()

    def test_rows_are_frozen_dataclass_instances(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, [1.0],
            self._FROM, self._TO,
        )
        row = rows[0]
        assert isinstance(row, BatchRow)
        # Frozen: assigning must raise FrozenInstanceError (dataclasses)
        with pytest.raises(Exception):
            row.output_value = 999.0  # type: ignore[misc]

    def test_parity_with_mass_magnitude(self) -> None:
        """Parity check on a second magnitude (Mass)."""
        magnitude = "Mass"
        # Get the actual unit names from core so we don't guess
        info = list_units(magnitude)
        units = info["units"]
        from_unit = units[0]
        to_unit = units[1] if len(units) > 1 else units[0]
        values = [1.0, 50.0, 0.001]
        rows = batch_convert_values(
            _direct_convert, magnitude, values, from_unit, to_unit,
        )
        for row, v in zip(rows, values):
            expected = convert(magnitude, v, from_unit, to_unit)
            assert row.output_value == expected


class TestBatchConvertValuesBadInput:
    """A bad value produces a row with error set; batch continues."""

    _MAGNITUDE = "Length"
    _FROM = "meter (m)"
    _TO = "foot (ft)"

    def test_bad_value_row_has_error_set(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, ["not_a_number"],
            self._FROM, self._TO,
        )
        assert len(rows) == 1
        assert rows[0].error is not None
        assert rows[0].output_value is None

    def test_bad_value_does_not_abort_rest(self) -> None:
        values = [1.0, "garbage", 2.0]
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, values,
            self._FROM, self._TO,
        )
        assert len(rows) == 3
        # Row 0: valid
        assert rows[0].error is None
        assert rows[0].output_value is not None
        # Row 1: error
        assert rows[1].error is not None
        assert rows[1].output_value is None
        # Row 2: valid
        assert rows[2].error is None
        assert rows[2].output_value is not None

    def test_bad_value_output_text_contains_error_info(self) -> None:
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, ["xyz"],
            self._FROM, self._TO,
        )
        # output_text on error should be the error message (non-empty)
        assert rows[0].output_text.strip()

    def test_unknown_unit_produces_error_row(self) -> None:
        """An unknown unit in the convert call produces an error row, not 0.0."""
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, [1.0],
            self._FROM,
            "nonexistent_unit_xyz",
        )
        assert rows[0].error is not None
        assert rows[0].output_value is None, (
            "Unknown unit must NOT produce 0.0 as a successful result"
        )

    def test_many_mixed_rows_all_returned(self) -> None:
        values = [1.0, "bad1", 3.0, "bad2", 5.0]
        rows = batch_convert_values(
            _direct_convert, self._MAGNITUDE, values,
            self._FROM, self._TO,
        )
        assert len(rows) == 5
        assert rows[0].error is None
        assert rows[1].error is not None
        assert rows[2].error is None
        assert rows[3].error is not None
        assert rows[4].error is None


class TestBatchConvertToAllUnits:
    """batch_convert_to_all_units: one row per unit, each equals convert()."""

    _MAGNITUDE = "Length"
    _VALUE = 1.0
    _FROM_UNIT = "metre (m)"

    def _units(self) -> list[str]:
        return list_units(self._MAGNITUDE)["units"]

    def test_returns_one_row_per_unit(self) -> None:
        expected_count = len(self._units())
        rows = batch_convert_to_all_units(
            _direct_convert, list_units,
            self._MAGNITUDE, self._VALUE, self._FROM_UNIT,
        )
        assert len(rows) == expected_count

    def test_complete_table_covers_all_units(self) -> None:
        units = self._units()
        rows = batch_convert_to_all_units(
            _direct_convert, list_units,
            self._MAGNITUDE, self._VALUE, self._FROM_UNIT,
        )
        row_units = [r.unit for r in rows]
        assert set(row_units) == set(units), (
            f"Missing units in batch result: {set(units) - set(row_units)}"
        )

    def test_each_row_equals_direct_convert(self) -> None:
        rows = batch_convert_to_all_units(
            _direct_convert, list_units,
            self._MAGNITUDE, self._VALUE, self._FROM_UNIT,
        )
        for row in rows:
            if row.error is not None:
                continue  # skip self-conversion edge cases
            expected = convert(
                self._MAGNITUDE, self._VALUE, self._FROM_UNIT, row.unit,
            )
            assert row.output_value == expected, (
                f"Unit {row.unit!r}: got {row.output_value!r}, "
                f"expected {expected!r}"
            )

    def test_index_field_is_none(self) -> None:
        rows = batch_convert_to_all_units(
            _direct_convert, list_units,
            self._MAGNITUDE, self._VALUE, self._FROM_UNIT,
        )
        for row in rows:
            assert row.index is None

    def test_unit_field_is_set(self) -> None:
        rows = batch_convert_to_all_units(
            _direct_convert, list_units,
            self._MAGNITUDE, self._VALUE, self._FROM_UNIT,
        )
        for row in rows:
            assert row.unit is not None and row.unit.strip()

    def test_input_value_preserved(self) -> None:
        rows = batch_convert_to_all_units(
            _direct_convert, list_units,
            self._MAGNITUDE, self._VALUE, self._FROM_UNIT,
        )
        for row in rows:
            assert row.input_value == str(self._VALUE)

    def test_parity_with_mass_magnitude(self) -> None:
        magnitude = "Mass"
        info = list_units(magnitude)
        from_unit = info["units"][0]
        rows = batch_convert_to_all_units(
            _direct_convert, list_units, magnitude, 1.0, from_unit,
        )
        for row in rows:
            if row.error is not None:
                continue
            expected = convert(magnitude, 1.0, from_unit, row.unit)
            assert row.output_value == expected


class TestRowsToCsv:
    """rows_to_csv produces correctly-quoted, parseable CSV."""

    def _make_row(self, idx=0, input_v="1", out_v=1.0, out_text="1", error=None, unit=None):
        return BatchRow(
            index=idx,
            unit=unit,
            input_value=input_v,
            output_value=out_v,
            output_text=out_text,
            error=error,
        )

    def test_header_row_present(self) -> None:
        row = self._make_row()
        csv_text = rows_to_csv([row], ["index", "input_value", "output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        header = next(reader)
        assert header == ["index", "input_value", "output_text"]

    def test_data_row_round_trips(self) -> None:
        row = self._make_row(idx=0, input_v="42", out_text="0.042")
        csv_text = rows_to_csv([row], ["index", "input_value", "output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)  # skip header
        data_row = next(reader)
        assert data_row == ["0", "42", "0.042"]

    def test_multiple_rows(self) -> None:
        rows = [
            self._make_row(idx=0, input_v="1", out_text="0.001"),
            self._make_row(idx=1, input_v="2", out_text="0.002"),
        ]
        csv_text = rows_to_csv(rows, ["index", "input_value", "output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)  # header
        r0 = next(reader)
        r1 = next(reader)
        assert r0 == ["0", "1", "0.001"]
        assert r1 == ["1", "2", "0.002"]

    def test_error_field_none_serialised_as_empty_string(self) -> None:
        row = self._make_row(error=None)
        csv_text = rows_to_csv([row], ["index", "error"])
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data = next(reader)
        assert data[1] == ""

    def test_commas_in_values_are_quoted(self) -> None:
        row = self._make_row(out_text="1,000")
        csv_text = rows_to_csv([row], ["output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data = next(reader)
        assert data[0] == "1,000"

    def test_quotes_in_values_are_escaped(self) -> None:
        row = self._make_row(out_text='say "hello"')
        csv_text = rows_to_csv([row], ["output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data = next(reader)
        assert data[0] == 'say "hello"'

    def test_unit_field_included(self) -> None:
        row = self._make_row(unit="kilometre (km)")
        csv_text = rows_to_csv([row], ["unit", "output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data = next(reader)
        assert data[0] == "kilometre (km)"

    def test_unknown_header_raises_value_error(self) -> None:
        row = self._make_row()
        with pytest.raises(ValueError, match="Unknown BatchRow field"):
            rows_to_csv([row], ["nonexistent_field"])

    def test_empty_rows_produces_header_only(self) -> None:
        csv_text = rows_to_csv([], ["index", "output_text"])
        reader = csv.reader(io.StringIO(csv_text))
        rows_parsed = list(reader)
        assert len(rows_parsed) == 1  # header only
        assert rows_parsed[0] == ["index", "output_text"]

    def test_all_valid_headers_accepted(self) -> None:
        valid_headers = ["index", "unit", "input_value", "output_value", "output_text", "error"]
        row = self._make_row(unit="m")
        # Should not raise
        csv_text = rows_to_csv([row], valid_headers)
        assert csv_text


class TestBatchRowDataclass:
    """BatchRow is a frozen dataclass with the expected fields."""

    def test_fields_present(self) -> None:
        row = BatchRow(
            index=0, unit=None, input_value="1", output_value=1.0,
            output_text="1", error=None,
        )
        assert row.index == 0
        assert row.unit is None
        assert row.input_value == "1"
        assert row.output_value == 1.0
        assert row.output_text == "1"
        assert row.error is None

    def test_frozen(self) -> None:
        row = BatchRow(
            index=0, unit=None, input_value="1", output_value=1.0,
            output_text="1", error=None,
        )
        with pytest.raises(Exception):
            row.index = 99  # type: ignore[misc]

    def test_unit_mode_row(self) -> None:
        row = BatchRow(
            index=None, unit="kilometre (km)", input_value="1000",
            output_value=1.0, output_text="1", error=None,
        )
        assert row.index is None
        assert row.unit == "kilometre (km)"

    def test_error_row(self) -> None:
        row = BatchRow(
            index=0, unit=None, input_value="bad", output_value=None,
            output_text="conversion error", error="conversion error",
        )
        assert row.output_value is None
        assert row.error == "conversion error"


# ===========================================================================
# Section 2 — offscreen Qt smoke test
# ===========================================================================

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


def _get_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([__name__, "-platform", "offscreen"])
    return app


@_requires_qt
class TestBatchDialogSmoke:
    """Build _BatchDialog offscreen to confirm construction succeeds."""

    @pytest.fixture(scope="class")
    def app(self):
        return _get_app()

    def test_batch_dialog_constructs(self, app) -> None:
        from unit_converter.core.converter import list_units
        from unit_converter.gui.main_window import _BatchDialog

        info = list_units("Length")
        units = info["units"]
        try:
            dlg = _BatchDialog(
                magnitude="Length",
                from_unit=units[0],
                to_unit=units[1] if len(units) > 1 else units[0],
                all_units=units,
                parent=None,
            )
            assert dlg is not None
            dlg.close()
        except Exception as exc:
            pytest.fail(f"_BatchDialog construction failed: {exc}")

    def test_batch_dialog_mode_switch(self, app) -> None:
        """Switching mode hides/shows mode-specific controls without errors.

        ``isVisible()`` requires the widget to be shown on screen; for an
        unshown dialog we check ``isHidden()`` instead (the inverse of
        visibility as set by ``setVisible``), which reflects the programmatic
        hide/show state regardless of whether the window has been shown.
        """
        from unit_converter.core.converter import list_units
        from unit_converter.gui.main_window import _BatchDialog

        info = list_units("Mass")
        units = info["units"]
        try:
            dlg = _BatchDialog(
                magnitude="Mass",
                from_unit=units[0],
                to_unit=units[1] if len(units) > 1 else units[0],
                all_units=units,
                parent=None,
            )
            # Switch to All-units mode (index 1)
            dlg._mode_combo.setCurrentIndex(1)
            # In All-units mode: values_edit hidden, single_value_edit NOT hidden
            assert dlg._values_edit.isHidden(), (
                "values_edit should be hidden in All-units mode"
            )
            assert not dlg._single_value_edit.isHidden(), (
                "single_value_edit should not be hidden in All-units mode"
            )
            # Switch back to Values-list mode (index 0)
            dlg._mode_combo.setCurrentIndex(0)
            assert not dlg._values_edit.isHidden(), (
                "values_edit should not be hidden in Values-list mode"
            )
            assert dlg._single_value_edit.isHidden(), (
                "single_value_edit should be hidden in Values-list mode"
            )
            dlg.close()
        except AssertionError:
            raise
        except Exception as exc:
            pytest.fail(f"Mode switch failed: {exc}")

    def test_no_inline_settoolTip_in_main_window(self) -> None:
        """Source guard: no inline setToolTip( calls in main_window.py.

        We detect real method-call sites: a line containing ``setToolTip(``
        that is actual code — not a comment (``#``), not inside a docstring
        (lines where the token appears after a backtick or inside a quoted
        string literal used in docstrings), and not in ``info_registry.py``
        (which legitimately calls ``widget.setToolTip`` in ``register_info``).

        The test mirrors the invariant already enforced in test_info_registry.py
        (``test_no_inline_settoolTip_literal``) and adds coverage for the new
        batch-related code added by SPEC-12.
        """
        import re
        from pathlib import Path
        src = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "main_window.py"
        ).read_text(encoding="utf-8")
        # A real setToolTip( call site:
        #   - contains the token ``setToolTip(``
        #   - the line is not a pure comment (stripped does not start with #)
        #   - the token is not inside backtick-delimited inline code (rst/md style)
        #   - the line is not a docstring line that only contains the token
        #     inside `` `` or between quotes
        real_calls = []
        for ln in src.splitlines():
            stripped = ln.strip()
            if "setToolTip(" not in ln:
                continue
            if stripped.startswith("#"):
                continue
            # Backtick-delimited inline code in docstrings/comments:
            # ``setToolTip(...)``  (RST double-backtick) or `setToolTip(...)`.
            # Remove all backtick-quoted spans (greedy from outermost `` to ``)
            # then re-check whether a real call site remains.
            without_backtick_code = re.sub(r"``[^`]*``", "", ln)
            without_backtick_code = re.sub(r"`[^`]*`", "", without_backtick_code)
            if "setToolTip(" not in without_backtick_code:
                continue
            real_calls.append(ln)
        assert not real_calls, (
            f"Inline setToolTip( calls found in main_window.py:\n"
            + "\n".join(real_calls)
        )
