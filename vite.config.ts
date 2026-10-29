/** Build the customer page at the repository root and run isolated browser lifecycle tests. */
import { defineConfig } from "vitest/config";

export default defineConfig({
  root: "frontend",
  base: "/",
  build: { outDir: "../dist/chat", emptyOutDir: true },
  server: { proxy: { "/chat/config": "http://127.0.0.1:8000" } },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    clearMocks: true,
  },
});
