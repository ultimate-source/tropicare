// ─────────────────────────────────────────────────────────────────────────────
// lib/api.ts — typed client for the FastAPI backend
// All calls go through /api/* Next.js routes (which forward auth cookies).
// ─────────────────────────────────────────────────────────────────────────────
const BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

async function request<T>(
  path:    string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    credentials: "include",   // send httpOnly cookie
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const api = {
  auth: {
    login:  (email: string, password: string) =>
      request<{ access_token: string; user: { id: string; email: string; roles: string[] } }>(
        "/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }
      ),
    logout: () => request<void>("/api/auth/logout", { method: "POST" }),
    me:     () => request<{ id: string; email: string; roles: string[] }>("/api/auth/me"),
  },

  // ── Sessions ────────────────────────────────────────────────────────────────
  sessions: {
    create: (patientContext: Record<string, unknown> = {}, language = "fr") =>
      request<{ session_id: string }>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ patient_context: patientContext, language }),
      }),
    get:  (id: string) =>
      request<Record<string, unknown>>(`/api/sessions/${id}`),
    list: () =>
      request<{ sessions: SessionSummary[] }>("/api/sessions"),
  },

  // ── Feedback ─────────────────────────────────────────────────────────────────
  feedback: {
    submit: (body: {
      turn_id: string
      verdict: "correct" | "partial" | "incorrect"
      clinician_note?: string
      actual_diagnosis?: string
    }) => request<void>("/api/feedback", { method: "POST", body: JSON.stringify(body) }),
  },

  // ── Admin ─────────────────────────────────────────────────────────────────────
  admin: {
    listDocuments: () =>
      request<KBDocument[]>("/api/admin/documents"),
    uploadDocument: (formData: FormData) =>
      fetch(`${BASE}/api/admin/documents`, {
        method: "POST",
        body: formData,
        credentials: "include",
        // No Content-Type header — browser sets multipart boundary automatically
      }).then(r => r.json() as Promise<{ document_id: string; status: string }>),
    supersede: (docId: string, replacedById: string) =>
      request<void>(`/api/admin/documents/${docId}?reason_id=${replacedById}`, { method: "DELETE" }),
    analytics: () =>
      request<AnalyticsSummary>("/api/admin/analytics"),
  },
}

// ── Shared domain types ───────────────────────────────────────────────────────
export interface SessionSummary {
  id:         string
  created_at: string
  language:   string
  turn_count: number
  last_query: string
}

export interface KBDocument {
  id:           string
  title:        string
  source_type:  string
  version:      string
  published_date: string | null
  ingested_at:  string
  chunk_count:  number
  superseded:   boolean
}

export interface AnalyticsSummary {
  total_sessions:    number
  total_turns:       number
  top_diseases:      { disease: string; count: number }[]
  p95_latency_ms:    number
  citation_rate:     number
  feedback_correct:  number
  feedback_total:    number
}
