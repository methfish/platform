"""
Binance API authentication - HMAC-SHA256 request signing.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode


class BinanceAuth:
    """Handles Binance API key authentication and request signing."""

    def __init__(self, api_key: str, api_secret: str):
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")

    @property
    def api_key(self) -> str:
        return self._api_key

    def sign(self, params: dict) -> dict:
        """Add timestamp and signature to request params."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret,
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key}

    def __repr__(self) -> str:
        return f"<BinanceAuth key={self._api_key[:8]}...>"
