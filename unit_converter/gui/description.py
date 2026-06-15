"""
unit_converter.gui.description
================================
Centralized, no-delay, reusable description widget for the U Converter GUI.

Problem solved
--------------
Qt's native ``QToolTip`` (``setToolTip``) shows a text popup with a platform
default delay of ~700 ms before it appears.  This module provides a
:class:`DescriptionLabel` that overlays an immediate, styled ``QLabel`` near
the target widget with configurable (default: zero) show delay, auto-sized to
fit its text, and theme-aware colors — making descriptions feel instant and
consistent across the whole application.

How it works
------------
:class:`DescriptionLabel` is a frameless, no-interaction ``QLabel`` that lives
as a top-level window (``Qt.ToolTip`` window flag keeps it visually consistent
with the app) parented to the target widget's top-level window.  It installs
itself as a ``QObject`` event filter on the *target* widget:

- ``QEvent.Enter``  → start a ``QTimer`` (default 0 ms) then ``show()``
- ``QEvent.Leave``  → ``hide()`` immediately
- ``QEvent.Hide``   → ``hide()`` immediately (target hidden, so must hide too)

The label is positioned below-left of the target, falling back to above it if
there is no room below, and it auto-resizes to fit the wrapped text.

Public API
----------
``DescriptionLabel(text, target, *, show_delay_ms=0, max_wrap_width=220,
                   colors=None, parent=None)``
    Construct the label and install it on *target*.  *colors* is a
    ``dict[str, str]`` from :mod:`unit_converter.gui.theme`; if omitted the
    ``LIGHT_THEME`` palette is used.

``DescriptionLabel.restyle(colors)``
    Apply a new color mapping after construction (called when the user changes
    theme in the Settings dialog).

``attach_description(target, text, *, show_delay_ms=0, max_wrap_width=220,
                     colors=None)``
    Convenience factory — create a :class:`DescriptionLabel` for *target* and
    return it.  The caller must keep the returned object alive (store it on
    ``self``) to prevent garbage collection from uninstalling the event filter.

Qt-freedom notes
----------------
This module **does** import PySide6 — it is a GUI widget module.  The helper
``attach_description`` is the only symbol called from ``main_window.py``.
Tests for the theme-color logic and the parameter extraction live in
``tests/test_description.py`` and are Qt-free (they test the pure-Python
helper ``_build_description_stylesheet`` directly without instantiating widgets).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from unit_converter.gui import theme as _theme


# ---------------------------------------------------------------------------
# Qt-free stylesheet builder (testable without Qt)
# ---------------------------------------------------------------------------

def build_description_stylesheet(colors: dict[str, str]) -> str:
    """
    Return the QSS stylesheet for a :class:`DescriptionLabel`.

    Parameters
    ----------
    colors:
        A merged theme colour mapping from :mod:`unit_converter.gui.theme`
        (keys ``"bg_title"``, ``"fg_main"``, ``"border_main"``).

    Returns
    -------
    str
        A QSS string suitable for ``QLabel.setStyleSheet()``.

    Notes
    -----
    This function is **Qt-free** — it is a pure string builder and can be
    exercised in tests without a ``QApplication``.
    """
    bg = colors.get("bg_title", "#D0D8E8")
    fg = colors.get("fg_main", "#1A1A1A")
    border = colors.get("border_main", "#A0A8B8")
    return (
        f"background-color: {bg}; "
        f"color: {fg}; "
        f"border: 1px solid {border}; "
        "border-radius: 3px; "
        "padding: 4px 8px; "
        "font-family: Verdana; "
        "font-size: 10pt;"
    )


# ---------------------------------------------------------------------------
# DescriptionLabel
# ---------------------------------------------------------------------------

class DescriptionLabel(QObject):
    """
    A no-delay, auto-sized, theme-aware description overlay for any widget.

    Parameters
    ----------
    text:
        The description to display.  Newlines are preserved.
    target:
        The widget this description is attached to.  An event filter is
        installed on it; hover-enter shows the label, hover-leave hides it.
    show_delay_ms:
        Milliseconds before the label appears after the cursor enters *target*.
        Defaults to ``0`` (immediate).
    max_wrap_width:
        Maximum pixel width of the description label before text wraps.
        Defaults to ``220``.
    colors:
        A ``dict[str, str]`` from :mod:`unit_converter.gui.theme` supplying the
        active palette.  Omit (or pass ``None``) to use
        :data:`~unit_converter.gui.theme.LIGHT_THEME`.
    parent:
        Optional QObject parent (not the visual parent — the label's visual
        parent is computed from *target*'s top-level window).
    """

    def __init__(
        self,
        text: str,
        target: QWidget,
        *,
        show_delay_ms: int = 0,
        max_wrap_width: int = 220,
        colors: Optional[dict[str, str]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._target = target
        self._show_delay_ms = max(0, show_delay_ms)
        self._max_wrap_width = max_wrap_width
        self._colors: dict[str, str] = colors if colors is not None else dict(_theme.LIGHT_THEME.colors)

        # Resolve the visual parent to the target's top-level window so the
        # label floats above everything in that window.
        top_level = target.window() if target.window() is not None else target
        self._label = QLabel(top_level)
        self._label.setWindowFlags(Qt.ToolTip | Qt.BypassGraphicsProxyWidget)  # type: ignore[attr-defined]
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # type: ignore[attr-defined]
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(max_wrap_width)
        self._label.setText(text)
        self._label.hide()
        self._apply_stylesheet()

        # Timer to introduce the configurable show delay
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._show_now)

        # Install event filter on the target
        target.installEventFilter(self)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def restyle(self, colors: dict[str, str]) -> None:
        """
        Apply *colors* to the overlay label (called on theme change).

        Parameters
        ----------
        colors:
            A fully-merged theme colour mapping from
            :func:`unit_converter.gui.theme_persist.merge_theme_colors`.
        """
        self._colors = colors
        self._apply_stylesheet()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_stylesheet(self) -> None:
        self._label.setStyleSheet(build_description_stylesheet(self._colors))

    def _show_now(self) -> None:
        """Position and show the label (called when the delay timer fires)."""
        if not self._target.isVisible():
            return
        self._label.adjustSize()
        pos = _compute_label_position(
            self._target, self._label, self._max_wrap_width
        )
        self._label.move(pos)
        self._label.raise_()
        self._label.show()

    # ------------------------------------------------------------------
    # QObject event filter
    # ------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self._target:
            if event.type() == QEvent.Enter:  # type: ignore[attr-defined]
                self._timer.stop()
                if self._show_delay_ms == 0:
                    self._show_now()
                else:
                    self._timer.start(self._show_delay_ms)
            elif event.type() in (QEvent.Leave, QEvent.Hide):  # type: ignore[attr-defined]
                self._timer.stop()
                self._label.hide()
        return False  # do not consume the event


# ---------------------------------------------------------------------------
# Position helper (Qt-free core logic, testable separately)
# ---------------------------------------------------------------------------

def _compute_label_position_offsets(
    target_width: int,
    target_height: int,
    label_width: int,
    label_height: int,
    target_global_x: int,
    target_global_y: int,
    screen_height: int,
) -> tuple[int, int]:
    """
    Compute (global_x, global_y) for the description label.

    Places the label below-left the target; falls back to above the target
    if there is insufficient room below.  This pure-Python function is the
    testable core of the positioning logic and has no Qt dependency.

    Parameters
    ----------
    target_width, target_height:
        Pixel size of the target widget.
    label_width, label_height:
        Pixel size of the description label after ``adjustSize()``.
    target_global_x, target_global_y:
        Global (screen) position of the top-left corner of the target widget.
    screen_height:
        Usable screen height in pixels.

    Returns
    -------
    tuple[int, int]
        ``(x, y)`` global coordinates for the label's top-left corner.
    """
    x = target_global_x
    y_below = target_global_y + target_height + 2
    y_above = target_global_y - label_height - 2

    if y_below + label_height <= screen_height:
        y = y_below
    else:
        y = max(0, y_above)

    return x, y


def _compute_label_position(
    target: QWidget,
    label: QLabel,
    max_wrap_width: int,
) -> "QPoint":
    """
    Compute the on-screen :class:`QPoint` for the description label.

    Delegates the pure arithmetic to :func:`_compute_label_position_offsets`
    and then maps the result to the label's parent coordinate system.

    Parameters
    ----------
    target:
        The widget the description is attached to.
    label:
        The :class:`QLabel` overlay (already ``adjustSize()``'d).
    max_wrap_width:
        Not used for positioning but kept for signature parity.

    Returns
    -------
    QPoint
        A point in *label*'s parent coordinate system.
    """
    from PySide6.QtWidgets import QApplication  # local import — Qt guard

    screen = QApplication.primaryScreen()
    screen_h = screen.availableGeometry().height() if screen else 1080

    tg = target.mapToGlobal(QPoint(0, 0))
    gx, gy = _compute_label_position_offsets(
        target_width=target.width(),
        target_height=target.height(),
        label_width=label.width(),
        label_height=label.height(),
        target_global_x=tg.x(),
        target_global_y=tg.y(),
        screen_height=screen_h,
    )

    # Map from global back to label parent's local coordinates
    parent_widget = label.parentWidget()
    if parent_widget is not None:
        local = parent_widget.mapFromGlobal(QPoint(gx, gy))
        return local
    return QPoint(gx, gy)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def attach_description(
    target: QWidget,
    text: str,
    *,
    show_delay_ms: int = 0,
    max_wrap_width: int = 220,
    colors: Optional[dict[str, str]] = None,
) -> "DescriptionLabel":
    """
    Create and return a :class:`DescriptionLabel` for *target*.

    The caller is responsible for keeping the returned object alive (assign it
    to an instance attribute) — otherwise garbage collection will remove the
    event filter and the description will no longer appear.

    Parameters
    ----------
    target:
        The widget to attach the description to.
    text:
        The description text (newlines are preserved).
    show_delay_ms:
        Milliseconds before the label appears.  Defaults to ``0``.
    max_wrap_width:
        Max pixel width before text wraps.  Defaults to ``220``.
    colors:
        Active theme colour mapping.  Defaults to ``LIGHT_THEME.colors``.

    Returns
    -------
    DescriptionLabel
        The attached description label.  Store this — do not discard.

    Examples
    --------
    In a ``QWidget.__init__``::

        self._desc_unit = attach_description(
            self._cb_unit1,
            "Select the source unit for the conversion.",
            colors=self._active_colors,
        )
    """
    return DescriptionLabel(
        text=text,
        target=target,
        show_delay_ms=show_delay_ms,
        max_wrap_width=max_wrap_width,
        colors=colors,
    )
