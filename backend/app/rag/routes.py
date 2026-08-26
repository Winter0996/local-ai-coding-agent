from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db import get_db
from app.rag import service
from app.rag.schemas import (
    IndexResponse,
    IndexStatusResponse,
    SemanticSearchHit,
    SemanticSearchResponse,
)
from app.repository import service as repo_service

router = APIRouter(prefix="/repo", tags=["rag"])


def _get_owned_root(workspace_id: str, current_user: User, db: Session):
    try:
        workspace = repo_service.get_owned_workspace(db, workspace_id, current_user)
    except repo_service.WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        root = repo_service.require_existing_root(workspace)
    except repo_service.RepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return root


@router.post("/{workspace_id}/index", response_model=IndexResponse)
def index_repository(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexResponse:
    root = _get_owned_root(workspace_id, current_user, db)

    result = service.index_repository(root, workspace_id)
    return IndexResponse(
        workspace_id=result.workspace_id,
        file_count=result.file_count,
        chunk_count=result.chunk_count,
        skipped_file_count=result.skipped_file_count,
        duration_seconds=round(result.duration_seconds, 2),
    )


@router.get("/{workspace_id}/index/status", response_model=IndexStatusResponse)
def index_status(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexStatusResponse:
    # Ownership check only — no need for the root to still exist on disk to
    # report whether an index was previously built for it.
    try:
        repo_service.get_owned_workspace(db, workspace_id, current_user)
    except repo_service.WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    count = service.index_status(workspace_id)
    return IndexStatusResponse(
        workspace_id=workspace_id, indexed=count is not None, chunk_count=count
    )


@router.get("/{workspace_id}/search/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    workspace_id: str,
    q: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(default=8, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SemanticSearchResponse:
    try:
        repo_service.get_owned_workspace(db, workspace_id, current_user)
    except repo_service.WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    hits = service.semantic_search(workspace_id, q, top_k)
    return SemanticSearchResponse(
        query=q,
        hits=[
            SemanticSearchHit(
                path=h.path,
                symbol=h.symbol,
                chunk_type=h.chunk_type,
                start_line=h.start_line,
                end_line=h.end_line,
                text=h.text,
                score=h.score,
            )
            for h in hits
        ],
    )