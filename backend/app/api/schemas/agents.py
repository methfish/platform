"""
Pydantic request/response schemas for agent/skill endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Skill definitions
# ---------------------------------------------------------------------------


class SkillDefinitionResponse(BaseModel):
    """Single skill definition detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    skill_id: str
    name: str
    description: Optional[str] = None
    version: str
    execution_type: str
    risk_level: str
    requires_human_review: bool
    enabled: bool
    created_at: datetime


class SkillDefinitionListResponse(BaseModel):
    """Paginated list of skill definitions."""

    skills: list[SkillDefinitionResponse]
    total: int


# ---------------------------------------------------------------------------
# Skill invocations
# ---------------------------------------------------------------------------


class SkillInvocationResponse(BaseModel):
    """Single skill invocation audit record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    skill_id: str
    agent_type: str
    status: str
    execution_type: str
    input_summary: Optional[dict[str, Any]] = None
    output_json: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    confidence: Optional[float] = None
    execution_time_ms: float
    version: str
    error: Optional[str] = None
    created_at: datetime


class SkillInvocationListResponse(BaseModel):
    """Paginated list of skill invocations."""

    invocations: list[SkillInvocationResponse]
    total: int


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------


class AgentRunResponse(BaseModel):
    """Single agent pipeline execution record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_type: str
    completed: bool
    short_circuited: bool
    short_circuit_reason: Optional[str] = None
    total_execution_time_ms: float
    skills_run: int
    skills_failed: int
    skills_skipped: int
    trading_mode: str
    created_at: datetime
    invocations: list[SkillInvocationResponse]


class AgentRunListResponse(BaseModel):
    """Paginated list of agent runs."""

    runs: list[AgentRunResponse]
    total: int


# ---------------------------------------------------------------------------
# Learned lessons
# ---------------------------------------------------------------------------


class LearnedLessonResponse(BaseModel):
    """Single learned lesson extracted by the Failure Analysis Agent."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    severity: str
    title: str
    description: Optional[str] = None
    root_cause: Optional[str] = None
    recommendation: Optional[str] = None
    symbol: Optional[str] = None
    applied: bool
    created_at: datetime


class LearnedLessonListResponse(BaseModel):
    """Paginated list of learned lessons."""

    lessons: list[LearnedLessonResponse]
    total: int


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SkillToggleRequest(BaseModel):
    """Request body for toggling a skill's enabled state."""

    enabled: bool = Field(..., description="Whether the skill should be enabled")
