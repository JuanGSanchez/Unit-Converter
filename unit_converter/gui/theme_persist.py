"""
unit_converter.gui.theme_persist
==================================
Qt-INDEPENDENT persistence and validation helpers for GUI theme settings.

This module contains NO PySide6 / Qt imports and must remain importable in a
headless Python environment (e.g. during unit tests run by test-author).

Responsibilities
----------------
- Validate ``#RRGGBB`` hex colour strings.
- Serialise/deserialise a flat colour mapping to/from a JSON file stored under
  the standard user data directory (``~/.unit-converter/gui_theme.json``),
  following the same convention used by ``core.history`` and ``core.data_loader``
  for custom units.
- Merge persisted overrides on top of a base theme so missing keys fall back
  gracefully to the built-in defaults.

Public API
----------
``is_valid_hex_color(value: str) -> bool``
    Return True iff *value* is a syntactically valid ``#RRGGBB`` colour string
    (case-insensitive; exactly 7 characters including the ``#`` prefix).

``normalize_hex_color(value: str) -> str | None``
    Return the colour uppercased (e.g. ``"#1a2b3c"`` -> ``"#1A2B3C"``), or
    ``None`` if *value* is not a valid ``#RRGGBB`` string.

``load_theme_prefs(path=None) -> dict[str, str]``
    Load the persisted theme preferences from *path* (default:
    ``~/.unit-converter/gui_theme.json``).  Returns ``{}`` on missing/corrupt
    file.  The returned dict has two special keys:
      - ``"__theme__"``: the name of the last-selected built-in theme
        (``"Light"`` or ``"Dark"``).
      - All other keys are widget-type colour overrides (``#RRGGBB`` strings).

``save_theme_prefs(prefs: dict[str, str], path=None) -> None``
    Persist *prefs* to *path*.  Silently ignores ``OSError`` (same pattern as
    ``core.history``).

``merge_theme_colors(base: dict[str, str], overrides: dict[str, str])
    -> dict[str, str]``
    Return a new dict that is *base* updated with only those entries in
    *overrides* whose values pass ``is_valid_hex_color``.  Special key
    ``"__theme__"`` is also passed through.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex for #RRGGBB validation
# ---------------------------------------------------------------------------
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_THEME_FILENAME = "gui_theme.json"


# ---------------------------------------------------------------------------
# Color validation
# ---------------------------------------------------------------------------

def is_valid_hex_color(value: str) -> bool:
    """
    Return True iff *value* is a valid ``#RRGGBB`` hex colour string.

    Parameters
    ----------
    value:
        Candidate string to check (e.g. ``"#FF0000"`` or ``"red"``).

    Returns
    -------
    bool
        ``True`` for exactly seven-char strings matching ``#[0-9A-Fa-f]{6}``.

    Examples
    --------
    >>> is_valid_hex_color("#FFFFFF")
    True
    >>> is_valid_hex_color("#fff")
    False
    >>> is_valid_hex_color("white")
    False
    >>> is_valid_hex_color("#GGGGGG")
    False
    """
    if not isinstance(value, str):
        return False
    return bool(_HEX_COLOR_RE.match(value))


def normalize_hex_color(value: str) -> Optional[str]:
    """
    Normalise a ``#RRGGBB`` string to upper-case, or return ``None``.

    Parameters
    ----------
    value:
        Candidate colour string.

    Returns
    -------
    str or None
        Upper-cased ``#RRGGBB`` string if valid, ``None`` otherwise.

    Examples
    --------
    >>> normalize_hex_color("#1a2b3c")
    '#1A2B3C'
    >>> normalize_hex_color("invalid")
    """
    if is_valid_hex_color(value):
        return value.upper()
    return None


# ---------------------------------------------------------------------------
# Path helper (mirrors core.data_loader._user_data_dir)
# ---------------------------------------------------------------------------

def _user_data_dir() -> Path:
    """Return ``~/.unit-converter/``, creating it if necessary."""
    user_dir = Path.home() / ".unit-converter"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _theme_path(path: Optional[Path] = None) -> Path:
    """Return the path to the GUI theme JSON file."""
    if path is not None:
        return Path(path)
    return _user_data_dir() / _THEME_FILENAME


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_theme_prefs(path: Optional[Path] = None) -> dict[str, str]:
    """
    Load persisted theme preferences from *path*.

    Returns ``{}`` on a missing or corrupt file — callers must fall back to
    built-in defaults in that case.

    Parameters
    ----------
    path:
        Override the default path (useful in tests).

    Returns
    -------
    dict[str, str]
        Raw key→value mapping as stored in the JSON file.  The special key
        ``"__theme__"`` holds the built-in theme name; all other keys are
        widget-type → ``#RRGGBB`` colour overrides.
    """
    target = _theme_path(path)
    try:
        text = target.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read theme prefs from %s: %s", target, exc)
    return {}


def save_theme_prefs(prefs: dict[str, str], path: Optional[Path] = None) -> None:
    """
    Persist *prefs* to the theme JSON file.

    Parameters
    ----------
    prefs:
        Key→value mapping to persist (``"__theme__"`` + widget colour keys).
    path:
        Override the default path (useful in tests).
    """
    target = _theme_path(path)
    try:
        target.write_text(
            json.dumps(prefs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not write theme prefs to %s: %s", target, exc)


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------

def merge_theme_colors(
    base: dict[str, str],
    overrides: dict[str, str],
) -> dict[str, str]:
    """
    Return *base* updated with validated entries from *overrides*.

    Only override entries whose values are valid ``#RRGGBB`` strings (or the
    special ``"__theme__"`` string key) are applied; invalid colour strings are
    silently dropped so a corrupt prefs file cannot break the UI.

    Parameters
    ----------
    base:
        Built-in theme colour mapping (all values must already be valid hex).
    overrides:
        Persisted or user-supplied overrides; invalid values are dropped.

    Returns
    -------
    dict[str, str]
        Merged colour mapping (a new dict, *base* and *overrides* are
        unchanged).

    Examples
    --------
    >>> base = {"bg_main": "#BFBFBF", "fg_title": "#0000FF"}
    >>> overrides = {"bg_main": "#222222", "fg_title": "notacolor"}
    >>> merge_theme_colors(base, overrides)
    {'bg_main': '#222222', 'fg_title': '#0000FF'}
    """
    result = dict(base)
    for key, value in overrides.items():
        if key == "__theme__":
            result[key] = value
        elif is_valid_hex_color(value):
            result[key] = value
        # else: silently drop invalid value
    return result
