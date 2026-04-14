"""Tests for MirAIeBroker"""

import json
from unittest.mock import MagicMock, patch

from py_miraie_ac.broker import MirAIeBroker
from py_miraie_ac.enums import (
    Converti7Mode,
    DisplayState,
    FanMode,
    HVACMode,
    PowerMode,
    PresetMode,
    SwingMode,
)


@patch("py_miraie_ac.broker.paho.Client")
def test_broker_creation(mock_client_cls):
    MirAIeBroker()
    mock_client_cls.assert_called_once()


@patch("py_miraie_ac.broker.paho.Client")
def test_broker_connect(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.init_broker("user", "pass", MagicMock())
    broker.connect()

    mock_client.connect.assert_called_once()
    mock_client.loop_start.assert_called_once()


@patch("py_miraie_ac.broker.paho.Client")
def test_broker_disconnect(mock_client_cls):
    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.disconnect()

    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()


@patch("py_miraie_ac.broker.paho.Client")
def test_broker_disconnect_when_not_connected(mock_client_cls):
    mock_client = MagicMock()
    mock_client.is_connected.return_value = False
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.disconnect()

    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_not_called()


@patch("py_miraie_ac.broker.paho.Client")
def test_set_temperature(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_temperature("topic/control", 24.0)

    mock_client.publish.assert_called_once()
    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["actmp"] == "24.0"
    assert msg["ki"] == 1


@patch("py_miraie_ac.broker.paho.Client")
def test_set_power(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_power("topic/control", PowerMode.ON)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["ps"] == "on"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_hvac_mode(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_hvac_mode("topic/control", HVACMode.COOL)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acmd"] == "cool"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_fan_mode(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_fan_mode("topic/control", FanMode.HIGH)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acfs"] == "high"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_preset_eco(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_preset_mode("topic/control", PresetMode.ECO)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acem"] == "on"
    assert msg["acpm"] == "off"
    assert "actmp" not in msg  # ECO no longer forces temperature


@patch("py_miraie_ac.broker.paho.Client")
def test_set_preset_boost(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_preset_mode("topic/control", PresetMode.BOOST)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acem"] == "off"
    assert msg["acpm"] == "on"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_preset_none(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_preset_mode("topic/control", PresetMode.NONE)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acem"] == "off"
    assert msg["acpm"] == "off"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_display_state(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_display_state("topic/control", DisplayState.OFF)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acdc"] == "off"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_eco_mode(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_eco_mode("topic/control", True)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acem"] == "on"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_boost_mode(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_boost_mode("topic/control", False)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acpm"] == "off"


@patch("py_miraie_ac.broker.paho.Client")
def test_set_vertical_swing(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_vertical_swing_mode("topic/control", SwingMode.THREE)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["acvs"] == 3


@patch("py_miraie_ac.broker.paho.Client")
def test_set_horizontal_swing(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_horizontal_swing_mode("topic/control", SwingMode.FIVE)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["achs"] == 5


@patch("py_miraie_ac.broker.paho.Client")
def test_register_and_call_callback(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    cb = MagicMock()
    broker.register_callback("test/topic", cb)

    # Simulate message
    mock_message = MagicMock()
    mock_message.topic = "test/topic"
    mock_message.payload = json.dumps({"test": "data"}).encode("utf-8")

    broker._on_mqtt_message_received(mock_client, None, mock_message)
    cb.assert_called_once_with({"test": "data"})


@patch("py_miraie_ac.broker.paho.Client")
def test_missing_callback_no_crash(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    # No callback registered for this topic

    mock_message = MagicMock()
    mock_message.topic = "unknown/topic"
    mock_message.payload = json.dumps({"test": "data"}).encode("utf-8")

    # Should not raise
    broker._on_mqtt_message_received(mock_client, None, mock_message)


@patch("py_miraie_ac.broker.paho.Client")
def test_remove_callback(mock_client_cls):
    broker = MirAIeBroker()
    cb = MagicMock()
    broker.register_callback("test/topic", cb)
    broker.remove_callback("test/topic")
    assert "test/topic" not in broker._callbacks


@patch("py_miraie_ac.broker.paho.Client")
def test_set_converti7_mode(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_converti7_mode("topic/control", Converti7Mode.HC)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["cnv"] == 110


@patch("py_miraie_ac.broker.paho.Client")
def test_set_converti7_mode_off(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    broker = MirAIeBroker()
    broker.set_converti7_mode("topic/control", Converti7Mode.OFF)

    msg = json.loads(mock_client.publish.call_args[0][1])
    assert msg["cnv"] == 0
