import { useState, useCallback, useEffect, useRef } from "react";

const API = "http://127.0.0.1:8765";

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  // Arrays and objects: pretty-print as JSON
  return JSON.stringify(value, null, 2);
}

interface Session {
  id: string;
  prompt_text: string | null;
  status: string;
  created_at: string | null;
  result_count: number;
}

interface Result {
  id: string;
  session_id: string;
  doc_id: string;
  doc_title: string | null;
  filename: string | null;
  result_data: string;
  citations: string;
  created_at: string | null;
}

export function ResultsPanel() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await fetch(`${API}/results/sessions`).then((r) => r.json());
      setSessions(data);
    } catch {}
  }, []);

  const loadResults = useCallback(
    async (sessionId: string | null, newOffset = 0) => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          limit: "50",
          offset: String(newOffset),
        });
        if (sessionId) params.set("session_id", sessionId);
        const data = await fetch(`${API}/results/?${params}`).then((r) =>
          r.json(),
        );
        if (newOffset === 0) {
          setResults(data);
        } else {
          setResults((prev) => [...prev, ...data]);
        }
        setHasMore(data.length === 50);
        setOffset(newOffset + data.length);
      } catch {}
      setLoading(false);
    },
    [],
  );

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    loadResults(selectedSession, 0);
  }, [selectedSession, loadResults]);

  // Infinite scroll
  const handleScroll = useCallback(() => {
    if (!scrollRef.current || loading || !hasMore) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    if (scrollHeight - scrollTop - clientHeight < 200) {
      loadResults(selectedSession, offset);
    }
  }, [loading, hasMore, selectedSession, offset, loadResults]);

  const handleEdit = useCallback(
    async (resultId: string, fieldName: string, newValue: string) => {
      await fetch(`${API}/results/${resultId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field_name: fieldName, new_value: newValue }),
      });
      // Refresh results
      loadResults(selectedSession, 0);
    },
    [selectedSession, loadResults],
  );

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-medium">Phase 5: Results</h2>

      {/* Session filter */}
      <div className="flex gap-3 items-center">
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={selectedSession ?? ""}
          onChange={(e) => setSelectedSession(e.target.value || null)}
        >
          <option value="">All sessions</option>
          {sessions
            .filter((s) => s.result_count > 0)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} — {s.prompt_text?.slice(0, 40) || "Template search"} (
                {s.result_count} results)
              </option>
            ))}
        </select>
        <button
          onClick={refreshSessions}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      {/* Results list */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="max-h-[600px] overflow-y-auto space-y-3"
      >
        {results.length === 0 && !loading && (
          <div className="py-12 text-center text-gray-400">
            No results yet. Run a search in Phase 4.
          </div>
        )}

        {results.map((r) => {
          let fields: Record<string, unknown> = {};
          let citations: Record<string, unknown> = {};
          try {
            fields = JSON.parse(r.result_data);
          } catch {}
          try {
            citations = JSON.parse(r.citations);
          } catch {}

          return (
            <div
              key={r.id}
              className="rounded-lg border border-gray-200 bg-white p-4"
            >
              <div className="flex justify-between items-start mb-2">
                <h4 className="text-sm font-medium">
                  {r.doc_title || r.filename || r.doc_id}
                </h4>
                <span className="text-xs text-gray-400">
                  {r.created_at?.slice(0, 19)}
                </span>
              </div>

              <div className="space-y-1">
                {Object.entries(fields).map(([key, value]) => {
                  const isComplex =
                    typeof value === "object" && value !== null;
                  return (
                    <div key={key} className={isComplex ? "text-sm" : "flex gap-2 text-sm"}>
                      <span className="min-w-[140px] text-gray-500 shrink-0">
                        {key}:
                      </span>
                      {isComplex ? (
                        <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-xs whitespace-pre-wrap">
                          {JSON.stringify(value, null, 2)}
                        </pre>
                      ) : (
                        <EditableField
                          value={formatFieldValue(value)}
                          onSave={(newVal) => handleEdit(r.id, key, newVal)}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              {Object.keys(citations).length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-gray-400">
                    Citations
                  </summary>
                  <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-xs">
                    {JSON.stringify(citations, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          );
        })}

        {loading && (
          <div className="py-4 text-center text-gray-400 text-sm">Loading...</div>
        )}
      </div>
    </div>
  );
}

function EditableField({
  value,
  onSave,
}: {
  value: string;
  onSave: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);

  if (!editing) {
    return (
      <span
        className="text-gray-700 cursor-pointer hover:bg-gray-50 px-1 rounded"
        onClick={() => {
          setEditing(true);
          setEditValue(value);
        }}
        title="Click to edit"
      >
        {value || "\u2014"}
      </span>
    );
  }

  return (
    <span className="flex gap-1">
      <input
        className="flex-1 rounded border border-blue-300 px-1 py-0.5 text-sm focus:outline-none"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            onSave(editValue);
            setEditing(false);
          }
          if (e.key === "Escape") setEditing(false);
        }}
        autoFocus
      />
      <button
        onClick={() => {
          onSave(editValue);
          setEditing(false);
        }}
        className="text-xs text-blue-600"
      >
        Save
      </button>
      <button
        onClick={() => setEditing(false)}
        className="text-xs text-gray-400"
      >
        Cancel
      </button>
    </span>
  );
}
