"""
unit_converter.gui.main_window
================================
PySide6 main window for the U Converter application.

Features:
- Fixed 260 x 421 px window (golden-ratio portrait, φ ≈ 1.618), centered on screen, non-resizable.
- Custom window icon from ``Logo UC.png``.
- Magnitude selector (QComboBox), two unit selectors with SI/IEC order
  controls (scrollable QLabel), numeric entry (QLineEdit), and a
  scientific-notation display label — for both the "From" and "To" slots.
- Bidirectional live conversion: editing either value recomputes the other.
- Order-of-magnitude control: scroll wheel on the order label cycles prefixes
  (q … Q for SI; 1 … Q for IEC/Data); click resets to "1".
- Digit-sweep control: scroll wheel on the sweep label adjusts the decimal
  position used by the Up/Down arrow increment; click resets to "...".
- Arrow-key (Up/Down) and mouse-wheel nudge of the numeric entry value.
- Hover tooltips (QToolTip) for every widget that carries user-visible info.
  All tooltips are set via :func:`info_registry.register_info` — no inline
  literals.  One ``QToolTip { ... }`` QSS block in ``theme.py`` styles them.
- Right-click context menu: Settings, History/Favorites, Add Custom Unit,
  About, and Exit.
- Ctrl+Q exits the application.
- Return/Enter triggers conversion.
- All conversion math delegated to ``unit_converter.core.converter``.
- Conversion history panel (UC-I07): recent conversions persist across sessions.
- Custom-unit dialog: add user-defined units persisted to ~/.unit-converter/custom.toml.
- Light/Dark theming: all colors driven from ``gui.theme``; user picks and
  persists their palette via Settings (right-click menu).

Implementation notes
--------------------
- The window is NOT frameless; the OS title-bar is preserved as expected.
- Hover tooltips use Qt native QToolTip via :func:`info_registry.register_info`,
  which sets tooltip + accessible description + WhatsThis from one registry.
- Ctrl+Q is the quit shortcut (universally expected in Qt apps).
- No ``del locals()`` / ``gc.collect()`` / ``del self`` cargo-cult exit — uses
  standard Qt ``QApplication.quit()``.
- Theme state is loaded from ``~/.unit-converter/gui_theme.json`` on startup
  via the Qt-independent ``gui.theme_persist`` helper.
"""

from __future__ import annotations

import logging
import math
import os

