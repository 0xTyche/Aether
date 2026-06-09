import { useEffect, useState } from "react";
import "./App.css";

interface Health {
  status: string;
  project: string;
  version: string;
}

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: Health) => setHealth(data))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="aether-root">
      <header>
        <h1>
          Aether <span className="aether-cn">· 以太</span>
        </h1>
        <p className="tagline">
          Macro events propagating through the global financial aether.
        </p>
      </header>

      <section className="status">
        <h2>Backend status</h2>
        {health && (
          <pre className="status-ok">
            {JSON.stringify(health, null, 2)}
          </pre>
        )}
        {error && (
          <pre className="status-err">backend unreachable: {error}</pre>
        )}
        {!health && !error && <pre>checking /api/health …</pre>}
      </section>

      <footer>
        <p>Phase 0 scaffolding · awaiting Phase 1.</p>
      </footer>
    </main>
  );
}

export default App;
