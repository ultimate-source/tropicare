// ─────────────────────────────────────────────────────────────────────────────
// app/api/auth/logout/route.ts
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
  const ct = req.headers.get("content-type") ?? ""
  const origin = `http://${req.headers.get("host") || "localhost:3000"}`

  if (!ct.includes("application/json")) {
    // Form POST — redirect to login
    const res = NextResponse.redirect(new URL("/login", origin))
    res.cookies.delete("tc_token")
    res.cookies.delete("tc_user")
    return res
  }

  // JSON — return response
  const res = NextResponse.json({ ok: true })
  res.cookies.delete("tc_token")
  res.cookies.delete("tc_user")
  return res
}
