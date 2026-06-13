"""
tests/test_api_routes.py
========================
REST route tests and MCP exact-names test for the 12 new access-layer routes.

Requires httpx, fastapi, fastmcp.  All network I/O is mocked — no real HTTP.
"""
from __future__ import annotations

import asyncio
import importlib
import socket
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Dependency guard
# ---------------------------------------------------------------------------

def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


_DEPS = all(_importable(m) for m in ("httpx", "fastapi", "fastmcp"))

pytestmark = pytest.mark.skipif(not _DEPS, reason="httpx/fastapi/fastmcp not installed")


# ---------------------------------------------------------------------------
# Shared async client helper
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def app():
    from unit_converter.api.rest import app as _app
    return _app


def _client(app):
    from httpx import ASGITransport, AsyncClient
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _get(app, path, **kwargs):
    async with _client(app) as ac:
        return await ac.get(path, **kwargs)


async def _post(app, path, **kwargs):
    async with _client(app) as ac:
        return await ac.post(path, **kwargs)


async def _delete(app, path, **kwargs):
    async with _client(app) as ac:
        return await ac.delete(path, **kwargs)


# ---------------------------------------------------------------------------
# Stub data reused across currency tests
# ---------------------------------------------------------------------------

_RATES_RESULT = None  # built lazily inside tests after import guard passes


def _make_rates_result():
    from unit_converter.core.rates import RatesResult
    return RatesResult(
        rates={"USD": 1.0, "EUR": 0.86, "GBP": 0.75},
        base="USD",
        date="2026-06-13",
        source="live",
        is_stale=False,
    )


# ===========================================================================
# GET /currencies
# ===========================================================================

