from sqlalchemy.orm import Session, joinedload

from app.core.security import verify_password
from app.models.user import User


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.username == username)
        .first()
    )


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:
    user = get_user_by_username(
        db=db,
        username=username,
    )

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user