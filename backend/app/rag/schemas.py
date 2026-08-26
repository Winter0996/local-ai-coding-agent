from pydantic import BaseModel, Field


class IndexResponse(BaseModel):
    workspace_id: str
    file_count: int
    chunk_count: int
    skipped_file_count: int
    duration_seconds: float


class IndexStatusResponse(BaseModel):
    workspace_id: str
    indexed: bool
    chunk_count: int | None = None


class SemanticSearchHit(BaseModel):
    path: str
    symbol: str | None
    chunk_type: str
    start_line: int
    end_line: int
    text: str
    score: float


class SemanticSearchResponse(BaseModel):
    query: str
    hits: list[SemanticSearchHit]


class SemanticSearchQuery(BaseModel):
    q: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=8, ge=1, le=30)