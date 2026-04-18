// ─────────────────────────────────────────────────────────────────────────────
// app/api/admin/documents/route.ts  — list + upload
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function GET(req: NextRequest) {
  const token = req.cookies.get("tc_token")?.value
  const r = await fetch(`${BACKEND}/api/v1/admin/documents`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  return NextResponse.json(await r.json(), { status: r.status })
}

export async function POST(req: NextRequest) {
  const token    = req.cookies.get("tc_token")?.value
  const formData = await req.formData()
  const r = await fetch(`${BACKEND}/api/v1/admin/documents`, {
    method:  "POST",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body:    formData,   // pass multipart form straight through
  })
  return NextResponse.json(await r.json(), { status: r.status })
}

