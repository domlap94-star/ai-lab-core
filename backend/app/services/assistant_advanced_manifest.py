from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Hashable, Iterable

from app.services.analysis_calculation_validator import (
    CalculationValidationError,
    DeterministicCalculationValidator,
)


BASE_REQUESTED_OUTPUT = (
    "Zwróć dokładnie NEXT_STABIL_TEMP_CHAT_RESULT_V2: {schema,claims,contradictions}. "
    "Nie zwracaj answer, claim_id ani decyzji accept/review/reject. target_scope jest "
    "niezmienny; używaj tylko uchwytów target/global. FACT wybiera fact/tool/visual "
    "handles. MISSING opisuje brak. HYPOTHESIS wymaga podstawy i sposobu weryfikacji. "
    "ESTIMATE ze statusem ESTIMABLE wymaga value_or_range, HIGH/MEDIUM/LOW, podstawy, "
    "założeń i braków. ESTIMATE ze statusem NOT_ESTIMABLE wymaga reason, podstawy i "
    "missing_inputs oraz nie może zawierać wartości, confidence ani założeń. Braków i "
    "źródeł nie zgaduj. Lokalny deterministyczny walidator sam wybiera dyspozycję."
)

_CONSISTENCY_INTENT = re.compile(
    r"(?i)\b(?:sp[oó]jn|niesp[oó]jn|sprzecz|zgodn|consistent|inconsistent|contradict)"
)
_CONTRADICTION_INTENT = re.compile(r"(?i)\b(?:sprzecz|contradict)")
_LIMIT_INTENT = re.compile(r"(?i)\b(?:wymagan|spe[lł]n|limit|dopuszcz|compliance|requirement)")
_MAXIMUM_LIMIT = re.compile(
    r"(?i)\b(?:limit|maksymal|najwy[zż]ej|nie\s+wi[eę]cej|dopuszczaln|maximum)"
)
_MINIMUM_LIMIT = re.compile(r"(?i)\b(?:minimal|co\s+najmniej|nie\s+mniej|minimum)")
_MEASUREMENT = re.compile(
    r"(?<![\w/])(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>MPa|kPa|Pa|kN|N|mm|cm|m)(?!\w)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AdvancedManifest:
    analysis_type: str
    claims: list[dict[str, Any]]
    requested_output: str
    validation_requirements: list[str]


def _atomize(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|;\s*", value)
        if item.strip()
    ]


def _number(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return format(numeric, ".12g")


def _safe_calculation_row(
    *,
    index: int,
    payload: dict[str, Any],
    source_handles: list[str],
) -> dict[str, Any] | None:
    tool = str(payload.get("tool") or "")
    data = payload.get("data")
    if "calcul" not in tool.casefold() or not isinstance(data, dict) or not source_handles:
        return None
    value = data.get("value")
    unit = data.get("unit")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    if not isinstance(unit, str) or not unit or len(unit) > 16:
        return None
    formula = data.get("formula")
    if formula is not None and (not isinstance(formula, str) or len(formula) > 500):
        return None
    display = data.get("display")
    if not isinstance(display, str) or not display.strip() or len(display) > 200:
        display = f"{_number(value)} {unit}"
    row: dict[str, Any] = {
        "kind": "TOOL_RESULT",
        "tool_handle": f"T{index}",
        "source_handles": source_handles,
        "statement": display.strip(),
        "value": float(value),
        "unit": unit,
    }
    if formula:
        row["formula"] = formula
    si_value, si_unit = data.get("si_value"), data.get("si_unit")
    if (
        not isinstance(si_value, bool)
        and isinstance(si_value, (int, float))
        and math.isfinite(float(si_value))
        and isinstance(si_unit, str)
        and 0 < len(si_unit) <= 16
    ):
        row.update({"si_value": float(si_value), "si_unit": si_unit})
    return row


def _derived_limit_comparison(
    *,
    tool_row: dict[str, Any],
    sources: list[tuple[str, Hashable, str]],
    question: str,
    tool_handle: str,
) -> dict[str, Any] | None:
    if not _LIMIT_INTENT.search(question):
        return None
    limit = tool_row.get("value")
    limit_unit = tool_row.get("unit")
    if not isinstance(limit, (int, float)) or not isinstance(limit_unit, str):
        return None
    relevant = set(tool_row.get("source_handles") or [])
    limit_sources = {
        handle
        for handle, _, text in sources
        if handle in relevant and (_MAXIMUM_LIMIT.search(text) or _MINIMUM_LIMIT.search(text))
    }
    if not limit_sources:
        return None
    minimum = any(
        _MINIMUM_LIMIT.search(text)
        for handle, _, text in sources
        if handle in limit_sources
    )
    calculator = DeterministicCalculationValidator()
    candidates: list[tuple[str, float, str]] = []
    for handle, _, text in sources:
        if handle not in relevant or handle in limit_sources:
            continue
        for match in _MEASUREMENT.finditer(text):
            observed_unit = match.group("unit")
            if observed_unit.casefold() != limit_unit.casefold():
                continue
            candidates.append((handle, float(match.group("value").replace(",", ".")), observed_unit))
    if len(candidates) != 1:
        return None
    observed_handle, observed, observed_unit = candidates[0]
    try:
        canonical_observed = calculator.normalize(observed, observed_unit)
        canonical_limit = calculator.normalize(float(limit), limit_unit)
    except CalculationValidationError:
        return None
    if canonical_observed.unit != canonical_limit.unit:
        return None
    satisfied = (
        canonical_observed.value >= canonical_limit.value
        if minimum
        else canonical_observed.value <= canonical_limit.value
    )
    relation = "jest spełnione" if satisfied else "nie jest spełnione"
    comparator = "nie jest mniejsza niż" if minimum else "nie przekracza"
    if not satisfied:
        comparator = "jest mniejsza niż" if minimum else "przekracza"
    statement = (
        f"Wartość zmierzona {_number(observed)} {observed_unit} {comparator} "
        f"obliczony limit {_number(float(limit))} {limit_unit}; wymaganie {relation}."
    )
    return {
        "kind": "TOOL_RESULT",
        "tool_handle": tool_handle,
        "source_handles": sorted(limit_sources | {observed_handle}),
        "statement": statement,
        "comparison": "greater_or_equal" if minimum else "less_or_equal",
        "observed_value": observed,
        "limit_value": float(limit),
        "unit": limit_unit,
        "satisfied": satisfied,
    }


def build_advanced_manifest(
    *,
    question: str,
    sources: Iterable[tuple[str, Hashable, str]],
    tool_payloads: Iterable[dict[str, Any]],
    default_analysis_type: str = "technical_interpretation",
) -> AdvancedManifest:
    source_rows = list(sources)
    handle_by_key = {key: handle for handle, key, _ in source_rows}
    consistency = bool(_CONSISTENCY_INTENT.search(question))
    explicit_contradiction = bool(_CONTRADICTION_INTENT.search(question))
    claims: list[dict[str, Any]] = []
    fact_index = 0
    for handle, _, excerpt in source_rows:
        statements = _atomize(excerpt) or [excerpt]
        for statement in statements:
            fact_index += 1
            row: dict[str, Any] = {
                "kind": "FACT",
                "fact_handle": f"F{fact_index}",
                "source_handle": handle,
                "statement": statement,
            }
            if consistency:
                row["comparison_group"] = "C1"
            if explicit_contradiction:
                row["contradiction_group"] = "G1"
            claims.append(row)

    calculation_rows: list[dict[str, Any]] = []
    for payload in tool_payloads:
        source_handles = sorted({
            handle_by_key[key]
            for raw_key in payload.get("source_keys", [])
            for key in [tuple(raw_key) if isinstance(raw_key, list) else raw_key]
            if key in handle_by_key
        })
        row = _safe_calculation_row(
            index=len(calculation_rows) + 1,
            payload=payload,
            source_handles=source_handles,
        )
        if row is not None:
            calculation_rows.append(row)
            comparison = _derived_limit_comparison(
                tool_row=row,
                sources=source_rows,
                question=question,
                tool_handle=f"T{len(calculation_rows) + 1}",
            )
            if comparison is not None:
                calculation_rows.append(comparison)

    analysis_type = "consistency_check" if consistency else default_analysis_type
    requested = BASE_REQUESTED_OUTPUT
    requirements = ["strict handle binding", "local claim IDs", "privacy minimization"]
    if calculation_rows:
        requested += (
            " Zwalidowane TOOL_RESULT są lokalnie autorytatywne: wybierz je w FACT. "
            "Dla pytania wykorzystującego obliczenie dodaj ESTIMATE ESTIMABLE z "
            "basis_tool_handles, zwięzłą wartością, założeniami i brakami."
        )
        requirements.extend(["deterministic tool result fidelity", "estimate discipline"])
    if consistency:
        requested += (
            " To jest analiza spójności. Porównaj wszystkie FACT z comparison_group. "
            "Jawnie wskaż, czy obserwacje są spójne, różne czy sprzeczne; gdy są "
            "materialnie niespójne, dodaj contradictions z właściwymi fact_handles."
        )
        requirements.append("explicit consistency relationship")
    bounded_tools = calculation_rows[:16]
    bounded_claims = claims[:max(0, 64 - len(bounded_tools))] + bounded_tools
    return AdvancedManifest(analysis_type, bounded_claims, requested, requirements)