from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)
from PySide6.QtGui import (
    QColor,
    QDoubleValidator,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from unit_converter.core import converter as _core
from unit_converter.core.data_loader import MagnitudeDataError, add_custom_unit
from unit_converter.core.history import (
    HistoryEntry,
    add_favorite,
    delete_entry as _delete_entry,
    list_favorites,
    load_history,
    record as _record_history,
    remove_favorite,
)
from unit_converter.gui.history_menu import context_menu_actions as _ctx_actions
from unit_converter.gui import theme as _theme
from unit_converter.gui.format_result import format_result as _format_result
from unit_converter.gui.info_registry import register_info as _register_info
from unit_converter.gui.theme_persist import (
    is_valid_hex_color,
    load_theme_prefs,
    merge_theme_colors,
    normalize_hex_color,
    save_theme_prefs,
)
from unit_converter.gui.geometry import (
    MARGIN_H,
    MARGIN_V,
    MARGIN_HEADER_TOP,
    SPACING_FORM_H,
    SPACING_FORM_V,
    SPACING_MAIN,
    SPACING_ROW,
    center_dialog_on_parent,
    dialog_default_size,
    golden_ratio_size,
)
from unit_converter.gui.resources import logo_path


# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

__author__ = "Juan Garcia Sanchez"
__title__ = "U Converter"
__version__ = "1.1.0"
__datver__ = "06-2026"
__pyver__ = "3.11"
__license__ = "GPLv3"

# Window geometry — golden ratio (φ ≈ 1.618) portrait, slightly larger than
# the original 235×385.  Width chosen first; height = round(width * PHI).
_WINDOW_WIDTH, _WINDOW_HEIGHT = golden_ratio_size(260)


# ---------------------------------------------------------------------------
# Scrollable order label
# ---------------------------------------------------------------------------

class _OrderLabel(QLabel):
    """
    A label whose scroll wheel cycles through SI or IEC prefix symbols.

    Clicking resets to ``"1"`` (no prefix).  The parent window supplies the
    prefix sequence via ``set_order_list``.
    """

    def __init__(self, on_change, parent: QWidget | None = None) -> None:
        super().__init__("1", parent)
        self._on_change = on_change   # callable() — triggered after a change
        self._keys: list[str] = ["1"]  # prefix symbol sequence
        self._vals: list[int] = [0]    # exponent sequence
        self.setAlignment(Qt.AlignCenter)
        _register_info(self, "order_label")
        # Stylesheet is applied by the caller via restyle(colors) immediately
        # after construction; no need for a redundant default-theme pass here.
        self.setFixedWidth(36)
        self.setCursor(Qt.PointingHandCursor)

    def restyle(self, colors: dict[str, str]) -> None:
        """Update stylesheet from the provided colour mapping."""
        self.setStyleSheet(_theme.build_order_label_stylesheet(colors))

    def set_order_list(self, keys: list[str], vals: list[int]) -> None:
        """Update the prefix table this label cycles through."""
        self._keys = keys
        self._vals = vals

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setText("1")
            self._on_change()
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        current = self.text()
        # Determine current index in the keys list
        try:
            idx = self._keys.index(current)
        except ValueError:
            idx = self._keys.index("1") if "1" in self._keys else 0

        delta = event.angleDelta().y()
        step = 1 if delta > 0 else -1
        new_idx = idx + step
        if 0 <= new_idx < len(self._keys):
            self.setText(self._keys[new_idx])
            self._on_change()
        event.accept()


# ---------------------------------------------------------------------------
# Scrollable sweep label
# ---------------------------------------------------------------------------

class _SweepLabel(QLabel):
    """
    A label that tracks the decimal position used for Up/Down nudging.

    Scrolling adjusts the digit position; clicking resets to ``"..."`` (auto).
    Text values: ``"..."`` (auto), ``"0"``, ``"1"``, ``"-1"``, ..., ``"99"``,
    ``"-99"`` — matching the original change_sweep logic exactly.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("...", parent)
        self.setAlignment(Qt.AlignCenter)
        _register_info(self, "sweep_label")
        # Stylesheet is applied by the caller via restyle(colors) immediately
        # after construction; no need for a redundant default-theme pass here.
        self.setFixedWidth(36)
        self.setCursor(Qt.PointingHandCursor)

    def restyle(self, colors: dict[str, str]) -> None:
        """Update stylesheet from the provided colour mapping."""
        self.setStyleSheet(_theme.build_sweep_label_stylesheet(colors))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setText("...")
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        step = 1 if delta > 0 else -1   # positive = forward = increment
        current = self.text()

        # Replicate change_sweep logic verbatim.
        # Original: step = int(e.delta/120); positive = scroll-up = increment.
        # '...' -> scroll-down goes to '-1'; scroll-up goes to '0'.
        # '0'   -> scroll-down goes to '...'; scroll-up goes to '1'.
        # '-1'  -> scroll-down goes to '-2'; scroll-up goes to '...'.
        match current:
            case "...":
                new = str(step) if step < 0 else "0"   # step<0 -> "-1"; step>0 -> "0"
            case "0":
                new = "..." if step < 0 else "1"
            case "-1":
                new = "-2" if step < 0 else "..."
            case "99":
                new = str(int(current) + step) if step < 0 else "99"
            case "-99":
                new = "-99" if step < 0 else str(int(current) + step)
            case _:
                new = str(int(current) + step)

        self.setText(new)
        event.accept()


# ---------------------------------------------------------------------------
# Numeric entry with wheel/arrow nudge
# ---------------------------------------------------------------------------

class _NumEntry(QLineEdit):
    """
    A QLineEdit that supports Up/Down arrow and mouse-wheel value nudging,
    driven by the associated sweep label.
    """

    def __init__(
        self,
        sweep_label: _SweepLabel,
        on_change,  # callable(slot: int) where slot=1 or 2
        slot: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("0.0", parent)
        self._sweep = sweep_label
        self._on_change = on_change
        self._slot = slot
        validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.setValidator(validator)
        self.setAlignment(Qt.AlignLeft)
        # Stylesheet is applied by the caller via restyle(colors) immediately
        # after construction; no need for a redundant default-theme pass here.
        self.setEnabled(False)
        _register_info(self, "num_entry")

    def restyle(self, colors: dict[str, str]) -> None:
        """Update stylesheet from the provided colour mapping."""
        self.setStyleSheet(_theme.build_entry_stylesheet(colors))

    def _nudge(self, step: int) -> None:
        """Increment / decrement the current value by one step at the current sweep position."""
        try:
            val = float(self.text())
        except ValueError:
            val = 0.0

        sweep_text = self._sweep.text()
        if sweep_text == "...":
            # Auto-detect decimal places from current string
            s = self.text()
            if "." in s:
                decimals = len(s.split(".")[-1])
            else:
                decimals = 0
        else:
            decimals = -int(sweep_text)  # negative sweep_text → integer step

        # Both branches mirror the original: round(val + e*10**(-decimals), decimals)
        new_val = round(val + step * 10 ** (-decimals), decimals)

        self.setText(f"{new_val}")
        self._on_change(self._slot)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Up:
            self._nudge(1)
            event.accept()
            return
        if event.key() == Qt.Key_Down:
            self._nudge(-1)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        step = 1 if delta > 0 else -1
        self._nudge(step)
        event.accept()


# ---------------------------------------------------------------------------
# History dialog (UC-I07)
# ---------------------------------------------------------------------------

class _HistoryDialog(QDialog):
    """
    Non-modal dialog listing recent conversions and favorites (UC-I07).

    Selecting an entry and clicking "Re-run" emits it back to the main window
    via ``accept()``; the parent reads ``selected_entry()`` after exec().

    Features
    --------
    - Full-history view (default) shows all entries via ``load_history()``;
      starred entries are prefixed with ``"* "``.
    - Favorites-only view shows only favorited entries via ``list_favorites()``.
    - "Show Favorites" / "Show All" toggle button switches between views; its
      label reflects the current mode.
    - Right-click context menu on the list provides: Re-run, Add to Favorites,
      Remove from Favorites, Delete.  Which actions are active is determined by
      :func:`unit_converter.gui.history_menu.context_menu_actions` (Qt-free
      helper) based on the current view mode and the selected entry's state.
    - After any mutating action (add/remove favorite, delete) the list is
      refreshed in-place, respecting the current view mode.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        colors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conversion History")
        _w, _h = dialog_default_size("history")
        center_dialog_on_parent(self, _w, _h)
        _register_info(self, "hist_dialog")

        # Apply dialog theme using the live override-aware color mapping.
        # Falls back to the built-in Light palette if no colors are supplied.
        _colors = colors if colors is not None else _theme.LIGHT_THEME.colors
        self.setStyleSheet(_theme.build_dialog_stylesheet(_colors))
        self._selected_entry: HistoryEntry | None = None

        # Track whether we are in favorites-only view
        self._favorites_mode: bool = False

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        _register_info(self._list, "hist_list")
        # Enable the custom context menu signal
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox()
        self._btn_rerun = buttons.addButton("Re-run", QDialogButtonBox.ActionRole)
        self._btn_fav = buttons.addButton("Favorite", QDialogButtonBox.ActionRole)
        self._btn_toggle = buttons.addButton(
            "Show Favorites", QDialogButtonBox.ActionRole
        )
        buttons.addButton(QDialogButtonBox.Close)
        layout.addWidget(buttons)

        _register_info(self._btn_rerun, "hist_btn_rerun")
        _register_info(self._btn_fav, "hist_btn_fav")
        # Initial toggle button tooltip — full→fav direction (not yet in fav mode)
        _register_info(self._btn_toggle, "hist_toggle_to_fav")

        self._btn_rerun.clicked.connect(self._on_rerun)
        self._btn_fav.clicked.connect(self._on_favorite)
        self._btn_toggle.clicked.connect(self._on_toggle_view)
        buttons.rejected.connect(self.close)

        self._entries: list[HistoryEntry] = []
        self._refresh()

    # ------------------------------------------------------------------
    # List refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Reload and redisplay entries for the current view mode."""
        self._list.clear()
        try:
            if self._favorites_mode:
                self._entries = list_favorites()
            else:
                self._entries = load_history()
        except Exception:
            logger.exception("Failed to load history for dialog refresh")
            self._entries = []
        for e in self._entries:
            star = "* " if e.favorite else ""
            label = (
                f"{star}{e.magnitude}: {e.value} {e.from_unit} -> "
                f"{e.result:.6g} {e.to_unit}  [{e.timestamp[:10]}]"
            )
            self._list.addItem(QListWidgetItem(label))

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_rerun(self) -> None:
        """Re-run button: accept dialog and surface the selected entry."""
        idx = self._list.currentRow()
        if 0 <= idx < len(self._entries):
            self._selected_entry = self._entries[idx]
            self.accept()

    def _on_favorite(self) -> None:
        """Favorite button: add the selected entry as a favorite."""
        idx = self._list.currentRow()
        if 0 <= idx < len(self._entries):
            entry = self._entries[idx]
            try:
                add_favorite(entry, label="")
            except Exception:
                logger.exception(
                    "Failed to add favorite for entry timestamp=%r", entry.timestamp
                )
                return
            self._refresh()

    def _on_toggle_view(self) -> None:
        """Toggle between full-history and favorites-only view.

        Uses registry keys ``hist_toggle_to_full`` and ``hist_toggle_to_fav``
        so the dynamic tooltip change is tested via :func:`register_info`
        (SPEC-01 state-dependent tooltip requirement).
        """
        self._favorites_mode = not self._favorites_mode
        if self._favorites_mode:
            self._btn_toggle.setText("Show All")
            _register_info(self._btn_toggle, "hist_toggle_to_full")
        else:
            self._btn_toggle.setText("Show Favorites")
            _register_info(self._btn_toggle, "hist_toggle_to_fav")
        self._refresh()

    # ------------------------------------------------------------------
    # Right-click context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        """Build and show a context menu for the list item under *pos*."""
        idx = self._list.currentRow()
        if not (0 <= idx < len(self._entries)):
            return

        entry = self._entries[idx]
        actions_enabled = _ctx_actions(
            is_favorites_view=self._favorites_mode,
            entry_is_favorite=entry.favorite,
        )

        menu = QMenu(self)

        act_rerun = menu.addAction("Re-run")
        act_rerun.setEnabled(actions_enabled.get("run_again", False))

        menu.addSeparator()

        act_add_fav = menu.addAction("Add to Favorites")
        act_add_fav.setEnabled(actions_enabled.get("add_favorite", False))
        act_add_fav.setVisible(actions_enabled.get("add_favorite", False))

        act_rem_fav = menu.addAction("Remove from Favorites")
        act_rem_fav.setEnabled(actions_enabled.get("remove_favorite", False))
        act_rem_fav.setVisible(actions_enabled.get("remove_favorite", False))

        menu.addSeparator()

        act_delete = menu.addAction("Delete")
        act_delete.setEnabled(actions_enabled.get("delete", False))

        chosen = menu.exec(self._list.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen is act_rerun:
            self._selected_entry = entry
            self.accept()
        elif chosen is act_add_fav:
            self._ctx_add_favorite(entry)
        elif chosen is act_rem_fav:
            self._ctx_remove_favorite(entry)
        elif chosen is act_delete:
            self._ctx_delete(entry)

    def _ctx_add_favorite(self, entry: HistoryEntry) -> None:
        """Context menu — Add to Favorites."""
        try:
            add_favorite(entry, label="")
        except Exception:
            logger.exception(
                "Context menu: failed to add favorite, timestamp=%r", entry.timestamp
            )
            return
        self._refresh()

    def _ctx_remove_favorite(self, entry: HistoryEntry) -> None:
        """Context menu — Remove from Favorites."""
        try:
            remove_favorite(entry)
        except Exception:
            logger.exception(
                "Context menu: failed to remove favorite, timestamp=%r", entry.timestamp
            )
            return
        self._refresh()

    def _ctx_delete(self, entry: HistoryEntry) -> None:
        """Context menu — Delete entry."""
        try:
            _delete_entry(entry)
        except Exception:
            logger.exception(
                "Context menu: failed to delete entry, timestamp=%r", entry.timestamp
            )
            return
        self._refresh()

    # ------------------------------------------------------------------
    # Public result accessor
    # ------------------------------------------------------------------

    def selected_entry(self) -> HistoryEntry | None:
        return self._selected_entry


# ---------------------------------------------------------------------------
# Custom-unit dialog (UC-I03 GUI integration)
# ---------------------------------------------------------------------------

class _AddUnitDialog(QDialog):
    """Simple dialog for adding a custom unit."""

    def __init__(
        self,
        magnitude_names: list[str],
        parent: QWidget | None = None,
        colors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Custom Unit")
        _w, _h = dialog_default_size("add_unit")
        center_dialog_on_parent(self, _w, _h)
        _register_info(self, "add_unit_dialog")

        # Apply dialog theme using the live override-aware color mapping.
        # Falls back to the built-in Light palette if no colors are supplied.
        _colors = colors if colors is not None else _theme.LIGHT_THEME.colors
        self.setStyleSheet(_theme.build_dialog_stylesheet(_colors))

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._cb_magnitude = QComboBox()
        self._cb_magnitude.addItems(magnitude_names)
        _register_info(self._cb_magnitude, "add_unit_magnitude_combo")
        form.addRow("Magnitude:", self._cb_magnitude)

        self._ed_name = QLineEdit()
        self._ed_name.setPlaceholderText("e.g. stone (st)")
        _register_info(self._ed_name, "add_unit_name_edit")
        form.addRow("Unit name:", self._ed_name)

        self._ed_factor = QLineEdit()
        self._ed_factor.setPlaceholderText("e.g. 6350.29")
        _register_info(self._ed_factor, "add_unit_factor_edit")
        form.addRow("Factor:", self._ed_factor)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        mag = self._cb_magnitude.currentText()
        name = self._ed_name.text().strip()
        factor_text = self._ed_factor.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Unit name must not be empty.")
            return
        try:
            factor = float(factor_text)
        except ValueError:
            QMessageBox.warning(self, "Validation", "Factor must be a number.")
            return
        try:
            add_custom_unit(mag, name, factor)
        except Exception as exc:
            QMessageBox.warning(self, "Validation", str(exc))
            return
        self.accept()


# ---------------------------------------------------------------------------
# Settings dialog (TASK 2)
# ---------------------------------------------------------------------------

# Human-readable labels for each colour role key
_COLOR_ROLE_LABELS: dict[str, str] = {
    "bg_main":      "Window background",
    "bg_title":     "Title / header strip background",
    "bg_entry":     "Entry field background",
    "bg_sweep":     "Sweep label background",
    "bg_combo":     "Combo box background",
    "bg_dialog":    "Dialog background",
    "fg_title":     "Title / header accent text",
    "fg_main":      "Body text",
    "fg_entry":     "Entry field text",
    "border_main":  "Control border",
    "border_heavy": "Ridge / heavy border",
}


class _SettingsDialog(QDialog):
    """
    Settings dialog — theme selection and per-widget-type colour overrides.

    Modelled on :class:`_HistoryDialog`.  Offers:
    - A built-in theme selector (Light / Dark).
    - A scrollable per-widget-type colour table with a colour swatch button
      (opens QColorDialog for Office-style palette picking) and a validated
      ``#RRGGBB`` hex text entry.
    - "Apply" (applies immediately without closing) and standard Ok/Cancel.

    On Ok the chosen colours are persisted to
    ``~/.unit-converter/gui_theme.json`` via :func:`theme_persist.save_theme_prefs`.
    """

    def __init__(
        self,
        current_colors: dict[str, str],
        current_theme_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings — Theme & Colors")
        _w, _h = dialog_default_size("settings")
        center_dialog_on_parent(self, _w, _h)
        _register_info(self, "settings_dialog")

        # Working copy of colours that the user is editing
        self._working: dict[str, str] = dict(current_colors)
        self._theme_name: str = current_theme_name

        layout = QVBoxLayout(self)

        # -- Theme selector ---------------------------------------------------
        theme_group = QGroupBox("Built-in theme")
        theme_row = QHBoxLayout(theme_group)
        theme_row.addWidget(QLabel("Theme:"))
        self._cb_theme = QComboBox()
        self._cb_theme.addItems(list(_theme.BUILT_IN_THEMES.keys()))
        idx = self._cb_theme.findText(current_theme_name)
        if idx >= 0:
            self._cb_theme.setCurrentIndex(idx)
        _register_info(self._cb_theme, "settings_theme_combo")
        theme_row.addWidget(self._cb_theme, stretch=1)
        load_btn = QPushButton("Load theme")
        _register_info(load_btn, "settings_load_btn")
        load_btn.clicked.connect(self._on_load_theme)
        theme_row.addWidget(load_btn)
        layout.addWidget(theme_group)

        # -- Per-widget colour overrides -------------------------------------
        color_group = QGroupBox("Widget colours  (hex #RRGGBB or click swatch)")
        scroll_content = QWidget()
        form = QFormLayout(scroll_content)
        form.setHorizontalSpacing(SPACING_FORM_H)
        form.setVerticalSpacing(SPACING_FORM_V)

        self._swatch_btns: dict[str, QPushButton] = {}
        self._hex_edits: dict[str, QLineEdit] = {}

        for key, label in _COLOR_ROLE_LABELS.items():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            swatch = QPushButton()
            swatch.setFixedSize(28, 22)
            _register_info(swatch, "settings_swatch_btn", extra=f"\n{label}")
            self._update_swatch(swatch, self._working.get(key, "#808080"))
            swatch.clicked.connect(lambda checked=False, k=key: self._on_pick_color(k))
            self._swatch_btns[key] = swatch
            row_layout.addWidget(swatch)

            hex_ed = QLineEdit(self._working.get(key, "#808080"))
            hex_ed.setFixedWidth(80)
            hex_ed.setMaxLength(7)
            hex_ed.setPlaceholderText("#RRGGBB")
            _register_info(hex_ed, "settings_hex_edit", extra=f"{label}")
            hex_ed.textEdited.connect(lambda text, k=key: self._on_hex_edited(k, text))
            self._hex_edits[key] = hex_ed
            row_layout.addWidget(hex_ed)

            form.addRow(label + ":", row_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # -- Buttons ----------------------------------------------------------
        button_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        _register_info(apply_btn, "settings_apply_btn")
        apply_btn.clicked.connect(self._on_apply)
        button_row.addWidget(apply_btn)

        dlg_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dlg_buttons.accepted.connect(self._on_ok)
        dlg_buttons.rejected.connect(self.reject)
        button_row.addWidget(dlg_buttons)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _update_swatch(btn: QPushButton, hex_color: str) -> None:
        """Set the swatch button background to *hex_color*."""
        btn.setStyleSheet(
            f"background-color: {hex_color}; "
            "border: 1px solid #808080;"
        )

    def _on_load_theme(self) -> None:
        """Reset all working colours to the selected built-in theme."""
        name = self._cb_theme.currentText()
        builtin = _theme.BUILT_IN_THEMES.get(name)
        if builtin is None:
            return
        self._theme_name = name
        self._working = dict(builtin.colors)
        # Update all swatch buttons and hex entries
        for key in _COLOR_ROLE_LABELS:
            color = self._working.get(key, "#808080")
            self._update_swatch(self._swatch_btns[key], color)
            self._hex_edits[key].setText(color)
            self._hex_edits[key].setStyleSheet("")

    def _on_pick_color(self, key: str) -> None:
        """Open QColorDialog for *key* and update swatch + hex entry."""
        current_hex = self._working.get(key, "#808080")
        initial = QColor(current_hex)
        picked = QColorDialog.getColor(initial, self, f"Choose colour — {_COLOR_ROLE_LABELS.get(key, key)}")
        if picked.isValid():
            hex_val = picked.name().upper()  # Qt returns #rrggbb; upper() for consistency
            self._working[key] = hex_val
            self._update_swatch(self._swatch_btns[key], hex_val)
            self._hex_edits[key].setText(hex_val)
            self._hex_edits[key].setStyleSheet("")

    def _on_hex_edited(self, key: str, text: str) -> None:
        """Validate and store a manually typed hex colour."""
        normed = normalize_hex_color(text)
        if normed is not None:
            self._working[key] = normed
            self._update_swatch(self._swatch_btns[key], normed)
            self._hex_edits[key].setStyleSheet("")  # clear error highlight
        else:
            # Visual feedback: red border while the string is invalid
            self._hex_edits[key].setStyleSheet("border: 2px solid red;")

    def _on_apply(self) -> None:
        """Apply current working colours to the main window without closing."""
        parent = self.parent()
        if parent is not None and hasattr(parent, "_apply_theme_colors"):
            parent._apply_theme_colors(self._working, self._theme_name)

    def _on_ok(self) -> None:
        """Apply colours, persist them, then accept the dialog."""
        self._on_apply()
        prefs: dict[str, str] = {"__theme__": self._theme_name}
        prefs.update(self._working)
        save_theme_prefs(prefs)
        self.accept()

    # ------------------------------------------------------------------
    # Public result accessors
    # ------------------------------------------------------------------

    def result_colors(self) -> dict[str, str]:
        """Return the working colour mapping as configured by the user."""
        return dict(self._working)

    def result_theme_name(self) -> str:
        """Return the selected built-in theme name."""
        return self._theme_name


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    """
    PySide6 main window for U Converter.

    Fixed 260 x 421 px (golden-ratio portrait), centered, non-resizable.  Wired entirely to the pure
    ``unit_converter.core.converter`` API — no conversion math is implemented
    here.  Integrates history (UC-I07) and custom units (UC-I03).

    All widget colours are driven by :mod:`unit_converter.gui.theme`; user
    preferences are loaded from / persisted to
    ``~/.unit-converter/gui_theme.json`` via
    :mod:`unit_converter.gui.theme_persist`.
    """

    def __init__(self) -> None:
        super().__init__()

        # --- Load and merge theme preferences --------------------------------
        prefs = load_theme_prefs()
        theme_name = prefs.pop("__theme__", _theme.DEFAULT_THEME_NAME)
        builtin = _theme.BUILT_IN_THEMES.get(theme_name, _theme.LIGHT_THEME)
        self._active_colors: dict[str, str] = merge_theme_colors(
            builtin.colors, prefs
        )
        self._active_theme_name: str = theme_name

        self._setup_window()

        # --- Load database via the pure core (raises MagnitudeDataError on failure) ---
        try:
            raw_db = _core._get_db()
        except MagnitudeDataError as exc:
            QMessageBox.critical(
                self,
                "Database error",
                f"Cannot load magnitude database:\n{exc}\n\nExiting.",
            )
            raise SystemExit(1) from exc

        # Build internal data structures matching the original attribute layout
        self._magnitudes: list[dict[str, float]] = []
        self._magnitude_names: dict[str, int] = {"*Select magnitude*": -1}
        for mag_name, units_dict in raw_db.items():
            self._magnitude_names[mag_name] = len(self._magnitudes)
            self._magnitudes.append(dict(units_dict))
        # Sentinel: used internally when no magnitude is selected
        self._magnitudes.append({"": 0.0, " ": 1.0})

        # Order-prefix tables (same contents as original dict_order1/2)
        self._order_si_keys: list[str] = list(_core.DICT_ORDER_SI.keys())
        self._order_si_vals: list[int] = list(_core.DICT_ORDER_SI.values())
        self._order_iec_keys: list[str] = list(_core.DICT_ORDER_IEC.keys())
        self._order_iec_vals: list[int] = list(_core.DICT_ORDER_IEC.values())

        self._val1: float = 0.0
        self._val2: float = 0.0
        self._val1_old: float = 0.0
        self._val2_old: float = 0.0

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()

        # Apply the loaded theme to all widgets now that they exist
        _theme.apply_colors_to_main_window(self, self._active_colors)

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(__title__)
        self.setFixedSize(_WINDOW_WIDTH, _WINDOW_HEIGHT)

        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - _WINDOW_WIDTH) // 2
        y = (screen.height() - _WINDOW_HEIGHT) // 2
        self.move(x, y)

        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowSystemMenuHint
            | Qt.MSWindowsFixedSizeDialogHint
        )

        # Icon
        logo = logo_path()
        if os.path.isfile(logo):
            self.setWindowIcon(QIcon(logo))

        self.setStyleSheet(_theme.build_main_window_stylesheet(self._active_colors))

    # ------------------------------------------------------------------
    # Theme application (called on startup and on Settings change)
    # ------------------------------------------------------------------

    def _apply_theme_colors(
        self,
        colors: dict[str, str],
        theme_name: str,
    ) -> None:
        """
        Apply *colors* to all widgets and store the active state.

        Called both on startup (from ``__init__``) and when the Settings
        dialog applies or accepts.
        """
        self._active_colors = colors
        self._active_theme_name = theme_name
        _theme.apply_colors_to_main_window(self, colors)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)
        layout.setSpacing(SPACING_MAIN)

        # ---- Magnitude label + combo ----
        self._lab_mag = QLabel("Magnitude")
        self._lab_mag.setAlignment(Qt.AlignCenter)
        # Initial stylesheet; will be overridden by apply_colors_to_main_window
        self._lab_mag.setStyleSheet(
            _theme.build_magnitude_label_stylesheet(self._active_colors)
        )
        layout.addWidget(self._lab_mag)

        self._cb_magnitude = QComboBox()
        self._cb_magnitude.addItems(list(self._magnitude_names.keys()))
        self._cb_magnitude.setCurrentIndex(0)
        self._cb_magnitude.setEnabled(True)
        self._cb_magnitude.setStyleSheet(
            _theme.build_combo_stylesheet(self._active_colors)
        )
        _register_info(self._cb_magnitude, "magnitude_combo")
        layout.addWidget(self._cb_magnitude)

        # ---- From section ----
        from_header = self._make_header_row("From:")
        layout.addLayout(from_header)

        from_controls = self._make_unit_row(slot=1)
        layout.addLayout(from_controls)

        from_entry = self._make_entry_row(slot=1)
        layout.addLayout(from_entry)

        # ---- To section ----
        to_header = self._make_header_row("To:")
        layout.addLayout(to_header)

        to_controls = self._make_unit_row(slot=2)
        layout.addLayout(to_controls)

        to_entry = self._make_entry_row(slot=2)
        layout.addLayout(to_entry)

        self.setLayout(layout)

    def _make_header_row(self, label_text: str):
        """Create a horizontal row with a direction label on the left and a
        scientific-notation value label on the right."""
        row = QHBoxLayout()
        row.setContentsMargins(0, MARGIN_HEADER_TOP, 0, 0)

        lab = QLabel(label_text)
        lab.setStyleSheet(
            _theme.build_header_label_stylesheet(self._active_colors)
        )
        row.addWidget(lab)

        # Store From:/To: label references for restyles
        if label_text.startswith("From"):
            self._lab_from = lab
        else:
            self._lab_to = lab

        row.addStretch(1)

        val_lab = QLabel("{:.1e}".format(0.0))
        val_lab.setAlignment(Qt.AlignCenter)
        val_lab.setStyleSheet(
            _theme.build_header_label_stylesheet(self._active_colors)
        )
        val_lab.setFixedWidth(90)
        _register_info(val_lab, "val_label")

        if label_text.startswith("From"):
            self._lab_val1 = val_lab
        else:
            self._lab_val2 = val_lab
        row.addWidget(val_lab)
        return row

    def _make_unit_row(self, slot: int):
        """Create the order label + unit combobox row for a given slot (1=from, 2=to)."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING_ROW)

        order_lab = _OrderLabel(
            on_change=lambda: self._unit_converter(1),
        )
        # Apply current active theme immediately (overrides the default light)
        order_lab.restyle(self._active_colors)

        unit_cb = QComboBox()
        unit_cb.setEnabled(False)
        unit_cb.setStyleSheet(
            _theme.build_unit_combo_stylesheet(self._active_colors)
        )

        if slot == 1:
            self._order1 = order_lab
            self._cb_unit1 = unit_cb
        else:
            self._order2 = order_lab
            self._cb_unit2 = unit_cb

        _register_info(unit_cb, "unit_combo")

        row.addWidget(order_lab)
        row.addWidget(unit_cb, stretch=1)
        return row

    def _make_entry_row(self, slot: int):
        """Create the numeric entry + sweep label row for a given slot."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING_ROW)

        sweep = _SweepLabel()
        sweep.restyle(self._active_colors)

        entry = _NumEntry(
            sweep_label=sweep,
            on_change=self._unit_converter,
            slot=slot,
        )
        entry.restyle(self._active_colors)

        if slot == 1:
            self._sweep1 = sweep
            self._entry1 = entry
        else:
            self._sweep2 = sweep
            self._entry2 = entry

        # sweep_label tooltip is set in _SweepLabel.__init__ via register_info.
        # No additional call needed here.

        row.addWidget(entry, stretch=1)
        row.addWidget(sweep)
        return row

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._cb_magnitude.currentTextChanged.connect(self._on_magnitude_changed)
        self._cb_unit1.currentTextChanged.connect(lambda _: self._unit_converter(1))
        self._cb_unit2.currentTextChanged.connect(lambda _: self._unit_converter(1))
        self._entry1.textEdited.connect(lambda _: self._unit_converter(1))
        self._entry2.textEdited.connect(lambda _: self._unit_converter(2))
        self._setup_tab_order()

    def _setup_tab_order(self) -> None:
        """
        Set the logical tab order for the main conversion flow (SPEC-22).

        Order: magnitude → unit1 → order1 → entry1 → entry2 → unit2 → order2.
        This ensures keyboard-only users can navigate the conversion inputs in
        a top-to-bottom, left-to-right sequence without extra Tab presses.
        """
        QWidget.setTabOrder(self._cb_magnitude, self._cb_unit1)
        QWidget.setTabOrder(self._cb_unit1, self._order1)
        QWidget.setTabOrder(self._order1, self._entry1)
        QWidget.setTabOrder(self._entry1, self._entry2)
        QWidget.setTabOrder(self._entry2, self._cb_unit2)
        QWidget.setTabOrder(self._cb_unit2, self._order2)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        # Return/Enter — trigger conversion
        sc_enter = QShortcut(QKeySequence(Qt.Key_Return), self)
        sc_enter.activated.connect(lambda: self._unit_converter())
        sc_enter2 = QShortcut(QKeySequence(Qt.Key_Enter), self)
        sc_enter2.activated.connect(lambda: self._unit_converter())

        # Ctrl+Q — standard Qt quit shortcut (replaces the Ctrl_R binding;
        # platform-neutral and always discoverable in the context menu as "Exit").
        sc_quit = QShortcut(QKeySequence("Ctrl+Q"), self)
        sc_quit.activated.connect(self._exit)

    # ------------------------------------------------------------------
    # Context menu (right-click)
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        settings_action = menu.addAction("Settings...")
        menu.addSeparator()
        history_action = menu.addAction("History / Favorites...")
        add_unit_action = menu.addAction("Add Custom Unit...")
        menu.addSeparator()
        about_action = menu.addAction("About...")
        exit_action = menu.addAction("Exit")
        action = menu.exec(event.globalPos())
        if action == settings_action:
            self._show_settings()
        elif action == history_action:
            self._show_history()
        elif action == add_unit_action:
            self._show_add_unit()
        elif action == about_action:
            self._show_about()
        elif action == exit_action:
            self._exit()

    def _show_settings(self) -> None:
        """Open the Settings dialog (TASK 2)."""
        dlg = _SettingsDialog(
            current_colors=self._active_colors,
            current_theme_name=self._active_theme_name,
            parent=self,
        )
        dlg.exec()
        # If the user clicked Ok, _on_ok already applied + persisted; if Cancel
        # or Apply was used, the live state is already updated via _apply_theme_colors.

    def _show_history(self) -> None:
        """Open the history/favorites dialog (UC-I07)."""
        dlg = _HistoryDialog(self, colors=self._active_colors)
        if dlg.exec() == QDialog.Accepted:
            entry = dlg.selected_entry()
            if entry is not None:
                self._apply_history_entry(entry)

    def _apply_history_entry(self, entry: HistoryEntry) -> None:
        """Re-populate the converter inputs from a history entry."""
        magnitude = entry.magnitude
        if magnitude not in self._magnitude_names:
            return
        idx = self._cb_magnitude.findText(magnitude)
        if idx >= 0:
            self._cb_magnitude.setCurrentIndex(idx)
        # Set units
        idx1 = self._cb_unit1.findText(entry.from_unit)
        if idx1 >= 0:
            self._cb_unit1.setCurrentIndex(idx1)
        idx2 = self._cb_unit2.findText(entry.to_unit)
        if idx2 >= 0:
            self._cb_unit2.setCurrentIndex(idx2)
        # Set value
        self._entry1.setText(str(entry.value))
        self._unit_converter(1)

    def _show_add_unit(self) -> None:
        """Open the add-custom-unit dialog (UC-I03 GUI)."""
        mag_names = [m for m in self._magnitude_names if m != "*Select magnitude*"]
        dlg = _AddUnitDialog(mag_names, self, colors=self._active_colors)
        if dlg.exec() == QDialog.Accepted:
            # Reload the database so the new unit appears
            _core.reload_database()
            QMessageBox.information(
                self,
                "Custom Unit Added",
                "Custom unit added successfully.\n"
                "Please re-select the magnitude to see the new unit.",
            )

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "About U Converter",
            f"Author: {__author__}\n"
            f"Version: {__version__}\n"
            f"License: {__license__}",
        )

    def _exit(self) -> None:
        """Clean Qt teardown — no cargo-cult del/gc dance."""
        QApplication.quit()

    # ------------------------------------------------------------------
    # Magnitude selection
    # ------------------------------------------------------------------

    def _on_magnitude_changed(self, text: str) -> None:
        if text == "*Select magnitude*":
            self._cb_unit1.clear()
            self._cb_unit1.setEnabled(False)
            self._cb_unit2.clear()
            self._cb_unit2.setEnabled(False)
            self._entry1.setEnabled(False)
            self._entry1.setText("0.0")
            self._entry2.setEnabled(False)
            self._entry2.setText("0.0")
            self._lab_val1.setText("{:.1e}".format(0.0))
            self._lab_val2.setText("{:.1e}".format(0.0))
            self._val1 = self._val1_old = 0.0
            self._val2 = self._val2_old = 0.0
            return

        mag_idx = self._magnitude_names[text]
        units = list(self._magnitudes[mag_idx].keys())

        # Block signals while repopulating to avoid spurious conversions
        self._cb_unit1.blockSignals(True)
        self._cb_unit2.blockSignals(True)

        self._cb_unit1.clear()
        self._cb_unit1.addItems(units)
        self._cb_unit1.setCurrentIndex(0)
        self._cb_unit1.setEnabled(True)

        self._cb_unit2.clear()
        self._cb_unit2.addItems(units)
        # Default "To" unit is the second one (matching original line 222)
        self._cb_unit2.setCurrentIndex(min(1, len(units) - 1))
        self._cb_unit2.setEnabled(True)

        self._cb_unit1.blockSignals(False)
        self._cb_unit2.blockSignals(False)

        self._entry1.setEnabled(True)
        self._entry2.setEnabled(True)

        # Set the prefix table on the order labels
        if text == "Data":
            self._order1.set_order_list(self._order_iec_keys, self._order_iec_vals)
            self._order2.set_order_list(self._order_iec_keys, self._order_iec_vals)
        else:
            self._order1.set_order_list(self._order_si_keys, self._order_si_vals)
            self._order2.set_order_list(self._order_si_keys, self._order_si_vals)

        # Reset orders to "1"
        self._order1.setText("1")
        self._order2.setText("1")

        self._unit_converter(1)

    # ------------------------------------------------------------------
    # Core converter bridge
    # ------------------------------------------------------------------

    def _get_float(self, entry: QLineEdit, old_val: float) -> float:
        """Parse the text from an entry, falling back to old_val on error."""
        try:
            return float(entry.text())
        except (ValueError, TypeError):
            return old_val

    def _unit_converter(self, slot: int = 0) -> None:
        """
        Bidirectional conversion — mirrors the original ``unit_converter`` method.

        slot=1 : val1 changed (or explicit trigger) → recompute val2.
        slot=2 : val2 changed → recompute val1.
        slot=0 : Return key pressed — treat as slot=1.
        """
        magnitude = self._cb_magnitude.currentText()
        if magnitude == "*Select magnitude*":
            return

        v1 = self._get_float(self._entry1, self._val1_old)
        v2 = self._get_float(self._entry2, self._val2_old)

        order_from = self._order1.text()
        order_to = self._order2.text()

        order_table = _core.DICT_ORDER_IEC if magnitude == "Data" else _core.DICT_ORDER_SI
        base = 1024 if magnitude == "Data" else 10

        if v1 != self._val1_old or slot == 1:
            # Clamp (mirrors original lines 308-313)
            if v1 < 0 or v1 == math.inf:
                v1 = 0.0
            self._val1 = v1
            self._val1_old = v1

            # Update scientific notation label
            order_exp1 = order_table.get(order_from, 0)
            self._lab_val1.setText("{:.1e}".format(v1 * base ** order_exp1))

            # Delegate to core
            try:
                result = _core.convert(
                    magnitude, v1,
                    self._cb_unit1.currentText(),
                    self._cb_unit2.currentText(),
                    from_order=order_from,
                    to_order=order_to,
                )
            except ValueError as exc:
                logger.error(
                    "Conversion error (slot 1): magnitude=%r from=%r to=%r: %s",
                    magnitude,
                    self._cb_unit1.currentText(),
                    self._cb_unit2.currentText(),
                    exc,
                )
                self._lab_val2.setText("error")
                return

            self._val2 = result
            self._val2_old = result

            self._entry2.blockSignals(True)
            self._entry2.setText(
                _format_result(result, self._sweep2.text())
            )
            self._entry2.blockSignals(False)

            order_exp2 = order_table.get(order_to, 0)
            self._lab_val2.setText("{:.1e}".format(result * base ** order_exp2))

            # Record to history (UC-I07) — silently ignore errors so history
            # never disrupts conversion.
            try:
                _record_history(
                    magnitude, v1,
                    self._cb_unit1.currentText(),
                    self._cb_unit2.currentText(),
                    result,
                    from_order=order_from,
                    to_order=order_to,
                )
            except Exception:
                pass

        elif v2 != self._val2_old or slot == 2:
            # Clamp
            if v2 < 0 or v2 == math.inf:
                v2 = 0.0
            self._val2 = v2
            self._val2_old = v2

            # Update scientific notation label
            order_exp2 = order_table.get(order_to, 0)
            self._lab_val2.setText("{:.1e}".format(v2 * base ** order_exp2))

            # Reverse conversion: from slot2 unit back to slot1 unit
            try:
                result = _core.convert(
                    magnitude, v2,
                    self._cb_unit2.currentText(),
                    self._cb_unit1.currentText(),
                    from_order=order_to,
                    to_order=order_from,
                )
            except ValueError as exc:
                logger.error(
                    "Conversion error (slot 2): magnitude=%r from=%r to=%r: %s",
                    magnitude,
                    self._cb_unit2.currentText(),
                    self._cb_unit1.currentText(),
                    exc,
                )
                self._lab_val1.setText("error")
                return

            self._val1 = result
            self._val1_old = result

            self._entry1.blockSignals(True)
            self._entry1.setText(
                _format_result(result, self._sweep1.text())
            )
            self._entry1.blockSignals(False)

            order_exp1 = order_table.get(order_from, 0)
            self._lab_val1.setText("{:.1e}".format(result * base ** order_exp1))
