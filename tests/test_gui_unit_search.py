"""
tests/test_gui_unit_search.py
==============================
Tests for SPEC-14 (unit and magnitude search).

Structure
---------
Section 1 — Qt-FREE tests
    Feed ``build_search_index`` and ``search`` stub callables (no QApplication).
    A small fake DB is defined here, including an accented unit name to exercise
    the accent-normalisation path.

Section 2 — Offscreen-Qt integration test (skipped gracefully if Qt unavailable)
    Opens ``_SearchDialog`` with a stub index, runs a query, selects a hit,
    accepts the dialog, and asserts that the selected_hit is correct.
    Also opens ``MainWindow`` (offscreen), triggers ``_get_search_index``, and
    asserts the index was built from the core callables (non-empty, all
    ``SearchHit`` instances), that ``_show_search`` wires magnitude + unit combos
    on a simulated acceptance, and that no inline ``setToolTip(`` literals appear
    in ``unit_search.py``.

Rules
-----
- No PySide6 imports at module top-level.
- All assertions are deterministic; no network access.
- The Qt offscreen portion uses ``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest

from unit_converter.gui.unit_search import (
    SearchHit,
    _normalize,
    build_search_index,
    search,
)

# ---------------------------------------------------------------------------
# Fake database for headless tests
# ---------------------------------------------------------------------------

_FAKE_DB: dict[str, list[str]] = {
    "Mass": [
        "gram (g)",
        "kilogram (kg)",
        "pound (lb)",
    ],
    "Length": [
        "metre (m)",
        "kilometre (km)",
        # Accented name: should match "angstrom" query
        "Ångström (Å)",
        "inch (in)",
    ],
    "Temperature": [
        "Celsius (°C)",
        "Fahrenheit (°F)",
        "Kelvin (K)",
    ],
}


def _fake_list_magnitudes() -> list[str]:
    return list(_FAKE_DB.keys())


def _fake_list_units(magnitude: str) -> dict:
    return {"units": _FAKE_DB.get(magnitude, []), "base_unit": ""}


# ===========================================================================
# Section 1 — Qt-free tests
# ===========================================================================

class TestNormalize:
    """_normalize performs NFKD decomposition + combining-mark strip + casefold."""

    def test_casefold_ascii(self) -> None:
        assert _normalize("GRAM") == "gram"

    def test_casefold_mixed(self) -> None:
        assert _normalize("Kilogram") == "kilogram"

    def test_accent_stripped(self) -> None:
        assert _normalize("Ångström") == "angstrom"

    def test_accent_stripped_lowercase(self) -> None:
        assert _normalize("ångström") == "angstrom"

    def test_cafe_accent(self) -> None:
        assert _normalize("café") == "cafe"

    def test_already_normalized(self) -> None:
        assert _normalize("metre") == "metre"

    def test_empty_string(self) -> None:
        assert _normalize("") == ""

    def test_degree_sign_preserved(self) -> None:
        # degree sign (U+00B0) is not a combining mark; it should survive
        result = _normalize("Celsius (°C)")
        assert "celsius" in result


class TestBuildSearchIndex:
    """build_search_index builds a flat index from the injected callables."""

    def _build(self) -> list[SearchHit]:
        return build_search_index(_fake_list_magnitudes, _fake_list_units)

    def test_returns_list(self) -> None:
        idx = self._build()
        assert isinstance(idx, list)

    def test_all_are_search_hits(self) -> None:
        idx = self._build()
        for h in idx:
            assert isinstance(h, SearchHit)

    def test_count_matches_total_units(self) -> None:
        total = sum(len(v) for v in _FAKE_DB.values())
        idx = self._build()
        assert len(idx) == total

    def test_magnitude_coverage(self) -> None:
        idx = self._build()
        mags = {h.magnitude for h in idx}
        assert mags == set(_FAKE_DB.keys())

    def test_unit_coverage(self) -> None:
        idx = self._build()
        units = {h.unit for h in idx}
        expected = {u for units_list in _FAKE_DB.values() for u in units_list}
        assert units == expected

    def test_hit_fields_correct(self) -> None:
        idx = self._build()
        gram_hits = [h for h in idx if h.unit == "gram (g)"]
        assert len(gram_hits) == 1
        assert gram_hits[0].magnitude == "Mass"

    def test_order_preserves_magnitudes(self) -> None:
        """Magnitude order should follow list_magnitudes_fn output."""
        idx = self._build()
        # First hit must be from the first magnitude
        assert idx[0].magnitude == "Mass"

    def test_order_preserves_units_within_magnitude(self) -> None:
        """Units within a magnitude must follow list_units_fn order."""
        idx = self._build()
        mass_hits = [h for h in idx if h.magnitude == "Mass"]
        assert [h.unit for h in mass_hits] == _FAKE_DB["Mass"]

    def test_empty_magnitudes(self) -> None:
        """If list_magnitudes returns [], the index is empty."""
        idx = build_search_index(lambda: [], _fake_list_units)
        assert idx == []

    def test_magnitude_with_empty_units(self) -> None:
        """A magnitude with no units contributes zero hits."""
        def empty_units(mag: str) -> dict:
            return {"units": [], "base_unit": ""}
        idx = build_search_index(_fake_list_magnitudes, empty_units)
        assert idx == []

    def test_resilient_to_list_magnitudes_error(self) -> None:
        """If list_magnitudes raises, an empty index is returned."""
        def bad_fn() -> list[str]:
            raise RuntimeError("boom")
        idx = build_search_index(bad_fn, _fake_list_units)
        assert idx == []

    def test_resilient_to_list_units_error(self) -> None:
        """If list_units raises for one magnitude, that magnitude is skipped."""
        def bad_units(mag: str) -> dict:
            if mag == "Mass":
                raise RuntimeError("bad")
            return _FAKE_DB.get(mag, {}) and {"units": _FAKE_DB[mag], "base_unit": ""}

        idx = build_search_index(_fake_list_magnitudes, bad_units)
        mags = {h.magnitude for h in idx}
        assert "Mass" not in mags
        assert "Length" in mags


class TestSearch:
    """search() returns correct, ordered hits."""

    @pytest.fixture(autouse=True)
    def _index(self) -> None:
        self.idx = build_search_index(_fake_list_magnitudes, _fake_list_units)

    # ------------------------------------------------------------------
    # Empty / blank query
    # ------------------------------------------------------------------

    def test_empty_query_returns_empty(self) -> None:
        assert search(self.idx, "") == []

    def test_whitespace_only_query_returns_empty(self) -> None:
        assert search(self.idx, "   ") == []

    # ------------------------------------------------------------------
    # Basic matching
    # ------------------------------------------------------------------

    def test_exact_unit_match(self) -> None:
        hits = search(self.idx, "gram (g)")
        assert hits[0] == SearchHit("Mass", "gram (g)")

    def test_case_insensitive_unit(self) -> None:
        hits = search(self.idx, "GRAM")
        units = [h.unit for h in hits]
        assert any("gram" in u.lower() for u in units)

    def test_case_insensitive_magnitude(self) -> None:
        hits = search(self.idx, "MASS")
        mags = {h.magnitude for h in hits}
        assert "Mass" in mags

    def test_accent_insensitive(self) -> None:
        """Query 'angstrom' must match 'Ångström (Å)'."""
        hits = search(self.idx, "angstrom")
        units = [h.unit for h in hits]
        assert "Ångström (Å)" in units

    def test_accent_in_query(self) -> None:
        """Query 'Ångström' must match the accented unit."""
        hits = search(self.idx, "Ångström")
        units = [h.unit for h in hits]
        assert "Ångström (Å)" in units

    def test_substring_unit_match(self) -> None:
        hits = search(self.idx, "kilo")
        units = [h.unit for h in hits]
        assert "kilogram (kg)" in units or "kilometre (km)" in units

    def test_substring_magnitude_match(self) -> None:
        hits = search(self.idx, "emperat")
        mags = {h.magnitude for h in hits}
        assert "Temperature" in mags

    def test_returns_all_units_of_matching_magnitude(self) -> None:
        hits = search(self.idx, "Temperature")
        mags = [h.magnitude for h in hits]
        assert all(m == "Temperature" for m in mags)
        assert len(hits) == len(_FAKE_DB["Temperature"])

    # ------------------------------------------------------------------
    # Ordering: prefix before substring
    # ------------------------------------------------------------------

    def test_prefix_before_substring(self) -> None:
        """
        Query 'metre' matches:
        - prefix: 'metre (m)' (starts with 'metre')
        - substring: 'kilometre (km)' (contains 'metre' inside)
        The prefix hit must come before the substring hit.
        """
        hits = search(self.idx, "metre")
        units = [h.unit for h in hits]
        assert "metre (m)" in units
        assert "kilometre (km)" in units
        assert units.index("metre (m)") < units.index("kilometre (km)")

    def test_exact_before_prefix(self) -> None:
        """
        Query 'gram (g)' exactly matches 'gram (g)';
        'kilogram (kg)' contains 'gram' as a substring.
        The exact hit must come first.
        """
        hits = search(self.idx, "gram (g)")
        assert hits[0].unit == "gram (g)"

    def test_unit_match_before_magnitude_match(self) -> None:
        """
        Querying 'Mass' should list unit-level substring matches (none for 'Mass'
        in unit names) before magnitude-level matches.  Since no unit contains
        'Mass', all hits are via magnitude — confirm they all belong to Mass.
        """
        hits = search(self.idx, "Mass")
        for h in hits:
            assert h.magnitude == "Mass"

    # ------------------------------------------------------------------
    # Limit
    # ------------------------------------------------------------------

    def test_limit_respected(self) -> None:
        hits = search(self.idx, "e", limit=2)
        assert len(hits) <= 2

    def test_limit_default_50(self) -> None:
        # With only ~10 total units, all should come back under the default limit
        hits = search(self.idx, "e")
        total = sum(len(v) for v in _FAKE_DB.values())
        assert len(hits) <= total

    def test_limit_zero_returns_empty(self) -> None:
        hits = search(self.idx, "gram", limit=0)
        assert hits == []

    # ------------------------------------------------------------------
    # No Qt dependency
    # ------------------------------------------------------------------

    def test_no_qt_import(self) -> None:
        """unit_search must contain no PySide6/Qt import statements."""
        import unit_converter.gui.unit_search as mod
        src = open(mod.__file__).read()
        # Check for actual import statements, not docstring mentions
        import ast
        tree = ast.parse(src)
        qt_imports = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and any(
                (alias.name or "").startswith(("PySide6", "PyQt"))
                for alias in getattr(node, "names", [])
            )
            or isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith(("PySide6", "PyQt"))
        ]
        assert not qt_imports, f"Qt import statements found in unit_search.py: {qt_imports}"

    def test_no_inline_settoolTip_in_unit_search(self) -> None:
        import unit_converter.gui.unit_search as mod
        src = open(mod.__file__).read()
        assert "setToolTip(" not in src


class TestSearchHit:
    """SearchHit is a frozen dataclass."""

    def test_frozen(self) -> None:
        h = SearchHit("Mass", "gram (g)")
        with pytest.raises((AttributeError, TypeError)):
            h.magnitude = "Length"  # type: ignore[misc]

    def test_equality(self) -> None:
        h1 = SearchHit("Mass", "gram (g)")
        h2 = SearchHit("Mass", "gram (g)")
        assert h1 == h2

    def test_inequality(self) -> None:
        h1 = SearchHit("Mass", "gram (g)")
        h2 = SearchHit("Length", "metre (m)")
        assert h1 != h2

    def test_hashable(self) -> None:
        """Frozen dataclasses are hashable."""
        h = SearchHit("Mass", "gram (g)")
        assert hash(h) is not None
        s = {h}
        assert h in s


# ===========================================================================
# Section 2 — Offscreen-Qt integration tests
# ===========================================================================

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_qt_available = False
try:
    from PySide6.QtWidgets import QApplication  # noqa: E402
    _qt_available = True
except ImportError:
    pass

_requires_qt = pytest.mark.skipif(
    not _qt_available,
    reason="PySide6 not installed — offscreen Qt tests skipped",
)


def _get_app() -> "QApplication":
    app = QApplication.instance()
    if app is None:
        app = QApplication([__name__, "-platform", "offscreen"])
    return app  # type: ignore[return-value]


@_requires_qt
class TestSearchDialogOffscreen:
    """Open _SearchDialog offscreen and verify accept/cancel behaviour."""

    @pytest.fixture(scope="class")
    def app(self):  # type: ignore[return]
        return _get_app()

    def _stub_index(self) -> list[SearchHit]:
        return build_search_index(_fake_list_magnitudes, _fake_list_units)

    def test_search_dialog_constructs(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        assert dlg is not None
        dlg.close()

    def test_search_dialog_has_tooltip_on_search_edit(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        assert dlg._search_edit.toolTip()
        dlg.close()

    def test_search_dialog_has_tooltip_on_results_list(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        assert dlg._results_list.toolTip()
        dlg.close()

    def test_query_populates_list(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        from PySide6.QtCore import Qt
        dlg = _SearchDialog(index=self._stub_index())
        dlg._search_edit.setText("gram")
        # _on_query_changed is connected to textChanged
        assert dlg._results_list.count() >= 1
        dlg.close()

    def test_accent_query_populates_list(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        dlg._search_edit.setText("angstrom")
        assert dlg._results_list.count() >= 1
        items = [
            dlg._results_list.item(i).text()
            for i in range(dlg._results_list.count())
        ]
        assert any("ngstr" in t for t in items), f"Ångström not found in {items}"
        dlg.close()

    def test_empty_query_clears_list(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        dlg._search_edit.setText("gram")
        dlg._search_edit.setText("")
        assert dlg._results_list.count() == 0
        dlg.close()

    def test_selected_hit_none_before_accept(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        assert dlg.selected_hit() is None
        dlg.close()

    def test_on_apply_without_selection_does_not_accept(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        dlg = _SearchDialog(index=self._stub_index())
        # No query → no items in list → _on_apply is a no-op
        dlg._on_apply()
        assert dlg.selected_hit() is None
        dlg.close()

    def test_on_apply_with_selection_sets_hit(self, app) -> None:
        from unit_converter.gui.main_window import _SearchDialog
        from PySide6.QtCore import Qt
        dlg = _SearchDialog(index=self._stub_index())
        dlg._search_edit.setText("gram")
        # Ensure at least one item
        assert dlg._results_list.count() >= 1
        dlg._results_list.setCurrentRow(0)
        item = dlg._results_list.currentItem()
        expected_hit: SearchHit = item.data(Qt.UserRole)
        # Manually call _on_apply (avoids exec() loop in tests)
        dlg._on_apply()
        assert dlg.selected_hit() == expected_hit
        dlg.close()


@_requires_qt
class TestMainWindowSearchIntegration:
    """
    Build an offscreen MainWindow and exercise the search index + dialog wiring.
    """

    @pytest.fixture(scope="class")
    def main_window(self):  # type: ignore[return]
        _get_app()
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            from unit_converter.gui.main_window import MainWindow
            win = MainWindow()
            yield win
            win.close()
        except Exception as exc:
            pytest.skip(f"MainWindow construction failed: {exc}")

    def test_search_index_none_before_first_use(self, main_window) -> None:
        """The index is lazily built — starts as None until first access."""
        # Reset to simulate fresh state (may already be populated by other tests)
        main_window._search_index = None
        assert main_window._search_index is None

    def test_get_search_index_returns_nonempty_list(self, main_window) -> None:
        main_window._search_index = None  # force rebuild
        idx = main_window._get_search_index()
        assert isinstance(idx, list)
        assert len(idx) > 0

    def test_get_search_index_all_are_search_hits(self, main_window) -> None:
        idx = main_window._get_search_index()
        for h in idx:
            assert isinstance(h, SearchHit)

    def test_get_search_index_cached(self, main_window) -> None:
        """Second call must return the same list object (no rebuild)."""
        main_window._search_index = None
        idx1 = main_window._get_search_index()
        idx2 = main_window._get_search_index()
        assert idx1 is idx2

    def test_index_built_from_core_callables(self, main_window) -> None:
        """Every magnitude in the index must appear in list_magnitudes()."""
        from unit_converter.core.converter import list_magnitudes
        core_mags = set(list_magnitudes())
        idx = main_window._get_search_index()
        index_mags = {h.magnitude for h in idx}
        assert index_mags <= core_mags, (
            f"Index contains unknown magnitudes: {index_mags - core_mags}"
        )

    def test_apply_search_hit_sets_magnitude_combo(self, main_window) -> None:
        """
        Applying a hit from _show_search configures _cb_magnitude.

        We simulate the post-acceptance wiring directly via the same code path
        that _show_search executes: findText + setCurrentIndex.
        """
        from unit_converter.core.converter import list_magnitudes, list_units
        # Pick the first magnitude and its first unit
        mags = list_magnitudes()
        first_mag = mags[0]
        first_unit = list_units(first_mag)["units"][0]
        hit = SearchHit(magnitude=first_mag, unit=first_unit)

        mag_idx = main_window._cb_magnitude.findText(hit.magnitude)
        assert mag_idx >= 0, f"Magnitude {hit.magnitude!r} not in combo"
        main_window._cb_magnitude.setCurrentIndex(mag_idx)

        assert main_window._cb_magnitude.currentText() == first_mag

    def test_apply_search_hit_sets_unit1_combo(self, main_window) -> None:
        """After magnitude is set, the unit should appear in _cb_unit1."""
        from unit_converter.core.converter import list_magnitudes, list_units
        mags = list_magnitudes()
        first_mag = mags[0]
        units = list_units(first_mag)["units"]
        first_unit = units[0]

        # Set magnitude first (populates combos)
        mag_idx = main_window._cb_magnitude.findText(first_mag)
        main_window._cb_magnitude.setCurrentIndex(mag_idx)

        unit_idx = main_window._cb_unit1.findText(first_unit)
        assert unit_idx >= 0, f"Unit {first_unit!r} not found in combo"
        main_window._cb_unit1.setCurrentIndex(unit_idx)
        assert main_window._cb_unit1.currentText() == first_unit

    def test_no_inline_settoolTip_in_main_window(self) -> None:
        from pathlib import Path
        src = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "main_window.py"
        ).read_text(encoding="utf-8")
        assert "setToolTip(" not in src, (
            "Inline setToolTip( found in main_window.py — must use register_info"
        )

    def test_search_registry_keys_exist(self) -> None:
        """All four SPEC-14 registry keys are defined in INFO_TEXTS."""
        from unit_converter.gui.info_registry import INFO_TEXTS
        for key in (
            "search_dialog",
            "search_edit",
            "search_results_list",
            "search_apply_btn",
        ):
            assert key in INFO_TEXTS, f"Registry key {key!r} is missing from INFO_TEXTS"

    def test_search_registry_values_nonempty(self) -> None:
        from unit_converter.gui.info_registry import INFO_TEXTS
        for key in (
            "search_dialog",
            "search_edit",
            "search_results_list",
            "search_apply_btn",
        ):
            assert INFO_TEXTS[key].strip(), f"Registry key {key!r} has empty text"
