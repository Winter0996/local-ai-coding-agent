# Architecture Design

CodeForge AI is an open-source, local-first AI software engineering agent designed to assist developers directly on their local machines without sending code or prompts to paid third-party AI APIs.

---

## 1. System Overview

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React + TypeScript + Vite)               │
│                                                                                │
│   ┌─────────────────────┐   ┌──────────────────────┐   ┌───────────────────┐  │
│   │ Repository Explorer │   │   Agent Playground   │   │  Agent Edit &     │  │
│   │ & File Viewer       │   │   (RAG Chat)         │   │  Validation Diff  │  │
│   └──────────┬──────────┘   └──────────┬───────────┘   └─────────┬─────────┘  │
└──────────────┼─────────────────────────┼─────────────────────────┼─────────────┘
               │                         │                         │ HTTP / JSON
               ▼                         ▼                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                              Backend (FastAPI + SQLModel)                       │
│                                                                                │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                            API Routing Layer                              │ │
│  │   /api/auth  │  /api/repo  │  /api/chat  │  /api/agent  │  /api/validation    │ │
│  └─────────────────────────────────────┬─────────────────────────────────────┘ │
│                                        │                                       │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                         Core Application Services                         │ │
│  │                                                                           │ │
│  │   ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐   │ │
│  │   │ Auth & Security  │  │ Repository       │  │ RAG & Vector Store    │   │ │
│  │   │ - JWT / Passlib  │  │ - Tree / Read    │  │ - AST & Regex Chunker │   │ │
│  │   │ - Rate Limiting  │  │ - Text Search    │  │ - ChromaDB Client     │   │ │
│  │   │ - Tenancy Guard  │  │ - Path Guard     │  │ - Embeddings Service  │   │ │
│  │   └──────────────────┘  └──────────────────┘  └───────────────────────┘   │ │
│  │   ┌────────────────────────────────────────┐  ┌───────────────────────┐   │ │
│  │   │ Agent Service                          │  │ Validation Runner     │   │ │
│  │   │ - Target File Resolution (RAG fallback)│  │ - Strict Allowlist    │   │ │
│  │   │ - Unified Diff Engine (difflib)        │  │ - Subprocess Isolation│   │ │
│  │   │ - Human-Gated Patch Application        │  │ - Secret Scrubbing    │   │ │
│  │   └────────────────────────────────────────┘  └───────────────────────┘   │ │
│  └─────────────────────────────────────┬─────────────────────────────────────┘ │
└────────────────────────────────────────┼───────────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│        Local LLM & Embeddings        │  │          Local Data Storage          │
│               (Ollama)               │  │                                      │
│  - Chat/Agent: qwen2.5-coder / llama │  │  - SQLite Database (Users, Workspaces│
│  - Embeddings: nomic-embed-text      │  │  - ChromaDB Vector Store (Chunks)    │
│  - 100% On-Device Inference          │  │  - Local Filesystem (Target Projects)│
└──────────────────────────────────────┘  └──────────────────────────────────────┘
```

---

## 2. Core Components

### 2.1 Backend Services (`backend/app/`)

- **Authentication (`app/auth/`)**:
  - JWT authentication using short-lived access tokens (15 minutes) and HTTP-only, secure refresh cookies (7 days).
  - Password hashing with bcrypt.
  - In-memory rate limiting on authentication routes to mitigate brute-force attacks.
  - Multi-tenant workspace ownership resolution (`get_owned_workspace`) ensuring tenant boundaries.

- **Repository Engine (`app/repository/`)**:
  - Validates and resolves local repository paths on the host filesystem.
  - Generates hierarchical file trees with automatic exclusion of vendor directories (`node_modules`, `.venv`, `.git`) and binary files.
  - Fast substring search and language detection across codebases.
  - Native OS directory picker endpoint (`/api/repo/pick-directory`).

- **Retrieval-Augmented Generation (`app/rag/`)**:
  - **Chunking Pipeline**: Language-aware AST chunking for Python (classes, functions, module docstrings), regex-heuristic chunking for TypeScript/JavaScript, and sliding-window fallback for other languages.
  - **Vector Storage**: Local embedded ChromaDB instance (`chromadb.PersistentClient`) storing document chunks and metadata.
  - **Embedding Generation**: Connects to local Ollama embedding models (`nomic-embed-text`).
  - **Semantic Retrieval**: Top-$k$ similarity search with cosine similarity scoring.

- **Agent Engine (`app/agent/`)**:
  - **Target Resolution**: Determines target file based on explicit path mentions or top RAG retrieval hits.
  - **Rewrite & Diff Generation**: Requests complete target file rewrite from the local LLM and computes clean unified diffs using Python's standard `difflib`.
  - **Human-in-the-Loop Approval Gate**: Changes are never written to disk autonomously; user review and explicit approval via `/api/agent/{id}/apply` is required.

- **Validation Runner (`app/validation/`)**:
  - Executes project tests and linters (`pytest`, `ruff check`, `npm test`, `npm run lint`) after patch application.
  - Enforces strict process isolation (`shell=False`), timeout budgets, output capture caps, and sensitive environment variable scrubbing.
  - Supports iterative feedback loops ("Ask agent to fix this") by passing failure logs back to the agent.

- **LLM Provider (`app/llm/`)**:
  - Asynchronous HTTP client communicating with the local Ollama daemon.
  - Configurable endpoints and fallback resilience.

---

### 2.2 Frontend Application (`frontend/src/`)

- **Single Page Application (SPA)**: Built with React 18, TypeScript, and Vite.
- **Views & Panels**:
  - **Repository Workspace (`RepoPanel`)**: Folder selection, native browse dialog, repository tree navigation, code viewer, and indexed chunk status.
  - **Playground (`ChatPanel`)**: Interactive chat interface with local LLMs, augmented with context chunks and cited source line ranges.
  - **Agent Edit (`AgentPanel` & `DiffView`)**: Natural language task prompt input, side-by-side/inline unified diff viewer, approval controls, and validation test runner.
- **Authentication Context (`AuthContext`)**: Manages session state, automatic token refreshing, and authenticated fetch requests.

---

## 3. Key Data Flows

### 3.1 Repository Indexing & Semantic Search

```text
User Workspace Path
       │
       ▼
app/repository ──(Traverse Files)──► AST / Regex Chunker
                                           │
                                           ▼
                                    Code Snippets & Symbols
                                           │
                                           ▼
Ollama (nomic-embed-text) ◄──(Vectorize)───┘
       │
       ▼
 ChromaDB (Persistent Vector Store)
```

### 3.2 Agent Propose & Approval Flow

```text
1. User Request ─────────► app/agent/service.py
                              │
                              ├──► Resolve target file (Explicit / RAG Search)
                              ├──► Read original file content
                              ├──► Prompt local LLM (Ollama)
                              │
2. LLM Rewrite ◄──────────────┘
       │
       ▼
3. difflib.unified_diff(original, proposed)
       │
       ▼
4. Return Diff & Proposal to UI ────► [ User Reviews Diff in Browser ]
                                                    │
                                           (User Clicks "Approve")
                                                    │
5. POST /api/agent/{id}/apply ◄─────────────────────┘
       │
       ▼
6. Re-validate Path Boundary & Write to Disk
       │
       ▼
7. Validation Runner (pytest / npm test)
```

---

## 4. Technology Stack Summary

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite | User interface, diff visualization, tree browsing |
| **Backend** | FastAPI, Python 3.12+ | Async REST API, agent orchestration, validation engine |
| **Database** | SQLite via SQLModel | Users, credentials, workspaces, metadata |
| **Vector DB** | ChromaDB | Local persistent vector storage for code chunk embeddings |
| **Local LLM** | Ollama (`qwen2.5-coder`, `llama3`, `nomic-embed-text`) | On-device inference for chat, coding, and embeddings |

