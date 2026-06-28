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
        # 1 gram → 1/453.59237 lb (NIST SP 811 exact value; factor corrected from 453.6)
        result = convert("Mass", 1.0, "gram (g)", "Av. pound (lb)")
        assert result == pytest.approx(1.0 / 453.59237, rel=1e-9)

    def test_mass_pound_to_gram(self):
        # 1 lb = 453.592 37 g (NIST SP 811 exact value; factor corrected from 453.6)
        result = convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
        assert result == pytest.approx(453.59237, rel=1e-9)

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
        # 1 mechanical HP = 745.699 871... W (NIST SP 811); factor corrected from 745.7
        result = convert("Power", 745.6998715822702, "watt (W)", "HP")
        assert result == pytest.approx(1.0, rel=1e-9)


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


# ---------------------------------------------------------------------------
# Value-locking tests: corrected existing factors (regression guard)
# ---------------------------------------------------------------------------

class TestCorrectedFactors:
    """
    Value-locking tests for factors that were corrected from rounded/approximate
    values to exact NIST SP 811 / BIPM definitions.  Each assertion references
    the authority cited in magnitudes.toml.
    """

    # Mass — NIST SP 811 Table B.8 exact definitions
    def test_mass_pound_exact(self):
        # 1 lb = 453.592 37 g (exact, NIST SP 811)
        assert convert("Mass", 1.0, "Av. pound (lb)", "gram (g)") == pytest.approx(453.59237, rel=1e-12)

    def test_mass_ounce_exact(self):
        # 1 oz = 28.349 523 125 g (exact = 453.59237/16)
        assert convert("Mass", 1.0, "Av. ounce (oz)", "gram (g)") == pytest.approx(28.349523125, rel=1e-12)

    def test_mass_16oz_equals_1lb(self):
        # round-trip: 16 oz == 1 lb
        oz_in_g = convert("Mass", 16.0, "Av. ounce (oz)", "gram (g)")
        lb_in_g = convert("Mass", 1.0, "Av. pound (lb)", "gram (g)")
        assert oz_in_g == pytest.approx(lb_in_g, rel=1e-12)

    # Length — NIST SP 811 Table B.8 exact definitions
    def test_length_mile_exact(self):
        # 1 mi = 1609.344 m (exact, NIST SP 811)
        assert convert("Length", 1.0, "mile (mi)", "meter (m)") == pytest.approx(1609.344, rel=1e-12)

    def test_length_foot_exact(self):
        # 1 ft = 0.3048 m (exact)
        assert convert("Length", 1.0, "foot (ft)", "meter (m)") == pytest.approx(0.3048, rel=1e-12)

    def test_length_mile_equals_5280_feet(self):
        # 1 mi = 5280 ft (exact by definition)
        mi_m = convert("Length", 1.0, "mile (mi)", "meter (m)")
        ft_m = convert("Length", 5280.0, "foot (ft)", "meter (m)")
        assert mi_m == pytest.approx(ft_m, rel=1e-12)

    # Area — corrected from rounded to exact squared-foot/yard/mile
    def test_area_sq_mile_exact(self):
        # 1 mi² = (1609.344)² = 2 589 988.110 336 m² (exact)
        assert convert("Area", 1.0, "square mile (mi²)", "square meter (m²)") == pytest.approx(2589988.110336, rel=1e-10)

    def test_area_sq_yard_exact(self):
        # 1 yd² = (0.9144)² = 0.836 127 36 m² (exact)
        assert convert("Area", 1.0, "square yard (yd²)", "square meter (m²)") == pytest.approx(0.83612736, rel=1e-12)

    # Power — corrected HP and CV
    def test_power_hp_mechanical(self):
        # 1 HP = 550 ft·lbf/s = 745.699 871 58... W (NIST SP 811)
        assert convert("Power", 1.0, "HP", "watt (W)") == pytest.approx(745.6998715822702, rel=1e-9)

    def test_power_cv_metric(self):
        # 1 CV = 75 kgf·m/s = 75 × 9.806 65 W = 735.498 75 W (exact)
        assert convert("Power", 1.0, "CV", "watt (W)") == pytest.approx(735.49875, rel=1e-12)

    def test_power_hp_not_equal_cv(self):
        # Mechanical HP ≠ metric HP (CV): verify distinct values
        hp_w = convert("Power", 1.0, "HP", "watt (W)")
        cv_w = convert("Power", 1.0, "CV", "watt (W)")
        assert hp_w != pytest.approx(cv_w, rel=1e-4)


