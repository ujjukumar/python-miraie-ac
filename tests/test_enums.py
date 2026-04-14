"""Tests for enums"""

from py_miraie_ac.enums import (
    AuthType,
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
    assert SwingMode(3) == SwingMode.THREE
