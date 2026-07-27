"""Always-on MirAIe AC controller service.

Designed to run continuously on a small server/VM (e.g. reached over Tailscale).
It exposes a tiny HTTP API to start/stop *automatic control* of an air
conditioner. While control is active it re-checks the AC every N seconds
(default 300) and re-applies the desired configuration if it has drifted --
for example after a power cut resets the unit.

Endpoints (every request needs the shared token from ac_daemon.ini, passed as
``?token=...`` or an ``X-Auth-Token`` header):

    GET/POST /start   Start automatic control. Optional query overrides:
                      temp, mode, fan, converti7
                      e.g. /start?token=SECRET&temp=24&mode=cool&fan=auto
    GET/POST /stop    Stop automatic control.
    GET      /status  Report control state, desired config, and live AC status.

Run it with the project's virtual environment:

    ./.venv/Scripts/python.exe example/ac-daemon.py       (Windows, dev)
    ./.venv/bin/python example/ac-daemon.py               (Linux VM)
"""

from __future__ import annotations

import asyncio
import configparser
import contextlib
import hmac
import logging
import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiohttp import web

from py_miraie_ac import (
    AuthException,
    AuthType,
    ConnectionException,
    Device,
    MirAIeAPI,
    MobileNotRegisteredException,
)
from py_miraie_ac.constants import MAX_TEMPERATURE, MIN_TEMPERATURE
from py_miraie_ac.deviceStatus import DeviceStatus
from py_miraie_ac.enums import Converti7Mode, FanMode, HVACMode, PowerMode

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = _ROOT / "ac_daemon.ini"
CREDENTIALS_FILE = _ROOT / "login_info.ini"

logger = logging.getLogger("ac_daemon")

CONVERTI7_MAP: dict[str, Converti7Mode] = {
    "off": Converti7Mode.OFF,
    "40": Converti7Mode.CAPACITY_40,
    "55": Converti7Mode.CAPACITY_55,
    "70": Converti7Mode.CAPACITY_70,
    "80": Converti7Mode.CAPACITY_80,
    "90": Converti7Mode.CAPACITY_90,
    "fc": Converti7Mode.FC,
    "hc": Converti7Mode.HC,
}

DEFAULT_CONFIG_TEXT = """\
[server]
# Interface to bind. Use 0.0.0.0 to accept connections from any interface
# (safe behind Tailscale + the token below), or your Tailscale IP to be strict.
host = 0.0.0.0
port = 8765
# Shared secret required on every request (?token=... or X-Auth-Token header).
# CHANGE THIS to a long random string.
token = change-me

[control]
# How often to verify the AC configuration, in seconds.
interval_seconds = 300
# Friendly device name to control (as shown in the MirAIe app).
# Leave blank to use the first discovered device.
device =
# Desired configuration to enforce whenever control is active.
temperature = 24
hvac_mode = cool
fan_mode = auto
# Converti7 capacity: off / 40 / 55 / 70 / 80 / 90 / fc / hc.
# Only enforced in cool mode. Leave blank to not touch Converti7.
converti7 = off
"""


@dataclass
class DesiredConfig:
    """The AC configuration the daemon tries to maintain."""

    temperature: float
    hvac_mode: HVACMode
    fan_mode: FanMode
    converti7_mode: Converti7Mode | None  # None = do not enforce

    def as_dict(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "hvac_mode": self.hvac_mode.value,
            "fan_mode": self.fan_mode.value,
            "converti7_mode": self.converti7_mode.name if self.converti7_mode else None,
        }


@dataclass
class ServerConfig:
    """Parsed contents of ac_daemon.ini."""

    host: str
    port: int
    token: str
    interval_seconds: int
    device_name: str | None
    desired: DesiredConfig


def _parse_converti7(raw: str) -> Converti7Mode | None:
    """Parse a Converti7 config/query value. Blank means 'do not enforce'."""
    value = raw.strip().lower()
    if not value:
        return None
    if value not in CONVERTI7_MAP:
        raise ValueError(f"invalid converti7 value: {raw!r}")
    return CONVERTI7_MAP[value]


def _validate_temperature(temp: float) -> float:
    if not MIN_TEMPERATURE <= temp <= MAX_TEMPERATURE:
        raise ValueError(
            f"temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}"
        )
    return temp


