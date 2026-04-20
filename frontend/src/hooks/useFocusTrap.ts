"use client"

import { useEffect, type RefObject } from "react"

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ")

/**
 * Traps keyboard focus within a container element while active.
 *
 * - Tab / Shift+Tab cycle through focusable children
 * - Escape calls `onEscape`
 * - Initial focus is set to the first focusable element on activation
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  isActive: boolean,
  onEscape?: () => void,
): void {
  useEffect(() => {
    if (!isActive) return

    const container = containerRef.current
    if (!container) return

    // Focus the first focusable element on activation
    const focusables = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
    if (focusables.length > 0) {
      focusables[0].focus()
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (!container) return

      if (e.key === "Escape") {
        onEscape?.()
        return
      }

      if (e.key !== "Tab") return

      const elements = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      if (elements.length === 0) return

      const first = elements[0]
      const last = elements[elements.length - 1]

      if (e.shiftKey) {
        // Shift+Tab: wrap from first → last
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        // Tab: wrap from last → first
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    container.addEventListener("keydown", handleKeyDown)
    return () => {
      container.removeEventListener("keydown", handleKeyDown)
    }
  }, [containerRef, isActive, onEscape])
}
