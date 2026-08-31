import { type FormEvent, useState } from "react";

import { AgentPanel } from "./components/AgentPanel";
import { AuthForm } from "./components/AuthForm";
import { Navbar } from "./components/Navbar";
import { RepoPanel } from "./components/RepoPanel";
import { useAuth } from "./context/AuthContext";
import type { Workspace } from "./lib/repoTypes";

type Tab = "chat" | "repo" | "agent";

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
  const { user, fetchWithAuth } = useAuth();
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
        headers: {
          "Content-Type": "application/json",
        },
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
          <div className="section-kicker">LOCAL MODEL</div>

          <h2>Agent Playground</h2>

          <p>
            Signed in as {user?.email}
            {workspace && <> · grounded in {workspace.name}</>}
          </p>
        </div>

        {model && <span className="model-badge">{model}</span>}
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

        <button
          className="primary-action"
          disabled={loading || !message.trim()}
          type="submit"
        >
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
            <div
              key={`${source.path}:${source.start_line}:${index}`}
              className="source-row"
            >
              <span className="source-path">
                {source.path}:{source.start_line}-{source.end_line}
              </span>

              {source.symbol && (
                <span className="badge">{source.symbol}</span>
              )}

              <span className="source-score">
                score {source.score.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function LoadingScreen() {
  return (
    <section className="panel loading-panel">
      <div className="loading-spinner" aria-hidden="true" />

      <div>
        <strong>Checking your session</strong>

        <p>Restoring your secure local workspace...</p>
      </div>
    </section>
  );
}

function App() {
  const { isLoading, isAuthenticated } = useAuth();

  const [tab, setTab] = useState<Tab>("repo");

  const [activeWorkspace, setActiveWorkspace] =
    useState<Workspace | null>(null);

  const year = new Date().getFullYear();

  return (
    <div className="app-root">
      <Navbar tab={tab} onTabChange={setTab} />

      <main className="app-shell">
        {!isAuthenticated && !isLoading ? (
          <section className="landing-header">
            <div className="hero-mark" aria-hidden="true">
              {"</>"}
            </div>

            <div>
              <p className="eyebrow">
                LOCAL-FIRST SOFTWARE ENGINEERING
              </p>

              <h1>
                Build with your codebase, not around it.
              </h1>

              <p className="subtitle">
                CodeForge AI is a local engineering assistant powered
                by Ollama. Your repositories stay on your machine, with
                no paid AI API or API key required.
              </p>
            </div>
          </section>
        ) : (
          <section className="workspace-header">
            <div>
              <p className="eyebrow">
                LOCAL-FIRST SOFTWARE ENGINEERING AGENT
              </p>

              <h1>
                {tab === "repo"
                  ? "Repository workspace"
                  : tab === "agent"
                    ? "Agent edit"
                    : "Agent playground"}
              </h1>

              <p className="subtitle">
                {tab === "repo"
                  ? "Open a local project, inspect its structure, search files, and prepare it for RAG."
                  : tab === "agent"
                    ? "Review proposed code changes, approve them, then validate the result."
                    : "Ask engineering questions and ground the model in your selected repository."}
              </p>
            </div>

            {isAuthenticated && (
              <div className="status-pill">
                <span className="status-dot" />
                Local environment
              </div>
            )}
          </section>
        )}

        {isLoading ? (
          <LoadingScreen />
        ) : isAuthenticated ? (
          <div className="content-stack">
            {tab === "repo" ? (
              <RepoPanel
                onWorkspaceSelected={setActiveWorkspace}
              />
            ) : tab === "agent" ? (
              <AgentPanel workspace={activeWorkspace} />
            ) : (
              <ChatPanel workspace={activeWorkspace} />
            )}
          </div>
        ) : (
          <AuthForm />
        )}
      </main>

      <footer className="site-footer">
        <div>
          <strong>CodeForge AI</strong>

          <span>
            Local-first AI software engineering
          </span>
        </div>

        <p>
          © {year} · Built with React, TypeScript, Vite, FastAPI &amp;
          Ollama · Open-source stack · Developed by Nathan Winter
        </p>
      </footer>
    </div>
  );
}

export default App;