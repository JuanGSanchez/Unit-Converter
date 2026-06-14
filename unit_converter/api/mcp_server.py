"""
unit_converter.api.mcp_server
==============================
FastMCP server derived from the REST FastAPI app.

This module creates the MCP server from the **same** ``rest.app`` FastAPI
application, ensuring zero logic duplication (F-single-core principle).
FastMCP introspects the FastAPI routes and auto-generates MCP tools from them.

MCP tools exposed
-----------------
health          — liveness + version (from GET /health).
get_magnitudes  — list magnitude names (from GET /magnitudes).
get_units       — list units for a magnitude (from GET /magnitudes/{magnitude}/units).
post_convert    — perform a conversion (from POST /convert).

Transports
----------
Streamable HTTP: ``mcp_app`` (ASGI app) mounted at ``/mcp`` by ``main.py``.
stdio:           run this module directly — ``python -m unit_converter.api.mcp_server``
                 — or via the ``unit-converter-mcp`` console script.

ValueError propagation
----------------------
FastMCP propagates HTTP 422 responses from the underlying FastAPI layer as
structured MCP tool errors (``isError: true`` with the ``detail`` field from
the 422 body), so the core's ``ValueError`` messages reach the MCP client
in a structured form.
"""
from __future__ import annotations

from fastmcp import FastMCP

from unit_converter.api.rest import app as _rest_app

# ---------------------------------------------------------------------------
# Create the MCP server from the REST app (single-core dual-interface pattern).
# FastMCP.from_fastapi() introspects the FastAPI route table and generates one
# MCP tool per route, delegating execution back to the FastAPI app.
# ---------------------------------------------------------------------------

mcp: FastMCP = FastMCP.from_fastapi(
    app=_rest_app,
    name="Unit-Converter MCP",
)

# ASGI app for Streamable HTTP transport.
# transport="streamable-http" is set explicitly (research limitation L3:
# confirm default at implementation time — we confirm it here and pin it).
mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")


# ---------------------------------------------------------------------------
# stdio entry point
# ---------------------------------------------------------------------------

def run_stdio() -> None:  # pragma: no cover
    """Run the MCP server over stdio (for CLI/agent clients).

    Invoked by the ``unit-converter-mcp`` console script or directly::

        python -m unit_converter.api.mcp_server
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    run_stdio()
