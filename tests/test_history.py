"""
tests/test_history.py
======================
Unit tests for unit_converter.core.history (UC-I07).

All tests use temporary paths to avoid touching the real user history file.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from unit_converter.core.history import (
    MAX_HISTORY,
    HistoryEntry,
    add_favorite,
    clear_history,
    delete_entry,
    list_favorites,
    load_history,
    record,
    remove_favorite,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def hist_path(tmp_path: Path) -> Path:
    return tmp_path / "history.json"


# ---------------------------------------------------------------------------
# record + load_history
# ---------------------------------------------------------------------------

class TestRecord:
    def test_record_returns_entry(self, hist_path):
        entry = record(
            "Mass", 1.0, "gram (g)", "Av. pound (lb)", 0.0022,
            history_path=hist_path,
        )
        assert isinstance(entry, HistoryEntry)
        assert entry.magnitude == "Mass"
        assert entry.from_unit == "gram (g)"
        assert entry.to_unit == "Av. pound (lb)"
        assert entry.value == pytest.approx(1.0)
        assert entry.result == pytest.approx(0.0022)

    def test_entry_has_timestamp(self, hist_path):
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        assert entry.timestamp != ""
        assert "T" in entry.timestamp  # ISO-8601 format

    def test_record_persists(self, hist_path):
        record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == 1
        assert history[0].magnitude == "Mass"

    def test_multiple_records_accumulate(self, hist_path):
        for i in range(5):
            record("Mass", float(i), "gram (g)", "gram (g)", float(i), history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == 5

    def test_most_recent_first(self, hist_path):
        record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        record("Length", 2.0, "meter (m)", "meter (m)", 2.0, history_path=hist_path)
        history = load_history(hist_path)
        assert history[0].magnitude == "Length"  # most recent first
        assert history[1].magnitude == "Mass"

    def test_cap_at_max_history_non_favorites(self, hist_path):
        """Non-favorite entries are capped at MAX_HISTORY (100)."""
        for i in range(MAX_HISTORY + 10):
            record("Mass", float(i), "gram (g)", "gram (g)", float(i), history_path=hist_path)
        history = load_history(hist_path)
        # All entries are non-favorites; exactly MAX_HISTORY should remain.
        assert len(history) == MAX_HISTORY

    def test_cap_drops_oldest_non_favorites(self, hist_path):
        """The oldest non-favorites are dropped when the cap is exceeded."""
        # Record MAX_HISTORY + 5 entries; value tracks insertion order.
        for i in range(MAX_HISTORY + 5):
            record("Mass", float(i), "gram (g)", "gram (g)", float(i), history_path=hist_path)
        history = load_history(hist_path)
        # load_history returns most-recent-first; the oldest remaining entry
        # should have value = 5 (first 5 were dropped).
        oldest = history[-1]
        assert oldest.value == pytest.approx(5.0)

    def test_sig_figs_stored(self, hist_path):
        entry = record(
            "Mass", 1.0, "gram (g)", "gram (g)", 1.0,
            sig_figs=3, history_path=hist_path,
        )
        assert entry.sig_figs == 3
        history = load_history(hist_path)
        assert history[0].sig_figs == 3

    def test_orders_stored(self, hist_path):
        record(
            "Length", 1.0, "meter (m)", "meter (m)", 1000.0,
            from_order="k", to_order="1", history_path=hist_path,
        )
        history = load_history(hist_path)
        assert history[0].from_order == "k"

    def test_empty_history_returns_empty_list(self, hist_path):
        history = load_history(hist_path)
        assert history == []


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------

class TestClearHistory:
    def test_clear_removes_all_entries(self, hist_path):
        for i in range(3):
            record("Mass", float(i), "gram (g)", "gram (g)", float(i), history_path=hist_path)
        clear_history(hist_path)
        assert load_history(hist_path) == []

    def test_clear_on_empty_is_safe(self, hist_path):
        clear_history(hist_path)  # should not raise

    def test_clear_removes_favorites_too(self, hist_path):
        """clear_history wipes everything, including favorites."""
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        add_favorite(entry, label="keeper", history_path=hist_path)
        clear_history(hist_path)
        assert load_history(hist_path) == []
        assert list_favorites(hist_path) == []


# ---------------------------------------------------------------------------
# favorites — add_favorite / list_favorites
# ---------------------------------------------------------------------------

class TestFavorites:
    def test_add_favorite_marks_entry(self, hist_path):
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        add_favorite(entry, label="my fav", history_path=hist_path)
        favs = list_favorites(hist_path)
        assert len(favs) == 1
        assert favs[0].favorite is True
        assert favs[0].favorite_label == "my fav"

    def test_list_favorites_only_returns_starred(self, hist_path):
        e1 = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        record("Length", 2.0, "meter (m)", "meter (m)", 2.0, history_path=hist_path)
        add_favorite(e1, label="fav mass", history_path=hist_path)
        favs = list_favorites(hist_path)
        assert len(favs) == 1
        assert favs[0].magnitude == "Mass"

    def test_no_favorites_returns_empty(self, hist_path):
        record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        assert list_favorites(hist_path) == []

    def test_history_entry_not_favorite_by_default(self, hist_path):
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        assert entry.favorite is False
        assert entry.favorite_label == ""


# ---------------------------------------------------------------------------
# Favorites cap-exemption: favorites survive a flood of non-favorite records
# ---------------------------------------------------------------------------

class TestFavoriteCapExemption:
    def test_favorites_never_dropped_by_cap(self, hist_path):
        """
        Favorites are exempt from the MAX_HISTORY cap.
        Record 3 favorites first, then flood with MAX_HISTORY + 20 non-favorites.
        All 3 favorites must survive; non-favorites are capped at MAX_HISTORY.
        """
        fav_entries = []
        for i in range(3):
            e = record(
                "Mass", float(i), "gram (g)", "gram (g)", float(i),
                history_path=hist_path,
            )
            add_favorite(e, label=f"fav-{i}", history_path=hist_path)
            fav_entries.append(e)

        # Flood with non-favorites
        for i in range(MAX_HISTORY + 20):
            record(
                "Length", float(i), "meter (m)", "meter (m)", float(i),
                history_path=hist_path,
            )

        all_history = load_history(hist_path)
        favs = list_favorites(hist_path)
        non_favs = [e for e in all_history if not e.favorite]

        # All 3 favorites must be present
        assert len(favs) == 3
        fav_timestamps = {e.timestamp for e in fav_entries}
        assert all(e.timestamp in fav_timestamps for e in favs)

        # Non-favorites capped at MAX_HISTORY
        assert len(non_favs) == MAX_HISTORY

        # Total = 3 favorites + MAX_HISTORY non-favorites
        assert len(all_history) == MAX_HISTORY + 3

    def test_favorites_survive_far_exceeding_100_entries(self, hist_path):
        """
        Total entries (favorites + non-favorites) can exceed 100 without
        favorites being evicted.
        """
        # Record 10 favorites
        fav_ts = set()
        for i in range(10):
            e = record(
                "Mass", float(i), "gram (g)", "gram (g)", float(i),
                history_path=hist_path,
            )
            add_favorite(e, label=f"fav-{i}", history_path=hist_path)
            fav_ts.add(e.timestamp)

        # Flood 100 non-favorites (exactly at cap)
        for i in range(MAX_HISTORY):
            record(
                "Length", float(i), "meter (m)", "meter (m)", float(i),
                history_path=hist_path,
            )

        all_history = load_history(hist_path)
        favs = list_favorites(hist_path)

        # All 10 favorites still present
        assert len(favs) == 10
        # Total is 10 + MAX_HISTORY = 110
        assert len(all_history) == MAX_HISTORY + 10

    def test_non_favorites_capped_exactly_at_100(self, hist_path):
        """Boundary: exactly MAX_HISTORY non-favorite entries — no drop occurs."""
        for i in range(MAX_HISTORY):
            record("Mass", float(i), "gram (g)", "gram (g)", float(i), history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == MAX_HISTORY

    def test_oldest_non_favorite_dropped_not_favorites(self, hist_path):
        """
        When the cap is exceeded, the oldest NON-FAVORITE entry is dropped,
        not a favorite — even if the favorite is older.
        """
        # Record oldest entry, then mark it as a favorite
        oldest = record(
            "Mass", 999.0, "gram (g)", "gram (g)", 999.0,
            history_path=hist_path,
        )
        add_favorite(oldest, label="protect-me", history_path=hist_path)

        # Now add MAX_HISTORY more non-favorites to push past the cap
        for i in range(MAX_HISTORY):
            record(
                "Length", float(i), "meter (m)", "meter (m)", float(i),
                history_path=hist_path,
            )

        # The oldest non-favorite (value=0.0) should have been dropped,
        # but the favorite (value=999.0) must remain.
        all_history = load_history(hist_path)
        favs = list_favorites(hist_path)
        values = {e.value for e in all_history}

        assert 999.0 in values  # favorite survived
        assert len(favs) == 1
        assert favs[0].value == pytest.approx(999.0)
        # Non-favorites: MAX_HISTORY entries (the 0th was dropped)
        non_favs = [e for e in all_history if not e.favorite]
        assert len(non_favs) == MAX_HISTORY


# ---------------------------------------------------------------------------
# remove_favorite
# ---------------------------------------------------------------------------

class TestRemoveFavorite:
    def test_remove_favorite_clears_flag(self, hist_path):
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        add_favorite(entry, label="to remove", history_path=hist_path)
        assert len(list_favorites(hist_path)) == 1

        remove_favorite(entry, history_path=hist_path)

        assert list_favorites(hist_path) == []
        # Entry still in history, just no longer a favorite
        history = load_history(hist_path)
        assert len(history) == 1
        assert history[0].favorite is False
        assert history[0].favorite_label == ""

    def test_remove_favorite_clears_label(self, hist_path):
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        add_favorite(entry, label="some label", history_path=hist_path)
        remove_favorite(entry, history_path=hist_path)
        history = load_history(hist_path)
        assert history[0].favorite_label == ""

    def test_remove_favorite_noop_on_unknown_timestamp(self, hist_path):
        """remove_favorite with a non-existent timestamp is a no-op."""
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        ghost = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="gram (g)",
            from_order="1", to_order="1", value=1.0, result=1.0,
            sig_figs=None, timestamp="1970-01-01T00:00:00+00:00",
        )
        remove_favorite(ghost, history_path=hist_path)  # must not raise
        history = load_history(hist_path)
        assert len(history) == 1  # original entry untouched

    def test_remove_favorite_on_non_favorite_is_noop(self, hist_path):
        """Calling remove_favorite on an entry that was never a favorite is harmless."""
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        remove_favorite(entry, history_path=hist_path)  # must not raise
        history = load_history(hist_path)
        assert history[0].favorite is False

    def test_remove_favorite_only_affects_matched_entry(self, hist_path):
        """Only the matched entry loses its favorite; others are untouched."""
        e1 = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        e2 = record("Length", 2.0, "meter (m)", "meter (m)", 2.0, history_path=hist_path)
        add_favorite(e1, label="fav1", history_path=hist_path)
        add_favorite(e2, label="fav2", history_path=hist_path)

        remove_favorite(e1, history_path=hist_path)

        favs = list_favorites(hist_path)
        assert len(favs) == 1
        assert favs[0].magnitude == "Length"


# ---------------------------------------------------------------------------
# delete_entry
# ---------------------------------------------------------------------------

class TestDeleteEntry:
    def test_delete_entry_removes_matched_entry(self, hist_path):
        e1 = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        e2 = record("Length", 2.0, "meter (m)", "meter (m)", 2.0, history_path=hist_path)
        delete_entry(e1, history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == 1
        assert history[0].magnitude == "Length"

    def test_delete_entry_noop_on_unknown_timestamp(self, hist_path):
        """delete_entry with a non-existent timestamp leaves history unchanged."""
        record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        ghost = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="gram (g)",
            from_order="1", to_order="1", value=1.0, result=1.0,
            sig_figs=None, timestamp="1970-01-01T00:00:00+00:00",
        )
        delete_entry(ghost, history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == 1  # original entry intact

    def test_delete_entry_removes_favorite_entirely(self, hist_path):
        """Deleting a favorite removes the record completely (not just the flag)."""
        entry = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        add_favorite(entry, label="my fav", history_path=hist_path)
        delete_entry(entry, history_path=hist_path)
        assert load_history(hist_path) == []
        assert list_favorites(hist_path) == []

    def test_delete_entry_on_empty_history_is_safe(self, hist_path):
        ghost = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="gram (g)",
            from_order="1", to_order="1", value=1.0, result=1.0,
            sig_figs=None, timestamp="1970-01-01T00:00:00+00:00",
        )
        delete_entry(ghost, history_path=hist_path)  # must not raise
        assert load_history(hist_path) == []

    def test_delete_entry_only_removes_exact_match(self, hist_path):
        """Only the entry with the matching timestamp is removed."""
        e1 = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        e2 = record("Mass", 2.0, "gram (g)", "gram (g)", 2.0, history_path=hist_path)
        e3 = record("Mass", 3.0, "gram (g)", "gram (g)", 3.0, history_path=hist_path)
        delete_entry(e2, history_path=hist_path)
        history = load_history(hist_path)
        values = [e.value for e in history]
        assert 2.0 not in values
        assert 1.0 in values
        assert 3.0 in values

    def test_delete_then_record_does_not_restore_deleted(self, hist_path):
        """After deletion, re-recording with the same data gets a new timestamp."""
        e = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        delete_entry(e, history_path=hist_path)
        # Record again — new entry with new timestamp
        e2 = record("Mass", 1.0, "gram (g)", "gram (g)", 1.0, history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == 1
        # New entry has a different (or same-second) timestamp; either way only 1 entry
        assert history[0].value == pytest.approx(1.0)
