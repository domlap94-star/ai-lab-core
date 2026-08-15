from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.user import User
from app.models.user_lifecycle_event import UserLifecycleEvent


DEACTIVATED = "DEACTIVATED"
USER_LIFECYCLE_ADVISORY_LOCK_KEY = 6_202_608_150


class UserLifecycleNotFoundError(Exception):
    pass


class UserLifecycleAuthorizationError(Exception):
    pass


class UserLifecycleConflictError(Exception):
    pass


class UserLifecycleService:
    """Fail-closed user lifecycle operations within the caller's transaction."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def deactivate_user(
        self,
        *,
        actor_user_id: int,
        target_user_id: int,
    ) -> UserLifecycleEvent:
        # Serializes lifecycle transitions across workers. The row locks below
        # then protect the actor, target and active-administrator set.
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": USER_LIFECYCLE_ADVISORY_LOCK_KEY},
        )

        actor = self._lock_user(actor_user_id)
        if (
            actor is None
            or not actor.is_active
            or actor.role.name != "Administrator"
        ):
            raise UserLifecycleAuthorizationError(
                "Administrator role required"
            )

        target = self._lock_user(target_user_id)
        if target is None:
            raise UserLifecycleNotFoundError("User not found")
        if target.id == actor.id:
            raise UserLifecycleConflictError(
                "Administrator cannot deactivate own account"
            )
        if not target.is_active:
            raise UserLifecycleConflictError("User is already inactive")

        if target.role.name == "Administrator":
            active_administrators = self._lock_active_administrators()
            self.ensure_admin_survives(
                target_user_id=target.id,
                active_administrator_ids={
                    user.id for user in active_administrators
                },
            )

        target.is_active = False
        event = UserLifecycleEvent(
            actor_user_id=actor.id,
            target_user_id=target.id,
            action=DEACTIVATED,
        )
        self.db.add(target)
        self.db.add(event)
        # Flush makes audit failure abort before the router commits. The caller
        # owns commit/rollback so both changes remain atomic.
        self.db.flush()
        return event

    def _lock_user(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )

    def _lock_active_administrators(self) -> list[User]:
        return (
            self.db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(
                User.is_active.is_(True),
                Role.name == "Administrator",
            )
            .order_by(User.id)
            .with_for_update()
            .all()
        )

    @staticmethod
    def ensure_admin_survives(
        *,
        target_user_id: int,
        active_administrator_ids: set[int],
    ) -> None:
        if target_user_id in active_administrator_ids and len(
            active_administrator_ids
        ) <= 1:
            raise UserLifecycleConflictError(
                "Cannot deactivate the last active Administrator"
            )
