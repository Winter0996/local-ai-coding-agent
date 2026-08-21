import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user
from app.auth.hashing import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.auth.models import User
from app.auth.rate_limit import enforce_login_rate_limit
from app.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.auth.tokens import (
    RefreshTokenInvalid,
    RefreshTokenReused,
    create_access_token,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "codeforge_refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"
# Over plain http (local dev) a "Secure" cookie won't be sent by the browser
# at all, so default this to False locally and flip it on in any deployed
# environment via COOKIE_SECURE=true.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=7 * 24 * 60 * 60,  # 7 days, matches REFRESH_TOKEN_TTL
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.exec(select(User).where(User.email == payload.email)).first()
    if existing is not None:
        # Deliberately vague — confirming "this email exists" to an
        # unauthenticated caller is a (minor) user-enumeration leak.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not register with the provided details.",
        )

    try:
        validate_password_strength(payload.password)
    except WeakPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    enforce_login_rate_limit(request)

    user = db.exec(select(User).where(User.email == payload.email)).first()

    # Run verify_password even when no user was found, against a dummy hash,
    # so login takes roughly the same time either way — otherwise a faster
    # response for unknown emails becomes a timing side-channel that leaks
    # which emails are registered.
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$dGhpc2lzYWR1bW15aGFzaA"
    password_ok = verify_password(
        payload.password, user.hashed_password if user else dummy_hash
    )

    if user is None or not user.is_active or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    access_token = create_access_token(user.id)
    refresh_token = issue_refresh_token(db, user.id)
    _set_refresh_cookie(response, refresh_token)

    return AccessTokenResponse(access_token=access_token)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided.",
        )

    try:
        new_refresh_token, user_id = rotate_refresh_token(db, raw_refresh_token)
    except RefreshTokenReused as exc:
        # The whole token family has already been revoked inside
        # rotate_refresh_token() — just make sure the client's stale cookie
        # is cleared so it stops retrying with it.
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid, please log in again.",
        ) from exc
    except RefreshTokenInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired, please log in again.",
        ) from exc

    _set_refresh_cookie(response, new_refresh_token)
    return AccessTokenResponse(access_token=create_access_token(user_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh_token is not None:
        revoke_refresh_token(db, raw_refresh_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
