"""
Code Generation skill.

Generates a Python signal function from deterministic templates
based on the strategy category identified by strategy_analysis.

Each template follows the exact signature required by the backtest engine:

    def signal_fn(bar: Bar, params: dict, state: dict)
        -> tuple[SignalSide, Decimal, str]

Generated code uses ONLY safe builtins: Decimal, float, int, str,
min, max, abs, sum, len, range, list, dict, round.

Execution type is HYBRID because the template selection is
deterministic but parameter defaults may be adapted from the
user's request text.
"""

from __future__ import annotations

import textwrap
from typing import Any

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)

# ---------------------------------------------------------------------------
# Strategy Templates
# ---------------------------------------------------------------------------

_TEMPLATE_MOMENTUM = textwrap.dedent('''\
def signal_fn(bar, params, state):
    """Momentum: buy/sell when price change over N bars exceeds threshold."""
    from decimal import Decimal

    period = int(params.get("period", {period}))
    threshold = float(params.get("threshold", {threshold}))

    prices = state.setdefault("price_history", [])
    prices.append(float(bar.close))

    if len(prices) < period + 1:
        return ("HOLD", Decimal("0"), "warming up")

    # Trim excess history
    if len(prices) > period * 3:
        state["price_history"] = prices[-period * 3:]
        prices = state["price_history"]

    old_price = prices[-period - 1]
    if old_price == 0:
        return ("HOLD", Decimal("0"), "zero price")

    momentum = (prices[-1] - old_price) / old_price

    if momentum > threshold:
        return ("BUY", bar.close, "momentum=%.4f > %.4f" % (momentum, threshold))

    if momentum < -threshold:
        return ("SELL", bar.close, "momentum=%.4f < -%.4f" % (momentum, threshold))

    return ("HOLD", Decimal("0"), "momentum=%.4f" % momentum)
''')

_TEMPLATE_DUAL_MA = textwrap.dedent('''\
def signal_fn(bar, params, state):
    """Dual Moving Average crossover."""
    from decimal import Decimal

    fast_period = int(params.get("fast_period", {fast_period}))
    slow_period = int(params.get("slow_period", {slow_period}))

    prices = state.setdefault("price_history", [])
    prices.append(float(bar.close))

    if len(prices) < slow_period:
        return ("HOLD", Decimal("0"), "warming up")

    # Trim excess history
    if len(prices) > slow_period * 3:
        state["price_history"] = prices[-slow_period * 3:]
        prices = state["price_history"]

    fast_sma = sum(prices[-fast_period:]) / fast_period
    slow_sma = sum(prices[-slow_period:]) / slow_period

    fast_above = fast_sma > slow_sma
    prev_fast_above = state.get("prev_fast_above")
    state["prev_fast_above"] = fast_above

    if prev_fast_above is None:
        return ("HOLD", Decimal("0"), "initialized crossover")

    if fast_above and not prev_fast_above:
        return ("BUY", bar.close, "fast SMA (%.4f) crossed above slow (%.4f)" % (fast_sma, slow_sma))

    if not fast_above and prev_fast_above:
        return ("SELL", bar.close, "fast SMA (%.4f) crossed below slow (%.4f)" % (fast_sma, slow_sma))

    return ("HOLD", Decimal("0"), "")
''')

_TEMPLATE_RSI_VARIANT = textwrap.dedent('''\
def signal_fn(bar, params, state):
    """RSI with configurable smoothing."""
    from decimal import Decimal

    rsi_period = int(params.get("rsi_period", {rsi_period}))
    oversold = float(params.get("oversold", {oversold}))
    overbought = float(params.get("overbought", {overbought}))
    smoothing = params.get("smoothing", "wilder")  # "wilder" or "sma"

    prices = state.setdefault("price_history", [])
    prices.append(float(bar.close))

    if len(prices) < rsi_period + 1:
        return ("HOLD", Decimal("0"), "warming up")

    avg_gain = state.get("avg_gain")
    avg_loss = state.get("avg_loss")

    if avg_gain is None:
        # Initial calculation over first rsi_period changes
        gains = []
        losses = []
        for i in range(len(prices) - rsi_period, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))
        avg_gain = sum(gains) / rsi_period
        avg_loss = sum(losses) / rsi_period
    else:
        change = prices[-1] - prices[-2]
        current_gain = max(change, 0.0)
        current_loss = abs(min(change, 0.0))
        if smoothing == "wilder":
            avg_gain = (avg_gain * (rsi_period - 1) + current_gain) / rsi_period
            avg_loss = (avg_loss * (rsi_period - 1) + current_loss) / rsi_period
        else:
            # Simple moving average of gains/losses
            gains_list = state.setdefault("gains_list", [])
            losses_list = state.setdefault("losses_list", [])
            gains_list.append(current_gain)
            losses_list.append(current_loss)
            if len(gains_list) > rsi_period:
                gains_list[:] = gains_list[-rsi_period:]
                losses_list[:] = losses_list[-rsi_period:]
            avg_gain = sum(gains_list) / len(gains_list)
            avg_loss = sum(losses_list) / len(losses_list)

    state["avg_gain"] = avg_gain
    state["avg_loss"] = avg_loss

    # Trim excess history
    if len(prices) > rsi_period * 3:
        state["price_history"] = prices[-rsi_period * 3:]

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    if rsi < oversold:
        return ("BUY", bar.close, "RSI=%.1f < %s" % (rsi, oversold))

    if rsi > overbought:
        return ("SELL", bar.close, "RSI=%.1f > %s" % (rsi, overbought))

    return ("HOLD", Decimal("0"), "RSI=%.1f" % rsi)
''')

