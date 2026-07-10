/** Vite + Vitest configuration: React plugin, node-environment unit tests (§2).
 *  Inside the Docker dev container (DOCKER_POLLING=true) file watching falls
 *  back to polling and HMR targets the published port — macOS bind mounts do
 *  not deliver inotify events into a Linux container, so native watching is
 *  silent there. Outside the container this branch is off and nothing changes.
 */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Read the container flag without pulling in @types/node (tsc checks this file).
const dockerPolling =
  (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env?.DOCKER_POLLING === "true";

export default defineConfig({
  plugins: [react()],
  server: dockerPolling
    ? { watch: { usePolling: true, interval: 300 }, hmr: { clientPort: 5173 } }
    : undefined,
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
