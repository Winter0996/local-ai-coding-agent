from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.agent import service
from app.agent.schemas import ApplyRequest, ApplyResponse, ProposeRequest, ProposeResponse
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db import get_db
from app.repository import service as repo_service

router = APIRouter(prefix="/agent", tags=["agent"])


def _get_owned_root(workspace_id: str, current_user: User, db: Session):
    try:
        workspace = repo_service.get_owned_workspace(db, workspace_id, current_user)
    except repo_service.WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        return repo_service.require_existing_root(workspace)
    except repo_service.RepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{workspace_id}/propose", response_model=ProposeResponse)
async def propose(
    workspace_id: str,
    request: ProposeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposeResponse:
    root = _get_owned_root(workspace_id, current_user, db)

    try:
        proposal = await service.propose_change(root, workspace_id, request.message)
    except service.NoTargetFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except repo_service.InvalidPathError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Local Ollama request failed: {exc}"
        ) from exc

    return ProposeResponse(
        workspace_id=proposal.workspace_id,
        target_path=proposal.target_path,
        diff=proposal.diff,
        proposed_content=proposal.proposed_content,
        explanation=proposal.explanation,
    )


@router.post("/{workspace_id}/apply", response_model=ApplyResponse)
def apply(
    workspace_id: str,
    request: ApplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyResponse:
    """This is the human-approval gate: the frontend only calls this after
    the user has reviewed the diff from /propose and explicitly clicked
    Approve. The backend does not trust that framing on its own, though —
    resolve_safe_path() inside apply_change() re-validates the path boundary
    regardless of what the client claims was reviewed."""
    root = _get_owned_root(workspace_id, current_user, db)

    try:
        result = service.apply_change(root, request.path, request.content)
    except repo_service.PathTraversalError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except repo_service.RepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApplyResponse(path=result.path, bytes_written=result.bytes_written)