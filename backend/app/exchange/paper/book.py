"""
Simulated order book state for paper trading.

Maintains open orders and current market prices for the paper adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from app.exchange.paper.matching import PaperOrderState


@dataclass
class MarketPrice:
    """Current market price for a symbol."""
    symbol: str
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    last: Decimal = Decimal("0")
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperOrderBook:
    """
    In-memory order book for paper trading.

    Stores open orders and current prices. Thread-safe via asyncio
    (single event loop, no concurrent modification).
    """

    def __init__(self) -> None:
        self._orders: dict[str, PaperOrderState] = {}  # exchange_order_id -> order
        self._prices: dict[str, MarketPrice] = {}  # symbol -> price
        self._balances: dict[str, Decimal] = {
            "USDT": Decimal("100000"),  # Default paper balance
            "BTC": Decimal("0"),
            "ETH": Decimal("0"),
            "SOL": Decimal("0"),
        }

    def add_order(self, order: PaperOrderState) -> None:
        self._orders[order.exchange_order_id] = order

    def remove_order(self, exchange_order_id: str) -> PaperOrderState | None:
        return self._orders.pop(exchange_order_id, None)

    def get_order(self, exchange_order_id: str) -> PaperOrderState | None:
        return self._orders.get(exchange_order_id)

    def get_order_by_client_id(self, client_order_id: str) -> PaperOrderState | None:
        for order in self._orders.values():
            if order.client_order_id == client_order_id:
                return order
        return None

    def get_open_orders(self, symbol: str | None = None) -> list[PaperOrderState]:
        orders = [o for o in self._orders.values() if o.status in ("NEW", "PARTIALLY_FILLED")]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def update_price(self, symbol: str, bid: Decimal, ask: Decimal, last: Decimal) -> None:
        self._prices[symbol] = MarketPrice(
            symbol=symbol, bid=bid, ask=ask, last=last,
            updated_at=datetime.now(timezone.utc),
        )

    def get_price(self, symbol: str) -> MarketPrice | None:
        return self._prices.get(symbol)

    def get_balance(self, asset: str) -> Decimal:
        return self._balances.get(asset, Decimal("0"))

    def update_balance(self, asset: str, delta: Decimal) -> None:
        current = self._balances.get(asset, Decimal("0"))
        self._balances[asset] = current + delta

    def set_balance(self, asset: str, amount: Decimal) -> None:
        self._balances[asset] = amount

    def get_all_balances(self) -> dict[str, Decimal]:
        return dict(self._balances)
