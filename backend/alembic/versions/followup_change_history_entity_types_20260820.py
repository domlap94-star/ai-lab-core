"""Extend Change History entity/action allowlists.

Revision ID: followup_change_history_entity_types_20260820
Revises: followup_ignored_mail_sources_20260820
"""

from alembic import op


revision = "followup_change_history_entity_types_20260820"
down_revision = "followup_ignored_mail_sources_20260820"
branch_labels = None
depends_on = None


_ORIGINAL_ENTITY_TYPES = (
    "client",
    "client_contact",
    "client_address",
    "client_workflow_status",
    "client_candidate",
    "candidate_merge",
)
_ENTITY_TYPES = _ORIGINAL_ENTITY_TYPES + ("ignored_mail_source", "user")
_ORIGINAL_ACTIONS = (
    "created",
    "updated",
    "deleted",
    "restored",
    "status_changed",
    "accepted",
    "rejected",
    "merged",
)
_ACTIONS = _ORIGINAL_ACTIONS + ("activated", "deactivated")


def _values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _replace_constraints(entity_types: tuple[str, ...], actions: tuple[str, ...]) -> None:
    op.drop_constraint(
        "ck_change_history_events_entity_type",
        "change_history_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_change_history_events_entity_type",
        "change_history_events",
        f"entity_type IN ({_values(entity_types)})",
    )
    op.drop_constraint(
        "ck_change_history_events_action",
        "change_history_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_change_history_events_action",
        "change_history_events",
        f"action IN ({_values(actions)})",
    )


def upgrade() -> None:
    _replace_constraints(_ENTITY_TYPES, _ACTIONS)


def downgrade() -> None:
    _replace_constraints(_ORIGINAL_ENTITY_TYPES, _ORIGINAL_ACTIONS)
