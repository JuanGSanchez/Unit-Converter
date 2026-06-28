"""
unit_converter.gui.info_registry
=================================
Centralized widget-info registry for the U Converter GUI (SPEC-01).

All user-visible help strings live here as values in ``INFO_TEXTS``, keyed by
stable widget-id strings (kebab-case).  Every interactive widget in the app is
wired through the single helper :func:`register_info`, which sets the tooltip,
accessible description, and WhatsThis text from one registry lookup — giving
keyboard-only and screen-reader users the same information as hover users.

Public API
----------
``INFO_TEXTS : dict[str, str]``
    Registry mapping stable widget-id keys to plain-text help strings.
    No HTML/rich-text markup — plain text with ``\\n`` for line breaks.

``INFO_KEYS : frozenset[str]``
    Frozenset of all keys defined in ``INFO_TEXTS``.  Use in tests to assert
    100% coverage (no orphan keys, no widget missing a key).

``register_info(widget, key, *, extra="") -> str``
    Look up ``INFO_TEXTS[key]`` (raises ``KeyError`` with a clear message if
    the key is absent), compute ``text = INFO_TEXTS[key] + extra``, then set
    all three on *widget*: ``setToolTip``, ``setAccessibleDescription``,
    ``setWhatsThis``.  Returns the final text.

``USED_KEYS : set[str]``
    Module-level set populated by :func:`register_info` at runtime; every key
    that has been registered at least once appears here.  Tests can assert this
    matches ``INFO_KEYS`` after the UI is fully built.

Notes
-----
- This module imports PySide6 — it is a GUI module.
- No conversion/business logic lives here; it is a pure text registry + helper.
- The registry is the ONLY place tooltip text is defined; no inline literals in
  ``setToolTip(...)`` calls anywhere in the GUI layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: All widget help strings keyed by stable widget-id (kebab-case).
#: Plain text — no HTML.  Use ``\n`` for intentional line breaks.
INFO_TEXTS: dict[str, str] = {
    # --- Order labels (scroll-to-change prefix, click-to-reset) ------------
    "order_label": (
        "Scroll to change order of magnitude.\n"
        "Click to reset."
    ),

    # --- Sweep labels (digit-position control) -----------------------------
    "sweep_label": (
        "Scroll to change the decimal digit position\n"
        "used by the Up/Down arrow increment.\n"
        "Click to reset to auto."
    ),

    # --- Numeric entry fields ----------------------------------------------
    "num_entry": (
        "Write or press Enter to run the conversion.\n"
        "Ctrl+C copies the result to the clipboard.\n"
        "Ctrl+V pastes a numeric value into this field."
    ),

    # --- Magnitude selector ------------------------------------------------
    "magnitude_combo": (
        "List of magnitudes added to the application."
    ),

    # --- Scientific-notation value labels ----------------------------------
    "val_label": (
        "Actual total value in scientific notation."
    ),

    # --- Unit selector combos ----------------------------------------------
    "unit_combo": (
        "Select the unit to convert from or to.\n"
        "Only units for the chosen magnitude are listed."
    ),

    # --- History dialog ----------------------------------------------------
    "hist_dialog": (
        "Recent conversions and saved favorites."
    ),
    "hist_list": (
        "Recent conversions — double-click to re-run.\n"
        "Right-click for more options."
    ),
    "hist_btn_rerun": (
        "Re-populate the converter with this entry."
    ),
    "hist_btn_fav": (
        "Mark this entry as a favorite."
    ),
    # Dynamic toggle keys — used by _on_toggle_view to swap between views.
    "hist_toggle_to_fav": (
        "Switch to favorites-only view."
    ),
    "hist_toggle_to_full": (
        "Switch back to the full history view."
    ),

    # --- Add-Custom-Unit dialog --------------------------------------------
    "add_unit_dialog": (
        "Add a custom unit to an existing magnitude."
    ),
    "add_unit_magnitude_combo": (
        "The magnitude to extend."
    ),
    "add_unit_name_edit": (
        "Name for the new unit."
    ),
    "add_unit_factor_edit": (
        "Conversion factor relative to the magnitude's base unit.\n"
        "Must be a positive, non-zero finite number."
    ),

    # --- Settings dialog ---------------------------------------------------
    "settings_dialog": (
        "Configure the application theme and widget colours."
    ),
    "settings_theme_combo": (
        "Select a built-in theme.\n"
        "Colours below will be reset to the theme's defaults."
    ),
    "settings_load_btn": (
        "Reset all colours to the selected built-in theme."
    ),
    # Swatch buttons and hex editors use extra= for the per-color label.
    "settings_swatch_btn": (
        "Click to open colour picker for:"
    ),
    "settings_hex_edit": (
        "Type a hex colour for:\n"
        "\nFormat: #RRGGBB"
    ),
    "settings_apply_btn": (
        "Apply the current colours to the window immediately."
    ),

    # --- Clipboard actions (SPEC-15) ---------------------------------------
    "copy_result_action": (
        "Copy the conversion result to the clipboard as a\n"
        "full expression: <from_value> <from_unit> = <to_value> <to_unit>.\n"
        "Shortcut: Ctrl+C (when no text is selected in an entry field)."
    ),
}

#: Frozenset of all defined keys — use in tests to assert coverage.
INFO_KEYS: frozenset[str] = frozenset(INFO_TEXTS)

#: Keys that have been registered at runtime via :func:`register_info`.
USED_KEYS: set[str] = set()


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_info(widget: "QWidget", key: str, *, extra: str = "") -> str:
    """
    Register help text on *widget* from the centralized registry.

    Looks up ``INFO_TEXTS[key]`` (raises ``KeyError`` with a descriptive
    message if the key is absent), computes ``text = INFO_TEXTS[key] + extra``,
    then sets all three accessibility properties on *widget*:

    - ``widget.setToolTip(text)``          — hover tooltip
    - ``widget.setAccessibleDescription(text)``  — screen-reader description
    - ``widget.setWhatsThis(text)``        — keyboard ``?`` affordance

    The tooltip text and ``accessibleDescription`` are always identical
    (SPEC-01 acceptance criterion).

    Parameters
    ----------
    widget:
        Any :class:`PySide6.QtWidgets.QWidget` subclass.
    key:
        A key that must exist in :data:`INFO_TEXTS`.
    extra:
        Optional suffix appended verbatim to the looked-up text (useful for
        per-instance dynamic details, e.g. the colour-role label in Settings).

    Returns
    -------
    str
        The final text that was set on the widget.

    Raises
    ------
    KeyError
        If *key* is not present in :data:`INFO_TEXTS`, with a message listing
        the valid keys so callers can fix typos immediately.
    """
    if key not in INFO_TEXTS:
        valid = ", ".join(sorted(INFO_TEXTS))
        raise KeyError(
            f"Unknown info key {key!r}. Valid keys: {valid}"
        )
    text = INFO_TEXTS[key] + extra
    widget.setToolTip(text)
    widget.setAccessibleDescription(text)
    widget.setWhatsThis(text)
    USED_KEYS.add(key)
    return text
