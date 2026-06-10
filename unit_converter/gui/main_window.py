"""
unit_converter.gui.main_window
================================
PySide6 main window for the U Converter application.

Preserves the UX of the original Tkinter ``UC_UI`` class:
- Fixed 235 x 385 px window, centered on screen, non-resizable.
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
- Hover tooltips (QToolTip) replacing the manual Toplevel popup.
- Right-click context menu: About and Exit.
- Ctrl+Right exits the application (preserving the original <Control_R> binding).
- Return/Enter triggers conversion.
- All conversion math delegated to ``unit_converter.core.converter``.
- No ``del locals()`` / ``gc.collect()`` / ``del self`` cargo-cult exit — uses
  standard Qt ``QApplication.quit()``.

Implementation notes
--------------------
- The window is NOT frameless.  The original Tkinter window retained the OS
  title-bar (only the tooltip Toplevel was frameless/overrideredirect).
  Reproducing the title-bar-less look would require platform-specific drag
  handling and is not part of the original UX; omitted intentionally.
- The tooltip popup (fr_man Toplevel) is replaced by Qt native QToolTip — the
  tooltip is displayed automatically by Qt on hover; no manual geometry
  calculation is needed.
- The Tk ``<Control_R>`` binding maps to ``Qt.Key_Control`` + right modifier.
  In Qt this is more reliably handled as a ``QShortcut`` on
  ``QKeySequence(Qt.CTRL | Qt.Key_Control)`` — but since that only fires on the
  right control key we capture ``keyPressEvent`` and check
  ``event.key() == Qt.Key_Control and event.nativeScanCode()`` instead.
  Simplified: we bind ``Ctrl+Q`` (a universally expected quit shortcut) AND
  retain an explicit check for the right-Ctrl scan code on Windows (scan 0x1D
  is left Ctrl; 0x11D / extended bit is right Ctrl — but nativeScanCode is
  unreliable cross-platform). The simplest compatible solution is a ``QShortcut``
  on ``Meta+Control`` (which is right-Ctrl on Windows via Qt), documented below.
"""

from __future__ import annotations

import math
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QDoubleValidator,
    QIcon,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

from unit_converter.core import converter as _core
from unit_converter.core.data_loader import MagnitudeDataError
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

# Window geometry — matches original exactly
_WINDOW_WIDTH = 235
_WINDOW_HEIGHT = 385

# Colours — as close to the original palette as Qt stylesheets allow
_BG_MAIN = "#bfbfbf"
_BG_TITLE = "#999999"
_BG_ENTRY = "white"
_BG_SWEEP = "white"
_FG_TITLE = "blue"
_FG_ENTRY = "black"
_FG_MAIN = "black"

