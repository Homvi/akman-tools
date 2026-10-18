from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import Role, User
from apps.api.security import hash_password

DEFAULT_ROLES = ("admin", "planner", "worker")


def ensure_roles_and_admin(db: Session) -> None:
    roles = {r.name: r for r in db.query(Role).all()}
    for name in DEFAULT_ROLES:
        if name not in roles:
            role = Role(name=name)
            db.add(role)
            db.flush()
            roles[name] = role

    admin = db.query(User).filter(User.email == settings.admin_email).first()
    if not admin:
        admin = User(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            is_active=True,
        )
        admin.roles = [roles["admin"], roles["planner"]]
        db.add(admin)
    db.commit()
