import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ["CODEFORGE_DB_PATH"] = ":memory:"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def setup_function() -> None:
    # Fresh schema for every test so tests don't leak state into each other.
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def _register(email: str = "nathan@example.com", password: str = "correcthorsebattery") -> None:
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text


def test_register_rejects_too_short_password() -> None:
    # Caught by the Pydantic schema's min_length=12 -> 422 Unprocessable Entity.
    response = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_register_rejects_common_password() -> None:
    # Long enough to pass the schema, but still on the common-password denylist
    # -> caught by validate_password_strength() -> 400 Bad Request.
    response = client.post(
        "/api/auth/register",
        json={"email": "weak2@example.com", "password": "password1234"},
    )
    assert response.status_code == 400


def test_register_rejects_duplicate_email() -> None:
    _register()
    response = client.post(
        "/api/auth/register",
        json={"email": "nathan@example.com", "password": "anotherlongpassword"},
    )
    assert response.status_code == 400


def test_login_success_returns_access_token_and_sets_refresh_cookie() -> None:
    _register()
    response = client.post(
        "/api/auth/login",
        json={"email": "nathan@example.com", "password": "correcthorsebattery"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "codeforge_refresh_token" in response.cookies


def test_login_wrong_password_rejected() -> None:
    _register()
    response = client.post(
        "/api/auth/login",
        json={"email": "nathan@example.com", "password": "wrongpassword123"},
    )
    assert response.status_code == 401


def test_chat_requires_auth() -> None:
    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_me_with_valid_access_token() -> None:
    _register()
    login_response = client.post(
        "/api/auth/login",
        json={"email": "nathan@example.com", "password": "correcthorsebattery"},
    )
    access_token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "nathan@example.com"


def test_refresh_rotates_token_and_old_one_becomes_invalid() -> None:
    _register()
    login_response = client.post(
        "/api/auth/login",
        json={"email": "nathan@example.com", "password": "correcthorsebattery"},
    )
    old_refresh_cookie = login_response.cookies["codeforge_refresh_token"]

    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 200
    assert "access_token" in refresh_response.json()

    # Replaying the now-rotated-out cookie should be rejected as reuse.
    client.cookies.set("codeforge_refresh_token", old_refresh_cookie)
    reuse_response = client.post("/api/auth/refresh")
    assert reuse_response.status_code == 401


def test_logout_revokes_refresh_token() -> None:
    _register()
    client.post(
        "/api/auth/login",
        json={"email": "nathan@example.com", "password": "correcthorsebattery"},
    )

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 204

    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 401
