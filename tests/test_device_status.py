"""Tests for DeviceStatus"""

from datetime import UTC

from py_miraie_ac.deviceStatus import DeviceStatus
from py_miraie_ac.enums import (
    DisplayState,
    FanMode,
    HVACMode,
    PowerMode,
    PresetMode,
    SwingMode,
)


def test_device_status_creation(sample_device_status):
    assert sample_device_status.is_online is True
    assert sample_device_status.temperature == 24.0
    assert sample_device_status.room_temp == 26.5
    assert sample_device_status.power_mode == PowerMode.ON
    assert sample_device_status.fan_mode == FanMode.AUTO
    assert sample_device_status.display_state == DisplayState.ON
    assert sample_device_status.hvac_mode == HVACMode.COOL
    assert sample_device_status.preset_mode == PresetMode.NONE
    assert sample_device_status.vertical_swing_mode == SwingMode.AUTO
    assert sample_device_status.horizontal_swing_mode == SwingMode.AUTO


def test_device_status_last_updated(sample_device_status):
    assert sample_device_status.last_updated is not None
    assert sample_device_status.last_updated.tzinfo == UTC


def test_device_status_repr(sample_device_status):
    repr_str = repr(sample_device_status)
    assert "DeviceStatus(" in repr_str
    assert "online=True" in repr_str
    assert "power=on" in repr_str
    assert "temp=24.0" in repr_str


def test_device_status_equality():
    s1 = DeviceStatus(
        is_online=True, temperature=24.0, room_temp=26.5,
        power_mode=PowerMode.ON, fan_mode=FanMode.AUTO,
        display_state=DisplayState.ON, hvac_mode=HVACMode.COOL,
        preset_mode=PresetMode.NONE, vertical_swing_mode=SwingMode.AUTO,
        horizontal_swing_mode=SwingMode.AUTO,
    )
    s2 = DeviceStatus(
        is_online=True, temperature=24.0, room_temp=26.5,
        power_mode=PowerMode.ON, fan_mode=FanMode.AUTO,
        display_state=DisplayState.ON, hvac_mode=HVACMode.COOL,
        preset_mode=PresetMode.NONE, vertical_swing_mode=SwingMode.AUTO,
        horizontal_swing_mode=SwingMode.AUTO,
    )
    assert s1 == s2


def test_device_status_inequality():
    s1 = DeviceStatus(
        is_online=True, temperature=24.0, room_temp=26.5,
        power_mode=PowerMode.ON, fan_mode=FanMode.AUTO,
        display_state=DisplayState.ON, hvac_mode=HVACMode.COOL,
        preset_mode=PresetMode.NONE, vertical_swing_mode=SwingMode.AUTO,
        horizontal_swing_mode=SwingMode.AUTO,
    )
    s2 = DeviceStatus(
        is_online=True, temperature=22.0, room_temp=26.5,
        power_mode=PowerMode.ON, fan_mode=FanMode.AUTO,
        display_state=DisplayState.ON, hvac_mode=HVACMode.COOL,
        preset_mode=PresetMode.NONE, vertical_swing_mode=SwingMode.AUTO,
        horizontal_swing_mode=SwingMode.AUTO,
    )
    assert s1 != s2


def test_device_status_eq_not_implemented():
    s = DeviceStatus(
        is_online=True, temperature=24.0, room_temp=26.5,
        power_mode=PowerMode.ON, fan_mode=FanMode.AUTO,
        display_state=DisplayState.ON, hvac_mode=HVACMode.COOL,
        preset_mode=PresetMode.NONE, vertical_swing_mode=SwingMode.AUTO,
        horizontal_swing_mode=SwingMode.AUTO,
    )
    assert s != "not a status"
