// ─────────────────────────────────────────────────────────────────────────────
// app/api/feedback/route.ts
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function POST(req: NextRequest) {
  const token = req.cookies.get("tc_token")?.value
  const body  = await req.json()
  const r = await fetch(`${BACKEND}/api/v1/feedback`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  return NextResponse.json(await r.json(), { status: r.status })
}
