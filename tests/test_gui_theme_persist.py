"""
tests/test_gui_theme_persist.py
================================
Deterministic offline tests for unit_converter.gui.theme_persist and the
Qt-free parts of unit_converter.gui.theme.

Rules enforced:
- No PySide6 import anywhere in this file (helpers must be Qt-free).
- No network access.
- All file I/O uses tmp_path; no real ~/.unit-converter/ is touched.
- Floats compared with pytest.approx where applicable (not relevant here, but
  the pattern is kept for consistency).

Covers:
- is_valid_hex_color: valid inputs, invalid inputs (no #, wrong length,
  non-hex chars, empty string, non-string types).
- normalize_hex_color: upper-case normalisation, returns None for invalids.
- load_theme_prefs: missing file -> {}, corrupt JSON -> {}, valid JSON -> dict,
  non-dict JSON -> {}, integer keys cast to str.
- save_theme_prefs: writes valid JSON; silently ignores OSError on a
  read-only path (mocked via monkeypatch).
- save -> load round-trip: persistence survives a write/read cycle.
- merge_theme_colors: overrides win, base keys preserved, invalid override
  values dropped, __theme__ key always passed through, unknown keys added,
  originals unmodified.
- build_dialog_stylesheet (theme.py): Qt-free string builder; bg_dialog and
  fg_main are embedded; Light and Dark palettes each produce valid output;
  custom overrides are respected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---- Qt-freedom guard ---------------------------------------------------
# Confirm the module can be imported without pulling in PySide6.
# We check sys.modules AFTER import; PySide6 must not appear.

from unit_converter.gui.theme_persist import (
    is_valid_hex_color,
    load_theme_prefs,
    merge_theme_colors,
    normalize_hex_color,
    save_theme_prefs,
)
from unit_converter.gui.theme import (
    build_dialog_stylesheet,
    LIGHT_THEME,
    DARK_THEME,
)


def test_no_pyside6_imported() -> None:
    """theme_persist source must not contain any PySide6 import statement.

    Checking sys.modules is ordering-dependent (other test modules in the same
    pytest session may import PySide6 legitimately).  Scanning the source text
    is order-independent and directly verifies the Qt-freedom requirement.
    """
    src_path = (
        Path(__file__).resolve().parent.parent
        / "unit_converter" / "gui" / "theme_persist.py"
    )
    src = src_path.read_text(encoding="utf-8")
    pyside_imports = [
        line.strip() for line in src.splitlines()
        if line.strip().startswith(("from PySide6", "import PySide6"))
    ]
    assert pyside_imports == [], (
        f"theme_persist.py contains PySide6 import(s): {pyside_imports}"
    )


# =========================================================================
# is_valid_hex_color
# =========================================================================

class TestIsValidHexColor:
    # --- valid inputs ---

    def test_uppercase_rrggbb(self) -> None:
        assert is_valid_hex_color("#FFFFFF") is True

    def test_lowercase_rrggbb(self) -> None:
        assert is_valid_hex_color("#ffffff") is True

    def test_mixed_case_rrggbb(self) -> None:
        assert is_valid_hex_color("#1a2B3c") is True

    def test_all_zeros(self) -> None:
        assert is_valid_hex_color("#000000") is True

    def test_all_ff(self) -> None:
        assert is_valid_hex_color("#FF00FF") is True

    def test_numeric_digits_only(self) -> None:
        assert is_valid_hex_color("#123456") is True

    def test_letters_only_valid(self) -> None:
        assert is_valid_hex_color("#ABCDEF") is True

    # --- invalid: missing # ---

    def test_no_hash_prefix(self) -> None:
        assert is_valid_hex_color("FFFFFF") is False

    def test_wrong_prefix_0x(self) -> None:
        assert is_valid_hex_color("0xFFFFFF") is False

    # --- invalid: wrong length ---

    def test_empty_string(self) -> None:
        assert is_valid_hex_color("") is False

    def test_hash_only(self) -> None:
        assert is_valid_hex_color("#") is False

    def test_shorthand_3_digits(self) -> None:
        # #RGB shorthand is NOT supported — only #RRGGBB
        assert is_valid_hex_color("#FFF") is False

    def test_too_long_8_digits(self) -> None:
        assert is_valid_hex_color("#FFFFFFFF") is False

    def test_5_hex_digits(self) -> None:
        assert is_valid_hex_color("#FFFFF") is False

    # --- invalid: non-hex characters ---

    def test_g_is_not_hex(self) -> None:
        assert is_valid_hex_color("#GGGGGG") is False

    def test_space_inside(self) -> None:
        assert is_valid_hex_color("# FFFFF") is False

    def test_css_color_name(self) -> None:
        assert is_valid_hex_color("white") is False

    def test_rgb_function_notation(self) -> None:
        assert is_valid_hex_color("rgb(255,0,0)") is False

    # --- invalid: non-string types ---

    def test_none_is_rejected(self) -> None:
        assert is_valid_hex_color(None) is False  # type: ignore[arg-type]

    def test_int_is_rejected(self) -> None:
        assert is_valid_hex_color(0xFFFFFF) is False  # type: ignore[arg-type]

    def test_bytes_is_rejected(self) -> None:
        assert is_valid_hex_color(b"#FFFFFF") is False  # type: ignore[arg-type]

    def test_list_is_rejected(self) -> None:
        assert is_valid_hex_color(["#FFFFFF"]) is False  # type: ignore[arg-type]


# =========================================================================
# normalize_hex_color
# =========================================================================

class TestNormalizeHexColor:
    def test_lowercase_becomes_uppercase(self) -> None:
        assert normalize_hex_color("#1a2b3c") == "#1A2B3C"

    def test_already_uppercase_unchanged(self) -> None:
        assert normalize_hex_color("#ABCDEF") == "#ABCDEF"

    def test_mixed_case_becomes_uppercase(self) -> None:
        assert normalize_hex_color("#aAbBcC") == "#AABBCC"

    def test_all_zeros(self) -> None:
        assert normalize_hex_color("#000000") == "#000000"

    def test_invalid_returns_none_no_hash(self) -> None:
        assert normalize_hex_color("FFFFFF") is None

    def test_invalid_returns_none_short(self) -> None:
        assert normalize_hex_color("#FFF") is None

    def test_invalid_returns_none_empty(self) -> None:
        assert normalize_hex_color("") is None

    def test_invalid_returns_none_non_hex(self) -> None:
        assert normalize_hex_color("#GGGGGG") is None

    def test_invalid_returns_none_none_input(self) -> None:
        assert normalize_hex_color(None) is None  # type: ignore[arg-type]

    def test_css_name_returns_none(self) -> None:
        assert normalize_hex_color("red") is None


# =========================================================================
# load_theme_prefs
# =========================================================================

class TestLoadThemePrefs:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such_file.json"
        result = load_theme_prefs(path=missing)
        assert result == {}

    def test_valid_json_dict_returned(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        payload = {"__theme__": "Dark", "bg_main": "#222222"}
        prefs_file.write_text(json.dumps(payload), encoding="utf-8")
        result = load_theme_prefs(path=prefs_file)
        assert result == {"__theme__": "Dark", "bg_main": "#222222"}

    def test_corrupt_json_returns_empty_dict(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        prefs_file.write_text("{ not valid json }", encoding="utf-8")
        result = load_theme_prefs(path=prefs_file)
        assert result == {}

    def test_json_array_returns_empty_dict(self, tmp_path: Path) -> None:
        # JSON root is a list, not a dict — must return {}
        prefs_file = tmp_path / "theme.json"
        prefs_file.write_text(json.dumps(["#FFFFFF", "#000000"]), encoding="utf-8")
        result = load_theme_prefs(path=prefs_file)
        assert result == {}

    def test_integer_keys_cast_to_str(self, tmp_path: Path) -> None:
        # JSON allows only string keys, but if somehow loaded with int keys
        # via a crafted payload the implementation casts them.
        # We simulate by writing valid JSON (JSON keys are always str) and
        # verify the cast path in a dict-cast scenario via patching json.loads.
        prefs_file = tmp_path / "theme.json"
        prefs_file.write_text(json.dumps({"key": "val"}), encoding="utf-8")
        with patch(
            "unit_converter.gui.theme_persist.json.loads",
            return_value={1: "val"},  # int key — exercises str(k) branch
        ):
            result = load_theme_prefs(path=prefs_file)
        assert result == {"1": "val"}

    def test_values_cast_to_str(self, tmp_path: Path) -> None:
        # Similarly exercises str(v) branch with a non-string value
        prefs_file = tmp_path / "theme.json"
        prefs_file.write_text(json.dumps({"key": "val"}), encoding="utf-8")
        with patch(
            "unit_converter.gui.theme_persist.json.loads",
            return_value={"key": 42},  # int value
        ):
            result = load_theme_prefs(path=prefs_file)
        assert result == {"key": "42"}

    def test_empty_json_object_returns_empty_dict(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        prefs_file.write_text("{}", encoding="utf-8")
        result = load_theme_prefs(path=prefs_file)
        assert result == {}

    def test_oserror_returns_empty_dict(self, tmp_path: Path) -> None:
        # A file that exists but raises OSError on read (permission error)
        prefs_file = tmp_path / "theme.json"
        prefs_file.write_text("{}", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            result = load_theme_prefs(path=prefs_file)
        assert result == {}


# =========================================================================
# save_theme_prefs
# =========================================================================

class TestSaveThemePrefs:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        save_theme_prefs({"__theme__": "Light"}, path=prefs_file)
        assert prefs_file.exists()

    def test_saved_content_is_valid_json(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        prefs = {"__theme__": "Dark", "bg_main": "#111111"}
        save_theme_prefs(prefs, path=prefs_file)
        loaded = json.loads(prefs_file.read_text(encoding="utf-8"))
        assert loaded == prefs

    def test_save_silent_on_oserror(self, tmp_path: Path) -> None:
        # Must not raise even if the write fails
        prefs_file = tmp_path / "theme.json"
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            save_theme_prefs({"__theme__": "Light"}, path=prefs_file)
        # No exception — passes if we reach here

    def test_overwrite_existing_file(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        save_theme_prefs({"__theme__": "Light"}, path=prefs_file)
        save_theme_prefs({"__theme__": "Dark"}, path=prefs_file)
        loaded = json.loads(prefs_file.read_text(encoding="utf-8"))
        assert loaded["__theme__"] == "Dark"


# =========================================================================
# save -> load round-trip
# =========================================================================

class TestRoundTrip:
    def test_basic_round_trip(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        original = {"__theme__": "Dark", "bg_main": "#1C1C1C", "fg_title": "#FFFFFF"}
        save_theme_prefs(original, path=prefs_file)
        recovered = load_theme_prefs(path=prefs_file)
        assert recovered == original

    def test_round_trip_empty_dict(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        save_theme_prefs({}, path=prefs_file)
        assert load_theme_prefs(path=prefs_file) == {}

    def test_round_trip_unicode_theme_name(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        prefs = {"__theme__": "Solarized-Düsseldorf"}
        save_theme_prefs(prefs, path=prefs_file)
        assert load_theme_prefs(path=prefs_file) == prefs

    def test_round_trip_many_color_keys(self, tmp_path: Path) -> None:
        prefs_file = tmp_path / "theme.json"
        colors = {f"widget_{i}": f"#0{i:05X}"[:7] for i in range(10)}
        # Build valid-length hex values manually
        valid_colors = {f"widget_{i}": "#ABCDEF" for i in range(10)}
        save_theme_prefs(valid_colors, path=prefs_file)
        recovered = load_theme_prefs(path=prefs_file)
        assert recovered == valid_colors

    def test_no_real_home_dir_touched(self, tmp_path: Path) -> None:
        # Verify the tmp_path isolation: the default path is NOT used
        # because we pass an explicit tmp_path file.
        prefs_file = tmp_path / "isolated.json"
        save_theme_prefs({"__theme__": "Light"}, path=prefs_file)
        loaded = load_theme_prefs(path=prefs_file)
        assert loaded["__theme__"] == "Light"


# =========================================================================
# merge_theme_colors
# =========================================================================

class TestMergeThemeColors:
    def test_valid_override_wins(self) -> None:
        base = {"bg_main": "#BFBFBF"}
        overrides = {"bg_main": "#222222"}
        result = merge_theme_colors(base, overrides)
        assert result["bg_main"] == "#222222"

    def test_base_keys_preserved_when_not_overridden(self) -> None:
        base = {"bg_main": "#BFBFBF", "fg_title": "#0000FF"}
        overrides = {"bg_main": "#222222"}
        result = merge_theme_colors(base, overrides)
        assert result["fg_title"] == "#0000FF"

    def test_invalid_override_value_dropped(self) -> None:
        base = {"fg_title": "#0000FF"}
        overrides = {"fg_title": "notacolor"}
        result = merge_theme_colors(base, overrides)
        assert result["fg_title"] == "#0000FF"  # base value preserved

    def test_dunder_theme_always_passed_through(self) -> None:
        base = {"bg_main": "#FFFFFF"}
        overrides = {"__theme__": "Dark"}
        result = merge_theme_colors(base, overrides)
        assert result["__theme__"] == "Dark"

    def test_dunder_theme_with_non_hex_value_still_passes(self) -> None:
        # __theme__ value is a name string, not a hex color — must still pass
        base = {}
        overrides = {"__theme__": "Solarized"}
        result = merge_theme_colors(base, overrides)
        assert result["__theme__"] == "Solarized"

    def test_unknown_key_with_valid_color_added(self) -> None:
        base = {"bg_main": "#FFFFFF"}
        overrides = {"new_key": "#AABBCC"}
        result = merge_theme_colors(base, overrides)
        assert result["new_key"] == "#AABBCC"

    def test_unknown_key_with_invalid_color_not_added(self) -> None:
        base = {"bg_main": "#FFFFFF"}
        overrides = {"bad_key": "invalid"}
        result = merge_theme_colors(base, overrides)
        assert "bad_key" not in result

    def test_base_is_not_mutated(self) -> None:
        base = {"bg_main": "#FFFFFF"}
        overrides = {"bg_main": "#000000"}
        merge_theme_colors(base, overrides)
        assert base["bg_main"] == "#FFFFFF"

    def test_overrides_is_not_mutated(self) -> None:
        base = {}
        overrides = {"__theme__": "Dark", "bg_main": "#000000"}
        merge_theme_colors(base, overrides)
        assert overrides == {"__theme__": "Dark", "bg_main": "#000000"}

    def test_empty_overrides_returns_copy_of_base(self) -> None:
        base = {"bg_main": "#FFFFFF", "fg_title": "#000000"}
        result = merge_theme_colors(base, {})
        assert result == base
        assert result is not base  # must be a new dict

    def test_empty_base_and_empty_overrides(self) -> None:
        result = merge_theme_colors({}, {})
        assert result == {}

    def test_empty_base_with_valid_overrides(self) -> None:
        overrides = {"bg_main": "#ABCDEF"}
        result = merge_theme_colors({}, overrides)
        assert result == {"bg_main": "#ABCDEF"}

    def test_multiple_invalid_overrides_all_dropped(self) -> None:
        base = {"a": "#111111", "b": "#222222"}
        overrides = {"a": "red", "b": "#ZZZ", "c": "rgb(0,0,0)"}
        result = merge_theme_colors(base, overrides)
        assert result == {"a": "#111111", "b": "#222222"}

    def test_docstring_example(self) -> None:
        # Directly from the module docstring
        base = {"bg_main": "#BFBFBF", "fg_title": "#0000FF"}
        overrides = {"bg_main": "#222222", "fg_title": "notacolor"}
        result = merge_theme_colors(base, overrides)
        assert result == {"bg_main": "#222222", "fg_title": "#0000FF"}

    def test_case_sensitive_key_matching(self) -> None:
        # Key matching is exact (dict key equality)
        base = {"bg_main": "#FFFFFF"}
        overrides = {"BG_MAIN": "#000000"}
        result = merge_theme_colors(base, overrides)
        assert result["bg_main"] == "#FFFFFF"   # unchanged
        assert result["BG_MAIN"] == "#000000"   # added as new key


# =========================================================================
# build_dialog_stylesheet  (Qt-free; pure string builder in theme.py)
# These tests cover the theming mechanism now wired into _HistoryDialog and
# _AddUnitDialog via the `colors` parameter introduced in this pass.
# =========================================================================

class TestBuildDialogStylesheet:
    """build_dialog_stylesheet is Qt-free (no PySide6 import) and can be
    exercised as plain Python.  It must embed bg_dialog and fg_main from the
    supplied color mapping."""

    def test_light_theme_contains_bg_dialog(self) -> None:
        css = build_dialog_stylesheet(LIGHT_THEME.colors)
        assert LIGHT_THEME.colors["bg_dialog"] in css

    def test_light_theme_contains_fg_main(self) -> None:
        css = build_dialog_stylesheet(LIGHT_THEME.colors)
        assert LIGHT_THEME.colors["fg_main"] in css

    def test_dark_theme_contains_bg_dialog(self) -> None:
        css = build_dialog_stylesheet(DARK_THEME.colors)
        assert DARK_THEME.colors["bg_dialog"] in css

    def test_dark_theme_contains_fg_main(self) -> None:
        css = build_dialog_stylesheet(DARK_THEME.colors)
        assert DARK_THEME.colors["fg_main"] in css

    def test_custom_override_bg_dialog_is_used(self) -> None:
        # Simulates what MainWindow._active_colors looks like after a user
        # override: bg_dialog is changed, all other keys come from base theme.
        colors = dict(LIGHT_THEME.colors)
        colors["bg_dialog"] = "#ABCDEF"
        css = build_dialog_stylesheet(colors)
        assert "#ABCDEF" in css

    def test_custom_override_fg_main_is_used(self) -> None:
        colors = dict(DARK_THEME.colors)
        colors["fg_main"] = "#123456"
        css = build_dialog_stylesheet(colors)
        assert "#123456" in css

    def test_returns_nonempty_string(self) -> None:
        css = build_dialog_stylesheet(LIGHT_THEME.colors)
        assert isinstance(css, str) and len(css) > 0

    def test_light_and_dark_produce_different_output(self) -> None:
        # The two built-in palettes have different bg_dialog values, so the
        # stylesheets must differ.
        assert (
            build_dialog_stylesheet(LIGHT_THEME.colors)
            != build_dialog_stylesheet(DARK_THEME.colors)
        )

    def test_no_pyside6_imported_by_theme(self) -> None:
        # theme.py must not contain any PySide6 import statement.
        # Source-text scan is order-independent; sys.modules checks are not
        # (other test modules in the same session may import PySide6 legitimately).
        src_path = (
            Path(__file__).resolve().parent.parent
            / "unit_converter" / "gui" / "theme.py"
        )
        src = src_path.read_text(encoding="utf-8")
        pyside_imports = [
            line.strip() for line in src.splitlines()
            if line.strip().startswith(("from PySide6", "import PySide6"))
        ]
        assert pyside_imports == [], (
            f"theme.py contains PySide6 import(s): {pyside_imports}"
        )


# =========================================================================
# Hover-description invariant lock  (Qt-free: source-text scan only)
#
# Guards TWO complementary invariants:
#
# 1. setToolTip floor — every interactive control that had a native Qt tooltip
#    still has one (count must not regress below the established floor).
#
# 2. DescriptionLabel / attach_description coverage — the two widget pairs that
#    must show INSTANT descriptions (unit combos, sweep labels) are wired via
#    attach_description in main_window.py, and the description module exists
#    with the required public API symbols.
#
# Both locks are pure source-text scans — no Qt/display required.
# =========================================================================

# Floor established after the Light/Dark theming + Settings pass.
# The DescriptionLabel additions are ADDITIVE — they do not replace setToolTip
# calls, so this count must stay at or above 19.
_MIN_SETTOOLTIP_CALLS = 19

# Minimum number of attach_description call-sites in main_window.py.
# _make_unit_row and _make_entry_row each contain one call-site, and each is
# invoked for slot=1 and slot=2 at runtime — so 2 source call-sites produce
# 4 DescriptionLabel objects.  The source scan sees 2.
_MIN_ATTACH_DESCRIPTION_CALLS = 2


def _main_window_source() -> str:
    src = (
        Path(__file__).resolve().parent.parent
        / "unit_converter" / "gui" / "main_window.py"
    )
    return src.read_text(encoding="utf-8")


def _description_module_source() -> str:
    src = (
        Path(__file__).resolve().parent.parent
        / "unit_converter" / "gui" / "description.py"
    )
    return src.read_text(encoding="utf-8")


class TestTooltipInvariant:
    """
    The GUI must keep its hover tooltips AND its instant descriptions.

    Invariant 1 (setToolTip floor): every interactive control keeps its Qt
    native tooltip — the count of setToolTip( calls must not regress.

    Invariant 2 (DescriptionLabel coverage): the two specified widget pairs
    (unit combos + sweep labels) have instant descriptions via
    attach_description.  The description.py module must export the required
    public API symbols.

    All checks are pure source-text scans — no Qt/display required.
    """

    # -- Invariant 1: setToolTip count floor --

    def test_setooltip_count_does_not_regress(self) -> None:
        count = _main_window_source().count("setToolTip(")
        assert count >= _MIN_SETTOOLTIP_CALLS, (
            f"setToolTip( count regressed: found {count}, "
            f"expected >= {_MIN_SETTOOLTIP_CALLS}. A hover tooltip was dropped."
        )

    # -- Invariant 2a: attach_description wired in main_window.py --

    def test_attach_description_imported_in_main_window(self) -> None:
        src = _main_window_source()
        assert "attach_description" in src, (
            "attach_description is not imported/used in main_window.py. "
            "Instant description overlays are not wired."
        )

    def test_attach_description_call_count_not_below_floor(self) -> None:
        count = _main_window_source().count("attach_description(")
        assert count >= _MIN_ATTACH_DESCRIPTION_CALLS, (
            f"attach_description( call count regressed: found {count}, "
            f"expected >= {_MIN_ATTACH_DESCRIPTION_CALLS}. "
            "An instant description for a unit combo or sweep label was dropped."
        )

    # -- Invariant 2b: description.py API symbols --

    def test_description_module_exports_attach_description(self) -> None:
        src = _description_module_source()
        assert "def attach_description" in src, (
            "attach_description function not found in description.py."
        )

    def test_description_module_exports_build_stylesheet(self) -> None:
        src = _description_module_source()
        assert "def build_description_stylesheet" in src, (
            "build_description_stylesheet not found in description.py."
        )

    def test_description_module_has_show_delay_param(self) -> None:
        src = _description_module_source()
        assert "show_delay_ms" in src, (
            "show_delay_ms parameter not found in description.py — "
            "delay configurability requirement is broken."
        )

    def test_description_module_has_max_wrap_width_param(self) -> None:
        src = _description_module_source()
        assert "max_wrap_width" in src, (
            "max_wrap_width parameter not found in description.py — "
            "auto-size/wrap requirement is broken."
        )

    def test_description_module_has_restyle_method(self) -> None:
        src = _description_module_source()
        assert "def restyle" in src, (
            "restyle method not found in description.py — "
            "theme-change wiring is broken."
        )

    # -- Qt-freedom guard --

    def test_no_pyside6_imported_by_this_scan(self) -> None:
        # theme_persist.py and theme.py must not contain PySide6 import
        # statements.  Source-text scan is order-independent; checking
        # sys.modules is not safe when other test modules in the same
        # pytest session legitimately import PySide6 (e.g. test_description.py).
        for mod_rel in (
            ("unit_converter", "gui", "theme_persist.py"),
            ("unit_converter", "gui", "theme.py"),
        ):
            src_path = Path(__file__).resolve().parent.parent.joinpath(*mod_rel)
            src = src_path.read_text(encoding="utf-8")
            bad = [
                line.strip() for line in src.splitlines()
                if line.strip().startswith(("from PySide6", "import PySide6"))
            ]
            assert bad == [], (
                f"{src_path.name} contains PySide6 import(s): {bad}"
            )
