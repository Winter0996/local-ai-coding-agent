import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlmodel import Session, select

from app.auth.models import RefreshToken

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. "
        "Generate one with `python -c \"import secrets; print(secrets.token_urlsafe(64))\"` "
        "and put it in your .env file — never hardcode it or commit it."
    )

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_aware_utc(value: datetime) -> datetime:
    # SQLite has no native timestamp-with-timezone type, so datetimes read
    # back from the DB come back naive even though they were written as UTC.
    # Re-attach UTC tzinfo before comparing so this doesn't blow up with
    # "can't compare offset-naive and offset-aware datetimes".
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# ---------------------------------------------------------------------------
# Access tokens (short-lived JWT, sent in the Authorization header, kept in
# memory on the frontend — never localStorage, to limit XSS blast radius)
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    now = _utcnow()
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the user_id (sub claim). Raises jwt.PyJWTError on invalid/expired."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload["sub"]


# ---------------------------------------------------------------------------
# Refresh tokens (opaque random string, stored httpOnly cookie client-side,
# stored HASHED server-side, rotated on every use)
# ---------------------------------------------------------------------------


def _hash_token(raw_token: str) -> str:
    # SHA-256 is fine here (unlike passwords, this is a high-entropy random
    # token, not something an attacker can feasibly brute-force offline).
    return hashlib.sha256(raw_token.encode()).hexdigest()


def issue_refresh_token(
    db: Session, user_id: str, family_id: str | None = None
) -> str:
    """Create and persist a new refresh token, returning the raw value to
    send to the client. `family_id` groups all tokens descended from one
    login — reused to detect theft on rotation."""
    raw_token = secrets.token_urlsafe(64)
    record = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        family_id=family_id or str(uuid.uuid4()),
        expires_at=_utcnow() + REFRESH_TOKEN_TTL,
    )
    db.add(record)
    db.commit()
    return raw_token


class RefreshTokenInvalid(Exception):
    pass


class RefreshTokenReused(Exception):
    """Raised when a token that was already rotated-away gets presented
    again — a strong signal of theft. Caller should revoke the whole
    token family and force re-login."""


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[str, str]:
    """Validate a refresh token, revoke it, and issue a replacement in the
    same family. Returns (new_raw_refresh_token, user_id)."""
    token_hash = _hash_token(raw_token)
    record = db.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()

    if record is None:
        raise RefreshTokenInvalid("Unknown refresh token")

    if record.revoked:
        # This exact token was already used once before — someone is
        # replaying an old token, likely because it was stolen. Revoke every
        # token in the family so the legitimate user is forced to re-login.
        _revoke_family(db, record.family_id)
        raise RefreshTokenReused("Refresh token reuse detected")

    if _as_aware_utc(record.expires_at) < _utcnow():
        raise RefreshTokenInvalid("Refresh token expired")

    new_raw = issue_refresh_token(db, record.user_id, family_id=record.family_id)
    record.revoked = True
    record.replaced_by = _hash_token(new_raw)
    db.add(record)
    db.commit()

    return new_raw, record.user_id


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    token_hash = _hash_token(raw_token)
    record = db.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    if record is not None:
        record.revoked = True
        db.add(record)
        db.commit()


def _revoke_family(db: Session, family_id: str) -> None:
    records = db.exec(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    for record in records:
        record.revoked = True
        db.add(record)
    db.commit()
