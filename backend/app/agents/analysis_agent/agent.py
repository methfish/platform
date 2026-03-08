"""
Failure Analysis Agent (Agent B) - Post-mortem and incident analysis.

Orchestrates a pipeline of skills that detect incidents, reconstruct
timelines, classify root causes, run counterfactual analysis, generate
recommendations, extract lessons, and compile a structured report.
"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.agents.skill_base import BaseSkill
from app.agents.skill_executor import SkillExecutor
from app.agents.skill_registry import SkillRegistry
from app.agents.types import AgentType, SkillContext

from app.agents.analysis_agent.skills.incident_detection import IncidentDetectionSkill
from app.agents.analysis_agent.skills.timeline_reconstruction import (
    TimelineReconstructionSkill,
)
from app.agents.analysis_agent.skills.root_cause_classification import (
    RootCauseClassificationSkill,
)
from app.agents.analysis_agent.skills.counterfactual_analysis import (
    CounterfactualAnalysisSkill,
)
from app.agents.analysis_agent.skills.recommendation_generation import (
    RecommendationGenerationSkill,
)
from app.agents.analysis_agent.skills.lesson_extraction import LessonExtractionSkill
from app.agents.analysis_agent.skills.report_writing import ReportWritingSkill

logger = logging.getLogger(__name__)

# Canonical pipeline ordering for the failure analysis agent.
_PIPELINE_SKILL_CLASSES: list[type[BaseSkill]] = [
    IncidentDetectionSkill,
    TimelineReconstructionSkill,
    RootCauseClassificationSkill,
    CounterfactualAnalysisSkill,
    RecommendationGenerationSkill,
    LessonExtractionSkill,
    ReportWritingSkill,
]


class FailureAnalysisAgent(BaseAgent):
    """
    Failure Analysis Agent (Agent B).

    Runs a sequential pipeline that analyses trading incidents:
    incident_detection -> timeline_reconstruction -> root_cause_classification
    -> counterfactual_analysis -> recommendation_generation
    -> lesson_extraction -> report_writing
    """

    def __init__(
        self,
        registry: SkillRegistry,
        executor: SkillExecutor,
    ) -> None:
        super().__init__(registry, executor)
        # Pre-instantiate skills so they are ready for every pipeline run.
        self._skills: list[BaseSkill] = [cls() for cls in _PIPELINE_SKILL_CLASSES]

    # --- Abstract property implementations ---

    @property
    def agent_type(self) -> AgentType:
        return AgentType.FAILURE_ANALYSIS

    @property
    def name(self) -> str:
        return "FailureAnalysisAgent"

    # --- Pipeline ---

    def get_pipeline(self, ctx: SkillContext) -> list[BaseSkill]:
        """Return the ordered list of skills for post-mortem analysis."""
        return list(self._skills)
