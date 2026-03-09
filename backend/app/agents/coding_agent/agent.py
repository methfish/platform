"""
Strategy Coding Agent.

Orchestrates a five-skill pipeline that moves from strategy
analysis through code generation, validation, backtest
verification, and runtime registration.

Pipeline order:
    1. strategy_analysis
    2. code_generation
    3. code_validation
    4. backtest_verification
    5. code_registration
"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.agents.skill_base import BaseSkill
from app.agents.skill_executor import SkillExecutor
from app.agents.skill_registry import SkillRegistry
from app.agents.types import AgentType, SkillContext

logger = logging.getLogger(__name__)

# Canonical pipeline order - skills are looked up by these IDs.
PIPELINE_SKILL_IDS: list[str] = [
    "strategy_analysis",
    "code_generation",
    "code_validation",
    "backtest_verification",
    "code_registration",
]


class StrategyCodingAgent(BaseAgent):
    """
    Strategy Coding Agent - Code generation and registration.

    Pulls its skills from the SkillRegistry in the canonical
    pipeline order defined above. Missing or disabled skills
    are silently omitted so the pipeline degrades gracefully.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        executor: SkillExecutor,
    ) -> None:
        super().__init__(registry=registry, executor=executor)

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    @property
    def agent_type(self) -> AgentType:
        return AgentType.STRATEGY_CODING

    @property
    def name(self) -> str:
        return "StrategyCodingAgent"

    def get_pipeline(self, ctx: SkillContext) -> list[BaseSkill]:
        """
        Build the ordered pipeline by resolving skill IDs from the registry.

        Skills that are not registered or are currently disabled are
        excluded - this lets operators toggle individual pipeline steps
        without restarting the agent.
        """
        pipeline: list[BaseSkill] = []

        for skill_id in PIPELINE_SKILL_IDS:
            skill = self._registry.get(skill_id)
            if skill is None:
                logger.debug(
                    "Skill '%s' not found in registry, skipping.",
                    skill_id,
                )
                continue
            if not self._registry.is_enabled(skill_id):
                logger.debug(
                    "Skill '%s' is disabled, skipping.",
                    skill_id,
                )
                continue
            pipeline.append(skill)

        logger.info(
            "StrategyCodingAgent pipeline: [%s]",
            ", ".join(s.skill_id for s in pipeline),
        )
        return pipeline
