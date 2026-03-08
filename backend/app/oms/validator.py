"""
Pre-submission order validation.

Performs structural validation on order parameters before the order
enters the risk-check pipeline. Returns a list of human-readable
validation error strings (empty list means the order is valid).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.core.enums import OrderSide, OrderType, TimeInForce


def validate_order(
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    time_in_force: TimeInForce = TimeInForce.GTC,
) -> list[str]:
    """
    Validate order parameters before submission.

    Args:
        symbol: Trading pair symbol (e.g. BTCUSDT).
        side: Order side (BUY / SELL).
        order_type: Order type (MARKET / LIMIT / etc.).
        quantity: Order quantity.
        price: Limit price (required for LIMIT and STOP_LIMIT orders).
        time_in_force: Time-in-force instruction.

    Returns:
        A list of validation error messages. Empty list indicates success.
    """
    errors: list[str] = []

    # --- Symbol ---
    if not symbol or not symbol.strip():
        errors.append("Symbol must not be empty.")

    # --- Quantity ---
    if quantity is None:
        errors.append("Quantity is required.")
    elif quantity <= Decimal("0"):
        errors.append(f"Quantity must be positive, got {quantity}.")

    # --- Price for limit-style orders ---
    requires_price = order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT}
    if requires_price:
        if price is None:
            errors.append(f"Price is required for {order_type.value} orders.")
        elif price <= Decimal("0"):
            errors.append(f"Price must be positive for {order_type.value} orders, got {price}.")

    # --- Side validation ---
    if not isinstance(side, OrderSide):
        try:
            OrderSide(side)
        except (ValueError, KeyError):
            errors.append(f"Invalid order side: {side}. Must be BUY or SELL.")

    # --- Order type validation ---
    if not isinstance(order_type, OrderType):
        try:
            OrderType(order_type)
        except (ValueError, KeyError):
            errors.append(f"Invalid order type: {order_type}.")

    # --- Time in force validation ---
    if not isinstance(time_in_force, TimeInForce):
        try:
            TimeInForce(time_in_force)
        except (ValueError, KeyError):
            errors.append(f"Invalid time_in_force: {time_in_force}.")

    return errors
