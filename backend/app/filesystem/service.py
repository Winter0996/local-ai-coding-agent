import os
import string
from dataclasses import dataclass
from pathlib import Path


class FilesystemError(Exception):
    pass


class PathNotFoundError(FilesystemError):
    pass


@dataclass
class DirEntry:
    name: str
    path: str


@dataclass
class BrowseResult:
    path: str | None  # None = virtual root (drive list on Windows, "/" on POSIX)
    parent: str | None
    entries: list[DirEntry]


def _list_windows_drives() -> list[DirEntry]:
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(DirEntry(name=drive, path=drive))
    return drives


def list_roots() -> list[DirEntry]:
    """The virtual root shown when no path is given: drive letters on
    Windows, or just '/' on POSIX (most users start browsing from their
    home directory anyway — see browse()'s default)."""
    if os.name == "nt":
        return _list_windows_drives()
    return [DirEntry(name="/", path="/")]


def _list_subdirectories(root: Path) -> list[DirEntry]:
    entries: list[DirEntry] = []
    try:
        with os.scandir(root) as it:
            for item in it:
                try:
                    if item.is_dir(follow_symlinks=False):
                        entries.append(DirEntry(name=item.name, path=str(Path(item.path))))
                except OSError:
                    continue  # permission error on this specific entry — skip it
    except PermissionError as exc:
        raise FilesystemError(f"Permission denied: {root}") from exc
    entries.sort(key=lambda e: e.name.lower())
    return entries


def browse(raw_path: str | None) -> BrowseResult:
    """Lists the immediate subdirectories of raw_path (or the user's home
    directory if raw_path is None/empty). Read-only, one level at a time,
    directories only — this exists purely so the user can navigate to a
    project folder without hand-typing a path, not as a general file
    manager. It deliberately does NOT expose file contents, only names."""
    if not raw_path or not raw_path.strip():
        home = Path.home()
        return BrowseResult(
            path=str(home),
            parent=str(home.parent) if home.parent != home else None,
            entries=_list_subdirectories(home),
        )

    path = Path(raw_path)
    if not path.exists() or not path.is_dir():
        raise PathNotFoundError(f"'{raw_path}' does not exist or is not a directory.")

    path = path.resolve()
    parent = str(path.parent) if path.parent != path else None

    return BrowseResult(
        path=str(path),
        parent=parent,
        entries=_list_subdirectories(path),
    )