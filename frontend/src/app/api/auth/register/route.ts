// ─────────────────────────────────────────────────────────────────────────────
// app/api/auth/register/route.ts — Proxies registration to the gateway
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.BACKEND_URL ?? "http://gateway:8000"

export async function POST(req: NextRequest) {
  const ct = req.headers.get("content-type") ?? ""
  let email: string, password: string, role: string

  if (ct.includes("application/json")) {
    const body = await req.json()
    email = body.email
    password = body.password
    role = body.role || "clinician"
  } else {
    const form = await req.formData()
    email = form.get("email") as string
    password = form.get("password") as string
    role = (form.get("role") as string) || "clinician"
  }

  const upstream = await fetch(`${BACKEND}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, role }),
  })

  const origin = `http://${req.headers.get("host") || "localhost:3000"}`

  if (!ct.includes("application/json")) {
    if (!upstream.ok) {
      const err = await upstream.text().catch(() => "")
      const msg = upstream.status === 409
        ? "Cette adresse e-mail est déjà utilisée."
        : upstream.status === 422
        ? "Mot de passe trop faible (min. 10 car., 1 majuscule, 1 minuscule, 1 chiffre)."
        : "Erreur lors de l'inscription."
      return NextResponse.redirect(new URL(`/register?error=1&msg=${encodeURIComponent(msg)}`, origin))
    }
    // Registration successful — redirect to login
    return NextResponse.redirect(new URL("/login", origin))
  }

  if (!upstream.ok) {
    const err = await upstream.json().catch(() => ({ detail: "Registration failed" }))
    return NextResponse.json(err, { status: upstream.status })
  }
  return NextResponse.json(await upstream.json(), { status: 201 })
}
