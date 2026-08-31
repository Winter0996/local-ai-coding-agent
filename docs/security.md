# Security Design & Threat Model

CodeForge AI is designed around a strict local-first security model: language models must never be given unrestricted operating system access, and user code must never leave the local environment.

---

## 1. Core Security Principles

1. **Local Isolation**: All LLM inference and embeddings run on-device via Ollama. Code, prompts, and embeddings are never transmitted to third-party cloud APIs.
2. **Multi-Tenant Workspace Boundaries**: Every resource (workspaces, file trees, searches, RAG indexes, agent proposals, and validations) is bound to an authenticated user and isolated at the database level.
3. **Human-in-the-Loop Approval Gate**: The agent can only *propose* modifications; file mutations require explicit human review and approval.
4. **Subprocess Sandboxing**: External commands are restricted to an immutable allowlist, executed without shell interpreters (`shell=False`), and executed in an environment sanitized of sensitive secrets.

---

## 2. Security Controls & Architecture

### 2.1 Workspace Boundary & Path Traversal Prevention
- **Path Resolution**: All filesystem paths are resolved to canonical absolute paths and validated against the workspace root:
  $$\text{resolved\_path} = \text{Path}(root / relative\_path).\text{resolve}()$$
  Any path attempting to traverse outside `workspace.root_path` (via `..`, symlinks, or absolute path overrides) raises a `PathTraversalError` and returns `403 Forbidden`.
- **System Path Protection**: Restricts workspace selection from operating directly on critical system roots (`/`, `C:\`, `C:\Windows`, etc.).
- **Binary & Media Handling**: Binary and non-text files are rejected (`415 Unsupported Media Type`) to prevent memory corruption or binary leakage into LLM prompts.

---

### 2.2 Multi-Tenant Isolation
- **Ownership Verification**: All route handlers enforce tenant ownership via `service.get_owned_workspace(db, workspace_id, current_user)`:
  ```python
  workspace = db.exec(
      select(Workspace)
      .where(Workspace.id == workspace_id)
      .where(Workspace.user_id == current_user.id)
  ).first()
  if not workspace:
      raise WorkspaceNotFoundError()
  ```
- **Vector Store Partitioning**: ChromaDB collections and vector queries are strictly partitioned by `workspace_id`.

---

### 2.3 Agent Approval Gate & Patch Reliability
- **Propose vs. Apply Separation**:
  - `POST /api/agent/{id}/propose`: Generates a proposal and calculates a standard unified diff using Python's `difflib`. No filesystem writes occur.
  - `POST /api/agent/{id}/apply`: The human approval gate. Re-verifies the server-side path boundary before applying the user-approved content to disk.
- **Defensive Parsing**: Strips model markdown code fences and extraneous text artifacts before generating diffs or applying patches.

#### Known Limitation & Defense
Small local models may occasionally hallucinate by dropping unrelated functions during full-file rewrites or echoing prompt instructions. CodeForge AI mitigates this by:
1. Computing unified diffs against the original file rather than trusting model-generated diffs.
2. Requiring human review of the unified diff before the apply endpoint can be invoked.

---

### 2.4 Validation Runner & Subprocess Security
The validation runner allows users to run tests and linters post-patch. To prevent arbitrary code execution and environment compromise:

1. **Strict Command Allowlist**: Only explicitly hardcoded tools are permitted:
   - `pytest`
   - `ruff check .`
   - `npm test`
   - `npm run lint`
   *User-supplied command strings or arbitrary flags are strictly rejected.*
2. **No Shell Execution**: Subprocesses are invoked with `shell=False` and tokenized argument arrays, completely eliminating shell injection vulnerabilities (e.g. `; rm -rf`, `&&`, `|`).
3. **Secret-Stripped Environment**: Child processes inherit an environment sanitized of sensitive application credentials:
   - Stripped: `JWT_SECRET`, database connection strings, auth tokens, and session keys.
4. **Execution Budgets**:
   - **Timeout**: Enforces strict execution timeouts (default: 30 seconds) to prevent infinite loops or denial-of-service.
   - **Output Truncation**: Standard output and error streams are capped (default: 50 KB) to prevent memory exhaustion.

---

### 2.5 Authentication & Session Management
- **Password Security**: Passwords hashed using bcrypt with salt.
- **Token Strategy**:
  - **Access Token**: Short-lived JWT (15 minutes) sent in `Authorization: Bearer` headers.
  - **Refresh Token**: Long-lived token (7 days) stored in an `HttpOnly`, `SameSite=Lax`, secure cookie to mitigate XSS-based token theft.
- **Brute-Force Protection**: In-memory rate limiting applied to `/api/auth/login` and `/api/auth/register`.
- **CORS Configuration**: Configured with strict origin whitelisting (`http://localhost:5173`) and explicit credential support (`allow_credentials=True`).

---

### 2.6 RAG Prompt Injection Defenses
- **Context Delimitation**: Retrieved repository code chunks are inserted into chat prompts within strictly delimited context blocks with clear role boundaries, preventing repository source code from masquerading as system instructions.