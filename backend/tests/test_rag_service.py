from app.rag import service, store


def _write_sample_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        "def hash_password(password):\n"
        "    \"\"\"Hashes a password using Argon2id.\"\"\"\n"
        "    return argon2_hash(password)\n"
        "\n"
        "\n"
        "def verify_password(password, hashed):\n"
        "    return argon2_verify(password, hashed)\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "math_utils.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def multiply(a, b):\n"
        "    return a * b\n",
        encoding="utf-8",
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text(
        "function shouldBeExcluded() {}\n", encoding="utf-8"
    )
    return tmp_path


def test_index_repository_counts_files_and_chunks(tmp_path):
    _write_sample_repo(tmp_path)

    result = service.index_repository(tmp_path, workspace_id="ws-1")

    assert result.file_count == 2  # auth.py, math_utils.py (node_modules excluded)
    assert result.chunk_count == 4  # 2 functions per file
    assert result.skipped_file_count == 0


def test_index_status_reflects_indexed_chunk_count(tmp_path):
    _write_sample_repo(tmp_path)

    assert service.index_status("ws-2") is None  # never indexed

    result = service.index_repository(tmp_path, workspace_id="ws-2")

    assert service.index_status("ws-2") == result.chunk_count


def test_reindex_replaces_rather_than_accumulates(tmp_path):
    _write_sample_repo(tmp_path)
    first = service.index_repository(tmp_path, workspace_id="ws-3")

    # Re-indexing the same unchanged repo should produce the same chunk
    # count, not double it — proves replace_chunks() actually replaces.
    second = service.index_repository(tmp_path, workspace_id="ws-3")

    assert first.chunk_count == second.chunk_count
    assert store.collection_count("ws-3") == second.chunk_count


def test_semantic_search_finds_exact_chunk_text(tmp_path):
    _write_sample_repo(tmp_path)
    service.index_repository(tmp_path, workspace_id="ws-4")

    # The fake embedding provider is hash-based (not semantically meaningful
    # — see app/rag/embeddings.py), so the reliable way to prove the
    # retrieval pipeline works end-to-end is to query with text identical to
    # an indexed chunk, which is guaranteed to produce the closest possible
    # match (distance 0) regardless of embedding quality.
    hits = service.semantic_search(
        "ws-4",
        "def hash_password(password):\n"
        '    """Hashes a password using Argon2id."""\n'
        "    return argon2_hash(password)",
        top_k=5,
    )

    assert len(hits) > 0
    assert hits[0].path == "src/auth.py"
    assert hits[0].symbol == "hash_password"
    assert hits[0].score == 1.0  # distance 0 -> perfect similarity


def test_semantic_search_on_unindexed_workspace_returns_empty():
    hits = service.semantic_search("never-indexed-workspace", "anything", top_k=5)
    assert hits == []


def test_search_excludes_node_modules(tmp_path):
    _write_sample_repo(tmp_path)
    service.index_repository(tmp_path, workspace_id="ws-5")

    hits = service.semantic_search("ws-5", "shouldBeExcluded", top_k=10)

    assert not any("node_modules" in h.path for h in hits)