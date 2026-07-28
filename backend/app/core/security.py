from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


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
# JWT Tokens
# ==========================================================

def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Creates JWT access token.

    Required:
        data["sub"]

    Example:
        create_access_token(
            data={
                "sub": user.username,
                "role": "admin",
            }
        )
    """

    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes,
        )

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode.update(
        {
            "exp": expire,
            "type": "access",
        }
    )

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Creates JWT refresh token.
    """

    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(days=30)

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
        }
    )

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_token(
    token: str,
) -> dict[str, Any]:
    """
    Decode JWT token.
    """

    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )


def get_subject_from_token(
    token: str,
) -> str | None:
    """
    Returns username (sub) from token.
    """

    try:
        payload = decode_token(token)
        return payload.get("sub")

    except JWTError:
        return None


def verify_access_token(
    token: str,
) -> dict[str, Any]:
    """
    Verify access token.
    """

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise JWTError("Invalid token type")

    return payload


def verify_refresh_token(
    token: str,
) -> dict[str, Any]:
    """
    Verify refresh token.
    """

    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise JWTError("Invalid token type")

    return payload