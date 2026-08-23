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
        json={"email": "repo-tester@example.com", "password": "correcthorsebattery"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "repo-tester@example.com", "password": "correcthorsebattery"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_sample_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "def hello():\n    print('hello world')\n", encoding="utf-8"
    )
    (tmp_path / "src" / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Sample project\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("should be excluded", encoding="utf-8")
    (tmp_path / "binary.dat").write_bytes(b"\x00\x01\x02\xff")
    return tmp_path


def test_select_repository_requires_auth() -> None:
    response = client.post("/api/repo/select", json={"path": "/tmp"})
    assert response.status_code == 401


def test_select_repository_rejects_relative_path(tmp_path) -> None:
    headers = _auth_headers()
    response = client.post("/api/repo/select", json={"path": "relative/path"}, headers=headers)
    assert response.status_code == 400


def test_select_repository_rejects_nonexistent_path() -> None:
    headers = _auth_headers()
    response = client.post(
        "/api/repo/select", json={"path": "/definitely/does/not/exist"}, headers=headers
    )
    assert response.status_code == 400


def test_select_repository_success(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()

    response = client.post("/api/repo/select", json={"path": str(tmp_path)}, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["root"] == str(tmp_path.resolve())
    assert "id" in body


def _select(tmp_path, headers) -> str:
    response = client.post("/api/repo/select", json={"path": str(tmp_path)}, headers=headers)
    return response.json()["id"]


def test_tree_excludes_node_modules_and_includes_src(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()
    workspace_id = _select(tmp_path, headers)

    response = client.get(f"/api/repo/{workspace_id}/tree", headers=headers)

    assert response.status_code == 200
    tree = response.json()["root"]
    child_names = {child["name"] for child in tree["children"]}
    assert "src" in child_names
    assert "README.md" in child_names
    assert "node_modules" not in child_names


def test_read_file_returns_content_and_language(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()
    workspace_id = _select(tmp_path, headers)

    response = client.get(
        f"/api/repo/{workspace_id}/file",
        params={"path": "src/main.py"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "hello world" in body["content"]
    assert body["language"] == "Python"
    assert body["truncated"] is False


def test_read_file_rejects_path_traversal(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()
    workspace_id = _select(tmp_path, headers)

    response = client.get(
        f"/api/repo/{workspace_id}/file",
        params={"path": "../../../../etc/passwd"},
        headers=headers,
    )

    assert response.status_code == 403


def test_read_file_rejects_binary(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()
    workspace_id = _select(tmp_path, headers)

    response = client.get(
        f"/api/repo/{workspace_id}/file",
        params={"path": "binary.dat"},
        headers=headers,
    )

    assert response.status_code == 415


def test_search_finds_matches_and_excludes_node_modules(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()
    workspace_id = _select(tmp_path, headers)

    response = client.get(
        f"/api/repo/{workspace_id}/search",
        params={"q": "def "},
        headers=headers,
    )

    assert response.status_code == 200
    matches = response.json()["matches"]
    paths = {m["path"] for m in matches}
    assert "src/main.py" in paths
    assert "src/utils.py" in paths
    assert not any("node_modules" in p for p in paths)


def test_metadata_reports_language_breakdown(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    headers = _auth_headers()
    workspace_id = _select(tmp_path, headers)

    response = client.get(f"/api/repo/{workspace_id}/metadata", headers=headers)

    assert response.status_code == 200
    body = response.json()
    languages = {entry["language"]: entry["file_count"] for entry in body["languages"]}
    assert languages.get("Python") == 2
    assert body["has_git"] is False


def test_cannot_access_another_users_workspace(tmp_path) -> None:
    _make_sample_repo(tmp_path)
    owner_headers = _auth_headers()
    workspace_id = _select(tmp_path, owner_headers)

    client.post(
        "/api/auth/register",
        json={"email": "someone-else@example.com", "password": "correcthorsebattery"},
    )
    other_login = client.post(
        "/api/auth/login",
        json={"email": "someone-else@example.com", "password": "correcthorsebattery"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get(f"/api/repo/{workspace_id}/tree", headers=other_headers)

    assert response.status_code == 404