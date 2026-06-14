"""
unit_converter.gui.resources
=============================
``sys._MEIPASS``-aware resource-path helper.

Works both when running from source and when the application is frozen by
PyInstaller (one-file or one-dir mode).  In a frozen build PyInstaller unpacks
bundled data into a temporary directory whose path is stored in ``sys._MEIPASS``;
the normal ``os.path.dirname(__file__)`` does not resolve correctly there.

Public API
----------
resource_path(rel_path: str) -> str
    Return the absolute path to *rel_path*, resolving relative to the
    PyInstaller bundle root (``sys._MEIPASS``) when frozen, or relative to the
    repository / install root when running from source.

logo_path() -> str
    Convenience wrapper — returns the absolute path to ``Logo UC.png``.
"""

from __future__ import annotations

import os
import sys


def resource_path(rel_path: str) -> str:
    """
    Return the absolute filesystem path for a bundled resource.

    Parameters
    ----------
    rel_path:
        Path relative to the application root (e.g. ``"Logo UC.png"``).

    Returns
    -------
    str
        Absolute path, valid in both source-run and PyInstaller-frozen contexts.

    Notes
    -----
    Strategy (per PyInstaller docs, ``sys._MEIPASS`` section):

    1. If ``sys._MEIPASS`` exists, use it as the base — this is the temp dir
       PyInstaller extracts the bundle into at runtime.
    2. Otherwise, use the directory **two levels above this file** (i.e. the
       repository root where ``Logo UC.png`` lives alongside ``pyproject.toml``).
       This is computed once to remain correct whether the package is installed
       (editable or otherwise) or run directly.
    """
    base: str = getattr(
        sys,
        "_MEIPASS",
        # Running from source: go up from unit_converter/gui/ to repo root
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        ),
    )
    return os.path.join(base, rel_path)


def logo_path() -> str:
    """Return the absolute path to the application logo PNG."""
    return resource_path("Logo UC.png")
