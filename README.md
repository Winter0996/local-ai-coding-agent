# CodeForge AI

**A local-first AI software engineering agent.** It runs entirely on your
machine — no OpenAI, no Anthropic, no hosted vector database, no API keys,
no credit card. It can browse a codebase, retrieve relevant context via
RAG, propose code changes with a reviewable diff, and run your tests —
every write gated behind explicit human approval.

![Backend](https://github.com/Winter0996/local-ai-coding-agent/actions/workflows/backend.yml/badge.svg)
![Frontend](https://github.com/Winter0996/local-ai-coding-agent/actions/workflows/frontend.yml/badge.svg)

---



## What it does

1. **Sign in.** Argon2id password hashing, JWT access tokens kept in memory
  (never localStorage), refresh tokens as httpOnly cookies with rotation
   and reuse detection.
2. **Open a local repository.** Browse its file tree, read files, run
  plain-text search — all scoped to that repo's root, with path-traversal
   protection on every read.
3. **Index it.** Code is chunked (AST-based for Python — real
  function/class boundaries, not arbitrary line windows; regex-heuristic
   for JS/TS; fixed-size fallback for everything else), embedded with
   `sentence-transformers`, and stored per-workspace in ChromaDB.
4. **Ask questions grounded in your actual code.** Chat retrieves relevant
  chunks and injects them into the prompt as clearly-delimited context —
   answers cite the real files and line ranges they came from.
5. **Propose a change.** Name a file explicitly or let semantic search pick
  the most relevant one; the agent asks the local model to rewrite it,
   then computes the diff itself via `difflib` — it never trusts the model
   to hand-write a correct diff.
6. **Review, then approve.** Nothing touches disk until you explicitly
  click Approve. The backend re-validates the file path server-side
   regardless of what the frontend claims was reviewed.
7. **Validate.** Run tests or lint against the repo from a fixed, hardcoded
  command allowlist — never a user-supplied string, never LLM-triggered.
   On failure, one click sends the real failure output back into a new
   proposal.



## Why this project, not another OpenAI wrapper

Most portfolio AI projects call a hosted API and stop. This one is built
around the harder, more interesting problem: **what does it take to let a
model act on a real codebase without it being able to do something
destructive?** Concretely:

- **A genuine security model**, not a disclaimer: workspace path boundaries
enforced on every file operation, multi-tenant isolation (one account
can't read another's workspace by guessing an ID), a fixed command
allowlist for test execution (no shell strings, ever), secrets stripped
from any spawned subprocess, and a human-approval gate on every write
that's enforced server-side, not just in the UI.
- **An honestly-documented failure mode.** During testing, the agent's
full-file-rewrite approach was twice observed producing genuinely broken
output — once deleting unrelated functions the file depended on, once
echoing a fragment of its own prompt instructions into the file as
literal code. Both were caught by the approval gate before anything was
written. That's not a bug swept under the rug — it's documented in
`[docs/security.md](docs/security.md)` as a known limitation, because
understanding a system's failure modes is part of understanding the
system.
- **Zero recurring cost.** Everything — inference, embeddings, the vector
store, the database — runs locally. No API bill, no rate limits, no
vendor lock-in.



## Screenshots

*(add a few here — Repository tab with a tree open, Agent Edit tab showing
a diff, Validate section showing a passing test run)*

## Stack


| Layer        | Choice                                                     |
| ------------ | ---------------------------------------------------------- |
| Frontend     | React + TypeScript + Vite                                  |
| Backend      | FastAPI                                                    |
| Auth         | Argon2id, JWT (access + rotating refresh), SQLModel/SQLite |
| LLM          | Ollama (Qwen3 8B, local)                                   |
| Embeddings   | sentence-transformers (all-MiniLM-L6-v2)                   |
| Vector store | ChromaDB (persistent, per-workspace collections)           |
| Testing      | Pytest (backend), Vitest-ready (frontend)                  |
| CI           | GitHub Actions — backend and frontend run on every push    |




## Prerequisites

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com), with a model pulled:

```powershell
  ollama pull qwen3:8b
```



## Setup



### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your `.env`:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Paste the generated secret into `.env` next to `JWT_SECRET=`.

Run it:

```powershell
uvicorn app.main:app --reload
```

Backend: [http://localhost:8000](http://localhost:8000) — interactive API docs at `/docs`.

> First-time note: `sentence-transformers` downloads the embedding model
> (~80MB) from Hugging Face the first time you index a repository. That
> needs real internet access once; after that it's cached locally and
> works fully offline.



### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend: [http://localhost:5173](http://localhost:5173)

### Tests

```powershell
cd backend
python -m pytest -v      # 73 tests
ruff check .
```



## API surface


| Area       | Endpoints                                                                              |
| ---------- | -------------------------------------------------------------------------------------- |
| Auth       | `POST /api/auth/register`, `/login`, `/refresh`, `/logout`, `GET /me`                  |
| Repository | `POST /api/repo/select`, `GET /{id}/tree`, `/file`, `/search`, `/metadata`             |
| RAG        | `POST /api/repo/{id}/index`, `GET /{id}/index/status`, `GET /{id}/search/semantic`     |
| Chat       | `POST /api/chat` (optional `workspace_id` for RAG-grounded answers with cited sources) |
| Agent      | `POST /api/agent/{id}/propose`, `POST /api/agent/{id}/apply`                           |
| Validation | `GET /api/agent/{id}/validation/commands`, `POST /{id}/validation/run`                 |




## Project docs

- `[docs/architecture.md](docs/architecture.md)` — system design
- `[docs/security.md](docs/security.md)` — the security model, including
the documented agent-reliability limitation above
- `[docs/roadmap.md](docs/roadmap.md)` — what's built vs. what's
deliberately deferred (agent tool registry, SSE streaming, an audit log,
a formal retrieval/agent evaluation harness)



## What's intentionally out of scope (for now)

- **Multi-file patches** — the agent edits one file per proposal.
- **Autonomous retry loops** — validation failures require a human click
to trigger a repair attempt; there's no unattended iteration.
- **Sandboxed/containerized command execution** — validation commands run
directly on the host, constrained by a fixed allowlist and a
secret-stripped environment rather than an OS-level sandbox.
- **Formal retrieval/agent evaluation** — retrieval and patch quality have
been validated by hand, not against a benchmark with measured
precision/recall.

These are documented, deliberate scope cuts for a working v1 — not
oversights.

---

Local-first. Open-source stack. $0 recurring cost.