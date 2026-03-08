"""
Skill router - sequences skill execution with prerequisite checking
and failure handling.

Mirrors RiskEngine.evaluate_order: runs skills in order, supports
short-circuit on critical failure, wraps exceptions as ERROR results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.agents.skill_base import BaseSkill
from app.agents.skill_executor import SkillExecutor
from app.agents.types import SkillContext, SkillResult, SkillRiskLevel, SkillStatus

logger = logging.getLogger(__name__)


@dataclass
class SkillPipelineResult:
    """Aggregated result from running a skill pipeline. Mirrors RiskEngineResult."""

    completed: bool = True
    results: list[SkillResult] = field(default_factory=list)
    failed_skills: list[str] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)
    total_execution_time_ms: float = 0.0
    short_circuited: bool = False
    short_circuit_reason: str = ""


class SkillRouter:
    """
    Routes and sequences skill execution within an agent.

    Takes an ordered list of skills, validates prerequisites,
    runs each via SkillExecutor, and accumulates results.
    """

    def __init__(self, executor: SkillExecutor) -> None:
        self._executor = executor

    async def run_pipeline(
        self,
        skills: list[BaseSkill],
        ctx: SkillContext,
        short_circuit_on_critical: bool = True,
        run_all: bool = False,
    ) -> SkillPipelineResult:
        """
        Execute an ordered list of skills.

        Args:
            skills: Skills to run in order.
            ctx: The shared context (upstream_results mutated in place).
            short_circuit_on_critical: Stop on CRITICAL skill failure.
            run_all: Run all skills regardless of failures (diagnostics).
        """
        pipeline_result = SkillPipelineResult()

        for skill in skills:
            # Check prerequisites via can_run
            can_run, reason = skill.can_run(ctx)
            if not can_run:
                skip_result = skill._skip(f"Cannot run: {reason}")
                pipeline_result.results.append(skip_result)
                pipeline_result.skipped_skills.append(skill.skill_id)
                logger.info("Skill skipped: %s - %s", skill.skill_id, reason)
                continue

            # Execute via executor
            result = await self._executor.execute(skill, ctx)
            pipeline_result.results.append(result)
            pipeline_result.total_execution_time_ms += result.execution_time_ms

            # Inject result into context for downstream skills
            ctx.upstream_results[skill.skill_id] = result

            # Handle failure
            if result.status in (
                SkillStatus.FAILURE,
                SkillStatus.ERROR,
                SkillStatus.TIMEOUT,
            ):
                pipeline_result.failed_skills.append(skill.skill_id)
                logger.warning(
                    "Skill failed: %s status=%s message=%s",
                    skill.skill_id,
                    result.status.value,
                    result.message,
                )

                # Short-circuit on critical failure
                if (
                    not run_all
                    and short_circuit_on_critical
                    and skill.risk_level == SkillRiskLevel.CRITICAL
                ):
                    pipeline_result.completed = False
                    pipeline_result.short_circuited = True
                    pipeline_result.short_circuit_reason = (
                        f"Critical skill '{skill.skill_id}' failed: {result.message}"
                    )
                    logger.error(
                        "Pipeline short-circuited: %s",
                        pipeline_result.short_circuit_reason,
                    )
                    break

        return pipeline_result
