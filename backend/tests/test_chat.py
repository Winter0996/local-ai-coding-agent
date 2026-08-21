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
