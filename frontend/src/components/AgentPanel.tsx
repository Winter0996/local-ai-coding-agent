import { type FormEvent, useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import type { AgentProposal, CommandResult, Workspace } from "../lib/repoTypes";
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

  const [availableCommands, setAvailableCommands] = useState<string[]>([]);
  const [runningCommand, setRunningCommand] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<CommandResult | null>(null);

  useEffect(() => {
    if (!workspace) {
      setAvailableCommands([]);
      return;
    }
    fetchWithAuth(`/api/agent/${workspace.id}/validation/commands`)
      .then((res) => (res.ok ? res.json() : { commands: [] }))
      .then((body) => setAvailableCommands(body.commands ?? []))
      .catch(() => setAvailableCommands([]));
  }, [workspace, fetchWithAuth]);

  async function handlePropose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !message.trim()) return;

    setProposing(true);
    setError("");
    setProposal(null);
    setApplied(false);
    setLastResult(null);

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
    setLastResult(null);
  }

  async function handleRunCommand(commandKey: string) {
    if (!workspace) return;

    setRunningCommand(commandKey);
    setError("");

    try {
      const response = await fetchWithAuth(`/api/agent/${workspace.id}/validation/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_key: commandKey }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Could not run that command.");
      }

      setLastResult((await response.json()) as CommandResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setRunningCommand(null);
    }
  }

  function handleFixBasedOnFailure() {
    if (!lastResult || !proposal) return;
    const failureExcerpt = (lastResult.stderr || lastResult.stdout).slice(0, 2000);
    setMessage(
      `The previous change to ${proposal.target_path} broke '${lastResult.command_key}'. ` +
        `Fix it. Failure output:\n${failureExcerpt}`,
    );
    setProposal(null);
    setApplied(false);
    setLastResult(null);
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

          {applied && availableCommands.length > 0 && (
            <div className="validation">
              <h3>Validate</h3>
              <div className="validation-buttons">
                {availableCommands.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => handleRunCommand(key)}
                    disabled={runningCommand !== null}
                  >
                    {runningCommand === key ? "Running..." : `Run ${key}`}
                  </button>
                ))}
              </div>

              {lastResult && (
                <div className={`validation-result ${lastResult.passed ? "passed" : "failed"}`}>
                  <div className="validation-result-header">
                    <span>
                      {lastResult.timed_out
                        ? "Timed out"
                        : lastResult.passed
                          ? "Passed"
                          : "Failed"}
                    </span>
                    <span className="validation-duration">
                      {lastResult.duration_seconds}s
                    </span>
                  </div>
                  <pre className="validation-output">
                    {(lastResult.stdout + "\n" + lastResult.stderr).trim() ||
                      "(no output)"}
                  </pre>
                  {lastResult.truncated && (
                    <p className="tree-truncated">Output truncated.</p>
                  )}
                  {!lastResult.passed && (
                    <button type="button" onClick={handleFixBasedOnFailure}>
                      Ask agent to fix this
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}