_TEMPLATE_CHANNEL_BREAKOUT = textwrap.dedent('''\
def signal_fn(bar, params, state):
    """Donchian channel breakout with configurable lookback."""
    from decimal import Decimal

    lookback = int(params.get("lookback", {lookback}))

    highs = state.setdefault("highs", [])
    lows = state.setdefault("lows", [])

    highs.append(float(bar.high))
    lows.append(float(bar.low))

    if len(highs) < lookback:
        return ("HOLD", Decimal("0"), "warming up")

    # Trim excess history
    if len(highs) > lookback * 3:
        state["highs"] = highs[-lookback * 3:]
        state["lows"] = lows[-lookback * 3:]
        highs = state["highs"]
        lows = state["lows"]

    # Channel is based on previous bars (exclude current bar)
    channel_high = max(highs[-lookback - 1:-1]) if len(highs) > lookback else max(highs[:-1])
    channel_low = min(lows[-lookback - 1:-1]) if len(lows) > lookback else min(lows[:-1])

    price = float(bar.close)

    if price > channel_high:
        return ("BUY", bar.close, "breakout above %.4f" % channel_high)

    if price < channel_low:
        return ("SELL", bar.close, "breakdown below %.4f" % channel_low)

    return ("HOLD", Decimal("0"), "in channel [%.4f, %.4f]" % (channel_low, channel_high))
''')

_TEMPLATE_VOLATILITY_MEAN_REVERT = textwrap.dedent('''\
def signal_fn(bar, params, state):
    """Volatility-based mean reversion: buy dips relative to recent vol."""
    from decimal import Decimal

    vol_period = int(params.get("vol_period", {vol_period}))
    entry_mult = float(params.get("entry_mult", {entry_mult}))
    exit_mult = float(params.get("exit_mult", {exit_mult}))

    prices = state.setdefault("price_history", [])
    prices.append(float(bar.close))

    if len(prices) < vol_period + 1:
        return ("HOLD", Decimal("0"), "warming up")

    # Trim excess history
    if len(prices) > vol_period * 3:
        state["price_history"] = prices[-vol_period * 3:]
        prices = state["price_history"]

    window = prices[-vol_period:]
    mean_price = sum(window) / len(window)
    variance = sum((p - mean_price) ** 2 for p in window) / len(window)
    std_dev = variance ** 0.5

    if std_dev == 0:
        return ("HOLD", Decimal("0"), "zero volatility")

    current = prices[-1]
    z_score = (current - mean_price) / std_dev

    if z_score < -entry_mult:
        return ("BUY", bar.close, "z=%.2f below -%.1f (vol dip)" % (z_score, entry_mult))

    if z_score > exit_mult:
        return ("SELL", bar.close, "z=%.2f above +%.1f (vol exit)" % (z_score, exit_mult))

    return ("HOLD", Decimal("0"), "z=%.2f" % z_score)
''')

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict[str, Any]] = {
    "momentum": {
        "source": _TEMPLATE_MOMENTUM,
        "default_params": {"period": 10, "threshold": 0.005},
        "params_schema": {
            "period": {"type": "int", "min": 2, "max": 200, "description": "Lookback bars for momentum calculation"},
            "threshold": {"type": "float", "min": 0.0001, "max": 0.1, "description": "Minimum price change ratio to trigger signal"},
        },
    },
    "dual_ma": {
        "source": _TEMPLATE_DUAL_MA,
        "default_params": {"fast_period": 10, "slow_period": 30},
        "params_schema": {
            "fast_period": {"type": "int", "min": 2, "max": 100, "description": "Fast moving average period"},
            "slow_period": {"type": "int", "min": 5, "max": 500, "description": "Slow moving average period"},
        },
    },
    "rsi_variant": {
        "source": _TEMPLATE_RSI_VARIANT,
        "default_params": {"rsi_period": 14, "oversold": 30, "overbought": 70, "smoothing": "wilder"},
        "params_schema": {
            "rsi_period": {"type": "int", "min": 2, "max": 100, "description": "RSI lookback period"},
            "oversold": {"type": "float", "min": 5, "max": 50, "description": "RSI oversold threshold"},
            "overbought": {"type": "float", "min": 50, "max": 95, "description": "RSI overbought threshold"},
            "smoothing": {"type": "str", "choices": ["wilder", "sma"], "description": "Smoothing method"},
        },
    },
    "channel_breakout": {
        "source": _TEMPLATE_CHANNEL_BREAKOUT,
        "default_params": {"lookback": 20},
        "params_schema": {
            "lookback": {"type": "int", "min": 5, "max": 200, "description": "Channel lookback period"},
        },
    },
    "volatility_mean_revert": {
        "source": _TEMPLATE_VOLATILITY_MEAN_REVERT,
        "default_params": {"vol_period": 20, "entry_mult": 2.0, "exit_mult": 2.0},
        "params_schema": {
            "vol_period": {"type": "int", "min": 5, "max": 200, "description": "Volatility lookback period"},
            "entry_mult": {"type": "float", "min": 0.5, "max": 5.0, "description": "Std-dev multiplier for entry"},
            "exit_mult": {"type": "float", "min": 0.5, "max": 5.0, "description": "Std-dev multiplier for exit"},
        },
    },
}


