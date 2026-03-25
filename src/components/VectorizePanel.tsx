import { useState, useCallback, useEffect } from "react";
import { api } from "../api";

export function VectorizePanel() {
  const [vectorizing, setVectorizing] = useState(false);
  const [lastResult, setLastResult] = useState<{
    vectorized: number;
    errors: string[];
  } | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [vectorCount, setVectorCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [c, vc] = await Promise.all([
        api.countPapers(),
        fetch("http://127.0.0.1:8765/papers/vector-count").then((r) => r.json()),
      ]);
      setCounts(c);
      setVectorCount(vc.count);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleVectorize = useCallback(async () => {
    setVectorizing(true);
    try {
      const result = await api.vectorizePapers();
      setLastResult(result);
      await refresh();
    } catch (e) {
      setLastResult({ vectorized: 0, errors: [String(e)] });
    } finally {
      setVectorizing(false);
    }
  }, [refresh]);

  const parsedCount = counts["parsed"] ?? 0;
  const vectorizedCount = counts["vectorized"] ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Phase 3: Vectorize</h2>
        <div className="flex gap-3 text-sm text-gray-500">
          <span>
            <span className="font-medium text-blue-700">{parsedCount}</span>{" "}
            parsed (ready)
          </span>
          <span>
            <span className="font-medium text-green-700">{vectorizedCount}</span>{" "}
            vectorized
          </span>
          <span>
            <span className="font-medium text-gray-700">{vectorCount}</span>{" "}
            chunks in DB
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="mb-3 text-sm text-gray-600">
          Embed parsed chunks using sentence-transformers and store in LanceDB.
          First run will download the embedding model (~80MB).
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleVectorize}
            disabled={vectorizing || parsedCount === 0}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {vectorizing
              ? "Vectorizing..."
              : `Vectorize ${parsedCount} Paper${parsedCount !== 1 ? "s" : ""}`}
          </button>
          <button
            onClick={refresh}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {lastResult && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            lastResult.errors.length > 0
              ? "border-yellow-200 bg-yellow-50 text-yellow-800"
              : "border-green-200 bg-green-50 text-green-800"
          }`}
        >
          Vectorized: {lastResult.vectorized} papers
          {lastResult.errors.length > 0 && (
            <div className="mt-1">
              Errors: {lastResult.errors.slice(0, 5).join("; ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
