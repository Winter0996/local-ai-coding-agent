import sys
from pathlib import Path

# SECURITY INVARIANT: the user (and the LLM) can only ever select a KEY from
# this dict — never supply the argv list itself. There is no code path
# anywhere in app/validation/ that builds a command from a string the user
# typed. This is what makes running a subprocess here fundamentally
# different (and safer) than a general "run shell command" tool: the
# blast radius is capped at whatever these fixed argv lists do.
#
# sys.executable (not the string "python") is used so this resolves to
# whichever interpreter is actually running the backend, regardless of
# venv activation state or PATH contents.
ALLOWED_COMMANDS: dict[str, list[str]] = {
    "pytest": [sys.executable, "-m", "pytest", "-q"],
    "ruff": [sys.executable, "-m", "ruff", "check", "."],
    "npm-test": ["npm", "test", "--", "--run"],
    "npm-lint": ["npm", "run", "lint"],
}

# Which marker file in the repo root implies a command is applicable.
_COMMAND_APPLICABILITY: dict[str, str] = {
    "pytest": "pyproject.toml",
    "ruff": "pyproject.toml",
    "npm-test": "package.json",
    "npm-lint": "package.json",
}

TIMEOUT_SECONDS = 120
MAX_OUTPUT_BYTES = 200_000

# Environment variables never passed through to a spawned command, even
# though the parent process has them — a test/build script has no
# legitimate need for your session secret or DB path, and stripping these
# costs nothing.
_STRIPPED_ENV_KEYS = {
    "JWT_SECRET",
    "CODEFORGE_DB_PATH",
    "CHROMA_PERSIST_DIR",
    "CODEFORGE_FAKE_EMBEDDINGS",
    "COOKIE_SECURE",
}


def detect_available_commands(root: Path) -> list[str]:
    """Only offer commands that plausibly apply to this repo, based on a
    marker file's presence — not a guarantee the command will succeed, just
    a UX filter so a pure-JS repo doesn't see a 'pytest' button."""
    available = []
    for key, marker in _COMMAND_APPLICABILITY.items():
        if (root / marker).exists():
            available.append(key)
    return available