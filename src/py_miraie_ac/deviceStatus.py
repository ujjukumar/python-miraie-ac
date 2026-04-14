"""Represents the status of a device"""

from datetime import UTC, datetime

from .enums import Converti7Mode, DisplayState, FanMode, HVACMode, PowerMode, PresetMode, SwingMode


class DeviceStatus:
    """The Device Status class"""

    def __init__(
        self,
        is_online: bool,
        temperature: float,
        room_temp: float,
        power_mode: PowerMode,
        fan_mode: FanMode,
        display_state: DisplayState,
        hvac_mode: HVACMode,
        preset_mode: PresetMode,
        horizontal_swing_mode: SwingMode,
        vertical_swing_mode: SwingMode,
        converti7_mode: Converti7Mode = Converti7Mode.OFF,
    ):
        self.is_online = is_online
        self.temperature = temperature
        self.room_temp = room_temp
        self.power_mode = power_mode
        self.fan_mode = fan_mode
        self.display_state = display_state
        self.hvac_mode = hvac_mode
        self.preset_mode = preset_mode
        self.horizontal_swing_mode = horizontal_swing_mode
        self.vertical_swing_mode = vertical_swing_mode
        self.converti7_mode = converti7_mode
        self.last_updated = datetime.now(UTC)
        self._room_temp_offset: float = 0.0

    @property
    def calibrated_room_temp(self) -> float:
        """Room temperature with calibration offset applied"""
        return round(self.room_temp + self._room_temp_offset, 1)

    def __repr__(self) -> str:
        return (
            f"DeviceStatus(online={self.is_online}, power={self.power_mode.value}, "
            f"temp={self.temperature}, room_temp={self.room_temp}, "
            f"calibrated_room_temp={self.calibrated_room_temp}, "
            f"hvac={self.hvac_mode.value}, fan={self.fan_mode.value}, "
            f"preset={self.preset_mode.value}, display={self.display_state.value}, "
            f"vswing={self.vertical_swing_mode.value}, hswing={self.horizontal_swing_mode.value}, "
            f"converti7={self.converti7_mode.name})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeviceStatus):
            return NotImplemented
        return (
            self.is_online == other.is_online
            and self.temperature == other.temperature
            and self.room_temp == other.room_temp
            and self.power_mode == other.power_mode
            and self.fan_mode == other.fan_mode
            and self.display_state == other.display_state
            and self.hvac_mode == other.hvac_mode
            and self.preset_mode == other.preset_mode
            and self.horizontal_swing_mode == other.horizontal_swing_mode
            and self.vertical_swing_mode == other.vertical_swing_mode
            and self.converti7_mode == other.converti7_mode
        )
