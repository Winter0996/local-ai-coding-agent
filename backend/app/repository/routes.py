from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from sqlmodel import select as sql_select

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db import get_db
from app.repository import service
from app.repository.models import Workspace
from app.repository.schemas import (
    FileContentResponse,
    FileTreeResponse,
    LanguageBreakdown,
    RepositoryMetadataResponse,
    SearchMatchResponse,
    SearchResponse,
    SelectRepositoryRequest,
    TreeNodeResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/repo", tags=["repository"])


def _to_tree_response(node: service.TreeNode) -> TreeNodeResponse:
    return TreeNodeResponse(
        name=node.name,
        path=node.path,
        type=node.type,
        language=node.language,
        children=[_to_tree_response(child) for child in node.children],
    )


def _get_owned_workspace(db: Session, workspace_id: str, user: User) -> Workspace:
    """Looking up by id AND user_id (not id alone) is what stops one user
    from reading another user's workspace by guessing/enumerating IDs — this
    is the multi-tenant boundary, the repository-path boundary in
    service.py is a separate, filesystem-level one."""
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )
    return workspace


def _existing_root(workspace: Workspace) -> Path:
    root = Path(workspace.root_path)
    if not root.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository path no longer exists on disk.",
        )
    return root


@router.post("/select", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def select_repository(
    payload: SelectRepositoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    try:
        root = service.resolve_repo_root(payload.path)
    except service.InvalidPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    workspace = Workspace(user_id=current_user.id, root_path=str(root), name=root.name)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    return WorkspaceResponse(
        id=workspace.id,
        root=workspace.root_path,
        name=workspace.name,
        created_at=workspace.created_at.isoformat(),
    )


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceResponse]:
    workspaces = db.exec(
        sql_select(Workspace)
        .where(Workspace.user_id == current_user.id)
        .order_by(Workspace.created_at.desc())
    ).all()
    return [
        WorkspaceResponse(
            id=w.id, root=w.root_path, name=w.name, created_at=w.created_at.isoformat()
        )
        for w in workspaces
    ]


@router.get("/{workspace_id}/metadata", response_model=RepositoryMetadataResponse)
def repository_metadata(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryMetadataResponse:
    workspace = _get_owned_workspace(db, workspace_id, current_user)
    root = _existing_root(workspace)

    metadata = service.get_metadata(root)
    return RepositoryMetadataResponse(
        workspace_id=workspace.id,
        root=metadata.root,
        name=metadata.name,
        file_count=metadata.file_count,
        total_size_bytes=metadata.total_size_bytes,
        languages=[
            LanguageBreakdown(language=lang, file_count=count)
            for lang, count in sorted(metadata.languages.items(), key=lambda kv: -kv[1])
        ],
        has_git=metadata.has_git,
    )


@router.get("/{workspace_id}/tree", response_model=FileTreeResponse)
def repository_tree(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileTreeResponse:
    workspace = _get_owned_workspace(db, workspace_id, current_user)
    root = _existing_root(workspace)

    tree, truncated = service.build_tree(root)
    return FileTreeResponse(root=_to_tree_response(tree), truncated=truncated)


@router.get("/{workspace_id}/file", response_model=FileContentResponse)
def repository_file(
    workspace_id: str,
    path: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileContentResponse:
    workspace = _get_owned_workspace(db, workspace_id, current_user)
    root = _existing_root(workspace)

    try:
        file_content = service.read_file(root, path)
    except service.PathTraversalError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except service.RepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.InvalidPathError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc

    return FileContentResponse(
        path=file_content.path,
        language=file_content.language,
        content=file_content.content,
        truncated=file_content.truncated,
        size_bytes=file_content.size_bytes,
    )


@router.get("/{workspace_id}/search", response_model=SearchResponse)
def repository_search(
    workspace_id: str,
    q: str = Query(..., min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    workspace = _get_owned_workspace(db, workspace_id, current_user)
    root = _existing_root(workspace)

    matches, truncated = service.search_repository(root, q)
    return SearchResponse(
        query=q,
        matches=[
            SearchMatchResponse(path=m.path, line_number=m.line_number, line_text=m.line_text)
            for m in matches
        ],
        truncated=truncated,
    )