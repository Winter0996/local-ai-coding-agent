import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.validation.security import (
    _STRIPPED_ENV_KEYS,
    ALLOWED_COMMANDS,
    MAX_OUTPUT_BYTES,
    TIMEOUT_SECONDS,
)


class ValidationError(Exception):
    """Base class for validation-service errors; routes.py maps these to HTTP codes."""


class UnknownCommandError(ValidationError):
    pass


@dataclass
class CommandResult:
    command_key: str
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    duration_seconds: float


def _truncate(text: str) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return text, False
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore"), True


def _safe_env() -> dict[str, str]:
    """Full parent environment MINUS this app's own secrets. Deliberately
    not a minimal allowlist-only environment — npm/pytest/node on Windows
    in particular depend on a wide, hard-to-predict set of system env vars
    (APPDATA, SystemRoot, etc.) to function at all. Subtracting known
    secrets is the safer, more reliable approach than trying to guess a
    minimal working set."""
    env = dict(os.environ)
    for key in _STRIPPED_ENV_KEYS:
        env.pop(key, None)
    return env


def run_command(root: Path, command_key: str) -> CommandResult:
    """Runs a fixed, allowlisted command (see security.py — the key is the
    ONLY thing ever selected by a caller; the argv list is never built from
    user input). This is a human-initiated action (a button click after
    reviewing/applying a patch), never something the LLM can trigger on its
    own — there is no code path from agent/service.py into this function."""
    argv = ALLOWED_COMMANDS.get(command_key)
    if argv is None:
        raise UnknownCommandError(f"'{command_key}' is not an allowed command.")

    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 — argv is from a fixed allowlist, never user input
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=_safe_env(),
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, _ = _truncate(exc.stdout or "" if isinstance(exc.stdout, str) else "")
        stderr, _ = _truncate(exc.stderr or "" if isinstance(exc.stderr, str) else "")
        return CommandResult(
            command_key=command_key,
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            truncated=False,
            timed_out=True,
            duration_seconds=time.monotonic() - started,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            command_key=command_key,
            exit_code=None,
            stdout="",
            stderr=f"Could not run '{argv[0]}': {exc}. Is it installed and on PATH?",
            truncated=False,
            timed_out=False,
            duration_seconds=time.monotonic() - started,
        )

    stdout, stdout_truncated = _truncate(completed.stdout)
    stderr, stderr_truncated = _truncate(completed.stderr)

    return CommandResult(
        command_key=command_key,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        truncated=stdout_truncated or stderr_truncated,
        timed_out=False,
        duration_seconds=time.monotonic() - started,
    )