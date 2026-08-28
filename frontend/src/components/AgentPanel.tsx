import { type FormEvent, useState } from "react";

import { useAuth } from "../context/AuthContext";
import type { AgentProposal, Workspace } from "../lib/repoTypes";
import { DiffView } from "./DiffView";

type AgentPanelProps = {
  workspace: Workspace | null;
};

export function AgentPanel({ workspace }: AgentPanelProps) {
  const { fetchWithAuth } = useAuth();
  const [message, setMessage] = useState("");
  const [proposal, setProposal] = useState<AgentProposal | null>(null);
  const [proposing, setProposing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [error, setError] = useState("");

  async function handlePropose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !message.trim()) return;

    setProposing(true);
    setError("");
    setProposal(null);
    setApplied(false);

    try {
      const response = await fetchWithAuth(`/api/agent/${workspace.id}/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Could not generate a proposal.");
      }

      setProposal((await response.json()) as AgentProposal);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setProposing(false);
    }
  }

  async function handleApprove() {
    if (!workspace || !proposal) return;

    setApplying(true);
    setError("");

    try {
      const response = await fetchWithAuth(`/api/agent/${workspace.id}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: proposal.target_path,
          content: proposal.proposed_content,
        }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Could not apply the change.");
      }

      setApplied(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setApplying(false);
    }
  }

  function handleDiscard() {
    setProposal(null);
    setApplied(false);
  }

  if (!workspace) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Agent</h2>
            <p>Open a repository first — the agent needs a workspace to edit.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Agent</h2>
          <p>Working in {workspace.name} — every change requires your approval.</p>
        </div>
      </div>

      <form onSubmit={handlePropose}>
        <label htmlFor="agent-message">What should change?</label>
        <textarea
          id="agent-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="e.g. add input validation to the login handler in auth/routes.py"
          rows={4}
        />
        <button disabled={proposing || !message.trim()} type="submit">
          {proposing ? "Thinking..." : "Propose change"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {proposal && (
        <div className="proposal">
          <div className="proposal-header">
            <span className="proposal-target">{proposal.target_path}</span>
          </div>
          <p className="proposal-explanation">{proposal.explanation}</p>

          <DiffView diff={proposal.diff} />

          {applied ? (
            <div className="applied-banner">
              Applied — {proposal.target_path} has been updated on disk.
            </div>
          ) : (
            <div className="proposal-actions">
              <button type="button" onClick={handleApprove} disabled={applying}>
                {applying ? "Applying..." : "Approve & apply"}
              </button>
              <button
                type="button"
                className="link-button"
                onClick={handleDiscard}
                disabled={applying}
              >
                Discard
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}