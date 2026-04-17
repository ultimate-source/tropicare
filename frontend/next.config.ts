import type { NextConfig } from "next";


const nextConfig: NextConfig = {
  // Stream the NDJSON body straight through without buffering.
  // Required for chunked streaming to work end-to-end.
  experimental: {
    serverActions: { bodySizeLimit: "10mb" },  // for file uploads
  },

  // Rewrite /api/* to the FastAPI backend when running in development
  // without Docker (useful for `pnpm dev` against a local gateway).
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return []
    return [
      {
        source:      "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ]
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options",           value: "DENY" },
          { key: "X-Content-Type-Options",     value: "nosniff" },
          { key: "Referrer-Policy",            value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy",         value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ]
  },
}

export default nextConfig
