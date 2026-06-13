"""
unit_converter.core.history
============================
Conversion history and favorites — local persistence helper (UC-I07).

Architecture
------------
- History is stored as a capped JSON list in
  ``~/.unit-converter/history.json`` (same user-data dir as custom units and
  the currency cache).
- Each entry records the magnitude, from/to units, orders, and the input +
  result values, plus an ISO-8601 timestamp.
- The list is capped at ``MAX_HISTORY`` entries (oldest entry dropped when
  full) so the file stays small.
- Favorites are stored as a named subset: each entry optionally has a
  ``"favorite"`` key with a user-supplied label.

All functions are pure Python / stdlib — no GUI imports ever enter this module.

Public API
----------
record(magnitude, value, from_unit, to_unit, result, *, from_order="1",
       to_order="1", sig_figs=None) -> HistoryEntry
    Append a completed conversion to the history file.

load_history(path=None) -> list[HistoryEntry]
    Load and return the full history list (most-recent-first).

clear_history(path=None) -> None
    Delete all history entries.

add_favorite(entry, label="", path=None) -> None
    Mark an existing entry (by index or copy) as a favorite with a label.

list_favorites(path=None) -> list[HistoryEntry]
    Return only the entries marked as favorites.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MAX_HISTORY = 200  # cap on the number of stored entries


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class HistoryEntry:
    """A single conversion history record."""
    magnitude: str
    from_unit: str
    to_unit: str
    from_order: str
    to_order: str
    value: float
    result: float
    sig_figs: Optional[int]
    timestamp: str          # ISO-8601 UTC
    favorite: bool = False
    favorite_label: str = ""


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------

def _history_path(path: Optional[Path] = None) -> Path:
    """Return the path to the history JSON file."""
    if path is not None:
        return Path(path)
    from unit_converter.core.data_loader import _user_data_dir
    return _user_data_dir() / "history.json"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _entry_from_dict(d: dict) -> HistoryEntry:
    return HistoryEntry(
        magnitude=d.get("magnitude", ""),
        from_unit=d.get("from_unit", ""),
        to_unit=d.get("to_unit", ""),
        from_order=d.get("from_order", "1"),
        to_order=d.get("to_order", "1"),
        value=float(d.get("value", 0.0)),
        result=float(d.get("result", 0.0)),
        sig_figs=d.get("sig_figs"),
        timestamp=d.get("timestamp", ""),
        favorite=bool(d.get("favorite", False)),
        favorite_label=d.get("favorite_label", ""),
    )


def _load_raw(path: Path) -> list[dict]:
    """Load the raw list from disk; returns [] on missing/corrupt file."""
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def _save_raw(entries: list[dict], path: Path) -> None:
    """Persist the entry list to disk."""
    try:
        path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not write history to %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record(
    magnitude: str,
    value: float,
    from_unit: str,
    to_unit: str,
    result: float,
    *,
    from_order: str = "1",
    to_order: str = "1",
    sig_figs: Optional[int] = None,
    history_path: Optional[Path] = None,
) -> HistoryEntry:
    """
    Append a completed conversion to the history file.

    Parameters
    ----------
    magnitude:
        Magnitude name (e.g. ``"Mass"``).
    value:
        Input value.
    from_unit, to_unit:
        Unit names as they appear in the database.
    result:
        Converted output value.
    from_order, to_order:
        SI/IEC prefix keys (default ``"1"``).
    sig_figs:
        Significant figures used, or ``None``.
    history_path:
        Override default history file path (useful in tests).

    Returns
    -------
    HistoryEntry
        The newly-appended entry.
    """
    path = _history_path(history_path)
    ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    entry = HistoryEntry(
        magnitude=magnitude,
        from_unit=from_unit,
        to_unit=to_unit,
        from_order=from_order,
        to_order=to_order,
        value=value,
        result=result,
        sig_figs=sig_figs,
        timestamp=ts,
    )

    raw = _load_raw(path)
    raw.append(asdict(entry))
    # Cap at MAX_HISTORY (drop oldest)
    if len(raw) > MAX_HISTORY:
        raw = raw[-MAX_HISTORY:]
    _save_raw(raw, path)
    return entry


def load_history(history_path: Optional[Path] = None) -> list[HistoryEntry]:
    """
    Load the full history list, most-recent-first.

    Parameters
    ----------
    history_path:
        Override default path (useful in tests).

    Returns
    -------
    list[HistoryEntry]
        All stored entries, newest first.
    """
    path = _history_path(history_path)
    raw = _load_raw(path)
    entries = [_entry_from_dict(d) for d in raw]
    return list(reversed(entries))


def clear_history(history_path: Optional[Path] = None) -> None:
    """
    Delete all history entries.

    Parameters
    ----------
    history_path:
        Override default path (useful in tests).
    """
    path = _history_path(history_path)
    _save_raw([], path)


def add_favorite(
    entry: HistoryEntry,
    label: str = "",
    history_path: Optional[Path] = None,
) -> None:
    """
    Mark an entry as a favorite.

    Finds the entry in the history file (matched by timestamp) and sets
    its ``favorite`` flag and optional ``favorite_label``.

    Parameters
    ----------
    entry:
        The entry to mark (must already be in history).
    label:
        Human-readable label for the favorite.
    history_path:
        Override default path (useful in tests).
    """
    path = _history_path(history_path)
    raw = _load_raw(path)
    for d in raw:
        if d.get("timestamp") == entry.timestamp:
            d["favorite"] = True
            d["favorite_label"] = label
            break
    _save_raw(raw, path)


def list_favorites(history_path: Optional[Path] = None) -> list[HistoryEntry]:
    """
    Return only the entries marked as favorites (most-recent-first).

    Parameters
    ----------
    history_path:
        Override default path (useful in tests).
    """
    return [e for e in load_history(history_path) if e.favorite]
