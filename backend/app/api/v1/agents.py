"""
Agent skill-system endpoints.

GET  /agents/skills                       - List all skill definitions.
GET  /agents/skills/{skill_id}            - Get a single skill by skill_id.
POST /agents/skills/{skill_id}/toggle     - Enable or disable a skill.
GET  /agents/invocations                  - List skill invocations.
GET  /agents/runs                         - List agent runs.
GET  /agents/runs/{run_id}                - Get a single agent run with invocations.
GET  /agents/lessons                      - List learned lessons.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.agents import (
    AgentRunListResponse,
    AgentRunResponse,
    LearnedLessonListResponse,
    LearnedLessonResponse,
    SkillDefinitionListResponse,
    SkillDefinitionResponse,
    SkillInvocationListResponse,
    SkillInvocationResponse,
    SkillToggleRequest,
)
from app.auth.jwt import get_current_user
from app.db.session import get_session
from app.models.agent import AgentRun, LearnedLesson, SkillDefinition, SkillInvocation
from app.models.user import User

logger = logging.getLogger("pensy.api.agents")

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Skill definitions
# ---------------------------------------------------------------------------


@router.get(
    "/skills",
    response_model=SkillDefinitionListResponse,
    summary="List all skill definitions",
)
async def list_skills(
    execution_type: Optional[str] = Query(None, description="Filter by execution type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled flag"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SkillDefinitionListResponse:
    """Return a paginated, filtered list of skill definitions."""
    query = select(SkillDefinition)

    if execution_type is not None:
        query = query.where(SkillDefinition.execution_type == execution_type)
    if enabled is not None:
        query = query.where(SkillDefinition.enabled == enabled)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(SkillDefinition.name).limit(limit).offset(offset)
    result = await session.execute(query)
    skills = result.scalars().all()

    return SkillDefinitionListResponse(
        skills=[SkillDefinitionResponse.model_validate(s) for s in skills],
        total=total,
    )


@router.get(
    "/skills/{skill_id}",
    response_model=SkillDefinitionResponse,
    summary="Get a single skill definition",
)
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SkillDefinitionResponse:
    """Retrieve a skill definition by its unique skill_id string."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.skill_id == skill_id)
    )
    skill = result.scalar_one_or_none()

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    return SkillDefinitionResponse.model_validate(skill)


@router.post(
    "/skills/{skill_id}/toggle",
    response_model=SkillDefinitionResponse,
    summary="Enable or disable a skill",
)
async def toggle_skill(
    skill_id: str,
    body: SkillToggleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SkillDefinitionResponse:
    """Set the enabled flag on a skill definition."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.skill_id == skill_id)
    )
    skill = result.scalar_one_or_none()

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    skill.enabled = body.enabled
    await session.flush()
    await session.refresh(skill)

    logger.info(
        "Skill %s %s by %s",
        skill.skill_id,
        "enabled" if body.enabled else "disabled",
        current_user.username,
    )

    return SkillDefinitionResponse.model_validate(skill)


# ---------------------------------------------------------------------------
# Skill invocations
# ---------------------------------------------------------------------------


@router.get(
    "/invocations",
    response_model=SkillInvocationListResponse,
    summary="List skill invocations",
)
async def list_invocations(
    skill_id: Optional[str] = Query(None, description="Filter by skill_id"),
    status: Optional[str] = Query(None, description="Filter by status"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SkillInvocationListResponse:
    """Return a paginated, filtered list of skill invocation audit records."""
    query = select(SkillInvocation)

    if skill_id is not None:
        query = query.where(SkillInvocation.skill_id == skill_id)
    if status is not None:
        query = query.where(SkillInvocation.status == status)
    if agent_type is not None:
        query = query.where(SkillInvocation.agent_type == agent_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = (
        query.order_by(SkillInvocation.created_at.desc()).limit(limit).offset(offset)
    )
    result = await session.execute(query)
    invocations = result.scalars().all()

    return SkillInvocationListResponse(
        invocations=[
            SkillInvocationResponse.model_validate(i) for i in invocations
        ],
        total=total,
    )


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------


@router.get(
    "/runs",
    response_model=AgentRunListResponse,
    summary="List agent runs",
)
async def list_runs(
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentRunListResponse:
    """Return a paginated, filtered list of agent pipeline runs."""
    query = select(AgentRun)

    if agent_type is not None:
        query = query.where(AgentRun.agent_type == agent_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(AgentRun.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    runs = result.scalars().all()

    return AgentRunListResponse(
        runs=[AgentRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunResponse,
    summary="Get a single agent run with invocations",
)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentRunResponse:
    """Retrieve a single agent run by UUID, including its skill invocations."""
    result = await session.execute(
        select(AgentRun).where(AgentRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail=f"Agent run not found: {run_id}")

    return AgentRunResponse.model_validate(run)


# ---------------------------------------------------------------------------
# Learned lessons
# ---------------------------------------------------------------------------


@router.get(
    "/lessons",
    response_model=LearnedLessonListResponse,
    summary="List learned lessons",
)
async def list_lessons(
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    applied: Optional[bool] = Query(None, description="Filter by applied flag"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LearnedLessonListResponse:
    """Return a paginated, filtered list of learned lessons."""
    query = select(LearnedLesson)

    if category is not None:
        query = query.where(LearnedLesson.category == category)
    if severity is not None:
        query = query.where(LearnedLesson.severity == severity)
    if applied is not None:
        query = query.where(LearnedLesson.applied == applied)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = (
        query.order_by(LearnedLesson.created_at.desc()).limit(limit).offset(offset)
    )
    result = await session.execute(query)
    lessons = result.scalars().all()

    return LearnedLessonListResponse(
        lessons=[LearnedLessonResponse.model_validate(l) for l in lessons],
        total=total,
    )
