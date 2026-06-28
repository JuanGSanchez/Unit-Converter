"""
unit_converter.gui.unit_search
================================
Pure, Qt-free search module for SPEC-14 (unit and magnitude search).

This module is intentionally free of any Qt/PySide6 imports so it can be
unit-tested headlessly without a display.

Public API
----------
``SearchHit``
    Frozen dataclass with fields ``magnitude: str`` and ``unit: str``.

``build_search_index(list_magnitudes, list_units) -> list[SearchHit]``
    Dependency-injected: accepts the two callables from
    ``unit_converter.core.converter`` (or test stubs).  Returns a flat list of
    all (magnitude, unit) pairs ordered by magnitude then by unit position.
    Builds once; the caller is responsible for caching.

``search(index, query, limit=50) -> list[SearchHit]``
    Case-AND-accent-insensitive substring match against both the unit string
    and the magnitude name.  Normalises accents via ``unicodedata.normalize``
    (NFKD) + strips combining marks so that e.g. "angstrom" matches
    "Ångström".

    Ordering guarantee (deterministic):
    1. Exact match on the *normalised* unit string (priority 0).
    2. Prefix match on the normalised unit string (priority 1).
    3. Substring match on the normalised unit string (priority 2).
    4. Exact match on the normalised magnitude name (priority 3).
    5. Prefix match on the normalised magnitude name (priority 4).
    6. Substring match on the normalised magnitude name (priority 5).
    Within each priority tier, hits are sorted alphabetically by magnitude
    then by unit (case-insensitive) for full determinism.

    Empty query returns an empty list ``[]`` (documented behaviour; callers
    that want "show all" should display the full index instead).

Notes
-----
- No GUI imports.  Import this module in tests without ``QApplication``.
- The caller (``_SearchDialog`` in ``main_window.py``) builds the index once
  at first use and caches it on the ``MainWindow`` instance, per SPEC-21.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchHit:
    """
    A single searchable entry pairing a magnitude with one of its units.

    Both fields are the exact strings returned by the core API
    (``list_magnitudes()`` and ``list_units(magnitude)["units"]``).
    """

    magnitude: str
    unit: str


# ---------------------------------------------------------------------------
# Normalisation helper
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """
    Return a case-folded, accent-stripped version of *text* for matching.

    Steps
    -----
    1. ``unicodedata.normalize("NFKD", text)`` — decompose accents into base
       character + combining mark.
    2. Strip all Unicode combining marks (category ``Mn``).
    3. ``casefold()`` — aggressive case-folding (handles ligatures and sharp-S).

    Examples
    --------
    >>> _normalize("Ångström")
    'angstrom'
    >>> _normalize("GRAM")
    'gram'
    >>> _normalize("café")
    'cafe'
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(
        ch for ch in decomposed if unicodedata.category(ch) != "Mn"
    )
    return stripped.casefold()


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

def build_search_index(
    list_magnitudes_fn: Callable[[], list[str]],
    list_units_fn: Callable[[str], dict],
) -> list[SearchHit]:
    """
    Build a flat search index from the core's discovery callables.

    Parameters
    ----------
    list_magnitudes_fn:
        A zero-argument callable that returns ``list[str]`` of magnitude
        names (e.g. ``unit_converter.core.converter.list_magnitudes``).
    list_units_fn:
        A one-argument callable ``(magnitude: str) -> dict`` whose ``"units"``
        key holds ``list[str]`` of unit display names
        (e.g. ``unit_converter.core.converter.list_units``).

    Returns
    -------
    list[SearchHit]
        One ``SearchHit`` per (magnitude, unit) pair, in the order returned
        by the core — i.e. magnitudes in ``list_magnitudes_fn()`` order,
        units in ``list_units_fn(magnitude)["units"]`` order.
        The caller is responsible for caching this result.

    Notes
    -----
    - Unknown magnitudes or empty unit lists are silently skipped.
    - No Qt dependency; safe to call from tests without ``QApplication``.
    """
    hits: list[SearchHit] = []
    try:
        magnitudes = list_magnitudes_fn()
    except Exception:
        return hits

    for magnitude in magnitudes:
        try:
            units_info = list_units_fn(magnitude)
            units = units_info.get("units", [])
        except Exception:
            continue
        for unit in units:
            hits.append(SearchHit(magnitude=magnitude, unit=unit))

    return hits


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search(
    index: list[SearchHit],
    query: str,
    limit: int = 50,
) -> list[SearchHit]:
    """
    Search *index* for hits matching *query* (case-and-accent-insensitive).

    Parameters
    ----------
    index:
        The flat list returned by :func:`build_search_index`.
    query:
        The search string typed by the user.  An empty string (after
        stripping) returns ``[]`` — callers that want "show all" should
        display the full index instead.
    limit:
        Maximum number of results returned (default 50).

    Returns
    -------
    list[SearchHit]
        Matching hits ordered by priority (exact > prefix > substring) within
        the unit field first, then the magnitude field; ties broken
        alphabetically.  At most *limit* hits are returned.

    Ordering
    --------
    Priority 0 — exact match on normalised unit string.
    Priority 1 — prefix match on normalised unit string.
    Priority 2 — substring match on normalised unit string.
    Priority 3 — exact match on normalised magnitude name.
    Priority 4 — prefix match on normalised magnitude name.
    Priority 5 — substring match on normalised magnitude name.
    Within each tier, alphabetical by ``(magnitude.lower(), unit.lower())``.
    """
    stripped = query.strip()
    if not stripped:
        return []

    norm_query = _normalize(stripped)

    # Assign each matching hit a priority bucket
    buckets: list[list[SearchHit]] = [[] for _ in range(6)]

    for hit in index:
        norm_unit = _normalize(hit.unit)
        norm_mag = _normalize(hit.magnitude)

        if norm_unit == norm_query:
            buckets[0].append(hit)
        elif norm_unit.startswith(norm_query):
            buckets[1].append(hit)
        elif norm_query in norm_unit:
            buckets[2].append(hit)
        elif norm_mag == norm_query:
            buckets[3].append(hit)
        elif norm_mag.startswith(norm_query):
            buckets[4].append(hit)
        elif norm_query in norm_mag:
            buckets[5].append(hit)

    # Sort each bucket alphabetically for determinism
    def _sort_key(h: SearchHit) -> tuple[str, str]:
        return (h.magnitude.lower(), h.unit.lower())

    results: list[SearchHit] = []
    for bucket in buckets:
        bucket.sort(key=_sort_key)
        results.extend(bucket)
        if len(results) >= limit:
            break

    return results[:limit]
