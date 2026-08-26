import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from app.rag import store
from app.rag.chunking import chunk_file
from app.rag.embeddings import get_embedding_provider
from app.repository.security import EXCLUDED_DIRS, is_binary_file

# Files larger than this are skipped during indexing entirely (not read) —
# keeps indexing time bounded on repos with large generated/data/lockfiles.
# Separate from repository.security.MAX_FILE_BYTES, which caps what the
# file *viewer* returns, not what gets indexed.
MAX_INDEX_FILE_BYTES = 512 * 1024

# Only meaningfully-textual/code extensions get indexed — no point
# embedding lockfiles, images-as-base64, or minified bundles.
INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".java", ".kt", ".go",
    ".rs", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs", ".swift",
    ".html", ".css", ".scss", ".sql", ".md", ".sh", ".ps1", ".toml",
    ".yaml", ".yml", ".json",
}


def _iter_indexable_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in INDEXABLE_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_INDEX_FILE_BYTES:
                continue
        except OSError:
            continue
        if is_binary_file(path):
            continue
        yield path


@dataclass
class IndexResult:
    workspace_id: str
    file_count: int
    chunk_count: int
    skipped_file_count: int
    duration_seconds: float


def index_repository(root: Path, workspace_id: str) -> IndexResult:
    """Full re-index of a workspace: walk indexable files, chunk each one,
    embed every chunk, and replace the workspace's vector-store collection
    wholesale. Synchronous and blocking by design for v1 — a background
    job/websocket progress stream is the natural upgrade once repos large
    enough to make this slow are a real usage pattern."""
    started = time.monotonic()
    provider = get_embedding_provider()

    all_texts: list[str] = []
    all_ids: list[str] = []
    all_metadatas: list[dict] = []

    file_count = 0
    skipped = 0

    for file_path in _iter_indexable_files(root):
        rel_path = file_path.relative_to(root).as_posix()
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped += 1
            continue

        chunks = chunk_file(rel_path, content, file_path.suffix)
        if not chunks:
            continue

        file_count += 1
        for i, chunk in enumerate(chunks):
            all_texts.append(chunk.text)
            # Chunk IDs must be stable across re-indexes of the SAME content
            # (not required for correctness here since replace_chunks wipes
            # the whole collection first, but stable IDs make the index
            # easier to reason about/debug).
            all_ids.append(f"{rel_path}::{i}::{chunk.start_line}-{chunk.end_line}")
            all_metadatas.append(
                {
                    "path": chunk.path,
                    "symbol": chunk.symbol or "",
                    "chunk_type": chunk.chunk_type,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
            )

    embeddings = provider.embed(all_texts) if all_texts else []

    store.replace_chunks(
        workspace_id=workspace_id,
        ids=all_ids,
        documents=all_texts,
        embeddings=embeddings,
        metadatas=all_metadatas,
    )

    return IndexResult(
        workspace_id=workspace_id,
        file_count=file_count,
        chunk_count=len(all_ids),
        skipped_file_count=skipped,
        duration_seconds=time.monotonic() - started,
    )


@dataclass
class SearchHit:
    path: str
    symbol: str | None
    chunk_type: str
    start_line: int
    end_line: int
    text: str
    score: float  # bounded 0-1 similarity, higher is more relevant


def semantic_search(workspace_id: str, query_text: str, top_k: int = 8) -> list[SearchHit]:
    provider = get_embedding_provider()
    query_embedding = provider.embed([query_text])[0]

    result = store.query(workspace_id, query_embedding, top_k)
    if result is None:
        return []

    hits: list[SearchHit] = []
    documents = result.get("documents") or [[]]
    metadatas = result.get("metadatas") or [[]]
    distances = result.get("distances") or [[]]

    for doc, meta, distance in zip(documents[0], metadatas[0], distances[0], strict=True):
        # The raw distance metric is provider/index-dependent (squared L2 by
        # default); converting to a bounded 0-1 "similarity" (higher =
        # better) is a friendlier contract for API consumers than exposing
        # a raw, implementation-specific distance number.
        score = 1.0 / (1.0 + distance)
        hits.append(
            SearchHit(
                path=meta["path"],
                symbol=meta["symbol"] or None,
                chunk_type=meta["chunk_type"],
                start_line=meta["start_line"],
                end_line=meta["end_line"],
                text=doc,
                score=round(score, 4),
            )
        )
    return hits


def index_status(workspace_id: str) -> int | None:
    """Returns the indexed chunk count, or None if never indexed."""
    return store.collection_count(workspace_id)