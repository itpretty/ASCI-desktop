import { useState, useEffect } from "react";
import { ImportPanel } from "./components/ImportPanel";
import { ParsePanel } from "./components/ParsePanel";
import { VectorizePanel } from "./components/VectorizePanel";
import { SearchPanel } from "./components/SearchPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { ExportPanel } from "./components/ExportPanel";

const API_BASE = "http://127.0.0.1:8765";

const PHASES = [
  { id: 1, label: "Import" },
  { id: 2, label: "Parse" },
  { id: 3, label: "Vectorize" },
  { id: 4, label: "Search" },
  { id: 5, label: "Results" },
  { id: 6, label: "Export" },
] as const;

function App() {
  const [backendStatus, setBackendStatus] = useState<
    "connecting" | "online" | "offline"
  >("connecting");
  const [aiStatus, setAiStatus] = useState<{
    available: boolean;
    error: string | null;
  } | null>(null);
  const [activePhase, setActivePhase] = useState(1);

  useEffect(() => {
    let failCount = 0;
    const checkBackend = async () => {
      try {
        const resp = await fetch(`${API_BASE}/health`);
        if (resp.ok) {
          setBackendStatus("online");
          failCount = 0;
          // Also check AI status
          try {
            const aiResp = await fetch(`${API_BASE}/search/ai-status`);
            if (aiResp.ok) setAiStatus(await aiResp.json());
          } catch {}
        } else {
          failCount++;
        }
      } catch {
        failCount++;
      }
      if (failCount >= 3) {
        setBackendStatus("offline");
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold tracking-tight">ASCI-Desktop</h1>
          {backendStatus === "online" && aiStatus && (
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  aiStatus.available ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-gray-500">
                {aiStatus.available
                  ? "Claude CLI available"
                  : "Claude CLI unavailable"}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Phase navigation */}
      {backendStatus === "online" && (
        <nav className="border-b border-gray-200 bg-white px-6">
          <div className="flex gap-1">
            {PHASES.map((phase) => (
              <button
                key={phase.id}
                onClick={() => setActivePhase(phase.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activePhase === phase.id
                    ? "border-gray-900 text-gray-900"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {phase.id}. {phase.label}
              </button>
            ))}
          </div>
        </nav>
      )}

      {/* Main content */}
      <main className="mx-auto max-w-5xl px-6 py-8">
        {backendStatus === "connecting" && (
          <div className="flex flex-col items-center justify-center py-24 text-gray-400">
            <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
            <p>Starting backend service...</p>
          </div>
        )}

        {backendStatus === "offline" && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-red-700">
              Backend is not running. Start it with:{" "}
              <code className="rounded bg-red-100 px-2 py-0.5 text-sm">
                cd backend && source .venv/bin/activate && python -m uvicorn
                app.main:app --port 8765
              </code>
            </p>
          </div>
        )}

        {backendStatus === "online" && (
          <>
            {activePhase === 1 && <ImportPanel onComplete={() => setActivePhase(2)} />}
            {activePhase === 2 && <ParsePanel onComplete={() => setActivePhase(3)} />}
            {activePhase === 3 && <VectorizePanel />}
            {activePhase === 4 && <SearchPanel />}
            {activePhase === 5 && <ResultsPanel />}
            {activePhase === 6 && <ExportPanel />}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
