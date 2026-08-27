import pytest

from app.auth.rate_limit import _attempts
from app.rag import store as rag_store
from app.rag.embeddings import reset_embedding_provider


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The login rate limiter tracks attempts in a module-level dict scoped
    to the whole process (see app/auth/rate_limit.py) — correct for a
    single-process app, but it means attempts accumulate across every test
    in the same pytest session unless we reset it here. Without this,
    test files that run after several login-heavy tests start getting 429'd
    even though each test is logically independent."""
    _attempts.clear()
    yield
    _attempts.clear()


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch, tmp_path):
    """Tests never hit the real sentence-transformers model — that would
    require a network call and a large download on every test run. Instead,
    every test gets CODEFORGE_FAKE_EMBEDDINGS=1 (a deterministic, hash-based
    provider — see app/rag/embeddings.py) and its own isolated Chroma
    persistence directory. Both app/rag/store.py's client and
    app/rag/embeddings.py's provider are cached module-level singletons, so
    they're explicitly reset before and after each test to prevent one
    test's vector data or provider choice from leaking into the next."""
    monkeypatch.setenv("CODEFORGE_FAKE_EMBEDDINGS", "1")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma_data"))
    rag_store.reset_client()
    reset_embedding_provider()
    yield
    rag_store.reset_client()
    reset_embedding_provider()