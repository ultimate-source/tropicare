// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/layout.tsx — shared clinic shell (nav + sidebar)
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/chat",     label: "Consultation",  icon: "💬" },
  { href: "/sessions", label: "Historique",    icon: "📋" },
]

export default function ClinicLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router   = useRouter()
  const { user, clearUser, language, setLanguage } = useAppStore()

  async function logout() {
    await api.auth.logout()
    clearUser()
    router.push("/login")
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r bg-white">
        <div className="flex items-center gap-2 px-4 py-4 border-b">
          <span className="text-xl">🌿</span>
          <span className="font-semibold text-gray-900 text-sm">TropiCare</span>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(n => (
            <Link
              key={n.href} href={n.href}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                pathname.startsWith(n.href)
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-100",
              )}
            >
              <span>{n.icon}</span>{n.label}
            </Link>
          ))}
        </nav>

        <div className="border-t p-3 space-y-2">
          {/* Language toggle */}
          <div className="flex gap-1">
            {(["fr", "en"] as const).map(l => (
              <button key={l}
                onClick={() => setLanguage(l)}
                className={cn(
                  "flex-1 rounded py-1 text-xs font-medium",
                  language === l ? "bg-blue-100 text-blue-700" : "text-gray-500 hover:bg-gray-100",
                )}>
                {l.toUpperCase()}
              </button>
            ))}
          </div>
          {/* User + logout */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500 truncate">{user?.email ?? "—"}</p>
            <button onClick={logout} className="text-xs text-gray-400 hover:text-red-500 ml-2">
              ⎋
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
