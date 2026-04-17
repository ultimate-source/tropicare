// ─────────────────────────────────────────────────────────────────────────────
// app/api/auth/login/route.ts
// Proxies login to FastAPI, sets httpOnly cookie on success.
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function POST(req: NextRequest) {
  const body = await req.json()
  const upstream = await fetch(`${BACKEND}/api/v1/auth/login`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  })

  if (!upstream.ok) {
    return NextResponse.json(
      { error: "Identifiants invalides" },
      { status: upstream.status }
    )
  }

  const data = await upstream.json()
  const res  = NextResponse.json({ user: data.user })

  // Set httpOnly cookie — JS cannot read it, mitigates XSS token theft
  res.cookies.set({
    name:     "tc_token",
    value:    data.access_token,
    httpOnly: true,
    secure:   process.env.NODE_ENV === "production",
    sameSite: "lax",
    path:     "/",
    maxAge:   60 * 60 * 8,  // 8 hours
  })
  return res
}
