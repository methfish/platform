"""
Base agent class - orchestrates a pipeline of skills.

Each agent defines its skill pipeline order and execution policy.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.agents.skill_base import BaseSkill
from app.agents.skill_executor import SkillExecutor
from app.agents.skill_registry import SkillRegistry
from app.agents.skill_router import SkillPipelineResult, SkillRouter
from app.agents.types import AgentType, SkillContext

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents.

    Each agent defines its skill pipeline order and execution policy.
    The agent core pulls skills from the registry, builds a pipeline,
    and delegates execution to the router.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        executor: SkillExecutor,
    ) -> None:
        self._registry = registry
        self._router = SkillRouter(executor)

    @property
    @abstractmethod
    def agent_type(self) -> AgentType: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_pipeline(self, ctx: SkillContext) -> list[BaseSkill]:
        """Return the ordered list of skills for this agent's pipeline."""
        ...

    async def run(
        self,
        ctx: SkillContext,
        run_all: bool = False,
    ) -> SkillPipelineResult:
        """Execute the agent's full skill pipeline."""
        ctx.agent_type = self.agent_type
        pipeline = self.get_pipeline(ctx)

        logger.info(
            "Agent %s starting pipeline with %d skills",
            self.name,
            len(pipeline),
        )

        result = await self._router.run_pipeline(
            skills=pipeline,
            ctx=ctx,
            short_circuit_on_critical=True,
            run_all=run_all,
        )

        logger.info(
            "Agent %s pipeline complete: completed=%s failed=%s time=%.0fms",
            self.name,
            result.completed,
            result.failed_skills,
            result.total_execution_time_ms,
        )

        return result
