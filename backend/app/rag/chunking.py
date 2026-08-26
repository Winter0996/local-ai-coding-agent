import ast
import re
from dataclasses import dataclass

# Keeps individual embedding inputs small and roughly comparable in size —
# very large functions get subdivided further, very tiny ones are skipped
# since they add noise to retrieval without much retrievable signal.
MAX_CHUNK_CHARS = 4000
MIN_CHUNK_CHARS = 20

# Fallback line-window chunker: used for any file type without a smarter
# strategy (or when a smarter strategy fails, e.g. a Python file with a
# syntax error). `overlap` keeps a boundary's context from being split
# across two chunks with zero shared text.
FALLBACK_CHUNK_LINES = 40
FALLBACK_OVERLAP_LINES = 5


@dataclass
class CodeChunk:
    path: str
    symbol: str | None  # function/class name, or None for generic chunks
    chunk_type: str  # "function" | "method" | "class" | "block"
    start_line: int
    end_line: int
    text: str


def _split_oversized(chunk: CodeChunk) -> list[CodeChunk]:
    """If an AST- or regex-derived chunk is bigger than MAX_CHUNK_CHARS,
    subdivide it by lines rather than truncating — truncation would silently
    drop code from the index, which is worse than a slightly awkward split."""
    if len(chunk.text) <= MAX_CHUNK_CHARS:
        return [chunk]

    lines = chunk.text.splitlines()
    pieces: list[CodeChunk] = []
    start = 0
    while start < len(lines):
        piece_lines = lines[start : start + FALLBACK_CHUNK_LINES]
        piece_text = "\n".join(piece_lines)
        if len(piece_text.strip()) >= MIN_CHUNK_CHARS:
            pieces.append(
                CodeChunk(
                    path=chunk.path,
                    symbol=chunk.symbol,
                    chunk_type=chunk.chunk_type,
                    start_line=chunk.start_line + start,
                    end_line=chunk.start_line + start + len(piece_lines) - 1,
                    text=piece_text,
                )
            )
        start += FALLBACK_CHUNK_LINES - FALLBACK_OVERLAP_LINES
    return pieces


def _chunk_by_lines(path: str, content: str) -> list[CodeChunk]:
    lines = content.splitlines()
    if not lines:
        return []

    chunks: list[CodeChunk] = []
    start = 0
    while start < len(lines):
        piece_lines = lines[start : start + FALLBACK_CHUNK_LINES]
        text = "\n".join(piece_lines)
        if len(text.strip()) >= MIN_CHUNK_CHARS:
            chunks.append(
                CodeChunk(
                    path=path,
                    symbol=None,
                    chunk_type="block",
                    start_line=start + 1,
                    end_line=start + len(piece_lines),
                    text=text,
                )
            )
        if start + FALLBACK_CHUNK_LINES >= len(lines):
            break
        start += FALLBACK_CHUNK_LINES - FALLBACK_OVERLAP_LINES
    return chunks


def _chunk_python(path: str, content: str) -> list[CodeChunk] | None:
    """Returns None (signal to fall back) if the file doesn't parse — a
    syntax error, or a Python 2-only file, shouldn't crash indexing."""
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return None

    lines = content.splitlines()
    chunks: list[CodeChunk] = []

    def node_text(node: ast.AST) -> str:
        start = node.lineno - 1
        end = getattr(node, "end_lineno", node.lineno)
        return "\n".join(lines[start:end])

    def visit(node: ast.AST, class_name: str | None = None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = f"{class_name}.{child.name}" if class_name else child.name
                text = node_text(child)
                if len(text.strip()) >= MIN_CHUNK_CHARS:
                    chunk = CodeChunk(
                        path=path,
                        symbol=symbol,
                        chunk_type="method" if class_name else "function",
                        start_line=child.lineno,
                        end_line=getattr(child, "end_lineno", child.lineno),
                        text=text,
                    )
                    chunks.extend(_split_oversized(chunk))
                # Deliberately do not recurse into function bodies — nested
                # functions/closures become part of their parent's chunk
                # rather than separate entries, which keeps retrieval units
                # at a meaningful "thing a person would look up" granularity.
            elif isinstance(child, ast.ClassDef):
                text = node_text(child)
                if len(text.strip()) >= MIN_CHUNK_CHARS:
                    chunk = CodeChunk(
                        path=path,
                        symbol=child.name,
                        chunk_type="class",
                        start_line=child.lineno,
                        end_line=getattr(child, "end_lineno", child.lineno),
                        text=text,
                    )
                    chunks.extend(_split_oversized(chunk))
                visit(child, class_name=child.name)

    visit(tree)

    if not chunks:
        # A file with no top-level functions/classes (a script, a constants
        # file) still deserves to be searchable — fall back to line chunks.
        return _chunk_by_lines(path, content)

    return chunks


# Deliberately conservative regex heuristics, not a real parser — good
# enough to find likely function/class boundaries in JS/TS without pulling
# in a full parser dependency. A wrong boundary just means a slightly
# oversized or undersized chunk, not incorrect code, so the failure mode is
# mild. Revisit with tree-sitter if chunk quality becomes a real problem.
_JS_BOUNDARY_PATTERN = re.compile(
    r"^\s*(export\s+)?(default\s+)?"
    r"(async\s+)?function\s+\w+|"
    r"^\s*(export\s+)?class\s+\w+|"
    r"^\s*(export\s+)?const\s+\w+\s*=\s*(async\s+)?\(.*?\)\s*=>|"
    r"^\s*(export\s+)?const\s+\w+\s*=\s*(async\s+)?function"
)


def _chunk_js_like(path: str, content: str) -> list[CodeChunk]:
    lines = content.splitlines()
    boundaries = [i for i, line in enumerate(lines) if _JS_BOUNDARY_PATTERN.match(line)]

    if not boundaries:
        return _chunk_by_lines(path, content)

    chunks: list[CodeChunk] = []
    for idx, start in enumerate(boundaries):
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(lines)
        text = "\n".join(lines[start:end])
        if len(text.strip()) >= MIN_CHUNK_CHARS:
            chunk = CodeChunk(
                path=path,
                symbol=None,
                chunk_type="block",
                start_line=start + 1,
                end_line=end,
                text=text,
            )
            chunks.extend(_split_oversized(chunk))

    # Anything before the first boundary (imports, top-level constants)
    # still gets indexed rather than silently dropped.
    if boundaries[0] > 0:
        preamble = "\n".join(lines[: boundaries[0]])
        if len(preamble.strip()) >= MIN_CHUNK_CHARS:
            chunks.insert(
                0,
                CodeChunk(
                    path=path,
                    symbol=None,
                    chunk_type="block",
                    start_line=1,
                    end_line=boundaries[0],
                    text=preamble,
                ),
            )

    return chunks


_JS_LIKE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs"}


def chunk_file(path: str, content: str, extension: str) -> list[CodeChunk]:
    """Entry point: dispatches to the best available chunking strategy for
    the file's extension, always falling back to a safe fixed-size window
    rather than raising."""
    if not content.strip():
        return []

    ext = extension.lower()

    if ext == ".py":
        result = _chunk_python(path, content)
        if result is not None:
            return result
        # Syntax error — fall through to the generic chunker below.

    if ext in _JS_LIKE_EXTENSIONS:
        return _chunk_js_like(path, content)

    return _chunk_by_lines(path, content)