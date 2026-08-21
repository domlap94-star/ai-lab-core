from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass


class CalculationValidationError(ValueError): pass


@dataclass(frozen=True)
class CalculationResult:
    value: float
    unit: str


class DeterministicCalculationValidator:
    OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                 ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}
    UNIT_SCALE = {"mm": ("m", .001), "cm": ("m", .01), "m": ("m", 1.0),
                  "g": ("kg", .001), "kg": ("kg", 1.0), "N": ("N", 1.0),
                  "kN": ("N", 1000.0), "Pa": ("Pa", 1.0), "kPa": ("Pa", 1000.0),
                  "MPa": ("Pa", 1_000_000.0), "V": ("V", 1.0), "A": ("A", 1.0)}

    def normalize(self, value: float, unit: str) -> CalculationResult:
        if unit not in self.UNIT_SCALE or not math.isfinite(value): raise CalculationValidationError("analysis_unit_invalid")
        canonical, scale = self.UNIT_SCALE[unit]; return CalculationResult(value * scale, canonical)

    def evaluate(self, expression: str, variables: dict[str, float]) -> float:
        if len(expression) > 500 or len(variables) > 128: raise CalculationValidationError("analysis_formula_invalid")
        tree = ast.parse(expression, mode="eval")
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
