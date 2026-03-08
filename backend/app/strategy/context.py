"""
Strategy context - what a strategy sees and can interact with.
"""

from __future__ import annotations

from decimal import Decimal

from app.exchange.models import NormalizedTicker
from app.models.position import Position


class StrategyContext:
    """
    Read-only context provided to strategies.

    Strategies cannot directly access the exchange or database.
    They receive market data and position information through this context.
    """

    def __init__(self) -> None:
        self._tickers: dict[str, NormalizedTicker] = {}
        self._positions: dict[str, Position] = {}

    def update_ticker(self, ticker: NormalizedTicker) -> None:
        self._tickers[ticker.symbol] = ticker

    def update_position(self, symbol: str, position: Position) -> None:
        self._positions[symbol] = position

    def get_last_price(self, symbol: str) -> Decimal | None:
        ticker = self._tickers.get(symbol)
        return ticker.last if ticker else None

    def get_bid(self, symbol: str) -> Decimal | None:
        ticker = self._tickers.get(symbol)
        return ticker.bid if ticker else None

    def get_ask(self, symbol: str) -> Decimal | None:
        ticker = self._tickers.get(symbol)
        return ticker.ask if ticker else None

    def get_position_quantity(self, symbol: str) -> Decimal:
        pos = self._positions.get(symbol)
        if not pos:
            return Decimal("0")
        return pos.quantity if pos.side == "LONG" else -pos.quantity

    def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)
