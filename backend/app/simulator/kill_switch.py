"""
Kill switch — monitors risk limits and triggers circuit breakers.

Checked after every fill and on every mark-to-market update.
When any rule fires, all open orders are cancelled and no new
orders are accepted until the engine is reset.

Rules:
  KS1. Max cumulative loss (USD)
  KS2. Max drawdown (% from peak equity)
  KS3. Max open orders
  KS4. Max position notional
  KS5. Max loss per single trade
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from app.simulator.types import (
    InventorySnapshot,
    KillSwitchTrigger,
    SimulatorConfig,
)
from app.simulator.inventory import ClosedTrade

logger = logging.getLogger("pensy.simulator.kill_switch")


class KillSwitch:
    """
    Risk monitor that checks limits after every state change.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        self._config = config
        self._active = False
        self._trigger: Optional[KillSwitchTrigger] = None

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def trigger(self) -> Optional[KillSwitchTrigger]:
        return self._trigger

    def check(
        self,
        snapshot: InventorySnapshot,
        open_order_count: int,
        last_trade: Optional[ClosedTrade] = None,
    ) -> Optional[KillSwitchTrigger]:
        """
        Check all kill-switch rules against current state.

        Returns a KillSwitchTrigger if any rule fires, else None.
        Once triggered, the kill switch stays active.
        """
        if self._active:
            return self._trigger

        trigger = (
            self._check_max_loss(snapshot)
            or self._check_max_drawdown(snapshot)
            or self._check_max_open_orders(open_order_count, snapshot)
            or self._check_max_position_notional(snapshot)
            or self._check_max_loss_per_trade(last_trade, snapshot)
        )

        if trigger is not None:
            self._active = True
            self._trigger = trigger
            logger.warning(
                "KILL SWITCH TRIGGERED: %s — %s",
                trigger.rule,
                trigger.message,
            )

        return trigger

    def reset(self) -> None:
        """Reset the kill switch (for testing or manual override)."""
        self._active = False
        self._trigger = None

    # ------------------------------------------------------------------
    # Individual rule checks
    # ------------------------------------------------------------------

    def _check_max_loss(
        self, snap: InventorySnapshot,
    ) -> Optional[KillSwitchTrigger]:
        """KS1: Total loss (realized + unrealized) exceeds threshold."""
        total_pnl = snap.realized_pnl + snap.unrealized_pnl
        if total_pnl < -self._config.max_loss_usd:
            return KillSwitchTrigger(
                rule="KS1_MAX_LOSS",
                message=(
                    f"Total loss ${total_pnl} (realized={snap.realized_pnl}, "
                    f"unrealized={snap.unrealized_pnl}) exceeds "
                    f"limit -${self._config.max_loss_usd}"
                ),
                timestamp=snap.timestamp,
                values={
                    "realized_pnl": str(snap.realized_pnl),
                    "unrealized_pnl": str(snap.unrealized_pnl),
                    "total_pnl": str(total_pnl),
                    "limit": str(self._config.max_loss_usd),
                },
            )
        return None

    def _check_max_drawdown(
        self, snap: InventorySnapshot,
    ) -> Optional[KillSwitchTrigger]:
        """KS2: Drawdown from peak equity exceeds threshold."""
        if snap.drawdown_pct > float(self._config.max_drawdown_pct):
            return KillSwitchTrigger(
                rule="KS2_MAX_DRAWDOWN",
                message=(
                    f"Drawdown {snap.drawdown_pct:.2f}% exceeds "
                    f"limit {self._config.max_drawdown_pct}%"
                ),
                timestamp=snap.timestamp,
                values={
                    "drawdown_pct": snap.drawdown_pct,
                    "limit_pct": str(self._config.max_drawdown_pct),
                },
            )
        return None

    def _check_max_open_orders(
        self,
        count: int,
        snap: InventorySnapshot,
    ) -> Optional[KillSwitchTrigger]:
        """KS3: Too many open orders."""
        if count > self._config.max_open_orders:
            return KillSwitchTrigger(
                rule="KS3_MAX_OPEN_ORDERS",
                message=(
                    f"Open orders {count} exceeds "
                    f"limit {self._config.max_open_orders}"
                ),
                timestamp=snap.timestamp,
                values={
                    "open_orders": count,
                    "limit": self._config.max_open_orders,
                },
            )
        return None

    def _check_max_position_notional(
        self, snap: InventorySnapshot,
    ) -> Optional[KillSwitchTrigger]:
        """KS4: Position notional too large."""
        notional = abs(snap.net_qty * snap.avg_entry_price)
        if notional > self._config.max_position_notional:
            return KillSwitchTrigger(
                rule="KS4_MAX_POSITION_NOTIONAL",
                message=(
                    f"Position notional ${notional} exceeds "
                    f"limit ${self._config.max_position_notional}"
                ),
                timestamp=snap.timestamp,
                values={
                    "notional": str(notional),
                    "limit": str(self._config.max_position_notional),
                },
            )
        return None

    def _check_max_loss_per_trade(
        self,
        trade: Optional[ClosedTrade],
        snap: InventorySnapshot,
    ) -> Optional[KillSwitchTrigger]:
        """KS5: Single trade loss exceeds threshold."""
        if trade is None:
            return None
        if trade.net_pnl < -self._config.max_loss_per_trade_usd:
            return KillSwitchTrigger(
                rule="KS5_MAX_LOSS_PER_TRADE",
                message=(
                    f"Trade loss ${trade.net_pnl} exceeds "
                    f"limit -${self._config.max_loss_per_trade_usd}"
                ),
                timestamp=snap.timestamp,
                values={
                    "trade_pnl": str(trade.net_pnl),
                    "limit": str(self._config.max_loss_per_trade_usd),
                },
            )
        return None
