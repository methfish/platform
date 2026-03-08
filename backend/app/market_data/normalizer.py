"""
Market data normalizer - converts raw exchange data to internal format.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.exchange.models import NormalizedTicker


def normalize_ticker_from_raw(
    symbol: str,
    exchange: str,
    bid: float | str | Decimal,
    ask: float | str | Decimal,
    last: float | str | Decimal,
    volume: float | str | Decimal = 0,
) -> NormalizedTicker:
    """Create a NormalizedTicker from raw values."""
    return NormalizedTicker(
        symbol=symbol.upper(),
        exchange=exchange,
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        last=Decimal(str(last)),
        volume_24h=Decimal(str(volume)),
        timestamp=datetime.now(timezone.utc),
    )
