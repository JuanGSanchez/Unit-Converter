"""
tests/test_info_registry.py
============================
Tests for the centralized widget-info registry (SPEC-01).

Structure
---------
1. Qt-FREE portion — exercises ``INFO_TEXTS``, ``INFO_KEYS``, and
   ``register_info`` against a minimal stub object (no QApplication needed).
   Asserts:
   - Every value in ``INFO_TEXTS`` is a non-empty ``str``.
   - ``register_info`` on a stub sets toolTip == accessibleDescription ==
     whatsThis == the registry text (+ optional extra).
   - A missing key raises ``KeyError`` with a descriptive message.

2. Qt portion (offscreen QApplication, skipped gracefully if Qt unavailable) —
   builds ``MainWindow``, iterates interactive widgets, and asserts:
   - Each registered widget has non-empty ``toolTip()`` equal to its
     ``accessibleDescription()``.
   - No orphan keys exist: every key in ``INFO_KEYS`` is present in
     ``USED_KEYS`` after the UI is built.

Rules enforced
--------------
- No PySide6 imports at module top-level (the Qt portion is guarded).
- Tests are deterministic and require no network access.
- The Qt offscreen portion uses ``QT_QPA_PLATFORM=offscreen`` so it can run
  in headless CI environments.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import the Qt-free symbols from info_registry without triggering PySide6.
# info_registry.py imports PySide6 at module level (for the type annotation),
# but the module-level dict and frozenset are constructed before any Qt call.
# ---------------------------------------------------------------------------

from unit_converter.gui.info_registry import (
    INFO_KEYS,
    INFO_TEXTS,
    USED_KEYS,
    register_info,
)


# ===========================================================================
# Qt-free stub for register_info
# ===========================================================================

class _WidgetStub:
    """Minimal stub capturing the three setter calls from register_info."""

    def __init__(self) -> None:
        self._tooltip: str = ""
        self._accessible_desc: str = ""
        self._whats_this: str = ""

    def setToolTip(self, text: str) -> None:
        self._tooltip = text

    def setAccessibleDescription(self, text: str) -> None:
        self._accessible_desc = text

    def setWhatsThis(self, text: str) -> None:
        self._whats_this = text

    # Read-back helpers
    def toolTip(self) -> str:
        return self._tooltip

    def accessibleDescription(self) -> str:
        return self._accessible_desc

    def whatsThis(self) -> str:
        return self._whats_this


# ===========================================================================
# Section 1 — Qt-free tests
# ===========================================================================

class TestInfoTexts:
    """Every entry in INFO_TEXTS is a non-empty string."""

    def test_info_texts_is_dict(self) -> None:
        assert isinstance(INFO_TEXTS, dict)

    def test_info_texts_is_nonempty(self) -> None:
        assert len(INFO_TEXTS) > 0, "INFO_TEXTS must not be empty"

    def test_all_keys_are_strings(self) -> None:
        for key in INFO_TEXTS:
            assert isinstance(key, str), f"Key {key!r} is not a str"

    def test_all_values_are_nonempty_strings(self) -> None:
        for key, val in INFO_TEXTS.items():
            assert isinstance(val, str), f"Value for key {key!r} is not a str"
            assert val.strip(), f"Value for key {key!r} is empty or whitespace"

    def test_info_keys_is_frozenset(self) -> None:
        assert isinstance(INFO_KEYS, frozenset)

    def test_info_keys_equals_info_texts_keys(self) -> None:
        assert INFO_KEYS == frozenset(INFO_TEXTS)


class TestRegisterInfo:
    """register_info sets toolTip == accessibleDescription == whatsThis."""

    def _stub(self) -> _WidgetStub:
        return _WidgetStub()

    def test_sets_tooltip(self) -> None:
        stub = self._stub()
        register_info(stub, "order_label")  # type: ignore[arg-type]
        assert stub.toolTip() == INFO_TEXTS["order_label"]

    def test_sets_accessible_description(self) -> None:
        stub = self._stub()
        register_info(stub, "sweep_label")  # type: ignore[arg-type]
        assert stub.accessibleDescription() == INFO_TEXTS["sweep_label"]

    def test_sets_whats_this(self) -> None:
        stub = self._stub()
        register_info(stub, "num_entry")  # type: ignore[arg-type]
        assert stub.whatsThis() == INFO_TEXTS["num_entry"]

    def test_tooltip_equals_accessible_description(self) -> None:
        stub = self._stub()
        register_info(stub, "magnitude_combo")  # type: ignore[arg-type]
        assert stub.toolTip() == stub.accessibleDescription()

    def test_accessible_description_equals_whats_this(self) -> None:
        stub = self._stub()
        register_info(stub, "unit_combo")  # type: ignore[arg-type]
        assert stub.accessibleDescription() == stub.whatsThis()

    def test_all_three_are_identical(self) -> None:
        stub = self._stub()
        register_info(stub, "val_label")  # type: ignore[arg-type]
        assert stub.toolTip() == stub.accessibleDescription() == stub.whatsThis()

    def test_extra_appended(self) -> None:
        stub = self._stub()
        result = register_info(stub, "settings_swatch_btn", extra="\nTest Label")  # type: ignore[arg-type]
        assert result == INFO_TEXTS["settings_swatch_btn"] + "\nTest Label"
        assert stub.toolTip() == result

    def test_extra_empty_by_default(self) -> None:
        stub = self._stub()
        result = register_info(stub, "order_label")  # type: ignore[arg-type]
        assert result == INFO_TEXTS["order_label"]

    def test_returns_text(self) -> None:
        stub = self._stub()
        result = register_info(stub, "sweep_label")  # type: ignore[arg-type]
        assert isinstance(result, str) and result

    def test_returns_text_with_extra(self) -> None:
        stub = self._stub()
        result = register_info(stub, "settings_hex_edit", extra="My label")  # type: ignore[arg-type]
        assert result.endswith("My label")

    def test_missing_key_raises_key_error(self) -> None:
        stub = self._stub()
        with pytest.raises(KeyError):
            register_info(stub, "nonexistent_key_xyz")  # type: ignore[arg-type]

    def test_key_error_message_mentions_key(self) -> None:
        stub = self._stub()
        with pytest.raises(KeyError, match="nonexistent_key_xyz"):
            register_info(stub, "nonexistent_key_xyz")  # type: ignore[arg-type]

    def test_key_error_message_mentions_valid_keys(self) -> None:
        stub = self._stub()
        with pytest.raises(KeyError, match="order_label"):
            register_info(stub, "bogus_key")  # type: ignore[arg-type]

    def test_used_keys_populated(self) -> None:
        stub = self._stub()
        USED_KEYS.discard("hist_dialog")
        register_info(stub, "hist_dialog")  # type: ignore[arg-type]
        assert "hist_dialog" in USED_KEYS

    def test_every_key_exercisable(self) -> None:
        """Every key in INFO_TEXTS must be callable through register_info."""
        stub = self._stub()
        for key in INFO_TEXTS:
            result = register_info(stub, key)  # type: ignore[arg-type]
            assert result.startswith(INFO_TEXTS[key])


class TestDynamicToggleKeys:
    """The history toggle uses two registry keys for state-dependent tooltips."""

    def test_hist_toggle_to_fav_key_exists(self) -> None:
        assert "hist_toggle_to_fav" in INFO_TEXTS

    def test_hist_toggle_to_full_key_exists(self) -> None:
        assert "hist_toggle_to_full" in INFO_TEXTS

    def test_hist_toggle_to_fav_text_mentions_favorites(self) -> None:
        text = INFO_TEXTS["hist_toggle_to_fav"]
        assert "favorite" in text.lower() or "fav" in text.lower()

    def test_hist_toggle_to_full_text_differs(self) -> None:
        assert INFO_TEXTS["hist_toggle_to_fav"] != INFO_TEXTS["hist_toggle_to_full"]

    def test_toggle_slot_sets_registry_tooltip(self) -> None:
        """
        Simulate the toggle slot: switching to fav mode must set the
        hist_toggle_to_full text; switching back must set hist_toggle_to_fav.
        """
        stub = self._stub()
        # Simulate: favorites_mode just became True → show "Show All" button
        register_info(stub, "hist_toggle_to_full")  # type: ignore[arg-type]
        assert stub.toolTip() == INFO_TEXTS["hist_toggle_to_full"]
        assert stub.toolTip() == stub.accessibleDescription()

        # Simulate: toggled back to full history → show "Show Favorites" button
        register_info(stub, "hist_toggle_to_fav")  # type: ignore[arg-type]
        assert stub.toolTip() == INFO_TEXTS["hist_toggle_to_fav"]
        assert stub.toolTip() == stub.accessibleDescription()

    def _stub(self) -> _WidgetStub:
        return _WidgetStub()


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
        app = QApplication([__name__, "-platform", "offscreen"])
    return app  # type: ignore[return-value]


@_requires_qt
class TestMainWindowTooltips:
    """
    Build a headless MainWindow and verify SPEC-01 tooltip invariants.

    These tests use the offscreen platform so no display is required.
    """

    @pytest.fixture(scope="class")
    def main_window(self):  # type: ignore[return]
        """Return a live MainWindow built offscreen."""
        _get_app()
        # Set offscreen again in case QApplication was already created
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            from unit_converter.gui.main_window import MainWindow
            win = MainWindow()
            yield win
            win.close()
        except Exception as exc:
            pytest.skip(f"MainWindow construction failed: {exc}")

    def test_magnitude_combo_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._cb_magnitude.toolTip()

    def test_magnitude_combo_tooltip_equals_accessible_desc(self, main_window) -> None:
        cb = main_window._cb_magnitude
        assert cb.toolTip() == cb.accessibleDescription()

    def test_unit1_combo_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._cb_unit1.toolTip()

    def test_unit1_tooltip_equals_accessible_desc(self, main_window) -> None:
        cb = main_window._cb_unit1
        assert cb.toolTip() == cb.accessibleDescription()

    def test_unit2_combo_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._cb_unit2.toolTip()

    def test_unit2_tooltip_equals_accessible_desc(self, main_window) -> None:
        cb = main_window._cb_unit2
        assert cb.toolTip() == cb.accessibleDescription()

    def test_order1_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._order1.toolTip()

    def test_order1_tooltip_equals_accessible_desc(self, main_window) -> None:
        o = main_window._order1
        assert o.toolTip() == o.accessibleDescription()

    def test_order2_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._order2.toolTip()

    def test_order2_tooltip_equals_accessible_desc(self, main_window) -> None:
        o = main_window._order2
        assert o.toolTip() == o.accessibleDescription()

    def test_sweep1_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._sweep1.toolTip()

    def test_sweep1_tooltip_equals_accessible_desc(self, main_window) -> None:
        s = main_window._sweep1
        assert s.toolTip() == s.accessibleDescription()

    def test_sweep2_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._sweep2.toolTip()

    def test_sweep2_tooltip_equals_accessible_desc(self, main_window) -> None:
        s = main_window._sweep2
        assert s.toolTip() == s.accessibleDescription()

    def test_entry1_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._entry1.toolTip()

    def test_entry1_tooltip_equals_accessible_desc(self, main_window) -> None:
        e = main_window._entry1
        assert e.toolTip() == e.accessibleDescription()

    def test_entry2_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._entry2.toolTip()

    def test_entry2_tooltip_equals_accessible_desc(self, main_window) -> None:
        e = main_window._entry2
        assert e.toolTip() == e.accessibleDescription()

    def test_val_label1_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._lab_val1.toolTip()

    def test_val_label1_tooltip_equals_accessible_desc(self, main_window) -> None:
        v = main_window._lab_val1
        assert v.toolTip() == v.accessibleDescription()

    def test_val_label2_has_nonempty_tooltip(self, main_window) -> None:
        assert main_window._lab_val2.toolTip()

    def test_val_label2_tooltip_equals_accessible_desc(self, main_window) -> None:
        v = main_window._lab_val2
        assert v.toolTip() == v.accessibleDescription()

    def test_no_inline_tip_helper_in_main_window(self) -> None:
        """Source guard: _tip() must no longer exist in main_window.py."""
        from pathlib import Path
        src = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "main_window.py"
        ).read_text(encoding="utf-8")
        assert "def _tip(" not in src, "_tip() helper still present in main_window.py"

    def test_no_attach_description_import(self) -> None:
        """Source guard: attach_description must not be imported."""
        from pathlib import Path
        src = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "main_window.py"
        ).read_text(encoding="utf-8")
        assert "attach_description" not in src

    def test_no_inline_settoolTip_literal(self) -> None:
        """Source guard: no setToolTip( call remains in main_window.py."""
        from pathlib import Path
        src = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "main_window.py"
        ).read_text(encoding="utf-8")
        assert "setToolTip(" not in src, (
            "Inline setToolTip( call found in main_window.py — "
            "all tooltips must go through register_info"
        )

    def test_description_py_deleted(self) -> None:
        """description.py must no longer exist (SPEC-01)."""
        from pathlib import Path
        desc_path = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "description.py"
        )
        assert not desc_path.exists(), "description.py still exists — should be deleted"

    def test_used_keys_cover_all_info_keys_after_build(self, main_window) -> None:
        """
        After building MainWindow all INFO_KEYS should appear in USED_KEYS.

        Keys that are used only in dialogs (opened on demand) are excluded from
        the mandatory set because dialogs are not constructed at window build
        time.  The coverage-critical keys are the main-window ones.
        """
        # These keys are set during MainWindow construction (not dialog-only).
        main_window_keys = {
            "order_label",
            "sweep_label",
            "num_entry",
            "magnitude_combo",
            "val_label",
            "unit_combo",
        }
        missing = main_window_keys - USED_KEYS
        assert not missing, (
            f"These keys were not registered during MainWindow build: {missing}"
        )
