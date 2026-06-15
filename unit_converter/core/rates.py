"""
unit_converter.core.rates
==========================
Live currency exchange rate fetching and caching for the Currency magnitude
(UC-I05).

Design
------
- Primary source: Frankfurter (https://api.frankfurter.dev/v1/latest), keyless,
  MIT-licensed, ECB euro reference rates.  No new dependency: uses stdlib
  ``urllib.request`` + ``json``.
- Fallback source: a bundled snapshot committed with the package
  (``unit_converter/data/currency_snapshot.json``), labelled as approximate
  and dated.
- Cache file: ``~/.unit-converter/currency_cache.json`` — the full dated rate
  table.  Staleness window: ~24 hours (one ECB business day).
- Offline graceful degradation: if the network is unavailable, conversion uses
  the last cached table (with a ``is_stale`` flag set in the return value so
  the caller can surface a "rates as of <date>" indicator).
- Cross-rate computation: all rates are stored relative to a single base (USD).
  ``rate(A→B) = rates[B] / rates[A]`` avoids multiple network calls.

Public API
----------
fetch_rates(base="USD", timeout=10) -> dict
    Fetch live rates from Frankfurter.  Returns the raw API response dict.
    Raises ``urllib.error.URLError`` or ``socket.timeout`` on network failure.

load_rates(custom_cache_path=None) -> RatesResult
    Return a ``RatesResult`` (rates dict, date string, is_stale flag).
    Tries the cache first; fetches and refreshes if stale.  Never blocks
    conversion on network failure.

get_rate(from_code, to_code, rates_result=None) -> float
    Compute the cross-rate A→B from a single-base rate table.

list_currencies(rates_result=None) -> list[str]
    Return sorted list of supported ISO 4217 currency codes.

refresh_rates(custom_cache_path=None) -> RatesResult
    Force a fresh fetch and update the cache.  Raises on network failure.
"""

from __future__ import annotations

import functools
import json
import logging
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
_DEFAULT_BASE = "USD"
_STALENESS_SECONDS = 86_400  # 24 hours
_FETCH_TIMEOUT = 10           # seconds
_USER_AGENT = "Unit-Converter/1.1 (github.com/JuanGSanchez/Unit-Converter)"

# Path to the bundled offline fallback snapshot (shipped with the package).
_BUNDLE_SNAPSHOT = Path(__file__).parent.parent / "data" / "currency_snapshot.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RatesResult:
    """
    The result of a rate-load operation.

    Attributes
    ----------
    rates:
        ``{"USD": 1.0, "EUR": 0.864, ...}`` — rates relative to *base*.
    base:
        The base currency code (typically ``"USD"``).
    date:
        The effective date string from the API (e.g. ``"2026-06-12"``).
    is_stale:
        ``True`` if the rates come from an old cache (>24 h) or from the
        bundled offline snapshot.
    source:
        One of ``"live"``, ``"cache"``, ``"stale_cache"``, ``"bundle"``.
    """
    rates: dict[str, float] = field(default_factory=dict)
    base: str = _DEFAULT_BASE
    date: str = ""
    is_stale: bool = False
    source: str = "bundle"


# ---------------------------------------------------------------------------
# Cache file path
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _cache_path(custom: Optional[Path] = None) -> Path:
    """Return the currency cache file path, caching the result per argument value.

    ``Path.home()`` resolution and the ``mkdir`` syscall are performed at most
    once per distinct *custom* value (including ``None``).  ``Path`` is
    hashable so ``lru_cache`` works correctly here.  ``mkdir(exist_ok=True)``
    is idempotent — calling it only once is safe.
    """
    user_dir = Path.home() / ".unit-converter"
    user_dir.mkdir(parents=True, exist_ok=True)
    return Path(custom) if custom is not None else user_dir / "currency_cache.json"


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------

def fetch_rates(base: str = _DEFAULT_BASE, timeout: int = _FETCH_TIMEOUT) -> dict:
    """
    Fetch live rates from Frankfurter /v1/latest.

    Returns
    -------
    dict
        Raw API response: ``{"amount": 1.0, "base": "USD", "date": "...",
        "rates": {"EUR": 0.86, ...}}``.

    Raises
    ------
    urllib.error.URLError
        On DNS/connection failure.
    socket.timeout
        If the server does not respond within *timeout* seconds.
    ValueError
        If the response JSON is structurally unexpected.
    """
    url = f"{_FRANKFURTER_URL}?base={base}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if "rates" not in data:
        raise ValueError(f"Unexpected Frankfurter response: {raw[:200]}")
    # Ensure the base currency itself is in the rates dict as 1.0
    data["rates"].setdefault(base, 1.0)
    return data


# ---------------------------------------------------------------------------
# Cache read/write
# ---------------------------------------------------------------------------

