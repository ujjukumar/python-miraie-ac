"""The MirAIe device"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC

from .broker import MirAIeBroker
from .constants import MAX_TEMPERATURE, MIN_TEMPERATURE
from .deviceStatus import DeviceStatus
from .enums import DisplayState, FanMode, HVACMode, PowerMode, PresetMode, SwingMode
from .utils import to_float

logger = logging.getLogger(__name__)


class Device:
    """The MirAIe device class"""

    _broker: MirAIeBroker
    _callbacks: list[Callable]
    _event_handlers: dict[str, list[Callable]]

    def __init__(
        self,
        device_id: str,
        name: str,
        friendly_name: str,
        control_topic: str,
        status_topic: str,
        connection_status_topic: str,
        model_name: str,
        mac_address: str,
        category: str,
        brand: str,
        firmware_version: str,
        serial_number: str,
        model_number: str,
        product_serial_number: str,
        status: DeviceStatus,
        broker: MirAIeBroker,
        area_name: str,
    ):
        self.device_id = device_id
        self.name = name
        self.friendly_name = friendly_name
        self.control_topic = control_topic
        self.status_topic = status_topic
        self.connection_status_topic = connection_status_topic
        self.model_name = model_name
        self.mac_address = mac_address
        self.category = category
        self.brand = brand
        self.firmware_version = firmware_version
        self.serial_number = serial_number
        self.model_number = model_number
        self.product_serial_number = product_serial_number
        self.status = status
        self.area_name = area_name

        self._broker = broker
        self._callbacks = []
        self._event_handlers = {}
        self._broker.register_callback(self.status_topic, self.status_callback_handler)
        self._broker.register_callback(
            self.connection_status_topic, self.connection_callback_handler
        )

    def _publish_state(self):
        for callback in self._callbacks:
            callback()

    def _emit(self, event: str):
        for handler in self._event_handlers.get(event, []):
            handler(self)

    def on(self, event: str, handler: Callable) -> None:
        """Registers an event handler. Supported events: 'status_changed', 'connection_changed'"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """Removes a previously registered event handler"""
        handlers = self._event_handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def status_callback_handler(self, status: dict):
        """Handles MQTT messages received on the status topic"""
        self.status = self._parse_status_response(status)
        self._publish_state()
        self._emit("status_changed")

    def _parse_status_response(self, json: dict) -> DeviceStatus:
        is_online = self.status.is_online
        if "onlineStatus" in json:
            is_online = json["onlineStatus"] == "true"

        device_status = DeviceStatus(
            is_online=is_online,
            temperature=to_float(json["actmp"]),
            room_temp=to_float(json["rmtmp"]),
            power_mode=PowerMode(json["ps"]),
            fan_mode=FanMode(json["acfs"]),
            display_state=DisplayState(json["acdc"]),
            hvac_mode=HVACMode(json["acmd"]),
            preset_mode=PresetMode.BOOST
            if json["acpm"] == "on"
            else PresetMode.ECO
            if json["acem"] == "on"
            else PresetMode.NONE,
            vertical_swing_mode=SwingMode(json["acvs"]),
            horizontal_swing_mode=SwingMode(json["achs"]),
        )

        return device_status

    def connection_callback_handler(self, status: dict):
        """Handles MQTT messages received on the connection status topic"""
        if "onlineStatus" in status:
            self.status.is_online = status["onlineStatus"] == "true"
            from datetime import datetime
            self.status.last_updated = datetime.now(UTC)
            self._publish_state()
            self._emit("connection_changed")

    def _warn_if_offline(self, action: str):
        if not self.status.is_online:
            logger.warning("Sending '%s' to offline device %s", action, self.friendly_name)

    def set_temperature(self, temp: float):
        """Sets the temperature (must be between 16.0 and 30.0)"""
        if temp < MIN_TEMPERATURE or temp > MAX_TEMPERATURE:
            raise ValueError(
                f"Temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}, got {temp}"
            )
        self._warn_if_offline("set_temperature")
        self._broker.set_temperature(self.control_topic, temp)

    def turn_on(self):
        """Turns on the device"""
        self._warn_if_offline("turn_on")
        self._broker.set_power(self.control_topic, PowerMode.ON)

    def turn_off(self):
        """Turns off the device"""
        self._warn_if_offline("turn_off")
        self._broker.set_power(self.control_topic, PowerMode.OFF)

    def set_hvac_mode(self, mode: HVACMode):
        """Sets the HVAC mode"""
        self._warn_if_offline("set_hvac_mode")
        self._broker.set_hvac_mode(self.control_topic, mode)

    def set_fan_mode(self, mode: FanMode):
        """Sets the fan mode"""
        self._warn_if_offline("set_fan_mode")
        self._broker.set_fan_mode(self.control_topic, mode)

    def set_preset_mode(self, mode: PresetMode):
        """Sets the preset mode"""
        self._warn_if_offline("set_preset_mode")
        self._broker.set_preset_mode(self.control_topic, mode)

    def set_display_state(self, state: DisplayState):
        """Sets the display state (on/off)"""
        self._warn_if_offline("set_display_state")
        self._broker.set_display_state(self.control_topic, state)

    def set_eco_mode(self, enabled: bool):
        """Enables or disables eco mode without changing temperature"""
        self._warn_if_offline("set_eco_mode")
        self._broker.set_eco_mode(self.control_topic, enabled)

    def set_boost_mode(self, enabled: bool):
        """Enables or disables boost mode"""
        self._warn_if_offline("set_boost_mode")
        self._broker.set_boost_mode(self.control_topic, enabled)

    def set_vertical_swing_mode(self, mode: SwingMode):
        """Sets the vertical swing mode"""
        self._warn_if_offline("set_vertical_swing_mode")
        self._broker.set_vertical_swing_mode(self.control_topic, mode)

    def set_horizontal_swing_mode(self, mode: SwingMode):
        """Sets the horizontal swing mode"""
        self._warn_if_offline("set_horizontal_swing_mode")
        self._broker.set_horizontal_swing_mode(self.control_topic, mode)

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Registers a callback function"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Removes a callback function"""
        self._callbacks.remove(callback)
