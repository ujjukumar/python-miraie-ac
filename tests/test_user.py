"""Tests for User"""

import time

from py_miraie_ac.user import User


def test_user_creation():
    user = User(access_token="token", expires_in=3600, refresh_token="refresh", user_id="uid")
    assert user.access_token == "token"
    assert user.refresh_token == "refresh"
    assert user.user_id == "uid"
    assert user.expires_in == 3600


def test_user_expires_at():
    user = User(access_token="token", expires_in=3600, refresh_token="refresh", user_id="uid")
    assert user.expires_at > time.time()
    assert user.expires_at <= time.time() + 3600


def test_user_not_expired():
    user = User(access_token="token", expires_in=3600, refresh_token="refresh", user_id="uid")
    assert user.is_expired() is False


def test_user_expired():
    user = User(access_token="token", expires_in=0, refresh_token="refresh", user_id="uid")
    assert user.is_expired() is True


def test_user_expired_with_buffer():
    user = User(access_token="token", expires_in=30, refresh_token="refresh", user_id="uid")
    # With 60s buffer, a token with 30s lifetime is considered expired
    assert user.is_expired(buffer_seconds=60) is True
    # With 0s buffer, it's not expired yet
    assert user.is_expired(buffer_seconds=0) is False
