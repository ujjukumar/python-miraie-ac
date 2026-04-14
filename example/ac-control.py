import asyncio
import configparser

from py_miraie_ac import (
    AuthException,
    AuthType,
    MirAIeAPI,
)
from py_miraie_ac.enums import DisplayState, FanMode, HVACMode, PresetMode, SwingMode

config = configparser.ConfigParser()
config.read("login_info.ini")

SEPARATOR = "-" * 50


def pick(prompt, options):
    """Display numbered options and return the chosen item."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input(">>> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"  Enter a number between 1 and {len(options)}")


def show_status(device):
    """Print full device status."""
    s = device.status
    online = "ONLINE" if s.is_online else "OFFLINE"
    print(f"\n{SEPARATOR}")
    print(f"  {device.friendly_name}  [{online}]")
    print(SEPARATOR)
    print(f"  Power       : {s.power_mode.value}")
    print(f"  Temperature : {s.temperature}°C")
    print(f"  Room Temp   : {s.room_temp}°C")
    print(f"  HVAC Mode   : {s.hvac_mode.value}")
    print(f"  Fan Mode    : {s.fan_mode.value}")
    print(f"  Preset      : {s.preset_mode.value}")
    print(f"  Display     : {s.display_state.value}")
    print(f"  V-Swing     : {s.vertical_swing_mode.name.lower()}")
    print(f"  H-Swing     : {s.horizontal_swing_mode.name.lower()}")
    print(f"  Last Update : {s.last_updated}")
    print(SEPARATOR)


DEVICE_ACTIONS = [
    "Show status",
    "Turn ON",
    "Turn OFF",
    "Set temperature",
    "Set HVAC mode",
    "Set fan mode",
    "Set preset mode",
    "Set display",
    "Set eco mode",
    "Set boost mode",
    "Set vertical swing",
    "Set horizontal swing",
    "Back to device list",
]


def handle_action(device, action):
    """Execute the chosen action on the device. Returns False to go back."""
    match action:
        case "Show status":
            show_status(device)

        case "Turn ON":
            device.turn_on()
            print("  -> Turned ON")

        case "Turn OFF":
            device.turn_off()
            print("  -> Turned OFF")

        case "Set temperature":
            while True:
                raw = input("  Temperature (16-30): ").strip()
                try:
                    temp = float(raw)
                    device.set_temperature(temp)
                    print(f"  -> Temperature set to {temp}°C")
                    break
                except ValueError as e:
                    print(f"  {e}")

        case "Set HVAC mode":
            modes = [m.value for m in HVACMode]
            choice = pick("Select HVAC mode:", modes)
            device.set_hvac_mode(HVACMode(choice))
            print(f"  -> HVAC mode set to {choice}")

        case "Set fan mode":
            modes = [m.value for m in FanMode]
            choice = pick("Select fan mode:", modes)
            device.set_fan_mode(FanMode(choice))
            print(f"  -> Fan mode set to {choice}")

        case "Set preset mode":
            modes = [m.value for m in PresetMode]
            choice = pick("Select preset mode:", modes)
            device.set_preset_mode(PresetMode(choice))
            print(f"  -> Preset mode set to {choice}")

        case "Set display":
            states = [s.value for s in DisplayState]
            choice = pick("Display state:", states)
            device.set_display_state(DisplayState(choice))
            print(f"  -> Display set to {choice}")

        case "Set eco mode":
            choice = pick("Eco mode:", ["on", "off"])
            device.set_eco_mode(choice == "on")
            print(f"  -> Eco mode {'enabled' if choice == 'on' else 'disabled'}")

        case "Set boost mode":
            choice = pick("Boost mode:", ["on", "off"])
            device.set_boost_mode(choice == "on")
            print(f"  -> Boost mode {'enabled' if choice == 'on' else 'disabled'}")

        case "Set vertical swing":
            modes = [m.name.lower() for m in SwingMode]
            choice = pick("Vertical swing:", modes)
            device.set_vertical_swing_mode(SwingMode[choice.upper()])
            print(f"  -> Vertical swing set to {choice}")

        case "Set horizontal swing":
            modes = [m.name.lower() for m in SwingMode]
            choice = pick("Horizontal swing:", modes)
            device.set_horizontal_swing_mode(SwingMode[choice.upper()])
            print(f"  -> Horizontal swing set to {choice}")

        case "Back to device list":
            return False

    return True


async def main():
    async with MirAIeAPI(
        auth_type=AuthType.MOBILE,
        login_id=config["login"]["username"],
        password=config["login"]["password"],
    ) as api:
        try:
            await api.initialize()
        except AuthException:
            print("Authentication failed. Check your credentials.")
            return

        devices = api.devices
        if not devices:
            print("No devices found.")
            return

        print(f"\nConnected! Found {len(devices)} device(s).\n")

        while True:
            # Device selection
            device_names = [f"{d.friendly_name} ({d.area_name})" for d in devices]
            device_names.append("Exit")

            choice = pick("Select a device:", device_names)
            if choice == "Exit":
                print("Bye!")
                break

            idx = device_names.index(choice)
            device = devices[idx]
            show_status(device)

            # Action loop for the selected device
            while True:
                action = pick(f"[{device.friendly_name}] Choose action:", DEVICE_ACTIONS)
                if not handle_action(device, action):
                    break


asyncio.run(main())
