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


def _auth_headers(email: str = "rag-tester@example.com") -> dict[str, str]:
    client.post(
        "/api/auth/register", json={"email": email, "password": "correcthorsebattery"}
    )
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebattery"}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _select_repo(tmp_path, headers) -> str:
    (tmp_path / "app.py").write_text(
        "def greet(name):\n    return f'hello {name}'\n", encoding="utf-8"
    )
    response = client.post("/api/repo/select", json={"path": str(tmp_path)}, headers=headers)
    return response.json()["id"]


def test_index_requires_auth() -> None:
    response = client.post("/api/repo/some-id/index")
    assert response.status_code == 401


def test_index_status_before_indexing(tmp_path) -> None:
    headers = _auth_headers()
    workspace_id = _select_repo(tmp_path, headers)

    response = client.get(f"/api/repo/{workspace_id}/index/status", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["indexed"] is False
    assert body["chunk_count"] is None


def test_index_then_status_reflects_chunk_count(tmp_path) -> None:
    headers = _auth_headers()
    workspace_id = _select_repo(tmp_path, headers)

    index_response = client.post(f"/api/repo/{workspace_id}/index", headers=headers)
    assert index_response.status_code == 200
    assert index_response.json()["chunk_count"] >= 1

    status_response = client.get(f"/api/repo/{workspace_id}/index/status", headers=headers)
    assert status_response.json()["indexed"] is True
    assert status_response.json()["chunk_count"] == index_response.json()["chunk_count"]


def test_semantic_search_endpoint(tmp_path) -> None:
    headers = _auth_headers()
    workspace_id = _select_repo(tmp_path, headers)
    client.post(f"/api/repo/{workspace_id}/index", headers=headers)

    response = client.get(
        f"/api/repo/{workspace_id}/search/semantic",
        params={"q": "def greet(name):\n    return f'hello {name}'"},
        headers=headers,
    )

    assert response.status_code == 200
    hits = response.json()["hits"]
    assert len(hits) >= 1
    assert hits[0]["path"] == "app.py"


def test_cannot_index_another_users_workspace(tmp_path) -> None:
    owner_headers = _auth_headers("owner@example.com")
    workspace_id = _select_repo(tmp_path, owner_headers)

    other_headers = _auth_headers("someone-else@example.com")
    response = client.post(f"/api/repo/{workspace_id}/index", headers=other_headers)

    assert response.status_code == 404