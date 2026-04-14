"""Represents a user"""

import time


class User:
    """The User class"""

    access_token: str
    expires_in: int
    refresh_token: str
    user_id: str
    _created_at: float

    def __init__(
        self,
        access_token: str,
        expires_in: int,
        refresh_token: str,
        user_id: str,
    ):
        self.access_token = access_token
        self.expires_in = expires_in
        self.refresh_token = refresh_token
        self.user_id = user_id
        self._created_at = time.time()

    @property
    def expires_at(self) -> float:
        """Returns the timestamp when the token expires"""
        return self._created_at + self.expires_in

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Returns True if the token is expired or about to expire within the buffer period"""
        return time.time() >= (self.expires_at - buffer_seconds)
