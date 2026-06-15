"""
tests/test_gui_history_menu.py
================================
Qt-free / logic-level unit tests for the history dialog context-menu action
helper (UC-I07 GUI, favorites view + context menu).

Rules:
- No PySide6 import anywhere in this file.
- No network access.
- No real user-data dir: all history tests use tmp_path or in-memory objects.
- Deterministic and offline.

Covers :func:`unit_converter.gui.history_menu.context_menu_actions`:
- Full-history view, non-favorite entry  -> add_favorite enabled; remove disabled.
- Full-history view, favorite entry      -> add_favorite disabled; remove enabled.
- Favorites-only view, favorite entry    -> add_favorite hidden/disabled; remove enabled.
- run_again and delete are always True.
"""

from __future__ import annotations

import pytest

from unit_converter.gui.history_menu import context_menu_actions


# ---------------------------------------------------------------------------
# Parametrized matrix: (is_favorites_view, entry_is_favorite) -> expected map
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "is_favorites_view, entry_is_favorite, expected",
    [
        # Full-history view, non-favorite entry
        (
            False, False,
            {
                "run_again": True,
                "delete": True,
                "add_favorite": True,     # entry not yet fav -> offer to add
                "remove_favorite": False, # not a fav -> nothing to remove
            },
        ),
        # Full-history view, favorite entry
        (
            False, True,
            {
                "run_again": True,
                "delete": True,
                "add_favorite": False,    # already a fav -> don't offer add
                "remove_favorite": True,  # is a fav -> offer to remove
            },
        ),
        # Favorites-only view (entry must be a favorite here by definition)
        (
            True, True,
            {
                "run_again": True,
                "delete": True,
                "add_favorite": False,    # not applicable in favorites view
                "remove_favorite": True,  # offer to remove from favorites
            },
        ),
        # Edge case: favorites view, non-favorite entry (shouldn't appear in
        # practice, but the helper must still be coherent / non-crashing)
        (
            True, False,
            {
                "run_again": True,
                "delete": True,
                "add_favorite": False,    # in favorites view -> never offer add
                "remove_favorite": False, # not a fav -> nothing to remove
            },
        ),
    ],
    ids=[
        "full_history/non_fav",
        "full_history/is_fav",
        "favs_view/is_fav",
        "favs_view/non_fav_edge",
    ],
)
def test_context_menu_actions(
    is_favorites_view: bool,
    entry_is_favorite: bool,
    expected: dict,
) -> None:
    result = context_menu_actions(is_favorites_view, entry_is_favorite)
    for key, want in expected.items():
        assert result[key] is want, (
            f"action '{key}' should be {want!r} for "
            f"is_favorites_view={is_favorites_view!r}, "
            f"entry_is_favorite={entry_is_favorite!r}; got {result[key]!r}"
        )


# ---------------------------------------------------------------------------
# run_again and delete are ALWAYS enabled (standalone assertions)
# ---------------------------------------------------------------------------

def test_run_again_always_enabled() -> None:
    """run_again must be True for all (view, favorite) combinations."""
    for fav_view in (True, False):
        for is_fav in (True, False):
            result = context_menu_actions(fav_view, is_fav)
            assert result["run_again"] is True, (
                f"run_again must be True; got False for "
                f"fav_view={fav_view}, is_fav={is_fav}"
            )


def test_delete_always_enabled() -> None:
    """delete must be True for all (view, favorite) combinations."""
    for fav_view in (True, False):
        for is_fav in (True, False):
            result = context_menu_actions(fav_view, is_fav)
            assert result["delete"] is True, (
                f"delete must be True; got False for "
                f"fav_view={fav_view}, is_fav={is_fav}"
            )


# ---------------------------------------------------------------------------
# add_favorite is never True in favorites view
# ---------------------------------------------------------------------------

def test_add_favorite_never_shown_in_favorites_view() -> None:
    """add_favorite must never be enabled when is_favorites_view=True."""
    for is_fav in (True, False):
        result = context_menu_actions(is_favorites_view=True, entry_is_favorite=is_fav)
        assert result["add_favorite"] is False, (
            f"add_favorite must be False in favorites view; "
            f"got True for is_fav={is_fav}"
        )


# ---------------------------------------------------------------------------
# remove_favorite mirrors entry_is_favorite
# ---------------------------------------------------------------------------

def test_remove_favorite_mirrors_entry_favorite_flag() -> None:
    """remove_favorite is enabled iff entry_is_favorite=True, in any view."""
    for fav_view in (True, False):
        result_fav = context_menu_actions(fav_view, entry_is_favorite=True)
        assert result_fav["remove_favorite"] is True, (
            f"remove_favorite should be True when entry is a fav "
            f"(fav_view={fav_view})"
        )

        result_non = context_menu_actions(fav_view, entry_is_favorite=False)
        assert result_non["remove_favorite"] is False, (
            f"remove_favorite should be False when entry is NOT a fav "
            f"(fav_view={fav_view})"
        )


# ---------------------------------------------------------------------------
# Return type is always dict[str, bool]
# ---------------------------------------------------------------------------

def test_return_type_is_dict_of_str_bool() -> None:
    result = context_menu_actions(False, False)
    assert isinstance(result, dict)
    for k, v in result.items():
        assert isinstance(k, str), f"key {k!r} is not str"
        assert isinstance(v, bool), f"value for {k!r} is not bool"


# ---------------------------------------------------------------------------
# All four expected keys are present
# ---------------------------------------------------------------------------

def test_all_expected_keys_present() -> None:
    required = {"run_again", "delete", "add_favorite", "remove_favorite"}
    for fav_view in (True, False):
        for is_fav in (True, False):
            result = context_menu_actions(fav_view, is_fav)
            missing = required - result.keys()
            assert not missing, (
                f"Missing keys {missing!r} for fav_view={fav_view}, is_fav={is_fav}"
            )
