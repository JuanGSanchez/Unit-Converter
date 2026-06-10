"""
unit_converter.api.rest
========================
FastAPI REST application over the shared ``service`` module.

Routes
------
GET  /health                           — liveness + version.
GET  /magnitudes                       — list all magnitude names.
GET  /magnitudes/{magnitude}/units     — list units for a magnitude.
POST /convert                          — perform a unit conversion.

All routes delegate entirely to ``unit_converter.api.service``.
``ValueError`` from the service is mapped to HTTP 422 (Unprocessable Entity)
with a structured JSON body: ``{"detail": "<error message>"}``.

This module exposes a bare ``FastAPI`` instance (``app``).  It is **not**
combined with the MCP routes here — that composition happens in ``main.py``
so this module stays importable and testable without the MCP stack.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from unit_converter import __version__
from unit_converter.api import service

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Unit-Converter REST API",
    version=__version__,
    description=(
        "REST interface over the Unit-Converter pure core. "
        "External agents can drive all conversion operations without launching the GUI."
    ),
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ConvertRequest(BaseModel):
    """Body for POST /convert."""

    magnitude: str
    value: float
    from_unit: str
    to_unit: str
    from_order: str = "1"
    to_order: str = "1"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "magnitude": "Mass",
                    "value": 1.0,
                    "from_unit": "Av. pound (lb)",
                    "to_unit": "gram (g)",
                    "from_order": "1",
                    "to_order": "1",
                }
            ]
        }
    }


class ConvertResponse(BaseModel):
    """Result of POST /convert."""

    result: float


class UnitsResponse(BaseModel):
    """Result of GET /magnitudes/{magnitude}/units."""

    units: list[str]
    base_unit: str


class HealthResponse(BaseModel):
    """Result of GET /health."""

    status: str
    version: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _value_error_to_422(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and version check",
    tags=["meta"],
)
def health() -> HealthResponse:
    """Return a liveness confirmation and the package version."""
    return HealthResponse(status="ok", version=__version__)


@app.get(
    "/magnitudes",
    response_model=list[str],
    summary="List all available magnitudes",
    tags=["discovery"],
)
def get_magnitudes() -> list[str]:
    """Return the sorted list of all magnitude names known to the converter."""
    return service.list_magnitudes()


@app.get(
    "/magnitudes/{magnitude}/units",
    response_model=UnitsResponse,
    summary="List units for a magnitude",
    tags=["discovery"],
)
def get_units(magnitude: str) -> UnitsResponse:
    """Return the units and base unit for *magnitude*.

    Raises HTTP 422 if *magnitude* is not in the database.
    """
    try:
        data = service.list_units(magnitude)
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return UnitsResponse(**data)


@app.post(
    "/convert",
    response_model=ConvertResponse,
    summary="Convert a value between units",
    tags=["conversion"],
)
def post_convert(body: ConvertRequest) -> ConvertResponse:
    """Convert *value* from *from_unit* to *to_unit* within *magnitude*.

    ``from_order`` and ``to_order`` are SI/IEC prefix keys (e.g. ``"k"``,
    ``"M"``); default ``"1"`` means no prefix.

    Raises HTTP 422 on unknown magnitude, unit, or order key.
    """
    try:
        result = service.convert(
            body.magnitude,
            body.value,
            body.from_unit,
            body.to_unit,
            body.from_order,
            body.to_order,
        )
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return ConvertResponse(result=result)
