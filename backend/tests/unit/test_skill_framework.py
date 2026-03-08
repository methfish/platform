"""
Unit tests for the agent skill framework.

Tests BaseSkill, SkillRegistry, SkillExecutor, and SkillRouter.
Each skill receives a SkillContext and returns a SkillResult.
"""

import asyncio
from decimal import Decimal

import pytest

from app.agents.skill_base import BaseSkill
from app.agents.skill_executor import SkillExecutor
from app.agents.skill_registry import SkillRegistry
from app.agents.skill_router import SkillPipelineResult, SkillRouter
from app.agents.types import (
    AgentType,
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummySkill(BaseSkill):
    """Minimal concrete skill for testing."""

    def __init__(
        self,
        *,
        skill_id: str = "dummy_skill",
        name: str = "Dummy Skill",
        description: str = "A dummy skill for tests",
        version: str = "1.0.0",
        execution_type: SkillExecutionType = SkillExecutionType.DETERMINISTIC,
        required_inputs: list[str] | None = None,
        risk_level: SkillRiskLevel = SkillRiskLevel.MEDIUM,
        requires_human_review: bool = False,
        timeout_seconds: float = 30.0,
        prerequisites: list[str] | None = None,
        allowed_modes: list[str] | None = None,
        execute_fn=None,
    ):
        self._skill_id = skill_id
        self._name = name
        self._description = description
        self._version = version
        self._execution_type = execution_type
        self._required_inputs = required_inputs or []
        self._risk_level = risk_level
        self._requires_human_review = requires_human_review
        self._timeout_seconds = timeout_seconds
        self._prerequisites = prerequisites or []
        self._allowed_modes = allowed_modes or ["PAPER", "LIVE"]
        self._execute_fn = execute_fn

    @property
    def skill_id(self) -> str:
        return self._skill_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def version(self) -> str:
        return self._version

    @property
    def execution_type(self) -> SkillExecutionType:
        return self._execution_type

    @property
    def required_inputs(self) -> list[str]:
        return self._required_inputs

    @property
    def risk_level(self) -> SkillRiskLevel:
        return self._risk_level

    @property
    def requires_human_review(self) -> bool:
        return self._requires_human_review

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    @property
    def prerequisites(self) -> list[str]:
        return self._prerequisites

    @property
    def allowed_modes(self) -> list[str]:
        return self._allowed_modes

    async def execute(self, ctx: SkillContext) -> SkillResult:
        if self._execute_fn is not None:
            return await self._execute_fn(self, ctx)
        return self._success({"result": "ok"}, message="Done")


def _make_skill(**overrides) -> DummySkill:
    """Factory that builds a DummySkill with sensible defaults."""
    return DummySkill(**overrides)


def _make_context(**overrides) -> SkillContext:
    """Factory that builds a SkillContext with sensible defaults."""
    defaults = dict(
        agent_type=AgentType.TRADE_DECISION,
        symbol="BTCUSDT",
        symbols=["BTCUSDT"],
        market_data={"last_price": 50000},
        total_portfolio_value=Decimal("100000"),
        available_capital=Decimal("50000"),
        trading_mode="PAPER",
    )
    defaults.update(overrides)
    return SkillContext(**defaults)


# ---------------------------------------------------------------------------
# BaseSkill tests
# ---------------------------------------------------------------------------

def test_concrete_skill_implements_all_properties():
    """A concrete DummySkill exposes all required abstract properties."""
    skill = _make_skill(
        skill_id="test_skill",
        name="Test Skill",
        description="Tests stuff",
        version="2.0.0",
        execution_type=SkillExecutionType.MODEL_ASSISTED,
        required_inputs=["symbol"],
    )
    assert skill.skill_id == "test_skill"
    assert skill.name == "Test Skill"
    assert skill.description == "Tests stuff"
    assert skill.version == "2.0.0"
    assert skill.execution_type == SkillExecutionType.MODEL_ASSISTED
    assert skill.required_inputs == ["symbol"]
    # Defaults
    assert skill.risk_level == SkillRiskLevel.MEDIUM
    assert skill.requires_human_review is False
    assert skill.timeout_seconds == 30.0
    assert skill.prerequisites == []
    assert skill.allowed_modes == ["PAPER", "LIVE"]


def test_success_helper_creates_correct_result():
    """_success() returns a SkillResult with SUCCESS status and the given output."""
    skill = _make_skill(skill_id="scorer", version="1.2.0")
    result = skill._success(
        {"score": 0.95}, message="High score", confidence=0.95
    )
    assert result.skill_id == "scorer"
    assert result.status == SkillStatus.SUCCESS
    assert result.output == {"score": 0.95}
    assert result.message == "High score"
    assert result.confidence == 0.95
    assert result.version == "1.2.0"


def test_failure_helper_creates_correct_result():
    """_failure() returns a SkillResult with FAILURE status."""
    skill = _make_skill(skill_id="validator")
    result = skill._failure("insufficient data", reason="no_candles")
    assert result.status == SkillStatus.FAILURE
    assert result.skill_id == "validator"
    assert result.message == "insufficient data"
    assert result.output == {}
    assert result.details == {"reason": "no_candles"}


def test_skip_helper_creates_correct_result():
    """_skip() returns a SkillResult with SKIPPED status."""
    skill = _make_skill(skill_id="optional_step")
    result = skill._skip("not needed", cause="already_done")
    assert result.status == SkillStatus.SKIPPED
    assert result.skill_id == "optional_step"
    assert result.message == "not needed"
    assert result.details == {"cause": "already_done"}


def test_can_run_passes_with_valid_context():
    """can_run() returns True when all prerequisites, inputs, and mode match."""
    skill = _make_skill(
        required_inputs=["symbol"],
        prerequisites=[],
        allowed_modes=["PAPER"],
    )
    ctx = _make_context(symbol="ETHUSDT", trading_mode="PAPER")
    can, reason = skill.can_run(ctx)
    assert can is True
    assert reason == ""


def test_can_run_fails_on_wrong_trading_mode():
    """can_run() rejects execution when trading_mode is not allowed."""
    skill = _make_skill(allowed_modes=["LIVE"])
    ctx = _make_context(trading_mode="PAPER")
    can, reason = skill.can_run(ctx)
    assert can is False
    assert "PAPER" in reason


def test_can_run_fails_on_missing_prerequisite():
    """can_run() rejects execution when a prerequisite skill has not run."""
    skill = _make_skill(prerequisites=["market_context"])
    ctx = _make_context(upstream_results={})
    can, reason = skill.can_run(ctx)
    assert can is False
    assert "market_context" in reason


def test_can_run_fails_on_failed_prerequisite():
    """can_run() rejects execution when a prerequisite skill did not succeed."""
    failed_result = SkillResult(
        skill_id="market_context",
        status=SkillStatus.FAILURE,
        message="no data",
    )
    skill = _make_skill(prerequisites=["market_context"])
    ctx = _make_context(upstream_results={"market_context": failed_result})
    can, reason = skill.can_run(ctx)
    assert can is False
    assert "did not succeed" in reason
    assert "FAILURE" in reason


def test_can_run_fails_on_missing_required_input():
    """can_run() rejects execution when a required context field is empty."""
    skill = _make_skill(required_inputs=["symbol"])
    ctx = _make_context(symbol="")
    can, reason = skill.can_run(ctx)
    assert can is False
    assert "symbol" in reason


def test_validate_result_passes_success_with_output():
    """validate_result() passes when a SUCCESS result has non-empty output."""
    skill = _make_skill()
    result = SkillResult(
        skill_id="test",
        status=SkillStatus.SUCCESS,
        output={"key": "value"},
    )
    valid, reason = skill.validate_result(result)
    assert valid is True
    assert reason == ""


def test_validate_result_fails_success_without_output():
    """validate_result() fails when a SUCCESS result has empty output."""
    skill = _make_skill()
    result = SkillResult(
        skill_id="test",
        status=SkillStatus.SUCCESS,
        output={},
    )
    valid, reason = skill.validate_result(result)
    assert valid is False
    assert "empty" in reason.lower()


def test_validate_result_passes_failure_without_output():
    """validate_result() passes when a non-SUCCESS result has empty output."""
    skill = _make_skill()
    result = SkillResult(
        skill_id="test",
        status=SkillStatus.FAILURE,
        output={},
    )
    valid, reason = skill.validate_result(result)
    assert valid is True


# ---------------------------------------------------------------------------
# SkillRegistry tests
# ---------------------------------------------------------------------------

def test_register_and_get():
    """A registered skill can be retrieved by ID."""
    registry = SkillRegistry()
    skill = _make_skill(skill_id="alpha")
    registry.register(skill, [AgentType.TRADE_DECISION])
    assert registry.get("alpha") is skill


def test_register_with_multiple_agents():
    """A single skill can be registered for multiple agent types."""
    registry = SkillRegistry()
    skill = _make_skill(skill_id="shared")
    registry.register(
        skill, [AgentType.TRADE_DECISION, AgentType.FAILURE_ANALYSIS]
    )
    trade_skills = registry.get_for_agent(AgentType.TRADE_DECISION)
    analysis_skills = registry.get_for_agent(AgentType.FAILURE_ANALYSIS)
    assert skill in trade_skills
    assert skill in analysis_skills


def test_unregister_removes_skill():
    """An unregistered skill is no longer retrievable or assigned to agents."""
    registry = SkillRegistry()
    skill = _make_skill(skill_id="temp")
    registry.register(skill, [AgentType.TRADE_DECISION])
    registry.unregister("temp")
    assert registry.get("temp") is None
    assert skill not in registry.get_for_agent(AgentType.TRADE_DECISION)


def test_get_returns_none_for_unknown():
    """Requesting an unregistered skill_id returns None."""
    registry = SkillRegistry()
    assert registry.get("does_not_exist") is None


def test_get_for_agent_returns_permitted_skills():
    """get_for_agent() only returns skills registered for that agent type."""
    registry = SkillRegistry()
    trade_only = _make_skill(skill_id="trade_only")
    analysis_only = _make_skill(skill_id="analysis_only")
    registry.register(trade_only, [AgentType.TRADE_DECISION])
    registry.register(analysis_only, [AgentType.FAILURE_ANALYSIS])

    trade_skills = registry.get_for_agent(AgentType.TRADE_DECISION)
    assert trade_only in trade_skills
    assert analysis_only not in trade_skills


def test_get_for_agent_excludes_disabled():
    """Disabled skills are excluded from get_for_agent() results."""
    registry = SkillRegistry()
    skill = _make_skill(skill_id="toggle_me")
    registry.register(skill, [AgentType.TRADE_DECISION])
    registry.disable("toggle_me")
    assert skill not in registry.get_for_agent(AgentType.TRADE_DECISION)


def test_disable_and_enable():
    """Disabling then re-enabling a skill restores it to agent queries."""
    registry = SkillRegistry()
    skill = _make_skill(skill_id="on_off")
    registry.register(skill, [AgentType.TRADE_DECISION])

    registry.disable("on_off")
    assert skill not in registry.get_for_agent(AgentType.TRADE_DECISION)

    registry.enable("on_off")
    assert skill in registry.get_for_agent(AgentType.TRADE_DECISION)


def test_is_enabled():
    """is_enabled() reflects registration and disabled state."""
    registry = SkillRegistry()
    skill = _make_skill(skill_id="checker")
    registry.register(skill, [AgentType.TRADE_DECISION])

    assert registry.is_enabled("checker") is True
    registry.disable("checker")
    assert registry.is_enabled("checker") is False
    registry.enable("checker")
    assert registry.is_enabled("checker") is True
    # Unregistered skill is not enabled
    assert registry.is_enabled("unknown") is False


def test_list_all_returns_metadata():
    """list_all() returns a dict per skill with correct metadata fields."""
    registry = SkillRegistry()
    skill = _make_skill(
        skill_id="meta_skill",
        name="Meta Skill",
        description="skill with metadata",
        version="3.0.0",
        execution_type=SkillExecutionType.HYBRID,
        risk_level=SkillRiskLevel.HIGH,
        requires_human_review=True,
    )
    registry.register(
        skill, [AgentType.TRADE_DECISION, AgentType.FAILURE_ANALYSIS]
    )
    items = registry.list_all()
    assert len(items) == 1

    entry = items[0]
    assert entry["skill_id"] == "meta_skill"
    assert entry["name"] == "Meta Skill"
    assert entry["description"] == "skill with metadata"
    assert entry["version"] == "3.0.0"
    assert entry["execution_type"] == "HYBRID"
    assert entry["risk_level"] == "HIGH"
    assert entry["requires_human_review"] is True
    assert entry["enabled"] is True
    assert "TRADE_DECISION" in entry["agents"]
    assert "FAILURE_ANALYSIS" in entry["agents"]


# ---------------------------------------------------------------------------
# SkillExecutor tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_success():
    """Executor wraps a successful skill result with timing information."""
    skill = _make_skill(skill_id="fast_skill")
    ctx = _make_context()
    executor = SkillExecutor()

    result = await executor.execute(skill, ctx)
    assert result.status == SkillStatus.SUCCESS
    assert result.skill_id == "fast_skill"
    assert result.output == {"result": "ok"}
    assert result.execution_time_ms > 0


@pytest.mark.asyncio
async def test_execute_timeout():
    """Executor produces a TIMEOUT result when a skill exceeds its time limit."""

    async def slow_fn(self, ctx):
        await asyncio.sleep(10)
        return self._success({"never": "reached"})

    skill = _make_skill(
        skill_id="slow_skill",
        timeout_seconds=0.05,
        execute_fn=slow_fn,
    )
    ctx = _make_context()
    executor = SkillExecutor()

    result = await executor.execute(skill, ctx)
    assert result.status == SkillStatus.TIMEOUT
    assert result.skill_id == "slow_skill"
    assert "Timed out" in result.message


@pytest.mark.asyncio
async def test_execute_exception_becomes_error():
    """Executor catches unhandled exceptions and wraps them as ERROR results."""

    async def exploding_fn(self, ctx):
        raise ValueError("kaboom")

    skill = _make_skill(skill_id="broken_skill", execute_fn=exploding_fn)
    ctx = _make_context()
    executor = SkillExecutor()

    result = await executor.execute(skill, ctx)
    assert result.status == SkillStatus.ERROR
    assert result.skill_id == "broken_skill"
    assert "kaboom" in result.message
    assert result.error == "kaboom"
    assert result.execution_time_ms > 0


@pytest.mark.asyncio
async def test_execute_validation_failure():
    """Executor downgrades a SUCCESS with empty output to FAILURE via validation."""

    async def empty_success_fn(self, ctx):
        # Return SUCCESS but with empty output - validation should catch this
        return SkillResult(
            skill_id=self.skill_id,
            status=SkillStatus.SUCCESS,
            output={},
            version=self.version,
        )

    skill = _make_skill(skill_id="bad_output", execute_fn=empty_success_fn)
    ctx = _make_context()
    executor = SkillExecutor()

    result = await executor.execute(skill, ctx)
    assert result.status == SkillStatus.FAILURE
    assert "Validation failed" in result.message


# ---------------------------------------------------------------------------
# SkillRouter tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_runs_all_skills_in_order():
    """Pipeline executes skills sequentially and collects all results."""
    call_order: list[str] = []

    async def tracking_fn(self, ctx):
        call_order.append(self.skill_id)
        return self._success({"step": self.skill_id})

    skills = [
        _make_skill(skill_id="step_1", execute_fn=tracking_fn),
        _make_skill(skill_id="step_2", execute_fn=tracking_fn),
        _make_skill(skill_id="step_3", execute_fn=tracking_fn),
    ]
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    pipeline = await router.run_pipeline(skills, ctx)
    assert call_order == ["step_1", "step_2", "step_3"]
    assert len(pipeline.results) == 3
    assert all(r.status == SkillStatus.SUCCESS for r in pipeline.results)
    assert pipeline.completed is True
    assert pipeline.short_circuited is False


@pytest.mark.asyncio
async def test_pipeline_injects_upstream_results():
    """Each skill's result is injected into ctx.upstream_results for downstream skills."""
    captured_upstream: dict[str, SkillResult] = {}

    async def capture_fn(self, ctx):
        captured_upstream.update(ctx.upstream_results)
        return self._success({"data": self.skill_id})

    skills = [
        _make_skill(skill_id="producer"),
        _make_skill(skill_id="consumer", execute_fn=capture_fn),
    ]
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    await router.run_pipeline(skills, ctx)
    # By the time consumer runs, producer's result should be in upstream
    assert "producer" in captured_upstream
    assert captured_upstream["producer"].status == SkillStatus.SUCCESS


@pytest.mark.asyncio
async def test_pipeline_skips_skill_with_failed_prerequisites():
    """A skill whose can_run() fails is skipped and added to skipped_skills."""
    skills = [
        _make_skill(skill_id="optional", prerequisites=["nonexistent"]),
    ]
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    pipeline = await router.run_pipeline(skills, ctx)
    assert "optional" in pipeline.skipped_skills
    assert len(pipeline.results) == 1
    assert pipeline.results[0].status == SkillStatus.SKIPPED


@pytest.mark.asyncio
async def test_pipeline_short_circuits_on_critical_failure():
    """Pipeline stops after a CRITICAL risk skill fails."""

    async def fail_fn(self, ctx):
        return self._failure("critical check failed")

    skills = [
        _make_skill(
            skill_id="critical_gate",
            risk_level=SkillRiskLevel.CRITICAL,
            execute_fn=fail_fn,
        ),
        _make_skill(skill_id="should_not_run"),
    ]
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    pipeline = await router.run_pipeline(
        skills, ctx, short_circuit_on_critical=True
    )
    assert pipeline.short_circuited is True
    assert pipeline.completed is False
    assert "critical_gate" in pipeline.short_circuit_reason
    assert "critical_gate" in pipeline.failed_skills
    # Only one result recorded - second skill never ran
    assert len(pipeline.results) == 1


@pytest.mark.asyncio
async def test_pipeline_no_short_circuit_when_disabled():
    """Pipeline continues past CRITICAL failure when short_circuit_on_critical=False."""
    call_order: list[str] = []

    async def fail_fn(self, ctx):
        call_order.append(self.skill_id)
        return self._failure("critical check failed")

    async def success_fn(self, ctx):
        call_order.append(self.skill_id)
        return self._success({"ok": True})

    skills = [
        _make_skill(
            skill_id="critical_gate",
            risk_level=SkillRiskLevel.CRITICAL,
            execute_fn=fail_fn,
        ),
        _make_skill(skill_id="runs_anyway", execute_fn=success_fn),
    ]
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    pipeline = await router.run_pipeline(
        skills, ctx, short_circuit_on_critical=False
    )
    assert pipeline.short_circuited is False
    assert call_order == ["critical_gate", "runs_anyway"]
    assert len(pipeline.results) == 2


@pytest.mark.asyncio
async def test_pipeline_run_all_ignores_failures():
    """run_all=True forces execution of all skills even after CRITICAL failure."""
    call_order: list[str] = []

    async def fail_fn(self, ctx):
        call_order.append(self.skill_id)
        return self._failure("broke")

    async def success_fn(self, ctx):
        call_order.append(self.skill_id)
        return self._success({"ok": True})

    skills = [
        _make_skill(
            skill_id="blocker",
            risk_level=SkillRiskLevel.CRITICAL,
            execute_fn=fail_fn,
        ),
        _make_skill(skill_id="survivor", execute_fn=success_fn),
    ]
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    pipeline = await router.run_pipeline(
        skills, ctx, short_circuit_on_critical=True, run_all=True
    )
    assert pipeline.short_circuited is False
    assert call_order == ["blocker", "survivor"]
    assert "blocker" in pipeline.failed_skills
    assert len(pipeline.results) == 2


@pytest.mark.asyncio
async def test_pipeline_empty_skills_list():
    """Running an empty pipeline returns a clean default result."""
    ctx = _make_context()
    executor = SkillExecutor()
    router = SkillRouter(executor)

    pipeline = await router.run_pipeline([], ctx)
    assert isinstance(pipeline, SkillPipelineResult)
    assert pipeline.completed is True
    assert pipeline.results == []
    assert pipeline.failed_skills == []
    assert pipeline.skipped_skills == []
    assert pipeline.total_execution_time_ms == 0.0
    assert pipeline.short_circuited is False
