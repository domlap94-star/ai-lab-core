import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.security import hash_password
from app.database.session import get_db
from app.models.role import Role
from app.models.user import User


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

    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "role": user.role.name,
            "must_change_password": (
                user.must_change_password
            ),
            "password_reset_requested": (
                user.password_reset_requested
            ),
        }
        for user in users
    ]


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
