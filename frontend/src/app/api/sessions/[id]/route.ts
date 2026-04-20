// ─────────────────────────────────────────────────────────────────────────────
// app/api/sessions/[id]/route.ts  — proxy session detail to gateway
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

function authHeader(req: NextRequest): Record<string, string> {
  const token = req.cookies.get("tc_token")?.value
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const r = await fetch(`${BACKEND}/api/v1/sessions/${id}`, {
    headers: { ...authHeader(req) },
  })
  return NextResponse.json(await r.json(), { status: r.status })
}
