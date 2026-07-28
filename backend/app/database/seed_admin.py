from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


def seed_admin(db: Session) -> None:
    admin_role = (
        db.query(Role)
        .filter(Role.name == "Administrator")
        .first()
    )

    if admin_role is None:
        admin_role = Role(
            name="Administrator",
            description="System administrator",
        )

        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)

    existing_user = (
        db.query(User)
        .filter(User.username == settings.admin_username)
        .first()
    )

    if existing_user is not None:
        return

    admin = User(
        username=settings.admin_username,
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        is_active=True,
        role_id=admin_role.id,
    )

    db.add(admin)
    db.commit()