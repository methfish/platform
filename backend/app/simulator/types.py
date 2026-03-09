"""
Simulator types — shared dataclasses, enums, and configuration.

Simplifying assumptions:
  A1. L1 book only: bid/ask derived from OHLCV bars, not a real order book.
  A2. Market impact via square-root model (L2) — optional.
  A3. Latency is stochastic with jitter (L3).
  A4. Cancel latency configurable independently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FillType(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SimOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class SimOrderStatus(str, Enum):
    PENDING = "PENDING"          # Submitted but not yet acked (in-flight latency)
    OPEN = "OPEN"                # Acked, resting on book
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class SimulatorConfig:
    """
    Configuration for a single simulation run.

    All monetary values are Decimal for precision.
    """

    # Capital
    initial_capital: Decimal = Decimal("100000")
    base_currency: str = "USD"

    # Cost model
    maker_fee_rate: Decimal = Decimal("0.00003")    # 0.3 bps  (ECN forex)
    taker_fee_rate: Decimal = Decimal("0.00010")    # 1.0 bps
    spread_bps: Decimal = Decimal("5")              # 0.5 pip for EURUSD
    slippage_bps: Decimal = Decimal("1")            # Additional market-order slippage

    # Fill model
    # A5. Queue position: your order joins behind queue_behind_pct of bar volume.
    queue_behind_pct: Decimal = Decimal("0.50")
    # A6. Partial fills: each bar drains up to fill_rate_pct of remaining queue ahead.
    fill_rate_pct: Decimal = Decimal("1.0")
    # A7. Minimum fill quantum (prevents dust fills).
    min_fill_qty: Decimal = Decimal("1")

    # Latency
    order_latency_ms: int = 50
    cancel_latency_ms: int = 50
    # L3: Stochastic latency (jitter_ms > 0 adds uniform random jitter)
    latency_jitter_ms: int = 0

    # Kill-switch thresholds
    max_loss_usd: Decimal = Decimal("5000")
    max_drawdown_pct: Decimal = Decimal("10")
    max_open_orders: int = 50
    max_position_notional: Decimal = Decimal("1000000")
    max_loss_per_trade_usd: Decimal = Decimal("500")

    # Position limits
    max_position_qty: Decimal = Decimal("100000")

    # L0: Balance / margin tracking
    use_margin_check: bool = False
    leverage: Decimal = Decimal("50")  # Max leverage (50:1 for forex retail)

    # L1: Dynamic spread estimation from bar data
    use_dynamic_spread: bool = False
    dynamic_spread_multiplier: Decimal = Decimal("0.5")  # Fraction of HL range as spread proxy

    # L2: Market impact model (square-root)
    use_market_impact: bool = False
    impact_coefficient: Decimal = Decimal("0.1")  # sigma * coeff * sqrt(qty/ADV)
    avg_daily_volume: Decimal = Decimal("5000000")  # ADV for impact calculation

    # L5: Time-of-day session scaling
    use_session_scaling: bool = False
    # Session definitions: (start_hour_utc, end_hour_utc, vol_mult, spread_mult)
    # Default forex sessions: Asian=low vol/wide spread, London=high vol/tight, NY=high/tight
    sessions: list = field(default_factory=lambda: [
        {"name": "ASIAN", "start": 0, "end": 8, "vol_mult": 0.5, "spread_mult": 1.5},
        {"name": "LONDON", "start": 8, "end": 13, "vol_mult": 1.5, "spread_mult": 0.7},
        {"name": "NY_OVERLAP", "start": 13, "end": 17, "vol_mult": 1.8, "spread_mult": 0.6},
        {"name": "NY_LATE", "start": 17, "end": 22, "vol_mult": 1.0, "spread_mult": 1.0},
        {"name": "OFFHOURS", "start": 22, "end": 24, "vol_mult": 0.3, "spread_mult": 2.0},
    ])

    # L6: Weekend/holiday gap handling
    use_gap_detection: bool = False
    gap_threshold_multiplier: float = 3.0  # Gap if inter-bar time > this × normal duration
    gap_spread_multiplier: Decimal = Decimal("3.0")  # Widen spread on gap bars

    # Misc
    symbol: str = "EURUSD"

    def half_spread(self, mid: Decimal, bar: Optional[Any] = None) -> Decimal:
        """Half the bid-ask spread in price units.

        If use_dynamic_spread=True and a bar is provided, estimates spread
        from bar high-low range instead of using fixed spread_bps.
        """
        if self.use_dynamic_spread and bar is not None:
            bar_range = bar.high - bar.low
            if bar_range > 0:
                # L1: Spread proxy = fraction of bar range
                return bar_range * self.dynamic_spread_multiplier / Decimal("2")
        return mid * self.spread_bps / Decimal("20000")

    def slippage(self, mid: Decimal) -> Decimal:
        """Additional slippage for market/aggressive orders."""
        return mid * self.slippage_bps / Decimal("10000")

    def market_impact(self, mid: Decimal, qty: Decimal) -> Decimal:
        """L2: Square-root market impact model.

        Impact = mid × impact_coefficient × sqrt(qty / ADV)
        Based on: Almgren et al. "Optimal execution of portfolio transactions"
        """
        if not self.use_market_impact or self.avg_daily_volume <= 0:
            return Decimal("0")
        participation = float(qty / self.avg_daily_volume)
        impact_bps = float(self.impact_coefficient) * math.sqrt(max(0, participation))
        return mid * Decimal(str(impact_bps)) / Decimal("10000")

    def buying_power(self, equity: Decimal) -> Decimal:
        """L0: Maximum notional position allowed given current equity."""
        return equity * self.leverage

    def session_multipliers(self, hour_utc: int) -> tuple:
        """L5: Return (vol_mult, spread_mult) for the given hour."""
        if not self.use_session_scaling:
            return (1.0, 1.0)
        for sess in self.sessions:
            start = sess.get("start", 0)
            end = sess.get("end", 24)
            if start <= hour_utc < end:
                return (sess.get("vol_mult", 1.0), sess.get("spread_mult", 1.0))
        return (1.0, 1.0)


# ---------------------------------------------------------------------------
# Bar (reuses field names from backtest engine)
# ---------------------------------------------------------------------------


@dataclass
class SimBar:
    """One OHLCV bar fed into the simulator."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    symbol: str = ""
    interval: str = ""

    @property
    def mid(self) -> Decimal:
        return (self.high + self.low) / 2

    @property
    def typical(self) -> Decimal:
        return (self.high + self.low + self.close) / 3


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------


