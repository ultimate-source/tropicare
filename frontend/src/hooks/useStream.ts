// ─────────────────────────────────────────────────────────────────────────────
// hooks/useStream.ts
// HTTP chunked streaming via fetch() + ReadableStream.
// The server emits NDJSON: one JSON object per line, no SSE envelope.
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useCallback, useRef, useState } from "react"
import type { SSEEvent, DiagnosisItem, TreatmentPlanData, Citation, EmergencyFlag } from "@/lib/types"

export interface StreamState {
  thinking:     string[]
  emergencies:  EmergencyFlag[]
  differential: DiagnosisItem[]
  treatment:    Partial<TreatmentPlanData> & { first_line: any[]; second_line: any[]; alternatives: any[] }
  citations:    Citation[]
  annotations:  string[]
  turnId:       string | null
  isStreaming:  boolean
  error:        string | null
}

const empty = (): StreamState => ({
  thinking:     [],
  emergencies:  [],
  differential: [],
  treatment:    { first_line: [], second_line: [], alternatives: [] },
  citations:    [],
  annotations:  [],
  turnId:       null,
  isStreaming:  false,
  error:        null,
})

// ── NDJSON reader ─────────────────────────────────────────────────────────────
//
// Reads a fetch() ReadableStream and yields one parsed JSON object per
// newline-delimited record.  Handles chunks that arrive mid-line
// (the decoder buffer stitches them together before parsing).
//
async function* readNdjson(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const reader  = body.getReader()
  const decoder = new TextDecoder("utf-8")
  let   buf     = ""

  try {
    while (true) {
      // Respect abort signal — reader.read() is not directly cancellable
      // in older browsers, so we check manually after each read.
      const { value, done } = await reader.read()
      if (signal.aborted) return
      if (done) break

      buf += decoder.decode(value, { stream: true })

      // Consume every complete line in the buffer
      let nl: number
      while ((nl = buf.indexOf("\n")) !== -1) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) continue          // skip blank lines
        try {
          yield JSON.parse(line) as SSEEvent
        } catch {
          // malformed record — skip silently, keep streaming
        }
      }
    }
  } finally {
    // Always release the lock so the response body can be GC'd
    reader.releaseLock()
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useStream(sessionId: string) {
  const [state, setState] = useState<StreamState>(empty)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(async (query: string) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setState({ ...empty(), isStreaming: true })

    try {
      const res = await fetch(`/api/sessions/${sessionId}/turns`, {
        method:  "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept":        "application/x-ndjson",
        },
        body:   JSON.stringify({ query }),
        signal: ctrl.signal,
        // Prevent the browser from buffering the response
        // (required in some Chromium versions with compression)
        cache:  "no-store",
      })

      if (!res.ok || !res.body) {
        const msg = await res.text().catch(() => "Erreur réseau")
        setState(s => ({ ...s, error: msg, isStreaming: false }))
        return
      }

      for await (const event of readNdjson(res.body, ctrl.signal)) {
        if (ctrl.signal.aborted) break
        setState(s => applyEvent(s, event))
      }

    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return
      setState(s => ({ ...s, error: String(err), isStreaming: false }))
    }
  }, [sessionId])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setState(s => ({ ...s, isStreaming: false }))
  }, [])

  return { state, send, abort }
}

// ── Pure reducer — no setState inside ────────────────────────────────────────

function applyEvent(s: StreamState, ev: SSEEvent): StreamState {
  switch (ev.type) {
    case "thinking":
      return { ...s, thinking: [...s.thinking, ev.content] }

    case "emergency_flag":
      return { ...s, emergencies: [...s.emergencies, ev.flag] }

    case "differential_item":
      return {
        ...s,
        differential: [...s.differential.filter(d => d.rank !== ev.item.rank), ev.item]
                        .sort((a, b) => a.rank - b.rank),
      }

    case "treatment_line": {
      const tier = ev.tier as "first_line" | "second_line" | "alternatives"
      return {
        ...s,
        treatment: {
          ...s.treatment,
          [tier]: [...(s.treatment[tier as keyof typeof s.treatment] as any[] ?? []), ev.drug],
        },
      }
    }

    case "citation":
      return s.citations.some(c => c.ref_id === ev.citation.ref_id)
        ? s
        : { ...s, citations: [...s.citations, ev.citation] }

    case "validation":
      return { ...s, annotations: ev.annotations }

    case "error":
      return { ...s, error: ev.message, isStreaming: false }

    case "done":
      return { ...s, turnId: ev.turn_id, isStreaming: false }

    default:
      return s
  }
}
