// ─────────────────────────────────────────────────────────────────────────────
// app/(auth)/register/page.tsx — Registration form (native HTML, no JS needed)
// ─────────────────────────────────────────────────────────────────────────────

export const dynamic = "force-dynamic"

export default async function RegisterPage(props: {
  searchParams: Promise<{ error?: string; msg?: string }>
}) {
  const params = await props.searchParams
  const hasError = !!params.error
  const errorMsg = params.msg || "Erreur lors de l'inscription. Veuillez réessayer."

  return (
    <div style={{ margin: 0, fontFamily: "system-ui, -apple-system, sans-serif", background: "#f9fafb", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
      <div style={{ width: "100%", maxWidth: "24rem" }}>

        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <span style={{ fontSize: "1.875rem" }}>🌿</span>
          <h1 style={{ marginTop: "0.5rem", fontSize: "1.5rem", fontWeight: 600, color: "#111827" }}>TropiCare</h1>
          <p style={{ marginTop: "0.25rem", fontSize: "0.875rem", color: "#6b7280" }}>
            Créer un compte clinicien
          </p>
        </div>

        <form
          action="/api/auth/register"
          method="POST"
          style={{ display: "flex", flexDirection: "column" as const, gap: "1rem", border: "1px solid #e5e7eb", background: "#fff", padding: "1.5rem", borderRadius: "0.75rem" }}
        >
          {hasError && (
            <p style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", padding: "0.5rem 0.75rem", borderRadius: "0.5rem", fontSize: "0.875rem" }}>
              {errorMsg}
            </p>
          )}
          <div>
            <label htmlFor="email" style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, color: "#374151", marginBottom: "0.25rem" }}>
              Adresse e-mail
            </label>
            <input
              id="email" name="email" type="email" required autoComplete="email"
              placeholder="medecin@hopital-lome.tg"
              style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: "0.5rem", padding: "0.5rem 0.75rem", fontSize: "0.875rem" }}
            />
          </div>
          <div>
            <label htmlFor="password" style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, color: "#374151", marginBottom: "0.25rem" }}>
              Mot de passe
            </label>
            <input
              id="password" name="password" type="password" required autoComplete="new-password"
              placeholder="Min. 10 caractères, 1 majuscule, 1 chiffre"
              style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: "0.5rem", padding: "0.5rem 0.75rem", fontSize: "0.875rem" }}
            />
          </div>
          <input type="hidden" name="role" value="clinician" />
          <button
            type="submit"
            style={{ width: "100%", background: "#2563eb", color: "#fff", border: "none", borderRadius: "0.5rem", padding: "0.5rem 1rem", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer" }}
          >
            Créer le compte
          </button>
        </form>

        <p style={{ textAlign: "center", fontSize: "0.875rem", color: "#6b7280", marginTop: "1rem" }}>
          Déjà un compte ?{" "}
          <a href="/login" style={{ color: "#2563eb", textDecoration: "underline" }}>Se connecter</a>
        </p>
      </div>
    </div>
  )
}
