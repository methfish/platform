"""Order execution service - places orders and manages their lifecycle."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.exchange.binance.client import BinanceRestClient
from app.exchange.paper.trading_engine import PaperTradingEngine, SimpleBalanceTracker
from app.models.order import Order, OrderFill
from app.models.position import Position
from app.config import Settings
from app.core.enums import TradingMode, OrderStatus

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Executes orders against Binance (live) or paper engine."""

    def __init__(
        self,
        binance_client: Optional[BinanceRestClient] = None,
        settings: Optional[Settings] = None,
    ):
        self.binance_client = binance_client
        self.settings = settings
        self.paper_engine = PaperTradingEngine()
        self.paper_balance = SimpleBalanceTracker()

    async def place_order(
        self,
        session: AsyncSession,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        trading_mode: str = "PAPER",
    ) -> Order:
        """
        Place an order (paper or live).

        Args:
            session: Database session
            symbol: Trading symbol (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: MARKET or LIMIT
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            trading_mode: PAPER or LIVE

        Returns:
            Order object

        Raises:
            ValueError: If order parameters are invalid
        """
        # Validate
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("MARKET", "LIMIT"):
            raise ValueError(f"Invalid order_type: {order_type}")
        if order_type == "LIMIT" and not price:
            raise ValueError("LIMIT orders require a price")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        # Create order record
        order = Order(
            client_order_id=f"PENSY-{uuid.uuid4().hex[:12].upper()}",
            symbol=symbol.upper(),
            side=side.upper(),
            order_type=order_type.upper(),
            quantity=quantity,
            price=price,
            status="PENDING",
            trading_mode=trading_mode,
            exchange="binance",
        )

        session.add(order)
        await session.flush()  # Get the ID

        logger.info(
            f"Created {trading_mode} order {order.client_order_id}: "
            f"{side} {quantity} {symbol} @ {price} ({order_type})"
        )

        # Execute based on mode
        if trading_mode == "PAPER":
            await self._execute_paper_order(session, order)
        else:
            await self._execute_live_order(session, order)

        await session.commit()
        return order

    async def _execute_paper_order(
        self,
        session: AsyncSession,
        order: Order,
    ) -> None:
        """Execute order in paper trading mode."""
        # Get current price (placeholder - in real system would fetch from market data)
        current_price = order.price if order.price else Decimal("50000")  # Fallback

        # For LIMIT orders, add to pending
        if order.order_type == "LIMIT":
            fills = await self.paper_engine.execute_order(order, current_price)
        else:
            # MARKET orders execute immediately
            fills = await self.paper_engine.execute_order(order, current_price)

        # Create fills in database
        if fills:
            total_filled_qty = sum(f.quantity for f in fills)
            total_cost = sum(f.quantity * f.price + f.commission for f in fills)
            avg_price = total_cost / total_filled_qty if total_filled_qty > 0 else Decimal("0")

            order.status = OrderStatus.FILLED.value
            order.filled_quantity = total_filled_qty
            order.avg_fill_price = avg_price
            order.filled_at = datetime.now(timezone.utc)

            for fill in fills:
                session.add(fill)

            # Update balance
            self.paper_balance.apply_fill(
                order.id,
                order.side,
                total_filled_qty,
                avg_price,
                Decimal("0"),  # Commission already in fills
            )

            logger.info(
                f"Paper order filled: {order.client_order_id} "
                f"{total_filled_qty} @ {avg_price:.4f}"
            )
        else:
            # LIMIT order pending
            order.status = OrderStatus.PENDING.value

    async def _execute_live_order(
        self,
        session: AsyncSession,
        order: Order,
    ) -> None:
        """Execute order against live Binance."""
        if not self.binance_client:
            order.status = OrderStatus.FAILED.value
            order.reject_reason = "Binance client not configured"
            logger.error("Cannot execute live order: Binance client not available")
            return

        try:
            # Place order on Binance
            response = await self.binance_client.place_order(
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price if order.price else None,
                client_order_id=order.client_order_id,
            )

            # Update order with exchange response
            order.exchange_order_id = str(response.get("orderId"))
            order.status = OrderStatus.FILLED.value if response.get("status") == "FILLED" else OrderStatus.PENDING

            if response.get("fills"):
                for fill_data in response["fills"]:
                    fill = OrderFill(
                        order_id=order.id,
                        exchange_fill_id=fill_data.get("tradeId"),
                        quantity=Decimal(str(fill_data["qty"])),
                        price=Decimal(str(fill_data["price"])),
                        commission=Decimal(str(fill_data.get("commission", 0))),
                        commission_asset=fill_data.get("commissionAsset"),
                        fill_time=datetime.fromtimestamp(
                            fill_data["time"] / 1000, tz=timezone.utc
                        ),
                    )
                    session.add(fill)

                order.filled_quantity = sum(
                    Decimal(str(f["qty"])) for f in response["fills"]
                )
                order.avg_fill_price = Decimal(str(response.get("executedQty", 0))) * Decimal(
                    str(response.get("cummulativeQuoteQty", 0))
                ) / (
                    order.filled_quantity if order.filled_quantity > 0 else Decimal("1")
                )

            logger.info(
                f"Live order placed: {order.client_order_id} "
                f"exchange_id={order.exchange_order_id}"
            )

        except Exception as e:
            order.status = OrderStatus.FAILED.value
            order.reject_reason = str(e)
            logger.error(f"Failed to place live order {order.client_order_id}: {e}")

    async def cancel_order(
        self,
        session: AsyncSession,
        order: Order,
    ) -> bool:
        """Cancel an order."""
        if order.status not in ("PENDING",):
            logger.warning(f"Cannot cancel {order.status} order {order.client_order_id}")
            return False

        if order.trading_mode == "PAPER":
            success = await self.paper_engine.cancel_order(order)
        else:
            # Cancel on Binance
            try:
                await self.binance_client.cancel_order(
                    symbol=order.symbol,
                    order_id=int(order.exchange_order_id) if order.exchange_order_id else None,
                    client_order_id=order.client_order_id,
                )
                success = True
            except Exception as e:
                logger.error(f"Failed to cancel order on Binance: {e}")
                return False

        if success:
            order.status = OrderStatus.CANCELLED.value
            order.cancelled_at = datetime.now(timezone.utc)
            logger.info(f"Cancelled order: {order.client_order_id}")

        return success
