import { useAuth } from "../context/AuthContext";

function CodeBrowserIcon() {
  return (
    <svg
      className="navbar-icon"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect x="2" y="4" width="20" height="16" rx="2.5" stroke="currentColor" strokeWidth="1.7" />
      <line x1="2" y1="8.5" x2="22" y2="8.5" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="5.2" cy="6.3" r="0.9" fill="currentColor" />
      <circle cx="8" cy="6.3" r="0.9" fill="currentColor" />
      <circle cx="10.8" cy="6.3" r="0.9" fill="currentColor" />
      <path
        d="M9 12.5L6.5 15L9 17.5M15 12.5L17.5 15L15 17.5M13 11.5L11 18.5"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <div className="navbar-brand">
          <CodeBrowserIcon />
          <span className="navbar-title">CodeForge AI</span>
        </div>

        {isAuthenticated && (
          <div className="navbar-actions">
            <span className="navbar-user">{user?.email}</span>
            <button type="button" className="navbar-signout" onClick={() => logout()}>
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}