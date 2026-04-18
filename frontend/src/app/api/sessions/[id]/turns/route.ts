// ─────────────────────────────────────────────────────────────────────────────
// app/api/sessions/[id]/turns/route.ts  — streaming proxy (NDJSON passthrough)
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function POST(
  req:     NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const token = req.cookies.get("tc_token")?.value
  const body  = await req.json()
  const { id } = await params

  const upstream = await fetch(
    `${BACKEND}/api/v1/sessions/${id}/turns`,
    {
      method:  "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept":        "application/x-ndjson",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body:    JSON.stringify(body),
      // Tell Node not to buffer — pass the readable stream straight through
      // @ts-expect-error — Node 18+ fetch supports duplex
      duplex: "half",
    }
  )

  // Pipe the upstream NDJSON body straight to the browser —
  // no buffering, no re-encoding, zero latency overhead.
  return new Response(upstream.body, {
    status:  upstream.status,
    headers: {
      "Content-Type":     "application/x-ndjson",
      "Transfer-Encoding":"chunked",
      "Cache-Control":    "no-cache, no-store",
      "X-Accel-Buffering":"no",
    },
  })
}
