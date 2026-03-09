"""
Code Validation skill.

Validates the generated Python source code for safety and
correctness using static analysis (ast parsing).

Checks performed:
    1. Valid Python syntax via ast.parse()
    2. No import / importfrom statements
    3. No forbidden builtins (exec, eval, open, __import__, dunder attrs)
    4. Maximum source code length (5000 chars)
    5. Must contain at least one function definition

Deterministic - no model calls, pure AST analysis.
"""

from __future__ import annotations

import ast

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SOURCE_LENGTH = 5000

_FORBIDDEN_BUILTINS = frozenset({
    "exec",
    "eval",
    "open",
    "__import__",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
    "exit",
    "quit",
})


def _validate_source(source: str) -> tuple[bool, list[str], int, int]:
    """
    Validate source code and return (valid, issues, node_count, func_count).
    """
    issues: list[str] = []

    # --- Check 4: Length ---
    if len(source) > _MAX_SOURCE_LENGTH:
        issues.append(
            f"Source code exceeds maximum length: "
            f"{len(source)} > {_MAX_SOURCE_LENGTH} chars"
        )

    # --- Check 1: Parse ---
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        issues.append(f"Syntax error: {exc.msg} (line {exc.lineno})")
        return False, issues, 0, 0

    # Walk all nodes
    node_count = 0
    function_count = 0

    for node in ast.walk(tree):
        node_count += 1

        # --- Check 5: Count function definitions ---
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_count += 1

        # --- Check 2: Forbidden imports ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Allow 'decimal' module import since templates use it
                if alias.name != "decimal":
                    issues.append(
                        f"Forbidden import: 'import {alias.name}' "
                        f"(line {node.lineno})"
                    )

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # Allow 'from decimal import Decimal'
            if module != "decimal":
                issues.append(
                    f"Forbidden import: 'from {module} import ...' "
                    f"(line {node.lineno})"
                )

        # --- Check 3: Forbidden builtins ---
        if isinstance(node, ast.Call):
            func = node.func
            # Direct call: exec(...), eval(...)
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_BUILTINS:
                issues.append(
                    f"Forbidden builtin call: '{func.id}()' "
                    f"(line {node.lineno})"
                )

        # Dunder attribute access: anything with __ prefix/suffix
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                issues.append(
                    f"Forbidden dunder access: '.{node.attr}' "
                    f"(line {node.lineno})"
                )
        if isinstance(node, ast.Name):
            if (
                node.id.startswith("__")
                and node.id.endswith("__")
                and node.id not in ("__name__",)
            ):
                issues.append(
                    f"Forbidden dunder name: '{node.id}' "
                    f"(line {node.lineno})"
                )

    # --- Check 5: Must have at least one function ---
    if function_count == 0:
        issues.append("No function definition found in source code")

    valid = len(issues) == 0
    return valid, issues, node_count, function_count


class CodeValidationSkill(BaseSkill):
    """Validate generated Python code for safety and correctness."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "code_validation"

    @property
    def name(self) -> str:
        return "Code Validation"

    @property
    def description(self) -> str:
        return (
            "Validates generated Python source code via AST analysis: "
            "syntax check, forbidden imports, forbidden builtins, "
            "length limit, and function presence."
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
        return []

    @property
    def prerequisites(self) -> list[str]:
        return ["code_generation"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Pull generated code from upstream
        gen_result = ctx.upstream_results.get("code_generation")
        if gen_result is None or gen_result.status != SkillStatus.SUCCESS:
            return self._failure("code_generation did not succeed")

        source_code = gen_result.output.get("source_code", "")
        if not source_code.strip():
            return self._failure("Generated source code is empty")

        valid, issues, node_count, function_count = _validate_source(source_code)

        if not valid:
            return self._failure(
                message=f"Validation failed with {len(issues)} issue(s): "
                + "; ".join(issues),
                issues=issues,
                ast_node_count=node_count,
                function_count=function_count,
            )

        return self._success(
            output={
                "valid": True,
                "issues": [],
                "ast_node_count": node_count,
                "function_count": function_count,
            },
            message=(
                f"Code validation passed. "
                f"{node_count} AST nodes, {function_count} function(s)."
            ),
        )
