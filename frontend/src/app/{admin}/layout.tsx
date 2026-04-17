// ─────────────────────────────────────────────────────────────────────────────
// app/(admin)/layout.tsx — admin shell
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

const ADMIN_NAV = [
  { href: "/admin/knowledge-base", label: "Base de connaissances", icon: "📚" },
  { href: "/admin/analytics",      label: "Analytiques",           icon: "📊" },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 border-r bg-white flex flex-col">
        <div className="px-4 py-4 border-b">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Admin</p>
          <Link href="/chat" className="text-xs text-blue-600 hover:underline">← Retour</Link>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {ADMIN_NAV.map(n => (
            <Link key={n.href} href={n.href}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
                pathname.startsWith(n.href)
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-100",
              )}>
              <span>{n.icon}</span>{n.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
