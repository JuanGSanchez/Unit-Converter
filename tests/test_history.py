"""
tests/test_history.py
======================
Unit tests for unit_converter.core.history (UC-I07).

All tests use temporary paths to avoid touching the real user history file.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from unit_converter.core.history import (
    MAX_HISTORY,
    HistoryEntry,
    add_favorite,
    clear_history,
    list_favorites,
    load_history,
    record,
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

    def test_cap_at_max_history(self, hist_path):
        for i in range(MAX_HISTORY + 10):
            record("Mass", float(i), "gram (g)", "gram (g)", float(i), history_path=hist_path)
        history = load_history(hist_path)
        assert len(history) == MAX_HISTORY

    def test_sig_figs_stored(self, hist_path):
        entry = record(
            "Mass", 1.0, "gram (g)", "gram (g)", 1.0,
            sig_figs=3, history_path=hist_path,
        )
        assert entry.sig_figs == 3
        history = load_history(hist_path)
        assert history[0].sig_figs == 3

    def test_orders_stored(self, hist_path):
        entry = record(
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


# ---------------------------------------------------------------------------
# favorites
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
