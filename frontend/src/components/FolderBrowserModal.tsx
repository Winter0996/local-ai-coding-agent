import { useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import type { BrowseResult } from "../lib/filesystemTypes";

type FolderBrowserModalProps = {
  onSelect: (path: string) => void;
  onClose: () => void;
};

export function FolderBrowserModal({ onSelect, onClose }: FolderBrowserModalProps) {
  const { fetchWithAuth } = useAuth();
  const [result, setResult] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(path: string | null) {
    setLoading(true);
    setError("");
    try {
      const url = path
        ? `/api/filesystem/browse?path=${encodeURIComponent(path)}`
        : "/api/filesystem/browse";
      const response = await fetchWithAuth(url);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Could not browse that folder.");
      }
      setResult((await response.json()) as BrowseResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal folder-browser" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>Choose a folder</h3>
          <button type="button" className="modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="folder-browser-path">{result?.path ?? "Loading..."}</div>

        {error && <div className="error">{error}</div>}

        <div className="folder-browser-list">
          {loading && <p className="folder-browser-empty">Loading...</p>}

          {!loading && result?.roots && result.roots.length > 1 && (
            <div className="folder-browser-roots">
              {result.roots.map((root) => (
                <button
                  key={root.path}
                  type="button"
                  className="folder-browser-root"
                  onClick={() => load(root.path)}
                >
                  {root.name}
                </button>
              ))}
            </div>
          )}

          {!loading && result?.parent && (
            <button
              type="button"
              className="folder-browser-row folder-browser-up"
              onClick={() => load(result.parent)}
            >
              ⤴ ..
            </button>
          )}

          {!loading &&
            result?.entries.map((entry) => (
              <button
                key={entry.path}
                type="button"
                className="folder-browser-row"
                onClick={() => load(entry.path)}
              >
                📁 {entry.name}
              </button>
            ))}

          {!loading && result && result.entries.length === 0 && !result.parent && (
            <p className="folder-browser-empty">No subfolders here.</p>
          )}
        </div>

        <div className="folder-browser-actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            disabled={!result?.path}
            onClick={() => result?.path && onSelect(result.path)}
          >
            Select this folder
          </button>
        </div>
      </div>
    </div>
  );
}