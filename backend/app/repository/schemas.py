from __future__ import annotations

from pydantic import BaseModel, Field


class SelectRepositoryRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


class WorkspaceResponse(BaseModel):
    id: str
    root: str
    name: str
    created_at: str


class LanguageBreakdown(BaseModel):
    language: str
    file_count: int


class RepositoryMetadataResponse(BaseModel):
    workspace_id: str
    root: str
    name: str
    file_count: int
    total_size_bytes: int
    languages: list[LanguageBreakdown]
    has_git: bool


class TreeNodeResponse(BaseModel):
    name: str
    path: str
    type: str
    language: str | None = None
    children: list[TreeNodeResponse] = []


TreeNodeResponse.model_rebuild()


class FileTreeResponse(BaseModel):
    root: TreeNodeResponse
    truncated: bool


class FileContentResponse(BaseModel):
    path: str
    language: str | None
    content: str
    truncated: bool
    size_bytes: int


class SearchMatchResponse(BaseModel):
    path: str
    line_number: int
    line_text: str


class SearchResponse(BaseModel):
    query: str
    matches: list[SearchMatchResponse]
    truncated: bool