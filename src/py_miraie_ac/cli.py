"""Command-line interface for MirAIe AC control"""

import argparse
import asyncio
import configparser
import sys
from pathlib import Path

from .api import MirAIeAPI
from .enums import AuthType, DisplayState, FanMode, HVACMode, SwingMode

CONFIG_DIR = Path.home() / ".config" / "miraie"
CONFIG_FILE = CONFIG_DIR / "config.ini"


def _load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)
    return config


def _save_config(config: configparser.ConfigParser):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        config.write(f)


def _get_api_from_config() -> tuple[AuthType, str, str]:
    config = _load_config()
    if "login" not in config:
        print("Not logged in. Run 'miraie login' first.", file=sys.stderr)
        sys.exit(1)

    auth_type = AuthType(config["login"]["auth_type"])
    login_id = config["login"]["login_id"]
    password = config["login"]["password"]
    return auth_type, login_id, password


async def _run_with_api(func):
    auth_type, login_id, password = _get_api_from_config()
    async with MirAIeAPI(auth_type=auth_type, login_id=login_id, password=password) as api:
        await api.initialize()
        await func(api)


def cmd_login(args):
    """Store credentials in config file"""
    config = _load_config()
    config["login"] = {
        "auth_type": args.auth_type,
        "login_id": args.login_id,
        "password": args.password,
    }
    _save_config(config)
    print(f"Credentials saved to {CONFIG_FILE}")


def cmd_devices(args):
    """List all devices"""
    async def _list(api: MirAIeAPI):
        for device in api.devices:
            online = "online" if device.status.is_online else "offline"
            print(f"  {device.friendly_name} ({device.model_name}) [{online}]")
            print(f"    ID: {device.device_id}")
            print(f"    Area: {device.area_name}")
            print(f"    Power: {device.status.power_mode.value}")
            print(f"    Temperature: {device.status.temperature}°C (Room: {device.status.room_temp}°C)")
            print(f"    Mode: {device.status.hvac_mode.value} | Fan: {device.status.fan_mode.value}")
            print()

    asyncio.run(_run_with_api(_list))


def cmd_status(args):
    """Show detailed status for a device"""
    async def _status(api: MirAIeAPI):
        device = _find_device(api, args.device)
        if device is None:
            return
        s = device.status
        print(f"Device: {device.friendly_name}")
        print(f"  Online:      {s.is_online}")
        print(f"  Power:       {s.power_mode.value}")
        print(f"  Temperature: {s.temperature}°C")
        print(f"  Room Temp:   {s.room_temp}°C")
        print(f"  HVAC Mode:   {s.hvac_mode.value}")
        print(f"  Fan Mode:    {s.fan_mode.value}")
        print(f"  Preset:      {s.preset_mode.value}")
        print(f"  Display:     {s.display_state.value}")
        print(f"  V-Swing:     {s.vertical_swing_mode.value}")
        print(f"  H-Swing:     {s.horizontal_swing_mode.value}")
        print(f"  Last Update: {s.last_updated}")

    asyncio.run(_run_with_api(_status))


def cmd_set(args):
    """Set device parameters"""
    async def _set(api: MirAIeAPI):
        device = _find_device(api, args.device)
        if device is None:
            return

        if args.temp is not None:
            device.set_temperature(args.temp)
            print(f"Temperature set to {args.temp}°C")

        if args.mode is not None:
            device.set_hvac_mode(HVACMode(args.mode))
            print(f"HVAC mode set to {args.mode}")

        if args.fan is not None:
            device.set_fan_mode(FanMode(args.fan))
            print(f"Fan mode set to {args.fan}")

        if args.display is not None:
            device.set_display_state(DisplayState(args.display))
            print(f"Display set to {args.display}")

        if args.vswing is not None:
            device.set_vertical_swing_mode(SwingMode(args.vswing))
            print(f"Vertical swing set to {args.vswing}")

        if args.hswing is not None:
            device.set_horizontal_swing_mode(SwingMode(args.hswing))
            print(f"Horizontal swing set to {args.hswing}")

        if args.eco is not None:
            device.set_eco_mode(args.eco.lower() == "on")
            print(f"Eco mode {'enabled' if args.eco.lower() == 'on' else 'disabled'}")

        if args.boost is not None:
            device.set_boost_mode(args.boost.lower() == "on")
            print(f"Boost mode {'enabled' if args.boost.lower() == 'on' else 'disabled'}")

    asyncio.run(_run_with_api(_set))


def cmd_on(args):
    """Turn on a device"""
    async def _on(api: MirAIeAPI):
        device = _find_device(api, args.device)
        if device is None:
            return
        device.turn_on()
        print(f"Turned on {device.friendly_name}")

    asyncio.run(_run_with_api(_on))


def cmd_off(args):
    """Turn off a device"""
    async def _off(api: MirAIeAPI):
        device = _find_device(api, args.device)
        if device is None:
            return
        device.turn_off()
        print(f"Turned off {device.friendly_name}")

    asyncio.run(_run_with_api(_off))


def _find_device(api: MirAIeAPI, name: str):
    """Find a device by name (case-insensitive partial match)"""
    name_lower = name.lower()
    for device in api.devices:
        if name_lower in device.friendly_name.lower() or name_lower in device.name:
            return device

    print(f"Device '{name}' not found. Available devices:", file=sys.stderr)
    for device in api.devices:
        print(f"  - {device.friendly_name}", file=sys.stderr)
    return None


def main():
    parser = argparse.ArgumentParser(
        prog="miraie",
        description="Control MirAIe air conditioners by Panasonic",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # login
    login_parser = subparsers.add_parser("login", help="Store login credentials")
    login_parser.add_argument("--auth-type", choices=["mobile", "email", "username"], default="mobile")
    login_parser.add_argument("--login-id", required=True, help="Phone number, email, or username")
    login_parser.add_argument("--password", required=True)
    login_parser.set_defaults(func=cmd_login)

    # devices
    devices_parser = subparsers.add_parser("devices", help="List all devices with status")
    devices_parser.set_defaults(func=cmd_devices)

    # status
    status_parser = subparsers.add_parser("status", help="Show detailed device status")
    status_parser.add_argument("device", help="Device name (partial match)")
    status_parser.set_defaults(func=cmd_status)

    # set
    set_parser = subparsers.add_parser("set", help="Set device parameters")
    set_parser.add_argument("device", help="Device name (partial match)")
    set_parser.add_argument("--temp", type=float, help="Temperature (16-30)")
    set_parser.add_argument("--mode", choices=["cool", "auto", "dry", "fan"], help="HVAC mode")
    set_parser.add_argument("--fan", choices=["auto", "quiet", "low", "medium", "high"], help="Fan mode")
    set_parser.add_argument("--display", choices=["on", "off"], help="Display state")
    set_parser.add_argument("--vswing", type=int, choices=range(6), help="Vertical swing (0-5)")
    set_parser.add_argument("--hswing", type=int, choices=range(6), help="Horizontal swing (0-5)")
    set_parser.add_argument("--eco", choices=["on", "off"], help="Eco mode")
    set_parser.add_argument("--boost", choices=["on", "off"], help="Boost mode")
    set_parser.set_defaults(func=cmd_set)

    # on
    on_parser = subparsers.add_parser("on", help="Turn on a device")
    on_parser.add_argument("device", help="Device name (partial match)")
    on_parser.set_defaults(func=cmd_on)

    # off
    off_parser = subparsers.add_parser("off", help="Turn off a device")
    off_parser.add_argument("device", help="Device name (partial match)")
    off_parser.set_defaults(func=cmd_off)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
