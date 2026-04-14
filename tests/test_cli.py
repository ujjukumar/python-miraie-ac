"""Tests for CLI"""

import contextlib
from unittest.mock import MagicMock, patch

from py_miraie_ac.cli import _find_device, main


def test_cli_help(capsys):
    with patch("sys.argv", ["miraie", "--help"]), contextlib.suppress(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "MirAIe" in captured.out or "miraie" in captured.out


def test_cli_login(tmp_path):
    config_file = tmp_path / "config.ini"
    with patch("py_miraie_ac.cli.CONFIG_FILE", config_file), \
         patch("py_miraie_ac.cli.CONFIG_DIR", tmp_path), \
         patch("sys.argv", ["miraie", "login", "--login-id", "1234567890", "--password", "test"]):
        main()
    assert config_file.exists()
    content = config_file.read_text()
    assert "1234567890" in content
    assert "mobile" in content


def test_find_device_match():
    device = MagicMock()
    device.friendly_name = "Living Room AC"
    device.name = "living-room-ac"

    api = MagicMock()
    api.devices = [device]

    result = _find_device(api, "living")
    assert result == device


def test_find_device_no_match(capsys):
    device = MagicMock()
    device.friendly_name = "Bedroom AC"
    device.name = "bedroom-ac"

    api = MagicMock()
    api.devices = [device]

    result = _find_device(api, "kitchen")
    assert result is None
