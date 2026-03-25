import { useState, useCallback, useEffect } from "react";

const API = "http://127.0.0.1:8765";

interface Template {
  id: string;
  name: string;
  type: string;
  format: string;
  created_at: string;
}

interface SearchResult {
  doc_id: string;
  doc_title: string;
  fields: Record<string, unknown>;
  citations: Record<string, unknown>;
}

export function SearchPanel() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [aiAvailable, setAiAvailable] = useState<boolean | null>(null);
  const [searching, setSearching] = useState(false);

  // Template upload
  const [templateName, setTemplateName] = useState("");
  const [templateType, setTemplateType] = useState<"input" | "output">("input");
  const [templateContent, setTemplateContent] = useState("");

  // Search config
  const [selectedInput, setSelectedInput] = useState("");
  const [selectedOutput, setSelectedOutput] = useState("");
  const [promptText, setPromptText] = useState("");

  // Results
  const [results, setResults] = useState<SearchResult[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [tRes, aiRes] = await Promise.all([
        fetch(`${API}/search/templates`).then((r) => r.json()),
        fetch(`${API}/search/ai-status`).then((r) => r.json()),
      ]);
      setTemplates(tRes);
      setAiAvailable(aiRes.available);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleUploadTemplate = useCallback(async () => {
    if (!templateName.trim() || !templateContent.trim()) return;
    await fetch(`${API}/search/templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: templateName,
        type: templateType,
        format: "markdown",
        content: templateContent,
      }),
    });
    setTemplateName("");
    setTemplateContent("");
    await refresh();
  }, [templateName, templateType, templateContent, refresh]);

  const handleSearch = useCallback(async () => {
    if (!selectedInput && !promptText.trim()) return;
    setSearching(true);
    setResults([]);
    setErrors([]);
    try {
      const resp = await fetch(`${API}/search/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_template_id: selectedInput || null,
          output_template_id: selectedOutput || null,
          prompt_text: promptText || null,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setErrors([data.detail || "Search failed"]);
      } else {
        setSessionId(data.session_id);
        setResults(data.results);
        setErrors(data.errors);
      }
    } catch (e) {
      setErrors([String(e)]);
    } finally {
      setSearching(false);
    }
  }, [selectedInput, selectedOutput, promptText]);

  const inputTemplates = templates.filter((t) => t.type === "input");
  const outputTemplates = templates.filter((t) => t.type === "output");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Phase 4: Search &amp; Extract</h2>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              aiAvailable === true
                ? "bg-green-500"
                : aiAvailable === false
                  ? "bg-red-500"
                  : "bg-gray-300"
            }`}
          />
          <span className="text-gray-500">
            {aiAvailable === true
              ? "Claude CLI available"
              : aiAvailable === false
                ? "Claude CLI not found"
                : "Checking..."}
          </span>
        </div>
      </div>

      {/* Template upload */}
      <details className="rounded-lg border border-gray-200 bg-white">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-gray-700">
          Upload Template ({templates.length} uploaded)
        </summary>
        <div className="border-t border-gray-200 p-4 space-y-3">
          <div className="flex gap-3">
            <input
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
              placeholder="Template name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
            />
            <select
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={templateType}
              onChange={(e) => setTemplateType(e.target.value as "input" | "output")}
            >
              <option value="input">Input</option>
              <option value="output">Output</option>
            </select>
          </div>
          <textarea
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            rows={6}
            placeholder="Paste template content (markdown)..."
            value={templateContent}
            onChange={(e) => setTemplateContent(e.target.value)}
          />
          <button
            onClick={handleUploadTemplate}
            disabled={!templateName.trim() || !templateContent.trim()}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Upload
          </button>

          {templates.length > 0 && (
            <div className="mt-3 text-sm text-gray-500">
              {templates.map((t) => (
                <div key={t.id} className="flex justify-between py-1">
                  <span>
                    <span className="font-medium text-gray-700">{t.name}</span>{" "}
                    <span className="text-xs">({t.type})</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </details>

      {/* Search configuration */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h3 className="text-sm font-medium text-gray-700">Search Configuration</h3>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs text-gray-500">
              Input Template
            </label>
            <select
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={selectedInput}
              onChange={(e) => setSelectedInput(e.target.value)}
            >
              <option value="">None</option>
              {inputTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">
              Output Template
            </label>
            <select
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={selectedOutput}
              onChange={(e) => setSelectedOutput(e.target.value)}
            >
              <option value="">None</option>
              {outputTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-gray-500">
            Additional Prompt
          </label>
          <textarea
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            rows={3}
            placeholder="Enter additional instructions or requirements..."
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
          />
        </div>

        <button
          onClick={handleSearch}
          disabled={
            searching || (!selectedInput && !promptText.trim()) || !aiAvailable
          }
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {searching ? "Searching..." : "Run Search"}
        </button>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {errors.map((e, i) => (
            <div key={i}>{e}</div>
          ))}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-700">
            Results ({results.length} papers) — Session: {sessionId}
          </h3>
          {results.map((r) => (
            <div
              key={r.doc_id}
              className="rounded-lg border border-gray-200 bg-white p-4"
            >
              <h4 className="mb-2 text-sm font-medium">{r.doc_title}</h4>
              <div className="text-sm text-gray-600">
                <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-xs">
                  {JSON.stringify(r.fields, null, 2)}
                </pre>
                {Object.keys(r.citations).length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-gray-400">
                      Citations
                    </summary>
                    <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-3 text-xs">
                      {JSON.stringify(r.citations, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
