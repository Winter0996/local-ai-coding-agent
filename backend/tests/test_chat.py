from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.llm.ollama import OllamaProvider
from app.main import app

client = TestClient(app)


async def fake_generate(self: OllamaProvider, message: str) -> str:
    return f"Mock response to: {message}"


def _fake_current_user() -> User:
    return User(id="test-user-id", email="test@example.com", hashed_password="unused")


def test_chat_route(monkeypatch) -> None:
    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    # /api/chat is auth-protected; override the dependency here rather than
    # doing a full register/login round trip, since this test is only
    # concerned with the chat behavior itself.
    app.dependency_overrides[get_current_user] = _fake_current_user

    try:
        response = client.post(
            "/api/chat",
            json={"message": "Hello CodeForge"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert "Mock response" in response.json()["response"]


def test_chat_route_requires_auth() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Hello CodeForge"},
    )

    assert response.status_code == 401


def test_chat_without_workspace_id_has_no_sources(monkeypatch) -> None:
    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    app.dependency_overrides[get_current_user] = _fake_current_user

    try:
        response = client.post("/api/chat", json={"message": "Hello CodeForge"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["sources"] == []


def test_chat_with_workspace_id_augments_prompt_and_returns_sources(
    monkeypatch, tmp_path
) -> None:
    captured_prompts: list[str] = []

    async def capturing_generate(self: OllamaProvider, message: str) -> str:
        captured_prompts.append(message)
        return "mocked response grounded in context"

    monkeypatch.setattr(OllamaProvider, "generate", capturing_generate)

    client.post(
        "/api/auth/register",
        json={"email": "chat-rag@example.com", "password": "correcthorsebattery"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "chat-rag@example.com", "password": "correcthorsebattery"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    (tmp_path / "greet.py").write_text(
        "def greet(name):\n    return f'hello {name}'\n", encoding="utf-8"
    )
    select_response = client.post(
        "/api/repo/select", json={"path": str(tmp_path)}, headers=headers
    )
    workspace_id = select_response.json()["id"]
    client.post(f"/api/repo/{workspace_id}/index", headers=headers)

    response = client.post(
        "/api/chat",
        json={
            "message": "def greet(name):\n    return f'hello {name}'",
            "workspace_id": workspace_id,
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["path"] == "greet.py"

    # The prompt actually sent to Ollama should include the retrieved
    # context, clearly delimited from the user's question.
    assert len(captured_prompts) == 1
    assert "BEGIN REPOSITORY CONTEXT" in captured_prompts[0]
    assert "greet.py" in captured_prompts[0]


def test_chat_with_unowned_workspace_id_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    app.dependency_overrides[get_current_user] = _fake_current_user

    try:
        response = client.post(
            "/api/chat",
            json={"message": "Hello", "workspace_id": "does-not-exist"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404