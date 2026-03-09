"""
Code Registration skill.

Registers the validated and verified strategy so it is available
for live backtesting:

    1. Compiles the signal function and inserts it into the
       SIGNAL_GENERATORS runtime dict.
    2. Optionally persists the strategy source to the database
       via a GeneratedStrategy model (when a session_factory is
       available in ctx.settings).

Deterministic - no model calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)

logger = logging.getLogger(__name__)


def _compile_signal_fn(source_code: str) -> callable:
    """Compile source code and return the signal_fn callable."""
    safe_builtins = {
        "Decimal": Decimal,
        "float": float,
        "int": int,
        "str": str,
        "min": min,
        "max": max,
        "abs": abs,
        "sum": sum,
        "len": len,
        "range": range,
        "list": list,
        "dict": dict,
        "round": round,
        "bool": bool,
        "tuple": tuple,
        "True": True,
        "False": False,
        "None": None,
        "__builtins__": {},
        "__import__": __import__,
    }

    code_obj = compile(source_code, "<generated_strategy>", "exec")
    namespace: dict = dict(safe_builtins)
    exec(code_obj, namespace)  # noqa: S102

    fn = namespace.get("signal_fn")
    if fn is None:
        raise ValueError("Compiled code does not define 'signal_fn'")
    return fn


def _wrap_signal_fn(fn: callable) -> callable:
    """
    Wrap the generated signal_fn to return proper SignalSide enums.

    Generated templates return plain strings ("BUY", "SELL", "HOLD")
    for safety sandbox reasons. This wrapper converts them to the
    SignalSide enum expected by BacktestEngine.
    """
    from app.backtest.engine import SignalSide

    _SIDE_MAP = {
        "BUY": SignalSide.BUY,
        "SELL": SignalSide.SELL,
        "HOLD": SignalSide.HOLD,
    }

    def wrapped(bar, params, state):
        side_str, price, reason = fn(bar, params, state)
        # Convert string to SignalSide enum
        if isinstance(side_str, str):
            side = _SIDE_MAP.get(side_str, SignalSide.HOLD)
        else:
            side = side_str
        return side, price, reason

    return wrapped


class CodeRegistrationSkill(BaseSkill):
    """Register the generated strategy in SIGNAL_GENERATORS."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "code_registration"

    @property
    def name(self) -> str:
        return "Code Registration"

    @property
    def description(self) -> str:
        return (
            "Registers the generated strategy function in the "
            "SIGNAL_GENERATORS dict and optionally persists to DB."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.HIGH

    @property
    def required_inputs(self) -> list[str]:
        return ["settings"]

    @property
    def prerequisites(self) -> list[str]:
        return ["backtest_verification"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Verify backtest passed
        bt_result = ctx.upstream_results.get("backtest_verification")
        if bt_result is None or bt_result.status != SkillStatus.SUCCESS:
            return self._skip(
                "Skipping registration because backtest_verification "
                "did not succeed."
            )

        passed = bt_result.output.get("passed", False)
        if not passed:
            return self._skip(
                "Skipping registration because backtest verification "
                "did not pass."
            )

        # Get source code and metadata from code_generation
        gen_result = ctx.upstream_results.get("code_generation")
        if gen_result is None or gen_result.status != SkillStatus.SUCCESS:
            return self._failure("code_generation result not available")

        source_code = gen_result.output.get("source_code", "")
        strategy_name = gen_result.output.get("strategy_name", "")
        default_params = gen_result.output.get("default_params", {})
        params_schema = gen_result.output.get("params_schema", {})
        category = gen_result.output.get("category", "")

        if not strategy_name:
            return self._failure("No strategy_name found in generation output")

        # --- Step 1: Register in SIGNAL_GENERATORS at runtime ---
        try:
            raw_fn = _compile_signal_fn(source_code)
            wrapped_fn = _wrap_signal_fn(raw_fn)

            from app.backtest.engine import SIGNAL_GENERATORS
            SIGNAL_GENERATORS[strategy_name] = wrapped_fn

            logger.info(
                "Registered strategy '%s' in SIGNAL_GENERATORS. "
                "Total strategies: %d",
                strategy_name,
                len(SIGNAL_GENERATORS),
            )
        except Exception as exc:
            return self._failure(
                f"Failed to register strategy at runtime: {exc}"
            )

        # --- Step 2: Optionally persist to DB ---
        persisted = False
        db_id = None

        session_factory = ctx.settings.get("session_factory")
        if session_factory is not None:
            try:
                persisted, db_id = await self._persist_to_db(
                    session_factory=session_factory,
                    strategy_name=strategy_name,
                    source_code=source_code,
                    category=category,
                    default_params=default_params,
                    params_schema=params_schema,
                    request_text=ctx.code_modification_request,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to persist strategy '%s' to DB: %s",
                    strategy_name,
                    exc,
                )
                # Non-fatal: the runtime registration already succeeded

        return self._success(
            output={
                "registered": True,
                "strategy_name": strategy_name,
                "available_in": "SIGNAL_GENERATORS",
                "persisted_to_db": persisted,
                "db_id": str(db_id) if db_id else None,
                "default_params": default_params,
            },
            message=(
                f"Strategy '{strategy_name}' registered in "
                f"SIGNAL_GENERATORS and "
                f"{'persisted to DB' if persisted else 'not persisted (no session_factory)'}."
            ),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _persist_to_db(
        session_factory,
        strategy_name: str,
        source_code: str,
        category: str,
        default_params: dict,
        params_schema: dict,
        request_text: str,
    ) -> tuple[bool, object]:
        """
        Persist the generated strategy to the database.

        Uses the strategy_loader module if available, falling back
        to direct model insert.

        Returns (persisted: bool, db_id).
        """
        try:
            from app.backtest.strategy_loader import register_strategy

            db_id = await register_strategy(
                session_factory=session_factory,
                name=strategy_name,
                source_code=source_code,
                category=category,
                default_params=default_params,
                params_schema=params_schema,
                description=request_text,
            )
            return True, db_id
        except ImportError:
            logger.debug(
                "strategy_loader not available, skipping DB persistence"
            )
            return False, None
        except Exception as exc:
            logger.warning("DB persistence failed: %s", exc)
            return False, None
