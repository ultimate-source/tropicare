// ─────────────────────────────────────────────────────────────────────────────
// app/api/sessions/route.ts  — create session + list sessions
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

function authHeader(req: NextRequest): Record<string, string> {
  const token = req.cookies.get("tc_token")?.value
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function GET(req: NextRequest) {
  const r = await fetch(`${BACKEND}/api/v1/sessions`, {
    headers: { ...authHeader(req) },
  })
  return NextResponse.json(await r.json(), { status: r.status })
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const r = await fetch(`${BACKEND}/api/v1/sessions`, {
    method:  "POST",
    headers: { "Content-Type": "application/json", ...authHeader(req) },
    body:    JSON.stringify(body),
  })
  return NextResponse.json(await r.json(), { status: r.status })
}