def _merge_params(
    default_params: dict[str, Any],
    suggested: dict[str, str],
) -> dict[str, Any]:
    """
    Merge user-suggested parameter values into the defaults.

    Only overrides keys that already exist in defaults (ignoring unknown
    keys). Coerces string values to the type of the default.
    """
    merged = dict(default_params)
    for key, str_val in suggested.items():
        if key in merged:
            target_type = type(merged[key])
            try:
                if target_type is int:
                    merged[key] = int(str_val)
                elif target_type is float:
                    merged[key] = float(str_val)
                else:
                    merged[key] = str_val
            except (ValueError, TypeError):
                pass  # Keep default on conversion failure
    return merged


def _render_template(template_source: str, params: dict[str, Any]) -> str:
    """
    Fill parameter placeholders in a template string.

    Placeholders are {param_name} inside the template and are
    replaced with the default values so the generated code has
    hard-coded fallback defaults.
    """
    rendered = template_source
    for key, value in params.items():
        placeholder = "{" + key + "}"
        rendered = rendered.replace(placeholder, repr(value))
    return rendered


class CodeGenerationSkill(BaseSkill):
    """Generate a Python signal function from deterministic templates."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "code_generation"

    @property
    def name(self) -> str:
        return "Code Generation"

    @property
    def description(self) -> str:
        return (
            "Generates a Python signal function using deterministic "
            "templates matched to the strategy category."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.HYBRID

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM

    @property
    def required_inputs(self) -> list[str]:
        return ["code_modification_request"]

    @property
    def prerequisites(self) -> list[str]:
        return ["strategy_analysis"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Pull analysis from upstream
        analysis_result = ctx.upstream_results.get("strategy_analysis")
        if analysis_result is None or analysis_result.status != SkillStatus.SUCCESS:
            return self._failure("strategy_analysis did not succeed")

        analysis = analysis_result.output.get("analysis", {})
        category = analysis.get("category", "momentum")
        strategy_name = analysis.get("strategy_name", "generated_strategy")
        suggested_params = analysis.get("suggested_param_values", {})

        # Look up the template
        template_info = _TEMPLATES.get(category)
        if template_info is None:
            return self._failure(
                f"No template available for category '{category}'. "
                f"Available: {list(_TEMPLATES.keys())}"
            )

        # Merge user-suggested params with defaults
        default_params = dict(template_info["default_params"])
        final_params = _merge_params(default_params, suggested_params)

        # Render the template with final parameter defaults
        source_code = _render_template(template_info["source"], final_params)

        return self._success(
            output={
                "source_code": source_code,
                "function_name": "signal_fn",
                "strategy_name": strategy_name,
                "category": category,
                "default_params": final_params,
                "params_schema": template_info["params_schema"],
            },
            message=(
                f"Generated '{category}' strategy code with "
                f"params: {final_params}."
            ),
        )
