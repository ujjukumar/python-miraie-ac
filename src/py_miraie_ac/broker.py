"""The MQTT broker implementation"""

import json
import logging
import math
import random
import ssl
from collections.abc import Callable
from typing import Any

from paho.mqtt import client as paho
from paho.mqtt.enums import CallbackAPIVersion

from .constants import MQTT_HOST, MQTT_PORT
from .enums import Converti7Mode, DisplayState, FanMode, HVACMode, PowerMode, PresetMode, SwingMode

logger = logging.getLogger(__name__)


class MirAIeBroker:
    """The MirAIe Broker class"""

    _host: str = MQTT_HOST
    _port: int = MQTT_PORT
    _use_ssl: bool = True
    _username: str
    _password: str
    _topics: list[str]
    _callbacks: dict[str, Callable[[dict[str, Any]], None]]
    _client: paho.Client
    _get_access_token_callback: Callable[..., None]

    def __init__(self) -> None:
        self._topics = []
        self._callbacks = {}
        self._client = paho.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self._generate_client_id(),
            transport="tcp",
            protocol=paho.MQTTv311,
            clean_session=False,
        )

    def init_broker(
        self, username: str, password: str, get_access_token_callback: Callable[..., None]
    ) -> None:
        """Initializes the MQTT client"""
        self._username = username
        self._password = password
        self._get_access_token_callback = get_access_token_callback
        self._init_mqtt_client()

    def set_topics(self, topics: list[str]) -> None:
        """Sets the topics to subscribe to"""
        self._topics = topics

    def register_callback(self, topic: str, callback: Callable[[dict[str, Any]], None]) -> None:
        """Registers callbacks for a given topic"""
        self._callbacks[topic] = callback

    def remove_callback(self, topic: str) -> None:
        """Removes an existing callback"""
        self._callbacks.pop(topic, None)

    def connect(self) -> None:
        """Connects to MirAIe"""
        self._client.connect(host=self._host, port=self._port)
        self._client.loop_start()
        logger.info("MQTT connection initiated to %s:%d", self._host, self._port)

    def reconnect(self, password: str) -> None:
        """Reconnects to MirAIe"""
        self._password = password
        self._client.username_pw_set(
            username=self._username, password=self._password
        )
        self.connect()

    def disconnect(self) -> None:
        """Disconnects from MirAIe"""
        self._client.loop_stop()
        if self._client.is_connected():
            self._client.disconnect()
        logger.info("MQTT disconnected")

    def set_temperature(self, topic: str, value: float) -> None:
        """Sets the Temperature to the given value"""
        message = self._build_temp_message(value)
        self._client.publish(topic, message)
        logger.debug("Published temperature %.1f to %s", value, topic)

    def set_power(self, topic: str, value: PowerMode) -> None:
        """Sets the Power to the given value"""
        message = self._build_power_message(value)
        self._client.publish(topic, message)
        logger.debug("Published power %s to %s", value.value, topic)

    def set_hvac_mode(self, topic: str, value: HVACMode) -> None:
        """Sets the Mode to the given value"""
        message = self._build_hvac_mode_message(value)
        self._client.publish(topic, message)
        logger.debug("Published HVAC mode %s to %s", value.value, topic)

    def set_fan_mode(self, topic: str, value: FanMode) -> None:
        """Sets the Fan to the given value"""
        message = self._build_fan_mode_message(value)
        self._client.publish(topic, message)
        logger.debug("Published fan mode %s to %s", value.value, topic)

    def set_preset_mode(self, topic: str, value: PresetMode) -> None:
        """Sets the Preset to the given value"""
        message = self._build_preset_mode_message(value)
        self._client.publish(topic, message)
        logger.debug("Published preset mode %s to %s", value.value, topic)

    def set_display_state(self, topic: str, value: DisplayState) -> None:
        """Sets the Display State to the given value"""
        message = self._build_display_state_message(value)
        self._client.publish(topic, message)
        logger.debug("Published display state %s to %s", value.value, topic)

    def set_eco_mode(self, topic: str, enabled: bool) -> None:
        """Sets eco mode on or off"""
        message = self._build_eco_mode_message(enabled)
        self._client.publish(topic, message)
        logger.debug("Published eco mode %s to %s", enabled, topic)

    def set_boost_mode(self, topic: str, enabled: bool) -> None:
        """Sets boost mode on or off"""
        message = self._build_boost_mode_message(enabled)
        self._client.publish(topic, message)
        logger.debug("Published boost mode %s to %s", enabled, topic)

    def set_vertical_swing_mode(self, topic: str, value: SwingMode) -> None:
        """Sets the Vertical Swing to the given value"""
        message = self._build_vertical_swing_mode_message(value)
        self._client.publish(topic, message)
        logger.debug("Published vertical swing %s to %s", value.value, topic)

    def set_horizontal_swing_mode(self, topic: str, value: SwingMode) -> None:
        """Sets the Horizontal Swing to the given value"""
        message = self._build_horizontal_swing_mode_message(value)
        self._client.publish(topic, message)
        logger.debug("Published horizontal swing %s to %s", value.value, topic)

    def set_converti7_mode(self, topic: str, value: Converti7Mode) -> None:
        """Sets the Converti7 (capacity) mode. Only works in COOL mode."""
        message = self._build_converti7_mode_message(value)
        self._client.publish(topic, message)
        logger.debug("Published converti7 mode %s to %s", value.value, topic)

    def _generate_client_id(self) -> str:
        return (
            f"an{self._generate_random_number(16)}{self._generate_random_number(5)}"
        )

    def _generate_random_number(self, length: int) -> str:
        value = math.floor(random.random() * math.pow(10, length))
        return str(value)

    def _init_mqtt_client(self) -> None:
        self._client.username_pw_set(
            username=self._username, password=self._password
        )
        self._client.on_connect = self._on_mqtt_connected
        self._client.on_disconnect = self._on_mqtt_disconnected
        self._client.on_message = self._on_mqtt_message_received

        if self._use_ssl:
            self._client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)

    def _on_mqtt_connected(
        self, client: paho.Client, user_data: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code == 0:
            logger.info("MQTT connected successfully")
            for topic in self._topics:
                client.subscribe(topic, qos=1)
                logger.debug("Subscribed to %s", topic)
        else:
            logger.error("MQTT connection failed with reason code: %s", reason_code)

    def _on_mqtt_disconnected(
        self, client: paho.Client, user_data: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        def callback(username: str, password: str) -> None:
            self._client.username_pw_set(username, password)
            self._client.reconnect()

        if reason_code != 0:
            logger.warning("MQTT disconnected unexpectedly (reason: %s), attempting reconnect", reason_code)
            self._get_access_token_callback(callback)

    def _on_mqtt_message_received(self, client: paho.Client, user_data: Any, message: Any) -> None:
        parsed = json.loads(message.payload.decode("utf-8"))
        logger.debug("Received message on %s: %s", message.topic, parsed)
        callback_func = self._callbacks.get(message.topic)
        if callback_func is not None:
            callback_func(parsed)
        else:
            logger.warning("No callback registered for topic: %s", message.topic)

    def _build_power_message(self, mode: PowerMode) -> str:
        message = self._build_base_message()
        message["ps"] = str(mode.value)
        return json.dumps(message)

    def _build_temp_message(self, temp: float) -> str:
        message = self._build_base_message()
        message["actmp"] = str(temp)
        return json.dumps(message)

    def _build_hvac_mode_message(self, mode: HVACMode) -> str:
        message = self._build_base_message()
        message["acmd"] = str(mode.value)
        return json.dumps(message)

    def _build_fan_mode_message(self, mode: FanMode) -> str:
        message = self._build_base_message()
        message["acfs"] = str(mode.value)
        return json.dumps(message)

    def _build_preset_mode_message(self, mode: PresetMode) -> str:
        message = self._build_base_message()

        if mode == PresetMode.NONE:
            message["acem"] = "off"
            message["acpm"] = "off"
            message["acec"] = "off"
        elif mode == PresetMode.ECO:
            message["acem"] = "on"
            message["acpm"] = "off"
            message["acec"] = "off"
        elif mode == PresetMode.BOOST:
            message["acem"] = "off"
            message["acpm"] = "on"
            message["acec"] = "off"
        elif mode == PresetMode.CLEAN:
            message["acem"] = "off"
            message["acpm"] = "off"
            message["acec"] = "on"
        return json.dumps(message)

    def _build_display_state_message(self, state: DisplayState) -> str:
        message = self._build_base_message()
        message["acdc"] = str(state.value)
        return json.dumps(message)

    def _build_eco_mode_message(self, enabled: bool) -> str:
        message = self._build_base_message()
        message["acem"] = "on" if enabled else "off"
        return json.dumps(message)

    def _build_boost_mode_message(self, enabled: bool) -> str:
        message = self._build_base_message()
        message["acpm"] = "on" if enabled else "off"
        return json.dumps(message)

    def _build_vertical_swing_mode_message(self, mode: SwingMode) -> str:
        message = self._build_base_message()
        message["acvs"] = mode.value
        return json.dumps(message)

    def _build_horizontal_swing_mode_message(self, mode: SwingMode) -> str:
        message = self._build_base_message()
        message["achs"] = mode.value
        return json.dumps(message)

    def _build_converti7_mode_message(self, mode: Converti7Mode) -> str:
        message = self._build_base_message()
        message["cnv"] = mode.value
        return json.dumps(message)

    def _build_base_message(self) -> dict[str, Any]:
        return {
            "ki": 1,
            "cnt": "an",
            "sid": "1",
        }