def _read_cache(path: Path) -> Optional[dict]:
    """Read and parse the cache JSON.  Returns None if missing or corrupt."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_cache(path: Path, api_response: dict) -> None:
    """Write the API response + a local fetch timestamp to the cache file."""
    payload = dict(api_response)
    payload["_fetched_at"] = time.time()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _cache_is_fresh(cache: dict) -> bool:
    """Return True if the cache was fetched within the staleness window."""
    fetched_at = cache.get("_fetched_at", 0)
    return (time.time() - fetched_at) < _STALENESS_SECONDS


# ---------------------------------------------------------------------------
# Bundled snapshot
# ---------------------------------------------------------------------------

def _load_bundle() -> Optional[dict]:
    """Load the bundled offline snapshot.  Returns None if not present."""
    try:
        text = _BUNDLE_SNAPSHOT.read_text(encoding="utf-8")
        return json.loads(text)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_rates(custom_cache_path: Optional[Path] = None) -> RatesResult:
    """
    Return a ``RatesResult`` with current exchange rates.

    Load order:
    1. Fresh cache (< 24 h old) — returns immediately.
    2. Stale cache — attempts a live fetch; falls back to stale cache on error.
    3. No cache — attempts a live fetch; falls back to bundled snapshot.
    4. No network + no cache — uses bundled snapshot (marked stale).

    Never raises on network failure; always returns a usable ``RatesResult``.
    """
    path = _cache_path(custom_cache_path)
    cache = _read_cache(path)

    # Case 1: fresh cache
    if cache is not None and _cache_is_fresh(cache):
        rates = dict(cache.get("rates", {}))
        rates.setdefault(cache.get("base", _DEFAULT_BASE), 1.0)
        return RatesResult(
            rates=rates,
            base=cache.get("base", _DEFAULT_BASE),
            date=cache.get("date", ""),
            is_stale=False,
            source="cache",
        )

    # Case 2 / 3: attempt live fetch
    try:
        api_resp = fetch_rates()
        _write_cache(path, api_resp)
        rates = dict(api_resp["rates"])
        rates.setdefault(api_resp.get("base", _DEFAULT_BASE), 1.0)
        return RatesResult(
            rates=rates,
            base=api_resp.get("base", _DEFAULT_BASE),
            date=api_resp.get("date", ""),
            is_stale=False,
            source="live",
        )
    except (urllib.error.URLError, socket.timeout, ValueError, OSError) as exc:
        logger.warning("Currency rate fetch failed (%s); using fallback.", exc)

    # Case 2 fallback: stale cache
    if cache is not None:
        rates = dict(cache.get("rates", {}))
        rates.setdefault(cache.get("base", _DEFAULT_BASE), 1.0)
        return RatesResult(
            rates=rates,
            base=cache.get("base", _DEFAULT_BASE),
            date=cache.get("date", ""),
            is_stale=True,
            source="stale_cache",
        )

    # Case 4: bundled snapshot
    bundle = _load_bundle()
    if bundle is not None:
        rates = dict(bundle.get("rates", {}))
        rates.setdefault(bundle.get("base", _DEFAULT_BASE), 1.0)
        return RatesResult(
            rates=rates,
            base=bundle.get("base", _DEFAULT_BASE),
            date=bundle.get("date", ""),
            is_stale=True,
            source="bundle",
        )

    # Absolute last resort: return an empty result so the caller can degrade
    return RatesResult(is_stale=True, source="bundle")


def refresh_rates(custom_cache_path: Optional[Path] = None) -> RatesResult:
    """
    Force a live fetch, update the cache, and return the new ``RatesResult``.

    Raises
    ------
    urllib.error.URLError / socket.timeout
        On network failure (unlike ``load_rates`` which degrades gracefully).
    """
    api_resp = fetch_rates()
    path = _cache_path(custom_cache_path)
    _write_cache(path, api_resp)
    rates = dict(api_resp["rates"])
    rates.setdefault(api_resp.get("base", _DEFAULT_BASE), 1.0)
    return RatesResult(
        rates=rates,
        base=api_resp.get("base", _DEFAULT_BASE),
        date=api_resp.get("date", ""),
        is_stale=False,
        source="live",
    )


def get_rate(
    from_code: str,
    to_code: str,
    rates_result: Optional[RatesResult] = None,
) -> float:
    """
    Compute the cross-rate from *from_code* to *to_code*.

    Uses ``rate(A→B) = rates[B] / rates[A]`` from a single-base table so
    only one network call is needed regardless of the currency pair.

    Parameters
    ----------
    from_code, to_code:
        ISO 4217 currency codes (e.g. ``"USD"``, ``"EUR"``).
    rates_result:
        A ``RatesResult`` to use.  If ``None``, calls ``load_rates()``.

    Returns
    -------
    float
        Exchange rate: 1 *from_code* expressed in *to_code*.

    Raises
    ------
    KeyError
        If either code is not in the rate table.
    """
    if rates_result is None:
        rates_result = load_rates()
    rates = rates_result.rates
    if from_code not in rates:
        raise KeyError(f"Currency code {from_code!r} not in rate table.")
    if to_code not in rates:
        raise KeyError(f"Currency code {to_code!r} not in rate table.")
    return rates[to_code] / rates[from_code]


def list_currencies(rates_result: Optional[RatesResult] = None) -> list[str]:
    """
    Return the sorted list of supported ISO 4217 currency codes.

    Parameters
    ----------
    rates_result:
        A ``RatesResult`` to use.  If ``None``, calls ``load_rates()``.
    """
    if rates_result is None:
        rates_result = load_rates()
    return sorted(rates_result.rates.keys())
