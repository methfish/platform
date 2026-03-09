"""
Fill model — simulates realistic order matching.

Handles:
  - Market orders: immediate taker fill at worst side of spread + slippage
  - Limit orders: queue position tracking and partial fills
  - Latency: orders are delayed before reaching the book
  - Maker/taker fee assignment

Simplifying assumptions:
  A5. Queue position: order joins behind (bar_volume × queue_behind_pct) shares.
      This approximates your position in the FIFO queue at that price level.
  A6. Each bar, volume at the limit price drains queue_ahead. When queue_ahead
      reaches zero, your order starts filling.
  A7. We only fill if the bar's price range trades THROUGH your limit —
      touching the limit is not enough (conservative assumption).
  A8. Market orders always fill completely (no partial market fills in
      liquid forex/stock markets at our size).
  A9. Volume available for limit fills = bar.volume × price_proximity_factor.
      If the limit is near the bar's extreme, less volume is available.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from app.simulator.types import (
    FillType,
    OrderSide,
    SimBar,
    SimFill,
    SimOrder,
    SimOrderStatus,
    SimOrderType,
    SimulatorConfig,
)

logger = logging.getLogger("pensy.simulator.fill_model")


class FillModel:
    """
    Determines when and how orders fill against incoming market data.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def try_fill_market(
        self,
        order: SimOrder,
        bar: SimBar,
    ) -> Optional[SimFill]:
        """
        Attempt to fill a market order.

        Market orders are always taker. They fill at the worse side of
        the spread plus slippage (assumption A8: full fill).

        Returns None if bar has no valid price (e.g., volume=0).
        """
        if order.order_type != SimOrderType.MARKET:
            return None

        mid = bar.typical
        if mid <= 0:
            return None

        half_spread = self._config.half_spread(mid)
        slip = self._config.slippage(mid)

        if order.side == OrderSide.BUY:
            # Buy at ask + slippage
            fill_price = mid + half_spread + slip
        else:
            # Sell at bid - slippage
            fill_price = mid - half_spread - slip
            fill_price = max(fill_price, Decimal("0.00001"))

        # P3: Volume guard — cap market fill at 10% of bar volume
        max_fill = bar.volume * Decimal("0.10")
        fill_qty = min(order.remaining_qty, max_fill) if max_fill > 0 else order.remaining_qty
        if fill_qty < self._config.min_fill_qty:
            logger.warning(
                "Market order %s rejected: fill_qty %s < min %s (bar vol=%s)",
                order.order_id, fill_qty, self._config.min_fill_qty, bar.volume,
            )
            return None
        commission = fill_qty * fill_price * self._config.taker_fee_rate

        is_full = fill_qty >= order.remaining_qty
        return SimFill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            fill_type=FillType.FULL if is_full else FillType.PARTIAL,
            quantity=fill_qty,
            price=fill_price,
            commission=commission,
            is_maker=False,
            timestamp=bar.timestamp,
        )

    def try_fill_limit(
        self,
        order: SimOrder,
        bar: SimBar,
    ) -> Optional[SimFill]:
        """
        Attempt to fill (or partially fill) a resting limit order.

        Steps:
          1. Check if the bar's price range trades through the limit.
          2. Drain queue_ahead based on bar volume at the price level.
          3. If queue is drained, fill up to available volume.

        Returns None if no fill occurs this bar.
        """
        if order.order_type != SimOrderType.LIMIT:
            return None
        if order.price is None:
            return None
        if order.is_terminal:
            return None

        limit_price = order.price

        # Check if price trades through our limit (assumption A7)
        if not self._price_trades_through(order.side, limit_price, bar):
            return None

        # Volume available at this price level (assumption A9)
        available_volume = self._volume_at_level(limit_price, bar)

        if available_volume <= 0:
            return None

        # Drain queue ahead (assumption A5, A6)
        drain = available_volume * self._config.fill_rate_pct
        old_queue = order.queue_ahead
        order.queue_ahead = max(Decimal("0"), order.queue_ahead - drain)

        if order.queue_ahead > 0:
            # Still waiting in queue
            logger.debug(
                "Order %s: queue drained %.0f → %.0f (vol=%.0f)",
                order.order_id, old_queue, order.queue_ahead, available_volume,
            )
            return None

        # Queue is empty — we can fill
        # Volume left after draining queue = available_volume - what was used for queue
        queue_consumed = old_queue  # We drained this much from available
        remaining_volume = max(Decimal("0"), available_volume - queue_consumed)

        if remaining_volume < self._config.min_fill_qty:
            return None

        fill_qty = min(order.remaining_qty, remaining_volume)
        if fill_qty < self._config.min_fill_qty:
            return None

        # Limit orders fill at the limit price (price improvement possible
        # but we use limit price — conservative for the strategy)
        fill_price = limit_price
        commission = fill_qty * fill_price * self._config.maker_fee_rate

        is_full = (fill_qty >= order.remaining_qty)

        return SimFill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            fill_type=FillType.FULL if is_full else FillType.PARTIAL,
            quantity=fill_qty,
            price=fill_price,
            commission=commission,
            is_maker=True,
            timestamp=bar.timestamp,
        )

    def assign_queue_position(
        self,
        order: SimOrder,
        bar: SimBar,
    ) -> None:
        """
        Assign initial queue position for a new limit order.

        The order joins behind queue_behind_pct of the bar's volume
        at this price level (assumption A5).
        """
        if order.order_type != SimOrderType.LIMIT:
            return

        vol_at_level = self._volume_at_level(order.price, bar)
        order.queue_ahead = vol_at_level * self._config.queue_behind_pct
        logger.debug(
            "Order %s: assigned queue position %.0f (vol_at_level=%.0f)",
            order.order_id, order.queue_ahead, vol_at_level,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _price_trades_through(
        self,
        side: OrderSide,
        limit_price: Decimal,
        bar: SimBar,
    ) -> bool:
        """
        Check if the bar's price range trades through the limit.

        Assumption A7: touching the limit is NOT enough.
        - BUY limit at P: bar.low must be < P (sellers crossed your bid)
        - SELL limit at P: bar.high must be > P (buyers crossed your ask)
        """
        if side == OrderSide.BUY:
            return bar.low < limit_price
        else:
            return bar.high > limit_price

    def _volume_at_level(
        self,
        price: Optional[Decimal],
        bar: SimBar,
    ) -> Decimal:
        """
        Estimate volume available at a given price level.

        Assumption A9: volume is distributed uniformly across the bar's
        high-low range. Volume at the limit level is proportional to
        how close the limit is to the bar's range.

        Returns an estimate of shares/units available at this price.
        """
        if price is None or bar.volume <= 0:
            return Decimal("0")

        bar_range = bar.high - bar.low
        if bar_range <= 0:
            # Flat bar — all volume at one price
            if bar.close == price:
                return bar.volume
            return Decimal("0")

        # L9: Volume distribution across bar range
        # Near close: higher concentration (1/bar_range_buckets of volume)
        # Away from close: lower concentration (half of near-close)
        near_close_frac = Decimal("0.10")  # 10% of volume near close
        away_frac = Decimal("0.05")        # 5% of volume elsewhere in range
        bucket_width = bar_range * near_close_frac
        if abs(price - bar.close) <= bucket_width:
            return bar.volume * near_close_frac
        elif bar.low <= price <= bar.high:
            return bar.volume * away_frac
        else:
            return Decimal("0")
