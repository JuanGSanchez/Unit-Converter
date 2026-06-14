"""
tests/test_api_smoke.py
=======================
Optional smoke tests for the REST API and MCP tool interface.

These tests require httpx, fastapi, and fastmcp to be importable.
If any of those dependencies are absent, the entire module is skipped —
the core coverage gate does NOT depend on these tests.
"""
from __future__ import annotations

import importlib
import pytest

# ---------------------------------------------------------------------------
# Dependency check — skip the whole module if httpx / fastapi / fastmcp absent
# ---------------------------------------------------------------------------

def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


_DEPS_AVAILABLE = all(_importable(m) for m in ("httpx", "fastapi", "fastmcp"))

pytestmark = pytest.mark.skipif(
    not _DEPS_AVAILABLE,
    reason="httpx/fastapi/fastmcp not installed — API smoke tests skipped",
)


# ---------------------------------------------------------------------------
# REST smoke tests (only reached if deps are present)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Return an httpx TestClient wrapping the FastAPI app."""
    from httpx import ASGITransport, AsyncClient
    from unit_converter.api.main import app
    # Return config dict; tests construct the client themselves to stay sync-friendly
    return app


def test_rest_list_magnitudes(client):
    import asyncio
    from httpx import ASGITransport, AsyncClient

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            resp = await ac.get("/magnitudes")
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "Mass" in data


def test_rest_list_units(client):
    import asyncio
    from httpx import ASGITransport, AsyncClient

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            resp = await ac.get("/magnitudes/Mass/units")
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code == 200
    data = resp.json()
    assert "units" in data
    assert "base_unit" in data


def test_rest_convert(client):
    import asyncio
    from httpx import ASGITransport, AsyncClient

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/convert",
                json={
                    "magnitude": "Mass",
                    "value": 453.6,
                    "from_unit": "gram (g)",
                    "to_unit": "Av. pound (lb)",
                },
            )
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert abs(data["result"] - 1.0) < 1e-4


def test_rest_unknown_magnitude_returns_error(client):
    import asyncio
    from httpx import ASGITransport, AsyncClient

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/convert",
                json={
                    "magnitude": "NoSuchMagnitude",
                    "value": 1.0,
                    "from_unit": "x",
                    "to_unit": "y",
                },
            )
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code in (400, 422)

