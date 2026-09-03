import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ["CODEFORGE_DB_PATH"] = ":memory:"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def setup_function() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def _auth_headers() -> dict[str, str]:
    client.post(
        "/api/auth/register",
        json={"email": "fs-tester@example.com", "password": "correcthorsebattery"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "fs-tester@example.com", "password": "correcthorsebattery"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_browse_requires_auth() -> None:
    response = client.get("/api/filesystem/browse")
    assert response.status_code == 401


def test_browse_lists_a_directory(tmp_path) -> None:
    (tmp_path / "sub").mkdir()
    headers = _auth_headers()

    response = client.get(
        "/api/filesystem/browse", params={"path": str(tmp_path)}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == str(tmp_path)
    assert any(e["name"] == "sub" for e in body["entries"])
    assert "roots" in body


def test_browse_nonexistent_path_returns_404(tmp_path) -> None:
    headers = _auth_headers()

    response = client.get(
        "/api/filesystem/browse",
        params={"path": str(tmp_path / "nope")},
        headers=headers,
    )

    assert response.status_code == 404