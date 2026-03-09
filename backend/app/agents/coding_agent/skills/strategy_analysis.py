"""
Strategy Analysis skill.

Analyzes the user's code modification request and any existing
strategy code to determine what kind of strategy to create or modify.
Extracts parameters, signal logic patterns, and categorises the
request for downstream code generation.

Deterministic skill - no model calls, pure text parsing.
"""

from __future__ import annotations

import re

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)

# ---------------------------------------------------------------------------
# Keyword-to-category mapping
# ---------------------------------------------------------------------------

_STRATEGY_KEYWORDS: dict[str, list[str]] = {
    "momentum": [
        "momentum", "price change", "rate of change", "roc",
        "velocity", "price velocity",
    ],
    "dual_ma": [
        "moving average", "ma crossover", "sma", "ema",
        "crossover", "dual ma", "golden cross", "death cross",
    ],
    "rsi_variant": [
        "rsi", "relative strength", "oscillator", "overbought",
        "oversold", "stochastic",
    ],
    "channel_breakout": [
        "breakout", "channel", "donchian", "high low",
        "range breakout", "price channel",
    ],
    "volatility_mean_revert": [
        "volatility", "mean revert", "mean reversion", "vol",
        "std dev", "standard deviation", "bollinger",
        "reversion", "dip buy",
    ],
}


def _classify_request(text: str) -> str:
    """Return the best-matching strategy category for *text*."""
    text_lower = text.lower()
    scores: dict[str, int] = {cat: 0 for cat in _STRATEGY_KEYWORDS}

    for category, keywords in _STRATEGY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[category] += 1

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] == 0:
        # Fallback: default to momentum if nothing matched
        return "momentum"
    return best


def _extract_suggested_params(text: str) -> dict[str, str]:
    """
    Pull out explicit numeric parameter hints from the request.

    Looks for patterns like ``period=20``, ``threshold 0.5``,
    ``lookback: 14``, etc.
    """
    params: dict[str, str] = {}
    # pattern: word followed by = or : or space, then a number
    for match in re.finditer(
        r"(\b[a-z_]+)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)", text.lower()
    ):
        params[match.group(1)] = match.group(2)
    return params


def _extract_existing_code_info(code: str) -> dict:
    """
    Analyze existing strategy source code to extract metadata.

    Returns dict with function_names, parameter_keys, and
    recognised signal patterns.
    """
    info: dict = {
        "function_names": [],
        "parameter_keys": [],
        "signal_patterns": [],
    }

    # Function names
    for match in re.finditer(r"def\s+(\w+)\s*\(", code):
        info["function_names"].append(match.group(1))

    # params.get("key", ...) calls
    for match in re.finditer(r'params\.get\(\s*["\'](\w+)["\']', code):
        info["parameter_keys"].append(match.group(1))

    # Detect signal patterns
    if "price_history" in code or "prices" in code:
        info["signal_patterns"].append("price_history_buffer")
    if "sma" in code.lower() or "moving" in code.lower():
        info["signal_patterns"].append("moving_average")
    if "rsi" in code.lower():
        info["signal_patterns"].append("rsi")
    if "breakout" in code.lower() or "highs" in code:
        info["signal_patterns"].append("breakout")
    if "volatility" in code.lower() or "std" in code.lower():
        info["signal_patterns"].append("volatility")

    return info


class StrategyAnalysisSkill(BaseSkill):
    """Analyze the strategy request and existing code to plan generation."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "strategy_analysis"

    @property
    def name(self) -> str:
        return "Strategy Analysis"

    @property
    def description(self) -> str:
        return (
            "Analyzes the code modification request and any existing strategy "
            "code to determine strategy type, parameters, and signal logic."
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
        return SkillRiskLevel.LOW

    @property
    def required_inputs(self) -> list[str]:
        return ["code_modification_request"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        request = ctx.code_modification_request.strip()
        if not request:
            return self._failure("code_modification_request is empty")

        # Determine create vs modify
        has_existing_code = bool(ctx.strategy_code and ctx.strategy_code.strip())
        request_type = "modify" if has_existing_code else "create"

        # Classify what kind of strategy this is
        category = _classify_request(request)

        # Extract any explicit parameter hints from the request text
        suggested_params = _extract_suggested_params(request)

        # Build a strategy name from the request or existing name
        strategy_name = ctx.generated_strategy_name
        if not strategy_name:
            # Derive a snake_case name from the category
            strategy_name = f"generated_{category}"

        # Analyse existing code if present
        existing_patterns: list[str] = []
        existing_info: dict = {}
        if has_existing_code:
            existing_info = _extract_existing_code_info(ctx.strategy_code)
            existing_patterns = existing_info.get("signal_patterns", [])

        analysis = {
            "request_type": request_type,
            "strategy_name": strategy_name,
            "description": request,
            "category": category,
            "parameters": list(suggested_params.keys()),
            "suggested_param_values": suggested_params,
            "signal_logic": category,
            "existing_patterns": existing_patterns,
            "existing_code_info": existing_info,
        }

        return self._success(
            output={"analysis": analysis},
            message=(
                f"Classified as '{category}' strategy "
                f"({request_type}). Name: {strategy_name}."
            ),
        )
