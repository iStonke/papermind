"""Serialize filesystem publication with account deletion."""
from sqlalchemy import select
from app.core.errors import UnauthorizedError
from app.models.user import User


def lock_storage_owner(db, owner_id):
    if owner_id is None:  # System imports have no interactive owner.
        return
    if db.scalar(select(User.id).where(User.id == owner_id, User.is_active.is_(True))
                 .with_for_update(read=True, key_share=True)) is None:
        raise UnauthorizedError("Account is no longer available")
