"""
Trading hours risk check.

Validates that the current time is within allowed trading hours.
Passes by default for crypto (24/7 markets). Can be configured
with specific allowed hours for equity/forex markets.
"""

from __future__ import annotations

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class TradingHoursCheck(BaseRiskCheck):
    """Check that the current time is within allowed trading hours."""

    @property
    def name(self) -> str:
        return "trading_hours"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        # Trading hours configuration.
        # Defaults: 0-24 (all hours), weekdays 0-6 (all days) = 24/7 crypto.
        start_hour = int(ctx.settings.get("TRADING_START_HOUR_UTC", 0))
        end_hour = int(ctx.settings.get("TRADING_END_HOUR_UTC", 24))
        allowed_weekdays = ctx.settings.get(
            "TRADING_ALLOWED_WEEKDAYS", {0, 1, 2, 3, 4, 5, 6}
        )

        # Convert weekday setting if provided as a string/list
        if isinstance(allowed_weekdays, str):
            allowed_weekdays = {
                int(d.strip())
                for d in allowed_weekdays.split(",")
                if d.strip().isdigit()
            }
        elif isinstance(allowed_weekdays, (list, tuple)):
            allowed_weekdays = set(allowed_weekdays)

        # Default 24/7 - pass immediately
        if start_hour == 0 and end_hour == 24 and len(allowed_weekdays) == 7:
            return self._pass("24/7 trading; no hour restrictions.")

        current_hour = ctx.current_hour_utc
        current_weekday = ctx.current_weekday

        # Check weekday
        if current_weekday not in allowed_weekdays:
            return self._fail(
                f"Trading not allowed on weekday {current_weekday} "
                f"(allowed: {sorted(allowed_weekdays)}).",
                current_weekday=current_weekday,
                allowed_weekdays=sorted(allowed_weekdays),
            )

        # Check hour
        if start_hour <= end_hour:
            # Simple range (e.g., 9-17)
            in_hours = start_hour <= current_hour < end_hour
        else:
            # Overnight range (e.g., 22-06)
            in_hours = current_hour >= start_hour or current_hour < end_hour

        if not in_hours:
            return self._fail(
                f"Current hour {current_hour} UTC is outside trading hours "
                f"({start_hour}-{end_hour} UTC).",
                current_hour=current_hour,
                start_hour=start_hour,
                end_hour=end_hour,
            )

        return self._pass(
            "Within trading hours.",
            current_hour=current_hour,
            start_hour=start_hour,
            end_hour=end_hour,
        )