def load_credentials() -> tuple[str, str]:
    """Read the mobile number and password from login_info.ini."""
    if not CREDENTIALS_FILE.exists():
        print(f"Credentials file not found: {CREDENTIALS_FILE}")
        print("Create it with a [login] section containing 'username' and 'password'.")
        raise SystemExit(1)

    config = configparser.ConfigParser()
    config.read(CREDENTIALS_FILE)
    try:
        return config["login"]["username"], config["login"]["password"]
    except KeyError as exc:
        print(f"Missing {exc} in {CREDENTIALS_FILE}.")
        raise SystemExit(1) from None


def load_config() -> ServerConfig:
    """Load ac_daemon.ini, writing a template and exiting if it is missing."""
    if not CONFIG_FILE.exists():
        with contextlib.suppress(OSError):
            CONFIG_FILE.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        print(f"Wrote a starter config to {CONFIG_FILE}.")
        print("Edit it (especially the token) and run the daemon again.")
        raise SystemExit(1)

    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE)
    server = parser["server"]
    control = parser["control"]

    desired = DesiredConfig(
        temperature=_validate_temperature(float(control.get("temperature", "24"))),
        hvac_mode=HVACMode(control.get("hvac_mode", "cool").strip().lower()),
        fan_mode=FanMode(control.get("fan_mode", "auto").strip().lower()),
        converti7_mode=_parse_converti7(control.get("converti7", "")),
    )
    return ServerConfig(
        host=server.get("host", "0.0.0.0").strip(),
        port=server.getint("port", 8765),
        token=server.get("token", "").strip(),
        interval_seconds=control.getint("interval_seconds", 300),
        device_name=(control.get("device", "").strip() or None),
        desired=desired,
    )


def _apply_overrides(base: DesiredConfig, query: Any) -> DesiredConfig:
    """Return a copy of ``base`` with any /start query parameters applied."""
    temperature = base.temperature
    if "temp" in query:
        temperature = _validate_temperature(float(query["temp"]))

    hvac_mode = base.hvac_mode
    if "mode" in query:
        hvac_mode = HVACMode(query["mode"].strip().lower())

    fan_mode = base.fan_mode
    if "fan" in query:
        fan_mode = FanMode(query["fan"].strip().lower())

    converti7_mode = base.converti7_mode
    if "converti7" in query:
        converti7_mode = _parse_converti7(query["converti7"])

    return DesiredConfig(temperature, hvac_mode, fan_mode, converti7_mode)


def _status_dict(status: DeviceStatus) -> dict[str, Any]:
    return {
        "online": status.is_online,
        "power": status.power_mode.value,
        "setpoint": status.temperature,
        "room_temp": status.room_temp,
        "hvac_mode": status.hvac_mode.value,
        "fan_mode": status.fan_mode.value,
        "converti7": status.converti7_mode.name,
    }


class Controller:
    """Owns the periodic 'enforce the desired config' loop."""

    def __init__(
        self,
        device: Device,
        default: DesiredConfig,
        interval_seconds: int,
    ) -> None:
        self._device = device
        self._default = default
        self._interval = interval_seconds
        self._desired = default
        self._active = False
        self._wake = asyncio.Event()
        self._last_check: datetime | None = None
        self._last_actions: list[str] = []

    @property
    def default(self) -> DesiredConfig:
        return self._default

    def start(self, desired: DesiredConfig) -> None:
        """Activate control with the given desired config and force a check now."""
        self._desired = desired
        self._active = True
        self._wake.set()
        logger.info("Automatic control started: %s", desired.as_dict())

    def stop(self) -> None:
        """Deactivate control. The AC is left in its current state."""
        self._active = False
        self._wake.set()
        logger.info("Automatic control stopped")

    async def run(self) -> None:
        """Main loop: enforce on /start and then once per interval while active."""
        while True:
            if self._active:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=self._interval)
            else:
                await self._wake.wait()
            self._wake.clear()

            if self._active:
                try:
                    await self.enforce()
                except Exception:
                    logger.exception("Enforcement cycle failed")

    async def enforce(self) -> None:
        """Compare live status against the desired config and correct any drift."""
        self._last_check = datetime.now(UTC)
        status = self._device.status
        name = self._device.friendly_name

        if not status.is_online:
            logger.warning("%s is offline; will retry next cycle", name)
            self._last_actions = ["device offline - skipped"]
            return

        desired = self._desired
        actions: list[str] = []

        if status.power_mode != PowerMode.ON:
            self._device.turn_on()
            actions.append("power=on")

        if status.hvac_mode != desired.hvac_mode:
            self._device.set_hvac_mode(desired.hvac_mode)
            actions.append(f"hvac={desired.hvac_mode.value}")

        if status.temperature != desired.temperature:
            self._device.set_temperature(desired.temperature)
            actions.append(f"temp={desired.temperature}")

        if status.fan_mode != desired.fan_mode:
            self._device.set_fan_mode(desired.fan_mode)
            actions.append(f"fan={desired.fan_mode.value}")

        # Converti7 only has an effect in cool mode.
        if (
            desired.converti7_mode is not None
            and desired.hvac_mode == HVACMode.COOL
            and status.converti7_mode != desired.converti7_mode
        ):
            self._device.set_converti7_mode(desired.converti7_mode)
            actions.append(f"converti7={desired.converti7_mode.name}")

        if actions:
            logger.info("Corrected %s: %s", name, ", ".join(actions))
        else:
            logger.debug("%s already in desired config", name)
        self._last_actions = actions or ["already correct"]

    def snapshot(self) -> dict[str, Any]:
        """A JSON-serializable view of the controller and device state."""
        return {
            "active": self._active,
            "interval_seconds": self._interval,
            "device": self._device.friendly_name,
            "desired": self._desired.as_dict(),
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "last_actions": self._last_actions,
            "current": _status_dict(self._device.status),
        }


