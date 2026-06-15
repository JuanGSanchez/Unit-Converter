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
GET  /currencies                       — list supported ISO 4217 currency codes.
GET  /currencies/rate                  — get exchange rate for a currency pair.
POST /currencies/convert               — convert an amount between currencies.
POST /currencies/refresh               — force-refresh the exchange rate cache.
POST /convert/compound                 — convert a value using compound unit exprs.
GET  /convert/compound/parse           — parse a compound unit expression.
GET  /history                          — retrieve conversion history.
GET  /history/favorites                — retrieve favorited history entries.
POST /history/record                   — append a conversion to history.
POST /history/favorites                — mark a history entry as a favorite.
DELETE /history                        — clear all history.
POST /units/custom                     — add a custom unit to the user database.

All routes delegate entirely to ``unit_converter.api.service``.
Error mapping:
  ValueError / subclasses              → HTTP 422
  KeyError (unknown currency code)     → HTTP 404
  urllib.error.URLError / socket.timeout → HTTP 503

This module exposes a bare ``FastAPI`` instance (``app``).  It is **not**
combined with the MCP routes here — that composition happens in ``main.py``
so this module stays importable and testable without the MCP stack.
"""
from __future__ import annotations

import socket
import urllib.error
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

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
    sig_figs: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Optional positive integer: round the result to this many "
            "significant figures.  Omit (null) to preserve full precision."
        ),
    )

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
                    "sig_figs": None,
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


# The health response is pure static data: ``status`` is always ``"ok"`` and
# ``__version__`` is fixed at import time.  Construct once to avoid allocating
# a new Pydantic model instance on every GET /health call.
_HEALTH_RESPONSE = HealthResponse(status="ok", version=__version__)


class CurrencyRateResponse(BaseModel):
    """Result of GET /currencies/rate."""

    from_currency: str = Field(alias="from")
    to_currency: str = Field(alias="to")
    rate: float
    date: str
    is_stale: bool

    model_config = {"populate_by_name": True}


class ConvertCurrencyRequest(BaseModel):
    """Body for POST /currencies/convert."""

    value: float = Field(ge=0, description="Amount to convert (must be non-negative).")
    from_currency: str = Field(alias="from", description="Source ISO 4217 code.")
    to_currency: str = Field(alias="to", description="Target ISO 4217 code.")

    model_config = {"populate_by_name": True}


class ConvertCurrencyResponse(BaseModel):
    """Result of POST /currencies/convert."""

    result: float
    rate: float
    date: str
    is_stale: bool


class RefreshRatesResponse(BaseModel):
    """Result of POST /currencies/refresh."""

    date: str
    base: str
    currency_count: int
    source: str


class CompoundConvertRequest(BaseModel):
    """Body for POST /convert/compound."""

    value: float
    from_expr: str = Field(description="Source compound unit expression, e.g. 'km/h'.")
    to_expr: str = Field(description="Target compound unit expression, e.g. 'm/s'.")


class CompoundConvertResponse(BaseModel):
    """Result of POST /convert/compound."""

    result: float
    from_expr: str
    to_expr: str


class ParseCompoundResponse(BaseModel):
    """Result of GET /convert/compound/parse."""

    expr: str
    factor: float
    dimensions: dict


class HistoryEntryResponse(BaseModel):
    """A single conversion history record."""

    magnitude: str
    from_unit: str
    to_unit: str
    from_order: str
    to_order: str
    value: float
    result: float
    sig_figs: Optional[int]
    timestamp: str
    favorite: bool
    favorite_label: str


class RecordConversionRequest(BaseModel):
    """Body for POST /history/record."""

    magnitude: str
    value: float
    from_unit: str
    to_unit: str
    result: float
    from_order: str = "1"
    to_order: str = "1"
    sig_figs: Optional[int] = Field(default=None, ge=1)


class AddFavoriteRequest(BaseModel):
    """Body for POST /history/favorites."""

    timestamp: str = Field(description="ISO-8601 UTC timestamp of the entry to mark.")
    label: str = Field(default="", description="Optional human-readable label.")


class AddFavoriteResponse(BaseModel):
    """Result of POST /history/favorites."""

    marked: bool
    timestamp: str


class AddCustomUnitRequest(BaseModel):
    """Body for POST /units/custom."""

    magnitude: str = Field(description="Name of an existing magnitude (e.g. 'Mass').")
    unit_name: str = Field(description="Name for the new unit.")
    factor: float = Field(
        gt=0,
        description="Conversion factor relative to the magnitude's base unit. Must be positive and finite.",
    )


class AddCustomUnitResponse(BaseModel):
    """Result of POST /units/custom."""

    magnitude: str
    unit_name: str
    factor: float


class ClearedResponse(BaseModel):
    """Result of DELETE /history."""

    cleared: bool


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _value_error_to_422(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )


def _key_error_to_404(exc: KeyError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


def _network_error_to_503(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Upstream rate service unavailable: {exc}",
    )


# ---------------------------------------------------------------------------
# Routes — existing (health, magnitudes, convert)
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and version check",
    tags=["meta"],
)
def health() -> HealthResponse:
    """Return a liveness confirmation and the package version."""
    return _HEALTH_RESPONSE


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
            body.sig_figs,
        )
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return ConvertResponse(result=result)


# ---------------------------------------------------------------------------
# Routes — currency
# ---------------------------------------------------------------------------


@app.get(
    "/currencies",
    response_model=list[str],
    summary="List supported currency codes",
    tags=["currency"],
)
def list_currencies() -> list[str]:
    """Return the sorted list of supported ISO 4217 currency codes.

    Uses the cached/live Frankfurter rate table; falls back to the bundled
    offline snapshot if the network is unavailable.
    """
    return service.list_currencies()


@app.get(
    "/currencies/rate",
    response_model=CurrencyRateResponse,
    summary="Get exchange rate for a currency pair",
    tags=["currency"],
)
def get_currency_rate(
    from_currency: str = Query(alias="from", description="Source ISO 4217 code."),
    to_currency: str = Query(alias="to", description="Target ISO 4217 code."),
) -> CurrencyRateResponse:
    """Return the exchange rate from *from* to *to*.

    Raises HTTP 404 if either code is not in the rate table.
    """
    try:
        data = service.get_rate(from_currency, to_currency)
    except KeyError as exc:
        raise _key_error_to_404(exc) from exc
    return CurrencyRateResponse(**{
        "from": data["from"],
        "to": data["to"],
        "rate": data["rate"],
        "date": data["date"],
        "is_stale": data["is_stale"],
    })


@app.post(
    "/currencies/convert",
    response_model=ConvertCurrencyResponse,
    summary="Convert an amount between currencies",
    tags=["currency"],
)
def post_convert_currency(body: ConvertCurrencyRequest) -> ConvertCurrencyResponse:
    """Convert *value* from *from* currency to *to* currency.

    Uses the cached/live exchange rate.  Raises HTTP 404 if either code is
    unknown; HTTP 422 if *value* is invalid.
    """
    try:
        data = service.convert_currency(
            body.value,
            body.from_currency,
            body.to_currency,
        )
    except KeyError as exc:
        raise _key_error_to_404(exc) from exc
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return ConvertCurrencyResponse(**data)


@app.post(
    "/currencies/refresh",
    response_model=RefreshRatesResponse,
    summary="Force-refresh the exchange rate cache",
    tags=["currency"],
)
def post_refresh_rates() -> RefreshRatesResponse:
    """Fetch fresh exchange rates from Frankfurter and update the local cache.

    Raises HTTP 503 if the upstream API is unreachable.
    """
    try:
        data = service.refresh_rates()
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise _network_error_to_503(exc) from exc
    return RefreshRatesResponse(**data)


# ---------------------------------------------------------------------------
# Routes — compound unit conversion
# ---------------------------------------------------------------------------


@app.get(
    "/convert/compound/parse",
    response_model=ParseCompoundResponse,
    summary="Parse a compound unit expression",
    tags=["conversion"],
)
def get_parse_compound(
    expr: str = Query(description="Compound unit expression, e.g. 'km/h', 'kg*m/s^2'."),
) -> ParseCompoundResponse:
    """Parse *expr* and return its factor and dimension vector.

    Raises HTTP 422 on syntax errors or unknown unit atoms.
    """
    try:
        data = service.parse_compound(expr)
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return ParseCompoundResponse(**data)


@app.post(
    "/convert/compound",
    response_model=CompoundConvertResponse,
    summary="Convert a value using compound unit expressions",
    tags=["conversion"],
)
def post_convert_compound(body: CompoundConvertRequest) -> CompoundConvertResponse:
    """Convert *value* from *from_expr* to *to_expr*.

    Raises HTTP 422 on dimension mismatches, unknown unit atoms, or syntax
    errors in either expression.
    """
    try:
        data = service.convert_compound(body.value, body.from_expr, body.to_expr)
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return CompoundConvertResponse(**data)


# ---------------------------------------------------------------------------
# Routes — history
# ---------------------------------------------------------------------------


@app.get(
    "/history",
    response_model=list[HistoryEntryResponse],
    summary="Retrieve conversion history",
    tags=["history"],
)
def get_history() -> list[HistoryEntryResponse]:
    """Return the full conversion history, most-recent-first."""
    return [HistoryEntryResponse(**e) for e in service.load_history()]


@app.get(
    "/history/favorites",
    response_model=list[HistoryEntryResponse],
    summary="Retrieve favorited history entries",
    tags=["history"],
)
def get_favorites() -> list[HistoryEntryResponse]:
    """Return only history entries marked as favorites, most-recent-first."""
    return [HistoryEntryResponse(**e) for e in service.list_favorites()]


@app.post(
    "/history/record",
    response_model=HistoryEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a conversion in history",
    tags=["history"],
)
def post_record_conversion(body: RecordConversionRequest) -> HistoryEntryResponse:
    """Append a completed conversion to the history file.

    Raises HTTP 422 if required fields are empty or *sig_figs* is invalid.
    """
    try:
        data = service.record_conversion(
            body.magnitude,
            body.value,
            body.from_unit,
            body.to_unit,
            body.result,
            from_order=body.from_order,
            to_order=body.to_order,
            sig_figs=body.sig_figs,
        )
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return HistoryEntryResponse(**data)


@app.post(
    "/history/favorites",
    response_model=AddFavoriteResponse,
    summary="Mark a history entry as a favorite",
    tags=["history"],
)
def post_add_favorite(body: AddFavoriteRequest) -> AddFavoriteResponse:
    """Mark the history entry identified by *timestamp* as a favorite.

    Raises HTTP 422 if *timestamp* is empty or no matching entry exists.
    """
    try:
        service.add_favorite_by_timestamp(body.timestamp, body.label)
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return AddFavoriteResponse(marked=True, timestamp=body.timestamp)


@app.delete(
    "/history",
    response_model=ClearedResponse,
    summary="Clear all conversion history",
    tags=["history"],
)
def delete_history() -> ClearedResponse:
    """Delete all conversion history entries."""
    data = service.clear_history()
    return ClearedResponse(**data)


# ---------------------------------------------------------------------------
# Routes — custom units
# ---------------------------------------------------------------------------


@app.post(
    "/units/custom",
    response_model=AddCustomUnitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a custom unit",
    tags=["units"],
)
def post_add_custom_unit(body: AddCustomUnitRequest) -> AddCustomUnitResponse:
    """Persist a new custom unit to the user's custom units file.

    Input validation applied at the boundary:
    - *unit_name* must be non-empty, ≤ 120 chars, free of control characters,
      path separators, and TOML structural characters.
    - *factor* must be a positive finite number (enforced by Pydantic ``gt=0``
      and the service-layer finite check).

    Raises HTTP 422 on any validation failure.
    """
    try:
        data = service.add_custom_unit(body.magnitude, body.unit_name, body.factor)
    except ValueError as exc:
        raise _value_error_to_422(exc) from exc
    return AddCustomUnitResponse(**data)
