# Python MirAIe AC API

[![CI](https://github.com/milothomas/py-miraie-ac/actions/workflows/ci.yml/badge.svg)](https://github.com/milothomas/py-miraie-ac/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/py-miraie-ac)](https://pypi.org/project/py-miraie-ac/)
[![Python](https://img.shields.io/pypi/pyversions/py-miraie-ac)](https://pypi.org/project/py-miraie-ac/)

A Python library and CLI tool to control MirAIe air conditioners by Panasonic.

## Installation

```
pip install py-miraie-ac
```

For development:
```
pip install -e ".[dev]"
```

## Quick Start (Library)

```python
import asyncio
from py_miraie_ac import MirAIeAPI, AuthType, HVACMode, FanMode, DisplayState

async def main():
    async with MirAIeAPI(
        auth_type=AuthType.MOBILE,
        login_id="YOUR_MOBILE_NUMBER",
        password="YOUR_PASSWORD"
    ) as api:
        await api.initialize()

        for device in api.devices:
            print(f"Found: {device.friendly_name} ({device.model_name})")
            print(f"  Status: {device.status}")

            # Control the AC
            device.turn_on()
            device.set_temperature(24)
            device.set_hvac_mode(HVACMode.COOL)
            device.set_fan_mode(FanMode.AUTO)
            device.set_display_state(DisplayState.ON)

            # Eco/Boost modes (without forcing temperature)
            device.set_eco_mode(True)
            device.set_boost_mode(False)

            # Listen for status changes
            device.on("status_changed", lambda d: print(f"Status updated: {d.status}"))

asyncio.run(main())
```

## CLI Usage

Store your credentials:
```bash
miraie login --login-id YOUR_PHONE --password YOUR_PASS
```

List devices:
```bash
miraie devices
```

Check status:
```bash
miraie status "Living Room"
```

Control your AC:
```bash
miraie on "Living Room"
miraie set "Living Room" --temp 24 --mode cool --fan auto
miraie set "Living Room" --display off --eco on
miraie off "Living Room"
```

## Device Control Methods

| Method | Description |
|--------|-------------|
| `turn_on()` / `turn_off()` | Power control |
| `set_temperature(temp)` | Set temperature (16-30°C) |
| `set_hvac_mode(HVACMode)` | COOL, AUTO, DRY, FAN |
| `set_fan_mode(FanMode)` | AUTO, QUIET, LOW, MEDIUM, HIGH |
| `set_preset_mode(PresetMode)` | NONE, ECO, BOOST |
| `set_display_state(DisplayState)` | ON, OFF |
| `set_eco_mode(bool)` | Toggle eco mode independently |
| `set_boost_mode(bool)` | Toggle boost mode independently |
| `set_vertical_swing_mode(SwingMode)` | AUTO, ONE through FIVE |
| `set_horizontal_swing_mode(SwingMode)` | AUTO, ONE through FIVE |

## Events

```python
# Called when device status changes (temperature, mode, etc.)
device.on("status_changed", lambda device: print(device.status))

# Called when device goes online/offline
device.on("connection_changed", lambda device: print(device.status.is_online))

# Remove a handler
device.off("status_changed", my_handler)

# Legacy callback system (still supported)
device.register_callback(my_callback)
device.remove_callback(my_callback)
```

## Error Handling

```python
from py_miraie_ac import AuthException, MobileNotRegisteredException, DeviceOfflineError

try:
    await api.initialize()
except AuthException:
    print("Invalid credentials")
except MobileNotRegisteredException:
    print("Phone number not registered")

# Temperature validation
device.set_temperature(35)  # Raises ValueError: must be 16-30°C
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=py_miraie_ac --cov-report=term-missing

# Lint
ruff check src/

# Type check
mypy src/ --ignore-missing-imports
```

## License

GPLv3 - see [LICENSE](LICENSE)