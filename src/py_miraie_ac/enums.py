"""The enums used in the library"""
from enum import Enum


class AuthType(Enum):
    """The Auth Type enum"""
    MOBILE = "mobile"
    EMAIL = "email"
    USERNAME = "username"


class DisplayState(Enum):
    """The Display State enum"""
    ON = "on"
    OFF = "off"


class FanMode(Enum):
    """The Fan Mode enum"""
    AUTO = "auto"
    QUIET = "quiet"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HVACMode(Enum):
    """The HVAC Mode enum"""
    COOL = "cool"
    AUTO = "auto"
    DRY = "dry"
    FAN = "fan"

class PowerMode(Enum):
    """The Power Mode enum"""
    ON = "on"
    OFF = "off"


class PresetMode(Enum):
    """The Preset Mode enum"""
    NONE = "none"
    ECO = "eco"
    BOOST = "boost"


class SwingMode(Enum):
    """The Swing Mode enum"""
    AUTO = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class Converti7Mode(Enum):
    """The Converti7 (capacity control) enum.

    Controls compressor capacity from 40% to 110%.
    HC = Hyper Cooling (110%), FC = Full Cooling (100%).
    Only works in COOL mode.
    """
    OFF = 0
    CAPACITY_40 = 40
    CAPACITY_55 = 55
    CAPACITY_70 = 70
    CAPACITY_80 = 80
    CAPACITY_90 = 90
    FC = 100
    HC = 110