@dataclass
class SimOrder:
    """An order in the simulator."""

    order_id: str = field(default_factory=lambda: f"SIM-{uuid4().hex[:12].upper()}")
    client_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: SimOrderType = SimOrderType.LIMIT
    quantity: Decimal = Decimal("0")
    price: Optional[Decimal] = None         # Limit price; None for market
    status: SimOrderStatus = SimOrderStatus.PENDING

    filled_qty: Decimal = Decimal("0")
    avg_fill_price: Decimal = Decimal("0")
    total_commission: Decimal = Decimal("0")

    submit_time: Optional[datetime] = None  # Wall-clock time of submission
    ack_time: Optional[datetime] = None     # Time order is "on book"
    last_fill_time: Optional[datetime] = None

    # Queue tracking (assumption A5)
    queue_ahead: Decimal = Decimal("0")     # Volume ahead of us in the queue

    # Replace tracking
    original_order_id: Optional[str] = None  # If this is a replace, link to original

    @property
    def remaining_qty(self) -> Decimal:
        return self.quantity - self.filled_qty

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            SimOrderStatus.FILLED,
            SimOrderStatus.CANCELLED,
            SimOrderStatus.REJECTED,
        )

    @property
    def is_maker(self) -> bool:
        """Limit orders that rest on the book are maker orders."""
        return self.order_type == SimOrderType.LIMIT


# ---------------------------------------------------------------------------
# Fill
# ---------------------------------------------------------------------------


@dataclass
class SimFill:
    """A single fill (or partial fill) event."""

    fill_id: str = field(default_factory=lambda: f"F-{uuid4().hex[:8].upper()}")
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    fill_type: FillType = FillType.FULL
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    is_maker: bool = False
    timestamp: Optional[datetime] = None

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.price


# ---------------------------------------------------------------------------
# PnL Attribution
# ---------------------------------------------------------------------------


@dataclass
class PnLAttribution:
    """
    Breakdown of PnL into components.

    total = alpha + spread_cost + slippage_cost + commission_cost
    alpha = gross PnL if execution were at mid-price with zero costs
    """

    alpha: Decimal = Decimal("0")           # Gross edge (mid-to-mid)
    spread_cost: Decimal = Decimal("0")     # Cost of crossing the spread
    slippage_cost: Decimal = Decimal("0")   # Market-impact / slippage
    commission_cost: Decimal = Decimal("0") # Fees paid
    realized_pnl: Decimal = Decimal("0")    # Net realized

    @property
    def total_cost(self) -> Decimal:
        return self.spread_cost + self.slippage_cost + self.commission_cost


# ---------------------------------------------------------------------------
# Inventory snapshot
# ---------------------------------------------------------------------------


@dataclass
class InventorySnapshot:
    """Point-in-time inventory state."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    net_qty: Decimal = Decimal("0")
    avg_entry_price: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")
    drawdown_pct: float = 0.0
    attribution: PnLAttribution = field(default_factory=PnLAttribution)
    # L0: Capital tracking
    position_notional: Decimal = Decimal("0")
    available_margin: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Kill-switch reason
# ---------------------------------------------------------------------------


@dataclass
class KillSwitchTrigger:
    """Why the kill switch fired."""

    rule: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    values: dict[str, Any] = field(default_factory=dict)
