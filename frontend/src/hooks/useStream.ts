// ─────────────────────────────────────────────────────────────────────────────
// hooks/useStream.ts
// HTTP chunked streaming via fetch() + ReadableStream.
// The server emits NDJSON: one JSON object per line, no SSE envelope.
//
// Accumulates conversation history as Turn[] so previous results remain
// visible when the clinician asks follow-up questions.
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useCallback, useRef, useState } from "react"
import type { SSEEvent, DiagnosisItem, TreatmentPlanData, Citation, EmergencyFlag, DrugRegimen } from "@/lib/types"

// ── Turn — a single completed or in-progress query/response cycle ────────────

export interface Turn {
  query:        string
  thinking:     string[]
  emergencies:  EmergencyFlag[]
  differential: DiagnosisItem[]
  treatment:    Partial<TreatmentPlanData> & {
    first_line:   DrugRegimen[]
    second_line:  DrugRegimen[]
    alternatives: DrugRegimen[]
  }
  citations:    Citation[]
  annotations:  string[]
  turnId:       string | null
  error:        string | null
}

export interface StreamState {
  turns:        Turn[]        // accumulated completed turns
  currentTurn:  Turn          // in-progress turn
  isStreaming:  boolean
  lastQuery:    string | null // stored for retry on error
}

export const emptyTurn = (): Turn => ({
  query:        "",
  thinking:     [],
  emergencies:  [],
  differential: [],
  treatment:    { first_line: [], second_line: [], alternatives: [] },
  citations:    [],
  annotations:  [],
  turnId:       null,
  error:        null,
})

const emptyState = (): StreamState => ({
  turns:       [],
  currentTurn: emptyTurn(),
  isStreaming:  false,
  lastQuery:   null,
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
      const { value, done } = await reader.read()
      if (signal.aborted) return
      if (done) break

      buf += decoder.decode(value, { stream: true })

      let nl: number
      while ((nl = buf.indexOf("\n")) !== -1) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) continue
        try {
          yield JSON.parse(line) as SSEEvent
        } catch {
          // malformed record — skip silently, keep streaming
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useStream(sessionId: string) {
  const [state, setState] = useState<StreamState>(emptyState)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(async (query: string) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    // Push any non-empty currentTurn into history, then start fresh
    setState(prev => {
      const newTurns = hasTurnContent(prev.currentTurn)
        ? [...prev.turns, prev.currentTurn]
        : prev.turns
      return {
        turns:       newTurns,
        currentTurn: { ...emptyTurn(), query },
        isStreaming:  true,
        lastQuery:   query,
      }
    })

    try {
      const res = await fetch(`/api/sessions/${sessionId}/turns`, {
        method:  "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept":        "application/x-ndjson",
        },
        body:   JSON.stringify({ query }),
        signal: ctrl.signal,
        cache:  "no-store",
      })

      if (!res.ok || !res.body) {
        const msg = await res.text().catch(() => "Erreur réseau")
        setState(s => ({
          ...s,
          currentTurn: { ...s.currentTurn, error: msg },
          isStreaming: false,
        }))
        return
      }

      for await (const event of readNdjson(res.body, ctrl.signal)) {
        if (ctrl.signal.aborted) break
        setState(s => ({
          ...s,
          currentTurn: applyEvent(s.currentTurn, event),
          // "done" and "error" events stop streaming
          isStreaming: event.type === "done" || event.type === "error"
            ? false
            : s.isStreaming,
        }))
      }

    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return
      setState(s => ({
        ...s,
        currentTurn: { ...s.currentTurn, error: String(err) },
        isStreaming: false,
      }))
    }
  }, [sessionId])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setState(s => ({ ...s, isStreaming: false }))
  }, [])

  const retry = useCallback(() => {
    if (state.lastQuery) {
      send(state.lastQuery)
    }
  }, [state.lastQuery, send])

  return { state, send, abort, retry }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Returns true if a turn has any meaningful content (not just an empty shell). */
function hasTurnContent(turn: Turn): boolean {
  return (
    turn.thinking.length > 0 ||
    turn.differential.length > 0 ||
    turn.emergencies.length > 0 ||
    turn.citations.length > 0 ||
    turn.annotations.length > 0 ||
    turn.treatment.first_line.length > 0 ||
    turn.treatment.second_line.length > 0 ||
    turn.treatment.alternatives.length > 0 ||
    turn.turnId !== null ||
    turn.error !== null
  )
}

// ── Pure reducer — applies a single NDJSON event to a Turn ───────────────────

export function applyEvent(turn: Turn, ev: SSEEvent): Turn {
  switch (ev.type) {
    case "thinking":
      return { ...turn, thinking: [...turn.thinking, ev.content] }

    case "emergency_flag":
      return { ...turn, emergencies: [...turn.emergencies, ev.flag] }

    case "differential_item":
      return {
        ...turn,
        differential: [...turn.differential.filter(d => d.rank !== ev.item.rank), ev.item]
                        .sort((a, b) => a.rank - b.rank),
      }

    case "treatment_line": {
      const tier = ev.tier as "first_line" | "second_line" | "alternatives"
      return {
        ...turn,
        treatment: {
          ...turn.treatment,
          [tier]: [...(turn.treatment[tier] ?? []), ev.drug],
        },
      }
    }

    case "citation":
      return turn.citations.some(c => c.ref_id === ev.citation.ref_id)
        ? turn
        : { ...turn, citations: [...turn.citations, ev.citation] }

    case "validation":
      return { ...turn, annotations: ev.annotations }

    case "error":
      return { ...turn, error: ev.message }

    case "done":
      return { ...turn, turnId: ev.turn_id }

    default:
      return turn
  }
}
