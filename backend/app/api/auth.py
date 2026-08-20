from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import API_PREFIX
from app.core.security import (
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)
from app.database.session import get_db
from app.models.user import User
from app.services.user_service import UserService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{API_PREFIX}/auth/login",
)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=10, max_length=200)


class PasswordResetRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_access_token(token)
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user_service = UserService(db)
    user = user_service.get_by_username(username)

    if user is None or not user.is_active:
        raise credentials_exception

    token_auth_version = payload.get("auth_version")
    if token_auth_version is None:
        if user.auth_version != 0:
            raise credentials_exception
    elif (
        not isinstance(token_auth_version, int)
        or token_auth_version != user.auth_version
    ):
        raise credentials_exception

    return user


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    user = user_service.get_by_username(form_data.username)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(
        data={
            "sub": user.username,
            "email": user.email,
            "role": user.role.name,
            "auth_version": user.auth_version,
        },
        expires_delta=timedelta(
            minutes=settings.access_token_expire_minutes,
        ),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_change_password": user.must_change_password,
    }


@router.get("/me")
def me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "role": current_user.role.name,
        "must_change_password": current_user.must_change_password,
        "password_reset_requested": (
            current_user.password_reset_requested
        ),
        "auth_version": current_user.auth_version,
    }


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(
        request.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from current password",
        )

    current_user.password_hash = hash_password(
        request.new_password,
    )
    current_user.must_change_password = False
    current_user.password_reset_requested = False

    db.add(current_user)
    db.commit()

    return {
        "status": "ok",
    }


@router.post(
    "/reset-password/request",
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    identifier = request.identifier.strip().lower()

    if identifier:
        user = (
            db.query(User)
            .filter(
                or_(
                    func.lower(User.username) == identifier,
                    func.lower(User.email) == identifier,
                )
            )
            .first()
        )

        if user is not None and user.is_active:
            user.password_reset_requested = True
            db.add(user)
            db.commit()

    return {
        "status": "accepted",
    }
