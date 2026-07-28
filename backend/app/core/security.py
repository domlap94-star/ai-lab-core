from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


# ==========================================================
# Passwords
# ==========================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# ==========================================================
# JWT helpers
# ==========================================================

def _build_token_payload(
    data: dict[str, Any],
    expires_delta: timedelta,
    token_type: str,
) -> dict[str, Any]:
    payload = data.copy()
    payload.setdefault("jti", str(uuid4()))
    payload["iat"] = datetime.now(timezone.utc)
    payload["nbf"] = datetime.now(timezone.utc)
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["type"] = token_type
    payload.setdefault("iss", settings.app_name)
    return payload


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes,
        )

    payload = _build_token_payload(
        data=data,
        expires_delta=expires_delta,
        token_type=TOKEN_TYPE_ACCESS,
    )

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(
            days=settings.refresh_token_expire_days,
        )

    payload = _build_token_payload(
        data=data,
        expires_delta=expires_delta,
        token_type=TOKEN_TYPE_REFRESH,
    )

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_token(
    token: str,
) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )


def verify_access_token(
    token: str,
) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise JWTError("Invalid token type")
    return payload


def verify_refresh_token(
    token: str,
) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise JWTError("Invalid token type")
    return payload


def get_subject_from_token(
    token: str,
) -> str | None:
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None