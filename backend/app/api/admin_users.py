import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.security import hash_password
from app.database.session import get_db
from app.models.role import Role
from app.models.user import User
from app.services.user_lifecycle_service import (
    USER_LIFECYCLE_ADVISORY_LOCK_KEY,
    UserLifecycleAuthorizationError,
    UserLifecycleConflictError,
    UserLifecycleNotFoundError,
    UserLifecycleService,
)
from app.services.change_history_service import ChangeHistoryService


router = APIRouter(
    prefix="/admin/users",
    tags=["Admin Users"],
)

EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


class AdminCreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(min_length=1, max_length=50)
    temporary_password: str = Field(
        min_length=10,
        max_length=200,
    )
    must_change_password: bool = True

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip()

        if len(normalized) < 3:
            raise ValueError(
                "Username must contain at least 3 characters"
            )

        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()

        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid email address")

        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip()

        if normalized not in {
            "Administrator",
            "User",
        }:
            raise ValueError("Unknown role")

        return normalized


class AdminResetUserPasswordRequest(BaseModel):
    temporary_password: str = Field(
        min_length=10,
        max_length=200,
    )


class AdminUpdateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Username must contain at least 3 characters")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid email address")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in {"Administrator", "User"}:
            raise ValueError("Unknown role")
        return value


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "role": user.role.name,
        "must_change_password": user.must_change_password,
        "password_reset_requested": user.password_reset_requested,
    }


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role.name != "Administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )

    return current_user


@router.get("")
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .order_by(User.id)
        .all()
    )

    return [_user_response(user) for user in users]


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    request: AdminUpdateUserRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    payload = request.model_dump(exclude_unset=True, exclude_none=True)
    if not payload:
        raise HTTPException(status_code=422, detail={"code": "empty_user_update"})
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": USER_LIFECYCLE_ADVISORY_LOCK_KEY})
        target = db.query(User).filter(User.id == user_id).with_for_update().first()
        if target is None:
            raise HTTPException(status_code=404, detail={"code": "user_not_found"})
        before = {"username": target.username, "email": target.email, "role": target.role.name}
        if "role" in payload and payload["role"] != target.role.name:
            if target.id == actor.id:
                raise HTTPException(status_code=409, detail={"code": "self_demotion_forbidden"})
            role = db.query(Role).filter(Role.name == payload["role"]).first()
            if role is None:
                raise HTTPException(status_code=422, detail={"code": "unknown_role"})
            if target.role.name == "Administrator" and payload["role"] != "Administrator":
                active_admin_ids = {
                    row.id for row in db.query(User).join(Role).filter(
                        User.is_active.is_(True), Role.name == "Administrator"
                    ).with_for_update().all()
                }
                UserLifecycleService.ensure_admin_survives(
                    target_user_id=target.id,
                    active_administrator_ids=active_admin_ids,
                )
            target.role = role
        for field in ("username", "email"):
            if field not in payload:
                continue
            duplicate = db.query(User).filter(
                User.id != target.id,
                func.lower(getattr(User, field)) == payload[field].lower(),
            ).first()
            if duplicate is not None:
                raise HTTPException(status_code=409, detail={"code": f"duplicate_{field}"})
            setattr(target, field, payload[field])
        after = {"username": target.username, "email": target.email, "role": target.role.name}
        db.add(target)
        db.flush()
        ChangeHistoryService(db).persist(
            actor_user_id=actor.id,
            entity_type="user",
            entity_id=target.id,
            action="updated",
            before=before,
            after=after,
            source_key=f"user-update:{target.id}:{int(datetime.now(timezone.utc).timestamp() * 1000000)}",
        )
        db.commit()
        db.refresh(target)
        return _user_response(target)
    except UserLifecycleConflictError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "last_administrator_demotion_forbidden"}) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "duplicate_username_or_email"},
        ) from error
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: AdminCreateUserRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = request.username
    email = request.email

    duplicate = (
        db.query(User)
        .filter(
            (
                func.lower(User.username)
                == username.lower()
            )
            | (
                func.lower(User.email)
                == email.lower()
            )
        )
        .first()
    )

    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    role = (
        db.query(Role)
        .filter(Role.name == request.role)
        .first()
    )

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown role",
        )

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(
            request.temporary_password,
        ),
        is_active=True,
        must_change_password=(
            request.must_change_password
        ),
        password_reset_requested=False,
        role_id=role.id,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "role": user.role.name,
        "must_change_password": (
            user.must_change_password
        ),
    }


@router.post(
    "/{user_id}/reset-password",
)
def reset_user_password(
    user_id: int,
    request: AdminResetUserPasswordRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reset password for inactive user",
        )

    user.password_hash = hash_password(
        request.temporary_password,
    )
    user.must_change_password = True
    user.password_reset_requested = False

    db.add(user)
    db.commit()

    return {
        "status": "ok",
        "user_id": user.id,
    }


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        UserLifecycleService(db).deactivate_user(
            actor_user_id=current_admin.id,
            target_user_id=user_id,
        )
        db.commit()
    except UserLifecycleNotFoundError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except UserLifecycleAuthorizationError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except UserLifecycleConflictError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except Exception:
        db.rollback()
        raise

    return {
        "status": "deactivated",
        "user_id": user_id,
        "is_active": False,
    }
