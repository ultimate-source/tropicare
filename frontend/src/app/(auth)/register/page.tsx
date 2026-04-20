// ─────────────────────────────────────────────────────────────────────────────
// app/(auth)/register/page.tsx — Registration form (native HTML, no JS needed)
// ─────────────────────────────────────────────────────────────────────────────

import { cookies } from "next/headers"
import { getServerTranslation } from "@/lib/i18n"

export const dynamic = "force-dynamic"

export default async function RegisterPage(props: {
  searchParams: Promise<{ error?: string; msg?: string }>
}) {
  const params = await props.searchParams
  const hasError = !!params.error
  const errorMsg = params.msg || undefined

  const cookieStore = await cookies()
  const lang = cookieStore.get("tropicare-lang")?.value
  const { t } = getServerTranslation(lang)

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-sm sm:max-w-[24rem]">

        <div className="text-center mb-6">
          <span className="text-3xl">🌿</span>
          <h1 className="mt-2 text-2xl font-semibold text-gray-900">TropiCare</h1>
          <p className="mt-1 text-sm text-gray-500">
            {t("auth.registerTitle")}
          </p>
        </div>

        <form
          action="/api/auth/register"
          method="POST"
          className="flex flex-col gap-4 border border-gray-200 bg-white p-6 rounded-xl"
        >
          {hasError && (
            <p className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
              {errorMsg ?? t("auth.registerError")}
            </p>
          )}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              {t("auth.email")}
            </label>
            <input
              id="email" name="email" type="email" required autoComplete="email"
              placeholder={t("auth.emailPlaceholder")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              {t("auth.password")}
            </label>
            <input
              id="password" name="password" type="password" required autoComplete="new-password"
              placeholder={t("auth.passwordPlaceholder")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <input type="hidden" name="role" value="clinician" />
          <button
            type="submit"
            className="w-full bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium cursor-pointer hover:bg-blue-700 transition-colors"
          >
            {t("auth.register")}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-4">
          {t("auth.hasAccount")}{" "}
          <a href="/login" className="text-blue-600 underline">{t("auth.signIn")}</a>
        </p>
      </div>
    </div>
  )
}
