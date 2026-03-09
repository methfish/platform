"""
Strategy loader — loads generated strategies from DB and registers them
in the SIGNAL_GENERATORS dict for use by the backtest engine.
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("pensy.backtest.strategy_loader")

# Restricted builtins for sandboxed execution
SAFE_BUILTINS = {
    "Decimal": __import__("decimal").Decimal,
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
    "True": True,
    "False": False,
    "None": None,
    "tuple": tuple,
}

# Maximum source code length
MAX_SOURCE_LENGTH = 5000

# Forbidden AST node types / patterns
FORBIDDEN_NAMES = {"exec", "eval", "open", "__import__", "compile", "globals", "locals", "getattr", "setattr", "delattr"}


def validate_source(source_code: str) -> tuple[bool, list[str]]:
    """Validate generated strategy source code for safety."""
    issues: list[str] = []

    if len(source_code) > MAX_SOURCE_LENGTH:
        issues.append(f"Source code too long: {len(source_code)} > {MAX_SOURCE_LENGTH}")
        return False, issues

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        issues.append(f"Syntax error: {e}")
        return False, issues

    # Walk AST to check for forbidden patterns
    for node in ast.walk(tree):
        # No imports allowed
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            issues.append(f"Import statement not allowed: {ast.dump(node)}")

        # No exec/eval/open etc
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                issues.append(f"Forbidden function call: {node.func.id}")

        # No dunder access
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            issues.append(f"Dunder attribute access not allowed: {node.attr}")

        if isinstance(node, ast.Name) and node.id.startswith("__"):
            issues.append(f"Dunder name not allowed: {node.id}")

    return len(issues) == 0, issues


def compile_strategy(
    name: str,
    source_code: str,
) -> Optional[Callable]:
    """
    Compile a strategy source code string into a callable signal function.

    The source code must define a function that matches the signal generator
    signature: (bar, params, state) -> (SignalSide, Decimal, str)

    Returns the compiled function, or None if compilation fails.
    """
    # Validate first
    valid, issues = validate_source(source_code)
    if not valid:
        logger.error("Strategy '%s' failed validation: %s", name, issues)
        return None

    try:
        # Build a restricted namespace
        from app.backtest.engine import SignalSide, Bar

        namespace: dict[str, Any] = {
            "__builtins__": SAFE_BUILTINS,
            "SignalSide": SignalSide,
            "Bar": Bar,
        }

        compiled = compile(source_code, f"<strategy:{name}>", "exec")
        exec(compiled, namespace)

        # Find the signal function (first callable that's not a class)
        signal_fn = None
        for key, val in namespace.items():
            if key.startswith("_"):
                continue
            if callable(val) and not isinstance(val, type):
                signal_fn = val
                break

        if signal_fn is None:
            logger.error("Strategy '%s' has no callable function", name)
            return None

        logger.info("Compiled strategy: %s -> %s", name, signal_fn.__name__)
        return signal_fn

    except Exception as e:
        logger.exception("Failed to compile strategy '%s': %s", name, e)
        return None


def register_strategy(name: str, source_code: str) -> bool:
    """
    Compile and register a strategy in SIGNAL_GENERATORS.

    Returns True if successful.
    """
    from app.backtest.engine import SIGNAL_GENERATORS

    fn = compile_strategy(name, source_code)
    if fn is None:
        return False

    SIGNAL_GENERATORS[name] = fn
    logger.info("Registered strategy '%s' in SIGNAL_GENERATORS (total: %d)", name, len(SIGNAL_GENERATORS))
    return True


async def load_strategies_from_db(session_factory) -> int:
    """
    Load all active GeneratedStrategy records from DB and register them.

    Called at startup to restore previously generated strategies.
    Returns the number of strategies loaded.
    """
    loaded = 0
    try:
        from sqlalchemy import select
        from app.models.backtest import GeneratedStrategy

        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedStrategy).where(GeneratedStrategy.is_active == True)
            )
            strategies = result.scalars().all()

            for strat in strategies:
                if register_strategy(strat.name, strat.source_code):
                    loaded += 1
                    logger.info("Loaded generated strategy from DB: %s", strat.name)
                else:
                    logger.warning("Failed to load generated strategy: %s", strat.name)

    except Exception as e:
        logger.warning("Could not load generated strategies from DB: %s", e)

    logger.info("Loaded %d generated strategies from database", loaded)
    return loaded
