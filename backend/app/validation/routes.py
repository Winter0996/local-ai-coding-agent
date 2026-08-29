from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db import get_db
from app.repository import service as repo_service
from app.validation import security, service
from app.validation.schemas import (
    AvailableCommandsResponse,
    RunCommandRequest,
    RunCommandResponse,
)

router = APIRouter(prefix="/agent", tags=["validation"])


def _get_owned_root(workspace_id: str, current_user: User, db: Session):
    try:
        workspace = repo_service.get_owned_workspace(db, workspace_id, current_user)
    except repo_service.WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        return repo_service.require_existing_root(workspace)
    except repo_service.RepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{workspace_id}/validation/commands", response_model=AvailableCommandsResponse)
def available_commands(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AvailableCommandsResponse:
    root = _get_owned_root(workspace_id, current_user, db)
    return AvailableCommandsResponse(commands=security.detect_available_commands(root))


@router.post("/{workspace_id}/validation/run", response_model=RunCommandResponse)
def run_command(
    workspace_id: str,
    request: RunCommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunCommandResponse:
    root = _get_owned_root(workspace_id, current_user, db)

    try:
        result = service.run_command(root, request.command_key)
    except service.UnknownCommandError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RunCommandResponse(
        command_key=result.command_key,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        truncated=result.truncated,
        timed_out=result.timed_out,
        duration_seconds=round(result.duration_seconds, 2),
        passed=(result.exit_code == 0 and not result.timed_out),
    )