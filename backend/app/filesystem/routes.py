from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.filesystem import service
from app.filesystem.schemas import BrowseResponse, DirEntryResponse

router = APIRouter(prefix="/filesystem", tags=["filesystem"])


@router.get("/browse", response_model=BrowseResponse)
def browse(
    path: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> BrowseResponse:
    """Lists subdirectories of `path` (or the user's home directory if
    omitted) so the frontend can offer a click-to-navigate folder picker
    instead of requiring a hand-typed absolute path. Deliberately NOT
    scoped to a workspace root — that boundary doesn't exist yet at this
    point, since the whole purpose is helping the user FIND a workspace
    root. Read-only, directory names only, never file contents."""
    try:
        result = service.browse(path)
    except service.PathNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.FilesystemError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return BrowseResponse(
        path=result.path,
        parent=result.parent,
        entries=[DirEntryResponse(name=e.name, path=e.path) for e in result.entries],
        roots=[DirEntryResponse(name=e.name, path=e.path) for e in service.list_roots()],
    )