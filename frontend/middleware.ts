// ─────────────────────────────────────────────────────────────────────────────
// middleware.ts — Protects clinic and admin routes
// Checks for tc_token cookie presence. JWT signature is verified by the gateway.
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"

const PUBLIC_PATHS = ["/login", "/register", "/api/auth", "/_next", "/favicon.ico"]

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Allow public paths
  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) return NextResponse.next()

  // Check for auth cookie
  const token = req.cookies.get("tc_token")?.value
  if (!token) {
    return NextResponse.redirect(new URL("/login", req.url))
  }

  // Decode JWT payload (no signature verification — gateway handles that)
  try {
    const parts = token.split(".")
    if (parts.length !== 3) throw new Error("invalid token")
    const payload = JSON.parse(atob(parts[1]))

    // Check expiry
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      const res = NextResponse.redirect(new URL("/login", req.url))
      res.cookies.delete("tc_token")
      return res
    }

    // Admin gate
    if (pathname.startsWith("/admin")) {
      const roles = (payload.roles as string[]) ?? []
      if (!roles.includes("admin")) {
        return NextResponse.redirect(new URL("/chat", req.url))
      }
    }

    return NextResponse.next()
  } catch {
    const res = NextResponse.redirect(new URL("/login", req.url))
    res.cookies.delete("tc_token")
    return res
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
