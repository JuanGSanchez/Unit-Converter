"""
unit_converter.gui.history_menu
================================
Qt-free helper for the History dialog's context-menu action logic (UC-I07).

The single public function :func:`context_menu_actions` determines which
right-click actions are applicable and enabled for a given combination of:

- **view mode** — full-history view vs. favorites-only view.
- **entry favorite state** — whether the selected entry is already a favorite.

This module has NO Qt/PySide6 imports and is fully unit-testable without a
running QApplication.

Action keys (strings) returned in the mapping
----------------------------------------------
``"run_again"``
    Always present and enabled (in both views, for any entry state).
``"add_favorite"``
    Present and enabled only in the full-history view when the entry is NOT
    already a favorite.  Hidden/absent in favorites-only view (not applicable)
    and disabled in full-history view when the entry is already a favorite.
``"remove_favorite"``
    Present and enabled when the entry IS a favorite (both views).
    Absent/disabled when the entry is not a favorite.
``"delete"``
    Always present and enabled (in both views, for any entry state).
"""

from __future__ import annotations


def context_menu_actions(
    is_favorites_view: bool,
    entry_is_favorite: bool,
) -> dict[str, bool]:
    """
    Return a mapping of action-name -> enabled (bool) for the history dialog
    context menu.

    Parameters
    ----------
    is_favorites_view:
        ``True`` when the dialog is showing the favorites-only list;
        ``False`` for the full-history list.
    entry_is_favorite:
        ``True`` when the selected entry has its ``favorite`` flag set.

    Returns
    -------
    dict[str, bool]
        Keys are action identifiers; values are ``True`` (action should be
        shown and enabled) or ``False`` (action should be hidden/disabled).
        An absent key is treated the same as ``False`` by callers.

    Rules
    -----
    - ``"run_again"`` — always ``True``.
    - ``"delete"``    — always ``True``.
    - ``"add_favorite"`` — ``True`` only in full-history view AND entry is NOT
      already a favorite.
    - ``"remove_favorite"`` — ``True`` when entry IS a favorite (both views).
    """
    return {
        "run_again": True,
        "delete": True,
        "add_favorite": (not is_favorites_view) and (not entry_is_favorite),
        "remove_favorite": entry_is_favorite,
    }
