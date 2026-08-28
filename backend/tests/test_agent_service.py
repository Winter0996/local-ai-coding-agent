import pytest

from app.agent import service
from app.llm.ollama import OllamaProvider
from app.rag import service as rag_service


def _write_sample_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "greet.py").write_text(
        "def greet(name):\n    return f'hello {name}'\n", encoding="utf-8"
    )
    (tmp_path / "src" / "math_utils.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    return tmp_path


@pytest.mark.asyncio
async def test_propose_uses_explicit_path_when_named(tmp_path, monkeypatch):
    _write_sample_repo(tmp_path)
    rag_service.index_repository(tmp_path, workspace_id="agent-ws-1")

    async def fake_generate(self, prompt):
        return "def add(a, b):\n    return a + b  # now with a comment\n"

    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)

    proposal = await service.propose_change(
        tmp_path, "agent-ws-1", "add a comment to src/math_utils.py"
    )

    assert proposal.target_path == "src/math_utils.py"
    assert "now with a comment" in proposal.proposed_content
    assert "+def add" in proposal.diff or "+    return a + b  # now with a comment" in proposal.diff


@pytest.mark.asyncio
async def test_propose_falls_back_to_semantic_search(tmp_path, monkeypatch):
    _write_sample_repo(tmp_path)
    rag_service.index_repository(tmp_path, workspace_id="agent-ws-2")

    async def fake_generate(self, prompt):
        return "def greet(name):\n    return f'hi {name}'\n"

    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)

    proposal = await service.propose_change(
        tmp_path,
        "agent-ws-2",
        "def greet(name):\n    return f'hello {name}'",  # matches greet.py content closely
    )

    assert proposal.target_path == "src/greet.py"


@pytest.mark.asyncio
async def test_propose_raises_when_no_target_found(tmp_path):
    _write_sample_repo(tmp_path)
    # Never indexed — no semantic hits, and message names no real file.
    with pytest.raises(service.NoTargetFileError):
        await service.propose_change(tmp_path, "never-indexed-ws", "do something vague")


@pytest.mark.asyncio
async def test_propose_strips_code_fences(tmp_path, monkeypatch):
    _write_sample_repo(tmp_path)
    rag_service.index_repository(tmp_path, workspace_id="agent-ws-3")

    async def fenced_generate(self, prompt):
        return "```python\ndef add(a, b):\n    return a + b\n```"

    monkeypatch.setattr(OllamaProvider, "generate", fenced_generate)

    proposal = await service.propose_change(
        tmp_path, "agent-ws-3", "touch src/math_utils.py please"
    )

    assert not proposal.proposed_content.startswith("```")
    assert not proposal.proposed_content.endswith("```")


def test_apply_change_writes_file(tmp_path):
    _write_sample_repo(tmp_path)

    result = service.apply_change(
        tmp_path, "src/math_utils.py", "def add(a, b):\n    return a + b + 0\n"
    )

    assert result.path == "src/math_utils.py"
    written = (tmp_path / "src" / "math_utils.py").read_text()
    assert written == "def add(a, b):\n    return a + b + 0\n"


def test_apply_change_rejects_path_traversal(tmp_path):
    _write_sample_repo(tmp_path)
    (tmp_path.parent / "outside_secret.txt").write_text("do not touch", encoding="utf-8")

    from app.repository.service import PathTraversalError

    with pytest.raises(PathTraversalError):
        service.apply_change(tmp_path, "../outside_secret.txt", "overwritten")


def test_apply_change_rejects_nonexistent_file(tmp_path):
    _write_sample_repo(tmp_path)

    from app.repository.service import RepositoryNotFoundError

    with pytest.raises(RepositoryNotFoundError):
        service.apply_change(tmp_path, "src/does_not_exist.py", "new content")