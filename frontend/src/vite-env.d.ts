/** Vite client types plus the env vars this app reads (§13). */

/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL; defaults to `/api` (nginx proxy), local dev sets `http://localhost:8000/api`. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
