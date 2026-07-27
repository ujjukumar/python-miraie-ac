"""Interactive example CLI for controlling MirAIe air conditioners.

Demonstrates authentication, device discovery, control commands, and the
event system for live status updates.
"""

import asyncio
import configparser
import contextlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from py_miraie_ac import (
    AuthException,
    AuthType,
    ConnectionException,
    Device,
    MirAIeAPI,
    MobileNotRegisteredException,
)
from py_miraie_ac.enums import ConsumptionPeriodType, Converti7Mode, FanMode, HVACMode

CONFIG_FILE = Path(__file__).resolve().parent.parent / "login_info.ini"
PREFS_FILE = Path(__file__).resolve().parent.parent / ".ac_control_prefs.json"
ENERGY_FILE = Path(__file__).resolve().parent.parent / ".ac_energy_history.json"

SEPARATOR = "-" * 50


class QuitRequested(Exception):
    """Raised when the user asks to quit (Ctrl+C or Ctrl+D)."""


# Live status/connection updates arrive on a background MQTT thread. Printing
# directly from that thread would corrupt whatever prompt the main thread is
# showing, so we buffer updates here and flush them from the main thread at
# menu boundaries instead.
_live_events: list[str] = []


def _add_live_event(message: str) -> None:
    """Buffer a live update, skipping consecutive duplicates."""
    if _live_events and _live_events[-1] == message:
        return
    _live_events.append(message)


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


