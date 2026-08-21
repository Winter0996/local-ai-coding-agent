import { type FormEvent, useState } from "react";

import { useAuth } from "../context/AuthContext";

export function AuthForm() {
  const { login, register, error } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    if (mode === "register" && password.length < 12) {
      setLocalError("Password must be at least 12 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
    } catch {
      // error state is already surfaced via useAuth().error
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel auth-panel">
      <div className="panel-header">
        <div>
          <h2>{mode === "login" ? "Sign in" : "Create an account"}</h2>
          <p>
            {mode === "login"
              ? "CodeForge AI runs locally — this just protects your workspace."
              : "Use at least 12 characters. This stays on your machine."}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={mode === "register" ? 12 : undefined}
          required
        />

        <button disabled={submitting || !email || !password} type="submit">
          {submitting
            ? "Please wait..."
            : mode === "login"
              ? "Sign in"
              : "Create account"}
        </button>
      </form>

      {(localError || error) && <div className="error">{localError ?? error}</div>}

      <button
        type="button"
        className="link-button"
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setLocalError(null);
        }}
      >
        {mode === "login"
          ? "Need an account? Register"
          : "Already have an account? Sign in"}
      </button>
    </section>
  );
}