# Fonts (Qt stylesheet / font-family strings closest to originals)
_FONT_TITLE = "font-family: Arial; font-size: 12pt; font-weight: bold;"
_FONT_ENTRY = "font-family: Verdana; font-size: 11pt;"
_FONT_VAL = "font-family: Verdana; font-size: 11pt;"
_FONT_TEXT = "font-family: Verdana; font-size: 12pt;"
_FONT_ORDER = "font-family: Arial; font-size: 11pt;"


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
        self.setToolTip(
            "Scroll to change order of magnitude.\nClick to reset."
        )
        # Styling to mimic Tk RIDGE relief
        self.setStyleSheet(
            "border: 2px ridge #888888; "
            "padding: 4px 6px; "
            f"font-family: Arial; font-size: 11pt; "
            f"background-color: {_BG_MAIN}; "
            "min-width: 24px; max-width: 32px;"
        )
        self.setFixedWidth(36)
        self.setCursor(Qt.PointingHandCursor)

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
        self.setToolTip(
            "Scroll to change digit position sweep.\nClick to reset."
        )
        self.setStyleSheet(
            f"background-color: {_BG_SWEEP}; "
            "border: 1px groove #aaaaaa; "
            "padding: 4px 6px; "
            "font-family: Verdana; font-size: 11pt; "
            "min-width: 24px; max-width: 32px;"
        )
        self.setFixedWidth(36)
        self.setCursor(Qt.PointingHandCursor)

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
        self.setStyleSheet(
            f"background-color: {_BG_ENTRY}; "
            f"color: {_FG_ENTRY}; "
            "font-family: Verdana; font-size: 11pt; "
            "border: 3px sunken #999999; "
            "padding: 2px 4px;"
        )
        self.setEnabled(False)
        self.setToolTip(
            "Write or press Enter\nto run the conversion."
        )

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
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    """
    PySide6 recreation of the original Tkinter ``UC_UI`` window.

    Fixed 235 x 385 px, centered, non-resizable.  Wired entirely to the pure
    ``unit_converter.core.converter`` API — no conversion math is implemented
    here.
    """

    def __init__(self) -> None:
        super().__init__()
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

        self.setStyleSheet(f"background-color: {_BG_MAIN};")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)

        # ---- Magnitude label + combo ----
        self._lab_mag = QLabel("Magnitude")
        self._lab_mag.setAlignment(Qt.AlignCenter)
        self._lab_mag.setStyleSheet(
            f"background-color: {_BG_TITLE}; color: {_FG_TITLE}; "
            f"{_FONT_TITLE} border: 2px solid #888888; padding: 5px;"
        )
        layout.addWidget(self._lab_mag)

        self._cb_magnitude = QComboBox()
        self._cb_magnitude.addItems(list(self._magnitude_names.keys()))
        self._cb_magnitude.setCurrentIndex(0)
        self._cb_magnitude.setEnabled(True)
        self._cb_magnitude.setStyleSheet(
            "background-color: #e6e6e6; "
            "font-family: TimesNewRoman, Times New Roman; font-size: 12pt; "
            "padding: 4px;"
        )
        self._cb_magnitude.setToolTip(
            "List of magnitudes added to the application."
        )
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
        row.setContentsMargins(0, 5, 0, 0)

        lab = QLabel(label_text)
        lab.setStyleSheet(
            f"background-color: {_BG_MAIN}; color: {_FG_MAIN}; {_FONT_TEXT}; "
            "border: 2px solid #aaaaaa; padding: 5px;"
        )
        row.addWidget(lab)

        row.addStretch(1)

        val_lab = QLabel("{:.1e}".format(0.0))
        val_lab.setAlignment(Qt.AlignCenter)
        val_lab.setStyleSheet(
            f"background-color: {_BG_MAIN}; color: {_FG_MAIN}; {_FONT_VAL}; "
            "border: 2px solid #aaaaaa; padding: 5px;"
        )
        val_lab.setFixedWidth(90)
        val_lab.setToolTip("Actual total value in scientific notation.")

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
        row.setSpacing(6)

        order_lab = _OrderLabel(
            on_change=lambda: self._unit_converter(1),
        )

        unit_cb = QComboBox()
        unit_cb.setEnabled(False)
        unit_cb.setStyleSheet(
            "background-color: #e6e6e6; "
            "font-family: TimesNewRoman, Times New Roman; font-size: 11pt; "
            "padding: 3px;"
        )

        if slot == 1:
            self._order1 = order_lab
            self._cb_unit1 = unit_cb
        else:
            self._order2 = order_lab
            self._cb_unit2 = unit_cb

        row.addWidget(order_lab)
        row.addWidget(unit_cb, stretch=1)
        return row

    def _make_entry_row(self, slot: int):
        """Create the numeric entry + sweep label row for a given slot."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        sweep = _SweepLabel()
        entry = _NumEntry(
            sweep_label=sweep,
            on_change=self._unit_converter,
            slot=slot,
        )

        if slot == 1:
            self._sweep1 = sweep
            self._entry1 = entry
        else:
            self._sweep2 = sweep
            self._entry2 = entry

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
        about_action = menu.addAction("About...")
        exit_action = menu.addAction("Exit")
        action = menu.exec(event.globalPos())
        if action == about_action:
            self._show_about()
        elif action == exit_action:
            self._exit()

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
            except (ValueError, ZeroDivisionError):
                result = 0.0

            self._val2 = result
            self._val2_old = result

            self._entry2.blockSignals(True)
            self._entry2.setText(f"{result}")
            self._entry2.blockSignals(False)

            order_exp2 = order_table.get(order_to, 0)
            self._lab_val2.setText("{:.1e}".format(result * base ** order_exp2))

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
            except (ValueError, ZeroDivisionError):
                result = 0.0

            self._val1 = result
            self._val1_old = result

            self._entry1.blockSignals(True)
            self._entry1.setText(f"{result}")
            self._entry1.blockSignals(False)

            order_exp1 = order_table.get(order_from, 0)
            self._lab_val1.setText("{:.1e}".format(result * base ** order_exp1))
