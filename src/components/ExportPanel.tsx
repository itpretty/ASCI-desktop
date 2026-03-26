import { useState, useCallback, useEffect } from "react";
import { save } from "@tauri-apps/plugin-dialog";
import { writeFile } from "@tauri-apps/plugin-fs";

const API = "http://127.0.0.1:8765";

interface Session {
  id: string;
  prompt_text: string | null;
  status: string;
  result_count: number;
}

interface ExportFile {
  filename: string;
  path: string;
  size: number;
  format: string;
  session_id?: string;
}

export function ExportPanel() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState("");
  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(
    new Set(["xlsx"]),
  );
  const [exporting, setExporting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [exportFiles, setExportFiles] = useState<ExportFile[]>([]);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await fetch(`${API}/results/sessions`).then((r) => r.json());
      setSessions(data);
    } catch {}
  }, []);

  const refreshFiles = useCallback(
    async (sessionId?: string) => {
      try {
        const params = sessionId ? `?session_id=${sessionId}` : "";
        const data = await fetch(`${API}/export/files${params}`).then((r) =>
          r.json(),
        );
        setExportFiles(data);
      } catch {}
    },
    [],
  );

  useEffect(() => {
    refreshSessions();
    refreshFiles();
  }, [refreshSessions, refreshFiles]);

  // Refresh files and clear status when session changes
  useEffect(() => {
    setStatus(null);
    refreshFiles(selectedSession || undefined);
  }, [selectedSession, refreshFiles]);

  const toggleFormat = useCallback((fmt: string) => {
    setSelectedFormats((prev) => {
      const next = new Set(prev);
      if (next.has(fmt)) {
        next.delete(fmt);
      } else {
        next.add(fmt);
      }
      return next;
    });
  }, []);

  const handleExport = useCallback(async () => {
    if (selectedFormats.size === 0) return;
    setExporting(true);
    setStatus(null);

    const exported: string[] = [];

    for (const fmt of selectedFormats) {
      try {
        const resp = await fetch(`${API}/export/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: selectedSession || null,
            format: fmt,
          }),
        });

        if (!resp.ok) {
          const err = await resp.json();
          setStatus(`Error (${fmt}): ${err.detail}`);
          continue;
        }

        const data = await resp.json();
        exported.push(data.filename);
      } catch (e) {
        setStatus(`Error (${fmt}): ${e}`);
      }
    }

    if (exported.length > 0) {
      setStatus(`Exported: ${exported.join(", ")}`);
    }
    setExporting(false);
    refreshFiles(selectedSession || undefined);
  }, [selectedSession, selectedFormats, refreshFiles]);

  const handleDownload = useCallback(async (filename: string) => {
    const ext = filename.split(".").pop() || "";
    const filters: Record<string, { name: string; extensions: string[] }> = {
      xlsx: { name: "Excel", extensions: ["xlsx"] },
      pdf: { name: "PDF", extensions: ["pdf"] },
      md: { name: "Markdown", extensions: ["md"] },
    };

    const dest = await save({
      defaultPath: filename,
      filters: filters[ext] ? [filters[ext]] : undefined,
      title: "Save exported file",
    });

    if (!dest) return;

    // Fetch file content from backend and write to chosen path
    const resp = await fetch(
      `${API}/export/download/${encodeURIComponent(filename)}`,
    );
    const blob = await resp.blob();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    await writeFile(dest, bytes);
  }, []);

  const handleDelete = useCallback(
    async (filename: string) => {
      await fetch(`${API}/export/files/${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      refreshFiles(selectedSession || undefined);
    },
    [selectedSession, refreshFiles],
  );

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const FORMATS = [
    { id: "xlsx", label: ".xlsx", desc: "Excel spreadsheet" },
    { id: "pdf", label: ".pdf", desc: "PDF document" },
    { id: "md", label: ".md", desc: "Markdown table" },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-medium">Phase 6: Export</h2>

      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        {/* Session selector */}
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Session to export
          </label>
          <select
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={selectedSession}
            onChange={(e) => setSelectedSession(e.target.value)}
          >
            <option value="">All results</option>
            {sessions
              .filter((s) => s.result_count > 0)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} — {s.prompt_text?.slice(0, 40) || "Template search"} (
                  {s.result_count} results)
                </option>
              ))}
          </select>
        </div>

        {/* Format selection */}
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Export formats
          </label>
          <div className="flex flex-col gap-2">
            {FORMATS.map((fmt) => (
              <label
                key={fmt.id}
                className="flex cursor-pointer items-center gap-2 text-sm text-gray-700"
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900"
                  checked={selectedFormats.has(fmt.id)}
                  onChange={() => toggleFormat(fmt.id)}
                />
                <span className="font-medium">{fmt.label}</span>
                <span className="text-gray-400">{fmt.desc}</span>
              </label>
            ))}
          </div>
        </div>

        <button
          onClick={handleExport}
          disabled={exporting || selectedFormats.size === 0}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {exporting ? "Exporting..." : "Export"}
        </button>
      </div>

      {status && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            status.startsWith("Error")
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-green-200 bg-green-50 text-green-700"
          }`}
        >
          {status}
        </div>
      )}

      {/* Exported files list */}
      {exportFiles.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-sm font-medium text-gray-700">Exported Files</h3>
          </div>
          <div className="divide-y divide-gray-100">
            {exportFiles.map((f) => (
              <div
                key={f.filename}
                className="flex items-center justify-between px-4 py-2 text-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600 uppercase">
                    {f.format}
                  </span>
                  <span className="truncate text-gray-700" title={f.filename}>
                    {f.filename}
                  </span>
                  <span className="text-gray-400 text-xs shrink-0">
                    {formatSize(f.size)}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-2">
                  <button
                    onClick={() => handleDownload(f.filename)}
                    className="text-blue-600 hover:text-blue-800 text-xs"
                  >
                    Download
                  </button>
                  <button
                    onClick={() => handleDelete(f.filename)}
                    className="text-gray-400 hover:text-red-500 text-xs"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
