// ─────────────────────────────────────────────────────────────────────────────
// tailwind.config.ts
// ─────────────────────────────────────────────────────────────────────────────
import type { Config } from "tailwindcss"

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      // Animate the thinking dots in ThinkingIndicator
      keyframes: {
        bounce: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":       { transform: "translateY(-4px)" },
        },
      },
      animation: {
        bounce: "bounce 0.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config

