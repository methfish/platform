"""
Abstract Exchange Adapter - the foundational abstraction of the Pensy platform.

Every exchange implementation (Binance spot, Binance futures, paper trading)
implements this interface identically. The OMS, risk engine, and reconciliation
service depend ONLY on this interface, never on concrete exchange implementations.

Adding a new exchange = implementing this ABC once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import AsyncIterator, Optional

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.exchange.models import (
    ExchangeBalance,
    ExchangeCancelResult,
    ExchangeInfo,
    ExchangeOrder,
    ExchangeOrderResult,
    ExchangePosition,
    NormalizedTicker,
    UserDataEvent,
)


class ExchangeAdapter(ABC):
    """
    Abstract exchange adapter contract.

    All methods are async. All financial values use Decimal.
    All responses use normalized models from exchange.models.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to the exchange (auth, websockets, etc.)."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connections."""
        ...

    @abstractmethod
    async def ping(self) -> bool:
        """Check if the exchange is reachable."""
        ...

    @abstractmethod
    async def get_exchange_info(self) -> ExchangeInfo:
        """Get exchange capabilities and metadata."""
        ...

    @abstractmethod
    async def get_server_time(self) -> int:
        """Get exchange server time in milliseconds."""
        ...

    @abstractmethod
    async def get_symbols(self) -> list[str]:
        """Get list of tradable symbols."""
        ...

    @abstractmethod
    async def get_balances(self) -> list[ExchangeBalance]:
        """Get account balances."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[ExchangePosition]:
        """Get current positions (futures). Spot adapters return balances as positions."""
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExchangeOrder]:
        """List all open orders, optionally filtered by symbol."""
        ...

    @abstractmethod
    async def get_order_status(
        self,
        symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        """Query current status of a single order."""
        ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        **kwargs,
    ) -> ExchangeOrderResult:
        """
        Submit an order to the exchange.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: MARKET, LIMIT, etc.
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            client_order_id: Idempotency key
            time_in_force: GTC, IOC, FOK

        Returns:
            ExchangeOrderResult with exchange ack
        """
        ...

    @abstractmethod
    async def cancel_order(
        self,
        symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeCancelResult:
        """Cancel an open order."""
        ...

    @abstractmethod
    async def subscribe_ticker(
        self, symbols: list[str]
    ) -> AsyncIterator[NormalizedTicker]:
        """
        Subscribe to real-time ticker updates.
        Yields normalized tickers. Auto-reconnects on disconnect.
        """
        ...

    @abstractmethod
    async def subscribe_user_data(self) -> AsyncIterator[UserDataEvent]:
        """
        Subscribe to user data stream (order updates, fills).
        Used for real-time order status and fill notifications.
        """
        ...

    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """Canonical exchange name (e.g., 'binance_spot', 'paper')."""
        ...

    @property
    @abstractmethod
    def is_paper(self) -> bool:
        """Whether this is a paper/simulated adapter."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the adapter is currently connected."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} exchange={self.exchange_name} paper={self.is_paper}>"
