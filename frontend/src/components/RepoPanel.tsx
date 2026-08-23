import { type FormEvent, useState } from "react";

import { useAuth } from "../context/AuthContext";
import type {
  FileContent,
  FileTree,
  RepositoryMetadata,
  SearchResult,
  Workspace,
} from "../lib/repoTypes";
import { FileTreeView } from "./FileTreeView";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function RepoPanel() {
  const { fetchWithAuth } = useAuth();

  const [path, setPath] = useState("");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [metadata, setMetadata] = useState<RepositoryMetadata | null>(null);
  const [tree, setTree] = useState<FileTree | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);

  const [selecting, setSelecting] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSelectRepo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!path.trim()) return;

    setSelecting(true);
    setError(null);
    setSelectedFile(null);
    setSearchResult(null);

    try {
      const selectRes = await fetchWithAuth("/api/repo/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });

      if (!selectRes.ok) {
        const body = await selectRes.json().catch(() => null);
        throw new Error(body?.detail ?? "Could not open that repository.");
      }

      const ws = (await selectRes.json()) as Workspace;
      setWorkspace(ws);

      const [treeRes, metaRes] = await Promise.all([
        fetchWithAuth(`/api/repo/${ws.id}/tree`),
        fetchWithAuth(`/api/repo/${ws.id}/metadata`),
      ]);

      if (treeRes.ok) setTree((await treeRes.json()) as FileTree);
      if (metaRes.ok) setMetadata((await metaRes.json()) as RepositoryMetadata);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
      setWorkspace(null);
      setTree(null);
      setMetadata(null);
    } finally {
      setSelecting(false);
    }
  }

  async function handleSelectFile(filePath: string) {
    if (!workspace) return;

    setLoadingFile(true);
    setError(null);

    try {
      const response = await fetchWithAuth(
        `/api/repo/${workspace.id}/file?path=${encodeURIComponent(filePath)}`,
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Could not read that file.");
      }
      setSelectedFile((await response.json()) as FileContent);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setLoadingFile(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !searchQuery.trim()) return;

    setSearching(true);
    setError(null);

    try {
      const response = await fetchWithAuth(
        `/api/repo/${workspace.id}/search?q=${encodeURIComponent(searchQuery)}`,
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Search failed.");
      }
      setSearchResult((await response.json()) as SearchResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <section className="panel repo-panel">
      <div className="panel-header">
        <div>
          <h2>Repository</h2>
          <p>Point CodeForge AI at a local project folder.</p>
        </div>
      </div>

      <form onSubmit={handleSelectRepo} className="repo-select-form">
        <input
          type="text"
          value={path}
          onChange={(event) => setPath(event.target.value)}
          placeholder="C:\Users\you\Projects\my-repo"
        />
        <button disabled={selecting || !path.trim()} type="submit">
          {selecting ? "Opening..." : "Open"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {metadata && (
        <div className="repo-meta">
          <span>
            <strong>{metadata.file_count}</strong> files
          </span>
          <span>{formatBytes(metadata.total_size_bytes)}</span>
          {metadata.has_git && <span className="badge">git</span>}
          {metadata.languages.slice(0, 5).map((lang) => (
            <span key={lang.language} className="badge">
              {lang.language} · {lang.file_count}
            </span>
          ))}
        </div>
      )}

      {workspace && (
        <form onSubmit={handleSearch} className="repo-search-form">
          <input
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search across this repository..."
          />
          <button disabled={searching || !searchQuery.trim()} type="submit">
            {searching ? "Searching..." : "Search"}
          </button>
        </form>
      )}

      {searchResult && (
        <div className="search-results">
          <p className="search-summary">
            {searchResult.matches.length} match
            {searchResult.matches.length === 1 ? "" : "es"}
            {searchResult.truncated && " (showing first results)"}
          </p>
          {searchResult.matches.map((match, index) => (
            <button
              type="button"
              key={`${match.path}:${match.line_number}:${index}`}
              className="search-result-row"
              onClick={() => handleSelectFile(match.path)}
            >
              <span className="search-result-path">
                {match.path}:{match.line_number}
              </span>
              <code>{match.line_text}</code>
            </button>
          ))}
        </div>
      )}

      {tree && (
        <div className="repo-body">
          <div className="tree-container">
            <FileTreeView
              node={tree.root}
              selectedPath={selectedFile?.path ?? null}
              onSelectFile={handleSelectFile}
            />
            {tree.truncated && (
              <p className="tree-truncated">Tree truncated — repository is large.</p>
            )}
          </div>

          <div className="file-viewer">
            {loadingFile && <p>Loading file...</p>}
            {!loadingFile && selectedFile && (
              <>
                <div className="file-viewer-header">
                  <span>{selectedFile.path}</span>
                  {selectedFile.language && (
                    <span className="badge">{selectedFile.language}</span>
                  )}
                  {selectedFile.truncated && (
                    <span className="badge badge-warning">truncated</span>
                  )}
                </div>
                <pre className="file-content">
                  <code>{selectedFile.content}</code>
                </pre>
              </>
            )}
            {!loadingFile && !selectedFile && (
              <p className="file-viewer-empty">Select a file to view its contents.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}