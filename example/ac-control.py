import asyncio
import configparser
from pathlib import Path

from py_miraie_ac import (
    AuthException,
    AuthType,
    MirAIeAPI,
)
from py_miraie_ac.enums import Converti7Mode, DisplayState, FanMode, HVACMode, PresetMode, SwingMode

CONFIG_FILE = Path(__file__).resolve().parent.parent / "login_info.ini"

SEPARATOR = "-" * 50


def load_credentials() -> tuple[str, str]:
    """Read the mobile number and password from login_info.ini."""
    if not CONFIG_FILE.exists():
        print(f"Config file not found: {CONFIG_FILE}")
        print("Create it with the following contents:\n")
        print("[login]")
        print("username = YOUR_MOBILE_NUMBER")
        print("password = YOUR_PASSWORD")
        raise SystemExit(1)

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    try:
        return config["login"]["username"], config["login"]["password"]
    except KeyError as exc:
        print(f"Missing {exc} in {CONFIG_FILE}.")
        print("Expected a [login] section with 'username' and 'password' keys.")
        raise SystemExit(1) from None


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
    print(f"  Room Temp   : {s.room_temp}°C (sensor)")
    if device.room_temp_offset != 0:
        print(f"  Calibrated  : {s.calibrated_room_temp}°C (offset {device.room_temp_offset:+.1f}°C)")
        compensate = "ON" if device.auto_compensate else "OFF"
        print(f"  Auto Comp.  : {compensate}")
    print(f"  HVAC Mode   : {s.hvac_mode.value}")
    print(f"  Fan Mode    : {s.fan_mode.value}")
    print(f"  Preset      : {s.preset_mode.value}")
    print(f"  Display     : {s.display_state.value}")
    print(f"  V-Swing     : {s.vertical_swing_mode.name.lower()}")
    print(f"  H-Swing     : {s.horizontal_swing_mode.name.lower()}")
    print(f"  Capacity    : {s.converti7_mode.name}")
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
    "Set capacity (Converti7)",
    "Set room temp offset",
    "Toggle auto-compensate",
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
            if device.auto_compensate and device.room_temp_offset != 0:
                print(f"  (Auto-compensate ON: offset {device.room_temp_offset:+.1f}°C)")
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

        case "Set capacity (Converti7)":
            labels = {
                Converti7Mode.OFF: "off",
                Converti7Mode.CAPACITY_40: "40%",
                Converti7Mode.CAPACITY_55: "55%",
                Converti7Mode.CAPACITY_70: "70%",
                Converti7Mode.CAPACITY_80: "80%",
                Converti7Mode.CAPACITY_90: "90%",
                Converti7Mode.FC: "100% (Full Cooling)",
                Converti7Mode.HC: "110% (Hyper Cooling)",
            }
            options = list(labels.values())
            modes = list(labels.keys())
            print(f"  Current capacity: {labels[device.status.converti7_mode]}")
            if device.status.hvac_mode != HVACMode.COOL:
                print("  WARNING: Converti7 only works in COOL mode!")
            choice = pick("Select capacity:", options)
            selected = modes[options.index(choice)]
            device.set_converti7_mode(selected)
            print(f"  -> Capacity set to {choice}")

        case "Set room temp offset":
            print(f"  Current offset: {device.room_temp_offset:+.1f}°C")
            print(f"  AC sensor reads: {device.status.room_temp}°C")
            print("  If your actual room temp is lower, enter a negative value (e.g. -2)")
            while True:
                raw = input("  Offset in °C: ").strip()
                try:
                    offset = float(raw)
                    device.room_temp_offset = offset
                    print(f"  -> Offset set to {offset:+.1f}°C")
                    print(f"  -> Calibrated room temp: {device.status.calibrated_room_temp}°C")
                    break
                except ValueError:
                    print("  Enter a valid number (e.g. -2, -1.5, 0)")

        case "Toggle auto-compensate":
            if device.room_temp_offset == 0:
                print("  Set a room temp offset first!")
            else:
                new_state = not device.auto_compensate
                device.auto_compensate = new_state
                state = "ON" if new_state else "OFF"
                print(f"  -> Auto-compensate: {state}")
                if new_state:
                    print(f"     set_temperature() will now adjust by {-device.room_temp_offset:+.1f}°C")

        case "Back to device list":
            return False

    return True


async def main():
    username, password = load_credentials()
    async with MirAIeAPI(
        auth_type=AuthType.MOBILE,
        login_id=username,
        password=password,
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
