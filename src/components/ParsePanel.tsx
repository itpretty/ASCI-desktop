import { useState, useCallback, useEffect } from "react";
import { api, type Paper } from "../api";

export function ParsePanel({ onComplete }: { onComplete?: () => void }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [parsing, setParsing] = useState(false);
  const [lastResult, setLastResult] = useState<{
    processed: number;
    skipped: number;
    errors: string[];
  } | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const refresh = useCallback(async () => {
    try {
      const [list, c] = await Promise.all([api.listPapers(), api.countPapers()]);
      setPapers(list);
      setCounts(c);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleParse = useCallback(async () => {
    setParsing(true);
    try {
      const result = await api.parsePapers();
      setLastResult(result);
      await refresh();
      // Auto-navigate if no more pending papers
      const freshCounts = await api.countPapers();
      if ((freshCounts["pending"] ?? 0) === 0) {
        onComplete?.();
      }
    } catch (e) {
      setLastResult({ processed: 0, skipped: 0, errors: [String(e)] });
    } finally {
      setParsing(false);
    }
  }, [refresh, onComplete]);

  const pendingCount = counts["pending"] ?? 0;
  const parsedCount = counts["parsed"] ?? 0;
  const skippedCount = counts["skipped_ocr"] ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Phase 2: Parse PDFs</h2>
        <div className="flex gap-3 text-sm text-gray-500">
          <span>
            <span className="font-medium text-gray-700">{pendingCount}</span> pending
          </span>
          <span>
            <span className="font-medium text-blue-700">{parsedCount}</span> parsed
          </span>
          {skippedCount > 0 && (
            <span>
              <span className="font-medium text-yellow-700">{skippedCount}</span> skipped (OCR)
            </span>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="mb-3 text-sm text-gray-600">
          Extract text from imported PDFs, detect scanned pages, and split into
          structured chunks. Uses PyMuPDF (no AI).
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleParse}
            disabled={parsing || pendingCount === 0}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {parsing ? "Parsing..." : `Parse ${pendingCount} Paper${pendingCount !== 1 ? "s" : ""}`}
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
          Parsed: {lastResult.processed}, Skipped (OCR): {lastResult.skipped}
          {lastResult.errors.length > 0 && (
            <div className="mt-1">
              Errors: {lastResult.errors.slice(0, 5).join("; ")}
              {lastResult.errors.length > 5 &&
                ` ... and ${lastResult.errors.length - 5} more`}
            </div>
          )}
        </div>
      )}

      {/* Parsed papers */}
      {papers.filter((p) => p.import_status !== "pending").length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500">
                <th className="px-4 py-2 font-medium">Filename</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Pages</th>
                <th className="px-4 py-2 font-medium">Chunks</th>
                <th className="px-4 py-2 font-medium">Title</th>
              </tr>
            </thead>
            <tbody>
              {papers
                .filter((p) => p.import_status !== "pending")
                .map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-gray-100 last:border-0"
                  >
                    <td className="px-4 py-2 max-w-[200px] truncate">
                      {p.filename}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          p.import_status === "parsed"
                            ? "bg-blue-100 text-blue-700"
                            : p.import_status === "skipped_ocr"
                              ? "bg-yellow-100 text-yellow-700"
                              : p.import_status === "vectorized"
                                ? "bg-green-100 text-green-700"
                                : "bg-red-100 text-red-700"
                        }`}
                      >
                        {p.import_status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500">
                      {p.page_count ?? "\u2014"}
                    </td>
                    <td className="px-4 py-2 text-gray-500">
                      {p.chunk_count ?? "\u2014"}
                    </td>
                    <td className="px-4 py-2 max-w-[300px] truncate text-gray-500">
                      {p.title ?? "\u2014"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
