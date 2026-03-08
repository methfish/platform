"""
Example TWAP (Time-Weighted Average Price) strategy.

Splits a large order into smaller slices executed at regular intervals.
This is a reference implementation showing how strategies interact
with the platform. The platform architecture matters more than alpha.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.strategy.base import BaseStrategy, OrderIntent

logger = logging.getLogger(__name__)


@dataclass
class TWAPConfig:
    symbol: str = "BTCUSDT"
    side: OrderSide = OrderSide.BUY
    total_quantity: Decimal = Decimal("1.0")
    num_slices: int = 10
    interval_seconds: float = 60.0
    use_limit: bool = True
    limit_offset_bps: Decimal = Decimal("0.001")  # 10 bps from market


class TWAPStrategy(BaseStrategy):
    """
    Simple TWAP strategy.

    Splits total_quantity into num_slices and submits one slice
    per interval_seconds. Uses limit orders offset from current price.
    """

    def __init__(self, config: TWAPConfig | None = None):
        self._config = config or TWAPConfig()
        self._slices_sent = 0
        self._last_slice_time: datetime | None = None
        self._filled_quantity = Decimal("0")
        self._active = False

    @property
    def name(self) -> str:
        return "twap_example"

    @property
    def strategy_type(self) -> str:
        return "TWAP"

    async def on_start(self) -> None:
        self._active = True
        self._slices_sent = 0
        self._last_slice_time = None
        self._filled_quantity = Decimal("0")
        logger.info(
            f"TWAP started: {self._config.side.value} "
            f"{self._config.total_quantity} {self._config.symbol} "
            f"in {self._config.num_slices} slices"
        )

    async def on_stop(self) -> None:
        self._active = False
        logger.info(
            f"TWAP stopped: {self._slices_sent}/{self._config.num_slices} "
            f"slices sent, {self._filled_quantity} filled"
        )

    async def on_tick(
        self, symbol: str, bid: Decimal, ask: Decimal, last: Decimal
    ) -> list[OrderIntent]:
        if not self._active:
            return []

        if symbol != self._config.symbol:
            return []

        if self._slices_sent >= self._config.num_slices:
            return []

        now = datetime.now(timezone.utc)
        if self._last_slice_time:
            elapsed = (now - self._last_slice_time).total_seconds()
            if elapsed < self._config.interval_seconds:
                return []

        # Calculate slice quantity
        remaining = self._config.total_quantity - self._filled_quantity
        slices_left = self._config.num_slices - self._slices_sent
        slice_qty = (remaining / slices_left).quantize(Decimal("0.00000001"))

        if slice_qty <= 0:
            return []

        # Calculate limit price
        price = None
        order_type = OrderType.MARKET
        if self._config.use_limit:
            order_type = OrderType.LIMIT
            if self._config.side == OrderSide.BUY:
                price = ask * (Decimal("1") + self._config.limit_offset_bps)
            else:
                price = bid * (Decimal("1") - self._config.limit_offset_bps)
            price = price.quantize(Decimal("0.01"))

        self._slices_sent += 1
        self._last_slice_time = now

        logger.info(
            f"TWAP slice {self._slices_sent}/{self._config.num_slices}: "
            f"{self._config.side.value} {slice_qty} {symbol} @ {price}"
        )

        return [OrderIntent(
            symbol=symbol,
            side=self._config.side,
            order_type=order_type,
            quantity=slice_qty,
            price=price,
            time_in_force=TimeInForce.GTC,
            metadata={"slice": self._slices_sent, "total_slices": self._config.num_slices},
        )]

    async def on_fill(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal
    ) -> None:
        self._filled_quantity += quantity
        logger.info(
            f"TWAP fill: {quantity} @ {price}, "
            f"total filled: {self._filled_quantity}/{self._config.total_quantity}"
        )
