// ─────────────────────────────────────────────────────────────────────────────
// app/api/auth/me/route.ts
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"
import { jwtVerify, importSPKI } from "jose"

export async function GET(req: NextRequest) {
  const token = req.cookies.get("tc_token")?.value
  if (!token) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 })

  try {
    const pubKeyPem = process.env.JWT_PUBLIC_KEY!.replace(/\\n/g, "\n")
    const pubKey    = await importSPKI(pubKeyPem, "RS256")
    const { payload } = await jwtVerify(token, pubKey)
    return NextResponse.json({ id: payload.sub, email: payload.email, roles: payload.roles })
  } catch {
    return NextResponse.json({ error: "Token invalide" }, { status: 401 })
  }
}
