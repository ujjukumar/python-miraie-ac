"""Interactive example CLI for controlling MirAIe air conditioners.

Demonstrates authentication, device discovery, control commands, and the
event system for live status updates.
"""

import asyncio
import configparser
import contextlib
import json
from pathlib import Path

from py_miraie_ac import (
    AuthException,
    AuthType,
    ConnectionException,
    Device,
    MirAIeAPI,
    MobileNotRegisteredException,
)
from py_miraie_ac.enums import Converti7Mode, FanMode, HVACMode

CONFIG_FILE = Path(__file__).resolve().parent.parent / "login_info.ini"
PREFS_FILE = Path(__file__).resolve().parent.parent / ".ac_control_prefs.json"

SEPARATOR = "-" * 50


class QuitRequested(Exception):
    """Raised when the user asks to quit (Ctrl+C or Ctrl+D)."""


# Live status/connection updates arrive on a background MQTT thread. Printing
# directly from that thread would corrupt whatever prompt the main thread is
# showing, so we buffer updates here and flush them from the main thread at
# menu boundaries instead.
_live_events: list[str] = []


def flush_live_events() -> None:
    """Print any buffered live updates. Called from the main thread only."""
    if not _live_events:
        return
    print("\nRecent updates:")
    while _live_events:
        print(f"  {_live_events.pop(0)}")


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


def load_prefs() -> dict[str, str]:
    """Load saved preferences (e.g. last selected device). Returns {} if none."""
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_prefs(prefs: dict[str, str]) -> None:
    """Persist preferences to disk. Failures are non-fatal."""
    with contextlib.suppress(OSError):
        PREFS_FILE.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def pick(prompt: str, options: list[str]) -> str:
    """Display numbered options and return the chosen item.

    Pressing Ctrl+C or Ctrl+D quits the program cleanly.
    """
    flush_live_events()
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        try:
            raw = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            raise QuitRequested from None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"  Enter a number between 1 and {len(options)}")


def prompt_float(prompt: str) -> float | None:
    """Prompt for a floating-point value.

    Returns None if the user cancels with a blank line. Ctrl+C or Ctrl+D quits
    the program cleanly.
    """
    while True:
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise QuitRequested from None
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            print("  Enter a valid number (e.g. 24, -1.5) or press Enter to cancel")


def show_status(device: Device) -> None:
    """Print the core device status."""
    s = device.status
    online = "ONLINE" if s.is_online else "OFFLINE"
    print(f"\n{SEPARATOR}")
    print(f"  {device.friendly_name}  [{online}]")
    print(SEPARATOR)
    print(f"  Power       : {s.power_mode.value}")
    print(f"  Temperature : {s.temperature}°C")
    print(f"  Room Temp   : {s.room_temp}°C (sensor)")
    print(f"  HVAC Mode   : {s.hvac_mode.value}")
    print(f"  Fan Mode    : {s.fan_mode.value}")
    print(f"  Last Update : {s.last_updated}")
    print(SEPARATOR)


DEVICE_ACTIONS = [
    "Show status",
    "Turn ON",
    "Turn OFF",
    "Set temperature",
    "Set HVAC mode",
    "Set fan mode",
    "Set capacity (Converti7)",
    "Quick Converti7 (toggle 40%)",
    "Back to device list",
]


CONVERTI7_LABELS = {
    Converti7Mode.OFF: "off",
    Converti7Mode.CAPACITY_40: "40%",
    Converti7Mode.CAPACITY_55: "55%",
    Converti7Mode.CAPACITY_70: "70%",
    Converti7Mode.CAPACITY_80: "80%",
    Converti7Mode.CAPACITY_90: "90%",
    Converti7Mode.FC: "100% (Full Cooling)",
    Converti7Mode.HC: "110% (Hyper Cooling)",
}


def handle_action(device: Device, action: str) -> bool:
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
            temp = prompt_float("  Temperature (16-30, blank to cancel): ")
            if temp is None:
                print("  Cancelled")
            else:
                try:
                    device.set_temperature(temp)
                    print(f"  -> Temperature set to {temp}°C")
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

        case "Set capacity (Converti7)":
            print(f"  Current capacity: {CONVERTI7_LABELS[device.status.converti7_mode]}")
            if device.status.hvac_mode != HVACMode.COOL:
                print("  WARNING: Converti7 only works in COOL mode!")
            options = list(CONVERTI7_LABELS.values())
            choice = pick("Select capacity:", options)
            selected = list(CONVERTI7_LABELS.keys())[options.index(choice)]
            device.set_converti7_mode(selected)
            print(f"  -> Capacity set to {choice}")

        case "Quick Converti7 (toggle 40%)":
            current = device.status.converti7_mode
            target = (
                Converti7Mode.OFF
                if current == Converti7Mode.CAPACITY_40
                else Converti7Mode.CAPACITY_40
            )
            if device.status.hvac_mode != HVACMode.COOL:
                print("  WARNING: Converti7 only works in COOL mode!")
            device.set_converti7_mode(target)
            print(f"  -> Converti7 {CONVERTI7_LABELS[target]}")

        case "Back to device list":
            return False

    return True


def on_status_changed(device: Device) -> None:
    """Live update handler fired when a device reports new status over MQTT."""
    s = device.status
    _live_events.append(
        f"[live] {device.friendly_name}: power={s.power_mode.value}, "
        f"temp={s.temperature}°C, mode={s.hvac_mode.value}"
    )


def on_connection_changed(device: Device) -> None:
    """Live update handler fired when a device goes online/offline."""
    state = "online" if device.status.is_online else "offline"
    _live_events.append(f"[live] {device.friendly_name} is now {state}")


async def main() -> None:
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
        except MobileNotRegisteredException:
            print("This mobile number is not registered with MirAIe.")
            return
        except ConnectionException as exc:
            print(f"Could not connect to MirAIe: {exc}")
            return

        devices = api.devices
        if not devices:
            print("No devices found.")
            return

        # Subscribe to live updates so changes made from the AC remote or the
        # MirAIe app (and confirmations of our own commands) appear here.
        for device in devices:
            device.on("status_changed", on_status_changed)
            device.on("connection_changed", on_connection_changed)

        print(f"\nConnected! Found {len(devices)} device(s).\n")

        prefs = load_prefs()
        last_device_id = prefs.get("last_device_id")

        try:
            auto_select = True
            while True:
                device = None

                # On the first pass, jump straight into the last-used device.
                if auto_select and last_device_id:
                    device = next(
                        (d for d in devices if d.device_id == last_device_id), None
                    )
                    if device is not None:
                        print(f"Auto-selected last device: {device.friendly_name}")
                auto_select = False

                if device is None:
                    device_names = [f"{d.friendly_name} ({d.area_name})" for d in devices]
                    device_names.append("Exit")
                    choice = pick("Select a device:", device_names)
                    if choice == "Exit":
                        break
                    device = devices[device_names.index(choice)]

                # Remember this device for next run.
                prefs["last_device_id"] = device.device_id
                save_prefs(prefs)

                show_status(device)

                # Action loop for the selected device
                while True:
                    action = pick(f"[{device.friendly_name}] Choose action:", DEVICE_ACTIONS)
                    if not handle_action(device, action):
                        break
        except QuitRequested:
            pass

        print("\nBye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, QuitRequested):
        print("\nBye!")