# ---------------------------------------------------------------------------
# Value-locking tests: new units in existing magnitudes
# ---------------------------------------------------------------------------

class TestNewUnitsExistingMagnitudes:
    """
    Value-locking + round-trip tests for units added to pre-existing magnitudes.
    Each reference value is traceable to NIST SP 811 or equivalent authority.
    """

    # Mass — new units
    def test_mass_tonne_to_gram(self):
        # 1 t = 1 000 000 g (exact)
        assert convert("Mass", 1.0, "tonne (t)", "gram (g)") == pytest.approx(1_000_000.0, rel=1e-12)

    def test_mass_stone_exact(self):
        # 1 stone = 14 lb = 14 × 453.59237 g = 6350.29318 g (exact)
        assert convert("Mass", 1.0, "stone (st)", "gram (g)") == pytest.approx(6350.29318, rel=1e-10)

    def test_mass_grain_exact(self):
        # 1 gr = 64.798 91 mg = 0.064 798 91 g (NIST SP 811 exact)
        assert convert("Mass", 1.0, "grain (gr)", "gram (g)") == pytest.approx(0.06479891, rel=1e-9)

    def test_mass_carat_exact(self):
        # 1 ct = 200 mg = 0.2 g (exact)
        assert convert("Mass", 1.0, "carat (ct)", "gram (g)") == pytest.approx(0.2, rel=1e-12)

    def test_mass_amu_codata(self):
        # 1 u = 1.660 539 066 60 × 10⁻²⁴ g (NIST CODATA 2018)
        assert convert("Mass", 1.0, "unified atomic mass unit (u)", "gram (g)") == pytest.approx(1.66053906660e-24, rel=1e-9)

    def test_mass_roundtrip_stone(self):
        original = 10.0
        g = convert("Mass", original, "stone (st)", "gram (g)")
        back = convert("Mass", g, "gram (g)", "stone (st)")
        assert back == pytest.approx(original, rel=1e-9)

    # Length — new units
    def test_length_foot_roundtrip(self):
        original = 100.0
        m = convert("Length", original, "foot (ft)", "meter (m)")
        back = convert("Length", m, "meter (m)", "foot (ft)")
        assert back == pytest.approx(original, rel=1e-9)

    def test_length_nautical_mile_exact(self):
        # 1 nmi = 1852 m (exact, BIPM / IHO)
        assert convert("Length", 1.0, "nautical mile (nmi)", "meter (m)") == pytest.approx(1852.0, rel=1e-12)

    def test_length_angstrom_exact(self):
        # 1 Å = 10⁻¹⁰ m (NIST SP 811)
        assert convert("Length", 1.0, "ångström (Å)", "meter (m)") == pytest.approx(1e-10, rel=1e-12)

    def test_length_au_iau(self):
        # 1 au = 149 597 870 700 m (IAU 2012, exact)
        assert convert("Length", 1.0, "astronomical unit (au)", "meter (m)") == pytest.approx(1.495978707e11, rel=1e-9)

    def test_length_lightyear_iau(self):
        # 1 ly = 9.460 730 472 5808 × 10¹⁵ m (IAU)
        assert convert("Length", 1.0, "light-year (ly)", "meter (m)") == pytest.approx(9.4607304725808e15, rel=1e-9)

    def test_length_parsec_iau(self):
        # 1 pc ≈ 3.0857 × 10¹⁶ m (IAU)
        assert convert("Length", 1.0, "parsec (pc)", "meter (m)") == pytest.approx(3.085677581491367e16, rel=1e-9)

    # Area — new units
    def test_area_acre_exact(self):
        # 1 acre = 4046.856 422 4 m² (exact, NIST SP 811)
        assert convert("Area", 1.0, "acre", "square meter (m²)") == pytest.approx(4046.8564224, rel=1e-10)

    def test_area_hectare_exact(self):
        # 1 ha = 10 000 m² (exact)
        assert convert("Area", 1.0, "hectare (ha)", "square meter (m²)") == pytest.approx(10000.0, rel=1e-12)

    def test_area_are_exact(self):
        # 1 a = 100 m² (exact)
        assert convert("Area", 1.0, "are (a)", "square meter (m²)") == pytest.approx(100.0, rel=1e-12)

    def test_area_100ha_equals_1sq_km(self):
        # 100 ha = 1 km² = 10⁶ m²
        ha_m2 = convert("Area", 100.0, "hectare (ha)", "square meter (m²)")
        assert ha_m2 == pytest.approx(1e6, rel=1e-12)

    # Volume — new units
    def test_volume_us_gallon_exact(self):
        # 1 US gal = 3.785 411 784 L = 3.785 411 784 × 10⁻³ m³ (exact)
        assert convert("Volume", 1.0, "US gallon (gal)", "litre (l)") == pytest.approx(3.785411784, rel=1e-9)

    def test_volume_imp_gallon_exact(self):
        # 1 Imp. gal = 4.546 09 L (exact, UK 1985)
        assert convert("Volume", 1.0, "Imp. gallon (gal Imp.)", "litre (l)") == pytest.approx(4.54609, rel=1e-9)

    def test_volume_4_us_quarts_equals_1_us_gallon(self):
        # 4 US qt == 1 US gal (exact)
        qt_m3 = convert("Volume", 4.0, "US quart (qt)", "cubic meter (m³)")
        gal_m3 = convert("Volume", 1.0, "US gallon (gal)", "cubic meter (m³)")
        assert qt_m3 == pytest.approx(gal_m3, rel=1e-12)

    def test_volume_oil_barrel_exact(self):
        # 1 bbl = 42 US gal (exact)
        bbl_m3 = convert("Volume", 1.0, "oil barrel (bbl)", "cubic meter (m³)")
        gal_m3 = convert("Volume", 42.0, "US gallon (gal)", "cubic meter (m³)")
        assert bbl_m3 == pytest.approx(gal_m3, rel=1e-12)

    def test_volume_cup_tablespoon_teaspoon(self):
        # 1 cup = 16 tablespoons = 48 teaspoons (exact)
        cup_m3 = convert("Volume", 1.0, "US cup (cup)", "cubic meter (m³)")
        tbsp16_m3 = convert("Volume", 16.0, "US tablespoon (tbsp)", "cubic meter (m³)")
        tsp48_m3 = convert("Volume", 48.0, "US teaspoon (tsp)", "cubic meter (m³)")
        assert cup_m3 == pytest.approx(tbsp16_m3, rel=1e-10)
        assert cup_m3 == pytest.approx(tsp48_m3, rel=1e-10)

    # Time — new units
    def test_time_week_exact(self):
        # 1 week = 7 × 86400 s = 604800 s (exact)
        assert convert("Time", 1.0, "week (wk)", "second (s)") == pytest.approx(604800.0, rel=1e-12)

    def test_time_julian_year_exact(self):
        # 1 Julian year = 365.25 × 86400 s = 31 557 600 s (IAU exact)
        assert convert("Time", 1.0, "Julian year (a)", "second (s)") == pytest.approx(31557600.0, rel=1e-12)

    def test_time_week_equals_7_days(self):
        wk_s = convert("Time", 1.0, "week (wk)", "second (s)")
        d7_s = convert("Time", 7.0, "day (d)", "second (s)")
        assert wk_s == pytest.approx(d7_s, rel=1e-12)

    # Energy — new units
    def test_energy_btu_nist(self):
        # 1 BTU_IT = 1055.055 852 62 J (NIST SP 811)
        assert convert("Energy", 1.0, "BTU (IT)", "joule (J)") == pytest.approx(1055.05585262, rel=1e-9)

    def test_energy_ft_lbf_nist(self):
        # 1 ft·lbf = 1.355 817 948... J (NIST SP 811)
        assert convert("Energy", 1.0, "foot-pound force (ft·lbf)", "joule (J)") == pytest.approx(1.3558179483314004, rel=1e-9)

    def test_energy_therm_equals_100000_btu(self):
        # 1 therm = 100 000 BTU_IT (exact)
        therm_j = convert("Energy", 1.0, "therm (EC)", "joule (J)")
        btu100k_j = convert("Energy", 100000.0, "BTU (IT)", "joule (J)")
        assert therm_j == pytest.approx(btu100k_j, rel=1e-9)

    def test_energy_ton_tnt(self):
        # 1 ton TNT = 10⁹ cal_th = 4.184 × 10⁹ J (NIST SP 811)
        assert convert("Energy", 1.0, "ton of TNT (tTNT)", "joule (J)") == pytest.approx(4.184e9, rel=1e-9)

    # Power — new unit
    def test_power_btu_h_nist(self):
        # 1 BTU_IT/h = 1055.055 852 62 / 3600 W ≈ 0.293 071 W (NIST SP 811)
        assert convert("Power", 1.0, "BTU/h", "watt (W)") == pytest.approx(0.29307107017222, rel=1e-9)

    # Pressure — new units
    def test_pressure_psi_nist(self):
        # 1 psi = 6894.757 293 168 Pa (NIST SP 811)
        assert convert("Pressure", 1.0, "pound per sq. inch (psi)", "Pascal (Pa)") == pytest.approx(6894.757293168, rel=1e-9)

    def test_pressure_inhg_nist(self):
        # 1 inHg = 3386.388 640 341 Pa (NIST SP 811)
        assert convert("Pressure", 1.0, "inch Hg (inHg)", "Pascal (Pa)") == pytest.approx(3386.388640341, rel=1e-9)

    def test_pressure_at_exact(self):
        # 1 technical atmosphere = 98066.5 Pa (exact: 1 kgf/cm²)
        assert convert("Pressure", 1.0, "technical atmosphere (at)", "Pascal (Pa)") == pytest.approx(98066.5, rel=1e-12)

    def test_pressure_torr_exact(self):
        # 1 Torr = 101325/760 Pa (exact definition)
        assert convert("Pressure", 1.0, "Torr (Torr)", "Pascal (Pa)") == pytest.approx(101325.0/760.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Value-locking tests: new magnitudes
# ---------------------------------------------------------------------------

class TestNewMagnitudes:
    """
    Value-locking + round-trip tests for newly added magnitudes.
    Covers all 14 new magnitudes with at least one reference conversion each.
    """

    def test_new_magnitudes_in_list(self):
        mags = list_magnitudes()
        for mag in (
            "Frequency", "Force", "Speed", "Acceleration", "Plane_angle",
            "Electric_charge", "Voltage", "Electric_resistance", "Density",
            "Amount_of_substance", "Absorbed_dose", "Equivalent_dose",
            "Radioactivity", "Radiation_exposure",
        ):
            assert mag in mags, f"{mag} missing from list_magnitudes()"

    # Frequency
    def test_frequency_rpm_to_hz(self):
        # 60 rpm = 1 Hz (exact)
        assert convert("Frequency", 60.0, "rpm (rpm)", "hertz (Hz)") == pytest.approx(1.0, rel=1e-12)

    def test_frequency_hz_to_rpm(self):
        assert convert("Frequency", 1.0, "hertz (Hz)", "rpm (rpm)") == pytest.approx(60.0, rel=1e-12)

    def test_frequency_roundtrip(self):
        original = 3000.0
        hz = convert("Frequency", original, "rpm (rpm)", "hertz (Hz)")
        back = convert("Frequency", hz, "hertz (Hz)", "rpm (rpm)")
        assert back == pytest.approx(original, rel=1e-9)

    # Force
    def test_force_dyne_exact(self):
        # 1 dyn = 10⁻⁵ N (exact, CGS)
        assert convert("Force", 1.0, "dyne (dyn)", "newton (N)") == pytest.approx(1e-5, rel=1e-12)

    def test_force_kgf_exact(self):
        # 1 kgf = 9.806 65 N (exact, BIPM)
        assert convert("Force", 1.0, "kilogram-force (kgf)", "newton (N)") == pytest.approx(9.80665, rel=1e-9)

    def test_force_lbf_nist(self):
        # 1 lbf = 4.448 221 615 260 5 N (NIST SP 811)
        assert convert("Force", 1.0, "pound-force (lbf)", "newton (N)") == pytest.approx(4.4482216152605, rel=1e-9)

    def test_force_roundtrip_kgf(self):
        original = 9.81
        n = convert("Force", original, "kilogram-force (kgf)", "newton (N)")
        back = convert("Force", n, "newton (N)", "kilogram-force (kgf)")
        assert back == pytest.approx(original, rel=1e-9)

    # Speed
    def test_speed_kmh_to_ms(self):
        # 1 km/h = 1/3.6 m/s (exact)
        assert convert("Speed", 1.0, "kilometer per hour (km/h)", "meter per second (m/s)") == pytest.approx(1.0/3.6, rel=1e-12)

    def test_speed_mph_to_ms(self):
        # 1 mph = 0.447 04 m/s (exact = 1609.344/3600)
        assert convert("Speed", 1.0, "mile per hour (mph)", "meter per second (m/s)") == pytest.approx(0.44704, rel=1e-9)

    def test_speed_knot_to_ms(self):
        # 1 kn = 1852/3600 m/s (exact)
        assert convert("Speed", 1.0, "knot (kn)", "meter per second (m/s)") == pytest.approx(1852.0/3600.0, rel=1e-12)

    def test_speed_fts_to_ms(self):
        # 1 ft/s = 0.3048 m/s (exact)
        assert convert("Speed", 1.0, "foot per second (ft/s)", "meter per second (m/s)") == pytest.approx(0.3048, rel=1e-12)

    def test_speed_roundtrip_mph(self):
        original = 60.0
        ms = convert("Speed", original, "mile per hour (mph)", "meter per second (m/s)")
        back = convert("Speed", ms, "meter per second (m/s)", "mile per hour (mph)")
        assert back == pytest.approx(original, rel=1e-9)

    # Acceleration
    def test_acceleration_g_n_exact(self):
        # 1 g_n = 9.806 65 m/s² (exact, BIPM)
        assert convert("Acceleration", 1.0, "standard gravity (g_n)", "meter per second squared (m/s²)") == pytest.approx(9.80665, rel=1e-12)

    def test_acceleration_gal_exact(self):
        # 1 Gal = 0.01 m/s² (exact, CGS)
        assert convert("Acceleration", 1.0, "gal (Gal)", "meter per second squared (m/s²)") == pytest.approx(0.01, rel=1e-12)

    def test_acceleration_100gal_equals_1ms2(self):
        gal100 = convert("Acceleration", 100.0, "gal (Gal)", "meter per second squared (m/s²)")
        assert gal100 == pytest.approx(1.0, rel=1e-12)

    # Plane angle
    def test_angle_180deg_equals_pi_rad(self):
        # 180° = π rad (exact definition)
        import math
        assert convert("Plane_angle", 180.0, "degree (°)", "radian (rad)") == pytest.approx(math.pi, rel=1e-12)

    def test_angle_360deg_equals_1_turn(self):
        # 360° = 1 turn (exact)
        assert convert("Plane_angle", 360.0, "degree (°)", "turn (rev)") == pytest.approx(1.0, rel=1e-12)

    def test_angle_400grad_equals_360deg(self):
        # 400 grad = 360° (exact)
        grad_rad = convert("Plane_angle", 400.0, "gradian (grad)", "radian (rad)")
        deg_rad = convert("Plane_angle", 360.0, "degree (°)", "radian (rad)")
        assert grad_rad == pytest.approx(deg_rad, rel=1e-12)

    def test_angle_60arcmin_equals_1deg(self):
        # 60 arcmin = 1° (exact)
        am60_rad = convert("Plane_angle", 60.0, "arcminute (′)", "radian (rad)")
        deg1_rad = convert("Plane_angle", 1.0, "degree (°)", "radian (rad)")
        assert am60_rad == pytest.approx(deg1_rad, rel=1e-12)

    def test_angle_3600arcsec_equals_1deg(self):
        # 3600 arcsec = 1° (exact)
        as3600_rad = convert("Plane_angle", 3600.0, "arcsecond (″)", "radian (rad)")
        deg1_rad = convert("Plane_angle", 1.0, "degree (°)", "radian (rad)")
        assert as3600_rad == pytest.approx(deg1_rad, rel=1e-12)

    def test_angle_roundtrip_degree(self):
        original = 45.0
        rad = convert("Plane_angle", original, "degree (°)", "radian (rad)")
        back = convert("Plane_angle", rad, "radian (rad)", "degree (°)")
        assert back == pytest.approx(original, rel=1e-9)

    # Electric charge
    def test_charge_ampere_hour_exact(self):
        # 1 Ah = 3600 C (exact)
        assert convert("Electric_charge", 1.0, "ampere-hour (Ah)", "coulomb (C)") == pytest.approx(3600.0, rel=1e-12)

    def test_charge_elementary_codata(self):
        # 1 e = 1.602 176 634 × 10⁻¹⁹ C (exact, SI 2019)
        assert convert("Electric_charge", 1.0, "elementary charge (e)", "coulomb (C)") == pytest.approx(1.602176634e-19, rel=1e-12)

    def test_charge_roundtrip_ah(self):
        original = 5.0
        c = convert("Electric_charge", original, "ampere-hour (Ah)", "coulomb (C)")
        back = convert("Electric_charge", c, "coulomb (C)", "ampere-hour (Ah)")
        assert back == pytest.approx(original, rel=1e-9)

    # Voltage
    def test_voltage_millivolt_exact(self):
        # 1 mV = 0.001 V (exact)
        assert convert("Voltage", 1.0, "millivolt (mV)", "volt (V)") == pytest.approx(0.001, rel=1e-12)

    def test_voltage_kilovolt_exact(self):
        # 1 kV = 1000 V (exact)
        assert convert("Voltage", 1.0, "kilovolt (kV)", "volt (V)") == pytest.approx(1000.0, rel=1e-12)

    def test_voltage_roundtrip(self):
        original = 230.0
        mv = convert("Voltage", original, "volt (V)", "millivolt (mV)")
        back = convert("Voltage", mv, "millivolt (mV)", "volt (V)")
        assert back == pytest.approx(original, rel=1e-9)

    # Electric resistance
    def test_resistance_kilohm_exact(self):
        # 1 kΩ = 1000 Ω (exact)
        assert convert("Electric_resistance", 1.0, "kilohm (kΩ)", "ohm (Ω)") == pytest.approx(1000.0, rel=1e-12)

    def test_resistance_megohm_exact(self):
        # 1 MΩ = 10⁶ Ω (exact)
        assert convert("Electric_resistance", 1.0, "megohm (MΩ)", "ohm (Ω)") == pytest.approx(1e6, rel=1e-12)

    def test_resistance_roundtrip(self):
        original = 4700.0
        kohm = convert("Electric_resistance", original, "ohm (Ω)", "kilohm (kΩ)")
        back = convert("Electric_resistance", kohm, "kilohm (kΩ)", "ohm (Ω)")
        assert back == pytest.approx(original, rel=1e-9)

    # Density
    def test_density_gcm3_to_kgm3(self):
        # 1 g/cm³ = 1000 kg/m³ (exact)
        assert convert("Density", 1.0, "gram per cubic centimeter (g/cm³)", "kilogram per cubic meter (kg/m³)") == pytest.approx(1000.0, rel=1e-12)

    def test_density_gl_equals_kgm3(self):
        # 1 g/L = 1 kg/m³ (exact)
        assert convert("Density", 1.0, "gram per litre (g/l)", "kilogram per cubic meter (kg/m³)") == pytest.approx(1.0, rel=1e-12)

    def test_density_roundtrip(self):
        original = 1.225  # air density in kg/m³
        gcm3 = convert("Density", original, "kilogram per cubic meter (kg/m³)", "gram per cubic centimeter (g/cm³)")
        back = convert("Density", gcm3, "gram per cubic centimeter (g/cm³)", "kilogram per cubic meter (kg/m³)")
        assert back == pytest.approx(original, rel=1e-9)

    # Amount of substance
    def test_amount_millimole_exact(self):
        # 1 mmol = 10⁻³ mol (exact)
        assert convert("Amount_of_substance", 1.0, "millimole (mmol)", "mole (mol)") == pytest.approx(0.001, rel=1e-12)

    def test_amount_micromole_exact(self):
        # 1 µmol = 10⁻⁶ mol (exact)
        assert convert("Amount_of_substance", 1.0, "micromole (µmol)", "mole (mol)") == pytest.approx(1e-6, rel=1e-12)

    def test_amount_roundtrip(self):
        original = 0.5
        mmol = convert("Amount_of_substance", original, "mole (mol)", "millimole (mmol)")
        back = convert("Amount_of_substance", mmol, "millimole (mmol)", "mole (mol)")
        assert back == pytest.approx(original, rel=1e-9)

    # Absorbed dose
    def test_absorbed_dose_rad_exact(self):
        # 1 rad = 0.01 Gy (exact, NIST SP 811)
        assert convert("Absorbed_dose", 1.0, "rad (rad)", "gray (Gy)") == pytest.approx(0.01, rel=1e-12)

    def test_absorbed_dose_100rad_equals_1gy(self):
        assert convert("Absorbed_dose", 100.0, "rad (rad)", "gray (Gy)") == pytest.approx(1.0, rel=1e-12)

    def test_absorbed_dose_roundtrip(self):
        original = 2.5
        rad = convert("Absorbed_dose", original, "gray (Gy)", "rad (rad)")
        back = convert("Absorbed_dose", rad, "rad (rad)", "gray (Gy)")
        assert back == pytest.approx(original, rel=1e-9)

    # Equivalent dose
    def test_equivalent_dose_rem_exact(self):
        # 1 rem = 0.01 Sv (exact, NIST SP 811)
        assert convert("Equivalent_dose", 1.0, "rem (rem)", "sievert (Sv)") == pytest.approx(0.01, rel=1e-12)

    def test_equivalent_dose_100rem_equals_1sv(self):
        assert convert("Equivalent_dose", 100.0, "rem (rem)", "sievert (Sv)") == pytest.approx(1.0, rel=1e-12)

    # Radioactivity
    def test_radioactivity_curie_exact(self):
        # 1 Ci = 3.7 × 10¹⁰ Bq (exact, NIST SP 811)
        assert convert("Radioactivity", 1.0, "curie (Ci)", "becquerel (Bq)") == pytest.approx(3.7e10, rel=1e-12)

    def test_radioactivity_roundtrip(self):
        original = 0.001  # 1 mCi in Ci
        bq = convert("Radioactivity", original, "curie (Ci)", "becquerel (Bq)")
        back = convert("Radioactivity", bq, "becquerel (Bq)", "curie (Ci)")
        assert back == pytest.approx(original, rel=1e-9)

    # Radiation exposure
    def test_radiation_exposure_roentgen_exact(self):
        # 1 R = 2.58 × 10⁻⁴ C/kg (exact, NIST SP 811)
        assert convert("Radiation_exposure", 1.0, "röntgen (R)", "coulomb per kilogram (C/kg)") == pytest.approx(2.58e-4, rel=1e-12)

    def test_radiation_exposure_roundtrip(self):
        original = 10.0
        ckg = convert("Radiation_exposure", original, "röntgen (R)", "coulomb per kilogram (C/kg)")
        back = convert("Radiation_exposure", ckg, "coulomb per kilogram (C/kg)", "röntgen (R)")
        assert back == pytest.approx(original, rel=1e-9)

    # Cross-magnitude regression: existing magnitudes unchanged after expansion
    def test_regression_mass_gram_identity(self):
        assert convert("Mass", 1.0, "gram (g)", "gram (g)") == pytest.approx(1.0)

    def test_regression_length_meter_identity(self):
        assert convert("Length", 1.0, "meter (m)", "meter (m)") == pytest.approx(1.0)

    def test_regression_time_hour_to_seconds(self):
        assert convert("Time", 1.0, "hour (hr)", "second (s)") == pytest.approx(3600.0, rel=1e-12)

    def test_regression_energy_joule_to_cal(self):
        assert convert("Energy", 4.184, "joule (J)", "calorie (cal)") == pytest.approx(1.0, rel=1e-9)

    def test_regression_data_byte_to_bit(self):
        assert convert("Data", 1.0, "byte (B)", "bit (b)") == pytest.approx(8.0, rel=1e-12)

    def test_regression_temperature_0c_to_32f(self):
        assert convert("Temperature", 0.0, "celsius (°C)", "fahrenheit (°F)") == pytest.approx(32.0, abs=1e-6)

    def test_regression_temperature_100c_to_212f(self):
        assert convert("Temperature", 100.0, "celsius (°C)", "fahrenheit (°F)") == pytest.approx(212.0, abs=1e-4)
