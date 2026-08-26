import hashlib
import os
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Real embedding provider used in production. The model is loaded
    lazily on first call to embed() — not at import time or construction —
    so importing this module never triggers a model download; only the
    first actual indexing/search request does.

    Model choice: all-MiniLM-L6-v2 — small (~80MB), fast on CPU, 384-dim,
    a well-established default for local semantic search. Downloaded once
    from Hugging Face on first use and cached locally afterward (typically
    under ~/.cache/huggingface) — requires internet access the first time
    only.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    dimension = 384

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.MODEL_NAME)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return vectors.tolist()


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic, dependency-free embedding provider used only in
    tests. Hashes each text into a fixed-size vector — has no real semantic
    meaning, but identical text always produces an identical vector, which
    is enough to test the index -> store -> query pipeline end-to-end
    without a network call or a multi-hundred-MB model download. Selected
    only via CODEFORGE_FAKE_EMBEDDINGS=1, never by default."""

    dimension = 32

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([b / 255.0 for b in digest[: self.dimension]])
        return vectors


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider

    if os.getenv("CODEFORGE_FAKE_EMBEDDINGS") == "1":
        _provider = FakeEmbeddingProvider()
    else:
        _provider = SentenceTransformerEmbeddingProvider()
    return _provider


def reset_embedding_provider() -> None:
    """Test hook: clears the cached singleton so tests can toggle
    CODEFORGE_FAKE_EMBEDDINGS and get a freshly-selected provider."""
    global _provider
    _provider = None