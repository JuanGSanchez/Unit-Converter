"""
unit_converter.gui.geometry
============================
Qt-free helpers for dialog geometry defaults and layout spacing constants.

This module contains NO PySide6 imports so every public symbol can be
unit-tested without a running QApplication.  Callers (``main_window.py``)
import the Qt-free helpers here and pass Qt objects as arguments only where
needed (``center_dialog_on_parent`` receives a QDialog, but the numeric
computation is pure Python).

Public API
----------
``PHI``
    The golden ratio (phi ≈ 1.6180339887).

``golden_ratio_size(target_width: int) -> tuple[int, int]``
    Return ``(width, height)`` for a portrait window whose width equals
    *target_width* and whose height = round(width * PHI).
    Width:height approximates phi in portrait orientation.

``dialog_default_size(dialog_type: str) -> tuple[int, int]``
    Return the canonical ``(width, height)`` for a named dialog type.
    Keys: ``"history"``, ``"add_unit"``, ``"settings"``.

``center_dialog_on_parent(dialog, default_w: int, default_h: int) -> None``
    Resize *dialog* to ``(default_w, default_h)`` and center it on its
    parent widget (or on the primary screen if no parent).

Layout spacing constants (all ~25% larger than the pre-refactor baseline):

``MARGIN_H``       Left/right content margin (px).
``MARGIN_V``       Top/bottom content margin (px).
``SPACING_MAIN``   Inter-widget spacing in the main vertical layout (px).
``SPACING_ROW``    Inter-widget spacing in horizontal rows (px).
``MARGIN_HEADER_TOP``  Top margin for the From:/To: header rows (px).
``SPACING_FORM_H`` QFormLayout horizontal spacing (px).
``SPACING_FORM_V`` QFormLayout vertical spacing (px).
"""

from __future__ import annotations

__all__ = [
    "PHI",
    "golden_ratio_size",
    "dialog_default_size",
    "center_dialog_on_parent",
    # spacing / margin constants
    "MARGIN_H",
    "MARGIN_V",
    "SPACING_MAIN",
    "SPACING_ROW",
    "MARGIN_HEADER_TOP",
    "SPACING_FORM_H",
    "SPACING_FORM_V",
]

# ---------------------------------------------------------------------------
# Golden ratio
# ---------------------------------------------------------------------------

#: The golden ratio φ ≈ 1.6180339887.
PHI: float = 1.6180339887


def golden_ratio_size(target_width: int) -> tuple[int, int]:
    """Return ``(width, height)`` for a portrait window with golden-ratio proportions.

    The height is computed as ``round(target_width * PHI)``.  The resulting
    width:height ratio approximates ``1 / PHI ≈ 0.618`` (portrait).

    Parameters
    ----------
    target_width:
        Desired window width in pixels.  Must be a positive integer.

    Returns
    -------
    tuple[int, int]
        ``(width, height)`` both as int.

    Examples
    --------
    >>> golden_ratio_size(260)
    (260, 421)
    """
    if target_width <= 0:
        raise ValueError(f"target_width must be positive, got {target_width!r}")
    height = round(target_width * PHI)
    return (target_width, height)


# ---------------------------------------------------------------------------
# Dialog canonical sizes
# ---------------------------------------------------------------------------

# Canonical default sizes for each named dialog, expressed as (w, h).
# These are used by center_dialog_on_parent to set a consistent geometry.
_DIALOG_DEFAULTS: dict[str, tuple[int, int]] = {
    "history":  (430, 355),  # _HistoryDialog — slightly wider + taller than old 420×340
    "add_unit": (315, 190),  # _AddUnitDialog — slightly larger than old 300×180
    "settings": (450, 500),  # _SettingsDialog — slightly larger than old 430×480
}


def dialog_default_size(dialog_type: str) -> tuple[int, int]:
    """Return the canonical ``(width, height)`` for a named dialog type.

    Parameters
    ----------
    dialog_type:
        One of ``"history"``, ``"add_unit"``, ``"settings"``.

    Returns
    -------
    tuple[int, int]
        ``(width, height)`` in pixels.

    Raises
    ------
    KeyError
        If *dialog_type* is not a recognised key.
    """
    return _DIALOG_DEFAULTS[dialog_type]


# ---------------------------------------------------------------------------
# Geometry-defaulting helper
# ---------------------------------------------------------------------------

def center_dialog_on_parent(dialog: object, default_w: int, default_h: int) -> None:
    """Resize *dialog* to ``(default_w, default_h)`` and center it on its parent.

    The parent is obtained via ``dialog.parent()``.  If the parent is ``None``,
    the dialog is centered on the primary screen via
    ``QApplication.primaryScreen().geometry()``.

    This function imports PySide6 locally so the module stays importable
    without Qt, keeping all pure-Python helpers testable.

    Parameters
    ----------
    dialog:
        Any QDialog (or QWidget) instance with a ``resize()`` and ``move()``
        method, and a ``parent()`` method.
    default_w, default_h:
        Default size in pixels.
    """
    # Local Qt import so this module's top-level stays Qt-free.
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    dialog.resize(default_w, default_h)  # type: ignore[attr-defined]

    parent = dialog.parent()  # type: ignore[attr-defined]
    if parent is not None:
        parent_geom = parent.geometry()
        # Map top-left to global coords
        global_top_left = parent.mapToGlobal(parent_geom.topLeft())
        # Use frameGeometry width/height of parent (already global)
        px = parent.frameGeometry().x()
        py = parent.frameGeometry().y()
        pw = parent.frameGeometry().width()
        ph = parent.frameGeometry().height()
        x = px + (pw - default_w) // 2
        y = py + (ph - default_h) // 2
    else:
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - default_w) // 2
        y = (screen.height() - default_h) // 2

    dialog.move(x, y)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Layout spacing / margin constants (~25% larger than the pre-refactor baseline)
# ---------------------------------------------------------------------------
# Pre-refactor baselines (for reference, not used at runtime):
#   MARGIN_H = 10, MARGIN_V = 7
#   SPACING_MAIN = 5, SPACING_ROW = 6, MARGIN_HEADER_TOP = 5
#   SPACING_FORM_H = 8, SPACING_FORM_V = 6

#: Left/right content margin for the main window layout (px).
MARGIN_H: int = 12  # was 10 → +20% (nearest even; 10*1.25=12.5→12)

#: Top/bottom content margin for the main window layout (px).
MARGIN_V: int = 9  # was 7 → +29% (7*1.25=8.75→9)

#: Inter-widget spacing in the main vertical layout (px).
SPACING_MAIN: int = 6  # was 5 → +20% (5*1.25=6.25→6)

#: Inter-widget spacing in horizontal rows (unit row, entry row) (px).
SPACING_ROW: int = 8  # was 6 → +33% (6*1.25=7.5→8)

#: Top margin for the From:/To: header row (px).
MARGIN_HEADER_TOP: int = 6  # was 5 → +20% (5*1.25=6.25→6)

#: QFormLayout horizontal spacing (px).
SPACING_FORM_H: int = 10  # was 8 → +25% (8*1.25=10)

#: QFormLayout vertical spacing (px).
SPACING_FORM_V: int = 8  # was 6 → +33% (6*1.25=7.5→8)
