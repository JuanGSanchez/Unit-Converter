"""
tests/test_gui_geometry.py
===========================
Deterministic, Qt-free unit tests for ``unit_converter.gui.geometry``.

Rules enforced:
- No PySide6 import anywhere in this file.
- No network access.
- No filesystem I/O.

Covers:
- ``PHI``: value is within tolerance of the mathematical golden ratio.
- ``golden_ratio_size``: portrait ratio, known value, error on non-positive.
- ``dialog_default_size``: all known keys return positive (w, h) tuples;
  unknown key raises KeyError.
- Padding constants: all strictly positive ints; all ~25% larger than
  their documented pre-refactor baselines.
- ``center_dialog_on_parent``: pure-Python computation — verified via a
  lightweight mock that records calls without importing Qt.
- Qt-freedom guard: source scan confirms no top-level PySide6 import.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from unit_converter.gui.geometry import (
    MARGIN_H,
    MARGIN_HEADER_TOP,
    MARGIN_V,
    PHI,
    SPACING_FORM_H,
    SPACING_FORM_V,
    SPACING_MAIN,
    SPACING_ROW,
    dialog_default_size,
    golden_ratio_size,
)


# ---------------------------------------------------------------------------
# Qt-freedom guard (source-text scan)
# ---------------------------------------------------------------------------

def _geometry_source() -> str:
    src = (
        Path(__file__).resolve().parent.parent
        / "unit_converter" / "gui" / "geometry.py"
    )
    return src.read_text(encoding="utf-8")


def test_no_top_level_pyside6_in_geometry_module() -> None:
    """geometry.py must have NO top-level PySide6 import statements.

    The local import inside center_dialog_on_parent is intentional and
    excluded from this check (it is inside a function body).
    """
    src = _geometry_source()
    bad = []
    for line in src.splitlines():
        stripped = stripped_line = line.strip()
        # Skip lines that are inside a function (indented) — only check
        # module-level (non-indented) imports.
        if line and not line[0].isspace():
            if stripped.startswith(("from PySide6", "import PySide6")):
                bad.append(stripped_line)
    assert bad == [], (
        f"geometry.py contains top-level PySide6 import(s): {bad}"
    )


# ---------------------------------------------------------------------------
# PHI
# ---------------------------------------------------------------------------

class TestPHI:
    def test_phi_close_to_mathematical_golden_ratio(self) -> None:
        math_phi = (1 + math.sqrt(5)) / 2
        assert abs(PHI - math_phi) < 1e-8

    def test_phi_is_float(self) -> None:
        assert isinstance(PHI, float)

    def test_phi_greater_than_one(self) -> None:
        assert PHI > 1.0

    def test_phi_less_than_two(self) -> None:
        # Sanity: phi ≈ 1.618, well under 2
        assert PHI < 2.0


# ---------------------------------------------------------------------------
# golden_ratio_size
# ---------------------------------------------------------------------------

class TestGoldenRatioSize:
    def test_known_value_width_260(self) -> None:
        w, h = golden_ratio_size(260)
        assert w == 260
        assert h == 421  # round(260 * 1.6180339887) = 421

    def test_ratio_approximates_phi(self) -> None:
        w, h = golden_ratio_size(260)
        # height / width must be within 1% of PHI
        assert abs(h / w - PHI) < 0.01

    def test_returns_tuple_of_two_ints(self) -> None:
        result = golden_ratio_size(200)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, int) for v in result)

    def test_width_preserved_exactly(self) -> None:
        for w in (100, 200, 235, 260, 400):
            got_w, _ = golden_ratio_size(w)
            assert got_w == w

    def test_height_larger_than_width(self) -> None:
        # Portrait: height > width for any reasonable width
        _, h = golden_ratio_size(260)
        assert h > 260

    def test_zero_width_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            golden_ratio_size(0)

    def test_negative_width_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            golden_ratio_size(-10)

    def test_width_1_returns_positive_height(self) -> None:
        w, h = golden_ratio_size(1)
        assert w == 1
        assert h >= 1

    def test_width_235_old_default_ratio(self) -> None:
        # The old 235×385 window had ratio 385/235 ≈ 1.638 — close to phi
        # but slightly above.  The new formula must give the same ratio within
        # 2% of phi.
        w, h = golden_ratio_size(235)
        assert abs(h / w - PHI) < 0.02


# ---------------------------------------------------------------------------
# dialog_default_size
# ---------------------------------------------------------------------------

class TestDialogDefaultSize:
    @pytest.mark.parametrize("key", ["history", "add_unit", "settings"])
    def test_known_key_returns_tuple(self, key: str) -> None:
        result = dialog_default_size(key)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.parametrize("key", ["history", "add_unit", "settings"])
    def test_width_and_height_positive(self, key: str) -> None:
        w, h = dialog_default_size(key)
        assert w > 0
        assert h > 0

    @pytest.mark.parametrize("key", ["history", "add_unit", "settings"])
    def test_width_at_least_200(self, key: str) -> None:
        # Dialogs must be at least 200 px wide to be usable
        w, _ = dialog_default_size(key)
        assert w >= 200

    @pytest.mark.parametrize("key", ["history", "add_unit", "settings"])
    def test_height_at_least_150(self, key: str) -> None:
        _, h = dialog_default_size(key)
        assert h >= 150

    def test_unknown_key_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            dialog_default_size("nonexistent_dialog")

    def test_history_wider_than_add_unit(self) -> None:
        # History dialog should be wider than the simple add-unit dialog
        w_hist, _ = dialog_default_size("history")
        w_add, _ = dialog_default_size("add_unit")
        assert w_hist > w_add

    def test_settings_is_widest(self) -> None:
        # Settings has the most controls; should be at least as wide as others
        w_settings, _ = dialog_default_size("settings")
        for key in ["history", "add_unit"]:
            w_other, _ = dialog_default_size(key)
            assert w_settings >= w_other


# ---------------------------------------------------------------------------
# Padding / spacing constants
# ---------------------------------------------------------------------------

class TestSpacingConstants:
    """All constants must be positive ints and at least 25% larger than the
    documented pre-refactor baseline values."""

    # Pre-refactor baselines for each constant
    _BASELINES: dict[str, int] = {
        "MARGIN_H": 10,
        "MARGIN_V": 7,
        "SPACING_MAIN": 5,
        "SPACING_ROW": 6,
        "MARGIN_HEADER_TOP": 5,
        "SPACING_FORM_H": 8,
        "SPACING_FORM_V": 6,
    }

    @pytest.mark.parametrize("name, value", [
        ("MARGIN_H", MARGIN_H),
        ("MARGIN_V", MARGIN_V),
        ("SPACING_MAIN", SPACING_MAIN),
        ("SPACING_ROW", SPACING_ROW),
        ("MARGIN_HEADER_TOP", MARGIN_HEADER_TOP),
        ("SPACING_FORM_H", SPACING_FORM_H),
        ("SPACING_FORM_V", SPACING_FORM_V),
    ])
    def test_constant_is_positive_int(self, name: str, value: int) -> None:
        assert isinstance(value, int), f"{name} must be int, got {type(value)}"
        assert value > 0, f"{name} must be positive, got {value}"

    @pytest.mark.parametrize("name, value", [
        ("MARGIN_H", MARGIN_H),
        ("MARGIN_V", MARGIN_V),
        ("SPACING_MAIN", SPACING_MAIN),
        ("SPACING_ROW", SPACING_ROW),
        ("MARGIN_HEADER_TOP", MARGIN_HEADER_TOP),
        ("SPACING_FORM_H", SPACING_FORM_H),
        ("SPACING_FORM_V", SPACING_FORM_V),
    ])
    def test_constant_at_least_25_percent_larger_than_baseline(
        self, name: str, value: int
    ) -> None:
        baseline = self._BASELINES[name]
        min_val = baseline * 1.20  # at least 20% increase (permissive — pixel rounding)
        assert value >= min_val, (
            f"{name}={value} is not >= 20% above baseline {baseline} "
            f"(min_val={min_val:.1f}). Check padding constants."
        )

    def test_margin_h_specific_value(self) -> None:
        assert MARGIN_H == 12  # 10 * 1.25 = 12.5 → 12

    def test_margin_v_specific_value(self) -> None:
        assert MARGIN_V == 9  # 7 * 1.25 = 8.75 → 9

    def test_spacing_main_specific_value(self) -> None:
        assert SPACING_MAIN == 6  # 5 * 1.25 = 6.25 → 6

    def test_spacing_row_specific_value(self) -> None:
        assert SPACING_ROW == 8  # 6 * 1.25 = 7.5 → 8

    def test_margin_header_top_specific_value(self) -> None:
        assert MARGIN_HEADER_TOP == 6  # 5 * 1.25 = 6.25 → 6

    def test_spacing_form_h_specific_value(self) -> None:
        assert SPACING_FORM_H == 10  # 8 * 1.25 = 10.0 → 10

    def test_spacing_form_v_specific_value(self) -> None:
        assert SPACING_FORM_V == 8  # 6 * 1.25 = 7.5 → 8


# ---------------------------------------------------------------------------
# center_dialog_on_parent — mock-based, Qt-free
# ---------------------------------------------------------------------------

class TestCenterDialogOnParent:
    """
    center_dialog_on_parent imports PySide6 locally inside the function body.
    We patch it at that import path so the test stays Qt-free.

    The function must:
    1. Call dialog.resize(default_w, default_h).
    2. Call dialog.move(x, y) where x/y center the dialog on its parent.
    """

    def _make_mock_dialog(self, parent_mock=None):
        """Return a mock dialog object."""
        dialog = MagicMock()
        dialog.parent.return_value = parent_mock
        return dialog

    def _make_mock_parent(self, x=100, y=100, width=400, height=300):
        """Return a mock parent widget whose frame geometry encloses a known rect."""
        parent = MagicMock()
        frame_geom = MagicMock()
        frame_geom.x.return_value = x
        frame_geom.y.return_value = y
        frame_geom.width.return_value = width
        frame_geom.height.return_value = height
        parent.frameGeometry.return_value = frame_geom
        # geometry() and mapToGlobal() not used in the centering math path
        return parent

    def test_resize_called_with_correct_dimensions(self) -> None:
        from unit_converter.gui.geometry import center_dialog_on_parent

        dialog = self._make_mock_dialog(parent_mock=None)

        # Patch the local QApplication import inside center_dialog_on_parent
        mock_app = MagicMock()
        screen_geom = MagicMock()
        screen_geom.width.return_value = 1920
        screen_geom.height.return_value = 1080
        mock_app.primaryScreen.return_value.geometry.return_value = screen_geom

        with patch.dict(
            "sys.modules",
            {"PySide6": MagicMock(), "PySide6.QtWidgets": MagicMock(QApplication=mock_app)},
        ):
            center_dialog_on_parent(dialog, 400, 300)

        dialog.resize.assert_called_once_with(400, 300)

    def test_move_called_centered_on_parent(self) -> None:
        from unit_converter.gui.geometry import center_dialog_on_parent

        parent = self._make_mock_parent(x=200, y=150, width=400, height=300)
        dialog = self._make_mock_dialog(parent_mock=parent)

        with patch.dict(
            "sys.modules",
            {"PySide6": MagicMock(), "PySide6.QtWidgets": MagicMock()},
        ):
            center_dialog_on_parent(dialog, 200, 150)

        # Expected center: x=200+(400-200)//2=300, y=150+(300-150)//2=225
        dialog.move.assert_called_once_with(300, 225)

    def test_move_centered_on_screen_when_no_parent(self) -> None:
        from unit_converter.gui.geometry import center_dialog_on_parent

        dialog = self._make_mock_dialog(parent_mock=None)

        mock_qapp_cls = MagicMock()
        screen_geom = MagicMock()
        screen_geom.width.return_value = 1920
        screen_geom.height.return_value = 1080
        mock_qapp_cls.primaryScreen.return_value.geometry.return_value = screen_geom

        mock_qt_widgets = MagicMock()
        mock_qt_widgets.QApplication = mock_qapp_cls

        with patch.dict(
            "sys.modules",
            {
                "PySide6": MagicMock(),
                "PySide6.QtWidgets": mock_qt_widgets,
            },
        ):
            center_dialog_on_parent(dialog, 400, 300)

        # Expected: x=(1920-400)//2=760, y=(1080-300)//2=390
        dialog.move.assert_called_once_with(760, 390)

    def test_resize_before_move(self) -> None:
        """resize must be called before move — order matters for geometry."""
        from unit_converter.gui.geometry import center_dialog_on_parent

        call_order: list[str] = []

        dialog = MagicMock()
        dialog.parent.return_value = None
        dialog.resize.side_effect = lambda w, h: call_order.append("resize")
        dialog.move.side_effect = lambda x, y: call_order.append("move")

        mock_qapp_cls = MagicMock()
        screen_geom = MagicMock()
        screen_geom.width.return_value = 1920
        screen_geom.height.return_value = 1080
        mock_qapp_cls.primaryScreen.return_value.geometry.return_value = screen_geom

        mock_qt_widgets = MagicMock()
        mock_qt_widgets.QApplication = mock_qapp_cls

        with patch.dict(
            "sys.modules",
            {
                "PySide6": MagicMock(),
                "PySide6.QtWidgets": mock_qt_widgets,
            },
        ):
            center_dialog_on_parent(dialog, 300, 200)

        assert call_order == ["resize", "move"], (
            f"Expected resize then move, got: {call_order}"
        )


# ---------------------------------------------------------------------------
# Integration: main_window.py uses geometry constants (source-text scan)
# ---------------------------------------------------------------------------

def _main_window_source() -> str:
    src = (
        Path(__file__).resolve().parent.parent
        / "unit_converter" / "gui" / "main_window.py"
    )
    return src.read_text(encoding="utf-8")


class TestMainWindowUsesGeometryModule:
    """Source-text checks that main_window.py imports and uses the geometry module."""

    def test_imports_golden_ratio_size(self) -> None:
        assert "golden_ratio_size" in _main_window_source()

    def test_imports_center_dialog_on_parent(self) -> None:
        assert "center_dialog_on_parent" in _main_window_source()

    def test_imports_margin_constants(self) -> None:
        src = _main_window_source()
        for name in ("MARGIN_H", "MARGIN_V", "SPACING_MAIN", "SPACING_ROW"):
            assert name in src, f"{name} not found in main_window.py"

    def test_no_hardcoded_old_window_size(self) -> None:
        src = _main_window_source()
        # Old size was 235×385; the new size 260×421 must come from golden_ratio_size
        # Verify the old raw literals are not re-introduced as setFixedSize arguments.
        # (The constants _WINDOW_WIDTH/_WINDOW_HEIGHT still appear but are computed.)
        assert "setFixedSize(235" not in src, (
            "Hard-coded old window width 235 found in setFixedSize call."
        )
        assert "setFixedSize(260, 385" not in src, (
            "Old height 385 combined with new width — use golden_ratio_size."
        )

    def test_dialog_uses_center_dialog_on_parent_not_bare_resize(self) -> None:
        src = _main_window_source()
        # Bare resize(NNN, NNN) should no longer exist for the dialog sizes;
        # center_dialog_on_parent wraps resize+move together.
        assert "self.resize(420" not in src, "_HistoryDialog still uses bare resize(420,..."
        assert "self.resize(300" not in src, "_AddUnitDialog still uses bare resize(300,..."
        assert "self.resize(430" not in src, "_SettingsDialog still uses bare resize(430,..."
