// ─────────────────────────────────────────────────────────────────────────────
// middleware.ts  (root of the Next.js app)
// Protects all (clinic) and (admin) routes.
// Reads the JWT from the httpOnly cookie and redirects to /login if absent.
// ─────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from "next/server"
import { jwtVerify, importSPKI } from "jose"

const PUBLIC_PATHS = ["/login", "/api/auth"]
const ADMIN_PATHS  = ["/admin"]

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) return NextResponse.next()

  const token = req.cookies.get("tc_token")?.value
  if (!token) return NextResponse.redirect(new URL("/login", req.url))

  try {
    const pubKeyPem = process.env.JWT_PUBLIC_KEY!.replace(/\\n/g, "\n")
    const pubKey    = await importSPKI(pubKeyPem, "RS256")
    const { payload } = await jwtVerify(token, pubKey)

    // Admin gate
    if (ADMIN_PATHS.some(p => pathname.startsWith(p))) {
      const roles = (payload.roles as string[]) ?? []
      if (!roles.includes("admin")) {
        return NextResponse.redirect(new URL("/chat", req.url))
      }
    }

    // Forward user info to API routes via header
    const res = NextResponse.next()
    res.headers.set("x-user-id",    String(payload.sub ?? ""))
    res.headers.set("x-user-roles", JSON.stringify(payload.roles ?? []))
    return res

  } catch {
    const res = NextResponse.redirect(new URL("/login", req.url))
    res.cookies.delete("tc_token")
    return res
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}



