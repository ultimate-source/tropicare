// ─────────────────────────────────────────────────────────────────────────────
// app/(admin)/layout.tsx — admin shell
// Requirements: 19.1, 29.2, 30.8, 32.1
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { useAppStore } from "@/lib/store"
import { useTranslation } from "@/lib/i18n"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { SkipLink } from "@/components/ui/SkipLink"
import { Breadcrumb, type BreadcrumbItem } from "@/components/ui/Breadcrumb"

const ADMIN_NAV = [
  { href: "/admin/knowledge-base", labelKey: "admin.knowledgeBase", icon: "📚" },
  { href: "/admin/analytics",      labelKey: "admin.analytics",     icon: "📊" },
]

/** Route-to-label map for breadcrumb derivation */
const ROUTE_LABELS: Record<string, string> = {
  "/admin/knowledge-base": "admin.knowledgeBase",
  "/admin/analytics": "admin.analytics",
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { language, sidebarOpen, toggleSidebar } = useAppStore()
  const { t } = useTranslation()

  function closeSidebar() {
    if (sidebarOpen) toggleSidebar()
  }

  // Derive breadcrumb items from current pathname
  const breadcrumbItems: BreadcrumbItem[] = (() => {
    const labelKey = ROUTE_LABELS[pathname]
    if (labelKey) {
      return [{ label: t("admin.title") }, { label: t(labelKey) }]
    }
    // For sub-routes, try to match the base path
    for (const [route, key] of Object.entries(ROUTE_LABELS)) {
      if (pathname.startsWith(route)) {
        return [
          { label: t("admin.title") },
          { label: t(key), href: route },
          { label: pathname.split("/").pop() ?? "" },
        ]
      }
    }
    return [{ label: t("admin.title") }]
  })()

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
        <header className="px-4 py-4 border-b">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t("admin.title")}</p>
          <Link href="/chat" onClick={closeSidebar} aria-label={t("admin.backAriaLabel")} className="text-xs text-blue-600 hover:underline">
            {t("admin.back")}
          </Link>
        </header>

        <nav className="flex-1 p-3 space-y-1" aria-label={t("nav.adminNav")}>
          {ADMIN_NAV.map(n => (
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
        </nav>
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
