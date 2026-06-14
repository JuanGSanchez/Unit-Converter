"""
tests/test_rates.py
====================
Unit tests for unit_converter.core.rates (UC-I05).

Tests use mocked fetch functions and temporary cache paths to avoid
any real network calls.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from unit_converter.core.rates import (
    RatesResult,
    _cache_is_fresh,
    _load_bundle,
    _read_cache,
    _write_cache,
    fetch_rates,
    get_rate,
    list_currencies,
    load_rates,
    refresh_rates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MOCK_API_RESPONSE = {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-06-13",
    "rates": {
        "EUR": 0.86,
        "GBP": 0.75,
        "JPY": 155.0,
        "USD": 1.0,
    },
}


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    """Provide a temporary cache path for tests."""
    return tmp_path / "currency_cache.json"


# ---------------------------------------------------------------------------
# _cache_is_fresh
# ---------------------------------------------------------------------------

class TestCacheIsFresh:
    def test_fresh_cache_within_window(self):
        cache = {"_fetched_at": time.time() - 100}  # 100 s ago
        assert _cache_is_fresh(cache) is True

    def test_stale_cache_beyond_window(self):
        cache = {"_fetched_at": time.time() - 100_000}  # > 24 h ago
        assert _cache_is_fresh(cache) is False

    def test_missing_fetched_at_is_stale(self):
        assert _cache_is_fresh({}) is False


# ---------------------------------------------------------------------------
# _read_cache / _write_cache
# ---------------------------------------------------------------------------

class TestCacheReadWrite:
    def test_write_then_read(self, cache_dir):
        _write_cache(cache_dir, _MOCK_API_RESPONSE)
        result = _read_cache(cache_dir)
        assert result is not None
        assert result["base"] == "USD"
        assert "EUR" in result["rates"]

    def test_read_missing_returns_none(self, cache_dir):
        assert _read_cache(cache_dir) is None

    def test_read_corrupt_returns_none(self, cache_dir):
        cache_dir.write_text("not valid json", encoding="utf-8")
        assert _read_cache(cache_dir) is None

    def test_write_adds_fetched_at(self, cache_dir):
        _write_cache(cache_dir, _MOCK_API_RESPONSE)
        result = _read_cache(cache_dir)
        assert "_fetched_at" in result


# ---------------------------------------------------------------------------
# load_rates - with mocked fetch
# ---------------------------------------------------------------------------

class TestLoadRates:
    def test_uses_fresh_cache_without_fetching(self, cache_dir):
        """If a fresh cache exists, no network call is made."""
        fresh_cache = dict(_MOCK_API_RESPONSE)
        fresh_cache["_fetched_at"] = time.time()
        cache_dir.write_text(json.dumps(fresh_cache), encoding="utf-8")

        with patch("unit_converter.core.rates.fetch_rates") as mock_fetch:
            result = load_rates(custom_cache_path=cache_dir)
            mock_fetch.assert_not_called()

        assert result.source == "cache"
        assert result.is_stale is False
        assert "EUR" in result.rates

    def test_fetches_when_no_cache(self, cache_dir):
        """With no cache, a live fetch is attempted."""
        with patch("unit_converter.core.rates.fetch_rates", return_value=_MOCK_API_RESPONSE):
            result = load_rates(custom_cache_path=cache_dir)

        assert result.source == "live"
        assert result.is_stale is False
        assert "EUR" in result.rates

    def test_falls_back_to_stale_cache_on_network_error(self, cache_dir):
        """If fetch fails, stale cache is used."""
        import urllib.error
        stale_cache = dict(_MOCK_API_RESPONSE)
        stale_cache["_fetched_at"] = time.time() - 200_000  # very old
        cache_dir.write_text(json.dumps(stale_cache), encoding="utf-8")

        with patch("unit_converter.core.rates.fetch_rates",
                   side_effect=urllib.error.URLError("network down")):
            result = load_rates(custom_cache_path=cache_dir)

        assert result.is_stale is True
        assert result.source == "stale_cache"

    def test_falls_back_to_bundle_on_network_error_no_cache(self, cache_dir):
        """If fetch fails and no cache exists, bundled snapshot is used."""
        import urllib.error
        with patch("unit_converter.core.rates.fetch_rates",
                   side_effect=urllib.error.URLError("network down")):
            result = load_rates(custom_cache_path=cache_dir)

        assert result.is_stale is True
        assert result.source in ("bundle", "stale_cache")

    def test_writes_cache_after_successful_fetch(self, cache_dir):
        """Successful fetch is persisted to cache."""
        with patch("unit_converter.core.rates.fetch_rates", return_value=_MOCK_API_RESPONSE):
            load_rates(custom_cache_path=cache_dir)

        assert cache_dir.exists()
        cached = json.loads(cache_dir.read_text(encoding="utf-8"))
        assert cached["base"] == "USD"


# ---------------------------------------------------------------------------
# get_rate
# ---------------------------------------------------------------------------

class TestGetRate:
    def _mock_result(self) -> RatesResult:
        return RatesResult(
            rates={"USD": 1.0, "EUR": 0.86, "GBP": 0.75, "JPY": 155.0},
            base="USD",
            date="2026-06-13",
        )

    def test_usd_to_eur(self):
        result = get_rate("USD", "EUR", self._mock_result())
        assert result == pytest.approx(0.86)

    def test_eur_to_usd(self):
        result = get_rate("EUR", "USD", self._mock_result())
        assert result == pytest.approx(1.0 / 0.86, rel=1e-6)

    def test_cross_rate_gbp_to_jpy(self):
        # GBP->JPY = rates[JPY] / rates[GBP] = 155 / 0.75
        result = get_rate("GBP", "JPY", self._mock_result())
        assert result == pytest.approx(155.0 / 0.75, rel=1e-6)

    def test_same_currency_returns_1(self):
        result = get_rate("USD", "USD", self._mock_result())
        assert result == pytest.approx(1.0)

    def test_unknown_from_raises(self):
        with pytest.raises(KeyError, match="XYZ"):
            get_rate("XYZ", "EUR", self._mock_result())

    def test_unknown_to_raises(self):
        with pytest.raises(KeyError, match="ZZZ"):
            get_rate("USD", "ZZZ", self._mock_result())


# ---------------------------------------------------------------------------
# list_currencies
# ---------------------------------------------------------------------------

class TestListCurrencies:
    def test_returns_sorted_list(self):
        result = RatesResult(
            rates={"USD": 1.0, "EUR": 0.86, "GBP": 0.75},
            base="USD",
            date="2026-06-13",
        )
        codes = list_currencies(result)
        assert codes == sorted(codes)
        assert "USD" in codes
        assert "EUR" in codes


# ---------------------------------------------------------------------------
# refresh_rates
# ---------------------------------------------------------------------------

class TestRefreshRates:
    def test_refresh_writes_cache_and_returns_live(self, cache_dir):
        with patch("unit_converter.core.rates.fetch_rates", return_value=_MOCK_API_RESPONSE):
            result = refresh_rates(custom_cache_path=cache_dir)

        assert result.source == "live"
        assert result.is_stale is False
        assert cache_dir.exists()

    def test_refresh_propagates_network_error(self, cache_dir):
        import urllib.error
        with pytest.raises(urllib.error.URLError):
            with patch("unit_converter.core.rates.fetch_rates",
                       side_effect=urllib.error.URLError("down")):
                refresh_rates(custom_cache_path=cache_dir)


# ---------------------------------------------------------------------------
# Bundle snapshot
# ---------------------------------------------------------------------------

class TestBundleSnapshot:
    def test_bundle_loads(self):
        """The shipped currency_snapshot.json must be loadable."""
        bundle = _load_bundle()
        if bundle is None:
            pytest.skip("Bundle snapshot not present in this test environment.")
        assert "rates" in bundle
        assert "date" in bundle
        assert "USD" in bundle["rates"] or bundle.get("base") == "USD"
