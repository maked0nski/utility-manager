import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
    css: true,
    // tests/visual/** are Playwright specs run separately via `npm run test:visual`
    // (playwright.visual.config.ts) - vitest's default include glob picks them up
    // too since they match *.spec.ts, which breaks because they call
    // `test.describe`/`test` from @playwright/test, not vitest's globals.
    exclude: [...configDefaults.exclude, "tests/visual/**"],
  },
});
