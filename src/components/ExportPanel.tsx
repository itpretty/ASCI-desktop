import { useState, useCallback, useEffect } from "react";

const API = "http://127.0.0.1:8765";

interface Session {
  id: string;
  prompt_text: string | null;
  status: string;
  result_count: number;
}

export function ExportPanel() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState("");
  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(
    new Set(["xlsx"]),
  );
  const [exporting, setExporting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/results/sessions`)
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {});
  }, []);

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

        // Download the file
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const ext = fmt === "xlsx" ? "xlsx" : fmt === "pdf" ? "pdf" : "md";
        a.download = `asci_export.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        exported.push(fmt);
      } catch (e) {
        setStatus(`Error (${fmt}): ${e}`);
      }
    }

    if (exported.length > 0) {
      setStatus(`Exported: ${exported.join(", ")}`);
    }
    setExporting(false);
  }, [selectedSession, selectedFormats]);

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
            {sessions.map((s) => (
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
    </div>
  );
}
