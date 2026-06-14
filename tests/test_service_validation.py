"""
tests/test_service_validation.py
==================================
Service-layer unit tests for state-changing operation validation.

All file/network I/O is mocked or redirected to tmp_path.
"""
from __future__ import annotations

import math
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# add_custom_unit: name-injection + factor validation
# ---------------------------------------------------------------------------

class TestAddCustomUnitService:
    """Tests for unit_converter.api.service.add_custom_unit."""

    def _call(self, magnitude, unit_name, factor):
        from unit_converter.api import service
        return service.add_custom_unit(magnitude, unit_name, factor)

    def test_empty_magnitude_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="magnitude"):
            service.add_custom_unit("", "myunit", 1.0)

    def test_whitespace_magnitude_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="magnitude"):
            service.add_custom_unit("   ", "myunit", 1.0)

    def test_empty_unit_name_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError):
            service.add_custom_unit("Mass", "", 1.0)

    def test_whitespace_unit_name_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError):
            service.add_custom_unit("Mass", "   ", 1.0)

    def test_path_traversal_slash_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="disallowed"):
            service.add_custom_unit("Mass", "../secret", 1.0)

    def test_path_traversal_backslash_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="disallowed"):
            service.add_custom_unit("Mass", "..\\secret", 1.0)

    def test_control_char_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="disallowed"):
            service.add_custom_unit("Mass", "bad\x01unit", 1.0)

    def test_toml_bracket_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="disallowed"):
            service.add_custom_unit("Mass", "[inject]", 1.0)

    def test_toml_equals_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="disallowed"):
            service.add_custom_unit("Mass", "a=b", 1.0)

    def test_name_exceeds_max_length_raises(self):
        from unit_converter.api import service
        long_name = "a" * 121
        with pytest.raises(ValueError, match="maximum length"):
            service.add_custom_unit("Mass", long_name, 1.0)

    def test_negative_factor_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="positive"):
            service.add_custom_unit("Mass", "myunit", -1.0)

    def test_zero_factor_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="positive"):
            service.add_custom_unit("Mass", "myunit", 0.0)

    def test_nan_factor_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="finite"):
            service.add_custom_unit("Mass", "myunit", float("nan"))

    def test_inf_factor_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="finite"):
            service.add_custom_unit("Mass", "myunit", math.inf)

    def test_valid_unit_calls_core(self, tmp_path):
        custom_path = tmp_path / "custom.toml"
        from unit_converter.api import service
        # Patch the core writer so we don't touch real FS
        with patch("unit_converter.api.service._core_add_custom_unit") as mock_core:
            result = service.add_custom_unit("Mass", "myunit", 2.5)
        mock_core.assert_called_once_with("Mass", "myunit", 2.5)
        assert result == {"magnitude": "Mass", "unit_name": "myunit", "factor": 2.5}


# ---------------------------------------------------------------------------
# record_conversion: field validation
# ---------------------------------------------------------------------------

class TestRecordConversionService:
    """Tests for unit_converter.api.service.record_conversion."""

    def test_empty_magnitude_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="magnitude"):
            service.record_conversion("", 1.0, "gram (g)", "Av. pound (lb)", 0.002)

    def test_whitespace_magnitude_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="magnitude"):
            service.record_conversion("  ", 1.0, "gram (g)", "Av. pound (lb)", 0.002)

    def test_empty_from_unit_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="from_unit"):
            service.record_conversion("Mass", 1.0, "", "Av. pound (lb)", 0.002)

    def test_empty_to_unit_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="to_unit"):
            service.record_conversion("Mass", 1.0, "gram (g)", "", 0.002)

    def test_success_delegates_to_core(self, tmp_path):
        from unit_converter.core.history import HistoryEntry
        stub_entry = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="Av. pound (lb)",
            from_order="1", to_order="1", value=1.0, result=0.002,
            sig_figs=None, timestamp="2026-06-13T10:00:00Z",
        )
        from unit_converter.api import service
        with patch("unit_converter.api.service._history.record", return_value=stub_entry):
            result = service.record_conversion(
                "Mass", 1.0, "gram (g)", "Av. pound (lb)", 0.002
            )
        assert result["magnitude"] == "Mass"
        assert result["result"] == pytest.approx(0.002)


# ---------------------------------------------------------------------------
# add_favorite_by_timestamp: timestamp validation
# ---------------------------------------------------------------------------

class TestAddFavoriteByTimestampService:
    def test_empty_timestamp_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="timestamp"):
            service.add_favorite_by_timestamp("")

    def test_whitespace_timestamp_raises(self):
        from unit_converter.api import service
        with pytest.raises(ValueError, match="timestamp"):
            service.add_favorite_by_timestamp("   ")

    def test_no_matching_entry_raises(self):
        from unit_converter.api import service
        with patch("unit_converter.api.service._history.load_history", return_value=[]):
            with pytest.raises(ValueError, match="No history entry"):
                service.add_favorite_by_timestamp("2026-06-13T10:00:00Z")

    def test_matching_entry_marks_favorite(self):
        from unit_converter.core.history import HistoryEntry
        from unit_converter.api import service
        entry = HistoryEntry(
            magnitude="Mass", from_unit="g", to_unit="lb",
            from_order="1", to_order="1", value=1.0, result=0.002,
            sig_figs=None, timestamp="2026-06-13T10:00:00Z",
        )
        with patch("unit_converter.api.service._history.load_history", return_value=[entry]), \
             patch("unit_converter.api.service._history.add_favorite") as mock_fav:
            service.add_favorite_by_timestamp("2026-06-13T10:00:00Z", "label")
        mock_fav.assert_called_once_with(entry, "label")


# ---------------------------------------------------------------------------
# refresh_rates offline fallback at service layer
# ---------------------------------------------------------------------------

class TestRefreshRatesServiceLayer:
    def test_network_error_propagates(self):
        from unit_converter.api import service
        with patch("unit_converter.api.service._rates.refresh_rates",
                   side_effect=urllib.error.URLError("down")):
            with pytest.raises(urllib.error.URLError):
                service.refresh_rates()

    def test_success_returns_dict(self):
        from unit_converter.core.rates import RatesResult
        from unit_converter.api import service
        rr = RatesResult(
            rates={"USD": 1.0, "EUR": 0.86},
            base="USD", date="2026-06-13", source="live", is_stale=False,
        )
        with patch("unit_converter.api.service._rates.refresh_rates", return_value=rr):
            result = service.refresh_rates()
        assert result["date"] == "2026-06-13"
        assert result["currency_count"] == 2
        assert result["source"] == "live"


# ---------------------------------------------------------------------------
# clear_history: service wrapper
# ---------------------------------------------------------------------------

class TestClearHistoryService:
    def test_returns_cleared_true(self):
        from unit_converter.api import service
        with patch("unit_converter.api.service._history.clear_history", return_value=None):
            result = service.clear_history()
        assert result == {"cleared": True}
