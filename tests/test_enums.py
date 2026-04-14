"""Tests for enums"""

from py_miraie_ac.enums import (
    AuthType,
    Converti7Mode,
    DisplayState,
    FanMode,
    HVACMode,
    PowerMode,
    PresetMode,
    SwingMode,
)


def test_auth_type_values():
    assert AuthType.MOBILE.value == "mobile"
    assert AuthType.EMAIL.value == "email"
    assert AuthType.USERNAME.value == "username"


def test_display_state_values():
    assert DisplayState.ON.value == "on"
    assert DisplayState.OFF.value == "off"


def test_fan_mode_values():
    assert FanMode.AUTO.value == "auto"
    assert FanMode.QUIET.value == "quiet"
    assert FanMode.LOW.value == "low"
    assert FanMode.MEDIUM.value == "medium"
    assert FanMode.HIGH.value == "high"


def test_hvac_mode_values():
    assert HVACMode.COOL.value == "cool"
    assert HVACMode.AUTO.value == "auto"
    assert HVACMode.DRY.value == "dry"
    assert HVACMode.FAN.value == "fan"


def test_power_mode_values():
    assert PowerMode.ON.value == "on"
    assert PowerMode.OFF.value == "off"


def test_preset_mode_values():
    assert PresetMode.NONE.value == "none"
    assert PresetMode.ECO.value == "eco"
    assert PresetMode.BOOST.value == "boost"


def test_swing_mode_values():
    assert SwingMode.AUTO.value == 0
    assert SwingMode.ONE.value == 1
    assert SwingMode.FIVE.value == 5


def test_enum_from_value():
    assert FanMode("auto") == FanMode.AUTO
    assert HVACMode("cool") == HVACMode.COOL


def test_converti7_mode_values():
    assert Converti7Mode.OFF.value == 0
    assert Converti7Mode.CAPACITY_40.value == 40
    assert Converti7Mode.CAPACITY_55.value == 55
    assert Converti7Mode.CAPACITY_70.value == 70
    assert Converti7Mode.CAPACITY_80.value == 80
    assert Converti7Mode.CAPACITY_90.value == 90
    assert Converti7Mode.FC.value == 100
    assert Converti7Mode.HC.value == 110


def test_converti7_mode_from_value():
    assert Converti7Mode(0) == Converti7Mode.OFF
    assert Converti7Mode(110) == Converti7Mode.HC
    assert SwingMode(3) == SwingMode.THREE
