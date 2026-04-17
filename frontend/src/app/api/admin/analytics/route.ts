// ─────────────────────────────────────────────────────────────────────────────
// app/api/admin/analytics/route.ts
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function GET(req: NextRequest) {
  const token = req.cookies.get("tc_token")?.value
  const r = await fetch(`${BACKEND}/api/v1/admin/analytics`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  return NextResponse.json(await r.json(), { status: r.status })
}
