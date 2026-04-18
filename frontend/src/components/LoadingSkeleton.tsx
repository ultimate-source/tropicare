// ─────────────────────────────────────────────────────────────────────────────
// components/LoadingSkeleton.tsx — reusable loading indicators
// ─────────────────────────────────────────────────────────────────────────────
"use client"

/** Simple inline spinner */
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent text-blue-600 ${className}`}
      role="status"
      aria-label="Chargement en cours"
    >
      <span className="sr-only">Chargement…</span>
    </div>
  )
}

/** Skeleton lines for content areas */
export function SkeletonLines({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3 animate-pulse" role="status" aria-label="Chargement du contenu">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-3 rounded bg-gray-200" style={{ width: `${85 - i * 10}%` }} />
      ))}
      <span className="sr-only">Chargement…</span>
    </div>
  )
}

/** Skeleton cards for card-based layouts */
export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border bg-white p-4 space-y-3" role="status" aria-label="Chargement de la carte">
      <div className="h-4 w-2/3 rounded bg-gray-200" />
      <div className="h-3 w-1/2 rounded bg-gray-200" />
      <div className="h-3 w-3/4 rounded bg-gray-200" />
      <span className="sr-only">Chargement…</span>
    </div>
  )
}

/** Skeleton table rows */
export function SkeletonTableRows({ cols = 6, rows = 3 }: { cols?: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} className="animate-pulse">
          {Array.from({ length: cols }).map((_, c) => (
            <td key={c} className="px-4 py-3">
              <div className="h-3 rounded bg-gray-200" style={{ width: `${60 + (c % 3) * 15}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
