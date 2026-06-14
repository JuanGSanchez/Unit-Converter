"""
tests/test_converter.py
=======================
Pytest suite for unit_converter.core.converter.

Covers:
- list_magnitudes()        — happy path, sorted order, returns list
- list_units()             — happy path, ValueError on unknown magnitude
- convert()                — happy paths, round-trips, SI/IEC prefix keys,
                             clamping (negative / NaN / inf), unknown magnitude /
                             unit / order ValueError, zero-factor guard
- reload_database()        — TOML fixture, legacy Magnitudes.txt fixture
- DICT_ORDER_SI / _IEC     — entry counts
"""
from __future__ import annotations

import math
import textwrap
from pathlib import Path

import pytest

import unit_converter.core.converter as conv
from unit_converter.core.converter import (
    DICT_ORDER_IEC,
    DICT_ORDER_SI,
    IncompatibleUnitsError,
    convert,
    list_magnitudes,
    list_units,
    reload_database,
)
from unit_converter.core.data_loader import MagnitudeDataError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_toml(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _write_legacy(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    """
    Reload the default database before and after every test so one test's
    reload_database() call cannot pollute a subsequent test.
    """
    reload_database()          # reset to shipped TOML at start
    yield
    reload_database()          # reset again after test


@pytest.fixture()
def toml_dir(tmp_path: Path) -> Path:
    """Minimal valid TOML data directory with two magnitudes."""
    _write_toml(
        tmp_path / "magnitudes.toml",
        """\
        [TestMass]
        base_unit = "gram (g)"
        [TestMass.units]
        "gram (g)" = 1.0
        "kilogram (kg)" = 1000.0

        [TestData]
        base_unit = "bit (b)"
        [TestData.units]
        "bit (b)" = 1.0
        "byte (B)" = 8.0
        """,
    )
    return tmp_path


@pytest.fixture()
def legacy_dir(tmp_path: Path) -> Path:
    """Minimal valid legacy Magnitudes.txt data directory."""
    _write_legacy(
        tmp_path / "Magnitudes.txt",
        """\
        LegacyMass
        gram (g),Av. pound (lb)
        1.0,453.6
        LegacyLength
        meter (m),inch (in)
        1.0,0.0254
        """,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# DICT_ORDER_SI / DICT_ORDER_IEC entry counts
# ---------------------------------------------------------------------------

class TestOrderTables:
    def test_si_has_21_entries(self):
        assert len(DICT_ORDER_SI) == 21

    def test_iec_has_11_entries(self):
        assert len(DICT_ORDER_IEC) == 11

    def test_si_contains_no_prefix(self):
        assert "1" in DICT_ORDER_SI
        assert DICT_ORDER_SI["1"] == 0

    def test_iec_contains_no_prefix(self):
        assert "1" in DICT_ORDER_IEC
        assert DICT_ORDER_IEC["1"] == 0

    def test_si_kilo_is_3(self):
        assert DICT_ORDER_SI["k"] == 3

    def test_iec_kilo_is_1(self):
        assert DICT_ORDER_IEC["k"] == 1

    def test_si_mega_is_6(self):
        assert DICT_ORDER_SI["M"] == 6

    def test_iec_mega_is_2(self):
        assert DICT_ORDER_IEC["M"] == 2


# ---------------------------------------------------------------------------
# list_magnitudes
# ---------------------------------------------------------------------------

class TestListMagnitudes:
    def test_returns_list(self):
        result = list_magnitudes()
        assert isinstance(result, list)

    def test_sorted(self):
        result = list_magnitudes()
        assert result == sorted(result)

    def test_nonempty(self):
        assert len(list_magnitudes()) > 0

    def test_contains_known_magnitudes(self):
        mags = list_magnitudes()
        for mag in ("Mass", "Length", "Area", "Data", "Time"):
            assert mag in mags

    def test_custom_toml_dir(self, toml_dir):
        reload_database(str(toml_dir))
        mags = list_magnitudes()
        assert "TestMass" in mags
        assert "TestData" in mags

    def test_custom_legacy_dir(self, legacy_dir):
        reload_database(str(legacy_dir))
        mags = list_magnitudes()
        assert "LegacyMass" in mags
        assert "LegacyLength" in mags


# ---------------------------------------------------------------------------
# list_units
# ---------------------------------------------------------------------------

class TestListUnits:
    def test_returns_dict_with_units_and_base(self):
        result = list_units("Mass")
        assert "units" in result
        assert "base_unit" in result

    def test_units_is_list(self):
        assert isinstance(list_units("Mass")["units"], list)

    def test_base_unit_is_first(self):
        result = list_units("Mass")
        assert result["base_unit"] == result["units"][0]

    def test_known_mass_units(self):
        units = list_units("Mass")["units"]
        assert "gram (g)" in units
        assert "Av. pound (lb)" in units

    def test_unknown_magnitude_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown magnitude"):
            list_units("NoSuchMagnitude")

    def test_data_units(self):
        result = list_units("Data")
        assert "bit (b)" in result["units"]
        assert "byte (B)" in result["units"]

    def test_custom_toml_dir(self, toml_dir):
        reload_database(str(toml_dir))
        result = list_units("TestMass")
        assert result["base_unit"] == "gram (g)"
        assert "kilogram (kg)" in result["units"]


# ---------------------------------------------------------------------------
# convert — happy paths
# ---------------------------------------------------------------------------

class TestConvertHappyPaths:
    def test_same_unit_identity(self):
        result = convert("Mass", 1.0, "gram (g)", "gram (g)")
        assert result == pytest.approx(1.0)

    def test_mass_gram_to_pound(self):
        # 1 gram → 1/453.6 lb
        result = convert("Mass", 1.0, "gram (g)", "Av. pound (lb)")
        assert result == pytest.approx(1.0 / 453.6, rel=1e-5)

    def test_mass_pound_to_gram(self):
        result = convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
        assert result == pytest.approx(453.6, rel=1e-5)

    def test_length_meter_to_inch(self):
        result = convert("Length", 1.0, "meter (m)", "inch (in)")
        assert result == pytest.approx(1.0 / 0.0254, rel=1e-5)

    def test_time_hour_to_second(self):
        result = convert("Time", 1.0, "hour (hr)", "second (s)")
        assert result == pytest.approx(3600.0, rel=1e-9)

    def test_data_byte_to_bit(self):
        result = convert("Data", 1.0, "byte (B)", "bit (b)")
        assert result == pytest.approx(8.0)

    def test_data_bit_to_byte(self):
        result = convert("Data", 8.0, "bit (b)", "byte (B)")
        assert result == pytest.approx(1.0)

    def test_energy_joule_to_calorie(self):
        result = convert("Energy", 4.184, "joule (J)", "calorie (cal)")
        assert result == pytest.approx(1.0, rel=1e-5)

    def test_pressure_pascal_to_bar(self):
        result = convert("Pressure", 100000.0, "Pascal (Pa)", "bar (b)")
        assert result == pytest.approx(1.0, rel=1e-9)

    def test_volume_cubic_meter_to_litre(self):
        result = convert("Volume", 1.0, "cubic meter (m³)", "litre (l)")
        assert result == pytest.approx(1000.0, rel=1e-6)

    def test_power_watt_to_hp(self):
        result = convert("Power", 745.7, "watt (W)", "HP")
        assert result == pytest.approx(1.0, rel=1e-5)


# ---------------------------------------------------------------------------
# convert — SI prefix / order scaling
# ---------------------------------------------------------------------------

class TestConvertSIOrders:
    def test_kilo_prefix_from_side(self):
        # 1 km → 1000 m
        result = convert("Length", 1.0, "meter (m)", "meter (m)", from_order="k", to_order="1")
        assert result == pytest.approx(1000.0)

    def test_kilo_prefix_to_side(self):
        # 1000 m → 1 km
        result = convert("Length", 1000.0, "meter (m)", "meter (m)", from_order="1", to_order="k")
        assert result == pytest.approx(1.0)

    def test_mega_prefix(self):
        # 1 Mm = 1e6 m
        result = convert("Length", 1.0, "meter (m)", "meter (m)", from_order="M", to_order="1")
        assert result == pytest.approx(1e6)

    def test_milli_prefix(self):
        # 1 mm = 0.001 m
        result = convert("Length", 1.0, "meter (m)", "meter (m)", from_order="m", to_order="1")
        assert result == pytest.approx(1e-3)

    def test_no_prefix_is_identity_on_scale(self):
        result = convert("Mass", 5.0, "gram (g)", "gram (g)", from_order="1", to_order="1")
        assert result == pytest.approx(5.0)

    def test_si_key_not_in_iec_raises_for_data(self):
        # SI-only key "m" (milli) is not in IEC table → ValueError
        with pytest.raises(ValueError, match="Unknown order prefix"):
            convert("Data", 1.0, "bit (b)", "bit (b)", from_order="m", to_order="1")

    def test_iec_key_in_data_magnitude(self):
        # 1 kibibit (k prefix, IEC base 1024) of bits
        result = convert("Data", 1.0, "bit (b)", "bit (b)", from_order="k", to_order="1")
        assert result == pytest.approx(1024.0)

    def test_iec_mega_is_1024_squared(self):
        # 1 Mebi-bit = 1024^2 bits
        result = convert("Data", 1.0, "bit (b)", "bit (b)", from_order="M", to_order="1")
        assert result == pytest.approx(1024 ** 2)


# ---------------------------------------------------------------------------
# convert — round-trip conversions
# ---------------------------------------------------------------------------

class TestConvertRoundTrips:
    """value → other unit → back must equal the original value."""

    def test_mass_gram_pound_roundtrip(self):
        original = 123.456
        lb = convert("Mass", original, "gram (g)", "Av. pound (lb)")
        back = convert("Mass", lb, "Av. pound (lb)", "gram (g)")
        assert back == pytest.approx(original, rel=1e-9)

    def test_length_meter_mile_roundtrip(self):
        original = 42.0
        mi = convert("Length", original, "meter (m)", "mile (mi)")
        back = convert("Length", mi, "mile (mi)", "meter (m)")
        assert back == pytest.approx(original, rel=1e-9)

    def test_data_bit_byte_roundtrip(self):
        original = 64.0
        b = convert("Data", original, "bit (b)", "byte (B)")
        back = convert("Data", b, "byte (B)", "bit (b)")
        assert back == pytest.approx(original, rel=1e-12)

    def test_time_hour_day_roundtrip(self):
        original = 7.5
        d = convert("Time", original, "hour (hr)", "day (d)")
        back = convert("Time", d, "day (d)", "hour (hr)")
        assert back == pytest.approx(original, rel=1e-9)

    def test_energy_joule_wh_roundtrip(self):
        original = 3600.0
        wh = convert("Energy", original, "joule (J)", "watt-hour (Wh)")
        back = convert("Energy", wh, "watt-hour (Wh)", "joule (J)")
        assert back == pytest.approx(original, rel=1e-9)

    def test_prefix_roundtrip_km(self):
        # 5 km expressed in m then back to km
        m = convert("Length", 5.0, "meter (m)", "meter (m)", from_order="k", to_order="1")
        km_back = convert("Length", m, "meter (m)", "meter (m)", from_order="1", to_order="k")
        assert km_back == pytest.approx(5.0, rel=1e-12)


# ---------------------------------------------------------------------------
# convert — input clamping (negative / NaN / inf)
# ---------------------------------------------------------------------------

class TestConvertClamping:
    def test_negative_value_clamped_to_zero(self):
        assert convert("Mass", -1.0, "gram (g)", "Av. pound (lb)") == 0.0

    def test_zero_value_returns_zero(self):
        assert convert("Mass", 0.0, "gram (g)", "Av. pound (lb)") == 0.0

    def test_nan_clamped_to_zero(self):
        assert convert("Mass", math.nan, "gram (g)", "Av. pound (lb)") == 0.0

    def test_pos_inf_clamped_to_zero(self):
        assert convert("Mass", math.inf, "gram (g)", "Av. pound (lb)") == 0.0

    def test_neg_inf_clamped_to_zero(self):
        assert convert("Mass", -math.inf, "gram (g)", "Av. pound (lb)") == 0.0

    def test_very_small_positive_not_clamped(self):
        result = convert("Mass", 1e-300, "gram (g)", "gram (g)")
        assert result == pytest.approx(1e-300)

    def test_large_positive_not_clamped(self):
        result = convert("Mass", 1e15, "gram (g)", "gram (g)")
        assert result == pytest.approx(1e15)


# ---------------------------------------------------------------------------
# convert — error cases
# ---------------------------------------------------------------------------

class TestConvertErrors:
    def test_unknown_magnitude_raises(self):
        with pytest.raises(ValueError, match="Unknown magnitude"):
            convert("NoSuchMag", 1.0, "gram (g)", "gram (g)")

    def test_unknown_from_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            convert("Mass", 1.0, "no_such_unit", "gram (g)")

    def test_unknown_to_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            convert("Mass", 1.0, "gram (g)", "no_such_unit")

    def test_unknown_from_order_raises(self):
        with pytest.raises(ValueError, match="Unknown order prefix"):
            convert("Mass", 1.0, "gram (g)", "gram (g)", from_order="NOPE")

    def test_unknown_to_order_raises(self):
        with pytest.raises(ValueError, match="Unknown order prefix"):
            convert("Mass", 1.0, "gram (g)", "gram (g)", to_order="NOPE")

    def test_zero_factor_guard_raises(self, tmp_path):
        """Zero factor in database triggers the second-line-of-defence ValueError."""
        _write_toml(
            tmp_path / "magnitudes.toml",
            """\
            [BadMag]
            base_unit = "unit_a"
            [BadMag.units]
            "unit_a" = 1.0
            "unit_b" = 0.00001
            """,
        )
        # Directly inject a zero factor by patching the module-level _db
        reload_database(str(tmp_path))
        # Now manually set the to_unit factor to 0 to exercise the guard
        conv._db["BadMag"]["unit_b"] = 0.0
        with pytest.raises(ValueError, match="factor.*zero"):
            convert("BadMag", 1.0, "unit_a", "unit_b")
        # restore
        reload_database()


# ---------------------------------------------------------------------------
# reload_database — TOML and legacy data paths
# ---------------------------------------------------------------------------

class TestReloadDatabase:
    def test_reload_with_toml_dir(self, toml_dir):
        reload_database(str(toml_dir))
        mags = list_magnitudes()
        assert "TestMass" in mags
        assert "TestData" in mags

    def test_reload_with_legacy_dir(self, legacy_dir):
        reload_database(str(legacy_dir))
        mags = list_magnitudes()
        assert "LegacyMass" in mags

    def test_reload_restores_default(self, toml_dir):
        reload_database(str(toml_dir))
        assert "Mass" not in list_magnitudes()
        reload_database()
        assert "Mass" in list_magnitudes()

    def test_toml_takes_precedence_over_legacy(self, tmp_path):
        """When both files exist in the same dir, TOML wins."""
        _write_toml(
            tmp_path / "magnitudes.toml",
            """\
            [TomlMag]
            base_unit = "u1"
            [TomlMag.units]
            "u1" = 1.0
            """,
        )
        _write_legacy(
            tmp_path / "Magnitudes.txt",
            """\
            LegacyMag
            u1,u2
            1.0,2.0
            """,
        )
        reload_database(str(tmp_path))
        mags = list_magnitudes()
        assert "TomlMag" in mags
        assert "LegacyMag" not in mags

    def test_missing_dir_raises_magnitude_data_error(self, tmp_path):
        empty = tmp_path / "no_such_subdir"
        with pytest.raises(MagnitudeDataError, match="No magnitude database found"):
            reload_database(str(empty))

    def test_same_dir_skips_reload(self, toml_dir):
        """Calling reload with the same dir twice should still work."""
        reload_database(str(toml_dir))
        mags_first = list_magnitudes()
        reload_database(str(toml_dir))
        mags_second = list_magnitudes()
        assert mags_first == mags_second


# ---------------------------------------------------------------------------
# UC-I01 — significant-figures rounding
# ---------------------------------------------------------------------------

class TestSigFigs:
    def test_sig_figs_3_pound_to_gram(self):
        result = convert("Mass", 1.0, "Av. pound (lb)", "gram (g)", sig_figs=3)
        assert result == pytest.approx(454.0, rel=1e-9)

    def test_sig_figs_1(self):
        result = convert("Mass", 123.456, "gram (g)", "gram (g)", sig_figs=1)
        assert result == pytest.approx(100.0, rel=1e-9)

    def test_sig_figs_none_preserves_precision(self):
        r1 = convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
        r2 = convert("Mass", 1.0, "Av. pound (lb)", "gram (g)", sig_figs=None)
        assert r1 == r2

    def test_sig_figs_zero_raises(self):
        with pytest.raises(ValueError, match="sig_figs"):
            convert("Mass", 1.0, "gram (g)", "gram (g)", sig_figs=0)

    def test_sig_figs_negative_raises(self):
        with pytest.raises(ValueError, match="sig_figs"):
            convert("Mass", 1.0, "gram (g)", "gram (g)", sig_figs=-1)

    def test_sig_figs_float_raises(self):
        with pytest.raises(ValueError, match="sig_figs"):
            convert("Mass", 1.0, "gram (g)", "gram (g)", sig_figs=2.5)

    def test_sig_figs_zero_value_returns_zero(self):
        assert convert("Mass", 0.0, "gram (g)", "gram (g)", sig_figs=3) == 0.0


# ---------------------------------------------------------------------------
# UC-I02 — IncompatibleUnitsError / dimensional guard
# ---------------------------------------------------------------------------

class TestIncompatibleUnitsError:
    def test_incompatible_units_error_is_value_error(self):
        assert issubclass(IncompatibleUnitsError, ValueError)

    def test_unknown_from_unit_raises_incompatible(self):
        with pytest.raises(IncompatibleUnitsError, match="Unknown unit"):
            convert("Mass", 1.0, "meter (m)", "gram (g)")

    def test_unknown_to_unit_raises_incompatible(self):
        with pytest.raises(IncompatibleUnitsError, match="Unknown unit"):
            convert("Mass", 1.0, "gram (g)", "meter (m)")

    def test_valid_same_magnitude_not_raised(self):
        result = convert("Mass", 1.0, "gram (g)", "Av. pound (lb)")
        assert result > 0.0


# ---------------------------------------------------------------------------
# UC-I04 — Temperature affine conversions
# ---------------------------------------------------------------------------

class TestTemperatureAffine:
    def test_celsius_to_fahrenheit_freezing(self):
        # 0°C -> 32°F
        result = convert("Temperature", 0.0, "celsius (°C)", "fahrenheit (°F)")
        assert result == pytest.approx(32.0, abs=1e-6)

    def test_celsius_to_fahrenheit_boiling(self):
        # 100°C -> 212°F
        result = convert("Temperature", 100.0, "celsius (°C)", "fahrenheit (°F)")
        assert result == pytest.approx(212.0, abs=1e-4)

    def test_celsius_to_kelvin_freezing(self):
        # 0°C -> 273.15 K
        result = convert("Temperature", 0.0, "celsius (°C)", "kelvin (K)")
        assert result == pytest.approx(273.15, abs=1e-6)

    def test_kelvin_to_celsius_roundtrip(self):
        k = convert("Temperature", 100.0, "celsius (°C)", "kelvin (K)")
        c = convert("Temperature", k, "kelvin (K)", "celsius (°C)")
        assert c == pytest.approx(100.0, abs=1e-6)

    def test_fahrenheit_to_celsius_freezing(self):
        # 32°F -> 0°C
        result = convert("Temperature", 32.0, "fahrenheit (°F)", "celsius (°C)")
        assert result == pytest.approx(0.0, abs=1e-4)

    def test_temperature_exists_in_magnitudes(self):
        mags = list_magnitudes()
        assert "Temperature" in mags

    def test_temperature_units_listed(self):
        units = list_units("Temperature")["units"]
        assert "kelvin (K)" in units
        assert "celsius (°C)" in units
        assert "fahrenheit (°F)" in units

    def test_temperature_delta_scale_only(self):
        # ΔT: 1°C increment = 1 K increment (scale only, no offset)
        result = convert("Temperature_delta", 1.0, "celsius (°C)", "kelvin (K)")
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_existing_magnitude_regression(self):
        # Existing magnitudes must be unaffected by the affine path
        assert convert("Mass", 1.0, "gram (g)", "gram (g)") == pytest.approx(1.0)
        assert convert("Length", 1.0, "meter (m)", "meter (m)") == pytest.approx(1.0)
