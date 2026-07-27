# Setup: MirAIe AC Controller Daemon

How to deploy the always-on AC controller ([example/ac-daemon.py](example/ac-daemon.py))
on a Linux VM (e.g. an Azure VM reached over Tailscale). The daemon keeps your
AC in a desired configuration and re-applies it every few minutes to recover
from power cuts.

> **Security note:** `login_info.ini` and `ac_daemon.ini` hold your MirAIe
> password and a control token. Both are gitignored — never commit them. If a
> credential is ever exposed, rotate it in the MirAIe app.

---

## 1. Install prerequisites (once)

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

The project needs **Python 3.12+**. Check with `python3 --version`. On older
Ubuntu, install a newer Python (e.g. via the deadsnakes PPA) and use
`python3.12` in place of `python3` below.

## 2. Get the project

```bash
cd ~
git clone https://github.com/milothomas/py-miraie-ac.git python-miraie-ac
cd python-miraie-ac
```

## 3. Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`pip install -e .` installs the `py_miraie_ac` library plus its dependencies
(`aiohttp`, `paho-mqtt`). No extra packages are needed for the daemon.

## 4. Configuration files (repo root)

**Credentials** — `login_info.ini`:

```ini
[login]
username = YOUR_MOBILE_NUMBER
password = YOUR_PASSWORD
```

**Daemon config** — `ac_daemon.ini` (copy the template, then edit):

```bash
cp example/ac_daemon.ini.example ac_daemon.ini
nano ac_daemon.ini
```

Key settings:

| Setting            | Meaning                                                        |
| ------------------ | ------------------------------------------------------------- |
| `host`             | `0.0.0.0` (any interface) or your Tailscale IP                |
| `port`             | HTTP port (default `8765`)                                    |
| `token`            | Shared secret required on every request — **set a long one**  |
| `interval_seconds` | How often to re-check the AC (default `300` = 5 min)          |
| `device`           | Friendly device name; blank = first discovered device         |
| `temperature`      | Target setpoint (16–30)                                        |
| `hvac_mode`        | `cool` / `auto` / `dry` / `fan`                               |
| `fan_mode`         | `auto` / `quiet` / `low` / `medium` / `high`                  |
| `converti7`        | `off`/`40`/`55`/`70`/`80`/`90`/`fc`/`hc`; blank = don't touch |

> If `ac_daemon.ini` is missing, the daemon writes a starter template on first
> run and exits so you can edit it.

## 5. Test it manually

```bash
.venv/bin/python example/ac-daemon.py
```

From another shell (or another device on your tailnet):

```bash
curl "http://localhost:8765/status?token=YOUR_TOKEN"
```

Press `Ctrl+C` to stop.

## 6. Run it always (systemd)

Edit [example/ac-daemon.service](example/ac-daemon.service) so `User=`,
`WorkingDirectory=`, and `ExecStart=` match your username and clone path, then:

```bash
sudo cp example/ac-daemon.service /etc/systemd/system/ac-daemon.service
sudo systemctl daemon-reload
sudo systemctl enable --now ac-daemon.service
journalctl -u ac-daemon -f      # follow logs
```

The unit uses `Restart=always`, so it comes back after crashes and reboots, and
waits for `tailscaled` before starting.

## 7. Control it over Tailscale

### Web UI (easiest — phone friendly)

Open the daemon's address in any browser on your tailnet:

```
http://<vm-ip>:8765/
```

Enter your token once (it's stored in the browser, not the URL), then set the
target temperature/mode/fan/Converti7 and tap **Start / Apply** or **Stop**.
Live AC status and recent log output are shown on the same page and refresh
every few seconds. Add it to your phone's home screen for one-tap access.

### curl

Replace `<vm-ip>` with the VM's Tailscale IP (`tailscale ip -4`):

```bash
# Start automatic control (uses ac_daemon.ini defaults)
curl "http://<vm-ip>:8765/start?token=YOUR_TOKEN"

# Start with one-off overrides
curl "http://<vm-ip>:8765/start?token=YOUR_TOKEN&temp=24&mode=cool&fan=auto"

# Check current state / desired config / last actions
curl "http://<vm-ip>:8765/status?token=YOUR_TOKEN"

# Stop automatic control (AC is left as-is)
curl "http://<vm-ip>:8765/stop?token=YOUR_TOKEN"
```

The token can also be sent as a header instead of a query param:

```bash
curl -H "X-Auth-Token: YOUR_TOKEN" "http://<vm-ip>:8765/status"
```

## How it works

While control is **active**, every `interval_seconds` the daemon reads the AC's
live status and, if anything drifted from the desired config (power off, wrong
temperature/mode/fan/Converti7 after a power cut), re-applies only the settings
that are wrong. Converti7 is enforced only in cool mode. Offline devices are
skipped and retried on the next cycle. Sending `/start` forces an immediate
check rather than waiting for the next interval.
