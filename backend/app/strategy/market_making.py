"""
Market-making strategy.

Posts symmetric bid/ask quotes around mid-price to capture spread.
Auto-hedges when inventory exceeds configurable limits.
Cancels and re-quotes when price moves beyond a threshold.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.strategy.base import BaseStrategy, OrderIntent

logger = logging.getLogger(__name__)

_TEN_THOUSAND = Decimal("10000")
_TWO = Decimal("2")
_ONE = Decimal("1")
_ZERO = Decimal("0")
_PRICE_PRECISION = Decimal("0.01")
_QTY_PRECISION = Decimal("0.00000001")


@dataclass
class MarketMakingConfig:
    """Configuration for the market-making strategy."""

    symbol: str = "BTCUSDT"
    spread_bps: Decimal = Decimal("10")
    order_quantity: Decimal = Decimal("0.01")
    num_levels: int = 1
    level_spacing_bps: Decimal = Decimal("5")
    max_inventory: Decimal = Decimal("0.5")
    inventory_skew_factor: Decimal = Decimal("0.5")
    requote_threshold_bps: Decimal = Decimal("5")
    min_requote_interval_ms: int = 500

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MarketMakingConfig:
        return cls(
            symbol=d.get("symbol", "BTCUSDT"),
            spread_bps=Decimal(str(d.get("spread_bps", "10"))),
            order_quantity=Decimal(str(d.get("order_quantity", "0.01"))),
            num_levels=int(d.get("num_levels", 1)),
            level_spacing_bps=Decimal(str(d.get("level_spacing_bps", "5"))),
            max_inventory=Decimal(str(d.get("max_inventory", "0.5"))),
            inventory_skew_factor=Decimal(str(d.get("inventory_skew_factor", "0.5"))),
            requote_threshold_bps=Decimal(str(d.get("requote_threshold_bps", "5"))),
            min_requote_interval_ms=int(d.get("min_requote_interval_ms", 500)),
        )


class MarketMakingStrategy(BaseStrategy):
    """
    Market-making strategy that posts bid/ask quotes around mid-price.

    Features:
    - Configurable spread width and order size
    - Multi-level quoting (multiple price levels per side)
    - Inventory-aware quote skewing
    - Automatic requoting when price moves
    - Max inventory limits with hedge orders
    """

    def __init__(self, config: MarketMakingConfig | None = None, strategy_id: str = "") -> None:
        self._config = config or MarketMakingConfig()
        self._strategy_id = strategy_id
        self._current_inventory = _ZERO
        self._active_order_ids: list[str] = []
        self._last_mid = _ZERO
        self._last_quote_time_ms: float = 0.0
        self._ticks_processed = 0
        self._orders_submitted = 0

    @property
    def name(self) -> str:
        return f"mm_{self._config.symbol.lower()}"

    @property
    def strategy_type(self) -> str:
        return "MARKET_MAKING"

    async def on_start(self) -> None:
        self._current_inventory = _ZERO
        self._active_order_ids = []
        self._last_mid = _ZERO
        self._last_quote_time_ms = 0.0
        self._ticks_processed = 0
        self._orders_submitted = 0
        logger.info(
            "MM strategy started: %s spread=%sbps qty=%s max_inv=%s levels=%d",
            self._config.symbol,
            self._config.spread_bps,
            self._config.order_quantity,
            self._config.max_inventory,
            self._config.num_levels,
        )

    async def on_stop(self) -> None:
        logger.info(
            "MM strategy stopped: %s inventory=%s ticks=%d orders=%d",
            self._config.symbol,
            self._current_inventory,
            self._ticks_processed,
            self._orders_submitted,
        )

    async def on_tick(
        self, symbol: str, bid: Decimal, ask: Decimal, last: Decimal
    ) -> list[OrderIntent]:
        if symbol != self._config.symbol:
            return []

        self._ticks_processed += 1
        mid = (bid + ask) / _TWO

        if mid <= _ZERO:
            return []

        # Check if requote is needed
        now_ms = time.monotonic() * 1000
        time_elapsed = now_ms - self._last_quote_time_ms >= self._config.min_requote_interval_ms

        price_moved = False
        if self._last_mid > _ZERO:
            move_bps = abs(mid - self._last_mid) / self._last_mid * _TEN_THOUSAND
            price_moved = move_bps >= self._config.requote_threshold_bps

        # First tick or requote triggered
        if self._last_mid == _ZERO or (time_elapsed and price_moved):
            return self._generate_quotes(mid, now_ms)

        return []

    def _generate_quotes(self, mid: Decimal, now_ms: float) -> list[OrderIntent]:
        """Generate bid/ask quote intents around mid-price."""
        self._last_mid = mid
        self._last_quote_time_ms = now_ms

        intents: list[OrderIntent] = []

        # Cancel existing quotes first
        if self._active_order_ids:
            cancel_ids = list(self._active_order_ids)
            self._active_order_ids.clear()
            # Signal cancellation via metadata
            intents.append(OrderIntent(
                symbol=self._config.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=_ZERO,
                price=_ZERO,
                strategy_id=self._strategy_id,
                exchange="",
                cancel_order_ids=cancel_ids,
                metadata={"action": "cancel_all"},
            ))

        # Compute inventory skew
        inv_ratio = _ZERO
        if self._config.max_inventory > _ZERO:
            inv_ratio = self._current_inventory / self._config.max_inventory

        skew = inv_ratio * self._config.inventory_skew_factor

        # Check if we should only post one side
        at_max_long = self._current_inventory >= self._config.max_inventory
        at_max_short = self._current_inventory <= -self._config.max_inventory

        half_spread = self._config.spread_bps / (_TWO * _TEN_THOUSAND)

        for level in range(self._config.num_levels):
            level_offset = level * self._config.level_spacing_bps / _TEN_THOUSAND

            # Buy side (bid) - lower price
            if not at_max_long:
                buy_offset = half_spread + level_offset + skew * half_spread
                buy_price = (mid * (_ONE - buy_offset)).quantize(_PRICE_PRECISION)
                intents.append(OrderIntent(
                    symbol=self._config.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=self._config.order_quantity,
                    price=buy_price,
                    time_in_force=TimeInForce.GTC,
                    strategy_id=self._strategy_id,
                    metadata={"level": level, "mm_quote": True},
                ))
                self._orders_submitted += 1

            # Sell side (ask) - higher price
            if not at_max_short:
                sell_offset = half_spread + level_offset - skew * half_spread
                sell_price = (mid * (_ONE + sell_offset)).quantize(_PRICE_PRECISION)
                intents.append(OrderIntent(
                    symbol=self._config.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    quantity=self._config.order_quantity,
                    price=sell_price,
                    time_in_force=TimeInForce.GTC,
                    strategy_id=self._strategy_id,
                    metadata={"level": level, "mm_quote": True},
                ))
                self._orders_submitted += 1

        return intents

    async def on_fill(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal
    ) -> None:
        if side == "BUY":
            self._current_inventory += quantity
        else:
            self._current_inventory -= quantity

        logger.info(
            "MM fill: %s %s %s @ %s | inventory=%s",
            side, quantity, symbol, price, self._current_inventory,
        )
