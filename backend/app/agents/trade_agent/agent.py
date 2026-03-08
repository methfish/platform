"""
Trade Decision Agent (Agent A).

Orchestrates a nine-skill pipeline that moves from budget
interpretation through opportunity scoring, position sizing,
entry planning, risk pre-check, and final trade decision.

Pipeline order:
    1. budget_interpretation
    2. market_context
    3. opportunity_scoring
    4. position_sizing
    5. entry_planning
    6. risk_precheck
    7. trade_decision
    8. no_trade_justification
    9. execution_review
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
    "budget_interpretation",
    "market_context",
    "opportunity_scoring",
    "position_sizing",
    "entry_planning",
    "risk_precheck",
    "trade_decision",
    "no_trade_justification",
    "execution_review",
]


class TradeDecisionAgent(BaseAgent):
    """
    Agent A - Capital deployment and order generation.

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
        return AgentType.TRADE_DECISION

    @property
    def name(self) -> str:
        return "TradeDecisionAgent"

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
            "TradeDecisionAgent pipeline: [%s]",
            ", ".join(s.skill_id for s in pipeline),
        )
        return pipeline