def build_app(controller: Controller, token: str) -> web.Application:
    """Create the aiohttp application with token-protected control endpoints."""

    def require_token(request: web.Request) -> None:
        provided = request.query.get("token") or request.headers.get("X-Auth-Token", "")
        if not (token and hmac.compare_digest(provided, token)):
            raise web.HTTPUnauthorized(text="invalid or missing token\n")

    async def handle_start(request: web.Request) -> web.Response:
        require_token(request)
        try:
            desired = _apply_overrides(controller.default, request.query)
        except (ValueError, KeyError) as exc:
            raise web.HTTPBadRequest(text=f"bad parameter: {exc}\n") from exc
        controller.start(desired)
        return web.json_response({"status": "control started", "desired": desired.as_dict()})

    async def handle_stop(request: web.Request) -> web.Response:
        require_token(request)
        controller.stop()
        return web.json_response({"status": "control stopped"})

    async def handle_status(request: web.Request) -> web.Response:
        require_token(request)
        return web.json_response(controller.snapshot())

    app = web.Application()
    app.add_routes(
        [
            web.get("/start", handle_start),
            web.post("/start", handle_start),
            web.get("/stop", handle_stop),
            web.post("/stop", handle_stop),
            web.get("/status", handle_status),
        ]
    )
    return app


def _select_device(devices: list[Device], name: str | None) -> Device | None:
    if not devices:
        return None
    if name:
        for device in devices:
            if device.friendly_name.lower() == name.lower():
                return device
        logger.warning("Device %r not found; falling back to the first device", name)
    return devices[0]


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        # add_signal_handler is unavailable on Windows; KeyboardInterrupt still works there.
        with contextlib.suppress(NotImplementedError, AttributeError):
            loop.add_signal_handler(sig, stop_event.set)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()
    if config.token in ("", "change-me"):
        logger.warning(
            "Token is not set (or still 'change-me'); all requests will be rejected. "
            "Edit %s.",
            CONFIG_FILE,
        )

    username, password = load_credentials()

    async with MirAIeAPI(
        auth_type=AuthType.MOBILE,
        login_id=username,
        password=password,
    ) as api:
        try:
            await api.initialize()
        except AuthException:
            logger.error("Authentication failed. Check your credentials.")
            return
        except MobileNotRegisteredException:
            logger.error("This mobile number is not registered with MirAIe.")
            return
        except ConnectionException as exc:
            logger.error("Could not connect to MirAIe: %s", exc)
            return

        device = _select_device(api.devices, config.device_name)
        if device is None:
            logger.error("No devices found.")
            return

        logger.info("Controlling device: %s", device.friendly_name)

        controller = Controller(device, config.desired, config.interval_seconds)
        loop_task = asyncio.create_task(controller.run())

        app = build_app(controller, config.token)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, config.host, config.port)
        await site.start()
        logger.info(
            "Listening on http://%s:%d  (endpoints: /start /stop /status)",
            config.host,
            config.port,
        )

        stop_event = asyncio.Event()
        _install_signal_handlers(stop_event)
        try:
            await stop_event.wait()
        finally:
            logger.info("Shutting down")
            loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await loop_task
            await runner.cleanup()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
