"""
unit_converter.gui.theme
=========================
Centralized colour/stylesheet definitions for the U Converter GUI.

Color-theory grounding
-----------------------
Both themes are built on a **monochromatic base** with a **complementary
accent** following standard colour-wheel principles:

Light ("Clear") theme
    Base: cool neutral grey scale (HSL ~210°, low saturation).  Inspired by
    Chrome and VS Code Light.
    - Window/control background: #F0F0F0 (near-white grey, equivalent to
      Windows 11 HWND default) — avoids harsh pure-white eye strain.
    - Title/header strips: #D0D8E8 (slightly blue-tinted, 210° hue) for
      visual grouping.
    - Entry fields: #FFFFFF (pure white so entered text pops visually).
    - Accent (FG title / interactive): #1E5AA8 (medium blue, WCAG AA contrast
      ratio ≈ 5.5:1 against #D0D8E8 strip background).
    - Body text: #1A1A1A (near-black — contrast ratio ≈ 12:1 against #F0F0F0).
    - Combo/selection background: #E8EDF5 (very light blue-grey, same hue family).
    - Border: #A0A8B8 (muted blue-grey to echo the accent without competing).

Dark theme
    Base: desaturated dark grey scale (HSL ~220°, very low saturation).
    Inspired by VS Code Dark+ and Chrome DevTools dark.
    - Window background: #1E1E2E (VS Code Dark+ sidebar shade).
    - Title/header strips: #2D3250 (navy accent hue — complementary to the
      warm amber accent below on the 220° side of the wheel).
    - Entry fields: #252540 (slightly lighter than window bg, readable).
    - Accent (FG title): #C8A95C (warm amber — complementary to the 220° blue
      base, WCAG AA ≈ 4.7:1 against #2D3250).
    - Body text: #E8E8F0 (near-white with a faint blue cast).
    - Combo/selection background: #2A2A40.
    - Border: #4A4A6A.

WCAG AA requires contrast ratio ≥ 4.5:1 for normal text.  Both themes meet or
exceed this for the primary text-on-background pairs listed above.

Widget-type colour keys
------------------------
Every key in a Theme.colors dict corresponds to exactly one semantic role:

  "bg_main"      — main window / outer frame background
  "bg_title"     — title/header label strip background
  "bg_entry"     — numeric entry field background
  "bg_sweep"     — sweep label background (same as entry in current design)
  "bg_combo"     — ComboBox background
  "bg_dialog"    — dialog background (settings, history)
  "fg_title"     — title/header foreground (accent colour)
  "fg_main"      — body label foreground
  "fg_entry"     — entry text foreground
  "border_main"  — general control border
  "border_heavy" — thicker/ridge border (order label, entry)

Public API
----------
``LIGHT_THEME`` / ``DARK_THEME``
    Pre-built :class:`Theme` instances.

``BUILT_IN_THEMES``
    ``dict[str, Theme]`` mapping display name → instance.

``Theme``
    Dataclass holding a display name and a ``colors: dict[str, str]`` mapping.

``apply_widget_colors(colors: dict[str, str]) -> None``
    Apply a merged colour mapping to all live widgets in the running
    QApplication.  Call after building the UI or after a theme/color change.

``build_main_window_stylesheet(colors: dict[str, str]) -> str``
    Return the full QSS stylesheet string for the main window frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # PySide6 imports only inside functions to keep top-level importable


# ---------------------------------------------------------------------------
# Theme dataclass
# ---------------------------------------------------------------------------

@dataclass
class Theme:
    """
    A named colour palette for the GUI.

    Attributes
    ----------
    name:
        Human-readable display name (``"Light"`` or ``"Dark"``).
    colors:
        Mapping from semantic role key to ``#RRGGBB`` hex colour string.
    """
    name: str
    colors: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Built-in palettes
# ---------------------------------------------------------------------------

#: Light ("Clear") theme — monochromatic cool-grey base + blue accent.
LIGHT_THEME = Theme(
    name="Light",
    colors={
        "bg_main":      "#F0F0F0",  # near-white grey window background
        "bg_title":     "#D0D8E8",  # light blue-grey header strip
        "bg_entry":     "#FFFFFF",  # pure white entry fields
        "bg_sweep":     "#FFFFFF",  # sweep label background
        "bg_combo":     "#E8EDF5",  # very light blue-grey combos
        "bg_dialog":    "#F5F5F8",  # dialog frame background
        "fg_title":     "#1E5AA8",  # medium blue accent — WCAG AA on bg_title
        "fg_main":      "#1A1A1A",  # near-black body text
        "fg_entry":     "#1A1A1A",  # entry text colour
        "border_main":  "#A0A8B8",  # muted blue-grey border
        "border_heavy": "#808898",  # slightly darker ridge/heavy border
    },
)

#: Dark theme — desaturated dark blue-grey base + warm amber accent.
DARK_THEME = Theme(
    name="Dark",
    colors={
        "bg_main":      "#1E1E2E",  # VS Code Dark+ inspired window background
        "bg_title":     "#2D3250",  # navy-blue header strip
        "bg_entry":     "#252540",  # dark blue-grey entry fields
        "bg_sweep":     "#252540",  # sweep label background
        "bg_combo":     "#2A2A40",  # combo box background
        "bg_dialog":    "#252538",  # dialog frame background
        "fg_title":     "#C8A95C",  # warm amber accent — complementary to blue
        "fg_main":      "#E8E8F0",  # near-white body text
        "fg_entry":     "#E8E8F0",  # entry text colour
        "border_main":  "#4A4A6A",  # muted dark border
        "border_heavy": "#5A5A7A",  # slightly lighter ridge border
    },
)

#: All built-in themes indexed by display name.
BUILT_IN_THEMES: dict[str, Theme] = {
    LIGHT_THEME.name: LIGHT_THEME,
    DARK_THEME.name:  DARK_THEME,
}

# Default theme name used on first launch.
DEFAULT_THEME_NAME = LIGHT_THEME.name


# ---------------------------------------------------------------------------
# Stylesheet builders
# ---------------------------------------------------------------------------

def build_main_window_stylesheet(colors: dict[str, str]) -> str:
    """
    Return the top-level QSS stylesheet for the main window background.

    Parameters
    ----------
    colors:
        A theme colour mapping (from :attr:`Theme.colors`, possibly
        merged with user overrides via
        :func:`theme_persist.merge_theme_colors`).

    Returns
    -------
    str
        A ``QWidget { background-color: ... }`` stylesheet string.
    """
    return f"background-color: {colors['bg_main']};"


def build_magnitude_label_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for the 'Magnitude' header label."""
    return (
        f"background-color: {colors['bg_title']}; "
        f"color: {colors['fg_title']}; "
        "font-family: Arial; font-size: 12pt; font-weight: bold; "
        f"border: 2px solid {colors['border_main']}; padding: 5px;"
    )


