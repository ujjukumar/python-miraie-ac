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
from collections import deque
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

# Recent log lines kept in memory so the web UI can show them.
_LOG_BUFFER: deque[str] = deque(maxlen=200)


class _BufferLogHandler(logging.Handler):
    """Logging handler that appends formatted records to _LOG_BUFFER."""

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            _LOG_BUFFER.append(self.format(record))


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

# Single-page web UI served at GET /. Plain string (not an f-string) so the
# JavaScript ${...} and literal \n stay intact.
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MirAIe AC Control</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --muted:#94a3b8; --text:#e2e8f0;
          --accent:#38bdf8; --accent2:#0ea5e9; --ok:#22c55e; --off:#64748b; --err:#f87171; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); padding: 16px; }
  .wrap { max-width: 520px; margin: 0 auto; }
  h1 { font-size: 1.25rem; margin: 0 0 12px; }
  .card { background: var(--card); border-radius: 14px; padding: 16px; margin-bottom: 14px;
          box-shadow: 0 1px 3px rgba(0,0,0,.4); }
  label { display:block; font-size:.8rem; color: var(--muted); margin: 10px 0 4px; }
  input, select { width:100%; padding:10px 12px; border-radius:10px; border:1px solid #334155;
                  background:#0b1220; color:var(--text); font-size:1rem; }
  .row { display:flex; gap:10px; }
  .row > div { flex:1; }
  .btns { display:flex; gap:10px; margin-top:14px; }
  button { flex:1; padding:12px; border:0; border-radius:10px; font-size:1rem; font-weight:600;
           cursor:pointer; }
  .primary { background: var(--accent2); color:#001018; }
  .ghost { background:#334155; color: var(--text); }
  .badge { font-size:.75rem; padding:3px 10px; border-radius:999px; font-weight:700; }
  .badge.on { background: var(--ok); color:#04140a; }
  .badge.off { background: var(--off); color:#0b0f19; }
  .head { display:flex; justify-content:space-between; align-items:center; }
  .grid { display:grid; grid-template-columns:auto 1fr; gap:6px 14px; font-size:.9rem; margin-top:10px; }
  .grid b { color: var(--text); }
  .k { color: var(--muted); }
  .msg { min-height:1.2em; font-size:.85rem; margin-top:10px; }
  .msg.ok { color: var(--accent); }
  .msg.err { color: var(--err); }
  pre#logs { background:#0b1220; border:1px solid #334155; border-radius:10px; padding:10px;
             height:220px; overflow:auto; font-size:.72rem; line-height:1.35; margin:0;
             white-space:pre-wrap; word-break:break-word; }
  .sub { color: var(--muted); font-size:.8rem; margin:0 0 4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>MirAIe AC Control</h1>

  <div class="card">
    <label for="token">Access token</label>
    <input id="token" type="password" placeholder="enter token" autocomplete="off">
  </div>

  <div class="card">
    <div class="head">
      <strong id="device">-</strong>
      <span id="active" class="badge off">...</span>
    </div>
    <div class="grid">
      <div class="k">Power</div><div><b id="power">-</b></div>
      <div class="k">Setpoint</div><div><b id="setpoint">-</b></div>
      <div class="k">Room temp</div><div><b id="room">-</b></div>
      <div class="k">Mode / Fan</div><div><b id="modefan">-</b></div>
      <div class="k">Converti7</div><div><b id="conv">-</b></div>
      <div class="k">Online</div><div><b id="online">-</b></div>
      <div class="k">Last check</div><div id="lastcheck">-</div>
      <div class="k">Last actions</div><div id="lastactions">-</div>
    </div>
  </div>

  <div class="card">
    <p class="sub">Set the target configuration, then Start / Apply.</p>
    <div class="row">
      <div>
        <label for="temp">Temperature (C)</label>
        <input id="temp" type="number" min="16" max="30" step="0.5" value="24">
      </div>
      <div>
        <label for="mode">HVAC mode</label>
        <select id="mode">
          <option value="cool">Cool</option>
          <option value="auto">Auto</option>
          <option value="dry">Dry</option>
          <option value="fan">Fan</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label for="fan">Fan</label>
        <select id="fan">
          <option value="auto">Auto</option>
          <option value="quiet">Quiet</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      <div>
        <label for="converti7">Converti7</label>
        <select id="converti7">
          <option value="">(don't enforce)</option>
          <option value="off">Off</option>
          <option value="40">40%</option>
          <option value="55">55%</option>
          <option value="70">70%</option>
          <option value="80">80%</option>
          <option value="90">90%</option>
          <option value="fc">100% (Full)</option>
          <option value="hc">110% (Hyper)</option>
        </select>
      </div>
    </div>
    <div class="btns">
      <button id="startBtn" class="primary">Start / Apply</button>
      <button id="stopBtn" class="ghost">Stop</button>
    </div>
    <div id="msg" class="msg"></div>
  </div>

  <div class="card">
    <label>Log output</label>
    <pre id="logs">...</pre>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);
const CONV_NAME_TO_OPT = { OFF:'off', CAPACITY_40:'40', CAPACITY_55:'55',
  CAPACITY_70:'70', CAPACITY_80:'80', CAPACITY_90:'90', FC:'fc', HC:'hc' };
let formInit = false;

function token() { return localStorage.getItem('ac_token') || ''; }

function buildQuery(params) {
  const p = new URLSearchParams(params || {});
  p.set('token', token());
  return p.toString();
}

async function api(path, params) {
  const res = await fetch(path + '?' + buildQuery(params));
  if (!res.ok) {
    const t = await res.text();
    throw new Error(res.status + ': ' + t.trim());
  }
  return res.json();
}

function msg(text, isErr) {
  const el = $('msg');
  el.textContent = text || '';
  el.className = 'msg ' + (isErr ? 'err' : 'ok');
}

function renderStatus(s) {
  $('device').textContent = s.device;
  const a = $('active');
  a.textContent = s.active ? 'ACTIVE' : 'stopped';
  a.className = 'badge ' + (s.active ? 'on' : 'off');
  const c = s.current || {};
  $('power').textContent = c.power ?? '-';
  $('setpoint').textContent = (c.setpoint ?? '-') + ' C';
  $('room').textContent = (c.room_temp ?? '-') + ' C';
  $('modefan').textContent = (c.hvac_mode ?? '-') + ' / ' + (c.fan_mode ?? '-');
  $('conv').textContent = c.converti7 ?? '-';
  $('online').textContent = c.online ? 'yes' : 'no';
  $('lastcheck').textContent = s.last_check || 'never';
  $('lastactions').textContent = (s.last_actions || []).join(', ') || '-';
  if (!formInit && s.desired) {
    $('temp').value = s.desired.temperature;
    $('mode').value = s.desired.hvac_mode;
    $('fan').value = s.desired.fan_mode;
    $('converti7').value = CONV_NAME_TO_OPT[s.desired.converti7_mode] || '';
    formInit = true;
  }
}

async function refresh() {
  try { renderStatus(await api('/status')); }
  catch (e) { msg(e.message, true); }
}

async function refreshLogs() {
  try {
    const r = await api('/logs');
    const pre = $('logs');
    const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 12;
    pre.textContent = (r.lines || []).join('\n');
    if (atBottom) pre.scrollTop = pre.scrollHeight;
  } catch (e) { /* ignore log fetch errors */ }
}

async function start() {
  try {
    const r = await api('/start', {
      temp: $('temp').value,
      mode: $('mode').value,
      fan: $('fan').value,
      converti7: $('converti7').value,
    });
    msg('Started - enforcing ' + JSON.stringify(r.desired));
    refresh(); refreshLogs();
  } catch (e) { msg(e.message, true); }
}

async function stop() {
  try { await api('/stop'); msg('Stopped.'); refresh(); refreshLogs(); }
  catch (e) { msg(e.message, true); }
}

$('token').value = token();
$('token').addEventListener('change', (e) => {
  localStorage.setItem('ac_token', e.target.value.trim());
  formInit = false; refresh(); refreshLogs();
});
$('startBtn').addEventListener('click', start);
$('stopBtn').addEventListener('click', stop);
refresh(); refreshLogs();
setInterval(() => { refresh(); refreshLogs(); }, 5000);
</script>
</body>
</html>
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

    async def handle_logs(request: web.Request) -> web.Response:
        require_token(request)
        return web.json_response({"lines": list(_LOG_BUFFER)})

    async def handle_index(request: web.Request) -> web.Response:
        return web.Response(text=INDEX_HTML, content_type="text/html")

    app = web.Application()
    app.add_routes(
        [
            web.get("/", handle_index),
            web.get("/start", handle_start),
            web.post("/start", handle_start),
            web.get("/stop", handle_stop),
            web.post("/stop", handle_stop),
            web.get("/status", handle_status),
            web.get("/logs", handle_logs),
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
    log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    buffer_handler = _BufferLogHandler()
    buffer_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(buffer_handler)

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
