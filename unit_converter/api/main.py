"""
unit_converter.api.main
========================
Combined ASGI application: REST routes + MCP at ``/mcp``.

This is the **single runnable entry point** for the access layer.  It
stitches together the FastAPI REST app (``rest.app``) and the FastMCP ASGI
app (``mcp_server.mcp_app``) into one ``FastAPI`` instance served by a
single uvicorn process.

Architecture
------------
  rest.app          — the FastAPI REST app (routes: /health, /magnitudes, /convert)
  mcp_server.mcp_app — the FastMCP ASGI app (Streamable HTTP at /mcp)
  combined_app      — this module's ``app``: all routes merged, MCP lifespan forwarded

The MCP lifespan is forwarded to ``combined_app`` as required by FastMCP
(it starts the internal MCP session manager).

Run commands
------------
HTTP server (REST + MCP Streamable HTTP)::

    uvicorn unit_converter.api.main:app --host 127.0.0.1 --port 8000

(``--host 127.0.0.1`` is loopback-only, matching the default bind; pass
``--host 0.0.0.0`` only to expose the server on all network interfaces.)

or via the ``unit-converter-api`` console script::

    unit-converter-api

stdio MCP client::

    unit-converter-mcp

Endpoints after startup
-----------------------
REST:
  GET  http://localhost:8000/health
  GET  http://localhost:8000/magnitudes
  GET  http://localhost:8000/magnitudes/{magnitude}/units
  POST http://localhost:8000/convert

MCP (Streamable HTTP):
  http://localhost:8000/mcp

Interactive docs (FastAPI auto-generated):
  http://localhost:8000/docs
  http://localhost:8000/redoc
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from unit_converter import __version__
from unit_converter.api.mcp_server import mcp_app
from unit_converter.api.rest import app as _rest_app

# ---------------------------------------------------------------------------
# Combine REST routes + MCP routes in one ASGI app.
# The MCP lifespan MUST be forwarded — it starts the FastMCP session manager
# (required per research Finding F1.4 / gofastmcp.com/integrations/fastapi).
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Unit-Converter (REST + MCP)",
    version=__version__,
    description=(
        "Combined REST + MCP access layer for the Unit-Converter package. "
        "REST routes are served directly; MCP (Streamable HTTP) is at /mcp."
    ),
    lifespan=mcp_app.lifespan,  # REQUIRED: starts the MCP session manager
)

# Mount all routes from both apps into the combined app.
for route in mcp_app.routes:
    app.routes.append(route)
for route in _rest_app.routes:
    app.routes.append(route)


# ---------------------------------------------------------------------------
# Console-script entry point (unit-converter-api)
# ---------------------------------------------------------------------------

def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover
    """Start the uvicorn server.

    Invoked by the ``unit-converter-api`` console script.

    Parameters
    ----------
    host:
        Interface to bind.  Defaults to ``127.0.0.1`` (loopback only —
        appropriate for a single-user local tool).  Pass ``"0.0.0.0"`` to
        expose to all network interfaces, e.g. for LAN access.
    port:
        TCP port.  Default ``8000``.
    """
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    run_server()
