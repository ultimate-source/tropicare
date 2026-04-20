// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/layout.tsx — shared clinic shell (nav + sidebar)
// Requirements: 18.1–18.5, 19.1–19.2, 20.1–20.2, 29.1, 32.1, 32.3
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { useTranslation } from "@/lib/i18n"
import { cn } from "@/lib/utils"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { SkipLink } from "@/components/ui/SkipLink"
import { Breadcrumb, type BreadcrumbItem } from "@/components/ui/Breadcrumb"

const NAV = [
  { href: "/chat",     labelKey: "nav.consultation", icon: "💬" },
  { href: "/sessions", labelKey: "nav.history",      icon: "📋" },
]

/** Route-to-label map for breadcrumb derivation */
const ROUTE_LABELS: Record<string, string> = {
  "/chat": "nav.consultation",
  "/sessions": "nav.history",
}

export default function ClinicLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router   = useRouter()
  const { user, clearUser, language, setLanguage, sidebarOpen, toggleSidebar } = useAppStore()
  const { t } = useTranslation()

  async function logout() {
    await api.auth.logout()
    clearUser()
    router.push("/login")
  }

  function closeSidebar() {
    if (sidebarOpen) toggleSidebar()
  }

  // Derive breadcrumb items from current pathname
  const breadcrumbItems: BreadcrumbItem[] = (() => {
    const labelKey = ROUTE_LABELS[pathname]
    if (labelKey) {
      return [{ label: t(labelKey) }]
    }
    // For sub-routes, try to match the base path
    const basePath = "/" + (pathname.split("/")[1] ?? "")
    const baseKey = ROUTE_LABELS[basePath]
    if (baseKey) {
      return [{ label: t(baseKey), href: basePath }, { label: pathname.split("/").pop() ?? "" }]
    }
    return []
  })()

  const isAdmin = user?.roles?.includes("admin")

  return (
    <div className="flex h-screen bg-gray-50">
      <SkipLink />

      {/* Hamburger button — visible below md */}
      <button
        type="button"
        className="fixed top-3 left-3 z-50 md:hidden rounded-md p-2 text-gray-700 hover:bg-gray-100"
        aria-label={t("nav.openMenu")}
        aria-expanded={sidebarOpen}
        onClick={toggleSidebar}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Backdrop — visible below md when sidebar open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-56 flex-col border-r bg-white transition-transform duration-300 ease-in-out md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <header className="flex items-center gap-2 px-4 py-4 border-b">
          <span className="text-xl">🌿</span>
          <span className="font-semibold text-gray-900 text-sm">{t("nav.brand")}</span>
        </header>

        <nav className="flex-1 p-3 space-y-1" aria-label={t("nav.mainNav")}>
          {NAV.map(n => (
            <Link
              key={n.href}
              href={n.href}
              onClick={closeSidebar}
              aria-label={t(n.labelKey)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                pathname.startsWith(n.href)
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-100",
              )}
            >
              <span>{n.icon}</span>{t(n.labelKey)}
            </Link>
          ))}

          {/* Admin link — only for admin role */}
          {isAdmin && (
            <Link
              href="/admin/knowledge-base"
              onClick={closeSidebar}
              aria-label={t("nav.admin")}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <span>⚙️</span>{t("nav.admin")}
            </Link>
          )}
        </nav>

        <div className="border-t p-3 space-y-2">
          {/* Language toggle */}
          <div className="flex gap-1">
            {(["fr", "en"] as const).map(l => (
              <button key={l}
                onClick={() => setLanguage(l)}
                aria-label={l === "fr" ? t("nav.langFr") : t("nav.langEn")}
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
            <button
              type="button"
              onClick={logout}
              aria-label={t("nav.logout")}
              className="text-xs text-gray-400 hover:text-red-500 ml-2"
            >
              {t("nav.logout")} ⎋
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main id="main-content" className="flex-1 overflow-hidden flex flex-col">
        {/* Breadcrumb */}
        <div className="px-4 pb-1 pt-12 md:pt-3">
          <Breadcrumb items={breadcrumbItems} />
        </div>
        <div className="flex-1 overflow-hidden">
          <ErrorBoundary language={language}>{children}</ErrorBoundary>
        </div>
      </main>
    </div>
  )
}
