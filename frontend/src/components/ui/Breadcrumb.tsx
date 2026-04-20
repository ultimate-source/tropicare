// ─────────────────────────────────────────────────────────────────────────────
// components/ui/Breadcrumb.tsx — Accessible breadcrumb navigation
// Requirements: 19.1, 19.2, 19.3
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useTranslation } from "@/lib/i18n"

export interface BreadcrumbItem {
  label: string
  href?: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
}

/**
 * Renders an accessible breadcrumb navigation with aria-current on the last item.
 */
export function Breadcrumb({ items }: BreadcrumbProps) {
  const { t } = useTranslation()

  if (items.length === 0) return null

  return (
    <nav aria-label={t("breadcrumb.ariaLabel")}>
      <ol className="flex items-center gap-1 text-sm text-gray-500">
        {items.map((item, index) => {
          const isLast = index === items.length - 1

          return (
            <li key={index} className="flex items-center gap-1">
              {index > 0 && (
                <span aria-hidden="true" className="text-gray-300">
                  /
                </span>
              )}
              {isLast || !item.href ? (
                <span
                  aria-current={isLast ? "page" : undefined}
                  className={isLast ? "font-medium text-gray-900" : ""}
                >
                  {item.label}
                </span>
              ) : (
                <a
                  href={item.href}
                  className="hover:text-gray-700 hover:underline"
                >
                  {item.label}
                </a>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