def load_energy_history() -> dict[str, dict[str, dict[str, float]]]:
    """Load stored energy history: {device_id: {period: {date: kWh}}}."""
    try:
        data = json.loads(ENERGY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_energy_history(history: dict[str, dict[str, dict[str, float]]]) -> None:
    """Persist energy history to disk. Failures are non-fatal.

    The MirAIe API only serves roughly the last 6 months of consumption data,
    so we keep our own copy here to retain older readings.
    """
    with contextlib.suppress(OSError):
        ENERGY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


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


def prompt_text(prompt: str) -> str | None:
    """Prompt for a line of text. Returns None on a blank line.

    Ctrl+C or Ctrl+D quits the program cleanly.
    """
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        raise QuitRequested from None
    return raw or None


def show_status(device: Device) -> None:
    """Print the core device status."""
    s = device.status
    online = "ONLINE" if s.is_online else "OFFLINE"
    print(f"\n{SEPARATOR}")
    print(f"  {device.friendly_name}  [{online}]")
    print(SEPARATOR)
    print(f"  Power       : {s.power_mode.value}")
    print(f"  Temperature : {s.temperature}°C")
    # The room-temp sensor only reports a real value while the unit is running;
    # it reads 0 when the AC is off, so don't present that as an actual reading.
    if s.is_online and s.room_temp:
        print(f"  Room Temp   : {s.room_temp}°C (sensor)")
    else:
        print("  Room Temp   : n/a (unit off)")
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
    "Energy consumption",
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


ENERGY_PERIODS = {
    "Daily": ConsumptionPeriodType.DAILY,
    "Weekly": ConsumptionPeriodType.WEEKLY,
    "Monthly": ConsumptionPeriodType.MONTHLY,
}

DATE_HINTS = {
    ConsumptionPeriodType.DAILY: "DDMMYYYY, e.g. 27072026",
    ConsumptionPeriodType.WEEKLY: "DDMMYYYY (a Sunday), e.g. 26072026",
    ConsumptionPeriodType.MONTHLY: "MMYYYY, e.g. 072026",
}


def _energy_sort_key(period: ConsumptionPeriodType, date_key: str) -> str:
    """Return a chronologically sortable form of a MirAIe date key."""
    if period == ConsumptionPeriodType.MONTHLY and len(date_key) == 6:
        return date_key[2:] + date_key[:2]  # MMYYYY -> YYYYMM
    if len(date_key) == 8:
        return date_key[4:] + date_key[2:4] + date_key[:2]  # DDMMYYYY -> YYYYMMDD
    return date_key


def _print_energy_table(period: ConsumptionPeriodType, data: dict[str, float]) -> None:
    """Print a chronologically sorted energy table with a total."""
    if not data:
        print("  (no records)")
        return
    total = 0.0
    for key in sorted(data, key=lambda k: _energy_sort_key(period, k)):
        total += float(data[key])
        print(f"  {key:>10} : {float(data[key]):7.2f} kWh")
    print(f"  {'-' * 26}")
    print(f"  {'Total':>10} : {total:7.2f} kWh  ({len(data)} record(s))")


def _energy_summary_line(period: ConsumptionPeriodType, data: dict[str, float]) -> str:
    """One-line summary: record count, date span, and total kWh."""
    if not data:
        return "(no records)"
    keys = sorted(data, key=lambda k: _energy_sort_key(period, k))
    total = sum(float(v) for v in data.values())
    return f"{len(data)} record(s), {keys[0]}–{keys[-1]}, total {total:.2f} kWh"


# The MirAIe API retains roughly the last 6 months of data. We request a little
# extra and fetch in ~30-day chunks to stay under any per-request range limit.
DAILY_DATE_FORMAT = "%d%m%Y"
API_RETENTION_DAYS = 190
CHUNK_DAYS = 30


async def _fetch_all_daily(api: MirAIeAPI, device: Device) -> dict[str, float]:
    """Fetch every available day of consumption back to the API's oldest date."""
    end = datetime.now().date()
    earliest = end - timedelta(days=API_RETENTION_DAYS)
    merged: dict[str, float] = {}
    window_end = end
    print(f"  Fetching daily history back to ~{earliest.strftime(DAILY_DATE_FORMAT)} ...")
    while window_end >= earliest:
        window_start = max(earliest, window_end - timedelta(days=CHUNK_DAYS - 1))
        try:
            fetched = await api.get_energy_consumption(
                device,
                ConsumptionPeriodType.DAILY,
                window_start.strftime(DAILY_DATE_FORMAT),
                window_end.strftime(DAILY_DATE_FORMAT),
            )
        except Exception as exc:
            print(f"  Stopped early ({window_start} to {window_end}): {exc}")
            break
        merged.update({str(k): float(v) for k, v in fetched.items()})
        print(
            f"    {window_start.strftime(DAILY_DATE_FORMAT)}–"
            f"{window_end.strftime(DAILY_DATE_FORMAT)}: {len(fetched)} day(s)"
        )
        window_end = window_start - timedelta(days=1)
    return merged


async def show_energy(api: MirAIeAPI, device: Device) -> None:
    """Fetch energy consumption for a date range, store it, and show history.

    Readings are cached locally in ENERGY_FILE so they remain available even
    after the MirAIe API drops them (it only serves roughly the last 6 months).
    """
    period_name = pick("Energy period:", list(ENERGY_PERIODS))
    period = ENERGY_PERIODS[period_name]

    print(f"  Date format: {DATE_HINTS[period]}")
    if period == ConsumptionPeriodType.DAILY:
        print("  (tip: enter 'all' to fetch the full available daily history)")
    from_date = prompt_text("  From date (blank to just show stored history): ")

    history = load_energy_history()
    stored = history.setdefault(device.device_id, {}).setdefault(period.value, {})

    printed_fetched = False
    if from_date and from_date.lower() == "all" and period == ConsumptionPeriodType.DAILY:
        fetched = await _fetch_all_daily(api, device)
        if fetched:
            stored.update(fetched)
            save_energy_history(history)
            print(f"\n  Fetched {len(fetched)} day(s) from the API:")
            _print_energy_table(period, fetched)
            printed_fetched = True
    elif from_date:
        to_date = prompt_text("  To date (blank = same as From): ") or from_date
        try:
            fetched = await api.get_energy_consumption(device, period, from_date, to_date)
        except Exception as exc:
            print(f"  Could not fetch from API: {exc}")
            fetched = {}
        if fetched:
            clean = {str(k): float(v) for k, v in fetched.items()}
            stored.update(clean)
            save_energy_history(history)
            print(f"\n  Fetched {len(clean)} record(s) from the API:")
            _print_energy_table(period, clean)
            printed_fetched = True

    if printed_fetched:
        # Avoid re-dumping the full table we just printed; summarize instead.
        print(
            f"\nStored {period_name.lower()} history for {device.friendly_name}: "
            f"{_energy_summary_line(period, stored)}"
        )
    else:
        print(f"\nStored {period_name.lower()} history for {device.friendly_name}:")
        _print_energy_table(period, stored)


async def handle_action(api: MirAIeAPI, device: Device, action: str) -> bool:
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
            current = CONVERTI7_LABELS.get(
                device.status.converti7_mode, device.status.converti7_mode.name
            )
            print(f"  Current capacity: {current}")
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

        case "Energy consumption":
            await show_energy(api, device)

        case "Back to device list":
            return False

    return True


def on_status_changed(device: Device) -> None:
    """Live update handler fired when a device reports new status over MQTT."""
    s = device.status
    _add_live_event(
        f"[live] {device.friendly_name}: power={s.power_mode.value}, "
        f"temp={s.temperature}°C, mode={s.hvac_mode.value}"
    )


def on_connection_changed(device: Device) -> None:
    """Live update handler fired when a device goes online/offline."""
    state = "online" if device.status.is_online else "offline"
    _add_live_event(f"[live] {device.friendly_name} is now {state}")


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
                    if not await handle_action(api, device, action):
                        break
        except QuitRequested:
            pass

        print("\nBye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, QuitRequested):
        print("\nBye!")
