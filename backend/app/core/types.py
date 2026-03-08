"""
Branded types and type aliases for the Pensy platform.
Uses NewType for type safety without runtime overhead.
"""

from decimal import Decimal
from typing import NewType
from uuid import UUID

# Branded ID types for type safety
OrderId = NewType("OrderId", UUID)
FillId = NewType("FillId", UUID)
PositionId = NewType("PositionId", UUID)
StrategyId = NewType("StrategyId", UUID)
UserId = NewType("UserId", UUID)

# Client order ID is a string used as an idempotency key
ClientOrderId = NewType("ClientOrderId", str)

# Exchange-assigned order ID
ExchangeOrderId = NewType("ExchangeOrderId", str)

# Financial types
Price = NewType("Price", Decimal)
Quantity = NewType("Quantity", Decimal)
Notional = NewType("Notional", Decimal)

# Correlation ID for request tracing
CorrelationId = NewType("CorrelationId", str)

# Agent / Skill types
SkillId = NewType("SkillId", str)
AgentRunId = NewType("AgentRunId", UUID)
LessonId = NewType("LessonId", UUID)
