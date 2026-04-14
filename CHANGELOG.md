# Changelog

## [1.0.0] - 2026-04-14

### Breaking Changes
- Minimum Python version raised to 3.12+ (was 3.6)
- Upgraded to paho-mqtt 2.x (breaking callback API changes)
- ECO preset mode no longer forces temperature to 26°C

### Added
- **CLI tool**: `miraie` command with `login`, `devices`, `status`, `set`, `on`, `off` subcommands
- **Display control**: `device.set_display_state()` to toggle the AC display on/off
- **Eco/Boost convenience methods**: `device.set_eco_mode(bool)` and `device.set_boost_mode(bool)`
- **Event system**: `device.on("status_changed", handler)` and `device.on("connection_changed", handler)`
- **Token expiry tracking**: `User.is_expired()` and `User.expires_at` property
- **Temperature validation**: `set_temperature()` now enforces 16-30°C range
- **Offline device warnings**: Logged when sending commands to offline devices
- **HTTP request timeouts**: All API calls now have a 30s timeout
- **Logging**: Comprehensive logging throughout all modules
- **DeviceStatus enhancements**: `last_updated` timestamp, `__repr__()`, `__eq__()`
- **New exceptions**: `TokenExpiredError`, `DeviceOfflineError`
- **PEP 561 support**: `py.typed` marker for type checker compatibility
- **Unit tests**: 79 tests covering all modules (76% coverage)
- **CI/CD**: GitHub Actions for testing (Python 3.12/3.13) and PyPI publishing
- **Pre-commit hooks**: ruff linting + mypy type checking
- **Typed configuration**: ruff, mypy, and pytest configs in pyproject.toml

### Fixed
- **Device details URL bug**: `DEVICE_DETAILS_URL` had a literal `/deviceId` in the path
- **MQTT callback crash**: `_on_mqtt_message_received` crashed when no callback was registered for a topic
- **Bare except**: `utils.to_float()` now catches only `ValueError`/`TypeError` instead of all exceptions
- **MQTT protocol**: Upgraded from MQTTv3.1 to MQTTv3.1.1 for better compatibility

### Changed
- Packaging consolidated from `setup.cfg` to `pyproject.toml` (PEP 621)
- MQTT broker constants moved to `constants.py`
- Dependencies updated: `aiohttp>=3.9`, `paho-mqtt>=2.0`

## [0.1.10] - Previous Release
- Initial working release with basic AC control via MQTT