def build_combo_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for magnitude/unit QComboBox widgets."""
    return (
        f"background-color: {colors['bg_combo']}; "
        f"color: {colors['fg_main']}; "
        "font-family: TimesNewRoman, 'Times New Roman'; font-size: 12pt; "
        "padding: 4px;"
    )


def build_unit_combo_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for the smaller per-slot unit QComboBox widgets."""
    return (
        f"background-color: {colors['bg_combo']}; "
        f"color: {colors['fg_main']}; "
        "font-family: TimesNewRoman, 'Times New Roman'; font-size: 11pt; "
        "padding: 3px;"
    )


def build_header_label_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for 'From:' / 'To:' direction labels and sci-notation value labels."""
    return (
        f"background-color: {colors['bg_main']}; "
        f"color: {colors['fg_main']}; "
        "font-family: Verdana; font-size: 12pt; "
        f"border: 2px solid {colors['border_main']}; padding: 5px;"
    )


def build_order_label_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for _OrderLabel (scrollable prefix multiplier)."""
    return (
        f"border: 2px ridge {colors['border_heavy']}; "
        "padding: 4px 6px; "
        "font-family: Arial; font-size: 11pt; "
        f"background-color: {colors['bg_main']}; "
        f"color: {colors['fg_main']}; "
        "min-width: 24px; max-width: 32px;"
    )


def build_sweep_label_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for _SweepLabel (digit-position sweep control)."""
    return (
        f"background-color: {colors['bg_sweep']}; "
        f"color: {colors['fg_entry']}; "
        f"border: 1px groove {colors['border_main']}; "
        "padding: 4px 6px; "
        "font-family: Verdana; font-size: 11pt; "
        "min-width: 24px; max-width: 32px;"
    )


def build_entry_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for _NumEntry (numeric input QLineEdit)."""
    return (
        f"background-color: {colors['bg_entry']}; "
        f"color: {colors['fg_entry']}; "
        "font-family: Verdana; font-size: 11pt; "
        f"border: 3px sunken {colors['border_heavy']}; "
        "padding: 2px 4px;"
    )


def build_dialog_stylesheet(colors: dict[str, str]) -> str:
    """Return the QSS for dialog windows (History, Settings, etc.)."""
    return (
        f"background-color: {colors['bg_dialog']}; "
        f"color: {colors['fg_main']};"
    )


# ---------------------------------------------------------------------------
# Runtime restyle helper
# ---------------------------------------------------------------------------

def apply_colors_to_main_window(win: "MainWindow", colors: dict[str, str]) -> None:  # type: ignore[name-defined]
    """
    Restyle all widgets in *win* using the supplied colour mapping.

    This function is called when the user switches themes or edits individual
    widget colours in the Settings dialog.  It must be called on the GUI
    thread (same restriction as all Qt widget operations).

    Parameters
    ----------
    win:
        The :class:`MainWindow` instance whose widgets are to be restyled.
    colors:
        Fully-merged colour mapping (built-in theme + user overrides).
    """
    # Store on the window so widgets spawned later can query it
    win._active_colors = colors

    # Main window background
    win.setStyleSheet(build_main_window_stylesheet(colors))

    # Magnitude label + combo
    win._lab_mag.setStyleSheet(build_magnitude_label_stylesheet(colors))
    win._cb_magnitude.setStyleSheet(build_combo_stylesheet(colors))

    # Header rows (From:/To: labels + sci-notation value labels)
    for lab in (win._lab_from, win._lab_to):
        lab.setStyleSheet(build_header_label_stylesheet(colors))
    for val_lab in (win._lab_val1, win._lab_val2):
        val_lab.setStyleSheet(build_header_label_stylesheet(colors))

    # Order labels
    for order_lab in (win._order1, win._order2):
        order_lab.setStyleSheet(build_order_label_stylesheet(colors))

    # Sweep labels
    for sweep in (win._sweep1, win._sweep2):
        sweep.setStyleSheet(build_sweep_label_stylesheet(colors))

    # Numeric entries
    for entry in (win._entry1, win._entry2):
        entry.setStyleSheet(build_entry_stylesheet(colors))

    # Unit combos
    for cb in (win._cb_unit1, win._cb_unit2):
        cb.setStyleSheet(build_unit_combo_stylesheet(colors))
