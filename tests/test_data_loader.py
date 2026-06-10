"""
tests/test_data_loader.py
=========================
Pytest suite for unit_converter.core.data_loader.

Covers:
- load_magnitudes()         — TOML path, legacy path, TOML-priority, missing dir
- MagnitudeDataError        — is a ValueError subclass
- _load_toml internals      — structural errors (missing 'units', bad factor, empty table,
                              TOML decode error, zero factor, negative factor, NaN/Inf factor)
- _load_legacy internals    — blank-line tolerance, superscript substitution,
                              mismatched counts, non-3-multiple lines, bad float,
                              zero factor, file-not-found
- _apply_superscripts       — direct unit tests for the superscript helper
- _validate_factor          — direct unit tests for all four error branches
"""
from __future__ import annotations

import math
import textwrap
from pathlib import Path

import pytest

from unit_converter.core.data_loader import (
    MagnitudeDataError,
    _apply_superscripts,
    _validate_factor,
    load_magnitudes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "magnitudes.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


def legacy(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "Magnitudes.txt"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# MagnitudeDataError
# ---------------------------------------------------------------------------

class TestMagnitudeDataError:
    def test_is_value_error_subclass(self):
        err = MagnitudeDataError("test")
        assert isinstance(err, ValueError)

    def test_message_preserved(self):
        err = MagnitudeDataError("something went wrong")
        assert "something went wrong" in str(err)

    def test_can_be_raised_and_caught_as_valueerror(self):
        with pytest.raises(ValueError):
            raise MagnitudeDataError("boom")


# ---------------------------------------------------------------------------
# load_magnitudes — TOML path
# ---------------------------------------------------------------------------

class TestLoadMagnitudesToml:
    def test_loads_valid_toml(self, tmp_path):
        d = toml(tmp_path, """\
            [Mass]
            base_unit = "gram (g)"
            [Mass.units]
            "gram (g)" = 1.0
            "kg" = 1000.0
            """)
        db = load_magnitudes(d)
        assert "Mass" in db
        assert db["Mass"]["gram (g)"] == 1.0
        assert db["Mass"]["kg"] == 1000.0

    def test_returns_dict_of_dicts(self, tmp_path):
        d = toml(tmp_path, """\
            [X]
            base_unit = "u"
            [X.units]
            "u" = 1.0
            """)
        db = load_magnitudes(d)
        assert isinstance(db, dict)
        assert isinstance(db["X"], dict)

    def test_multiple_magnitudes(self, tmp_path):
        d = toml(tmp_path, """\
            [A]
            base_unit = "a1"
            [A.units]
            "a1" = 1.0
            "a2" = 2.0

            [B]
            base_unit = "b1"
            [B.units]
            "b1" = 1.0
            """)
        db = load_magnitudes(d)
        assert set(db.keys()) == {"A", "B"}

    def test_toml_missing_units_key_raises(self, tmp_path):
        d = toml(tmp_path, """\
            [Mass]
            base_unit = "gram (g)"
            """)
        with pytest.raises(MagnitudeDataError, match="missing the required 'units' key"):
            load_magnitudes(d)

    def test_toml_empty_units_raises(self, tmp_path):
        d = toml(tmp_path, """\
            [Mass]
            base_unit = "gram (g)"
            [Mass.units]
            """)
        # Empty inline table — magnitude has no units
        # This will either raise on parse or on empty validation
        with pytest.raises(MagnitudeDataError):
            load_magnitudes(d)

    def test_toml_zero_factor_raises(self, tmp_path):
        d = toml(tmp_path, """\
            [Mass]
            base_unit = "gram (g)"
            [Mass.units]
            "gram (g)" = 1.0
            "bad" = 0.0
            """)
        with pytest.raises(MagnitudeDataError, match="zero"):
            load_magnitudes(d)

    def test_toml_negative_factor_raises(self, tmp_path):
        d = toml(tmp_path, """\
            [Mass]
            base_unit = "gram (g)"
            [Mass.units]
            "gram (g)" = 1.0
            "bad" = -5.0
            """)
        with pytest.raises(MagnitudeDataError, match="negative"):
            load_magnitudes(d)

    def test_toml_empty_top_level_raises(self, tmp_path):
        d = toml(tmp_path, "")
        with pytest.raises(MagnitudeDataError):
            load_magnitudes(d)

    def test_toml_decode_error_raises(self, tmp_path):
        p = tmp_path / "magnitudes.toml"
        p.write_text("[[[ not valid toml", encoding="utf-8")
        with pytest.raises(MagnitudeDataError, match="TOML parse error"):
            load_magnitudes(tmp_path)

    def test_toml_file_not_found_raises(self, tmp_path):
        """Pointing directly at a nonexistent TOML raises MagnitudeDataError."""
        # No magnitudes.toml or Magnitudes.txt in a fresh empty subdir
        empty = tmp_path / "empty_subdir"
        empty.mkdir()
        with pytest.raises(MagnitudeDataError, match="No magnitude database found"):
            load_magnitudes(empty)


# ---------------------------------------------------------------------------
# load_magnitudes — legacy path
# ---------------------------------------------------------------------------

class TestLoadMagnitudesLegacy:
    def test_loads_valid_legacy(self, tmp_path):
        d = legacy(tmp_path, """\
            Mass
            gram (g),Av. pound (lb)
            1.0,453.6
            """)
        db = load_magnitudes(d)
        assert "Mass" in db
        assert db["Mass"]["gram (g)"] == pytest.approx(1.0)
        assert db["Mass"]["Av. pound (lb)"] == pytest.approx(453.6)

    def test_blank_lines_tolerated(self, tmp_path):
        """Extra blank lines between blocks must not break parsing."""
        d = legacy(tmp_path, """\
            Mass
            gram (g),kg
            1.0,1000.0

            Length
            meter (m),inch (in)
            1.0,0.0254

            """)
        db = load_magnitudes(d)
        assert "Mass" in db
        assert "Length" in db

    def test_superscript_m2_substitution(self, tmp_path):
        d = legacy(tmp_path, """\
            Area
            square meter (m2),square inch (in2)
            1.0,0.00064516
            """)
        db = load_magnitudes(d)
        assert "Area" in db
        units = list(db["Area"].keys())
        assert "square meter (m²)" in units
        assert "square inch (in²)" in units

    def test_superscript_m3_substitution(self, tmp_path):
        d = legacy(tmp_path, """\
            Volume
            cubic meter (m3),litre (l)
            1.0,0.001
            """)
        db = load_magnitudes(d)
        units = list(db["Volume"].keys())
        assert "cubic meter (m³)" in units

    def test_non_three_multiple_lines_raises(self, tmp_path):
        d = legacy(tmp_path, """\
            Mass
            gram (g),kg
            """)
        with pytest.raises(MagnitudeDataError, match="not.*divisible by 3"):
            load_magnitudes(d)

    def test_mismatched_unit_factor_count_raises(self, tmp_path):
        d = legacy(tmp_path, """\
            Mass
            gram (g),kg,oz
            1.0,1000.0
            """)
        with pytest.raises(MagnitudeDataError, match="count"):
            load_magnitudes(d)

    def test_bad_float_factor_raises(self, tmp_path):
        d = legacy(tmp_path, """\
            Mass
            gram (g),kg
            1.0,NOT_A_NUMBER
            """)
        with pytest.raises(MagnitudeDataError, match="cannot parse factor"):
            load_magnitudes(d)

    def test_zero_factor_raises(self, tmp_path):
        d = legacy(tmp_path, """\
            Mass
            gram (g),bad_unit
            1.0,0.0
            """)
        with pytest.raises(MagnitudeDataError, match="zero"):
            load_magnitudes(d)

    def test_file_not_found_falls_through_to_error(self, tmp_path):
        empty = tmp_path / "no_data"
        empty.mkdir()
        with pytest.raises(MagnitudeDataError):
            load_magnitudes(empty)

    def test_scientific_notation_factor(self, tmp_path):
        d = legacy(tmp_path, """\
            Energy
            joule (J),electronvolt (eV)
            1.0,1.6022E-19
            """)
        db = load_magnitudes(d)
        assert db["Energy"]["electronvolt (eV)"] == pytest.approx(1.6022e-19)

    def test_multiple_magnitudes_in_legacy(self, tmp_path):
        d = legacy(tmp_path, """\
            Mass
            gram (g),kg
            1.0,1000.0
            Length
            meter (m),inch (in)
            1.0,0.0254
            """)
        db = load_magnitudes(d)
        assert "Mass" in db
        assert "Length" in db

    def test_trailing_blank_lines_tolerated(self, tmp_path):
        p = tmp_path / "Magnitudes.txt"
        p.write_text("Mass\ngram (g),kg\n1.0,1000.0\n\n\n", encoding="utf-8")
        db = load_magnitudes(tmp_path)
        assert "Mass" in db


# ---------------------------------------------------------------------------
# TOML takes priority over legacy
# ---------------------------------------------------------------------------

class TestTomlPriority:
    def test_toml_wins_when_both_present(self, tmp_path):
        toml(tmp_path, """\
            [Toml]
            base_unit = "t1"
            [Toml.units]
            "t1" = 1.0
            """)
        legacy(tmp_path, """\
            Legacy
            l1,l2
            1.0,2.0
            """)
        db = load_magnitudes(tmp_path)
        assert "Toml" in db
        assert "Legacy" not in db


# ---------------------------------------------------------------------------
# _apply_superscripts — direct unit tests
# ---------------------------------------------------------------------------

class TestApplySuperscripts:
    def test_m2_becomes_m_squared(self):
        assert _apply_superscripts("square meter (m2)") == "square meter (m²)"

    def test_m3_becomes_m_cubed(self):
        assert _apply_superscripts("cubic meter (m3)") == "cubic meter (m³)"

    def test_h2o_not_changed(self):
        """Digit in the middle of a word is not replaced."""
        assert _apply_superscripts("H2O") == "H2O"

    def test_in2_becomes_in_squared(self):
        assert _apply_superscripts("square inch (in2)") == "square inch (in²)"

    def test_no_digit_unchanged(self):
        assert _apply_superscripts("gram (g)") == "gram (g)"

    def test_empty_string_unchanged(self):
        assert _apply_superscripts("") == ""

    def test_trailing_3_not_inside_parens(self):
        # A unit name that ends with "3" directly (no parens)
        assert _apply_superscripts("unit3") == "unit³"

    def test_digit_1_not_in_superscript_map(self):
        """'1' is not in _SUPERSCRIPT_MAP so stays literal."""
        assert _apply_superscripts("unit1") == "unit1"


# ---------------------------------------------------------------------------
# _validate_factor — direct unit tests
# ---------------------------------------------------------------------------

class TestValidateFactor:
    def test_valid_factor_does_not_raise(self):
        _validate_factor("Mag", "unit", 1.0, Path("fake.toml"))

    def test_zero_raises(self):
        with pytest.raises(MagnitudeDataError, match="zero"):
            _validate_factor("Mag", "unit", 0.0, Path("fake.toml"))

    def test_negative_raises(self):
        with pytest.raises(MagnitudeDataError, match="negative"):
            _validate_factor("Mag", "unit", -1.0, Path("fake.toml"))

    def test_nan_raises(self):
        with pytest.raises(MagnitudeDataError, match="NaN"):
            _validate_factor("Mag", "unit", math.nan, Path("fake.toml"))

    def test_inf_raises(self):
        with pytest.raises(MagnitudeDataError, match="infinite"):
            _validate_factor("Mag", "unit", math.inf, Path("fake.toml"))

    def test_neg_inf_raises(self):
        with pytest.raises(MagnitudeDataError, match="infinite"):
            _validate_factor("Mag", "unit", -math.inf, Path("fake.toml"))

    def test_very_small_positive_valid(self):
        _validate_factor("Mag", "unit", 1e-300, Path("fake.toml"))

    def test_very_large_positive_valid(self):
        _validate_factor("Mag", "unit", 1e300, Path("fake.toml"))
