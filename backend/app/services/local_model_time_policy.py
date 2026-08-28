from __future__ import annotations

from datetime import UTC, datetime


# Preserve Ollama's automatic CPU-thread selection unless an explicit,
# separately qualified override is supplied.
V2_LOCAL_NUM_THREAD: int | None = None
V2_STANDARD_INITIAL_NUM_PREDICT = 480
V2_STANDARD_TRUNCATION_RETRY_NUM_PREDICT = 768
V2_STANDARD_SEMANTIC_CORRECTION_NUM_PREDICT = 480
V2_STANDARD_TASK_COMPLETION_CORRECTION_NUM_PREDICT = 480
V2_GENERAL_NUM_PREDICT = 160
V2_KB_OVERVIEW_INITIAL_NUM_PREDICT = 200
V2_KB_OVERVIEW_CORRECTION_NUM_PREDICT = 200
LOCAL_OUTPUT_BUDGET_EXHAUSTED = "LOCAL_OUTPUT_BUDGET_EXHAUSTED"
MODEL_LOAD_ABSOLUTE_SECONDS = 180
PROMPT_EVALUATION_ABSOLUTE_SECONDS = 300
GENERATION_INACTIVITY_SECONDS = 120
GENERATION_ABSOLUTE_SECONDS = 600
STANDARD_LOCAL_ABSOLUTE_SECONDS = 900
DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS = 900

LOCAL_MODEL_PHASES = frozenset({
    "model_load",
    "prompt_evaluation",
    "generation",
    "validation",
    "cleanup",
})


class LocalOutputBudgetExhausted(RuntimeError):
    """The local generator stopped because its configured output budget ended."""

    def __init__(
        self,
        *,
        requested_num_predict: int,
        eval_count: int | None,
        done_reason: str | None,
    ) -> None:
        super().__init__(LOCAL_OUTPUT_BUDGET_EXHAUSTED)
        self.requested_num_predict = requested_num_predict
        self.eval_count = eval_count
        self.done_reason = done_reason


def local_output_budget_exhausted(
    *,
    done_reason: object,
    eval_count: object,
    requested_num_predict: int,
    parse_failed: bool,
) -> bool:
    """Classify only explicit or strongly evidenced output-limit termination."""

    if done_reason == "length":
        return True
    return (
        (done_reason is None or done_reason == "")
        and parse_failed
        and isinstance(eval_count, int)
        and eval_count >= requested_num_predict
    )


def utc_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def phase_timeout_code(
    *,
    manifest: dict | None,
    last_progress_at: datetime | None,
    now: datetime | None = None,
) -> str | None:
    """Evaluate a local phase without treating a heartbeat as model progress."""

    phase_state = (manifest or {}).get("local_model_phase")
    if not isinstance(phase_state, dict):
        return None
    phase = str(phase_state.get("phase") or "")
    if phase not in LOCAL_MODEL_PHASES:
        return None
    raw_started = phase_state.get("started_at")
    if not isinstance(raw_started, str):
        return None
    try:
        started = datetime.fromisoformat(raw_started.replace("Z", "+00:00"))
    except ValueError:
        return "LOCAL_MODEL_PHASE_STATE_INVALID"
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    elapsed = (current - started.astimezone(UTC)).total_seconds()

    if phase == "model_load" and elapsed > MODEL_LOAD_ABSOLUTE_SECONDS:
        return "LOCAL_MODEL_LOAD_TIMEOUT"
    if phase == "prompt_evaluation" and elapsed > PROMPT_EVALUATION_ABSOLUTE_SECONDS:
        return "LOCAL_PROMPT_EVALUATION_TIMEOUT"
    if phase == "generation":
        if elapsed > GENERATION_ABSOLUTE_SECONDS:
            return "LOCAL_GENERATION_ABSOLUTE_TIMEOUT"
        progress = last_progress_at or started
        if progress.tzinfo is None:
            progress = progress.replace(tzinfo=UTC)
        if (current - progress.astimezone(UTC)).total_seconds() > GENERATION_INACTIVITY_SECONDS:
            return "LOCAL_GENERATION_INACTIVITY_TIMEOUT"
    return None
