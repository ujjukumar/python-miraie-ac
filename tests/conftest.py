"""Shared test fixtures"""

from unittest.mock import MagicMock

import pytest

from py_miraie_ac.broker import MirAIeBroker
from py_miraie_ac.device import Device
from py_miraie_ac.deviceStatus import DeviceStatus
from py_miraie_ac.enums import (
    DisplayState,
    FanMode,
    HVACMode,
    PowerMode,
    PresetMode,
    SwingMode,
)

SAMPLE_STATUS_JSON = {
    "onlineStatus": "true",
    "actmp": "24.0",
    "rmtmp": "26.5",
    "ps": "on",
    "acfs": "auto",
    "acdc": "on",
    "acmd": "cool",
    "acem": "off",
    "acpm": "off",
    "acvs": 0,
    "achs": 0,
    "cnv": 0,
}

SAMPLE_LOGIN_RESPONSE = {
    "accessToken": "test-access-token",
    "refreshToken": "test-refresh-token",
    "userId": "test-user-id",
    "expiresIn": 3600,
}

SAMPLE_HOME_RESPONSE = [
    {
        "homeId": "home-123",
        "spaces": [
            {
                "spaceName": "Living Room",
                "devices": [
                    {
                        "deviceId": "device-001",
                        "deviceName": "Living Room AC",
                        "topic": ["home/device-001"],
                    }
                ],
            }
        ],
    }
]

SAMPLE_DEVICE_DETAILS = [
    {
        "modelName": "CS/CU-WU12WKYXF",
        "macAddress": "AA:BB:CC:DD:EE:FF",
        "category": "AC",
        "brand": "Panasonic",
        "firmwareVersion": "1.0.0",
        "serialNumber": "SN12345",
        "modelNumber": "MN12345",
        "productSerialNumber": "PSN12345",
    }
]


@pytest.fixture
def sample_device_status():
    return DeviceStatus(
        is_online=True,
        temperature=24.0,
        room_temp=26.5,
        power_mode=PowerMode.ON,
        fan_mode=FanMode.AUTO,
        display_state=DisplayState.ON,
        hvac_mode=HVACMode.COOL,
        preset_mode=PresetMode.NONE,
        vertical_swing_mode=SwingMode.AUTO,
        horizontal_swing_mode=SwingMode.AUTO,
    )


@pytest.fixture
def mock_broker():
    broker = MagicMock(spec=MirAIeBroker)
    return broker


@pytest.fixture
def sample_device(sample_device_status, mock_broker):
    return Device(
        device_id="device-001",
        name="living-room-ac",
        friendly_name="Living Room AC",
        control_topic="home/device-001/control",
        status_topic="home/device-001/status",
        connection_status_topic="home/device-001/connectionStatus",
        model_name="CS/CU-WU12WKYXF",
        mac_address="AA:BB:CC:DD:EE:FF",
        category="AC",
        brand="Panasonic",
        firmware_version="1.0.0",
        serial_number="SN12345",
        model_number="MN12345",
        product_serial_number="PSN12345",
        status=sample_device_status,
        broker=mock_broker,
        area_name="Living Room",
    )
