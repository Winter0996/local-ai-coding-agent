export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <p>
        © {year} · Built with React, TypeScript, FastAPI, Vite · Coded in
        Cursor · Local-first AI agent, $0 API cost · Developed by Nathan
        Winter
      </p>
    </footer>
  );
}