class TestListCurrencies:
    def test_success(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.load_rates", return_value=rr), \
             patch("unit_converter.api.service._rates.list_currencies", return_value=["EUR", "GBP", "USD"]):
            resp = _run(_get(app, "/currencies"))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "EUR" in data


# ===========================================================================
# GET /currencies/rate
# ===========================================================================

class TestGetCurrencyRate:
    def test_success(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.load_rates", return_value=rr), \
             patch("unit_converter.api.service._rates.get_rate", return_value=0.86):
            resp = _run(_get(app, "/currencies/rate", params={"from": "USD", "to": "EUR"}))
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate"] == pytest.approx(0.86)
        assert data["from"] == "USD"
        assert data["to"] == "EUR"
        assert "date" in data
        assert "is_stale" in data

    def test_unknown_currency_returns_404(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.load_rates", return_value=rr), \
             patch("unit_converter.api.service._rates.get_rate", side_effect=KeyError("XYZ")):
            resp = _run(_get(app, "/currencies/rate", params={"from": "USD", "to": "XYZ"}))
        assert resp.status_code == 404

    def test_missing_params_returns_422(self, app):
        resp = _run(_get(app, "/currencies/rate"))
        assert resp.status_code == 422


# ===========================================================================
# POST /currencies/convert
# ===========================================================================

class TestConvertCurrency:
    def test_success(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.load_rates", return_value=rr), \
             patch("unit_converter.api.service._rates.get_rate", return_value=0.86):
            resp = _run(_post(app, "/currencies/convert",
                              json={"value": 100.0, "from": "USD", "to": "EUR"}))
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert data["result"] == pytest.approx(86.0)

    def test_unknown_currency_returns_404(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.load_rates", return_value=rr), \
             patch("unit_converter.api.service._rates.get_rate", side_effect=KeyError("ZZZ")):
            resp = _run(_post(app, "/currencies/convert",
                              json={"value": 1.0, "from": "USD", "to": "ZZZ"}))
        assert resp.status_code == 404

    def test_negative_value_returns_422(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.load_rates", return_value=rr), \
             patch("unit_converter.api.service._rates.get_rate", return_value=0.86):
            resp = _run(_post(app, "/currencies/convert",
                              json={"value": -1.0, "from": "USD", "to": "EUR"}))
        # Pydantic ge=0 constraint or service ValueError → 422
        assert resp.status_code == 422

    def test_missing_fields_returns_422(self, app):
        resp = _run(_post(app, "/currencies/convert", json={"value": 10.0}))
        assert resp.status_code == 422


# ===========================================================================
# POST /currencies/refresh
# ===========================================================================

class TestRefreshRates:
    def test_success(self, app):
        rr = _make_rates_result()
        with patch("unit_converter.api.service._rates.refresh_rates", return_value=rr):
            resp = _run(_post(app, "/currencies/refresh"))
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "currency_count" in data
        assert data["source"] == "live"

    def test_network_failure_returns_503(self, app):
        with patch("unit_converter.api.service._rates.refresh_rates",
                   side_effect=urllib.error.URLError("network down")):
            resp = _run(_post(app, "/currencies/refresh"))
        assert resp.status_code == 503

    def test_socket_timeout_returns_503(self, app):
        with patch("unit_converter.api.service._rates.refresh_rates",
                   side_effect=socket.timeout("timed out")):
            resp = _run(_post(app, "/currencies/refresh"))
        assert resp.status_code == 503


# ===========================================================================
# GET /convert/compound/parse
# ===========================================================================

class TestParseCompound:
    def test_success(self, app):
        resp = _run(_get(app, "/convert/compound/parse", params={"expr": "km/h"}))
        assert resp.status_code == 200
        data = resp.json()
        assert "expr" in data
        assert "factor" in data
        assert "dimensions" in data

    def test_invalid_expr_returns_422(self, app):
        resp = _run(_get(app, "/convert/compound/parse", params={"expr": "##bad##"}))
        assert resp.status_code == 422

    def test_missing_expr_returns_422(self, app):
        resp = _run(_get(app, "/convert/compound/parse"))
        assert resp.status_code == 422


# ===========================================================================
# POST /convert/compound
# ===========================================================================

class TestConvertCompound:
    def test_success(self, app):
        resp = _run(_post(app, "/convert/compound",
                          json={"value": 100.0, "from_expr": "km/h", "to_expr": "m/s"}))
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert data["result"] == pytest.approx(100.0 / 3.6, rel=1e-5)

    def test_incompatible_dimensions_returns_422(self, app):
        resp = _run(_post(app, "/convert/compound",
                          json={"value": 1.0, "from_expr": "km/h", "to_expr": "kg"}))
        assert resp.status_code == 422

    def test_unknown_unit_returns_422(self, app):
        resp = _run(_post(app, "/convert/compound",
                          json={"value": 1.0, "from_expr": "xyzunit/s", "to_expr": "m/s"}))
        assert resp.status_code == 422


# ===========================================================================
# GET /history
# ===========================================================================

class TestGetHistory:
    def test_empty_history(self, app):
        with patch("unit_converter.api.service._history.load_history", return_value=[]):
            resp = _run(_get(app, "/history"))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_entries(self, app):
        from unit_converter.core.history import HistoryEntry
        entry = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="Av. pound (lb)",
            from_order="1", to_order="1", value=1.0, result=0.0022,
            sig_figs=None, timestamp="2026-06-13T10:00:00Z",
        )
        with patch("unit_converter.api.service._history.load_history", return_value=[entry]):
            resp = _run(_get(app, "/history"))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["magnitude"] == "Mass"


# ===========================================================================
# GET /history/favorites
# ===========================================================================

class TestGetFavorites:
    def test_empty_favorites(self, app):
        with patch("unit_converter.api.service._history.list_favorites", return_value=[]):
            resp = _run(_get(app, "/history/favorites"))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_favorites(self, app):
        from unit_converter.core.history import HistoryEntry
        entry = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="Av. pound (lb)",
            from_order="1", to_order="1", value=1.0, result=0.0022,
            sig_figs=None, timestamp="2026-06-13T10:00:00Z",
            favorite=True, favorite_label="fav",
        )
        with patch("unit_converter.api.service._history.list_favorites", return_value=[entry]):
            resp = _run(_get(app, "/history/favorites"))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["favorite"] is True


# ===========================================================================
# POST /history/record
# ===========================================================================

class TestPostRecordConversion:
    def test_success_201(self, app):
        from unit_converter.core.history import HistoryEntry
        entry = HistoryEntry(
            magnitude="Mass", from_unit="gram (g)", to_unit="Av. pound (lb)",
            from_order="1", to_order="1", value=453.6, result=1.0,
            sig_figs=None, timestamp="2026-06-13T10:00:00Z",
        )
        with patch("unit_converter.api.service._history.record", return_value=entry):
            resp = _run(_post(app, "/history/record", json={
                "magnitude": "Mass", "value": 453.6,
                "from_unit": "gram (g)", "to_unit": "Av. pound (lb)", "result": 1.0,
            }))
        assert resp.status_code == 201
        data = resp.json()
        assert data["magnitude"] == "Mass"

    def test_empty_magnitude_returns_422(self, app):
        resp = _run(_post(app, "/history/record", json={
            "magnitude": "", "value": 1.0,
            "from_unit": "gram (g)", "to_unit": "Av. pound (lb)", "result": 0.002,
        }))
        assert resp.status_code == 422

    def test_empty_from_unit_returns_422(self, app):
        resp = _run(_post(app, "/history/record", json={
            "magnitude": "Mass", "value": 1.0,
            "from_unit": "", "to_unit": "Av. pound (lb)", "result": 0.002,
        }))
        assert resp.status_code == 422

    def test_missing_fields_returns_422(self, app):
        resp = _run(_post(app, "/history/record", json={"magnitude": "Mass"}))
        assert resp.status_code == 422


# ===========================================================================
# POST /history/favorites
# ===========================================================================

class TestPostAddFavorite:
    def test_success(self, app):
        with patch("unit_converter.api.service.add_favorite_by_timestamp", return_value=None):
            resp = _run(_post(app, "/history/favorites",
                              json={"timestamp": "2026-06-13T10:00:00Z", "label": "fav"}))
        assert resp.status_code == 200
        data = resp.json()
        assert data["marked"] is True
        assert data["timestamp"] == "2026-06-13T10:00:00Z"

    def test_empty_timestamp_returns_422(self, app):
        with patch("unit_converter.api.service.add_favorite_by_timestamp",
                   side_effect=ValueError("timestamp must be a non-empty string.")):
            resp = _run(_post(app, "/history/favorites",
                              json={"timestamp": "", "label": ""}))
        assert resp.status_code == 422

    def test_missing_entry_returns_422(self, app):
        with patch("unit_converter.api.service.add_favorite_by_timestamp",
                   side_effect=ValueError("No history entry")):
            resp = _run(_post(app, "/history/favorites",
                              json={"timestamp": "9999-01-01T00:00:00Z", "label": ""}))
        assert resp.status_code == 422


# ===========================================================================
# DELETE /history
# ===========================================================================

class TestDeleteHistory:
    def test_success(self, app):
        with patch("unit_converter.api.service._history.clear_history", return_value=None):
            resp = _run(_delete(app, "/history"))
        assert resp.status_code == 200
        assert resp.json()["cleared"] is True


# ===========================================================================
# POST /units/custom
# ===========================================================================

class TestAddCustomUnit:
    def test_success_201(self, app):
        with patch("unit_converter.api.service._core_add_custom_unit", return_value=None):
            resp = _run(_post(app, "/units/custom",
                              json={"magnitude": "Mass", "unit_name": "my-unit", "factor": 2.5}))
        assert resp.status_code == 201
        data = resp.json()
        assert data["magnitude"] == "Mass"
        assert data["unit_name"] == "my-unit"
        assert data["factor"] == pytest.approx(2.5)

    def test_negative_factor_returns_422(self, app):
        resp = _run(_post(app, "/units/custom",
                          json={"magnitude": "Mass", "unit_name": "badunit", "factor": -1.0}))
        assert resp.status_code == 422

    def test_zero_factor_returns_422(self, app):
        resp = _run(_post(app, "/units/custom",
                          json={"magnitude": "Mass", "unit_name": "badunit", "factor": 0.0}))
        assert resp.status_code == 422

    def test_name_injection_slash_returns_422(self, app):
        with patch("unit_converter.api.service._core_add_custom_unit", return_value=None):
            resp = _run(_post(app, "/units/custom",
                              json={"magnitude": "Mass", "unit_name": "../etc/passwd", "factor": 1.0}))
        assert resp.status_code == 422

    def test_name_with_control_char_returns_422(self, app):
        with patch("unit_converter.api.service._core_add_custom_unit", return_value=None):
            resp = _run(_post(app, "/units/custom",
                              json={"magnitude": "Mass", "unit_name": "bad\x00name", "factor": 1.0}))
        assert resp.status_code == 422

    def test_empty_name_returns_422(self, app):
        with patch("unit_converter.api.service._core_add_custom_unit", return_value=None):
            resp = _run(_post(app, "/units/custom",
                              json={"magnitude": "Mass", "unit_name": "", "factor": 1.0}))
        assert resp.status_code == 422

    def test_empty_magnitude_returns_422(self, app):
        with patch("unit_converter.api.service._core_add_custom_unit", return_value=None):
            resp = _run(_post(app, "/units/custom",
                              json={"magnitude": "", "unit_name": "myunit", "factor": 1.0}))
        assert resp.status_code == 422

    def test_name_with_toml_chars_returns_422(self, app):
        with patch("unit_converter.api.service._core_add_custom_unit", return_value=None):
            resp = _run(_post(app, "/units/custom",
                              json={"magnitude": "Mass", "unit_name": "[inject]", "factor": 1.0}))
        assert resp.status_code == 422


# ===========================================================================
# MCP tool exact names — updated for 16 routes
# ===========================================================================

_EXPECTED_TOOL_NAMES_16 = frozenset({
    "health_health_get",
    "get_magnitudes_magnitudes_get",
    "get_units_magnitudes",
    "post_convert_convert_post",
    "list_currencies_currencies_get",
    "get_currency_rate_currencies_rate_get",
    "post_convert_currency_currencies_convert_post",
    "post_refresh_rates_currencies_refresh_post",
    "get_parse_compound_convert_compound_parse_get",
    "post_convert_compound_convert_compound_post",
    "get_history_history_get",
    "get_favorites_history_favorites_get",
    "post_record_conversion_history_record_post",
    "post_add_favorite_history_favorites_post",
    "delete_history_history_delete",
    "post_add_custom_unit_units_custom_post",
})


def test_mcp_tool_exact_names_16():
    """Verify the exact 16 MCP tool names derived from all FastAPI routes."""
    try:
        from unit_converter.api.mcp_server import mcp
    except Exception as exc:
        pytest.skip(f"MCP server not importable: {exc}")

    try:
        tools = asyncio.run(mcp.list_tools())
        tool_names = frozenset(
            t.name if hasattr(t, "name") else str(t) for t in tools
        )
        assert tool_names == _EXPECTED_TOOL_NAMES_16, (
            f"MCP tool names mismatch.\n"
            f"Expected: {sorted(_EXPECTED_TOOL_NAMES_16)}\n"
            f"Actual:   {sorted(tool_names)}"
        )
    except Exception as exc:
        pytest.skip(f"MCP introspection failed: {exc}")
