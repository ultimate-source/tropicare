"use client"

import { useCallback, useEffect, useRef, useState, type RefObject } from "react"

const BOTTOM_THRESHOLD = 50

/**
 * Auto-scrolls a container to the bottom when dependencies change,
 * unless the user has manually scrolled up.
 *
 * Returns `isAtBottom` for conditional UI (e.g. "scroll to bottom" button)
 * and `scrollToBottom` to programmatically jump back down.
 */
export function useAutoScroll(
  containerRef: RefObject<HTMLElement | null>,
  dependencies: unknown[],
): { isAtBottom: boolean; scrollToBottom: () => void } {
  const [isAtBottom, setIsAtBottom] = useState(true)
  // Track whether the user manually scrolled away from the bottom
  const userScrolledRef = useRef(false)

  // Update isAtBottom on every scroll event
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    function onScroll() {
      if (!el) return
      const atBottom =
        el.scrollTop + el.clientHeight >= el.scrollHeight - BOTTOM_THRESHOLD
      setIsAtBottom(atBottom)
      userScrolledRef.current = !atBottom
    }

    el.addEventListener("scroll", onScroll, { passive: true })
    return () => el.removeEventListener("scroll", onScroll)
  }, [containerRef])

  // Auto-scroll when dependencies change, only if user hasn't scrolled up
  useEffect(() => {
    const el = containerRef.current
    if (!el || userScrolledRef.current) return

    el.scrollTop = el.scrollHeight
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    userScrolledRef.current = false
    setIsAtBottom(true)
  }, [containerRef])

  return { isAtBottom, scrollToBottom }
}
