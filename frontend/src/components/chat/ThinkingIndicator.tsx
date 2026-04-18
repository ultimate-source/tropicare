// ─────────────────────────────────────────────────────────────────────────────
// components/chat/ThinkingIndicator.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

export function ThinkingIndicator({ lines }: { lines: string[] }) {
  return (
    <div className="rounded-lg border border-dashed border-blue-200 bg-blue-50/50 px-3 py-2">
      <div className="flex items-center gap-2 mb-1">
        <span className="flex gap-0.5">
          {[0, 1, 2].map(i => (
            <span key={i}
              className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </span>
        <span className="text-xs text-blue-600 font-medium">Analyse en cours</span>
      </div>
      {lines.slice(-2).map((l, i) => (
        <p key={i} className="text-xs text-blue-700/70 italic truncate">{l}</p>
      ))}
    </div>
  )
}
