import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // `server-only` throws outside React Server Components; unit tests import those modules directly.
      "server-only": fileURLToPath(new URL("./test/unit/server-only-stub.ts", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    include: ["test/unit/**/*.test.{ts,tsx}"],
    setupFiles: ["./test/unit/setup.ts"],
    restoreMocks: true,
  },
});
