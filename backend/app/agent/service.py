import difflib
from dataclasses import dataclass
from pathlib import Path

from app.llm.ollama import OllamaProvider
from app.rag import service as rag_service
from app.repository import service as repo_service

MAX_CONTEXT_CHUNKS = 3


class AgentError(Exception):
    """Base class for agent-service errors; routes.py maps these to HTTP codes."""


class NoTargetFileError(AgentError):
    pass


def _find_explicit_path(message: str, candidate_paths: list[str]) -> str | None:
    """If the user's message literally names one of the repo's files (e.g.
    'fix the bug in app/auth/routes.py'), prefer that over retrieval —
    an explicit reference is a stronger signal than semantic similarity.
    Longest match wins so 'app/auth/routes.py' beats a shorter path that
    happens to also appear as a substring."""
    matches = [p for p in candidate_paths if p in message]
    if not matches:
        return None
    return max(matches, key=len)


def _strip_code_fences(text: str) -> str:
    """Models frequently wrap output in ``` fences even when told not to.
    Defensive cleanup rather than relying on the prompt alone."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return stripped


def _build_rewrite_prompt(
    message: str, target_path: str, original_content: str, extra_chunks: list[rag_service.SearchHit]
) -> str:
    context = ""
    if extra_chunks:
        blocks = [f"# {c.path} (lines {c.start_line}-{c.end_line})\n{c.text}" for c in extra_chunks]
        context = (
            "For additional context, here is related code elsewhere in the "
            "repository (reference only — do not modify these):\n\n"
            + "\n\n".join(blocks)
            + "\n\n"
        )

    return (
        "You are an AI software engineering agent. Rewrite ONE file to satisfy "
        "the user's request. Output ONLY the complete new file content — no "
        "explanations, no markdown code fences, no commentary. Preserve all "
        "code not related to the request.\n\n"
        f"{context}"
        f"--- CURRENT CONTENT OF {target_path} ---\n{original_content}\n"
        f"--- END CURRENT CONTENT ---\n\n"
        f"User request: {message}\n\n"
        f"Output the complete new content of {target_path}:"
    )


@dataclass
class AgentProposal:
    workspace_id: str
    target_path: str
    original_content: str
    proposed_content: str
    diff: str
    explanation: str


async def propose_change(root: Path, workspace_id: str, message: str) -> AgentProposal:
    """Single-step agent loop: pick a target file (explicit mention or top
    retrieval hit), ask the model to rewrite it, diff the result against
    the original. Returns a proposal — nothing is written to disk here;
    apply_change() is a separate, explicitly human-approved step."""
    all_paths = repo_service.list_file_paths(root)
    explicit_path = _find_explicit_path(message, all_paths)

    hits = rag_service.semantic_search(workspace_id, message, top_k=MAX_CONTEXT_CHUNKS + 1)

    target_path = explicit_path or (hits[0].path if hits else None)
    if target_path is None:
        raise NoTargetFileError(
            "Could not determine which file to modify. Try naming the file "
            "explicitly, or index the repository first."
        )

    file_content = repo_service.read_file(root, target_path)
    original_content = file_content.content

    extra_chunks = [h for h in hits if h.path != target_path][:MAX_CONTEXT_CHUNKS]

    prompt = _build_rewrite_prompt(message, target_path, original_content, extra_chunks)
    provider = OllamaProvider()
    raw_response = await provider.generate(prompt)
    proposed_content = _strip_code_fences(raw_response)

    diff = "".join(
        difflib.unified_diff(
            original_content.splitlines(keepends=True),
            proposed_content.splitlines(keepends=True),
            fromfile=f"a/{target_path}",
            tofile=f"b/{target_path}",
        )
    )

    explanation = (
        f"Proposed a rewrite of {target_path} "
        f"({'explicitly named' if explicit_path else 'selected via semantic search'}) "
        f"based on: \"{message}\""
    )

    return AgentProposal(
        workspace_id=workspace_id,
        target_path=target_path,
        original_content=original_content,
        proposed_content=proposed_content,
        diff=diff,
        explanation=explanation,
    )


@dataclass
class ApplyResult:
    path: str
    bytes_written: int


def apply_change(root: Path, path: str, content: str) -> ApplyResult:
    """Writes approved content to an EXISTING file only — this is the
    human-approval gate described in docs/security.md. The caller (routes.py)
    is responsible for only reaching this after explicit user confirmation;
    this function itself re-validates the path boundary regardless, since a
    server-side check must never depend solely on the frontend having asked
    nicely."""
    target = repo_service.resolve_safe_path(root, path)

    if not target.exists() or not target.is_file():
        raise repo_service.RepositoryNotFoundError(
            f"'{path}' does not exist — the agent can only edit existing files in v1."
        )

    encoded = content.encode("utf-8")
    target.write_bytes(encoded)

    return ApplyResult(path=path, bytes_written=len(encoded))