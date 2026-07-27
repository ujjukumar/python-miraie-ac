"""Tests for MirAIeAPI"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from py_miraie_ac.api import MirAIeAPI
from py_miraie_ac.enums import AuthType, ConsumptionPeriodType
from py_miraie_ac.exceptions import AuthException, ConnectionException, MobileNotRegisteredException
from py_miraie_ac.user import User
from tests.conftest import SAMPLE_LOGIN_RESPONSE


@pytest.fixture
def mock_response():
    """Creates a mock aiohttp response"""
    def _make(status=200, json_data=None):
        resp = AsyncMock()
        resp.status = status
        resp.json = AsyncMock(return_value=json_data)
        return resp
    return _make


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, mock_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response(200, SAMPLE_LOGIN_RESPONSE))
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="1234567890", password="test")
            api._http_session = mock_session

            user = await api._login()
            assert user.access_token == "test-access-token"
            assert user.refresh_token == "test-refresh-token"
            assert user.user_id == "test-user-id"
            assert user.expires_in == 3600

    @pytest.mark.asyncio
    async def test_login_auth_failure(self, mock_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response(401))
            mock_session_cls.return_value = mock_session

            api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="1234567890", password="wrong")
            api._http_session = mock_session

            with pytest.raises(AuthException):
                await api._login()

    @pytest.mark.asyncio
    async def test_login_mobile_not_registered(self, mock_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response(412, {"error": "not registered"}))
            mock_session_cls.return_value = mock_session

            api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="0000000000", password="test")
            api._http_session = mock_session

            with pytest.raises(MobileNotRegisteredException):
                await api._login()

    @pytest.mark.asyncio
    async def test_login_connection_error(self, mock_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response(500, {"error": "server error"}))
            mock_session_cls.return_value = mock_session

            api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="1234567890", password="test")
            api._http_session = mock_session

            with pytest.raises(ConnectionException):
                await api._login()


class TestAPIProperties:
    @patch("py_miraie_ac.api.aiohttp.ClientSession")
    def test_auth_type_stored(self, mock_session):
        api = MirAIeAPI(auth_type=AuthType.EMAIL, login_id="test@test.com", password="test")
        assert api._auth_type == "email"

    @patch("py_miraie_ac.api.aiohttp.ClientSession")
    def test_scope_generation(self, mock_session):
        api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="123", password="test")
        scope = api._get_scope()
        assert scope.startswith("an")
        assert len(scope) > 2

    @patch("py_miraie_ac.api.aiohttp.ClientSession")
    def test_http_headers(self, mock_session):
        api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="123", password="test")
        api._user = User(access_token="token123", expires_in=3600, refresh_token="ref", user_id="uid")
        headers = api._build_http_headers()
        assert headers["Authorization"] == "Bearer token123"
        assert headers["Content-Type"] == "application/json"


class TestEnergyConsumption:
    def _make_api(self, mock_session):
        api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id="123", password="test")
        api._http_session = mock_session
        api._user = User(
            access_token="tok", refresh_token="ref", user_id="uid", expires_in=3600
        )
        return api

    @pytest.mark.asyncio
    async def test_energy_consumption_daily(self, mock_response):
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(
            return_value=mock_response(
                200,
                [
                    {"day": "30032025", "power": 2.35},
                    {"day": "31032025", "power": 3.64},
                ],
            )
        )
        api = self._make_api(mock_session)
        device = SimpleNamespace(device_id="abc123")

        result = await api.get_energy_consumption(
            device, ConsumptionPeriodType.DAILY, "30032025", "31032025"
        )

        assert result == {"30032025": 2.35, "31032025": 3.64}

    @pytest.mark.asyncio
    async def test_energy_consumption_defaults_to_from_date(self, mock_response):
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(
            return_value=mock_response(200, [{"month": "032025", "power": 55.1}])
        )
        api = self._make_api(mock_session)
        device = SimpleNamespace(device_id="abc123")

        result = await api.get_energy_consumption(
            device, ConsumptionPeriodType.MONTHLY, "032025"
        )

        assert result == {"032025": 55.1}
        called_url = mock_session.get.call_args[0][0]
        assert "devices/abc123" in called_url
        assert "grain=Monthly" in called_url
        assert "startDate=032025" in called_url
        assert "endDate=032025" in called_url
