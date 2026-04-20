// ─────────────────────────────────────────────────────────────────────────────
// lib/store.ts — Zustand session + UI state with split persistence
// ─────────────────────────────────────────────────────────────────────────────
import { create, type StateCreator } from "zustand"
import { persist, type PersistStorage, type StorageValue } from "zustand/middleware"

export interface User {
  id:    string
  email: string
  roles: string[]
}

export interface SessionMeta {
  sessionId: string
  language:  "fr" | "en"
  createdAt: string
}

export interface AppStore {
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

  // Dismissed emergency alerts
  dismissedAlerts: string[]
  dismissAlert: (disease: string) => void
  clearDismissedAlerts: () => void
}

export const AUTH_STORAGE_KEY = "tropicare-auth"
export const PREFS_STORAGE_KEY = "tropicare-prefs"

interface AuthPersist {
  user: User | null
  token: string | null
}

interface PrefsPersist {
  language: "fr" | "en"
  session: SessionMeta | null
  dismissedAlerts: string[]
}

type PersistedSlice = AuthPersist & PrefsPersist

/**
 * Custom storage adapter that splits state across sessionStorage (auth)
 * and localStorage (prefs), merging both on rehydration.
 */
const splitStorage: PersistStorage<PersistedSlice> = {
  getItem: (_name: string): StorageValue<PersistedSlice> | null => {
    if (typeof window === "undefined") return null

    const authRaw = sessionStorage.getItem(AUTH_STORAGE_KEY)
    const prefsRaw = localStorage.getItem(PREFS_STORAGE_KEY)

    const auth: AuthPersist | null = authRaw ? JSON.parse(authRaw) : null
    const prefs: PrefsPersist | null = prefsRaw ? JSON.parse(prefsRaw) : null

    if (!auth && !prefs) return null

    const defaults: PersistedSlice = {
      user: null,
      token: null,
      language: "fr",
      session: null,
      dismissedAlerts: [],
    }

    return {
      state: {
        ...defaults,
        ...(auth ?? {}),
        ...(prefs ?? {}),
      },
      version: 0,
    }
  },

  setItem: (_name: string, value: StorageValue<PersistedSlice>): void => {
    if (typeof window === "undefined") return
    const { state } = value

    const auth: AuthPersist = { user: state.user ?? null, token: state.token ?? null }
    const prefs: PrefsPersist = {
      language: state.language ?? "fr",
      session: state.session ?? null,
      dismissedAlerts: state.dismissedAlerts ?? [],
    }

    sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth))
    localStorage.setItem(PREFS_STORAGE_KEY, JSON.stringify(prefs))
  },

  removeItem: (_name: string): void => {
    if (typeof window === "undefined") return
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
    localStorage.removeItem(PREFS_STORAGE_KEY)
  },
}

const storeCreator: StateCreator<AppStore> = (set) => ({
  user:  null,
  token: null,
  setUser:   (user, token) => set({ user, token }),
  clearUser: () => {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(AUTH_STORAGE_KEY)
      localStorage.removeItem(PREFS_STORAGE_KEY)
    }
    set({ user: null, token: null, session: null, language: "fr", dismissedAlerts: [] })
  },

  session:      null,
  setSession:   (s) => set({ session: s }),
  clearSession: () => set({ session: null }),

  language:      "fr",
  setLanguage:   (l) => {
    if (typeof window !== "undefined") {
      document.cookie = `tropicare-lang=${l}; path=/; SameSite=Lax; max-age=31536000`
    }
    set({ language: l })
  },
  sidebarOpen:   false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  dismissedAlerts: [],
  dismissAlert: (disease) =>
    set((s) => ({
      dismissedAlerts: s.dismissedAlerts.includes(disease)
        ? s.dismissedAlerts
        : [...s.dismissedAlerts, disease],
    })),
  clearDismissedAlerts: () => set({ dismissedAlerts: [] }),
})

export const useAppStore = create<AppStore>()(
  persist<AppStore, [], [], PersistedSlice>(storeCreator, {
    name: "tropicare-split",
    storage: splitStorage,
    partialize: (state): PersistedSlice => ({
      user: state.user,
      token: state.token,
      language: state.language,
      session: state.session,
      dismissedAlerts: state.dismissedAlerts,
    }),
  })
)
