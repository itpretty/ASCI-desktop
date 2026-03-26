import { useState, useCallback, useEffect } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { readTextFile } from "@tauri-apps/plugin-fs";

const API = "http://127.0.0.1:8765";

interface Template {
  id: string;
  name: string;
  type: string;
  format: string;
  created_at: string;
}

interface ProgressEntry {
  type: string;
  paper?: string;
  error?: string;
  reason?: string;
  fields?: Record<string, unknown>;
  current?: number;
  total?: number;
  session_id?: string;
  completed?: number;
  errors?: number;
}

export function SearchPanel() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [aiStatus, setAiStatus] = useState<{
    available: boolean;
    error: string | null;
  } | null>(null);
  const [searching, setSearching] = useState(false);

  // Search config
  const [promptText, setPromptText] = useState("");

  // Progress
  const [progress, setProgress] = useState<ProgressEntry[]>([]);
  const [currentStatus, setCurrentStatus] = useState("");
  const [, setSessionId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [tRes, aiRes] = await Promise.all([
        fetch(`${API}/search/templates`).then((r) => r.json()),
        fetch(`${API}/search/ai-status`).then((r) => r.json()),
      ]);
      setTemplates(tRes);
      setAiStatus(aiRes);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleUploadImportReq = useCallback(async () => {
    const selected = await open({
      multiple: false,
      filters: [{ name: "Text", extensions: ["md", "txt"] }],
      title: "Select Import Requirements (.md or .txt)",
    });
    if (!selected) return;
    const path = Array.isArray(selected) ? selected[0] : selected;
    const content = await readTextFile(path);
    const name = path.split("/").pop() || "import-requirements";
    const resp = await fetch(`${API}/search/templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, type: "input", format: "markdown", content }),
    });
    await resp.json();
    await refresh();
  }, [refresh]);

  const handleUploadExportRes = useCallback(async () => {
    const selected = await open({
      multiple: false,
      title: "Select Export Results Template (any format)",
    });
    if (!selected) return;
    const path = Array.isArray(selected) ? selected[0] : selected;
    const content = await readTextFile(path);
    const name = path.split("/").pop() || "export-results";
    const ext = name.split(".").pop() || "txt";
    const resp = await fetch(`${API}/search/templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, type: "output", format: ext, content }),
    });
    await resp.json();
    await refresh();
  }, [refresh]);

  const handleDeleteTemplate = useCallback(
    async (id: string) => {
      await fetch(`${API}/search/templates/${id}`, { method: "DELETE" });
      await refresh();
    },
    [refresh],
  );

  const inputTemplates = templates.filter((t) => t.type === "input");
  const outputTemplates = templates.filter((t) => t.type === "output");

  const handleSearch = useCallback(async () => {
    if (inputTemplates.length === 0 && !promptText.trim()) return;
    setSearching(true);
    setProgress([]);
    setCurrentStatus("Starting search...");
    setSessionId(null);

    try {
      const resp = await fetch(`${API}/search/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_template_id: inputTemplates[0]?.id || null,
          output_template_id: outputTemplates[0]?.id || null,
          prompt_text: promptText || null,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        setProgress([{ type: "fatal", error: err.detail || "Search failed" }]);
        setCurrentStatus("");
        setSearching(false);
        return;
      }

      // Read SSE stream
      const reader = resp.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        setProgress([{ type: "fatal", error: "No response stream" }]);
        setSearching(false);
        return;
      }

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event: ProgressEntry = JSON.parse(line.slice(6));
            setProgress((prev) => [...prev, event]);

            if (event.type === "start") {
              setSessionId(event.session_id || null);
              setCurrentStatus(`Processing ${event.total} paper${event.total !== 1 ? "s" : ""}...`);
            } else if (event.type === "progress") {
              setCurrentStatus(
                `[${event.current}/${event.total}] Processing: ${event.paper}`,
              );
            } else if (event.type === "done") {
              setCurrentStatus(
                `Done. ${event.completed} processed, ${event.errors} error${event.errors !== 1 ? "s" : ""}.`,
              );
            } else if (event.type === "fatal") {
              setCurrentStatus("");
            }
          } catch {}
        }
      }
    } catch (e) {
      setProgress((prev) => [
        ...prev,
        { type: "fatal", error: String(e) },
      ]);
      setCurrentStatus("");
    } finally {
      setSearching(false);
    }
  }, [inputTemplates, outputTemplates, promptText]);

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-medium">Phase 4: Search &amp; Extract</h2>

      {/* Templates */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h3 className="text-sm font-medium text-gray-700">Templates</h3>

        <div className="grid grid-cols-2 gap-6">
          {/* Import Requirements column */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-xs text-gray-500">
                Import Requirements (.md / .txt)
              </label>
              <button
                onClick={handleUploadImportReq}
                className="rounded-md border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:bg-gray-50"
              >
                Select...
              </button>
            </div>
            {inputTemplates.length === 0 && (
              <p className="text-xs text-gray-400 py-2">No templates uploaded</p>
            )}
            {inputTemplates.map((t) => (
              <div
                key={t.id}
                className="flex justify-between items-center py-1 text-sm text-gray-500"
              >
                <span className="font-medium text-gray-700 truncate">
                  {t.name}
                </span>
                <button
                  onClick={() => handleDeleteTemplate(t.id)}
                  className="text-gray-400 hover:text-red-500 text-xs shrink-0 ml-2"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>

          {/* Export Results column */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-xs text-gray-500">
                Export Results (any format)
              </label>
              <button
                onClick={handleUploadExportRes}
                className="rounded-md border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:bg-gray-50"
              >
                Select...
              </button>
            </div>
            {outputTemplates.length === 0 && (
              <p className="text-xs text-gray-400 py-2">No templates uploaded</p>
            )}
            {outputTemplates.map((t) => (
              <div
                key={t.id}
                className="flex justify-between items-center py-1 text-sm text-gray-500"
              >
                <span className="font-medium text-gray-700 truncate">
                  {t.name}
                </span>
                <button
                  onClick={() => handleDeleteTemplate(t.id)}
                  className="text-gray-400 hover:text-red-500 text-xs shrink-0 ml-2"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Additional prompt + Run */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
        <label className="block text-sm font-medium text-gray-700">
          Additional Prompt
        </label>
        <textarea
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          rows={3}
          placeholder="Enter additional instructions or requirements..."
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          disabled={searching}
        />
        <button
          onClick={handleSearch}
          disabled={
            searching ||
            (inputTemplates.length === 0 && !promptText.trim()) ||
            (aiStatus !== null && !aiStatus.available)
          }
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {searching ? "Searching..." : "Run Search"}
        </button>
      </div>

      {/* Progress log */}
      {(progress.length > 0 || currentStatus) && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
          {currentStatus && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              {searching && (
                <div className="h-3 w-3 animate-spin rounded-full border border-gray-300 border-t-gray-600" />
              )}
              {currentStatus}
            </div>
          )}

          <div className="max-h-64 overflow-y-auto space-y-1 text-sm">
            {progress.map((entry, i) => (
              <div
                key={i}
                className={`py-1 ${
                  entry.type === "error" || entry.type === "fatal"
                    ? "text-red-600"
                    : entry.type === "result"
                      ? "text-green-700"
                      : entry.type === "skip"
                        ? "text-yellow-600"
                        : "text-gray-500"
                }`}
              >
                {entry.type === "result" && (
                  <span>
                    Extracted: <span className="font-medium">{entry.paper}</span>
                  </span>
                )}
                {entry.type === "error" && (
                  <span>
                    Error ({entry.paper}): {entry.error}
                  </span>
                )}
                {entry.type === "fatal" && (
                  <span className="font-medium">{entry.error}</span>
                )}
                {entry.type === "skip" && (
                  <span>
                    Skipped: {entry.paper} — {entry.reason}
                  </span>
                )}
                {entry.type === "done" && (
                  <span className="font-medium text-gray-700">
                    Search complete. Session: {entry.session_id}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
