from pathlib import Path

EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".pytest_cache", ".ruff_cache", ".next", ".turbo",
    ".mypy_cache", "target", ".idea", ".vscode",
}

# Deliberately conservative and non-exhaustive — this blocks the most
# obviously-wrong choices (opening your whole home directory or a system
# directory as a "repository"), not a full sandbox. Combined with
# resolve_safe_path()'s boundary check in service.py, it's defense-in-depth,
# not the only line of defense.
_BLOCKED_ROOTS = {
    Path("/"), Path("/etc"), Path("/bin"), Path("/usr"), Path("/System"),
    Path("C:/"), Path("C:/Windows"), Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
}


def is_blocked_root(root: Path) -> bool:
    return root in _BLOCKED_ROOTS or root == Path.home()


MAX_FILE_BYTES = 512 * 1024  # 512 KB — plenty for source files, not for logs/dumps
MAX_TREE_NODES = 5000
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_MATCHES_PER_FILE = 20

LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust",
    ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".cs": "C#", ".swift": "Swift",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sql": "SQL",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".md": "Markdown",
    ".sh": "Shell", ".ps1": "PowerShell", ".toml": "TOML",
    ".xml": "XML", ".vue": "Vue",
}


def detect_language(path: Path) -> str | None:
    """Maps file extensions to language names for the tree view and metadata."""
    if path.name == "Dockerfile":
        return "Dockerfile"
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


def is_binary_file(path: Path, sniff_bytes: int = 8000) -> bool:
    """Heuristic, not perfect: reads a chunk and checks for a null byte,
    which is present in virtually all binary formats but essentially never
    in real text. Good enough to keep binaries out of the file viewer and
    out of search — this isn't a security boundary, just a UX one."""
    try:
        with path.open("rb") as f:
            chunk = f.read(sniff_bytes)
    except OSError:
        return True
    return b"\x00" in chunk