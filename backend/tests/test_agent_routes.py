import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ["CODEFORGE_DB_PATH"] = ":memory:"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.db import engine  # noqa: E402
from app.llm.ollama import OllamaProvider  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def setup_function() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


async def fake_generate(self: OllamaProvider, message: str) -> str:
    return "def greet(name):\n    return f'hi {name}'\n"


def _auth_headers(email: str = "agent-tester@example.com") -> dict[str, str]:
    client.post(
        "/api/auth/register", json={"email": email, "password": "correcthorsebattery"}
    )
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebattery"}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _select_and_index_repo(tmp_path, headers) -> str:
    (tmp_path / "greet.py").write_text(
        "def greet(name):\n    return f'hello {name}'\n", encoding="utf-8"
    )
    select_response = client.post(
        "/api/repo/select", json={"path": str(tmp_path)}, headers=headers
    )
    workspace_id = select_response.json()["id"]
    client.post(f"/api/repo/{workspace_id}/index", headers=headers)
    return workspace_id


def test_propose_requires_auth() -> None:
    response = client.post("/api/agent/some-id/propose", json={"message": "do something"})
    assert response.status_code == 401


def test_propose_returns_diff_and_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    headers = _auth_headers()
    workspace_id = _select_and_index_repo(tmp_path, headers)

    response = client.post(
        f"/api/agent/{workspace_id}/propose",
        json={"message": "greet.py: change hello to hi"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target_path"] == "greet.py"
    assert "hi" in body["proposed_content"]
    assert body["diff"] != ""


def test_apply_writes_approved_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    headers = _auth_headers()
    workspace_id = _select_and_index_repo(tmp_path, headers)

    propose_response = client.post(
        f"/api/agent/{workspace_id}/propose",
        json={"message": "greet.py: change hello to hi"},
        headers=headers,
    )
    proposed_content = propose_response.json()["proposed_content"]

    apply_response = client.post(
        f"/api/agent/{workspace_id}/apply",
        json={"path": "greet.py", "content": proposed_content},
        headers=headers,
    )

    assert apply_response.status_code == 200
    assert (tmp_path / "greet.py").read_text() == proposed_content


def test_apply_rejects_path_traversal(tmp_path) -> None:
    headers = _auth_headers()
    workspace_id = _select_and_index_repo(tmp_path, headers)

    response = client.post(
        f"/api/agent/{workspace_id}/apply",
        json={"path": "../../etc/passwd", "content": "malicious"},
        headers=headers,
    )

    assert response.status_code == 403


def test_cannot_propose_on_another_users_workspace(tmp_path) -> None:
    owner_headers = _auth_headers("owner2@example.com")
    workspace_id = _select_and_index_repo(tmp_path, owner_headers)

    other_headers = _auth_headers("someone-else2@example.com")
    response = client.post(
        f"/api/agent/{workspace_id}/propose",
        json={"message": "anything"},
        headers=other_headers,
    )

    assert response.status_code == 404