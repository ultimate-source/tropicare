// ─────────────────────────────────────────────────────────────────────────────
// lib/store.ts — Zustand session + UI state
// ─────────────────────────────────────────────────────────────────────────────
import { create } from "zustand"

interface User {
  id:    string
  email: string
  roles: string[]
}

interface SessionMeta {
  sessionId: string
  language:  "fr" | "en"
  createdAt: string
}

interface AppStore {
  // Auth
  user:    User | null
  token:   string | null
  setUser: (user: User, token: string) => void
  clearUser: () => void

  // Active session
  session:    SessionMeta | null
  setSession: (s: SessionMeta) => void
  clearSession: () => void

  // UI prefs
  language:     "fr" | "en"
  setLanguage:  (l: "fr" | "en") => void
  sidebarOpen:  boolean
  toggleSidebar: () => void
}

export const useAppStore = create<AppStore>((set) => ({
  user:  null,
  token: null,
  setUser:   (user, token) => set({ user, token }),
  clearUser: () => set({ user: null, token: null }),

  session:      null,
  setSession:   (s) => set({ session: s }),
  clearSession: () => set({ session: null }),

  language:      "fr",
  setLanguage:   (l) => set({ language: l }),
  sidebarOpen:   false,
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
}))
