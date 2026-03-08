"""
Central registry for all agent skills.

Mirrors the RiskEngine check registration pattern with added
per-agent permissions and enable/disable controls.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agents.skill_base import BaseSkill
from app.agents.types import AgentType

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Central registry for all skills across all agents.

    Skills are registered globally. Agent permissions control
    which agents can invoke which skills.
    """

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._permissions: dict[AgentType, set[str]] = {
            AgentType.TRADE_DECISION: set(),
            AgentType.FAILURE_ANALYSIS: set(),
        }
        self._disabled: set[str] = set()

    def register(self, skill: BaseSkill, agents: list[AgentType]) -> None:
        """Register a skill and grant it to specified agents."""
        self._skills[skill.skill_id] = skill
        for agent_type in agents:
            self._permissions[agent_type].add(skill.skill_id)
        logger.info(
            "Registered skill: %s (v%s, type=%s) for agents=%s",
            skill.skill_id,
            skill.version,
            skill.execution_type.value,
            [a.value for a in agents],
        )

    def unregister(self, skill_id: str) -> None:
        """Remove a skill from the registry entirely."""
        self._skills.pop(skill_id, None)
        for perms in self._permissions.values():
            perms.discard(skill_id)

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """Look up a skill by ID."""
        return self._skills.get(skill_id)

    def get_for_agent(self, agent_type: AgentType) -> list[BaseSkill]:
        """Return all enabled skills permitted for a given agent type."""
        allowed_ids = self._permissions.get(agent_type, set())
        return [
            self._skills[sid]
            for sid in allowed_ids
            if sid in self._skills and sid not in self._disabled
        ]

    def disable(self, skill_id: str) -> None:
        """Globally disable a skill."""
        self._disabled.add(skill_id)
        logger.warning("Skill disabled: %s", skill_id)

    def enable(self, skill_id: str) -> None:
        """Re-enable a previously disabled skill."""
        self._disabled.discard(skill_id)
        logger.info("Skill enabled: %s", skill_id)

    def is_enabled(self, skill_id: str) -> bool:
        """Check if a skill is registered and not disabled."""
        return skill_id in self._skills and skill_id not in self._disabled

    def list_all(self) -> list[dict]:
        """Return metadata for all registered skills."""
        return [
            {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "execution_type": skill.execution_type.value,
                "risk_level": skill.risk_level.value,
                "requires_human_review": skill.requires_human_review,
                "enabled": skill.skill_id not in self._disabled,
                "agents": [
                    agent.value
                    for agent, perms in self._permissions.items()
                    if skill.skill_id in perms
                ],
            }
            for skill in self._skills.values()
        ]
