"""Tests for Device"""

from unittest.mock import MagicMock

import pytest

from py_miraie_ac.enums import (
    DisplayState,
    FanMode,
    HVACMode,
    PowerMode,
    PresetMode,
    SwingMode,
)


def test_device_creation(sample_device):
    assert sample_device.device_id == "device-001"
    assert sample_device.friendly_name == "Living Room AC"
    assert sample_device.area_name == "Living Room"


def test_turn_on(sample_device, mock_broker):
    sample_device.turn_on()
    mock_broker.set_power.assert_called_once_with(
        "home/device-001/control", PowerMode.ON
    )


def test_turn_off(sample_device, mock_broker):
    sample_device.turn_off()
    mock_broker.set_power.assert_called_once_with(
        "home/device-001/control", PowerMode.OFF
    )


def test_set_temperature(sample_device, mock_broker):
    sample_device.set_temperature(22.0)
    mock_broker.set_temperature.assert_called_once_with(
        "home/device-001/control", 22.0
    )


def test_set_temperature_too_low(sample_device):
    with pytest.raises(ValueError, match="Temperature must be between"):
        sample_device.set_temperature(10.0)


def test_set_temperature_too_high(sample_device):
    with pytest.raises(ValueError, match="Temperature must be between"):
        sample_device.set_temperature(35.0)


def test_set_temperature_boundary_low(sample_device, mock_broker):
    sample_device.set_temperature(16.0)
    mock_broker.set_temperature.assert_called_once_with(
        "home/device-001/control", 16.0
    )


def test_set_temperature_boundary_high(sample_device, mock_broker):
    sample_device.set_temperature(30.0)
    mock_broker.set_temperature.assert_called_once_with(
        "home/device-001/control", 30.0
    )


def test_set_hvac_mode(sample_device, mock_broker):
    sample_device.set_hvac_mode(HVACMode.DRY)
    mock_broker.set_hvac_mode.assert_called_once_with(
        "home/device-001/control", HVACMode.DRY
    )


def test_set_fan_mode(sample_device, mock_broker):
    sample_device.set_fan_mode(FanMode.HIGH)
    mock_broker.set_fan_mode.assert_called_once_with(
        "home/device-001/control", FanMode.HIGH
    )


def test_set_preset_mode(sample_device, mock_broker):
    sample_device.set_preset_mode(PresetMode.ECO)
    mock_broker.set_preset_mode.assert_called_once_with(
        "home/device-001/control", PresetMode.ECO
    )


def test_set_display_state(sample_device, mock_broker):
    sample_device.set_display_state(DisplayState.OFF)
    mock_broker.set_display_state.assert_called_once_with(
        "home/device-001/control", DisplayState.OFF
    )


def test_set_eco_mode(sample_device, mock_broker):
    sample_device.set_eco_mode(True)
    mock_broker.set_eco_mode.assert_called_once_with(
        "home/device-001/control", True
    )


def test_set_boost_mode(sample_device, mock_broker):
    sample_device.set_boost_mode(True)
    mock_broker.set_boost_mode.assert_called_once_with(
        "home/device-001/control", True
    )


def test_set_vertical_swing(sample_device, mock_broker):
    sample_device.set_vertical_swing_mode(SwingMode.THREE)
    mock_broker.set_vertical_swing_mode.assert_called_once_with(
        "home/device-001/control", SwingMode.THREE
    )


def test_set_horizontal_swing(sample_device, mock_broker):
    sample_device.set_horizontal_swing_mode(SwingMode.FIVE)
    mock_broker.set_horizontal_swing_mode.assert_called_once_with(
        "home/device-001/control", SwingMode.FIVE
    )


def test_register_callback(sample_device):
    cb = MagicMock()
    sample_device.register_callback(cb)
    assert cb in sample_device._callbacks


def test_remove_callback(sample_device):
    cb = MagicMock()
    sample_device.register_callback(cb)
    sample_device.remove_callback(cb)
    assert cb not in sample_device._callbacks


def test_status_callback_handler(sample_device):
    from tests.conftest import SAMPLE_STATUS_JSON
    cb = MagicMock()
    sample_device.register_callback(cb)
    sample_device.status_callback_handler(SAMPLE_STATUS_JSON)
    cb.assert_called_once()
    assert sample_device.status.temperature == 24.0
    assert sample_device.status.power_mode == PowerMode.ON


def test_connection_callback_handler(sample_device):
    cb = MagicMock()
    sample_device.register_callback(cb)
    sample_device.connection_callback_handler({"onlineStatus": "false"})
    cb.assert_called_once()
    assert sample_device.status.is_online is False


def test_event_system(sample_device):
    handler = MagicMock()
    sample_device.on("status_changed", handler)
    from tests.conftest import SAMPLE_STATUS_JSON
    sample_device.status_callback_handler(SAMPLE_STATUS_JSON)
    handler.assert_called_once_with(sample_device)


def test_event_system_off(sample_device):
    handler = MagicMock()
    sample_device.on("status_changed", handler)
    sample_device.off("status_changed", handler)
    from tests.conftest import SAMPLE_STATUS_JSON
    sample_device.status_callback_handler(SAMPLE_STATUS_JSON)
    handler.assert_not_called()


def test_connection_event(sample_device):
    handler = MagicMock()
    sample_device.on("connection_changed", handler)
    sample_device.connection_callback_handler({"onlineStatus": "false"})
    handler.assert_called_once_with(sample_device)
