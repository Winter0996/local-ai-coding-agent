import { type FormEvent, useState } from "react";

import { useAuth } from "../context/AuthContext";
import type {
  FileContent,
  FileTree,
  IndexResult,
  IndexStatus,
  RepositoryMetadata,
  SearchResult,
  Workspace,
} from "../lib/repoTypes";
import { FileTreeView } from "./FileTreeView";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type RepoPanelProps = {
  onWorkspaceSelected?: (
    workspace: Workspace | null,
  ) => void;
};

function FolderIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width="15"
      height="15"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 6.5h6l2 2h9v9.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-9.5a2 2 0 0 1 2-2Z" />
      <path d="M3.5 6.5v-1a2 2 0 0 1 2-2h4l2 2h4" />
    </svg>
  );
}

export function RepoPanel({
  onWorkspaceSelected,
}: RepoPanelProps) {
  const { fetchWithAuth } = useAuth();

  const [path, setPath] = useState("");
  const [workspace, setWorkspace] =
    useState<Workspace | null>(null);

  const [metadata, setMetadata] =
    useState<RepositoryMetadata | null>(null);

  const [tree, setTree] =
    useState<FileTree | null>(null);

  const [selectedFile, setSelectedFile] =
    useState<FileContent | null>(null);

  const [searchQuery, setSearchQuery] = useState("");

  const [searchResult, setSearchResult] =
    useState<SearchResult | null>(null);

  const [indexStatus, setIndexStatus] =
    useState<IndexStatus | null>(null);

  const [lastIndexResult, setLastIndexResult] =
    useState<IndexResult | null>(null);

  const [selecting, setSelecting] = useState(false);
  const [loadingFile, setLoadingFile] =
    useState(false);
  const [searching, setSearching] = useState(false);
  const [indexing, setIndexing] = useState(false);

  const [error, setError] =
    useState<string | null>(null);

  async function refreshIndexStatus(
    workspaceId: string,
  ) {
    const response = await fetchWithAuth(
      `/api/repo/${workspaceId}/index/status`,
    );

    if (response.ok) {
      setIndexStatus(
        (await response.json()) as IndexStatus,
      );
    }
  }

  async function handleIndex() {
    if (!workspace) return;

    setIndexing(true);
    setError(null);

    try {
      const response = await fetchWithAuth(
        `/api/repo/${workspace.id}/index`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        const body =
          await response.json().catch(() => null);

        throw new Error(
          body?.detail ?? "Indexing failed.",
        );
      }

      const result =
        (await response.json()) as IndexResult;

      setLastIndexResult(result);

      await refreshIndexStatus(workspace.id);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unknown error.",
      );
    } finally {
      setIndexing(false);
    }
  }

  async function handleBrowse() {
    setSelecting(true);
    setError(null);

    try {
      const response = await fetchWithAuth(
        "/api/repo/pick-directory",
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        const body =
          await response.json().catch(() => null);

        throw new Error(
          body?.detail ??
            "Could not open the folder picker.",
        );
      }

      const data =
        (await response.json()) as {
          path: string | null;
        };

      if (data.path) {
        setPath(data.path);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not open the folder picker.",
      );
    } finally {
      setSelecting(false);
    }
  }

  async function handleSelectRepo(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!path.trim()) return;

    setSelecting(true);
    setError(null);
    setSelectedFile(null);
    setSearchResult(null);
    setLastIndexResult(null);
    setIndexStatus(null);

    try {
      const selectRes = await fetchWithAuth(
        "/api/repo/select",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ path }),
        },
      );

      if (!selectRes.ok) {
        const body =
          await selectRes.json().catch(() => null);

        throw new Error(
          body?.detail ??
            "Could not open that repository.",
        );
      }

      const ws =
        (await selectRes.json()) as Workspace;

      setWorkspace(ws);

      onWorkspaceSelected?.(ws);

      const [treeRes, metaRes] =
        await Promise.all([
          fetchWithAuth(
            `/api/repo/${ws.id}/tree`,
          ),
          fetchWithAuth(
            `/api/repo/${ws.id}/metadata`,
          ),
        ]);

      if (treeRes.ok) {
        setTree(
          (await treeRes.json()) as FileTree,
        );
      }

      if (metaRes.ok) {
        setMetadata(
          (await metaRes.json()) as RepositoryMetadata,
        );
      }

      await refreshIndexStatus(ws.id);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unknown error.",
      );

      setWorkspace(null);

      onWorkspaceSelected?.(null);

      setTree(null);
      setMetadata(null);
    } finally {
      setSelecting(false);
    }
  }

  async function handleSelectFile(
    filePath: string,
  ) {
    if (!workspace) return;

    setLoadingFile(true);
    setError(null);

    try {
      const response = await fetchWithAuth(
        `/api/repo/${workspace.id}/file?path=${encodeURIComponent(
          filePath,
        )}`,
      );

      if (!response.ok) {
        const body =
          await response.json().catch(() => null);

        throw new Error(
          body?.detail ??
            "Could not read that file.",
        );
      }

      setSelectedFile(
        (await response.json()) as FileContent,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unknown error.",
      );
    } finally {
      setLoadingFile(false);
    }
  }

  async function handleSearch(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (
      !workspace ||
      !searchQuery.trim()
    ) {
      return;
    }

    setSearching(true);
    setError(null);

    try {
      const response = await fetchWithAuth(
        `/api/repo/${workspace.id}/search?q=${encodeURIComponent(
          searchQuery,
        )}`,
      );

      if (!response.ok) {
        const body =
          await response.json().catch(() => null);

        throw new Error(
          body?.detail ?? "Search failed.",
        );
      }

      setSearchResult(
        (await response.json()) as SearchResult,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unknown error.",
      );
    } finally {
      setSearching(false);
    }
  }

  return (
    <section className="panel repo-panel">
      <div className="panel-header">
        <div>
          <h2>Repository</h2>

          <p>
            Point CodeForge AI at a local project folder.
          </p>
        </div>
      </div>

      <form
        onSubmit={handleSelectRepo}
        className="repo-select-form"
      >
        <input
          type="text"
          value={path}
          onChange={(event) =>
            setPath(event.target.value)
          }
          placeholder={
            "C:\\Users\\you\\Projects\\my-repo"
          }
          aria-label="Repository path"
        />

        <button
          type="button"
          className="browse-button"
          onClick={() => void handleBrowse()}
          disabled={selecting}
          title="Choose a folder using your computer's file picker"
        >
          <FolderIcon />
          Browse
        </button>

        <button
          className="primary-action"
          disabled={
            selecting || !path.trim()
          }
          type="submit"
        >
          {selecting
            ? "Opening..."
            : "Open"}
        </button>
      </form>

      {error && (
        <div className="error">
          {error}
        </div>
      )}

      {metadata && (
        <div className="repo-meta">
          <span>
            <strong>
              {metadata.file_count}
            </strong>{" "}
            files
          </span>

          <span>
            {formatBytes(
              metadata.total_size_bytes,
            )}
          </span>

          {metadata.has_git && (
            <span className="badge">
              git
            </span>
          )}

          {metadata.languages
            .slice(0, 5)
            .map((lang) => (
              <span
                key={lang.language}
                className="badge"
              >
                {lang.language} ·{" "}
                {lang.file_count}
              </span>
            ))}
        </div>
      )}

      {workspace && (
        <div className="index-bar">
          <div className="index-status">
            {indexStatus?.indexed ? (
              <span>
                Indexed —{" "}
                <strong>
                  {indexStatus.chunk_count}
                </strong>{" "}
                chunks searchable

                {lastIndexResult && (
                  <span className="index-detail">
                    {" "}
                    (
                    {
                      lastIndexResult.file_count
                    }{" "}
                    files,{" "}
                    {
                      lastIndexResult.duration_seconds
                    }
                    s)
                  </span>
                )}
              </span>
            ) : (
              <span>
                Repository not indexed
              </span>
            )}
          </div>

          <button
            type="button"
            className="secondary-action"
            onClick={() =>
              void handleIndex()
            }
            disabled={indexing}
          >
            {indexing
              ? "Indexing..."
              : indexStatus?.indexed
                ? "Re-index"
                : "Index repository"}
          </button>
        </div>
      )}

      {workspace && tree && (
        <div className="repo-workspace">
          <aside className="file-tree">
            <div className="file-tree-header">
              <strong>
                {workspace.name}
              </strong>
            </div>

            <FileTreeView
              node={tree.root}
              selectedPath={
                selectedFile?.path ?? null
              }
              onSelectFile={(filePath) =>
                void handleSelectFile(
                  filePath,
                )
              }
            />
            {tree.truncated && (
              <p className="tree-truncated">
                Tree truncated — repository is large.
              </p>
            )}
          </aside>

          <section className="file-viewer">
            <div className="file-viewer-header">
              <form
                onSubmit={handleSearch}
                className="search-form"
              >
                <input
                  value={searchQuery}
                  onChange={(event) =>
                    setSearchQuery(
                      event.target.value,
                    )
                  }
                  placeholder="Search repository..."
                  aria-label="Search repository"
                />

                <button
                  type="submit"
                  className="secondary-action"
                  disabled={
                    searching ||
                    !searchQuery.trim()
                  }
                >
                  {searching
                    ? "Searching..."
                    : "Search"}
                </button>
              </form>
            </div>

            {searchResult && (
              <div className="search-results">
                <h3>
                  Search results
                </h3>

                {searchResult.matches.map(
                  (match, index) => (
                    <button
                      key={`${match.path}:${match.line_number}:${index}`}
                      type="button"
                      className="search-result"
                      onClick={() =>
                        void handleSelectFile(
                          match.path,
                        )
                      }
                    >
                      <strong>
                        {match.path}
                      </strong>

                      <span>
                        Line {match.line_number}
                      </span>

                      <code>
                        {match.line_text}
                      </code>
                    </button>
                  ),
                )}
              </div>
            )}

            {loadingFile && (
              <div className="empty-state">
                Loading file...
              </div>
            )}

            {!loadingFile &&
              selectedFile && (
                <article className="code-viewer">
                  <div className="code-viewer-header">
                    <span>
                      {selectedFile.path}
                    </span>

                    <span className="badge">
                      {selectedFile.language}
                    </span>
                  </div>

                  <pre>
                    <code>
                      {selectedFile.content}
                    </code>
                  </pre>
                </article>
              )}

            {!loadingFile &&
              !selectedFile && (
                <div className="empty-state">
                  Select a file from the
                  repository tree to inspect
                  its contents.
                </div>
              )}
          </section>
        </div>
      )}
    </section>
  );
}