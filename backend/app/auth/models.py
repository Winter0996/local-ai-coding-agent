import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = Field(default=True)


class RefreshToken(SQLModel, table=True):
    """
    Refresh tokens are stored hashed (never in plaintext) so a leaked database
    doesn't hand out valid sessions. `revoked` + `replaced_by` implement
    rotation-with-reuse-detection: if a revoked token is ever presented again,
    it signals theft and every token in the family is revoked (see tokens.py).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, nullable=False)
    token_hash: str = Field(unique=True, index=True, nullable=False)
    family_id: str = Field(index=True, nullable=False)
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime = Field(nullable=False)
    revoked: bool = Field(default=False)
    replaced_by: str | None = Field(default=None)
