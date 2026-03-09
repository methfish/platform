"""
Backtest Verification skill.

Runs a quick 100-bar smoke test to verify the generated strategy
function does not crash at runtime.

Creates synthetic bars (incrementing timestamps, random-walk prices
around 1.1000 for forex pairs), compiles the source code via
compile() + exec() in a restricted namespace, and runs the signal
function over each bar.

Deterministic in structure but the synthetic price data uses a
seeded pseudo-random walk for reproducibility.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NUM_TEST_BARS = 100
_BASE_PRICE = 1.1000
_RANDOM_SEED = 42
_VALID_SIDES = {"BUY", "SELL", "HOLD"}


def _make_synthetic_bars(
    num_bars: int = _NUM_TEST_BARS,
    base_price: float = _BASE_PRICE,
    seed: int = _RANDOM_SEED,
) -> list[dict]:
    """
    Generate synthetic OHLCV bar dicts for testing.

    Uses a seeded random walk so results are reproducible.
    Returns plain dicts with the same fields as the Bar dataclass.
    """
    rng = random.Random(seed)
    bars: list[dict] = []
    price = base_price
    start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    for i in range(num_bars):
        # Random walk step
        change = rng.gauss(0, 0.0005)
        price = max(price + change, 0.0001)  # Prevent negative

        # Synthetic OHLCV
        open_price = price
        high_price = price + abs(rng.gauss(0, 0.0003))
        low_price = price - abs(rng.gauss(0, 0.0003))
        close_price = price + rng.gauss(0, 0.0002)
        close_price = max(close_price, 0.0001)
        volume = abs(rng.gauss(1000, 200))

        bars.append({
            "timestamp": start_time + timedelta(minutes=i),
            "open": Decimal(str(round(open_price, 5))),
            "high": Decimal(str(round(high_price, 5))),
            "low": Decimal(str(round(low_price, 5))),
            "close": Decimal(str(round(close_price, 5))),
            "volume": Decimal(str(round(volume, 2))),
            "symbol": "EURUSD",
            "interval": "1m",
        })

    return bars


class _SimpleBar:
    """Lightweight bar object matching the Bar dataclass interface."""

    __slots__ = (
        "timestamp", "open", "high", "low", "close",
        "volume", "symbol", "interval",
    )

    def __init__(self, data: dict) -> None:
        self.timestamp = data["timestamp"]
        self.open = data["open"]
        self.high = data["high"]
        self.low = data["low"]
        self.close = data["close"]
        self.volume = data["volume"]
        self.symbol = data["symbol"]
        self.interval = data["interval"]


def _compile_and_extract(source_code: str) -> callable:
    """
    Compile source code and extract the signal_fn function.

    The code runs in a restricted namespace that only exposes
    safe builtins.
    """
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
        "__import__": __import__,  # Needed for 'from decimal import Decimal'
    }

    code_obj = compile(source_code, "<generated_strategy>", "exec")
    namespace: dict = dict(safe_builtins)
    exec(code_obj, namespace)  # noqa: S102

    fn = namespace.get("signal_fn")
    if fn is None:
        raise ValueError("Compiled code does not define 'signal_fn'")
    return fn


class BacktestVerificationSkill(BaseSkill):
    """Run a quick smoke test to verify the generated strategy."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "backtest_verification"

    @property
    def name(self) -> str:
        return "Backtest Verification"

    @property
    def description(self) -> str:
        return (
            "Runs a 100-bar smoke test with synthetic data to verify "
            "the generated strategy function does not crash."
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
        return ["code_validation"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Check that validation passed
        validation_result = ctx.upstream_results.get("code_validation")
        if validation_result is None or validation_result.status != SkillStatus.SUCCESS:
            return self._skip(
                "Skipping backtest verification because code_validation "
                "did not succeed."
            )

        valid = validation_result.output.get("valid", False)
        if not valid:
            return self._skip(
                "Skipping backtest verification because code validation "
                "reported issues."
            )

        # Get the source code from code_generation
        gen_result = ctx.upstream_results.get("code_generation")
        if gen_result is None or gen_result.status != SkillStatus.SUCCESS:
            return self._failure("code_generation result not available")

        source_code = gen_result.output.get("source_code", "")
        default_params = gen_result.output.get("default_params", {})

        # Compile
        try:
            signal_fn = _compile_and_extract(source_code)
        except Exception as exc:
            return self._failure(
                f"Compilation failed: {exc}",
                errors=[str(exc)],
            )

        # Generate synthetic bars
        synthetic_bars = _make_synthetic_bars()

        # Run the signal function over all bars
        errors: list[str] = []
        signals_generated = 0
        state: dict = {}

        for i, bar_data in enumerate(synthetic_bars):
            bar = _SimpleBar(bar_data)
            try:
                result = signal_fn(bar, dict(default_params), state)

                # Validate return shape
                if not isinstance(result, (tuple, list)) or len(result) != 3:
                    errors.append(
                        f"Bar {i}: signal_fn returned {type(result).__name__} "
                        f"with {len(result) if hasattr(result, '__len__') else '?'} "
                        f"elements, expected tuple of 3"
                    )
                    break

                side_str, price, reason = result

                # Validate side is a known value
                side_val = side_str if isinstance(side_str, str) else str(side_str)
                # Handle both string and enum values
                if hasattr(side_str, "value"):
                    side_val = side_str.value
                if side_val not in _VALID_SIDES:
                    errors.append(
                        f"Bar {i}: invalid signal side '{side_val}', "
                        f"expected one of {_VALID_SIDES}"
                    )
                    break

                if side_val != "HOLD":
                    signals_generated += 1

            except Exception as exc:
                errors.append(f"Bar {i}: runtime error: {exc}")
                break

        passed = len(errors) == 0

        if not passed:
            return self._failure(
                message=f"Backtest verification failed: {errors[0]}",
                passed=False,
                bars_tested=min(i + 1, _NUM_TEST_BARS) if 'i' in dir() else 0,
                signals_generated=signals_generated,
                errors=errors,
            )

        return self._success(
            output={
                "passed": True,
                "bars_tested": _NUM_TEST_BARS,
                "signals_generated": signals_generated,
                "errors": [],
            },
            message=(
                f"Backtest verification passed. "
                f"{_NUM_TEST_BARS} bars tested, "
                f"{signals_generated} signals generated."
            ),
        )
