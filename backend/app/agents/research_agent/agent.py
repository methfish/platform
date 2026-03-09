"""
Research Agent (Agent C).

Orchestrates a six-skill pipeline that moves from data inventory
through collection, backtesting, result analysis, parameter
optimization, and final report generation.

Pipeline order:
    1. data_inventory
    2. data_collection
    3. backtest_execution
    4. result_analysis
    5. parameter_optimization
    6. report_generation
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
    "data_inventory",
    "data_collection",
    "backtest_execution",
    "result_analysis",
    "parameter_optimization",
    "report_generation",
]


class ResearchAgent(BaseAgent):
    """
    Agent C - Automated strategy research and backtesting.

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
        return AgentType.RESEARCH

    @property
    def name(self) -> str:
        return "ResearchAgent"

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
            "ResearchAgent pipeline: [%s]",
            ", ".join(s.skill_id for s in pipeline),
        )
        return pipeline
