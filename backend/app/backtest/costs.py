"""
Realistic cost modeling for backtesting.

Models fees, slippage, spread, and partial fill probability
to avoid the most common backtesting pitfalls.

Default assumptions calibrated for a $2k crypto account:
  - Binance spot maker/taker fees
  - Conservative slippage estimates
  - Volume-aware fill probability
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CostModel:
    """
    Complete cost model for realistic backtesting.

    All rates are expressed as decimals (e.g., 0.001 = 0.1%).
    """

    # Commission
    maker_fee_rate: Decimal = Decimal("0.001")    # 0.10% Binance default
    taker_fee_rate: Decimal = Decimal("0.001")    # 0.10% Binance default

    # Slippage
    slippage_bps: Decimal = Decimal("2")          # 0.02% base slippage
    slippage_per_1k_usd: Decimal = Decimal("1")   # Extra bps per $1k notional

    # Spread
    spread_bps: Decimal = Decimal("3")            # Default bid-ask spread assumption

    # Partial fills
    fill_probability: Decimal = Decimal("0.85")   # % of limit orders that fill
    partial_fill_pct: Decimal = Decimal("0.70")   # Avg fill % when partially filled

    # Latency
    latency_ms: int = 50                           # Simulated order latency

    def compute_commission(
        self, notional: Decimal, is_maker: bool = False
    ) -> Decimal:
        """Compute commission for a given notional value."""
        rate = self.maker_fee_rate if is_maker else self.taker_fee_rate
        return (notional * rate).quantize(Decimal("0.00000001"))

    def compute_slippage(
        self, price: Decimal, notional: Decimal, side: str
    ) -> Decimal:
        """
        Compute slippage-adjusted execution price.

        Slippage increases with order size (notional).
        BUY orders slip up, SELL orders slip down.
        """
        base_slip = self.slippage_bps / Decimal("10000")
        size_slip = (notional / Decimal("1000")) * self.slippage_per_1k_usd / Decimal("10000")
        total_slip = base_slip + size_slip

        if side.upper() == "BUY":
            return price * (Decimal("1") + total_slip)
        else:
            return price * (Decimal("1") - total_slip)

    def compute_spread_cost(self, mid_price: Decimal) -> Decimal:
        """Compute half-spread cost (cost to cross the spread)."""
        return mid_price * self.spread_bps / Decimal("20000")

    def compute_effective_price(
        self,
        mid_price: Decimal,
        notional: Decimal,
        side: str,
        is_maker: bool = False,
    ) -> Decimal:
        """
        Compute the all-in effective execution price.

        Includes spread crossing + slippage.
        Commission is added separately.
        """
        spread_half = self.compute_spread_cost(mid_price)

        if side.upper() == "BUY":
            crossed_price = mid_price + spread_half
        else:
            crossed_price = mid_price - spread_half

        return self.compute_slippage(crossed_price, notional, side)

    def compute_total_cost(
        self,
        mid_price: Decimal,
        quantity: Decimal,
        side: str,
        is_maker: bool = False,
    ) -> dict:
        """
        Compute full cost breakdown for a trade.

        Returns dict with execution_price, commission, slippage_cost,
        spread_cost, total_cost.
        """
        notional = mid_price * quantity
        exec_price = self.compute_effective_price(mid_price, notional, side, is_maker)
        actual_notional = exec_price * quantity
        commission = self.compute_commission(actual_notional, is_maker)

        price_diff = abs(exec_price - mid_price)
        spread_cost = self.compute_spread_cost(mid_price) * quantity
        slippage_cost = (price_diff * quantity) - spread_cost
        if slippage_cost < 0:
            slippage_cost = Decimal("0")

        return {
            "mid_price": mid_price,
            "execution_price": exec_price,
            "quantity": quantity,
            "notional": actual_notional,
            "commission": commission,
            "spread_cost": spread_cost.quantize(Decimal("0.00000001")),
            "slippage_cost": slippage_cost.quantize(Decimal("0.00000001")),
            "total_cost": (commission + spread_cost + slippage_cost).quantize(Decimal("0.00000001")),
        }


# ---------------------------------------------------------------------------
# Preset cost models
# ---------------------------------------------------------------------------

BINANCE_SPOT = CostModel(
    maker_fee_rate=Decimal("0.001"),
    taker_fee_rate=Decimal("0.001"),
    slippage_bps=Decimal("2"),
    spread_bps=Decimal("2"),
)

BINANCE_SPOT_BNB_DISCOUNT = CostModel(
    maker_fee_rate=Decimal("0.00075"),
    taker_fee_rate=Decimal("0.00075"),
    slippage_bps=Decimal("2"),
    spread_bps=Decimal("2"),
)

CONSERVATIVE = CostModel(
    maker_fee_rate=Decimal("0.001"),
    taker_fee_rate=Decimal("0.001"),
    slippage_bps=Decimal("5"),
    spread_bps=Decimal("5"),
    fill_probability=Decimal("0.70"),
)

ZERO_COST = CostModel(
    maker_fee_rate=Decimal("0"),
    taker_fee_rate=Decimal("0"),
    slippage_bps=Decimal("0"),
    spread_bps=Decimal("0"),
    fill_probability=Decimal("1.0"),
)
