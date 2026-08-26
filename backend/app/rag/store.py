import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import NotFoundError

_client: chromadb.ClientAPI | None = None


def _chroma_dir() -> str:
    # Read lazily (not as a module-level constant) so tests can point this
    # at a fresh tmp_path per test via monkeypatch before the client is
    # first created.
    return os.getenv("CHROMA_PERSIST_DIR", "chroma_data")


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        chroma_dir = _chroma_dir()
        Path(chroma_dir).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=chroma_dir)
    return _client


def reset_client() -> None:
    """Test hook — clears the cached client so tests using a different
    CHROMA_PERSIST_DIR (e.g. a tmp_path) get a fresh one."""
    global _client
    _client = None


def _collection_name(workspace_id: str) -> str:
    # Chroma collection names must be 3-63 chars of [a-zA-Z0-9._-] — a
    # workspace UUID already satisfies this; the prefix is just for clarity
    # when inspecting the Chroma data directory directly.
    return f"workspace_{workspace_id}"


def get_or_create_collection(workspace_id: str):
    return _get_client().get_or_create_collection(name=_collection_name(workspace_id))


def delete_collection(workspace_id: str) -> None:
    try:
        _get_client().delete_collection(name=_collection_name(workspace_id))
    except NotFoundError:
        pass  # never indexed yet — deleting is idempotent


def replace_chunks(
    workspace_id: str,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> None:
    """Full re-index: wipes any existing collection for this workspace and
    inserts fresh. Simpler and more correct than incrementally diffing
    against the previous index for a v1 — a since-deleted or -renamed file
    can never linger stale in the index this way. Revisit with
    content-hash-based incremental updates if full re-index time becomes a
    real problem on very large repositories."""
    delete_collection(workspace_id)
    if not ids:
        return
    collection = get_or_create_collection(workspace_id)
    # Chroma's add() has a practical batch-size ceiling; chunk large
    # repositories into batches rather than sending everything in one call.
    batch_size = 500
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )


def query(
    workspace_id: str, query_embedding: list[float], top_k: int
) -> dict[str, Any] | None:
    try:
        collection = _get_client().get_collection(name=_collection_name(workspace_id))
    except NotFoundError:
        return None  # not indexed yet
    return collection.query(query_embeddings=[query_embedding], n_results=top_k)


def collection_count(workspace_id: str) -> int | None:
    try:
        collection = _get_client().get_collection(name=_collection_name(workspace_id))
    except NotFoundError:
        return None
    return collection.count()