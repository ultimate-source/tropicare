// ─────────────────────────────────────────────────────────────────────────────
// app/(auth)/login/page.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { useAppStore } from "@/lib/store"

export default function LoginPage() {
  const router   = useRouter()
  const setUser  = useAppStore(s => s.setUser)
  const [email,  setEmail]  = useState("")
  const [pass,   setPass]   = useState("")
  const [error,  setError]  = useState<string | null>(null)
  const [loading,setLoading]= useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await api.auth.login(email, pass)
      setUser(data.user, data.access_token)
      router.push("/chat")
    } catch {
      setError("Identifiants incorrects. Veuillez réessayer.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm space-y-6">

        {/* Logo / title */}
        <div className="text-center">
          <span className="text-3xl">🌿</span>
          <h1 className="mt-2 text-2xl font-semibold text-gray-900">TropiCare</h1>
          <p className="mt-1 text-sm text-gray-500">
            Aide au diagnostic — maladies tropicales · Togo
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border bg-white p-6 shadow-sm">
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 border border-red-200">
              {error}
            </p>
          )}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Adresse e-mail
            </label>
            <input
              id="email" type="email" required autoComplete="email"
              value={email} onChange={e => setEmail(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="medecin@hopital-lome.tg"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Mot de passe
            </label>
            <input
              id="password" type="password" required autoComplete="current-password"
              value={pass} onChange={e => setPass(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit" disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400">
          Réservé au personnel médical habilité · v1.0
        </p>
      </div>
    </div>
  )
}
