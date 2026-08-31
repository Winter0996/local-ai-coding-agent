import { useAuth } from "../context/AuthContext";

type Tab = "chat" | "repo" | "agent";

type NavbarProps = {
  tab: Tab;
  onTabChange: (tab: Tab) => void;
};

function CodeBrowserIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m8 8-4 4 4 4" />
      <path d="m16 8 4 4-4 4" />
      <path d="m14 4-4 16" />
    </svg>
  );
}

export function Navbar({
  tab,
  onTabChange,
}: NavbarProps) {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <header className="site-nav">
      <div className="nav-inner">
        <button
          className="brand"
          type="button"
          onClick={() => onTabChange("repo")}
          aria-label="CodeForge AI home"
        >
          <span className="brand-icon">
            <CodeBrowserIcon />
          </span>

          <span>
            CodeForge
            <small>AI</small>
          </span>
        </button>

        {isAuthenticated && (
          <nav
            className="main-nav"
            aria-label="Primary navigation"
          >
            <button
              type="button"
              className={`nav-link ${
                tab === "repo" ? "nav-link-active" : ""
              }`}
              onClick={() => onTabChange("repo")}
            >
              Repository
            </button>

            <button
              type="button"
              className={`nav-link ${
                tab === "chat" ? "nav-link-active" : ""
              }`}
              onClick={() => onTabChange("chat")}
            >
              Playground
            </button>

            <button
              type="button"
              className={`nav-link ${
                tab === "agent" ? "nav-link-active" : ""
              }`}
              onClick={() => onTabChange("agent")}
            >
              Agent Edit
            </button>
          </nav>
        )}

        <div className="nav-actions">
          {isAuthenticated && user && (
            <div className="user-chip" title={user.email}>
              <span className="user-avatar">
                {user.email.charAt(0).toUpperCase()}
              </span>

              <span className="user-email">
                {user.email}
              </span>
            </div>
          )}

          {isAuthenticated && (
            <button
              type="button"
              className="secondary-action nav-logout"
              onClick={() => void logout()}
            >
              Sign out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}