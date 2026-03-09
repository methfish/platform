"""
Paper Trading Exchange Adapter.

Implements the ExchangeAdapter ABC with simulated execution.
This adapter is the DEFAULT for the Pensy platform. All order lifecycle,
risk checks, and position tracking work identically whether using this
adapter or a live exchange adapter.

Fill simulation:
- Market orders fill immediately at last price + slippage
- Limit orders fill when market price crosses the limit
- Configurable commission rate
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncIterator, Optional
from uuid import uuid4

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.exchange.base import ExchangeAdapter
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
from app.exchange.paper.book import PaperOrderBook
from app.exchange.paper.matching import MatchingEngine, PaperOrderState

logger = logging.getLogger(__name__)


class PaperExchangeAdapter(ExchangeAdapter):
    """
    Paper trading adapter. Simulates exchange behavior in-memory.

    This is a first-class adapter, not a mock. The OMS treats it
    identically to a live exchange adapter.
    """

    def __init__(
        self,
        initial_balances: dict[str, Decimal] | None = None,
        commission_rate: Decimal = Decimal("0.001"),
    ):
        self._book = PaperOrderBook()
        self._matching = MatchingEngine(commission_rate=commission_rate)
        self._connected = False
        self._user_data_queue: asyncio.Queue[UserDataEvent] = asyncio.Queue()
        self._ticker_queues: dict[str, asyncio.Queue[NormalizedTicker]] = {}

        if initial_balances:
            for asset, amount in initial_balances.items():
                self._book.set_balance(asset, amount)

    # --- Lifecycle ---

    async def connect(self) -> None:
        self._connected = True
        logger.info("Paper exchange adapter connected")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper exchange adapter disconnected")

    async def ping(self) -> bool:
        return self._connected

    async def get_exchange_info(self) -> ExchangeInfo:
        return ExchangeInfo(
            exchange_name="paper",
            supports_spot=True,
            supports_futures=False,
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=False,
            supports_post_only=False,
            max_orders_per_second=100,
        )

    async def get_server_time(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    async def get_symbols(self) -> list[str]:
        crypto = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"]
        forex = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP"]
        stocks = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "SPY", "QQQ", "BRK.B"]
        return crypto + forex + stocks

    # --- Account ---

    async def get_balances(self) -> list[ExchangeBalance]:
        balances = []
        for asset, total in self._book.get_all_balances().items():
            if total > 0:
                balances.append(ExchangeBalance(
                    asset=asset,
                    free=total,
                    locked=Decimal("0"),
                    total=total,
                ))
        return balances

    async def get_positions(self) -> list[ExchangePosition]:
        # Spot paper trading: positions derived from balances
        positions = []
        for asset, qty in self._book.get_all_balances().items():
            if asset in ("USDT", "USDC", "BUSD"):
                continue
            if qty > 0:
                positions.append(ExchangePosition(
                    symbol=f"{asset}USDT",
                    side="LONG",
                    quantity=qty,
                ))
        return positions

    # --- Orders ---

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExchangeOrder]:
        paper_orders = self._book.get_open_orders(symbol)
        return [self._to_exchange_order(o) for o in paper_orders]

    async def get_order_status(
        self,
        symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        order = None
        if exchange_order_id:
            order = self._book.get_order(exchange_order_id)
        elif client_order_id:
            order = self._book.get_order_by_client_id(client_order_id)

        if not order:
            raise ValueError(f"Order not found: {exchange_order_id or client_order_id}")

        return self._to_exchange_order(order)

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
        exchange_order_id = f"PAPER-{uuid4().hex[:16].upper()}"
        coid = client_order_id or str(uuid4())

        paper_order = PaperOrderState(
            exchange_order_id=exchange_order_id,
            client_order_id=coid,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="NEW",
            created_at=datetime.now(timezone.utc),
        )

        self._book.add_order(paper_order)

        logger.info(
            f"Paper order placed: {exchange_order_id} {symbol} {side.value} "
            f"{order_type.value} qty={quantity} price={price}"
        )

        # Try immediate fill for market orders
        if order_type == OrderType.MARKET:
            market_price = self._book.get_price(symbol)
            if market_price and market_price.last > 0:
                fill = self._matching.try_fill_market(
                    paper_order, market_price.last, market_price.bid, market_price.ask
                )
                if fill:
                    paper_order.filled_quantity = fill.quantity
                    paper_order.status = "FILLED"
                    self._apply_fill_to_balances(paper_order, fill.price, fill.quantity, fill.commission)
                    self._book.remove_order(exchange_order_id)

                    # Emit user data event
                    await self._user_data_queue.put(UserDataEvent(
                        event_type="FILL",
                        exchange_order_id=exchange_order_id,
                        client_order_id=coid,
                        symbol=symbol,
                        side=side.value,
                        status="FILLED",
                        filled_quantity=fill.quantity,
                        fill_price=fill.price,
                        commission=fill.commission,
                        commission_asset=fill.commission_asset,
                        timestamp=fill.fill_time,
                    ))

                    return ExchangeOrderResult(
                        success=True,
                        exchange_order_id=exchange_order_id,
                        client_order_id=coid,
                        status="FILLED",
                    )
            else:
                # No price available, reject market order
                paper_order.status = "REJECTED"
                self._book.remove_order(exchange_order_id)
                return ExchangeOrderResult(
                    success=False,
                    exchange_order_id=exchange_order_id,
                    client_order_id=coid,
                    status="REJECTED",
                    message="No market price available for paper fill",
                )

        return ExchangeOrderResult(
            success=True,
            exchange_order_id=exchange_order_id,
            client_order_id=coid,
            status="NEW",
        )

    async def cancel_order(
        self,
        symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeCancelResult:
        order = None
        oid = exchange_order_id or ""

        if exchange_order_id:
            order = self._book.get_order(exchange_order_id)
        elif client_order_id:
            order = self._book.get_order_by_client_id(client_order_id)
            if order:
                oid = order.exchange_order_id

        if not order:
            return ExchangeCancelResult(
                success=False,
                exchange_order_id=oid,
                message="Order not found",
            )

        order.status = "CANCELLED"
        self._book.remove_order(order.exchange_order_id)

        logger.info(f"Paper order cancelled: {order.exchange_order_id}")

        return ExchangeCancelResult(
            success=True,
            exchange_order_id=order.exchange_order_id,
            client_order_id=order.client_order_id,
        )

    # --- Market Data ---

    def update_market_price(
        self, symbol: str, bid: Decimal, ask: Decimal, last: Decimal
    ) -> None:
        """Update market prices and check for limit order fills."""
        self._book.update_price(symbol, bid, ask, last)
        # Check pending limit orders
        asyncio.get_event_loop().create_task(self._check_limit_fills(symbol, bid, ask))

    async def _check_limit_fills(self, symbol: str, bid: Decimal, ask: Decimal) -> None:
        """Check if any limit orders should fill at current prices."""
        open_orders = self._book.get_open_orders(symbol)
        for order in open_orders:
            if order.order_type != OrderType.LIMIT:
                continue

            fill = self._matching.try_fill_limit(order, bid, ask)
            if fill:
                order.filled_quantity = order.quantity
                order.status = "FILLED"
                self._apply_fill_to_balances(order, fill.price, fill.quantity, fill.commission)
                self._book.remove_order(order.exchange_order_id)

                await self._user_data_queue.put(UserDataEvent(
                    event_type="FILL",
                    exchange_order_id=order.exchange_order_id,
                    client_order_id=order.client_order_id,
                    symbol=symbol,
                    side=order.side.value,
                    status="FILLED",
                    filled_quantity=fill.quantity,
                    fill_price=fill.price,
                    commission=fill.commission,
                    commission_asset=fill.commission_asset,
                    timestamp=fill.fill_time,
                ))

    async def subscribe_ticker(self, symbols: list[str]) -> AsyncIterator[NormalizedTicker]:
        """Yield tickers as prices are updated externally."""
        queue: asyncio.Queue[NormalizedTicker] = asyncio.Queue()
        for symbol in symbols:
            self._ticker_queues[symbol] = queue

        try:
            while True:
                ticker = await queue.get()
                yield ticker
        finally:
            for symbol in symbols:
                self._ticker_queues.pop(symbol, None)

    async def subscribe_user_data(self) -> AsyncIterator[UserDataEvent]:
        """Yield user data events (fills, order updates)."""
        while True:
            event = await self._user_data_queue.get()
            yield event

    # --- Helpers ---

    def _apply_fill_to_balances(
        self,
        order: PaperOrderState,
        fill_price: Decimal,
        fill_qty: Decimal,
        commission: Decimal,
    ) -> None:
        """Update paper balances after a fill."""
        # Parse symbol into base/quote
        # Forex: EURUSD -> base=EUR quote=USD; Stocks: AAPL -> base=AAPL quote=USD
        quote = "USD"
        base = order.symbol
        for q in ["USDT", "USDC", "BUSD", "USD", "EUR", "GBP", "JPY"]:
            if order.symbol.endswith(q) and order.symbol != q:
                base = order.symbol[: -len(q)]
                quote = q
                break

        notional = fill_qty * fill_price

        if order.side == OrderSide.BUY:
            self._book.update_balance(quote, -notional - commission)
            self._book.update_balance(base, fill_qty)
        else:
            self._book.update_balance(base, -fill_qty)
            self._book.update_balance(quote, notional - commission)

    def _to_exchange_order(self, order: PaperOrderState) -> ExchangeOrder:
        avg_price = None
        if order.filled_quantity > 0 and order.price:
            avg_price = order.price  # Simplified for paper

        return ExchangeOrder(
            exchange_order_id=order.exchange_order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=order.filled_quantity,
            avg_fill_price=avg_price,
            status=order.status,
            created_at=order.created_at,
        )

    @property
    def exchange_name(self) -> str:
        return "paper"

    @property
    def is_paper(self) -> bool:
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected
