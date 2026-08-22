from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass
from typing import Any


class CalculationValidationError(ValueError): pass


@dataclass(frozen=True)
class CalculationResult:
    value: float
    unit: str


class DeterministicCalculationValidator:
    OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                 ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}
    # SI base dimensions: mass, length, time, electric current.
    UNIT_SCALE = {
        "": ("", 1.0, (0, 0, 0, 0)), "1": ("", 1.0, (0, 0, 0, 0)),
        "%": ("", .01, (0, 0, 0, 0)),
        "mm": ("m", .001, (0, 1, 0, 0)), "cm": ("m", .01, (0, 1, 0, 0)),
        "m": ("m", 1.0, (0, 1, 0, 0)), "mm2": ("m2", 1e-6, (0, 2, 0, 0)),
        "cm2": ("m2", 1e-4, (0, 2, 0, 0)), "m2": ("m2", 1.0, (0, 2, 0, 0)),
        "g": ("kg", .001, (1, 0, 0, 0)), "kg": ("kg", 1.0, (1, 0, 0, 0)),
        "N": ("N", 1.0, (1, 1, -2, 0)), "kN": ("N", 1000.0, (1, 1, -2, 0)),
        "Pa": ("Pa", 1.0, (1, -1, -2, 0)), "kPa": ("Pa", 1000.0, (1, -1, -2, 0)),
        "MPa": ("Pa", 1_000_000.0, (1, -1, -2, 0)),
        "V": ("V", 1.0, (1, 2, -3, -1)), "A": ("A", 1.0, (0, 0, 0, 1)),
    }

    def normalize(self, value: float, unit: str) -> CalculationResult:
        if unit not in self.UNIT_SCALE or not math.isfinite(value): raise CalculationValidationError("analysis_unit_invalid")
        canonical, scale, _ = self.UNIT_SCALE[unit]
        return CalculationResult(value * scale, canonical)

    def evaluate_checked(
        self,
        expression: str,
        variables: dict[str, float],
        units: dict[str, str],
        result_unit: str | None = None,
    ) -> CalculationResult:
        names = self.required_variables(expression)
        if names != set(variables):
            raise CalculationValidationError("analysis_variable_missing")
        normalized: dict[str, float] = {}
        dimensions: dict[str, tuple[int, int, int, int]] = {}
        for name, value in variables.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise CalculationValidationError("analysis_numeric_invalid")
            unit = units.get(name, "")
            if unit not in self.UNIT_SCALE:
                raise CalculationValidationError("analysis_unit_invalid")
            _, scale, dimension = self.UNIT_SCALE[unit]
            normalized[name] = float(value) * scale
            dimensions[name] = dimension
        value = self.evaluate(expression, normalized)
        dimension = self._dimension(expression, dimensions)
        if result_unit is None:
            return CalculationResult(value, self._canonical_unit(dimension))
        if result_unit not in self.UNIT_SCALE:
            raise CalculationValidationError("analysis_unit_invalid")
        canonical, scale, expected_dimension = self.UNIT_SCALE[result_unit]
        if dimension != expected_dimension:
            raise CalculationValidationError("analysis_dimension_mismatch")
        return CalculationResult(value / scale, result_unit or canonical)

    @staticmethod
    def required_variables(expression: str) -> set[str]:
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, ValueError) as error:
            raise CalculationValidationError("analysis_formula_invalid") from error
        return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    def _dimension(self, expression: str, dimensions: dict[str, tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, ValueError) as error:
            raise CalculationValidationError("analysis_formula_invalid") from error

        def combine(first, second, direction=1):
            return tuple(a + direction * b for a, b in zip(first, second, strict=True))

        def visit(node: Any):
            if isinstance(node, ast.Expression): return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return (0, 0, 0, 0)
            if isinstance(node, ast.Name) and node.id in dimensions: return dimensions[node.id]
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub): return visit(node.operand)
            if isinstance(node, ast.BinOp):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, (ast.Add, ast.Sub)):
                    if left != right: raise CalculationValidationError("analysis_dimension_mismatch")
                    return left
                if isinstance(node.op, ast.Mult): return combine(left, right)
                if isinstance(node.op, ast.Div): return combine(left, right, -1)
                if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
                    return tuple(value * node.right.value for value in left)
            raise CalculationValidationError("analysis_formula_invalid")

        return visit(tree)

    @staticmethod
    def _canonical_unit(dimension: tuple[int, int, int, int]) -> str:
        return {
            (0, 0, 0, 0): "", (0, 1, 0, 0): "m", (0, 2, 0, 0): "m2",
            (1, 0, 0, 0): "kg", (1, 1, -2, 0): "N", (1, -1, -2, 0): "Pa",
            (1, 2, -3, -1): "V", (0, 0, 0, 1): "A",
        }.get(dimension, "SI")

    def evaluate(self, expression: str, variables: dict[str, float]) -> float:
        if len(expression) > 500 or len(variables) > 128: raise CalculationValidationError("analysis_formula_invalid")
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, ValueError) as error:
            raise CalculationValidationError("analysis_formula_invalid") from error
        def visit(node):
            if isinstance(node, ast.Expression): return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return float(node.value)
            if isinstance(node, ast.Name) and node.id in variables: return float(variables[node.id])
            if isinstance(node, ast.BinOp) and type(node.op) in self.OPERATORS: return self.OPERATORS[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in self.OPERATORS: return self.OPERATORS[type(node.op)](visit(node.operand))
            raise CalculationValidationError("analysis_formula_invalid")
        value = visit(tree)
        if not math.isfinite(value): raise CalculationValidationError("analysis_numeric_invalid")
        return value

    @staticmethod
    def compare(first: float, second: float, *, tolerance: float = 1e-6) -> bool:
        return math.isclose(first, second, rel_tol=tolerance, abs_tol=1e-9)
