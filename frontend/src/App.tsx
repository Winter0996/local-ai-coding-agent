import { type FormEvent, useState } from "react";

import { AuthForm } from "./components/AuthForm";
import { RepoPanel } from "./components/RepoPanel";
import { useAuth } from "./context/AuthContext";
import type { Workspace } from "./lib/repoTypes";

type ChatSource = {
  path: string;
  symbol: string | null;
  start_line: number;
  end_line: number;
  score: number;
};

type ChatResponse = {
  response: string;
  model: string;
  sources: ChatSource[];
};

function ChatPanel({ workspace }: { workspace: Workspace | null }) {
  const { user, logout, fetchWithAuth } = useAuth();
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState("");
  const [model, setModel] = useState("");
  const [sources, setSources] = useState<ChatSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!message.trim()) return;

    setLoading(true);
    setError("");
    setResponse("");
    setSources([]);

    try {
      const result = await fetchWithAuth("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          workspace_id: workspace?.id ?? null,
        }),
      });

      if (!result.ok) {
        const body = await result.json().catch(() => null);
        throw new Error(body?.detail ?? "The API request failed.");
      }

      const data = (await result.json()) as ChatResponse;
      setResponse(data.response);
      setModel(data.model);
      setSources(data.sources);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Agent Playground</h2>
          <p>
            Signed in as {user?.email}
            {workspace && <> · grounded in {workspace.name}</>}
          </p>
        </div>
        <div className="panel-header-actions">
          {model && <span className="model-badge">{model}</span>}
          <button type="button" className="link-button" onClick={() => logout()}>
            Sign out
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <label htmlFor="message">Engineering task</label>
        <textarea
          id="message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={
            workspace
              ? `Ask about ${workspace.name}...`
              : "Ask the local model a software engineering question..."
          }
          rows={7}
        />

        <button disabled={loading || !message.trim()} type="submit">
          {loading ? "Running local model..." : "Ask CodeForge"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {response && (
        <article className="response">
          <h3>Agent response</h3>
          <pre>{response}</pre>
        </article>
      )}

      {sources.length > 0 && (
        <div className="sources">
          <h3>Retrieved from your repository</h3>
          {sources.map((source, index) => (
            <div key={`${source.path}:${source.start_line}:${index}`} className="source-row">
              <span className="source-path">
                {source.path}:{source.start_line}-{source.end_line}
              </span>
              {source.symbol && <span className="badge">{source.symbol}</span>}
              <span className="source-score">score {source.score.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function App() {
  const { isLoading, isAuthenticated } = useAuth();
  const [tab, setTab] = useState<"chat" | "repo">("repo");
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">LOCAL AI SOFTWARE ENGINEERING AGENT</p>
        <h1>CodeForge AI</h1>
        <p className="subtitle">
          A local-first engineering assistant powered by Ollama. No paid AI
          APIs. No API keys. No credit card.
        </p>
      </section>

      {isLoading ? (
        <section className="panel">
          <p>Checking session...</p>
        </section>
      ) : isAuthenticated ? (
        <>
          <nav className="tab-bar">
            <button
              type="button"
              className={tab === "repo" ? "tab-active" : ""}
              onClick={() => setTab("repo")}
            >
              Repository
            </button>
            <button
              type="button"
              className={tab === "chat" ? "tab-active" : ""}
              onClick={() => setTab("chat")}
            >
              Agent Playground
            </button>
          </nav>
          {tab === "repo" ? (
            <RepoPanel onWorkspaceSelected={setActiveWorkspace} />
          ) : (
            <ChatPanel workspace={activeWorkspace} />
          )}
        </>
      ) : (
        <AuthForm />
      )}

      <footer>
        <span>CodeForge AI v0.1.0</span>
        <span>Local-first • Open-source stack • $0 API cost</span>
      </footer>
    </main>
  );
}

export default App;