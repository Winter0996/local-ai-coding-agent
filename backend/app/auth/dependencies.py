import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.auth.models import User
from app.auth.tokens import decode_access_token
from app.db import get_db

# tokenUrl is only used to populate FastAPI's auto-generated OpenAPI docs
# (the "Authorize" button in /docs) — the actual login endpoint below issues
# the token, this class does not perform auth itself.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_error

    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise credentials_error from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error

    return user
