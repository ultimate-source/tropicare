// ─────────────────────────────────────────────────────────────────────────────
// components/chat/ThinkingIndicator.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useRef, useState } from "react"
import { useAutoScroll } from "@/hooks/useAutoScroll"
import { useTranslation } from "@/lib/i18n"

export function ThinkingIndicator({ lines }: { lines: string[] }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useAutoScroll(scrollRef, [lines])

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
        <span className="text-xs text-blue-600 font-medium">{t("chat.thinking")}</span>
        {lines.length > 0 && (
          <button
            type="button"
            onClick={() => setExpanded(prev => !prev)}
            className="ml-auto text-xs text-blue-500 hover:text-blue-700 underline"
            aria-expanded={expanded}
          >
            {expanded ? t("chat.thinkingCollapse") : t("chat.thinkingExpand")}
          </button>
        )}
      </div>
      <div
        ref={scrollRef}
        className={expanded ? "overflow-y-auto" : "max-h-[200px] overflow-y-auto"}
      >
        {lines.map((l, i) => (
          <p key={i} className="text-xs text-blue-700/70 italic">{l}</p>
        ))}
      </div>
    </div>
  )
}
