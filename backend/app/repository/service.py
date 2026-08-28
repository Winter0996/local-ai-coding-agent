from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session

from app.auth.models import User
from app.repository.models import Workspace
from app.repository.security import (
    EXCLUDED_DIRS,
    MAX_FILE_BYTES,
    MAX_SEARCH_MATCHES_PER_FILE,
    MAX_SEARCH_RESULTS,
    MAX_TREE_NODES,
    detect_language,
    is_binary_file,
    is_blocked_root,
)


class RepositoryError(Exception):
    """Base class for repository-service errors; routes.py maps these to
    the appropriate HTTP status codes."""


class RepositoryNotFoundError(RepositoryError):
    pass


class InvalidPathError(RepositoryError):
    pass


class PathTraversalError(RepositoryError):
    pass


class WorkspaceNotFoundError(RepositoryError):
    pass


def get_owned_workspace(db: Session, workspace_id: str, user: User) -> Workspace:
    """Looking up by id AND user_id (not id alone) is what stops one user
    from reading another user's workspace by guessing/enumerating IDs.
    Shared by both app/repository/routes.py and app/rag/routes.py so the
    multi-tenant boundary is enforced identically in both places."""
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.user_id != user.id:
        raise WorkspaceNotFoundError("Workspace not found.")
    return workspace


def require_existing_root(workspace: Workspace) -> Path:
    root = Path(workspace.root_path)
    if not root.exists():
        raise RepositoryNotFoundError("Repository path no longer exists on disk.")
    return root


def resolve_repo_root(raw_path: str) -> Path:
    root = Path(raw_path).expanduser()
    if not root.is_absolute():
        raise InvalidPathError("Repository path must be an absolute path.")

    root = root.resolve()

    if not root.exists() or not root.is_dir():
        raise InvalidPathError(f"'{root}' does not exist or is not a directory.")

    if is_blocked_root(root):
        raise InvalidPathError(
            f"Refusing to open '{root}' — it looks like a system or home "
            "directory rather than a project folder."
        )

    return root


def resolve_safe_path(root: Path, relative: str) -> Path:
    """Resolve `relative` against `root` and guarantee the result stays
    inside root, even across symlinks (Path.resolve() follows symlinks to
    their real target, and relative_to() then checks the REAL target is
    still under root — a symlink inside the repo pointing outside it will
    still be caught).

    This is the single choke point every file-reading/searching function in
    this module goes through — the path-traversal boundary described in
    docs/security.md.
    """
    candidate = (root / relative.lstrip("/\\")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError(
            f"'{relative}' resolves outside the selected repository."
        ) from exc
    return candidate


def _iter_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


@dataclass
class TreeNode:
    name: str
    path: str
    type: str  # "file" | "directory"
    language: str | None = None
    children: list["TreeNode"] = field(default_factory=list)


def build_tree(root: Path) -> tuple[TreeNode, bool]:
    """Returns (tree, truncated). `truncated` is True if MAX_TREE_NODES was
    hit while walking — callers should tell the user the tree is partial
    rather than silently showing an incomplete view."""
    node_count = 0
    truncated = False

    def build(dir_path: Path) -> TreeNode:
        nonlocal node_count, truncated
        node = TreeNode(
            name=dir_path.name or str(dir_path),
            path="" if dir_path == root else dir_path.relative_to(root).as_posix(),
            type="directory",
        )

        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return node

        for entry in entries:
            if entry.name in EXCLUDED_DIRS:
                continue
            if node_count >= MAX_TREE_NODES:
                truncated = True
                break
            node_count += 1

            if entry.is_dir():
                node.children.append(build(entry))
            else:
                node.children.append(
                    TreeNode(
                        name=entry.name,
                        path=entry.relative_to(root).as_posix(),
                        type="file",
                        language=detect_language(entry),
                    )
                )
        return node

    return build(root), truncated


@dataclass
class FileContent:
    path: str
    language: str | None
    content: str
    truncated: bool
    size_bytes: int


def read_file(root: Path, relative_path: str) -> FileContent:
    target = resolve_safe_path(root, relative_path)

    if not target.exists() or not target.is_file():
        raise RepositoryNotFoundError(f"'{relative_path}' does not exist.")

    if is_binary_file(target):
        raise InvalidPathError(
            f"'{relative_path}' looks like a binary file and can't be displayed."
        )

    size = target.stat().st_size
    truncated = size > MAX_FILE_BYTES

    with target.open("r", encoding="utf-8", errors="replace") as f:
        content = f.read(MAX_FILE_BYTES)

    return FileContent(
        path=target.relative_to(root).as_posix(),
        language=detect_language(target),
        content=content,
        truncated=truncated,
        size_bytes=size,
    )


@dataclass
class SearchMatch:
    path: str
    line_number: int
    line_text: str


def search_repository(root: Path, query: str) -> tuple[list[SearchMatch], bool]:
    """Plain case-insensitive substring search — deliberately NOT regex.
    User-supplied regex evaluated against arbitrary file content is a
    classic ReDoS vector (a crafted pattern can pin a CPU core); substring
    search gets most of the practical value for v1 without that risk.
    Worth revisiting with a vetted, non-backtracking regex engine if regex
    search becomes a real requirement later."""
    if not query.strip():
        return [], False

    needle = query.lower()
    matches: list[SearchMatch] = []
    truncated = False

    for file_path in _iter_files(root):
        if len(matches) >= MAX_SEARCH_RESULTS:
            truncated = True
            break
        if is_binary_file(file_path):
            continue

        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                file_matches = 0
                for line_number, line in enumerate(f, start=1):
                    if needle in line.lower():
                        matches.append(
                            SearchMatch(
                                path=file_path.relative_to(root).as_posix(),
                                line_number=line_number,
                                line_text=line.strip()[:300],
                            )
                        )
                        file_matches += 1
                        if file_matches >= MAX_SEARCH_MATCHES_PER_FILE:
                            break
                        if len(matches) >= MAX_SEARCH_RESULTS:
                            truncated = True
                            break
        except OSError:
            continue

    return matches, truncated


@dataclass
class RepositoryMetadata:
    root: str
    name: str
    file_count: int
    total_size_bytes: int
    languages: dict[str, int]
    has_git: bool

def list_file_paths(root: Path) -> list[str]:
    """All indexable-repository-relative file paths, POSIX-style. Used by
    the agent to detect when a user's message explicitly names a file."""
    return sorted(f.relative_to(root).as_posix() for f in _iter_files(root))


def get_metadata(root: Path) -> RepositoryMetadata:
    file_count = 0
    total_size = 0
    languages: dict[str, int] = {}

    for file_path in _iter_files(root):
        file_count += 1
        try:
            total_size += file_path.stat().st_size
        except OSError:
            continue
        language = detect_language(file_path)
        if language:
            languages[language] = languages.get(language, 0) + 1

    return RepositoryMetadata(
        root=str(root),
        name=root.name,
        file_count=file_count,
        total_size_bytes=total_size,
        languages=languages,
        has_git=(root / ".git").exists(),
    )