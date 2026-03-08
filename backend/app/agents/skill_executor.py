"""
Skill executor - runs a single skill with timing, validation,
timeout handling, and audit logging.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.agents.skill_base import BaseSkill
from app.agents.types import SkillContext, SkillResult, SkillStatus
from app.core.events import EventBus

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Executes a single skill with:
    - Timing measurement
    - asyncio.timeout enforcement
    - Exception wrapping (mirrors RiskEngine exception -> FAIL)
    - Output validation
    - Optional audit persistence
    """

    def __init__(
        self,
        session_factory=None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def execute(self, skill: BaseSkill, ctx: SkillContext) -> SkillResult:
        """Execute a skill with full safety wrapper."""
        start = time.monotonic()
        result: SkillResult

        try:
            async with asyncio.timeout(skill.timeout_seconds):
                result = await skill.execute(ctx)

        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(
                "Skill timed out: %s after %.0fms (limit=%.0fs)",
                skill.skill_id,
                elapsed,
                skill.timeout_seconds,
            )
            result = SkillResult(
                skill_id=skill.skill_id,
                status=SkillStatus.TIMEOUT,
                message=f"Timed out after {skill.timeout_seconds}s",
                execution_time_ms=elapsed,
                version=skill.version,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception(
                "Skill raised exception: %s - %s", skill.skill_id, str(exc)
            )
            result = SkillResult(
                skill_id=skill.skill_id,
                status=SkillStatus.ERROR,
                message=f"Exception: {exc}",
                error=str(exc),
                execution_time_ms=elapsed,
                version=skill.version,
            )

        else:
            result.execution_time_ms = (time.monotonic() - start) * 1000

            # Validate result
            valid, reason = skill.validate_result(result)
            if not valid:
                logger.warning(
                    "Skill output validation failed: %s - %s",
                    skill.skill_id,
                    reason,
                )
                result.status = SkillStatus.FAILURE
                result.message = f"Validation failed: {reason}"

        # Log for audit trail
        logger.info(
            "Skill executed: %s status=%s time=%.0fms",
            skill.skill_id,
            result.status.value,
            result.execution_time_ms,
        )

        # Persist invocation record
        if self._session_factory:
            await self._persist_invocation(skill, ctx, result)

        return result

    async def _persist_invocation(
        self, skill: BaseSkill, ctx: SkillContext, result: SkillResult
    ) -> None:
        """Persist skill invocation to DB for audit trail."""
        try:
            async with self._session_factory() as session:
                from app.models.agent import SkillInvocation

                invocation = SkillInvocation(
                    skill_id=skill.skill_id,
                    agent_type=ctx.agent_type.value,
                    status=result.status.value,
                    execution_type=skill.execution_type.value,
                    input_summary={
                        "symbol": ctx.symbol,
                        "correlation_id": ctx.correlation_id,
                        "trading_mode": ctx.trading_mode,
                    },
                    output_json=result.output,
                    message=result.message,
                    confidence=result.confidence,
                    execution_time_ms=result.execution_time_ms,
                    version=result.version,
                    error=result.error,
                )
                session.add(invocation)
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to persist skill invocation for %s", skill.skill_id
            )
