import nextPlugin from "@next/eslint-plugin-next"
import reactHooksPlugin from "eslint-plugin-react-hooks"
import tseslint from "typescript-eslint"

export default [
  {
    ignores: [".next/**", "out/**", "build/**", "next-env.d.ts", "node_modules/**"],
  },
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: ["**/*.ts", "**/*.tsx"],
  })),
  {
    files: ["**/*.{js,jsx,mjs,ts,tsx}"],
    plugins: {
      "@next/next": nextPlugin,
      "react-hooks": reactHooksPlugin,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_",
        destructuredArrayIgnorePattern: "^_",
      }],
    },
  },
]
