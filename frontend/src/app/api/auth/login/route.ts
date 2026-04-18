// ─────────────────────────────────────────────────────────────────────────────
// app/api/auth/login/route.ts — handles both JSON and form POST
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function POST(req: NextRequest) {
  let email: string
  let password: string
  const ct = req.headers.get("content-type") ?? ""
  const isJson = ct.includes("application/json")

  console.log("[login] content-type:", ct, "host:", req.headers.get("host"))

  if (isJson) {
    const body = await req.json()
    email = body.email
    password = body.password
  } else {
    // Native form POST — works with both urlencoded and multipart
    const form = await req.formData()
    email = form.get("email") as string
    password = form.get("password") as string
  }

  console.log("[login] email:", email, "isJson:", isJson)

  const upstream = await fetch(`${BACKEND}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })

  console.log("[login] upstream status:", upstream.status)

  const origin = `http://${req.headers.get("host") || "localhost:3000"}`

  if (!isJson) {
    if (!upstream.ok) {
      console.log("[login] redirect to error")
      return NextResponse.redirect(new URL("/login?error=1", origin))
    }
    const data = await upstream.json()
    console.log("[login] success, redirecting to /chat at", origin)
    const res = NextResponse.redirect(new URL("/chat", origin))
    res.cookies.set("tc_token", data.access_token, {
      httpOnly: true,
      secure: false,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 8,
    })
    res.cookies.set("tc_user", JSON.stringify(data.user), {
      httpOnly: false,
      secure: false,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 8,
    })
    return res
  }

  if (!upstream.ok) {
    return NextResponse.json({ error: "Identifiants invalides" }, { status: upstream.status })
  }
  const data = await upstream.json()
  const res = NextResponse.json({ access_token: data.access_token, user: data.user })
  res.cookies.set("tc_token", data.access_token, {
    httpOnly: true,
    secure: false,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  })
  return res
}
