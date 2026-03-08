"""
Abstract base class for all agent skills.

Every skill in the system inherits from BaseSkill and implements
the execute() method. This mirrors the BaseRiskCheck pattern:
abstract properties + abstract execute() + convenience helpers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Optional

from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)


class BaseSkill(ABC):
    """
    Abstract base class for all agent skills.

    Subclasses must implement:
        - skill_id: Unique identifier (e.g. "budget_interpretation").
        - name: Human-readable name.
        - description: What this skill does.
        - version: Semver version string.
        - execution_type: DETERMINISTIC | MODEL_ASSISTED | HYBRID.
        - required_inputs: Context keys that must be present.
        - execute(ctx): Async method returning a SkillResult.
    """

    # --- Abstract Properties ---

    @property
    @abstractmethod
    def skill_id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    @abstractmethod
    def execution_type(self) -> SkillExecutionType: ...

    @property
    @abstractmethod
    def required_inputs(self) -> list[str]: ...

    # --- Optional Properties with Defaults ---

    @property
    def optional_inputs(self) -> list[str]:
        return []

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM

    @property
    def requires_human_review(self) -> bool:
        return False

    @property
    def timeout_seconds(self) -> float:
        return 30.0

    @property
    def prerequisites(self) -> list[str]:
        """skill_ids that must have run successfully before this skill."""
        return []

    @property
    def allowed_modes(self) -> list[str]:
        """Trading modes this skill is allowed to run in."""
        return ["PAPER", "LIVE"]

    # --- Abstract Methods ---

    @abstractmethod
    async def execute(self, ctx: SkillContext) -> SkillResult: ...

    # --- Concrete Methods ---

    def can_run(self, ctx: SkillContext) -> tuple[bool, str]:
        """
        Check whether this skill can run given the context.

        Validates prerequisites, required inputs, and allowed modes.
        """
        # Check trading mode
        if ctx.trading_mode not in self.allowed_modes:
            return False, f"Skill not allowed in {ctx.trading_mode} mode"

        # Check prerequisites
        for prereq_id in self.prerequisites:
            upstream = ctx.upstream_results.get(prereq_id)
            if upstream is None:
                return False, f"Missing prerequisite skill: {prereq_id}"
            if upstream.status != SkillStatus.SUCCESS:
                return False, (
                    f"Prerequisite '{prereq_id}' did not succeed "
                    f"(status={upstream.status.value})"
                )

        # Check required inputs
        for key in self.required_inputs:
            val = getattr(ctx, key, None)
            if val is None or val == "" or val == {} or val == [] or val == Decimal("0"):
                # Allow Decimal("0") for some fields - only block truly empty
                if not isinstance(val, Decimal):
                    return False, f"Missing required input: {key}"

        return True, ""

    def validate_result(self, result: SkillResult) -> tuple[bool, str]:
        """
        Validate the skill's output after execution.

        Override in subclasses for custom validation.
        Default: checks that SUCCESS results have non-empty output.
        """
        if result.status == SkillStatus.SUCCESS and not result.output:
            return False, "Skill returned SUCCESS but output is empty"
        return True, ""

    # --- Convenience Helpers (mirror BaseRiskCheck._pass/_fail) ---

    def _success(
        self,
        output: dict[str, Any],
        message: str = "",
        confidence: Optional[float] = None,
        **details: Any,
    ) -> SkillResult:
        return SkillResult(
            skill_id=self.skill_id,
            status=SkillStatus.SUCCESS,
            output=output,
            message=message,
            confidence=confidence,
            details=details,
            version=self.version,
            requires_human_review=self.requires_human_review,
        )

    def _failure(self, message: str, **details: Any) -> SkillResult:
        return SkillResult(
            skill_id=self.skill_id,
            status=SkillStatus.FAILURE,
            message=message,
            details=details,
            version=self.version,
        )

    def _skip(self, message: str = "", **details: Any) -> SkillResult:
        return SkillResult(
            skill_id=self.skill_id,
            status=SkillStatus.SKIPPED,
            message=message,
            details=details,
            version=self.version,
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.skill_id} "
            f"v={self.version} type={self.execution_type.value}>"
        )
