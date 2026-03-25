import { useState, useCallback, useEffect } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { api, type Paper, type ImportResult } from "../api";

export function ImportPanel({ onComplete }: { onComplete?: () => void }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [importing, setImporting] = useState(false);
  const [lastResult, setLastResult] = useState<ImportResult | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const refreshPapers = useCallback(async () => {
    try {
      const [list, c] = await Promise.all([api.listPapers(), api.countPapers()]);
      setPapers(list);
      setCounts(c);
    } catch {
      // Backend may not be ready yet
    }
  }, []);

  useEffect(() => {
    refreshPapers();
  }, [refreshPapers]);

  const handleImport = useCallback(
    async (paths: string[]) => {
      if (paths.length === 0) return;
      setImporting(true);
      try {
        const result = await api.importPapers(paths);
        setLastResult(result);
        await refreshPapers();
      } catch (e) {
        setLastResult({
          imported: 0,
          skipped: 0,
          errors: [String(e)],
        });
      } finally {
        setImporting(false);
      }
    },
    [refreshPapers],
  );

  const handleSelectFiles = useCallback(async () => {
    const selected = await open({
      multiple: true,
      filters: [{ name: "PDF", extensions: ["pdf"] }],
      title: "Select PDF Papers",
    });

    if (!selected) return;

    // open() returns string | string[] | null
    const paths = Array.isArray(selected) ? selected : [selected];
    await handleImport(paths);
    onComplete?.();
  }, [handleImport, onComplete]);

  const handleDelete = useCallback(
    async (id: string) => {
      await api.deletePaper(id);
      await refreshPapers();
    },
    [refreshPapers],
  );

  const totalPapers = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Phase 1: Import Papers</h2>
        {totalPapers > 0 && (
          <span className="text-sm text-gray-500">
            {totalPapers} paper{totalPapers !== 1 ? "s" : ""} imported
          </span>
        )}
      </div>

      {/* Import form */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="mb-3 text-sm text-gray-600">
          Select PDF files to import into the library.
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleSelectFiles}
            disabled={importing}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {importing ? "Importing..." : "Select PDF Files"}
          </button>
          <button
            onClick={refreshPapers}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Import result */}
      {lastResult && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            lastResult.errors.length > 0
              ? "border-yellow-200 bg-yellow-50 text-yellow-800"
              : "border-green-200 bg-green-50 text-green-800"
          }`}
        >
          Imported: {lastResult.imported}, Skipped: {lastResult.skipped}
          {lastResult.errors.length > 0 && (
            <div className="mt-1">
              Errors: {lastResult.errors.join("; ")}
            </div>
          )}
        </div>
      )}

      {/* Status summary */}
      {totalPapers > 0 && (
        <div className="flex gap-4 text-sm">
          {Object.entries(counts).map(([status, count]) => (
            <span key={status} className="text-gray-500">
              <span className="font-medium text-gray-700">{count}</span>{" "}
              {status}
            </span>
          ))}
        </div>
      )}

      {/* Papers list */}
      {papers.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500">
                <th className="px-4 py-2 font-medium">Filename</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Pages</th>
                <th className="px-4 py-2 font-medium">Chunks</th>
                <th className="px-4 py-2 font-medium w-16"></th>
              </tr>
            </thead>
            <tbody>
              {papers.map((p) => (
                <tr key={p.id} className="border-b border-gray-100 last:border-0">
                  <td className="px-4 py-2 max-w-xs truncate" title={p.filepath ?? ""}>
                    {p.filename}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        p.import_status === "vectorized"
                          ? "bg-green-100 text-green-700"
                          : p.import_status === "parsed"
                            ? "bg-blue-100 text-blue-700"
                            : p.import_status === "error"
                              ? "bg-red-100 text-red-700"
                              : p.import_status === "skipped_ocr"
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-gray-100 text-gray-700"
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
                  <td className="px-4 py-2">
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="text-gray-400 hover:text-red-500"
                      title="Remove"
                    >
                      &times;
                    </button>
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
