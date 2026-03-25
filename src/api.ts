const API_BASE = "http://127.0.0.1:8765";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API error ${resp.status}: ${text}`);
  }
  return resp.json();
}

export interface Paper {
  id: string;
  filename: string;
  filepath: string | null;
  title: string | null;
  authors: string | null;
  year: number | null;
  import_status: string;
  page_count: number | null;
  chunk_count: number | null;
  imported_at: string | null;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  importPapers: (paths: string[]) =>
    request<ImportResult>("/papers/import", {
      method: "POST",
      body: JSON.stringify({ paths }),
    }),

  listPapers: (status?: string, limit = 100, offset = 0) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return request<Paper[]>(`/papers/?${params}`);
  },

  countPapers: () => request<Record<string, number>>("/papers/count"),

  deletePaper: (id: string) =>
    request<{ deleted: string }>(`/papers/${id}`, { method: "DELETE" }),

  parsePapers: () =>
    request<{ processed: number; skipped: number; errors: string[] }>(
      "/papers/parse",
      { method: "POST" },
    ),

  vectorizePapers: () =>
    request<{ vectorized: number; errors: string[] }>("/papers/vectorize", {
      method: "POST",
    }),
};
