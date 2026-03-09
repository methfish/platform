"""
Cross-exchange arbitrage strategy.

Monitors the same symbol across two exchanges. When bid on Exchange A
exceeds ask on Exchange B (or vice versa), simultaneously buys on the
cheap exchange and sells on the expensive exchange.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.strategy.base import BaseStrategy, OrderIntent

logger = logging.getLogger(__name__)

_TEN_THOUSAND = Decimal("10000")
_ZERO = Decimal("0")


class ArbLegStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ArbOpportunity:
    """Tracks a single arbitrage attempt with two legs."""

    arb_id: str
    buy_exchange: str
    sell_exchange: str
    symbol: str
    buy_price: Decimal
    sell_price: Decimal
    quantity: Decimal
    spread_bps: Decimal
    buy_leg_status: ArbLegStatus = ArbLegStatus.PENDING
    sell_leg_status: ArbLegStatus = ArbLegStatus.PENDING
    buy_filled_qty: Decimal = _ZERO
    sell_filled_qty: Decimal = _ZERO
    created_at: float = 0.0

    @property
    def is_complete(self) -> bool:
        return (
            self.buy_leg_status in (ArbLegStatus.FILLED, ArbLegStatus.CANCELLED, ArbLegStatus.FAILED)
            and self.sell_leg_status in (ArbLegStatus.FILLED, ArbLegStatus.CANCELLED, ArbLegStatus.FAILED)
        )

    @property
    def profit(self) -> Decimal:
        return (self.sell_price - self.buy_price) * min(self.buy_filled_qty, self.sell_filled_qty)


@dataclass
class ArbitrageConfig:
    """Configuration for the arbitrage strategy."""

    symbol: str = "BTCUSDT"
    exchange_a: str = "binance_spot"
    exchange_b: str = "paper"
    min_spread_bps: Decimal = Decimal("5")
    order_quantity: Decimal = Decimal("0.01")
    max_open_arbs: int = 3
    max_leg_risk_seconds: float = 5.0
    use_market_orders: bool = True
    max_inventory_imbalance: Decimal = Decimal("0.1")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArbitrageConfig:
        return cls(
            symbol=d.get("symbol", "BTCUSDT"),
            exchange_a=d.get("exchange_a", "binance_spot"),
            exchange_b=d.get("exchange_b", "paper"),
            min_spread_bps=Decimal(str(d.get("min_spread_bps", "5"))),
            order_quantity=Decimal(str(d.get("order_quantity", "0.01"))),
            max_open_arbs=int(d.get("max_open_arbs", 3)),
            max_leg_risk_seconds=float(d.get("max_leg_risk_seconds", 5.0)),
            use_market_orders=bool(d.get("use_market_orders", True)),
            max_inventory_imbalance=Decimal(str(d.get("max_inventory_imbalance", "0.1"))),
        )


class ArbitrageStrategy(BaseStrategy):
    """
    Cross-exchange arbitrage strategy.

    Monitors tickers from two exchanges via the StrategyContext.
    When a profitable spread is detected (bid_A > ask_B or bid_B > ask_A),
    emits simultaneous buy+sell OrderIntents targeting different exchanges.
    """

    def __init__(self, config: ArbitrageConfig | None = None, strategy_id: str = "") -> None:
        self._config = config or ArbitrageConfig()
        self._strategy_id = strategy_id
        self._open_arbs: list[ArbOpportunity] = []
        self._completed_arbs: list[ArbOpportunity] = []
        self._net_inventory = _ZERO
        self._ticks_processed = 0
        self._arbs_attempted = 0

        # Cache tickers from both exchanges
        self._ticker_a: dict[str, Decimal] | None = None  # {bid, ask, last}
        self._ticker_b: dict[str, Decimal] | None = None

    @property
    def name(self) -> str:
        return f"arb_{self._config.symbol.lower()}"

    @property
    def strategy_type(self) -> str:
        return "ARBITRAGE"

    async def on_start(self) -> None:
        self._open_arbs = []
        self._completed_arbs = []
        self._net_inventory = _ZERO
        self._ticks_processed = 0
        self._arbs_attempted = 0
        self._ticker_a = None
        self._ticker_b = None
        logger.info(
            "Arb strategy started: %s (%s vs %s) min_spread=%sbps qty=%s",
            self._config.symbol,
            self._config.exchange_a,
            self._config.exchange_b,
            self._config.min_spread_bps,
            self._config.order_quantity,
        )

    async def on_stop(self) -> None:
        total_profit = sum(a.profit for a in self._completed_arbs)
        logger.info(
            "Arb strategy stopped: %s arbs=%d profit=%s inventory=%s",
            self._config.symbol,
            len(self._completed_arbs),
            total_profit,
            self._net_inventory,
        )

    async def on_tick(
        self, symbol: str, bid: Decimal, ask: Decimal, last: Decimal
    ) -> list[OrderIntent]:
        """
        Process ticks. The runner calls this for each exchange tick.
        We use metadata from the context to determine which exchange
        the tick came from.
        """
        if symbol != self._config.symbol:
            return []

        self._ticks_processed += 1

        # Clean up completed arbs
        self._open_arbs = [a for a in self._open_arbs if not a.is_complete]
        if len(self._completed_arbs) > 100:
            self._completed_arbs = self._completed_arbs[-50:]

        # Check for leg risk timeout
        self._check_leg_risk()

        # Can't detect arb without both exchange tickers
        # The runner updates context with exchange-keyed tickers
        # For now, we rely on the runner to call with enriched context
        if self._ticker_a is None or self._ticker_b is None:
            return []

        # Check capacity
        if len(self._open_arbs) >= self._config.max_open_arbs:
            return []

        # Check inventory imbalance
        if abs(self._net_inventory) >= self._config.max_inventory_imbalance:
            return []

        return self._detect_and_emit()

    def update_exchange_ticker(
        self, exchange: str, bid: Decimal, ask: Decimal, last: Decimal
    ) -> None:
        """Called by the runner to update per-exchange ticker data."""
        ticker = {"bid": bid, "ask": ask, "last": last}
        if exchange == self._config.exchange_a:
            self._ticker_a = ticker
        elif exchange == self._config.exchange_b:
            self._ticker_b = ticker

    def _detect_and_emit(self) -> list[OrderIntent]:
        """Detect arbitrage opportunity and emit order intents."""
        assert self._ticker_a is not None and self._ticker_b is not None

        bid_a = self._ticker_a["bid"]
        ask_a = self._ticker_a["ask"]
        bid_b = self._ticker_b["bid"]
        ask_b = self._ticker_b["ask"]

        intents: list[OrderIntent] = []

        # Opportunity 1: Buy on B, sell on A (bid_A > ask_B)
        if bid_a > ask_b and ask_b > _ZERO:
            spread_bps = (bid_a - ask_b) / ask_b * _TEN_THOUSAND
            if spread_bps >= self._config.min_spread_bps:
                intents = self._create_arb_intents(
                    buy_exchange=self._config.exchange_b,
                    sell_exchange=self._config.exchange_a,
                    buy_price=ask_b,
                    sell_price=bid_a,
                    spread_bps=spread_bps,
                )

        # Opportunity 2: Buy on A, sell on B (bid_B > ask_A)
        elif bid_b > ask_a and ask_a > _ZERO:
            spread_bps = (bid_b - ask_a) / ask_a * _TEN_THOUSAND
            if spread_bps >= self._config.min_spread_bps:
                intents = self._create_arb_intents(
                    buy_exchange=self._config.exchange_a,
                    sell_exchange=self._config.exchange_b,
                    buy_price=ask_a,
                    sell_price=bid_b,
                    spread_bps=spread_bps,
                )

        return intents

    def _create_arb_intents(
        self,
        buy_exchange: str,
        sell_exchange: str,
        buy_price: Decimal,
        sell_price: Decimal,
        spread_bps: Decimal,
    ) -> list[OrderIntent]:
        """Create paired buy/sell intents for an arb opportunity."""
        arb_id = str(uuid4())[:8]
        order_type = OrderType.MARKET if self._config.use_market_orders else OrderType.LIMIT

        arb = ArbOpportunity(
            arb_id=arb_id,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            symbol=self._config.symbol,
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=self._config.order_quantity,
            spread_bps=spread_bps,
            created_at=time.monotonic(),
        )
        self._open_arbs.append(arb)
        self._arbs_attempted += 1

        logger.info(
            "Arb opportunity: buy %s@%s sell %s@%s spread=%sbps",
            buy_exchange, buy_price, sell_exchange, sell_price, spread_bps.quantize(Decimal("0.1")),
        )

        buy_intent = OrderIntent(
            symbol=self._config.symbol,
            side=OrderSide.BUY,
            order_type=order_type,
            quantity=self._config.order_quantity,
            price=buy_price if order_type == OrderType.LIMIT else None,
            time_in_force=TimeInForce.IOC,
            strategy_id=self._strategy_id,
            exchange=buy_exchange,
            metadata={"arb_id": arb_id, "arb_leg": "buy"},
        )

        sell_intent = OrderIntent(
            symbol=self._config.symbol,
            side=OrderSide.SELL,
            order_type=order_type,
            quantity=self._config.order_quantity,
            price=sell_price if order_type == OrderType.LIMIT else None,
            time_in_force=TimeInForce.IOC,
            strategy_id=self._strategy_id,
            exchange=sell_exchange,
            metadata={"arb_id": arb_id, "arb_leg": "sell"},
        )

        return [buy_intent, sell_intent]

    def _check_leg_risk(self) -> None:
        """Check for one-legged arbs that exceeded the timeout."""
        now = time.monotonic()
        for arb in self._open_arbs:
            age = now - arb.created_at
            if age > self._config.max_leg_risk_seconds:
                # If one leg filled but other didn't, log warning
                if arb.buy_leg_status == ArbLegStatus.FILLED and arb.sell_leg_status != ArbLegStatus.FILLED:
                    arb.sell_leg_status = ArbLegStatus.CANCELLED
                    logger.warning("Arb %s: sell leg timed out, buy leg exposed", arb.arb_id)
                elif arb.sell_leg_status == ArbLegStatus.FILLED and arb.buy_leg_status != ArbLegStatus.FILLED:
                    arb.buy_leg_status = ArbLegStatus.CANCELLED
                    logger.warning("Arb %s: buy leg timed out, sell leg exposed", arb.arb_id)

    async def on_fill(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal
    ) -> None:
        if side == "BUY":
            self._net_inventory += quantity
        else:
            self._net_inventory -= quantity

        # Try to match fill to an arb opportunity
        for arb in self._open_arbs:
            if side == "BUY" and arb.buy_leg_status in (ArbLegStatus.PENDING, ArbLegStatus.SUBMITTED):
                arb.buy_leg_status = ArbLegStatus.FILLED
                arb.buy_filled_qty = quantity
                break
            elif side == "SELL" and arb.sell_leg_status in (ArbLegStatus.PENDING, ArbLegStatus.SUBMITTED):
                arb.sell_leg_status = ArbLegStatus.FILLED
                arb.sell_filled_qty = quantity
                break

        # Move completed arbs to history
        newly_complete = [a for a in self._open_arbs if a.is_complete]
        for arb in newly_complete:
            self._completed_arbs.append(arb)
            logger.info(
                "Arb %s completed: profit=%s",
                arb.arb_id, arb.profit,
            )
